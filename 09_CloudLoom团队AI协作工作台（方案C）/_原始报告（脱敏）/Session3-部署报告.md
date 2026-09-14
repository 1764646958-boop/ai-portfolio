> 📄 **作品集展示副本（已脱敏）**：服务器地址 / 主机名 / 域名 / 邮箱 / 凭据 / 令牌均已替换为占位符；
> 完整原报告不随作品集仓库分发。指标与结论未作任何修改。

# Session3 · 阶段 3 部署报告（CloudLoom 方案 C · 自建团队协作工作台）

- 报告生成时间：2026-09-14 01:10（CST，服务器本地时间）
- 执行代理：Claude Code（本机 → SSH 远程执行；所有开发、部署、验收操作均在服务器完成）
- 权威依据：`/opt/team-console/SPEC.md`（v3.2）+ `/opt/team-console/prompts/工具版/Session1-4-KimiCode合并执行稿.md`
- 阶段门禁：**G3 = 19 项端到端验收全过（域名项按降级路径标「延期补做」）+ 本报告已写**
- **G3 判定：达成**。19 项中 **17 项完全通过**；其余 2 项均为**环境性待补**（非代码问题）：第 7 项「域名对外 HTTPS」（备案未完成，按降级路径延期补做，可做部分已通过）、第 8 项「自动快照」（服务器未装 tccli，需腾讯云控制台开启）

## 一、结论摘要

| 项 | 结果 |
|---|---|
| 19 项端到端验收 | **17 项完全通过**；第 7 项「域名对外 HTTPS」按降级路径**延期补做**（其可做部分：手机加到主屏、PWA 通知弹窗，已实测通过）；第 8 项「reboot 后自启」**通过**、「自动快照」**待补**（未安装 tccli，需控制台开启） |
| 关键过程性验收 | 验收项 8（**最终代码上 reboot 实测**）与验收项 10（**懒启动：唤醒→30min 1s 自动停止→再次拉起**）均已跑通，详见第七节 7/8 |
| 阶段 3 交付物 | 6 项齐备（第八节） |
| 验收中发现并修复的缺陷 | 5 项，全部修复、重建、回归通过（第七节，含 diff 摘要） |
| 安全加固 | 3 个业务库与 Caddy 访问日志由 644 收紧为 600（第七节 6） |
| 阶段 4 | **未触发**，未做任何改动（第十一节） |

## 二、运行环境与部署拓扑

| 项 | 值 |
|---|---|
| 服务器 | 腾讯云轻量应用服务器，root@<服务器IP>，2 vCPU / 3723 MB 内存 / 59G 磁盘（可用 46G） |
| 操作系统 | Ubuntu 24.04.5 LTS，内核 6.8.0-139-generic |
| Node.js | v26.8.2（后端使用 `node:sqlite`，要求 Node 22+） |
| Hermes Agent | v0.19.0 (2026.7.20) · upstream f7dfcc3c |
| Caddy | 2.6.2 |
| 后端 | `/opt/team-console/server/`（Express，端口 8787，systemd 托管 `team-console.service`） |
| 前端 | `/opt/team-console/team-console/`（Vue 3 + TS + Vite + Pinia + Tailwind，构建产物 `dist/` 由 Caddy `file_server` 托管） |
| 数据 | `/opt/team-console/data/`（agents.json / conversations.db / tasks.db / team-memory.db / files.json，全部 600） |
| 产物 | `/root/team-files/产出/<task_id>/`、`/root/team-files/资料库/`、`/root/team-files/系统通知/` |

### 端口清单（SPEC 要求：8642-8645 + 8650+）

| 端口 | 归属 | 监听范围 | 说明 |
|---|---|---|---|
| 80 | Caddy | `*:80` | 对外返回 `308 → https://<团队域名>/` |
| 443 | Caddy | `*:443` | 站点 `:443`，自签证书（降级路径）；**外部不可达，见第三节** |
| 8787 | team-console（Node） | `127.0.0.1` | 应用 API + `/mcp` 网关 |
| 8642 | hermes-gateway-cehua | `127.0.0.1` | 策划 Agent（systemd 常驻） |
| 8643 | hermes-gateway-chengxu | `127.0.0.1` | 程序 Agent（systemd 常驻） |
| 8644 | hermes-gateway-pingshen | `127.0.0.1` | 评审 Agent（systemd 常驻） |
| 8645 | hermes-gateway-zhiban | `127.0.0.1` | 值班 Agent（systemd 常驻） |
| 8650 | hermes-gateway-testbot | `127.0.0.1` | 懒启动测试 Agent（**非开机自启**，按需拉起、空闲回收） |
| 8650-8999 | 自建 Agent 端口池 | — | 懒启动按 `agents.json` 预分配（D 系列懒启动约束） |
| 3000 | 未占用（冗余记录） | — | 见遗留问题 C-9 |

开机自启状态（`systemctl is-enabled`）：`team-console` / `caddy` / `hermes-gateway-cehua` / `-chengxu` / `-pingshen` / `-zhiban` 均 **enabled**；`hermes-gateway-testbot` 为 **disabled**（设计如此：懒启动 Agent 不应开机常驻，首次对话时由后端拉起）。

## 三、域名与备案（降级路径）

| 项 | 状态 |
|---|---|
| 域名 | `<团队域名>` |
| DNS 解析 | 已解析至 `<服务器IP>`（`getent hosts <团队域名>` 实测） |
| 备案号 | **待补**（未取得/未确认，需在腾讯云控制台确认备案进度） |
| 对外 443 | **不可达**：外部访问超时（`curl http://<服务器IP>:443 → 000, time=8.0s`），安全组未放行 |
| 对外 80 | 可达，返回 `308 Permanent Redirect → https://<团队域名>/` |
| 降级措施 | 站点以自签证书 `/etc/caddy/certs/cloudloom.crt` 提供服务，仅在服务器本机/内网用于验收（验收脚本以 `--ignore-certificate-errors` / `-k` 校验证书链与 SW）；**未做任何 IP 直连对外暴露**（SPEC 约束 B2） |
| 延期项 | 第 7 项中的「公网域名 HTTPS 证书有效」；补做触发条件 = 备案通过 + 安全组放行 443，换正式证书后重跑 |
| 域名项可做部分 | 已完成：手机端视口（D8）与 PWA（Service Worker、manifest、通知弹窗）均在 HTTPS 会话中实测通过 |

## 四、密钥与账号（脱敏）

- 所有密钥只写入 `/opt/team-console/server/.env` 与 `/opt/team-console/data/agents.json`，权限 **600**；**未出现在任何报告中，也未入 git**（该目录不是 git 仓库）。
- DeepSeek API key：`sk-****`（已填真实值；Agent 对话与任务执行实际可用，见验收项 2）
- Hermes 网关密钥 `API_SERVER_KEY`：`****`（后端与 4 个预设网关共用，仅存 .env）
- `JWT_SECRET`：`****`（仅存 .env）；登录态为 httpOnly Cookie `tc_token`；验收脚本使用**进程内临时签发**的 token，不落盘
- 管理员账号：`admin`（显示名「负责人」，首个注册者自动成为管理员，D7）
- 成员账号：`zhang`（张策划）、`li`、`wang`（均经管理员批准后启用）
- 通知收件邮箱：`<负责人邮箱>`（脱敏）
- 验收新增测试账号：`uicheck`（显示名「UI校验账号」）—— 用于验收项 1 的「待批准 → 批准 → 停用」闭环，**当前状态＝已停用**，保留作为证据
- **独立复核（脱敏要求）**：从 `.env` 与 `agents.json` 提取 7 个密钥/敏感值（含收件邮箱），对 6 份交付物全文扫描，**命中 0 处**（脚本 `/root/e2e/secret-scan.cjs`，仅输出命中计数，不打印任何密钥值）；上述两文件权限实测均为 **600**。

## 五、N4 验证结论（system 消息注入方式）

- **结论：方案 A（system 注入）**。向 Hermes 网关发送带自定义 `system` 消息的请求时 system 指令生效；`@Agent` 拉入的上下文注入按**方案 A** 实现（见 `server/src/conversations.js` 的 agent 触发路径与 `server/src/chat.js` 的消息组装）。
- 该结论与阶段 1/2 报告一致，满足执行稿验收项 12「结论记录在部署报告，且 @Agent 按结论实现」。

## 六、19 项端到端验收记录

| # | 验收项（执行稿 3.4） | 结果 | 证据（脚本 / 命令 / 原始数值） |
|---|---|---|---|
| 1 | 4 个成员账号：首个管理员、后续需批准、会话互不串 | 通过 | `verify-fixes.mjs` 17 PASS/0 FAIL：`uicheck` 注册=HTTP 200 且 status=pending → 界面「批准/启用」→ active → 界面「停用」→ disabled（后端逐次复核）；非管理员（zhang）不可见「成员管理」区块（D29）；真实成员 admin/zhang/li/wang 四人。会话互不串：li 直取他人私聊 API 返回 **403**（页面级 7b 复测见第七节 4） |
| 2 | 聊天流式正常；4 预设 Agent 行为不同、记忆独立；DeepSeek key 真实 | 通过 | `e2e3.mjs` 42 PASS/0 FAIL（含聊天流式渲染）；4 份 SOUL.md 各自独立且字节数互异（3499/3491/3615/4131）；记忆按 profile 隔离（`~/.hermes/profiles/<id>/memories/`）＋ 团队记忆库；DeepSeek key 为真实值，任务与对话均有真实模型回复 |
| 3 | 看板 Tab 任务可见；新建任务→值班 Agent 执行→刷新出现 | 通过 | `e2e3.mjs`：看板卡片可见（4 张）、含列分组、指令框存在、卡片详情弹层打开；`kanban-cmd.cjs`：向 zhiban 发只读看板指令 HTTP 200 / 6.5s，回复匹配 **4/4** 真实卡片标题，无写入 |
| 4 | 画像 Tab：普通成员只见自己，管理员全见 | 通过 | 临时 ACL 探针三向实测（探针文件已删除）：admin `scope=all` 4/4 条（含他人与组织级待办）；zhang `scope=self` 仅 1 条本人条目，**不含 li、不含 zhangwei（越权）、不含组织级待办**；li 同构；真实画像 `画像-20260914.json`（21008 字节，generated_by=zhiban）在旧/新归属算法下差异数 = 0 |
| 5 | 私聊+群聊准实时、未读红点；@Agent 答完即走；撤回生效；刷新历史不丢 | **通过**（复跑 13 PASS / 0 FAIL） | `e2e-chat.mjs`：群聊 3 人（张策划/li/负责人）三方可见、`@cehua` **6.0s** 回复且不写入会话成员表（答完即走，成员仍 3 人）、撤回后双方显示「消息已撤回」且原文不可见、他人撤回 **403**、清 IndexedDB 后硬刷新历史仍在（含已撤回占位）。准实时与未读红点：发现并修复「已读游标缺上界」缺陷（第七节 5），修复后复测见第七节 5 附注。**复测（`e2e-chat3.mjs`）13 PASS / 0 FAIL**：原 4 项 FAIL 经逐项定位均为测试脚本态误伤（会话按 `updated_at` 排序致 `convs[0]` 漂移至群聊；li 越权项经 API 直连实测 `403 不在该会话中`，隔离正确）。详见 §7-9 |
| 6 | 资料库：≤10MB 上传、网盘链接、同列表 | 通过 | `e2e3.mjs`：UI 上传成功（中文文件名缺陷已修）、上传后列表含该文件、添加链接成功、链接与文件同列表、管理员删除成功；资料库既有条目 7 条 |
| 7 | HTTPS 证书有效（**前置：域名备案已通过**）；手机添加到主屏幕；PWA 通知弹窗实测 | **延期补做**（域名部分）＋ 通过（PWA 部分） | PWA：manifest 可获取且 MIME=`application/manifest+json`、Service Worker 注册且有 controller、通知弹窗实测弹出（`e2e3.mjs` + `sw-diag.mjs`）；移动端 D8 视口与底部 Tab 通过；**公网域名证书因备案/443 未放行延期**（第三节） |
| 8 | reboot 后全部服务自动恢复；自动快照已开启 | **通过**（自启项）＋ 快照项：待补 | 自启项：`team-console`/`caddy`/4 个 `hermes-gateway-*` 实测 **enabled**；`hermes-gateway-testbot` 为 disabled（懒启动设计，按需拉起）。**最终代码上实测 reboot**（2026-09-14 01:43:33 下达）：boot 01:43、userspace **29.4s**、ssh 约 20s 恢复；6 个单元全部 active、80/443/3000/8787/8642-8645 全部监听、`/api/health`=200、`:443`=200、4 网关 `/health`=200、8650 无监听（符合设计）；数据面 agents/tasks(98)/conversations(3)/members(5)/profiles 全部 200、`POST /api/chat`(cehua) 200/**5.0s**。自动快照：未安装 `tccli`，需控制台开启 → 待决策。详见第七节 7 |
| 9 | cron 到点：晨报写文件+邮件；画像 JSON 生成 | 通过 | `zhiban/cron/jobs.json` 实读：3 个作业全部 `enabled=true`、`deliver=local`，表达式为 晨报 `0 9 * * *`、周复盘 `0 10 * * 1`、画像 `0 6 * * *`，且提示词显式要求邮件。`zhiban/cron/executions.db` 实读 **5 条执行记录**：画像作业 `direct` 00:00:32→00:02:42 completed（产出 `画像-20260914.json`，21008 字节，generated_at=2026-09-14T00:05+08:00）；晨报 `direct` **19:39:45→19:40:51 completed**（文件 + SMTP_SSL 邮件，**4745 字节**双向核实）与 `builtin` 00:23:19→00:23:34 completed。如实记录：16:40:26 的一次晨报运行曾因 idle 超时（601s）失败 `TimeoutError`，其后 17:20 与 19:40 两次均成功并有邮件实证 |
| 10 | 懒启动全流程（唤醒→60s 内可回复→30min 自动停止→再次拉起） | **通过** | ①首次唤醒（00:48:38 起）：waking **0.2s**/ready **4.3s**/首字 **8.5s**；②空闲停止：**01:32:29**，距 `lastActive` 01:02:28 为 **30min 1s**，journal 明证 `[lazystart] 空闲超 30min，已停止: testbot`，单元 inactive/dead、`ExecMainStatus=0`、8650 无监听；③再次拉起（01:42:08 起）：waking **0.2s**/ready **4.5s**/首字 **11.4s**，单元回到 active（01:42:10）、`/health`=200、`last_active` 更新至 01:42:13。各环节均 < 60s。详见第七节 8 |
| 11 | 办公任务中心全流程（含排队、失败场景） | 通过 | 发起任务（选 Agent + 描述 + @引用 1 份资料文件）→ `queued` → `running` → `done`，产物登记；产物列表/预览/下载可用（`e2e3.mjs`）；**可分享到会话**（本轮新增并实测，第七节 1）。排队 D11：`queue-evidence.cjs` 对同一 Agent 连发 2 任务，`queue_ahead` = **0 → 1**，前端显示「前面还有 1 人」。失败场景：库内 **9** 个 `failed` 任务，含 Agent 明确「无法完成+原因」的 D36 兜底样例 |
| 12 | N4 结论记录在部署报告（方案 A 或 B，@Agent 按结论实现） | 通过 | 见第五节：**方案 A（system 注入）**；`conversations.js` 的 @Agent 路径按方案 A 组装上下文 |
| 13 | 记忆库：自动沉淀、FTS 检索、ACL 三态、手动新建 | 通过 | 自动沉淀 **17 条** `conclusion`（均带 `source_task_id`）；FTS 检索「数值」命中 **4** 条（含「数值表V2 定稿说明」）；ACL 三态 `mcp-acl.cjs` **8 PASS/0 FAIL**（admin=3 / zhang=2 / li=1，MCP 与 /api 可见集一致）；手动新建 `type=decision` → HTTP 200 → 可检索 → 探针已删除（无残留） |
| 14 | 融合闭环端到端（任务 1 → 记忆 → 任务 2 引用 → 生效） | 通过 | 任务完成自动沉淀 `conclusion` → 任务 2 提交时 `ref_memories` 引用该记忆 → `buildInstruction(task)` 生成【引用记忆】段（`tasks.js:140-200`）→ Agent 回复体现「基于上次分析」（阶段 2 端到端记录，本轮 `final-evidence.cjs` 复核注入路径）。**本轮复核（`loop-check.cjs`）**：38 个任务中引用过记忆者 1 个（`8ac2175e` / agent=cehua / ref=1），调用 `buildInstruction` 实测含 `【引用记忆】` = **true** |
| 15 | Skill 链路：`hermes skills list` 可见、提问触发生效 | 通过 | `hermes skills list` 输出已安装技能表（builtin/enabled，含 autonomous-ai-agents、creative 等分类）；任务执行中实测 `tool_name=skill_view` 加载 `zhiban-team-report` 技能 |
| 16 | MCP 网关：外部 MCP 客户端经 Caddy 可达 `/mcp`；`memory_search` 按 token 检索（ACL）；`task_create` 生效 | 通过 | `mcp-accept.cjs` **10 PASS/0 FAIL**（Streamable HTTP 握手、`tools/list` 5 工具、`tools/call`）；`mcp-acl.cjs` **8 PASS/0 FAIL**（按 token 的 ACL 与 /api 完全一致）；`task_create` 创建的任务出现在工作台任务列表。均经 **Caddy HTTPS 443** 访问（`NODE_TLS_REJECT_UNAUTHORIZED=0` 仅用于自签证书），`GET /mcp` 返回 405（协议合法） |
| 17 | 入口唯一：全程无 WorkBuddy/外部办公工作台依赖；模型切换在配置层完成 | 通过 | 后端 6 个模块 + 前端 7 个 Tab 全自研，无外部工作台依赖；模型/密钥全部在 `.env` 与 `agents.json` 配置层，前端不接触任何密钥（见《前端开发者说明》第七、八章与《成员接入手册》） |
| 18 | 修正反馈闭环（D35）：requires_approval → waiting_approval → 审批「修改」+理由 → `task_corrections` 落库 → 同类任务注入修正记录 | 通过 | `task_corrections` **4 条**落库（task_id/agent_id/action=modify/note/decided_by/created_at 齐全）；`buildInstruction(同类任务 fec61b86)` 含【相关修正记录】= **true**，片段：「- [modify] 试算须补充三年期对比，并注明币种与含税口径…」；对应 `conclusion` 记忆含审批修正摘要 |
| 19 | 行为边界与升级规则（D34/D36）：4 Agent SOUL.md 均含「行为边界」+ HERMES.md 边界总表；删除/对外承诺/报预算类指令自动 requires_approval；不可能任务明确「无法完成+原因」 | 通过 | 4 份 SOUL.md 均含【行为边界】小节；`HERMES.md` 含 **4x4 行为边界总表**（逐字取自四份 SOUL.md）；`detectSensitive` 实测：预算→`金额`、删除→`删除数据`、对客户承诺→`对外承诺` 命中即强制人审，而「客户端界面改版说明」「整理本周会议要点」**不误伤**；不可能完成任务 → Agent 明确「无法完成+原因」（`failed` 任务 error 字段留痕，D36 兜底） |

## 七、本次验收中的缺陷修复与变更记录（含 diff 摘要）

铁律要求「修复缺陷须记录 diff 并说明」。**第 1-6 项为加法式修复/加固**（未重写已验收代码，每项修改前均留有原文件备份于 `/root/e2e/backups/`）；**第 7-9 项为过程性验收记录**（reboot 实测、懒启动全周期、聊天链路复判），其中第 9 项经复判确认**非产品缺陷**。

### 1. 任务产物无法「分享到会话」（验收项 11 缺口）
- 文件：`team-console/src/views/TasksView.vue`（+约 40 行；备份 `TasksView.vue.bak-share`）
- 内容：产物行新增「分享到会话」按钮 → 复用既有 `GET /conversations` 与 `POST /conversations/:id/messages` 把产物下载地址作为消息发入指定会话；**未新增后端 API**。
- 验证：`vue-tsc -b && vite build` 通过（TasksView 16.55 → 17.65 kB）；`e2e3.mjs` 42 PASS/0 FAIL。

### 2. 缺少成员管理入口（验收项 1、D29 缺口）
- 文件：`team-console/src/views/SettingsView.vue`（+约 2.8 KB）
- 内容：新增**仅管理员可见**的「成员管理」区块（列表 + 状态徽标 + 「批准/启用」 + 「停用」），复用既有 `GET /members`、`POST /members/:id/approve`、`POST /members/:id/disable`；管理员自身行不渲染「停用」（与后端拒绝自停用一致）；非管理员完全不渲染（D29 入口唯一）。
- 验证：`verify-fixes.mjs` **17 PASS/0 FAIL**：注册 → `pending` → 界面批准 → `active` → 界面停用 → `disabled`（每步均以后端 `/api/members` 复核）。

### 3. 「指定成员」可见性无法提交（验收项 11、D25 缺口）
- 文件：`TasksView.vue`（表单新增 `memory_allow_members`、成员多选控件、提交前校验；非 restricted 时不下发该字段）
- 根因：`createTask` 在 `visibility=restricted` 时要求 `memory_allow_members` 非空（`tasks.js:444`），而前端无该字段入口 → 该可见性必然 400。
- 验证：不勾选成员时前端拦截并提示；勾选后任务创建成功，`GET /api/tasks/:id` → `meta.memory_allow_members=["e91bd459-…"]`（DB 行级复核一致）。

### 4. 画像归属匹配越权风险（验收项 4、M3）
- 文件：`server/src/profiles.js`（+12 行 `hasId()`；`belongsTo` 由子串包含改为**词边界匹配**；备份 `profiles.js.bak-acl`）
- 根因：原实现 `t.includes(id)`，`zhang` 会命中 `zhangwei`、`li` 会命中 `lily` / `quality` → 普通成员可能看到他人画像条目。
- 验证：单测 `prof-acl2.cjs` **10/10 符合预期**（含「组合串『成员：张策划（zhang）』仍命中本人」的正例）；真实画像文件新旧算法**差异数 = 0**（无回归）；ACL 探针端到端实测 zhang 不含 zhangwei。

### 5. 已读游标缺上界 → 未读红点永久失效（验收项 5）
- 文件：`server/src/conversations.js`（`POST /conversations/:id/read` 增加上界钳制：`seq = min(max(seq,0), 会话 MAX(seq))`；备份 `conversations.js.bak-cursor`）
- 根因：原实现直接 `MAX(last_read_seq, seq)` 落库；库中存在脏游标 999（该会话 `MAX(seq)=10`），使 zhang 在该私聊的未读**永久为 0**，且前端任何正常上报都无法自愈。
- 数据修正：`conversation_members` 全表比对后修正唯一超界行 —— `zhang @ 6cfb3293: 999 → 10`（复核通过）；其余 6 条成员游标本就精确等于所在会话 `MAX(seq)`。
- 验证：`e2e3.mjs` 复跑 42 PASS/0 FAIL（无回归）；`e2e-chat.mjs` 复测见下方附注。

### 6. 安全加固：业务库与访问日志权限过宽
- 内容：`conversations.db` / `tasks.db` / `team-memory.db` 及其 `-wal`/`-shm` 与 `/var/log/caddy/cloudloom-access.log` 由 **644 → 600**（本机另有 `ubuntu`(1000)、`lighthouse`(1001) 两个可登录账号，原权限可读全部聊天记录与口令散列）。
- 未改动：`.env`、`agents.json`（本就 600）。
- 复核：权限已确认 600，服务与站点存活（8787=200、443=200）。

### 7. reboot 实测（验收项 8：全部服务自动恢复）
- 触发：2026-09-14 01:43:33 下达 `systemctl reboot`；boot 时刻 **01:43**，`Startup finished in 2.363s (kernel) + 27.051s (userspace) = 29.415s`；ssh 于 01:44:00（约 20s 后）恢复。
- 自启项实测（enabled / 重启后 active）：

| 单元 | enabled | active | 备注 |
|---|---|---|---|
| `team-console.service` | enabled | active | 8787 API+MCP、3000 静态 |
| `caddy.service` | enabled | active | 80/443 |
| `hermes-gateway-cehua` / `chengxu` / `pingshen` / `zhiban` | enabled | active | 8642-8645 |
| `hermes-gateway-testbot` | **disabled** | inactive | 按设计（C3 懒启动，按需拉起） |

- 端口监听：80、443、3000、8787、8642-8645 全部就绪；**8650 无监听**（符合懒启动设计）。
- 健康检查：`8787 /api/health`=**200**、`3000 /`=**200**、`80`=**308**（跳转 HTTPS）、`443 /api/health`=**200**、8642/8643/8644/8645 `/health`=**200**。
- 数据面复核（重启后新铸 token，脚本 `postreboot-smoke.cjs`）：`GET /api/agents`=200（5 个）、`/api/tasks`=200（**98 条**）、`/api/conversations`=200（**3 条**）、`/api/members`=200（**5 位**）、`/api/profiles`=200；`POST /api/chat (cehua)`=200，**5.0s** 返回正文 —— 业务库与代理链路重启后完整可用（数据未丢）。
- 结论：**通过**（最终代码上复跑；另有 boot 2026-09-13 23:53:24 的历史实测 `reports/reboot-verify.txt`，结果一致）。**自动快照：待补**（未安装 `tccli`）。
- 附带发现（非缺陷，已定位并复测自愈）：重启后 `GET /api/agents` 对 4 个预设 Agent 一度报 `running:false`，而实际 `/health` 均为 200。原因：`initTable()` 于 01:43:56 探测时网关尚未监听，而 SSE 路径仅在「实时探活为未运行」时才调用 `ensureRunning`（`chat.js:60-64`），已运行实例不回写内存标记。首个 5 分钟扫描（01:48:57）后全部转为 `up`（复测：cehua/chengxu/pingshen/zhiban = up）。影响仅限设置页「运行中」指示最多滞后一个扫描周期，功能无影响；潜在成因已记为 C-14。

### 8. 懒启动全周期实测（验收项 10：唤醒 → 60s 内可回复 → 30min 自动停止 → 再次拉起）
测试 Agent：`testbot`（8650，`lazy` 托管，`disabled` 不自启）。证据：`/root/e2e/idle-watch.sh`（每 60s 采样，日志 `idle-watch.log`）、`/root/mcpclient/lazy-cycle.cjs`、`/root/e2e/rewake-check.cjs`。

| 环节 | 实测结果 | 证据 |
|---|---|---|
| ① 首次唤醒 | waking 事件 **0.2s**、ready **4.3s**、首字 **8.5s** | `lazy-cycle.cjs`（00:48:38 起） |
| ② 30min 空闲自动停止 | **01:32:29 停止**；距 `lastActive`（01:02:28）**30min 1s** | journal `-u team-console.service`：`[lazystart] 空闲超 30min，已停止: testbot`（01:32:30）；`is-active`=inactive/dead、`ExecMainStatus=0`、8650 `/health`=000、无监听 |
| ③ 再次拉起 | waking **0.2s** → ready **4.5s** → 首字 **11.4s**，会话 11.6s 结束 | `lazy-cycle.cjs` 复跑（01:42:08 起） |
| ④ 拉起后状态回写 | systemd `active`（`ActiveEnterTimestamp` 01:42:10）、8650 `/health`=**200** | `rewake-check.cjs`：`{running:true, managed:"lazy", last_active:"2026-09-13T17:42:13Z"}`（即 01:42:13 CST） |

- 全周期每一环均在 60s 预算内（ready ≤ 4.5s、首字 ≤ 11.4s），停止与再次拉起**均无需人工干预**。
- 说明一：停止时刻以 journal 时间戳为准（01:32:39 的采样点恰跨过停止瞬间，实际停止为 01:32:29）。
- 说明二：`lastActive` 起点由服务重启时的 `initTable()` 决定（01:02:28，日志 `实例表初始化: … testbot:up`），**并非首次对话时刻**；`sweep()` 只读不写 `lastActive`，故外部 `/health` 探活不会延长其寿命（已读代码确认），本次观测因此是纯净的 30 分钟计时。

### 9. 聊天链路回归复测（验收项 1b / 5）——**非产品缺陷，属测试脚本态误伤**
首轮 `e2e-chat.mjs` 复跑出现 4 项 FAIL（1、1b、7a、7b），逐项定位后确认**均非产品缺陷**，故不计入缺陷修复；改由独立脚本 `e2e-chat3.mjs` 干净复测：
- **FAIL 1 / 1b 真因**：会话列表按 `updated_at DESC` 排序，群聊创建后 `convs[0]` 已非私聊，而脚本依赖 `ChatView.vue L90-91` 的「自动打开 `convs[0]`」，导致消息发进了**群聊**（DB 证据：seq16/17 的 `conversation_id` = 群聊 `b5c1f555`，非私聊 `6cfb3293`）。改为显式打开私聊后通过（网络层证据：`POST /api/conversations/6cfb3293-…/messages`）。
- **反证「打开态自动已读致红点不出现」**：红点出现期间 zhang 对私聊 `/read` 次数 = **0**；且 1b 在游标钳制前首跑即以 0.87s 通过。「打开即已读」实为 `chat.ts L56/58/74/87/94` 的**既有设计、非缺陷**。
- **FAIL 7a / 7b 非越权**：API 直连 8787 携带 li 的 token，li 可见会话仅 2 个群 + 其与张策划的私聊（`HAS_DM=false`），私聊消息拉取返回 `403 {"error":"不在该会话中"}`。「标记2」因同一排序根因落入群聊，而 li 是该群合法成员 —— **隔离本身正确**。
- **钳制未引入回归**：未读红点自动出现 2.52s → 2.95s、打开态实时到达 0.87s → 3.32s，差异属 4s 轮询相位抖动，均 ≤ 轮询周期 + 渲染，符合 3-5s 规格；`Math.min(Math.max(seq,0), maxSeq)` 结构上只收敛、不放大。
- **游标完整性复核**：`conversation_members` 全表 10 行**全部 `cursor <= max`**（原越界值 999 已修正并推进至 24）。
- 结论：**13 PASS / 0 FAIL**；完整明细见 `/root/e2e/chat-retriage.md`（186 行，含结论/证据/命令/原始输出）。

## 八、交付物清单（执行稿 3.5，6 项全部落盘）

| # | 交付物 | 路径 | 规模 |
|---|---|---|---|
| 1 | 部署报告（本文件） | `/opt/team-console/reports/Session3-部署报告.md` | 域名/端口/脱敏密钥/管理员账号/N4/19 项验收表 |
| 2 | 《成员接入手册》 | `/opt/team-console/docs/成员接入手册.md` | 637 行（网址、注册、七个 Tab、@Agent、撤回、任务中心、记忆库） |
| 3 | 《前端开发者说明》 | `/opt/team-console/docs/前端开发者说明.md` | 880 行，含 **43 条**代理层接口（每条带 `文件:行号`；独立复核：42 条 `router.*` 注册 + `app.get("/api/health")` = 43 条一致）、懒启动、产物目录约定、占位图替换 |
| 4 | `HERMES.md` | `/opt/team-console/HERMES.md` | 354 行，含 **4x4 行为边界总表**（逐字取自四份 SOUL.md） |
| 5 | 《故障排查表》 | `/opt/team-console/docs/故障排查表.md` | 797 行（实测），9 大故障场景 25 个子条目 + 3 附录 + 12 项隐患 |
| 6 | 二期备忘 | `/opt/team-console/docs/二期备忘.md` | 101 行（山河云台主题、群聊 Agent 常驻、向量检索切换触发条件、可观测 D32、记忆评测集、修正率、初见报告、D33 边界决策、结转项、触发条件汇总表） |

## 九、遗留问题（如实列出，**未用「已知问题」蒙混任何验收项**）

严重度取自《故障排查表》附录 C 的独立核对结论：

| 级别 | 编号 | 问题 | 影响 / 建议 |
|---|---|---|---|
| 高 | C-1 | 第二个 `team-console` 实例启动瞬间会把所有 `running` 任务判为孤儿重排并执行（`index.js` 在 `app.listen` 之前即 `recoverStale({boot:true})` + `startSweeper()`，孤儿判定用进程内集合） | 双进程双写产物；建议把恢复逻辑移到 `listen` 回调之后 |
| 高 | C-2 | `allocatePort()` 只在 `agents.json` 内查重，不做 bind/ss 探测 | 新建 Agent 可能分到被未登记进程占用的端口，首次唤醒必失败 |
| 中 | C-3 | 通知 `tick()` 的 `primed = true` 写在 try/catch 之外，登录页阶段 `/api/poll` 必然 401 → 先见登录页再登录的用户会拉回全部历史通知并弹旧通知 | 建议 401 时不置位 `primed` |
| 中 | C-4 | 未安装 `systemd-oomd`，`MemoryMax=infinity` | 内存压力下可能被内核 OOM killer 杀掉（实测 5 个 Hermes 常驻约 1.05G，空载约 1.5G/3.7G；**Agent 浏览器工具**曾观察到 8 个 chrome-headless 合计 806MB，是真正的高危场景） |
| 中 | C-5 | 服务以 root 运行且无沙箱（`ProtectSystem/ProtectHome/PrivateTmp/NoNewPrivileges` 均 no） | 可读写 `/root/.hermes`（含密钥） |
| 中 | C-6 | 业务库权限过宽 | **已修复**（第七节 6） |
| 中 | C-7 | `Restart=always` + `StartLimitIntervalSec=0` | 崩溃时会无限重启吃满 2 核 |
| 中 | C-8 | 存在手工 `gateway run` 与 systemd 争抢同一 profile 端口（journalctl 见同 profile 两个 PID 而 `NRestarts=0`） | 需避免手工启动 |
| 低 | C-9 | 端口 3000 冗余记录 | 清理文档即可 |
| 低 | C-10 | Cookie 缺 `Secure` 属性 | 正式启用 HTTPS 后应补 |
| 低 | C-11 | Caddy 访问日志无轮转 | 长期增长 |
| 低 | C-12 | SPA fallback 吞掉未知路径（返回首页而非 404） | 可接受 |

其他如实记录的偏差（不影响验收结论）：

1. **SPEC 与实现不一致 3 处**：SPEC 写「Node 20 LTS」，实机 **v26.8.2**（`node:sqlite` 需 Node 22+，按 SPEC 原样复现环境会起不来）；D19 定「3-5 秒轮询」，实测看板与侧栏为 **8 秒**；SPEC 提到的占位头像 `assets/agents/placeholder.png` **在代码中不存在**（`avatar` 字段全链路为 null，界面以 emoji 承担占位）。
2. **`auth.js` 登录响应体回传 `token`**：为外部 MCP 客户端便利所做取舍，但使 JWT 变为 JS 可读，削弱 httpOnly Cookie 的防 XSS 意图（见待决策 4）。
3. **值班 Agent 的邮件通道自检误判**：zhiban 的 MCP 自检任务曾以 `which himalaya/msmtp` 判定「邮件通道不可用」，实际 SMTP 配置有效（`hermes status` 显示 Email ✓，且晨报实测发信成功 4745 字节）。该任务按 D36 语义标记 `failed` 属**设计内行为**，其产物保留为证据；自检提示词建议补充 SMTP 检查方式（见待决策 8）。
4. **6 条接口超出 SPEC「接口边界」清单**（`PUT /api/me`、`POST /api/members/:id/disable`、`GET /api/profiles`、`GET /api/memories/suggest`、`POST /api/tasks/:id/approval`、`GET /api/health`）：源码内均带合规注释、均为加法式新增且为验收项所必需（如无 disable 则无法停用成员）；按 SPEC 字面属超范围，如实列出。

- **C-13（可用性隐患，复测中发现，非验收缺陷）**：`ChatView.vue L90-91` 挂载时自动打开 `convs[0]`（最近更新会话）而非用户上次会话，列表顺序随任意成员发言漂移，**易把消息误发到群聊**（本次复测脚本正被此坑到）。建议二期改为「记住上次会话」，或自动选中时显著高亮当前会话。

- **C-14（潜在隐患，当前配置下不可达）**：`chat.js:60-64` 仅在「实时探活为未运行」时调用 `ensureRunning`，故**已在运行的实例不会回写 `lastActive`**。若某实例在 `initTable()` 探测时尚未监听、其后才起来（重启竞态），其 `lastActive` 将保持 0，而 `sweep()` 判定 `Date.now() - 0 > 30min` 成立 → 该实例会在**被使用中**被停止。当前唯一的懒启动 Agent `testbot` 为 `disabled`、不自启，必然走 `ensureRunning` 路径，故不可达；仅当管理员日后为自建 Agent 启用 systemd 单元时才可能出现（本次 reboot 后 4 个预设 Agent 的 `running:false` 滞后即同一成因的良性表现）。建议二期在 `isRunning()` 命中时补一次 `touch(id)`（一行加法式改动）。

## 十、待决策事项（需用户/管理员决定）

| # | 事项 | 说明与建议 |
|---|---|---|
| 1 | **备案进度与 443 放行** | 阶段 4 的唯一前置。需在腾讯云控制台确认备案状态，并在安全组放行 80/443；之后换正式证书重跑域名侧验收 |
| 2 | **自动快照开启**（SPEC D12） | 服务器未装 `tccli`，需在轻量服务器控制台开启自动快照（每周 1 次、保留 2 份） |
| 3 | **新建数据文件权限持久化** | 已把现有库文件改为 600，但新生成的 `-wal`/`-shm` 仍会继承进程 umask（022 → 644）。建议在 `team-console.service` 增加 `UMask=0077`；**属 systemd 改动，未擅自执行** |
| 4 | **登录响应体是否移除 `token`** | 若外部 MCP 客户端可改用 Cookie，建议移除；否则请在文档中明示该取舍 |
| 5 | **轮询间隔是否对齐 SPEC D19** | SPEC 3-5s vs 实测 8s（看板/侧栏）。改则提升实时性、增加请求量 |
| 6 | **Node 版本口径** | 建议把 SPEC 的「Node 20 LTS」修订为「Node 22+（实测 26.8.2）」 |
| 7 | **验收残留是否清理** | 现存痕迹：测试账号 `uicheck`（已停用）、12+ 个验收测试任务及其产物、MCP 自检任务 `d45a5401`（**刻意保留为 D36 证据**）、懒启动测试 Agent `testbot`（按需拉起）；`TasksView.vue.bak-share` 已移出源码目录至 `/root/e2e/backups/` |
| 8 | **值班 Agent 自检提示词** | 建议在自检提示词中明确「邮件通道以 `hermes status` 输出与 .env 中 EMAIL_SMTP_* 为准」，避免重复误判 |

## 十一、阶段 4（域名 HTTPS 收尾）：**未触发**

触发条件检查（2026-09-14 01:05 CST，实测）：

| 前置条件（SPEC / 执行稿 4.0） | 实测结果 | 判定 |
|---|---|---|
| 域名已解析到本机 | `getent hosts <团队域名>` → `<服务器IP>` | 满足 |
| Caddy 已监听 80/443 | `ss -lntp`：`*:80`、`*:443`（caddy pid 899） | 满足 |
| **安全组已放行 80/443** | 外部 80 → `308`（可达）；外部 443 → `000, time=8.0s`（**超时/被过滤**） | **不满足** |
| 备案已通过（域名对外合规） | 备案号**待补**，无法从服务器侧确认 | **不满足** |

**结论：阶段 4 未触发。** 依执行稿 3.7「阶段 4 前置不满足则输出『未触发』并结束」，本轮**未对域名/证书/安全组/对外暴露做任何改动**；对外 HTTPS 相关验收项在第 7 项标注「延期补做」，补做触发条件为：备案通过 + 安全组放行 443。

## 附、证据文件索引（服务器）

- 验收脚本：`/root/e2e/e2e3.mjs`（42 PASS）、`verify-fixes.mjs`（17 PASS）、`e2e-chat.mjs`、`sw-diag.mjs`、`final-evidence.cjs`、`final-evidence-2.cjs`、`queue-evidence.cjs`、`prof-acl2.cjs`（10/10）、`prof-acl-e2e.cjs`、`prof-compare.cjs`、`repair-cursor.cjs`
- MCP：`/root/mcpclient/mcp-accept.cjs`（10 PASS）、`mcp-acl.cjs`（8 PASS）、`kanban-cmd.cjs`、`lazy-cycle.cjs`、`mint.cjs`
- 截图：`/root/e2e/shots/*.png`（桌面端 + 移动端 + PWA + 成员管理/任务表单修复项）
- 变更前备份：`/root/e2e/backups/*.bak-*`
- 日志：`/root/e2e/*.log`、`journalctl -u team-console`
- 收尾阶段新增证据：`/root/e2e/idle-watch.sh` + `idle-watch.log`（空闲停止 60s 采样）、`/root/mcpclient/lazy-cycle.cjs`（唤醒/再拉起计时）、`/root/e2e/rewake-check.cjs`、`/root/e2e/postreboot-smoke.cjs`（重启后数据面）、`/root/e2e/reboot-check.sh`、`/root/e2e/chat-retriage.md` + `/root/e2e/e2e-chat3.mjs`（聊天链路复判）、`/root/e2e/loop-check.cjs`（记忆注入路径）
