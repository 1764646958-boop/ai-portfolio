# Session 1 · 后端代理层基础（4.1-4.7 + 4.11 骨架 + 前端脚手架）—— Kimi Code 执行稿

> **运行方式**：SSH 登录服务器 → `cd /opt/team-console && kimi --yolo -m kimi-code/k3-256k` → 粘贴**本稿全文**。
> （或非交互：`kimi -m kimi-code/k3-256k -p "$(cat /opt/team-console/prompts/工具版/Session1-KimiCode执行稿.md)"`）
> 本稿为**一次性完整执行**设计：先读前置文件与规格 → 按序实现 → 每项 curl 自测 → 写报告 → 停止。

---

## 0. 开工前置（必须先做）

1. 完整读取 `/opt/team-console/SPEC.md`（重点：三、接口边界；四、决策清单 D2/D7/D8/D9/D14/D18/D19/D22/D28/D29；五、第 3 阶段；五、第 4 阶段 4.1-4.7 与 **4.11**；五、第 9 阶段验收项 1/2/5/6/10/12/**16**）
2. 读取上一批报告 `/opt/team-console/reports/Session0-环境部署报告.md`（拿到 4 端口、API_SERVER_KEY、目录约定、延后项）
3. 建目录：`/opt/team-console/server/`（Node/Express，端口 8787）、`/opt/team-console/data/`（agents.json / conversations.db / files.json）、前端项目 `/opt/team-console/team-console/`（Vite 脚手架建于此）

## 1. 你的角色

资深 Node.js/Express 后端工程师。严格按规格实现，**不发明规格外的接口**。

## 2. 本批次范围（严格限定）

**做：**
1. 初始化 Node 后端项目（Express + 必要依赖），端口 **8787**，systemd 托管（开机自启）
2. **4.1 基础 API**：`/api/chat`（按 agents.json 路由 + **SSE 流式透传**）、`/api/kanban`（只读 SQLite）、`/api/kanban-command`、`/api/poll`（mtime 增量）
3. **4.2 懒启动进程管理**：探活 / 拉起 / 60s 超时 / 空闲 30min 停止 / 端口预分配 **8650+** / 文件锁
4. **4.3 认证**：register（首个即管理员）/ login / me / members / approve（**JWT httpOnly cookie**）
5. **4.4 Agent 管理**：agents.json 读写、创建（`profile create --clone` + 覆盖 SOUL.md + 端口分配）、删除 / 停用
6. **4.5 文件与资料库**：`/api/files`（≤10MB multipart）、`/api/links`、下载、删除（仅管理员）
7. **4.6 团队会话**：conversations.db 三表、私聊 / 群聊 CRUD、@ 通知解析、**5 分钟撤回**
8. **4.7 通知**：`/api/poll` 读系统通知目录
9. **N4 验证**：向 8642 发带自定义 system 消息的请求 → 记录「方案 A 或 B」→ 写入部署说明
10. **4.11 MCP 网关骨架（v3.1/D28）**：8787 增加 `/mcp` 端点（Streamable HTTP，Bearer 复用 JWT）；
    先暴露 **`kanban_list`**（包装 /api/kanban）与 **`file_search`**（包装 /api/files）；
    `memory_search`/`memory_add`/`task_create` **留接口位**（返回"服务未就绪"，Session 2 填充）
11. **前端脚手架**：Vite + Vue3 + TS + Pinia + Tailwind，**只搭登录页 + 主布局空壳**

**不做：**
- ❌ 4.8 任务中心 / 4.9 记忆库 / 4.10 闭环（Session 2）
- ❌ 前端业务页面（Session 2/3）
- ❌ 接入任何外部 MCP server（4.11.2 默认关闭，本批只做暴露侧）

## 3. 执行要求

1. 每个 API 实现后**立即 curl 自测**（注册→登录→发消息→传文件→撤回→懒启动拉起）
2. 数据文件放 `/opt/team-console/data/`；密钥只进 `.env`
3. 懒启动的「正在唤醒」状态要在 /api/chat 响应流中体现（**先发一条 SSE 事件**）
4. **顺序提醒**：N4 验证（范围第 9 条）必须在 4.6 的 @Agent 上下文注入逻辑落地**前**完成（SPEC 八、约束：注入方式 A/B 由 N4 实测决定）
5. 约束：只使用 SPEC「接口边界」清单里的通道（**禁止发明后端 API**）；决策清单不得偏离；前端不接触任何密钥；不确定参数以实际命令输出为准

## 4. 本批验收（全部通过才能交接）

1. 注册首个账号成为管理员；第二个注册后待批准；批准后可登录
2. 成员 A 私聊 B：后端增量拉取正确（准实时前端由 S2 做）
3. 上传 ≤10MB 文件成功可下载；加网盘链接成功；管理员可删
4. 消息 5 分钟内撤回；撤回后读取显示"已撤回"
5. 懒启动：建测试 Agent → 首次 /api/chat 触发拉起（60s 内可对话）→ 空闲后自动停止
6. N4 验证完成，结论（A/B）写入部署说明
7. **MCP 骨架**：MCP 客户端连接 `/mcp` 握手成功；`kanban_list`、`file_search` 可调用返回结果；`memory_search` 返回"服务未就绪"
8. `reboot` 后后端服务自动恢复

## 5. 交付物（写成文件）

写入 **`/opt/team-console/reports/Session1-后端自测报告.md`**：
1. 《后端 API 自测报告》：每端点 curl 命令 + 响应摘要
2. agents.json 当前内容（4 预设 + 测试 Agent）
3. N4 验证结论（A 或 B）
4. 前端脚手架状态（已生成哪些文件）
5. **MCP 骨架说明**：/mcp 端点、已暴露工具、留位工具、握手验证方式
6. **给 Session 2 的注意事项**：路由约定、端口占用、.env 已有项、**MCP 留位接口签名**

## 6. 结束动作

在对话中输出：报告路径 + 验收结论摘要，然后**停止**——不要顺手开始 Session 2 的工作（4.8/4.9/4.10 属跨批）。
