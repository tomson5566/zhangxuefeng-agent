// PUBLIC_FIX_v1 - public deployment fix (auto-applied; do not edit by hand)
// 反代后 API 和前端同源,用相对路径。nginx 把 /api/* 转发到后端 :8000。
// 留个 fallback:同源失败时回退到当前 host :8000 直连(供调试)
const API_BASE = '';

// ==================== Session ID(多轮记忆)====================
// 首次访问生成 UUID 放 localStorage,后续复用 — 同一浏览器同一会话
function getSessionId() {
    let sid = null;
    try { sid = localStorage.getItem('zx_session_id'); } catch (_) {}
    if (!sid || !/^[0-9a-f-]{8,128}$/i.test(sid)) {
        // crypto.randomUUID 在所有现代浏览器 + 局域网 IP 都可用
        sid = (window.crypto && crypto.randomUUID)
            ? crypto.randomUUID()
            : 'sess-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
        try { localStorage.setItem('zx_session_id', sid); } catch (_) {}
    }
    return sid;
}
const SESSION_ID = getSessionId();

// ==================== Markdown 渲染 ====================
// marked.js 从 CDN 加载,失败时降级到纯文本(不阻塞聊天)
if (window.marked) {
    marked.setOptions({
        gfm: true,           // 启用 GitHub Flavored Markdown(表格、删除线等)
        breaks: true,        // 单换行变 <br>,聊天场景友好
        headerIds: false,    // 不生成 id
        mangle: false,
    });
    // 简单 XSS 防护:剥掉 <script> 块
    const _origParse = marked.parse.bind(marked);
    marked.parse = (md) => _origParse(md).replace(/<script[\s\S]*?<\/script>/gi, '');
}

function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

function renderMarkdown(md) {
    if (window.marked) {
        try {
            return marked.parse(md);
        } catch (e) {
            console.warn('marked.parse failed:', e);
            return escapeHtml(md);
        }
    }
    return escapeHtml(md);
}
// =====================================================

const form = document.getElementById('chat-form');
const input = document.getElementById('question-input');
const messages = document.getElementById('messages');
const sendBtn = document.getElementById('send-btn');

function appendMessage(role, text) {
    messages.classList.remove('has-empty');
    const div = document.createElement('div');
    div.className = `message message-${role}`;
    if (role === 'agent') {
        // Agent 输出走 markdown:dataset 存原始文本,innerHTML 存渲染结果
        div.dataset.markdown = text || '';
        div.innerHTML = renderMarkdown(div.dataset.markdown);
    } else {
        // 用户消息是纯文本,绝对不要渲染 HTML
        div.textContent = text;
    }
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
}

function setStreaming(bubble, on) {
    if (on) bubble.classList.add('streaming');
    else bubble.classList.remove('streaming');
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;

    appendMessage('user', q);
    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;
    input.disabled = true;

    const agentBubble = appendMessage('agent', '');
    setStreaming(agentBubble, true);

    const url = `${API_BASE}/api/chat?q=${encodeURIComponent(q)}`;

    try {
        const resp = await fetch(url, {
            method: 'GET',
            headers: { 'X-Session-ID': SESSION_ID },
        });
        if (!resp.ok || !resp.body) {
            // 404 / 502 / connection refused — 给用户具体指引
            let hint = '';
            if (resp.status === 404) {
                hint = '（后端路由没找到，请确认 http://localhost:8000/health 返回 ok）';
            } else if (resp.status === 0 || resp.status >= 500) {
                hint = `（后端没起来，试试浏览器单独访问 ${API_BASE}/health）`;
            }
            throw new Error(`HTTP ${resp.status} ${hint}`.trim());
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            // SSE: data: <payload>\n\n
            let sep;
            while ((sep = buffer.indexOf('\n\n')) !== -1) {
                const evt = buffer.slice(0, sep);
                buffer = buffer.slice(sep + 2);
                if (!evt.startsWith('data: ')) continue;
                const raw = evt.slice(6);
                if (raw === '[DONE]') {
                    setStreaming(agentBubble, false);
                    continue;
                }
                if (raw.startsWith('[ERROR]')) {
                    agentBubble.dataset.markdown += `\n\n[出错了: ${raw.slice(7)}]`;
                    agentBubble.innerHTML = renderMarkdown(agentBubble.dataset.markdown);
                    setStreaming(agentBubble, false);
                    continue;
                }
                // 后端用 json.dumps({"t": ...}) 编码 payload,正常路径走 JSON.parse
                // 兜底:万一 JSON 解析失败(双转义 / 损坏 / 老格式),尝试从
                //       {"t":"..."} 字面量里用正则抢救出 token 文本
                let token = '';
                try {
                    const obj = JSON.parse(raw);
                    token = obj.t || '';
                } catch {
                    let s = raw;
                    const m = s.match(/\{"t"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}/);
                    if (m) {
                        token = m[1]
                            .replace(/\\n/g, '\n')
                            .replace(/\\"/g, '"')
                            .replace(/\\\\/g, '\\');
                    } else {
                        // 真的兜不住,原样显示
                        token = s;
                    }
                }
                if (!token) continue;
                agentBubble.dataset.markdown += token;
                agentBubble.innerHTML = renderMarkdown(agentBubble.dataset.markdown);
                messages.scrollTop = messages.scrollHeight;
            }
        }
    } catch (err) {
        agentBubble.dataset.markdown += `\n[网络/读取错误: ${err.message}]`;
        agentBubble.innerHTML = renderMarkdown(agentBubble.dataset.markdown);
        setStreaming(agentBubble, false);
    } finally {
        sendBtn.disabled = false;
        input.disabled = false;
        input.focus();
    }
});

// 自动撑高 textarea
input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
});

// Ctrl/Cmd+Enter 提交
input.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        form.requestSubmit();
    }
});

// 初始空状态提示
messages.classList.add('has-empty');
