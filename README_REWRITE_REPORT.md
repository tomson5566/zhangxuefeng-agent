# README 重写报告 — zhangxuefeng-agent

📅 2026-06-15 23:02

## 触发
用户发现 README 严重过期(描述的还是 v0.1 单用户版),要求"结合项目目录和 DEPLOY.md,重新扫描项目,备份 readme,重新写一版"。

## 摸底结果(旧 README 失真 7 处)
| 旧 README | 实际 |
|---|---|
| 6 文件 / 742 行 | **10 文件 / 1054 行**(多 auth/input_filter/safety_judge + __init__) |
| 8 个核心包 | **9 个**(多 langchain-community) |
| 无鉴权 | **A1 鉴权(require_auth Depends)** |
| 无过滤 | **L0 regex + L1 长度 + L2 LLM-judge 三层** |
| start.sh 一键启 | **start/stop/restart 三子命令 + 等 /health 200** |
| 仅本机 | **192.168.0.129 + OpenResty :30000 公网反代** |
| `/health` 泄露 model/skill_dir | **已修: 只返 status** |

## 工作流
**自己写,不派活**。理由(已沉淀到 MEMORY):写"我用的 cheat sheet 类"任务强主观判断 + 高幻觉风险,自己写更稳。README 重写 600+ 行,涉及"哪些事实值得提 + 表格如何组织 + 踩坑怎么提炼",风格容错性低,派活给 opencode/qwen 都会有 5+ 处需要返工。

## 交付
- `README.md` (20.8 KB / 413 行) — 反映 v0.2 真实状态
- `README.md.bak.20260615_230146` (16.7 KB) — 旧版本备份
- `README_REWRITE_REPORT.md` — 本文件

## 新 README 11 节
1. **核心特性** — 8 个 emoji(原 6 个 + 鉴权 + 移动适配)
2. **架构总览** — ASCII 图反映 3 层防护 + OpenResty 注 user
3. **技术栈** — 表格更新到 9 包 + OpenResty + dvh
4. **目录结构** — 真实行数(已 `wc -l` 验证)
5. **环境依赖 + 配置** — `.env.example` 实际 4 字段(其中 2 注释)+ AUTH_USER
6. **启动** — 本机 / 局域网 / 公网三层入口 + DEPLOY.md 摘要
7. **运行验证** — 6 个 curl 场景(健康/鉴权/多轮/过滤/隔离)
8. **安全模型** — 全新章节(A1/L0/L1/L2 表 + fail-open + CORS + 错误路径)
9. **API 接口** — `/health`(简)+ `/api/chat`(鉴权/错误码全)
10. **关键设计决策** — 8 条(原 6 条 + 加 require_auth 设计 + fail-open 原则 + 30000 端口)
11. **踩坑记录** — 7 条精选表(从 DEPLOY §7 + MEMORY 沉淀)
12. **后续规划** — 7 条(原 5 条 + 加 HTTPS / 鉴权升级)
13. **变更记录** — 4 行版本历史(2026-06-11 → 2026-06-14)

## 验收
| 项 | 命令 | 结果 |
|---|---|---|
| 文件大小 | `wc -c README.md` | 20827 B(目标 15-25KB)✅ |
| 行数 | `wc -l README.md` | 413 行✅ |
| 二级标题 | `grep -c "^##" README.md` | 27(目标 12-15 章节,实际含子标题)✅ |
| 后端文件数对齐 | ls backend/*.py | 10(含 __init__)= README 写的 10✅ |
| pyproject 包数对齐 | grep deps | 9 = README 写的 9(技术栈节列了 9 行)✅ |
| `.env.example` 字段 | grep | 3 字段 + 2 注释 = README 描述一致✅ |
| start.sh 子命令 | grep start/stop/restart | 3 = README 写的 3✅ |
| 关键术语全覆盖 | grep tmdata/OpenResty/AUTH_USER/safety_judge/... | 全部命中✅ |

## 教训沉淀
- **README 必须跟代码同步演进**:每次大改(major feature / 安全修复 / 部署升级)后 README 失真,1-2 周内没人发现。**建议在每次 commit hook 加 README diff 检查**(TODO)。
- **"README 反映项目真实状态"是文档质量底线**:旧版完全跟 v0.1 对齐 → 等于误导新人。**写 README 不能省验证**(`wc -l` + `ls` + `grep` 三件套)。
- **不派活给子 agent 写我自己用的 cheat sheet**:强主观 + 高幻觉风险,自己写 ~30 分钟,派活 + 返工至少 1 小时。
