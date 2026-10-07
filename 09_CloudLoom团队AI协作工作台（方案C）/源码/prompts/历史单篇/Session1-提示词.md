# Session 1 · 后端代理层基础 — AI Coding 任务提示词（可直接粘贴）

> 用法：把【前置状态】粘贴 Session 0 的《环境部署报告》关键内容后，将**本文件全文**粘贴给 AI Coding 工具。
> 本批做完后：检查《后端 API 自测报告》+ N4 结论 → 填进 Session 2 提示词的【前置状态】。

# Session 1 · 后端代理层基础（4.1-4.7）

## 你的角色
资深 Node.js/Express 后端工程师。严格按规格实现，不发明规格外的接口。

## 规格文件（必读）
`/opt/team-console/SPEC.md`——完整读取，重点章节：三、接口边界；四、决策清单（D2/D7/D8/D9/D14/D18/D19/D22/D28/D29）；五、第 3 阶段；五、第 4 阶段（4.1-4.7、**4.11 MCP 网关**）；五、第 9 阶段验收项 1/2/5/6/10/12/**16**。

## 项目环境
- 工作目录：`/opt/team-console/team-console`（若不存在则创建；前端项目脚手架一并在此创建，本批只搭骨架）
- 后端代码目录：`/opt/team-console/server/`（Node/Express，端口 8787）
- 前置状态（Session 0 已完成）：【粘贴 Session 0 的《环境部署报告》关键内容】

## 本批次范围（严格限定）
**做：**
1. 初始化 Node 后端项目（Express + 必要依赖），端口 8787，systemd 托管
2. 实现 4.1 基础 API：`/api/chat`（按 agents.json 路由 + SSE 流式透传）、`/api/kanban`（只读 SQLite）、`/api/kanban-command`、`/api/poll`（mtime 增量）
3. 实现 4.2 懒启动进程管理（探活/拉起/60s 超时/空闲 30min 停止/端口预分配 8650+ / 文件锁）
4. 实现 4.3 认证：register（首个为管理员）/login/me/members/approve（JWT httpOnly cookie）
5. 实现 4.4 Agent 管理：agents.json 读写、创建（profile create --clone + 覆盖 SOUL.md + 端口分配）、删除/停用
6. 实现 4.5 文件与资料库：/api/files（≤10MB multipart）、/api/links、下载、删除（管理员）
7. 实现 4.6 团队会话：conversations.db 三表、私聊/群聊 CRUD、@ 通知解析、5 分钟撤回
8. 实现 4.7 通知：/api/poll 读系统通知目录
9. **N4 验证**：向 8642 发带自定义 system 消息的请求，记录"方案 A 或 B"，写入部署说明
10. **实现 4.11 MCP 网关骨架（v3.1 新增，D28）**：在 8787 增加 `/mcp` 端点
    （Streamable HTTP，Bearer 认证复用现有 JWT），先暴露**不依赖 4.8/4.9 的工具**
    （`kanban_list` 包装 /api/kanban、`file_search` 包装 /api/files）；
    `memory_search`/`memory_add`/`task_create` 的包装**留接口位**（返回"服务未就绪"，
    Session 2 填充）——保证本批 MCP 端点可握手、可调用 2 个工具即可
11. 创建前端项目脚手架（Vite + Vue3 + TS + Pinia + Tailwind），只搭登录页 + 主布局空壳

**不做：**
- ❌ 不实现任务中心（4.8）——Session 2 的事
- ❌ 不实现记忆库（4.9）——Session 2 的事
- ❌ 不实现前端聊天/看板等页面——Session 2/3 的事
- ❌ 不实现闭环（4.10）——Session 2 的事
- ❌ 不接入任何外部 MCP server（4.11.2 默认关闭）——本期仅实现暴露侧

## 执行要求
1. 每个 API 实现后立即用 curl 自测（注册→登录→发消息→传文件→撤回→懒启动拉起）
2. 数据文件放 `/opt/team-console/data/`（agents.json / conversations.db / files.json）
3. 密钥只进 `.env`（API_SERVER_KEY 从 Session 0 报告获取）
4. 懒启动的"正在唤醒"状态要在 /api/chat 响应流中体现（先发一条 SSE 事件）

## 本批验收标准（全部通过才能交接）
1. 注册第一个账号成为管理员；第二个账号注册后待批准；管理员批准后可登录
2. 成员 A 私聊成员 B，消息准实时（轮询 3-5s 由前端实现，本批验证后端增量拉取正确）
3. 上传 ≤10MB 文件成功，可下载；加网盘链接成功；管理员可删
4. 发送消息后 5 分钟内撤回，撤回后读取显示"已撤回"
5. 懒启动：手动建一个测试 Agent（用 API 或 CLI），首次 /api/chat 触发拉起，60s 内可对话；空闲后停止
6. N4 验证完成，结论（A/B）写入部署说明
7. **MCP 网关骨架（v3.1）**：MCP 客户端连接 `/mcp` 握手成功；`kanban_list` 和
   `file_search` 可调用返回结果；`memory_search` 返回"服务未就绪"（符合留位设计）
8. `reboot` 后后端服务自动恢复

## 交接物（Session 1 结束必须输出）
1. 《后端 API 自测报告》：每个端点的 curl 命令 + 响应摘要
2. agents.json 当前内容（含 4 个预设 + 测试 Agent）
3. N4 验证结论（方案 A 或 B）
4. 前端脚手架状态说明（已生成哪些文件）
5. **MCP 网关骨架说明**：/mcp 端点、已暴露工具清单、留位工具清单、握手验证方式
6. 给 Session 2 的注意事项（路由约定、端口占用、.env 已有项、MCP 留位接口签名）

## 约束
- 只使用 SPEC「接口边界」清单里的通道，**禁止发明后端 API**
- 决策清单不得偏离；前端不接触任何密钥（全部经 8787 代理）
- 不确定参数以实际命令输出为准

---
