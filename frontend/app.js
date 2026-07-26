/* ============ 状态管理 ============ */
const STORAGE = {
    chats: 'xf_chats',
    curId: 'xf_cur',
    dark: 'xf_dark',
};

let state = {
    chats: {},          // {id: {name, msgs: [{role, content}], uploaded: [{filename, size, ext, saved_path}]}}
    curId: null,
    sessionId: null,    // 后端 session_id(每次刷新变化)
    uploading: false,
    curAgent: 'zhangxuefeng',  // 当前 AI 角色(zhangxuefeng | zhongkao)
};

/* ============ Session ID 管理 ============ */
function getSessionId() {
    if (!state.sessionId) {
        state.sessionId = 'web-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);
    }
    return state.sessionId;
}

/* ============ localStorage ============ */
function saveState() {
    try {
        localStorage.setItem(STORAGE.chats, JSON.stringify(state.chats));
        localStorage.setItem(STORAGE.curId, state.curId || '');
    } catch (e) { console.warn('localStorage save failed:', e); }
}
function loadState() {
    try {
        const raw = localStorage.getItem(STORAGE.chats);
        if (raw) state.chats = JSON.parse(raw);
        const curId = localStorage.getItem(STORAGE.curId);
        if (curId && state.chats[curId]) state.curId = curId;
    } catch (e) { console.warn('localStorage load failed:', e); }
}
function saveDark(dark) {
    localStorage.setItem(STORAGE.dark, dark ? '1' : '');
}
function loadDark() {
    return localStorage.getItem(STORAGE.dark) === '1';
}

/* ============ 对话管理 ============ */
function newChat() {
    const id = 'c' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
    state.chats[id] = {
        name: '新对话',
        msgs: [],
        uploaded: [],
        createdAt: Date.now(),
    };
    state.curId = id;
    saveState();
    renderChatList();
    renderMessages();
    renderChips();
}
function delChat(id) {
    if (!state.chats[id]) return;
    if (!confirm('确定删除这个对话?')) return;
    delete state.chats[id];
    if (state.curId === id) state.curId = null;
    if (!state.curId && Object.keys(state.chats).length > 0) {
        state.curId = Object.keys(state.chats)[0];
    }
    if (Object.keys(state.chats).length === 0) {
        newChat();
        return;
    }
    saveState();
    renderChatList();
    renderMessages();
    renderChips();
}
function getCurChat() {
    if (!state.curId || !state.chats[state.curId]) return null;
    return state.chats[state.curId];
}
function updateCurName() {
    const chat = getCurChat();
    if (!chat) return;
    const firstUser = chat.msgs.find(m => m.role === 'u');
    if (firstUser && firstUser.content) {
        chat.name = firstUser.content.slice(0, 18).replace(/\n/g, ' ');
    }
    saveState();
    renderChatList();
}

/* ============ 渲染 ============ */
function renderChatList() {
    const el = document.getElementById('chatList');
    const ids = Object.keys(state.chats).sort((a, b) =>
        (state.chats[b].createdAt || 0) - (state.chats[a].createdAt || 0)
    );
    if (ids.length === 0) {
        el.innerHTML = '<div class="list-empty">暂无对话<br>点下方按钮创建</div>';
        return;
    }
    el.innerHTML = ids.map(id => {
        const c = state.chats[id];
        const on = id === state.curId ? ' on' : '';
        return `<div class="item${on}" data-id="${id}">
            <span class="name">${escapeHtml(c.name)}</span>
            <span class="del" data-del="${id}">×</span>
        </div>`;
    }).join('');
    // 绑定事件
    el.querySelectorAll('.item').forEach(item => {
        item.addEventListener('click', e => {
            if (e.target.dataset.del) return;
            state.curId = item.dataset.id;
            saveState();
            renderChatList();
            renderMessages();
            renderChips();
        });
    });
    el.querySelectorAll('.del').forEach(del => {
        del.addEventListener('click', e => {
            e.stopPropagation();
            delChat(del.dataset.del);
        });
    });
}

function renderMessages() {
    const el = document.getElementById('messages');
    const chat = getCurChat();
    if (!chat || chat.msgs.length === 0) {
        el.innerHTML = `<div class="welcome">
            <div class="icon">🎓</div>
            <h2>高考志愿 · 用就业倒推法给你说实话</h2>
            <p>输入分数 / 选科 / 想去哪,让张雪峰给你盘</p>
        </div>`;
        return;
    }
    el.innerHTML = chat.msgs.map(m => bubbleHtml(m)).join('');
    el.scrollTop = el.scrollHeight;
}

function bubbleHtml(m) {
    if (m.role === 'thinking') {
        return '<div class="thinking">张雪峰思考中</div>';
    }
    const cls = m.role === 'u' ? 'u' : 'a';
    const who = m.role === 'u' ? '你' : '张雪峰';
    const content = m.role === 'a' ? renderMarkdown(m.content) : escapeHtml(m.content);
    return `<div class="bubble ${cls}">
        <div class="who">${who}</div>
        <div class="content">${content}</div>
    </div>`;
}

function renderMarkdown(text) {
    if (window.marked && window.marked.parse) {
        try { return window.marked.parse(text); }
        catch (e) { return escapeHtml(text); }
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function renderChips() {
    const chat = getCurChat();
    const uploaded = chat ? chat.uploaded : [];
    const wrap = document.getElementById('fileChips');
    const list = document.getElementById('chipsList');
    const count = document.getElementById('chipCount');
    count.textContent = uploaded.length;
    if (uploaded.length === 0) {
        wrap.hidden = true;
        return;
    }
    wrap.hidden = false;
    list.innerHTML = uploaded.map((f, i) => {
        const icon = extIcon(f.ext);
        const sizeKb = Math.round(f.size / 1024 * 10) / 10;
        return `<div class="chip" data-i="${i}">
            <span class="icon">${icon}</span>
            <span class="name">${escapeHtml(f.filename)}</span>
            <span class="size">${sizeKb}KB</span>
            <span class="del" data-del-i="${i}">×</span>
        </div>`;
    }).join('');
    list.querySelectorAll('.del').forEach(d => {
        d.addEventListener('click', e => {
            const i = parseInt(d.dataset.delI);
            const chat = getCurChat();
            if (chat) {
                chat.uploaded.splice(i, 1);
                saveState();
                renderChips();
            }
        });
    });
}

function extIcon(ext) {
    const m = {
        '.txt': '📄', '.md': '📝',
        '.docx': '📘', '.xlsx': '📊',
        '.pdf': '📕', '.pptx': '📙',
    };
    return m[ext] || '📎';
}

/* ============ 上传 ============ */
async function uploadFiles(fileList) {
    if (state.uploading) {
        toast('正在上传中,请稍候', 'error');
        return;
    }
    const btn = document.getElementById('uploadBtn');
    const files = Array.from(fileList);
    const ALLOWED = ['.txt', '.md', '.docx', '.xlsx', '.pdf', '.pptx'];
    const MAX = 50 * 1024 * 1024;  // 50MB

    for (const file of files) {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!ALLOWED.includes(ext)) {
            toast(`不支持的格式: ${ext} (仅 ${ALLOWED.join(',')})`, 'error');
            continue;
        }
        if (file.size > MAX) {
            toast(`文件过大: ${file.name} (${Math.round(file.size/1024/1024)}MB > 50MB)`, 'error');
            continue;
        }
        state.uploading = true;
        btn.classList.add('uploading');
        try {
            const fd = new FormData();
            fd.append('file', file);
            const r = await fetch(`/api/upload?session_id=${encodeURIComponent(getSessionId())}`, {
                method: 'POST',
                body: fd,
            });
            if (!r.ok) {
                const err = await r.text();
                throw new Error(`HTTP ${r.status}: ${err.slice(0, 100)}`);
            }
            const meta = await r.json();
            const chat = getCurChat();
            if (chat) {
                chat.uploaded.push({
                    filename: meta.filename,
                    size: meta.size,
                    ext: meta.ext,
                    saved_path: meta.saved_path,
                });
                saveState();
                renderChips();
            }
            toast(`已上传: ${file.name}`, 'success');
        } catch (e) {
            toast(`上传失败: ${e.message}`, 'error');
        } finally {
            state.uploading = false;
            btn.classList.remove('uploading');
        }
    }
    document.getElementById('fileInput').value = '';   // 清空以便同名再上传
}

/* ============ Toast ============ */
function toast(msg, type) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast' + (type === 'error' ? ' error' : '');
    el.hidden = false;
    clearTimeout(el._t);
    el._t = setTimeout(() => { el.hidden = true; }, 3000);
}

/* ============ 聊天流式 ============ */
async function sendChat(question) {
    const chat = getCurChat();
    if (!chat) return;
    // 1. 拼 user 消息
    chat.msgs.push({ role: 'u', content: question });
    // 2. 拼 thinking 泡(LLM 思考中)
    chat.msgs.push({ role: 'thinking', content: '' });
    // 3. 拼 AI 占位(流式填充)
    const aiMsg = { role: 'a', content: '' };
    chat.msgs.push(aiMsg);
    saveState();
    updateCurName();
    renderMessages();
    setStatus('thinking');

    // 4. fetch SSE
    try {
        const url = `/api/chat?q=${encodeURIComponent(question)}`;
        const r = await fetch(url, {
            headers: {
                'X-Session-ID': getSessionId(),
                'X-Agent-Name': state.curAgent || 'zhangxuefeng',
            }
        });
        if (!r.ok || !r.body) {
            throw new Error(`HTTP ${r.status}`);
        }
        // 5. 流式读
        const reader = r.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        let firstChunk = true;
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            // 拆 SSE 帧 (\n\n 分隔)
            let idx;
            while ((idx = buf.indexOf('\n\n')) !== -1) {
                const frame = buf.slice(0, idx);
                buf = buf.slice(idx + 2);
                const line = frame.replace(/^data:\s*/, '').trim();
                if (line === '[DONE]') continue;
                try {
                    const obj = JSON.parse(line);
                    if (obj.t) {
                        // 第一次收到 token,移除 thinking 占位
                        if (firstChunk) {
                            const thinkIdx = chat.msgs.findIndex(m => m.role === 'thinking');
                            if (thinkIdx !== -1) chat.msgs.splice(thinkIdx, 1);
                            firstChunk = false;
                        }
                        aiMsg.content += obj.t;
                        renderMessages();
                    }
                } catch (e) { /* skip invalid JSON */ }
            }
        }
    } catch (e) {
        const thinkIdx = chat.msgs.findIndex(m => m.role === 'thinking');
        if (thinkIdx !== -1) chat.msgs.splice(thinkIdx, 1);
        aiMsg.content += `\n\n[错误: ${e.message}]`;
        renderMessages();
    } finally {
        setStatus('ready');
        saveState();
    }
}

function setStatus(s) {
    const el = document.getElementById('status');
    if (s === 'thinking') {
        el.textContent = '思考中';
        el.classList.add('thinking');
    } else {
        el.textContent = '已就绪';
        el.classList.remove('thinking');
    }
}

/* ============ 主题切换 ============ */
function toggleDark() {
    document.body.classList.toggle('dark');
    saveDark(document.body.classList.contains('dark'));
}

async function loadAgents() {
    const sel = document.getElementById('agent-select');
    if (!sel) return;
    try {
        const r = await fetch('/api/agents');
        if (!r.ok) return;
        const d = await r.json();
        sel.innerHTML = '';
        d.agents.forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.name;
            opt.textContent = a.display_name;
            sel.appendChild(opt);
        });
        const last = localStorage.getItem('xf_agent');
        if (last && d.agents.find(a => a.name === last)) {
            sel.value = last;
        }
        state.curAgent = sel.value || 'zhangxuefeng';
    } catch (e) {
        console.warn('loadAgents failed:', e);
        state.curAgent = 'zhangxuefeng';
    }
}

/* ============ 事件绑定 ============ */
function bindEvents() {
    // 新建对话
    document.getElementById('newBtn').addEventListener('click', newChat);
    // 主题切换
    document.getElementById('themeBtn').addEventListener('click', toggleDark);
    // 移动端侧边栏开关
    document.getElementById('menuBtn').addEventListener('click', () => {
        document.getElementById('side').classList.toggle('open');
    });

    // 发送(表单 submit)
    document.getElementById('chat-form').addEventListener('submit', e => {
        e.preventDefault();
        const ta = document.getElementById('question-input');
        const q = ta.value.trim();
        if (!q) return;
        ta.value = '';
        sendChat(q);
    });

    // textarea: Enter 发送, Shift+Enter 换行
    document.getElementById('question-input').addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            document.getElementById('chat-form').requestSubmit();
        }
    });

    // 上传
    document.getElementById('fileInput').addEventListener('change', e => {
        if (e.target.files && e.target.files.length > 0) {
            uploadFiles(e.target.files);
        }
    });

    // agent 切换
    const agentSel = document.getElementById('agent-select');
    if (agentSel) {
        agentSel.addEventListener('change', e => {
            state.curAgent = e.target.value;
            localStorage.setItem('xf_agent', state.curAgent);
            toast(`已切换到: ${e.target.options[e.target.selectedIndex].textContent}`);
        });
    }
}

/* ============ 启动 ============ */
function init() {
    // 1. localStorage 恢复
    loadState();
    // 2. 主题恢复
    if (loadDark()) document.body.classList.add('dark');
    // 3. 没有对话就建一个
    if (Object.keys(state.chats).length === 0) {
        newChat();
    } else if (!state.curId) {
        state.curId = Object.keys(state.chats).sort((a, b) =>
            (state.chats[b].createdAt || 0) - (state.chats[a].createdAt || 0)
        )[0];
        saveState();
    }
    // 4. 渲染
    renderChatList();
    renderMessages();
    renderChips();
    // 5. 事件
    bindEvents();
    // 6. session id 预生(让前端稳定)
    getSessionId();
    // 7. 加载 agent 列表
    loadAgents();
}

init();
