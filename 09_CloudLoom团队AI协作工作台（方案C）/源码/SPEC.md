# 方案 C（CloudLoom）· 完整规格 SPEC（v3.3）

> 本文件由 `方案C-最终Prompt-v3.3.docx` 转换生成（2026-09-14），是 4-Session 开发的**唯一权威规格**。
> 部署位置：服务器 `/opt/team-console/SPEC.md`
> 改规格请改源 docx 后用 `docx2spec.py` 重新转换，不要直接改本文件。

---


## 方案 C（最终版 v3.3）：自研团队协作工作台 — 完整 Coding Prompt

本文件是唯一权威版本（v3.3，2026-09-14 第六次修订）。

所有决策已由团队负责人确认（见第四节决策清单），执行时不得偏离。

v3.2 → v3.3 修订（2026-09-14，S4.0 加固改进包落地后对齐现实；均为表述修正与补录，不改系统设计意图）：

- 环境口径：原写 Node 20 LTS（按 setup_20.x 安装）→ 改为 Node 22+。后端使用 node:sqlite，需 Node 22+，照原文装出 20.20.2 将无法启动后端；服务器实际运行的是 /usr/local/bin/node v26.8.2，安装命令同步改为 setup_22.x。
- D19 轮询间隔：按界面分档（实测）——通知 4s、聊天流 4s、任务列表 5s、看板 8s、会话列表 8s；并删除未实现的“活跃 3s / 后台 5s”表述。
- 占位头像：原 assets/agents/placeholder.png 已删除；改为 public/avatar-placeholder.png，前端在 avatar 为空时自动回退，agents.json 填 URL 即覆盖（avatar 字段全链路透传，S4.0/B4）。
- 登录响应：只回用户信息、不回 token；会话唯一载体为 httpOnly Cookie（SameSite=Lax）——旧“响应带 token”口径作废（S4.0/B3）。
- 接口边界补录 6 条（S1-S3 实际新增且验收必需）：PUT /api/me、POST /api/members/:id/disable、GET /api/profiles、GET /api/memories/suggest、POST /api/tasks/:id/approval、GET /api/health。
- 新增「重启恢复」语义（见 4.8）：重启后中断的任务自动恢复执行，且必须同时满足“可见 + 不覆盖已有产物”。
v3.1 → v3.2 修订：修正两处文档矛盾（Ubuntu 版本统一为 24.04；策划 Profile 拼音统一为 cephua→cehua）；

新增行为设计三决策：D34 行为边界与失败模式（四 Agent SOUL.md 显式定义"可自主/需升级/禁止"+失败兜底）、

D35 修正反馈闭环（任务审批动作落库为修正记录，下次同类任务注入上下文——成员改了什么 Agent 记住）、

D36 不确定性升级规则（涉金额/对外承诺/删数据三类任务强制人工确认；低置信度任务自动转值班复核）；

任务状态机扩展 waiting_approval；验收项 17 → 19。

v3.0 → v3.1 修订：放弃 WorkBuddy（办公能力由 Hermes 工具+Skill 实现）；

新增 MCP 中枢串联（8787 代理层升级为 MCP 网关，对外暴露团队记忆/任务/看板，

对内可接 TencentDB/外部数据源/工具）；明确"入口唯一、零件可换"架构原则。

记忆能力用 Hermes 原生 + 自研 SQLite 记忆库实现，不依赖 TencentDB（升级件）。

直接扔给 Claude Code / Codex / Hermes 任一，从零搭完。

### 一、任务目标

在一台腾讯云轻量服务器（Ubuntu Server 24.04 LTS，D30）上，从零搭建 4 人团队的 AI 协作系统，

前端为自研单页应用（团队专属工作台），一个页面内完成：

成员间聊天（私聊+群聊）、成员-Agent 聊天（多 Agent 可选）、办公任务中心、

任务看板、成员画像、团队共享记忆库、资料库、通知，并实现

「办公任务执行 → 产物交付 → 自动沉淀记忆 → 下次直接引用」的融合闭环。

后端完全依赖 Hermes 标准版（API Server + Kanban + Memory）+ 自研薄层

（Node 代理 + SQLite），不引入其它中间件。

范围声明（N2，先读）：本系统做团队协作层 + 团队记忆层 + 办公执行层。

游戏运行时记忆（NPC 记忆、玩家状态、剧情分支持久化）是**独立的游戏后端系统，

不在本 Prompt 范围内**，不在此实现，也不要为它预留接口。

团队记忆能力用自研记忆库（data/team-memory.db）实现，不接入 TencentDB。

架构原则（v3.1 新增，先读）：

- 入口唯一：成员只面对工作台一个界面；所有平台（记忆/数据/工具/模型）均为后台零件，用户无感切换
- 中枢串联（MCP）：Hermes 为中枢；8787 代理层同时是 MCP 网关——对内统一自研能力，
对外按需接入外部 MCP server（TencentDB、MySQL、Notion 等），随时可换、谁也别想绑定

- 放弃 WorkBuddy：办公能力（文档/PPT/分析）由 Hermes 的 Agent 工具 + Skill 实现，
不引入任何外部办公工作台

### 二、环境与前置

- 服务器：腾讯云轻量 2核4G，60GB SSD，Ubuntu Server 24.04 LTS（镜像：Ubuntu 24.04-Docker 29.6.1，预装 Docker），root SSH，公网 IP
- 域名（B2）：已购买域名（约 30-60 元/年），DNS A 记录指向服务器公网 IP
- 已有：DeepSeek API Key —— 部署时填入占位符（见第 1 阶段，管理员操作）
- 团队：4 人混编（策划/程序/美术/运营），异地；未来可能扩员（账号体系按可扩展设计）
- 全程 root 执行；每步验证，失败先诊断，禁止静默跳过

### 三、接口边界（先读！这是本方案成败关键）

#### ✅ 可用接口

聊天：POST http://127.0.0.1:<实例端口>/v1/chat/completions

- OpenAI 兼容格式；Authorization: Bearer <API_SERVER_KEY>
- stream: true 走 SSE 流式输出；返回的 model 字段 = 当前 profile 名
- 这是唯一的前端聊天通道，支持完整工具调用（Hermes 在服务端执行）
- M1：API Server 无状态——每次请求必须携带完整会话历史（messages 数组）
健康检查：GET /health；模型列表：GET /v1/models

API Server 配置项：API_SERVER_ENABLED、API_SERVER_PORT（默认 8642）、

API_SERVER_HOST（默认 127.0.0.1）、API_SERVER_KEY —— 多实例靠不同 PORT+KEY

Kanban（跨 Profile 原生共享）：官方设计跨 Profile 共享，默认

~/.hermes/kanban.db；HERMES_KANBAN_BOARD 环境变量固定路径。前端只读查询

聊天驱动的写操作：看板创建/状态流转/评论，通过向 Agent 发指令消息

（如 "/kanban create 标题 --body 内容"）让 kanban_* 工具执行

邮件通知：Hermes Email 平台（SMTP 配置在 ~/.hermes/.env）

#### ✅ 自研层接口（本方案自己实现，全在代理层 8787）

- 办公任务：POST /api/tasks、GET /api/tasks、GET /api/tasks/:id、
POST /api/tasks/:id/cancel、GET /api/tasks/:id/outputs/:oid/download

- 团队记忆库：POST /api/memories、GET /api/memories?q=&type=、
GET /api/memories/:id、PUT /api/memories/:id、DELETE /api/memories/:id

- 详见第 4 阶段 4.8 / 4.9
- 支撑接口（v3.3 补录；S1-S3 实际新增且验收必需，均为加法式实现）：
PUT /api/me、POST /api/members/:id/disable、GET /api/profiles、GET /api/memories/suggest、POST /api/tasks/:id/approval、GET /api/health

- MCP 网关（v3.1 新增，D28）：8787 同时提供 MCP server 端点
（/mcp，Streamable HTTP 或 stdio 均可，默认 HTTP），把团队记忆/任务/看板

暴露为标准 MCP 工具（memory_search/memory_add/task_create/kanban_list 等），

供 Hermes 中枢及外部 Agent 调用；并作为 MCP 客户端接入外部 server（见 4.11）

#### ❌ 不可用/不要臆造

- Hermes API Server 没有 kanban/memory/画像 REST API —— 不要发明 /v1/... 端点
- 实时推送：没有 WebSocket 事件流。通知用「前端轮询 + Notification API（PWA）」，
轮询间隔按界面分档（v3.3 修订，实测）：通知/聊天 4 秒、任务列表 5 秒、看板与会话列表 8 秒（M1）

- 外部 system 消息注入行为未确认（N4 验证项）：部署时必须先验证（验收项 12），
结果决定 @Agent 拉入的上下文注入方式（4.6 备选 A/B）

### 四、已确认决策清单（团队负责人拍板，不得更改）

| # | 决策项 | 选定方案 |
|---|---|---|
| D1 | 服务器配置 | 2核4G（预算约 200-300 元/年） |
| D2 | 团队规模 | 账号体系可扩展（当前 4 人） |
| D3 | 外部人员 | 不需要访客角色，系统保持内部纯净 |
| D4 | 数据保留 | 聊天记录/文件/记忆永久保留 |
| D5 | Agent 架构 | 4 个预设 Agent 各自独立常驻实例 + 自建 Agent 独立 Profile + 懒启动（不常驻，按需拉起，空闲 30 分钟停止） |
| D6 | 界面风格 | 先素净极简上线，主题二期再加（山河云台主题设定包作为二期素材） |
| D7 | 登录 | 管理员邀请制（第一个注册者为管理员，之后需批准） |
| D8 | 设备 | 手机/电脑响应式两端都做好 |
| D9 | 成员群聊 | 私聊 + 群聊都做（首版即含） |
| D10 | AI 费用 | 不设预算上限，不实现限流逻辑 |
| D11 | 并发 | Agent 忙时排队等待，提示"正在忙，前面还有 N 人" |
| D12 | 备份 | 腾讯云控制台开启自动快照 |
| D13 | 访问方式 | 域名 + HTTPS（Caddy 自动证书；解锁 PWA 通知） |
| D14 | 大文件 | 美术大文件（>10MB）走网盘，系统只存链接；≤10MB 直接上传 |
| D15 | 晨报/周复盘 | 每天 09:00 晨报；每周一 10:00 周复盘 |
| D16 | 主题素材 | 本期用占位图；二期替换主题包 |
| D17 | 审批节点 | 设计定稿 / 预算 / 对外承诺，必须人工确认 |
| D18 | 消息撤回 | 支持 5 分钟内撤回（仅发送者本人） |
| D19 | 轮询频率 | 前端轮询按界面分档（v3.3 修订，实测）：通知 4s、聊天流 4s、任务列表 5s、看板 8s、会话列表 8s，准实时 |
| D20 | 通知文件 | cron 结果由 Agent 用 file 工具写入 ~/team-files/系统通知/ |
| D21 | 画像生成 | 画像由 cron 每日生成 JSON 到 ~/team-files/系统通知/画像/，按请求者过滤 |
| D22 | Profile 命名 | Profile 名用拼音（cehua/chengxu/pingshen/zhiban），显示名中文 |
| D23 | 办公任务中心 | 新增"任务"Tab：发起任务（选 Agent + 描述 + @引用资料/记忆）→ 执行 → 产物预览/下载/分享；任务状态机 queued/running/done/failed |
| D24 | 团队共享记忆库 | 自研 data/team-memory.db（SQLite+FTS5）：团队记忆集中存储，不依赖 TencentDB |
| D25 | 记忆 ACL | 记忆可见性：private（仅作者）/ team（全员）/ restricted（指定成员）；检索与展示按当前用户过滤 |
| D26 | 融合闭环 | 任务完成 → 自动沉淀 conclusion 记忆 → 下次任务发起时可检索并 @引用记忆 → Agent 带历史执行 |
| D27 | 放弃 WorkBuddy | 不引入任何外部办公工作台；办公能力（文档/PPT/分析）由 Hermes Agent 工具 + Skill 实现 |
| D28 | MCP 中枢串联 | 8787 代理层升级为 MCP 网关：对外暴露团队记忆/任务/看板为 MCP server（供外部 Agent/工具调用）；对内可接入外部 MCP server（TencentDB/MySQL/Notion 等） |
| D29 | 入口唯一原则 | 成员只面对工作台一个界面；模型切换（DeepSeek/Claude 等）在配置层完成，不改变用户入口；外部平台均为可换零件 |
| D30 | 部署环境确认 | 腾讯云轻量 2核4G + Ubuntu Server 24.04 LTS（镜像：Ubuntu 24.04-Docker 29.6.1，预装 Docker）；规格第 1 阶段已同步（跳过 Docker 安装 + Node 20 LTS） |
| D31 | 记忆内核自研 + 零件选用 | 记忆 schema/规则/评测集自研（护城河）；存储 SQLite 起步、TencentDB 为升级件；执行层用 Hermes；办公能力自研（放弃 WorkBuddy） |
| D32 | 可观测（统计级，二期） | 二期新增"运营统计"能力（统计级，不做 Trace）：每 Agent 调用次数/成功率/平均耗时/Token 估算、成本看板（DeepSeek 按量估算）、高频场景 TopN、低成功率链路提示；数据源=任务中心 + /api/chat 日志 + cron 画像（借鉴 ADP Agent Portal 治理层，2026-08-20 决策） |
| D33 | 不做 Agent 治理平台（边界决策） | 不做"跨平台智能体纳管/调度/治理平台"（ADP Agent Portal 的主场，巨头赛道，备忘录 5.5"不做什么"清单）；方案 C 定位="小型创意团队的数字员工办公室 + 团队记忆容器"，B 端出路是"城市记忆层/记忆资产服务"而非 Agent 管理（2026-08-20 决策） |
| D34 | 行为边界与失败模式（v3.2 新增） | 每个 Agent 的 SOUL.md 必须显式定义"行为边界"三清单：可自主（无需人审的动作）/ 需升级人审（触发 D17 审批节点或 D36 强制项）/ 禁止（任何情况不得执行）；并写"失败兜底"（做不了/不确定时怎么办）。HERMES.md 汇总四 Agent 边界总表供成员查阅；新增 Agent 时模板化套用（2026-08-24 决策） |
| D35 | 修正反馈闭环（v3.2 新增） | 任务的审批动作（通过/打回/修改）落库为修正记录（task_corrections 表）；下次发起同类任务（同 Agent + 相关标签）时把最近修正记录注入 Agent 上下文——"成员改了什么，Agent 记住"，形成人-AI 双向学习闭环（2026-08-24 决策） |
| D36 | 不确定性升级规则（v3.2 新增） | 任务描述/引用内容涉金额、对外承诺、删除数据三类时强制 requires_approval=1（状态机进 waiting_approval）；Agent 自我评估低置信（评测集匹配失败或明确声明不确定）自动转值班 Agent（zhiban）复核后再交付（2026-08-24 决策） |

### 五、执行步骤

#### 第 1 阶段：基础环境 + Hermes + DeepSeek（非交互配置）

```bash
apt update && apt upgrade -y
apt install -y curl git python3 python3-venv python3-pip
# 本机为 Ubuntu 24.04 + 预装 Docker 29.6.1（已确认），跳过 docker 安装：
# 若执行环境无 Docker，则补装：apt install -y docker.io docker-compose-plugin && systemctl enable --now docker
# Node 22+（前端构建需要；apt 源默认 18 太旧。后端 node:sqlite 需 Node 22+，实测 v26.8.2）：
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
node -v # 确认 v20+
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
# N4：hermes 可能不在非交互 shell 的 PATH：
# export PATH="$HOME/.local/bin:$PATH" # 以安装脚本实际提示为准
hermes config set model.provider deepseek
hermes config set model.base_url https://api.deepseek.com
hermes config set model.default deepseek-chat
# B1：DeepSeek key 占位 —— 部署时管理员填入真实 key：
# echo 'DEEPSEEK_API_KEY=sk-<管理员部署时填入真实key>' >> ~/.hermes/.env
hermes doctor
hermes chat -q "回复OK两个字" # 验证前必须已填真实 key
```

#### 第 2 阶段：4 个预设 Agent（C1/C2/B1 原生方案）

C1 Kanban 共享：写共享环境文件供 systemd 引用（B3）：

```bash
cat > /etc/hermes.env <<'EOF'
```

HERMES_KANBAN_BOARD=/root/.hermes/kanban.db

EOF

C2 多实例：Profile 名拼音（M4），创建带 --clone（B1）：

for p in cehua chengxu pingshen zhiban; do hermes profile create "$p" --clone; done

```bash
# N1：--clone 继承 SOUL —— 下一步完全覆盖 SOUL.md
# 每 profile：cehua→8642 / chengxu→8643 / pingshen→8644 / zhiban→8645
# API_SERVER_KEY 各用 openssl rand -hex 24 生成，记录进 agents.json
```

覆盖 SOUL.md（写透，不残留默认人格）：

- cehua（策划Agent）：世界观/剧情/数值。结论先行；重大变更给 2 个备选；定稿前请示负责人
- chengxu（程序Agent）：架构/代码/技术评审。附复杂度与风险；破坏性变更先发说明
- pingshen（评审Agent）：只读审查。问题清单（严重度+位置+建议）；无问题须说"通过"
- zhiban（值班Agent）：晨报/周复盘/阻塞提醒/催办/任务调度协助
每份 SOUL.md 必须含「行为边界」小节（D34，v3.2），格式固定：

【行为边界】

可自主：<该 Agent 无需人审即可执行的动作清单>

需升级人审：<触发条件清单，含 D17 审批节点（设计定稿/预算/对外承诺）与 D36 强制项（金额/对外承诺/删数据）>

禁止：<任何情况不得执行的动作清单>

失败兜底：<任务做不了/信息不足/低置信时的标准动作，如：明确告知"无法完成+原因"、转 pingshen 复核、升级 zhiban 转人工>

启动（profile 别名命令）：

cehua gateway start # 8642，其余同理 8643/8644/8645

systemd 托管 4 个服务单元，每单元加 `EnvironmentFile=/etc/hermes.env`（B3）。

验证：curl -s http://127.0.0.1:8642/health 等 4 端口全 ok；

```bash
hermes -p cehua -q "介绍你的职责" 是策划人格。
```

#### 第 3 阶段：搭建前端项目（Vue 3 + Vite + TypeScript + Pinia + Tailwind）

```bash
npm create vite@latest team-console -- --template vue-ts
cd team-console
npm i vue-router@4 pinia @vueuse/core
npm i -D tailwindcss@3
# 素净主题（D6）：浅色/深色跟随系统，灰色占位头像 public/avatar-placeholder.png（前端在 avatar 为空时自动回退；agents.json 填 URL 即覆盖）
```

#### 第 4 阶段：后端代理服务（Node/Express，端口 8787）

##### 4.1 基础 API

- POST /api/chat → 按 agents.json 路由到实例端口；注入 Bearer key；SSE 流式透传；
懒启动 Agent 先启动再转发（4.2）；M1 请求体必须含完整 messages 数组

- GET /api/kanban → 只读查询 $HERMES_KANBAN_BOARD
- POST /api/kanban-command → 指令转聊天消息（kanban_* 工具）
- GET /api/poll → 读 ~/team-files/系统通知/ 通知文件；N2 按文件 mtime 增量；
前端轮询（D19 v3.3 修订）：通知 4 秒、看板 8 秒

##### 4.2 懒启动进程管理（C3）

代理层维护"实例运行表"（内存 + 注册表 running 字段）：

调用 /api/chat?agent=<自建Agent>

→ 查注册表 profile 与端口（8650-8999 预分配，M4 文件锁防竞态）

→ GET /health 探活：

在跑 → 转发

没跑 → <profile> gateway start → 轮询 /health（上限 60s）→ 转发

→ 前端先显示"正在唤醒 <Agent>…"

→ 后台任务（每 5 分钟）：空闲 >30 分钟实例 → 停止

启动失败 → 返回"Agent 启动失败，请管理员检查"，不静默重试。

##### 4.3 认证与成员（D2/D7）

- POST /api/register（首个为管理员）、POST /api/login、GET /api/me（JWT 仅走 httpOnly Cookie，SameSite=Lax；登录响应**只回用户信息、不回 token** —— S4.0/B3 加固，旧“响应带 token”口径作废）、POST /api/logout（清 Cookie）
- GET /api/members、POST /api/members/:id/approve（管理员）

##### 4.4 Agent 管理（D5/D16/D22）

- GET /api/agents；POST /api/agents（管理员：hermes profile create <拼音id> --clone
→ 覆盖 SOUL.md → 端口预分配 → 写注册表，不立即启动）；DELETE/PUT（管理员）

- 权限：创建/改/删仅管理员；普通成员只读

##### 4.5 文件与资料库（D4/D14）

- POST /api/files（multipart ≤10MB）→ ~/team-files/<分类>/<原名>，登记 data/files.json
- POST /api/links → 大文件网盘链接条目
- GET /api/files（过滤/搜索）、GET /api/files/:id/download；DELETE（管理员）
- Agent 联动：HERMES.md 写明"被问项目问题先查文件索引，再读 ~/team-files/"

##### 4.6 团队会话与 @Agent 拉入（D9/D18）

- data/conversations.db（SQLite）：conversations（type: dm|group）、
conversation_members、messages（sender_id、content、type=text|file|link、

created_at、recalled_at）

- 会话列表（含未读数）/ 建会话 / 增量拉取 / 发消息（成员-成员不调 LLM）/
5 分钟撤回（D18）

- @Agent 拉入（临时咨询）：@ 选择器 → 后端触发；Agent 只收最近 20 条/24h
片段，回复一次即离开；完整上下文需显式"共享完整会话"（二次确认）；

记忆联动：咨询写入 Agent 记忆与提问者画像；管理员可关"可被拉入"

- N4 注入方式（验收项 12 决定）：A=system 注入；B=user 前缀注入
（"【上下文提示】…\n片段\n【当前问题】…"）

##### 4.7 通知（PWA + 邮件兜底）

- Service Worker + Notification API，/api/poll 轮询 4 秒；B2 已保证 HTTPS secure context。（D19 v3.3 修订为按界面分档：通知 4s、聊天流 4s、任务列表 5s、看板 8s、会话列表 8s）
- cron 产物（晨报/周复盘/画像）写到 ~/team-files/系统通知/，/api/poll 读取；邮件兜底
- 手机"添加到主屏幕"（manifest.json）

##### 4.8 办公任务中心（D23，v3.0 新增，核心；v3.2 扩展审批与修正反馈 D35/D36）

数据：data/tasks.db（SQLite）：

tasks(id TEXT PK, title TEXT, description TEXT, agent_id TEXT,

ref_files TEXT(JSON 数组), ref_memories TEXT(JSON 数组),

status TEXT(queued|running|waiting_approval|done|failed),

requires_approval INTEGER(0|1, D36 三类触发或发起人勾选),

approval_status TEXT(pending|approved|rejected|modified),

approved_by TEXT, correction_note TEXT,

progress TEXT, error TEXT,

created_by TEXT, created_at TEXT, completed_at TEXT)

task_corrections(id TEXT PK, task_id TEXT, agent_id TEXT,

action TEXT(approve|reject|modify), note TEXT,

decided_by TEXT, created_at TEXT) -- D35 修正记录

outputs(id TEXT PK, task_id TEXT, file_path TEXT, file_name TEXT,

file_size INTEGER, created_at TEXT)

API：

- POST /api/tasks {title, description, agent_id, ref_files[], ref_memories[], requires_approval?}
→ 建任务（status=queued）→ 若 requires_approval=1（D36 关键词命中 金额/对外承诺/删除数据，或发起人勾选）则执行完成后进 waiting_approval → 进入该 Agent 的任务队列

- GET /api/tasks?status= → 任务列表（创建者或全员可见，按 D4 全员可查）
- GET /api/tasks/:id → 详情 + 产物列表 + 修正记录
- POST /api/tasks/:id/approval {action: approve|reject|modify, note}（D35）
→ 仅创建者/管理员；写 task_corrections；approve → status=done + 触发记忆沉淀（4.10）；

reject/modify → 回 queued（带 correction_note 重新执行）或按 note 终止；note 必填

- POST /api/tasks/:id/cancel → 仅创建者/管理员，queued/running 可取消
- GET /api/tasks/:id/outputs/:oid/download → 下载产物
执行流程（关键，v3.2 扩展）：

创建任务(queued) → 入队（同一 Agent 同时只跑 1 个任务，其余排队，D11 排队提示）

→ 轮到执行(running)：

组装任务指令发给该 Agent 的 /api/chat：

"【办公任务】<title>\n<description>\n"

+ "【引用资料】" + ref_files 对应的文件索引内容（路径+摘要）

+ "【引用记忆】" + ref_memories 对应的记忆条目内容

+ "【相关修正记录】" + task_corrections 中同类任务（同 agent，近 30 天）

最近 5 条（action+note，D35）——成员上次改了什么，Agent 执行前先看到

+ "【行为边界】" + 该 Agent SOUL.md 的行为边界摘要（D34）

+ "【交付要求】请用工具完成任务，把全部产物写入 ~/team-files/产出/<task_id>/ 目录；

若任务涉金额/对外承诺/删数据或你无法高置信完成，请在回复中明确声明（D36）"

→ Agent 执行（工具写产物）

→ 扫描 ~/team-files/产出/<task_id>/ 目录登记 outputs（完成后立即扫）

→ requires_approval=1 → status=waiting_approval（前端提示"待人工确认"，

通知发起人/管理员审批）

→ 否则 status=done

→ approved 后触发记忆沉淀（4.10 闭环）

→ D36 低置信任务：Agent 在交付要求中声明"无法高置信完成"时，

后端转 zhiban（值班 Agent）复核 → 复核通过后才进入审批/完成流程

→ status=failed 时 error 信息（失败不沉淀结论记忆，仅记录 error）

重启恢复（S4.0/B5-① 新增，实测）：进程重启后，DB 中 status=running 但已无执行者的任务（① 启动时 30 秒宽限后回收；② 每 60 秒巡检孤儿任务）自动回到 queued 重新执行，且必须同时满足两点：

（a）可见：progress 置为“系统重启后恢复（可能与中断前重复执行）”，并写一条 ~/team-files/系统通知/任务恢复-<时间>.md（含来源与任务清单），工作台通知中心可见；（b）不覆盖：恢复前先快照该任务产出目录中已有文件名（写入 meta.pre_retry_files），重试时向 Agent 注入【重试约束】——列明已有产物、严禁覆盖或删除、同名文件必须改名为 <原名>-retry-<HHMMSS>；started_at 置空，恢复执行时重新写入。

产物目录约定：~/team-files/产出/<task_id>/ 下放全部交付物

（文档/表格/图片等），支持子目录。

##### 4.9 团队共享记忆库（D24/D25，v3.0 新增，核心）

数据：data/team-memory.db（SQLite + FTS5，中文用 trigram tokenizer）：

memories(id TEXT PK, type TEXT(decision|preference|fact|conclusion),

title TEXT, content TEXT, tags TEXT,

author TEXT, visibility TEXT(private|team|restricted),

allow_members TEXT(JSON 数组，restricted 时用),

source_task_id TEXT, source_agent TEXT, created_at TEXT)

memory_fts（FTS5 虚拟表，trigram tokenizer，索引 title+content+tags）

API：

- POST /api/memories {type, title, content, tags, visibility, allow_members[]}
→ 写入记忆 + 同步 FTS 索引

- GET /api/memories?q=&type=&visibility= → 检索，按当前用户过滤 ACL：
可见 = author=我 或 visibility=team 或（visibility=restricted 且我在 allow_members）

- GET /api/memories/:id、PUT /api/memories/:id（作者/管理员）、
DELETE /api/memories/:id（作者/管理员）

- GET /api/memories/suggest?q= → 任务发起时的记忆引用建议（FTS 检索 + ACL 过滤，
返回前 10 条供 @ 引用）

写入来源（多处沉淀）：

- 任务 approved/无审批直接完成时自动沉淀（4.10）
- 成员手动"保存为记忆"（前端记忆 Tab 新建）
- @Agent 咨询有明确结论时，可由值班 Agent 或后端提取写入（type=decision）
- 画像（cron 生成）也可作为 type=preference 记忆入库存档

##### 4.10 融合闭环（D26，v3.0 新增，核心；v3.2 加入修正反馈 D35）

任务 → 沉淀记忆（任务 approved/无审批直接 done 时自动执行；failed 不沉淀）：

任务完成 → 后端自动写一条记忆：

type=conclusion

title="任务结论：<task.title>"

content="任务摘要 + 关键决策/结论 + 产物路径 ~/team-files/产出/<task_id>/"

+ (若有) "审批修正：" + 最近 task_corrections 摘要（action+note）

tags=[task.title, agent名, 产物类型]

visibility=team（默认；创建者可在任务里选 private/restricted）

source_task_id=<task_id>

记忆 → 下次引用（任务发起时）：

发起任务 → 前端"引用记忆"按钮 → GET /api/memories/suggest?q=<描述关键词>

→ 选 1-N 条 → 作为 ref_memories 传给 POST /api/tasks

→ 执行时注入 Agent 上下文（4.8 执行流程）

闭环图示：

办公任务执行 → 产物交付(~/team-files/产出/) → 自动沉淀记忆(team-memory.db)

↑ ↓

带记忆执行 ← 发起任务时 @引用记忆(suggest) ← 下次任务检索

##### 4.11 MCP 中枢网关（D28/D29，v3.1 新增，核心）

目标：让 8787 代理层成为"入口唯一、零件可换"的 MCP 网关——既把团队自研能力

暴露给外部（MCP server 角色），又能接入外部平台（MCP client 角色）。

##### 4.11.1 暴露团队能力为 MCP server（对外）

- 在 8787 上增加 /mcp 端点（Streamable HTTP 传输，Bearer 认证复用现有 JWT/API key）
- 暴露工具（每个工具包装现有 /api 实现，不改业务逻辑）：
memory_search(query, type?, limit?) → 包装 GET /api/memories?q=

memory_add(type, title, content, ...) → 包装 POST /api/memories

task_create(title, description, ...) → 包装 POST /api/tasks

kanban_list(status?) → 包装 GET /api/kanban

file_search(keyword?) → 包装 GET /api/files

- 认证与 ACL 不变：外部调用者需携带有效成员 token，记忆/任务按该用户权限过滤
- 目的：将来任何外部 Agent（Claude Code / Codex / 竞品 Agent）都能通过标准 MCP
协议使用"团队记忆/任务"，即团队记忆即服务（呼应产品化方向，勿过度设计，

本期只需跑通 1 个外部调用方验证）

##### 4.11.2 接入外部 MCP server（对内，可选，默认关闭）

- Hermes 中枢通过 hermes mcp add 接入外部 server（TencentDB Agent Memory、
MySQL、Notion 等）——本期不强制接入任何外部 MCP，仅保留配置能力：

- hermes mcp add <name> --url <endpoint> 或 --command <cmd>（以 hermes 实际 CLI 为准）
- 接入后的工具自动出现在 Agent 工具集，前端无感知
- 接入触发条件（与七、记忆层演进策略一致）：记忆需求升级 / 游戏要部署 TencentDB 时
- 模型切换（D29）：DeepSeek/Claude 等在 Hermes provider 配置层切换，前端入口不变

#### 第 5 阶段：前端页面与组件

- 登录/注册页：极简（D6），团队名 + Logo 占位
- 主布局（三栏，仿飞书/企微）：
- 左栏：会话列表两区（团队交流 + 团队 Agent）+ 新建会话/群聊
- 主区：聊天流（同一气泡组件；流式 SSE；📎 ≤10MB；群聊 @；懒启动"正在唤醒"；
M1 会话历史 IndexedDB 持久化，刷新不丢）

- 顶栏 Tab：聊天 | 看板 | 任务 | 画像 | 资料库 | 记忆 | 设置（v3.0 新增 任务/记忆）
- 看板 Tab：任务卡（标题/状态/assignee/评论），新建任务 → kanban-command
- 任务 Tab（D23，新增）：
- 发起任务表单：标题、描述、选 Agent、@引用资料文件（files）、
@引用记忆（memories/suggest）、可见性（team/private/restricted）

- 任务列表（卡片：状态徽标 queued「排队中」/running「执行中」/waiting_approval「待确认」/done「完成」/failed「失败」+ 进度文案 + 排队提示"正在忙，前面还有 N 人"）
- 任务详情：描述 + 引用清单 + 审批区（v3.2：waiting_approval 任务显示"通过/打回/修改"+ 理由输入框，D35） + 产物区（预览图片/文档 / 下载按钮 / 分享到会话）
- 取消按钮（queued/running，创建者/管理员）
- 画像 Tab（M3）：成员卡片，读 cron 画像 JSON，后端按请求者过滤（普通成员
只见自己，管理员全见）

- 资料库 Tab：文件 + 链接混合列表（分类/搜索/上传/加链接），管理员可删除
- 记忆 Tab（D24/D25，新增）：
- 搜索框（FTS 检索）+ 类型过滤（决策/偏好/事实/结论）+ 可见范围标识
- 记忆卡片列表：标题/类型/作者/可见性徽标（私有/团队/定向）/时间
- 新建记忆按钮（手动沉淀：type/title/content/tags/visibility/allow_members）
- 我的记忆：编辑/删除（作者/管理员）
- 设置 Tab：个人信息、通知开关、退出登录
- Agent 工坊（设置内，管理员）：Agent 卡片 + 新建表单 + 编辑/停用
- 移动端（D8）：响应式，<768px 左栏抽屉、Tab 置底

#### 第 6 阶段：部署（域名 + HTTPS，B2/D13）

```bash
npm run build
apt install -y caddy
cat > /etc/caddy/Caddyfile <<'EOF'
```

<你的域名> {

root * /opt/team-console/dist

file_server

handle /api/* {

reverse_proxy 127.0.0.1:8787

}

try_files {path} /index.html

}

EOF

```bash
systemctl enable --now caddy # Caddy 自动签发/续期 Let's Encrypt 证书
# 前置：域名 A 记录已解析；安全组放行 80、443
# 代理服务 systemd 托管；4 个 gateway systemd 托管（每单元 EnvironmentFile=/etc/hermes.env）
```

#### 第 7 阶段：团队机制（Kanban + cron + HERMES.md + 邮件 + Skill）

```bash
# Kanban（C1）
hermes kanban init
hermes kanban create "剧情系统设计" --body "第一章三个抉择点分支设计与文案" --assignee 策划Agent
hermes kanban create "美术规范" --body "角色/场景美术风格统一规范" --assignee 评审Agent
hermes kanban create "对话框架" --body "NPC对话系统技术框架" --assignee 程序Agent
hermes kanban create "数值表V2" --body "经济与成长数值平衡表" --assignee 策划Agent
# cron（M2/M3，绑定 zhiban；tick lock 防重复，无需自研去重）
```

zhiban cron create "0 9 * * *" --prompt "扫描Kanban，汇总进行中/阻塞/待拍板；用 file 工具把结果写入 ~/team-files/系统通知/晨报-YYYYMMDD.md；同时发邮件（N3：即使写文件失败也必须发邮件）"

zhiban cron create "0 10 * * 1" --prompt "本周复盘：完成/阻塞/风险/下周计划/机制改进建议；写入 ~/team-files/系统通知/周复盘-YYYYMMDD.md；同时发邮件（N3）"

zhiban cron create "0 6 * * *" --prompt "汇总每位成员近期协作记录，生成成员画像 JSON，写入 ~/team-files/系统通知/画像/画像-YYYYMMDD.json；同时将重要偏好同步为 type=preference 记忆（经 /api/memories）"

```bash
# Skill 安装（N1）：hermes skills search/install，安装 1 个示例技能验证链路
# 项目仓库根目录写 HERMES.md（成员清单、Agent 角色与拼音对应表、汇报格式、
# 审批节点【D17】、共享目录 ~/team-files/、大文件走网盘【D14】、通知目录约定、
# 办公任务交付规范：产物一律写 ~/team-files/产出/<task_id>/、
# 记忆沉淀规范：重要决策请同步为记忆、Skill 安装说明【N1】）
```

#### 第 8 阶段：备份与收尾（D12）

```bash
# 腾讯云控制台 → 轻量服务器 → 快照 → 开启自动快照（每周 1 次，保留 2 份）
# 或 CLI：tccli lighthouse CreateInstanceSnapshot
# 验收：reboot 后全部服务自动恢复
```

#### 第 9 阶段：端到端验收

4 个成员账号：首个为管理员，后续需批准；会话互不串

聊天流式正常；4 个预设 Agent 行为不同、记忆独立；DeepSeek key 已填真实值（B1）

看板 Tab：任务可见；新建任务 → 值班Agent 执行 → 刷新出现（C1 共享生效）

画像 Tab：普通成员只见自己，管理员全见（M3）

成员间私聊+群聊：准实时（聊天流 4s、会话列表 8s，v3.3 修订）、未读红点；@Agent 拉入答完即走；撤回生效；

刷新页面历史仍在（M1）

资料库：≤10MB 上传、网盘链接、同列表

HTTPS（B2）：https://域名 证书有效；手机添加到主屏幕；PWA 通知弹窗实测

```bash
reboot 后全部服务自动恢复；自动快照已开启（D12）
cron 到点：晨报写文件+邮件；画像 JSON 生成（D20/D21）
```

懒启动（C3）：新建测试 Agent → 首次对话"正在唤醒"→ 60s 内可回复 →

30 分钟自动停止 → 再次拉起

办公任务中心（D23，核心验收）：

- 发起任务（选 Agent + 描述 + @引用 1 份资料文件）→ 状态 queued → running
- Agent 用工具执行，产物写入 ~/team-files/产出/<task_id>/
- 完成后：状态 done、产物列表出现、预览/下载可用、可分享到会话
- 同一 Agent 连发 2 个任务 → 第 2 个排队并显示"前面还有 1 人"（D11）
- 失败场景：故意给不可能完成的任务 → status=failed + error 信息
system 注入验证（N4）：结果决定 @Agent 拉入注入方式 A/B，写入部署报告

团队记忆库（D24/D25，核心验收）：

- 任务完成后，team-memory.db 自动出现一条 conclusion 记忆（闭环第一步）
- 搜索"数值"能召回"数值表V2"相关记忆（FTS 检索生效）
- ACL：成员 A 建 private 记忆 → 成员 B 检索不到；team 记忆全员可见；
restricted 仅指定成员可见

- 手动新建记忆（type=decision）成功并可检索
融合闭环（D26，核心验收）：

- 发起任务 1（如"做美术风格分析"）→ 完成 → 自动沉淀记忆
- 发起任务 2，发起时 @引用任务 1 的记忆 → Agent 上下文包含该记忆 →
回复中体现"基于上次分析"（引用生效）

- 全程无 TencentDB 依赖，纯 Hermes + 自研层跑通
Skill 链路（N1）：hermes skills list 可见；提问触发技能生效

MCP 网关（D28，v3.1 核心验收）：

- GET http://127.0.0.1:8787/mcp 或等价探测确认 MCP 端点存活（以 MCP 协议握手为准）
- 用一个外部 MCP 客户端（或 hermes mcp 连接测试）调用 memory_search，
能按成员 token 检索到该用户可见的记忆（ACL 生效）

- 调用 task_create 能创建任务并出现在工作台任务列表
- 验证"团队记忆即服务"链路：外部调用方（模拟 Claude Code/Codex）通过 MCP
使用团队记忆成功，写入部署报告

入口唯一（D29，v3.1 验收）：全程无 WorkBuddy/外部办公工作台依赖；

成员仅通过工作台界面完成聊天/任务/记忆/看板全部操作；模型切换在配置层

完成（文档说明如何切 DeepSeek/Claude），前端入口不变

修正反馈闭环（D35，v3.2 验收）：

- 发起一个 requires_approval 任务（如描述含"预算"）→ 执行完成后状态为
waiting_approval，前端出现审批区

- 审批人选择"修改"并填写理由 → 记录写入 task_corrections；再次发起同类任务时，
Agent 上下文出现【相关修正记录】，回复/产物体现"避免上次被否的点"

- conclusion 记忆 content 含审批修正摘要
行为边界与升级规则（D34/D36，v3.2 验收）：

- 4 个预设 Agent 的 SOUL.md 均含「行为边界」小节（可自主/需升级人审/禁止/失败兜底），
HERMES.md 有边界总表

- 给 Agent 下"删除某文件/对外承诺/报预算"类指令 → 任务自动 requires_approval
- 给不可能完成的任务 → Agent 明确"无法完成+原因"，不硬编（D36 失败兜底）

### 六、交付物清单

部署报告：域名、端口（8642-8645 + 8650+）、API key、管理员账号、N4 验证结果

《成员接入手册》：网址、注册、七个 Tab 用法、@Agent 用法、撤回、任务中心、记忆库

《前端开发者说明》：项目结构、代理层接口文档（含任务/记忆 API）、懒启动说明、

产物目录约定、占位头像（public/avatar-placeholder.png + avatar 字段透传）

HERMES.md 内容

故障排查表（含懒启动/任务失败排查）

二期备忘：山河云台主题、群聊 Agent 常驻开关、**记忆库升级向量语义检索

（当前 FTS5 关键词检索；二期可接 embedding 或 TencentDB 升级语义）**、

可观测（统计级，D32）：每 Agent 调用次数/成功率/平均耗时/Token 估算 +

成本看板 + 高频场景 TopN + 低成功率链路提示（数据源：任务中心 + /api/chat 日志 +

```bash
cron 画像）；配合记忆评测集（四 Agent 各 20-50 条黄金用例）形成"工程纪律闭环"；
```

边界决策（D33）：不做 Agent 治理平台，定位=小型创意团队的数字员工办公室 + 团队记忆容器；

「初见报告」机制（借鉴 Memmy）：新成员/新 Agent 加入时自动生成团队初见报告

（团队现状/关键决策/协作习惯），降低冷启动成本；

修正反馈闭环（D35，v3.2）：task_corrections 数据随记忆评测集一起纳入二期

运营统计（修正率=被打回任务占比，作为 Agent 质量指标）

### 七、记忆层演进策略（团队决策，v3.0 附录）

当前状态：团队记忆用自研 SQLite 记忆库（data/team-memory.db），不依赖 TencentDB。

为什么：4 人团队记忆量级小（每天几十条消息），显式沉淀（任务结论 + 手动保存 +

```bash
cron 画像）已覆盖 90% 协作记忆；2核4G 资源紧张，加 TencentDB 三件套大概率 OOM；
```

记忆抽取持续烧 token（几十～几百元/月）。

何时切换 TencentDB（触发条件，满足任一即评估切换）：

"群里随口定的决策经常找不到" → 需要对话自动捕获（L0-L4 分层）

"搜文件只能靠文件名，搜不到内容" → 需要 Wiki/CodeGraph 语义检索

游戏开发启动，TencentDB 反正要部署给游戏用 → 一套基础设施两用，边际成本最低

切换成本与方式：记忆层已隔离在 /api/memories 接口之后，前端、任务中心、闭环

一行不改；只重写代理层记忆 API 后端（对接 TencentDB SDK/MCP），约 1-2 天。

对话记忆走 Hermes 官方 memory_tencentdb provider（已验证存在），文件记忆走

MemoryKnowledge 知识服务（8424）。

v3.1 补充（MCP 方式）：TencentDB 也可作为外部 MCP server 接入（hermes mcp add，

见 4.11.2）——接入后其记忆工具自动进入 Agent 工具集，与自研记忆库并存过渡，

切换更平滑，前端无感知。

决策记录：2026-08-18 团队确认——现在自研跑通机制，游戏开发期部署 TencentDB，

团队记忆层按触发条件切换，两头好处各归各位。

### 八、约束

- 只使用「接口边界」清单里的通道，禁止发明后端 API；自研接口按 4.8/4.9 定义实现
- 前端不接触任何密钥（全部经 8787 代理）
- 决策清单第四节不得偏离；不确定参数以实际命令输出为准
- N4 验证项必须在 @Agent 拉入实现前完成
- 每个模块完成即自测并汇报；遇错先诊断再继续
- N3 风险注记：2核4G 跑 4 个常驻实例内存偏紧（峰值 3-3.5GB）；若 OOM 将低频
预设 Agent 改懒启动，结论写进部署报告

- B2 依赖项：部署前必须完成域名购买 + DNS 解析 + 放行 80/443；
若域名未就绪先暂停部署，不要用 IP 直连代替（D13 已变更）

