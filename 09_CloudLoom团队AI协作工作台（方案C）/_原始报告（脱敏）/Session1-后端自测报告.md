> 📄 **作品集展示副本（已脱敏）**：服务器地址 / 主机名 / 域名 / 邮箱 / 凭据 / 令牌均已替换为占位符；
> 完整原报告不随作品集仓库分发。指标与结论未作任何修改。

# Session 1 · 后端自测报告（阶段 1 验收）

| 项目 | 内容 |
|---|---|
| 项目 | CloudLoom 团队协作工作台（方案 C） |
| 服务器 | <服务器IP>（Ubuntu 24.04 LTS · 腾讯云轻量 2C4G） |
| 阶段 | 1 · 后端代理层基础（SPEC 4.1-4.7 + 4.11 骨架 + 前端脚手架） |
| 权威规格 | /opt/team-console/SPEC.md v3.2 |
| 执行稿 | /opt/team-console/prompts/工具版/Session1-4-KimiCode合并执行稿.md |
| 报告日期 | 2026-09-13 |
| **验收结论** | **8 / 8 项通过 → 满足 G1 门禁** |

---

## 0. 基线来源说明（务必先读）

本阶段开工时，服务器上存在一份**前序代理归档的阶段 1 实现**：/opt/team-console/_backup-20260913/
（约 1200 行后端 + 已构建前端脚手架 + node_modules），与任务简报中「前一代理未写入任何文件、
从干净状态开始」的前提**不符**。此处未按简报直接推翻重写，而是先做审计，审计结论：

- 归档后端**质量良好、与 SPEC 4.1-4.7 / 4.11 高度一致**，可正常启动并连通 4 个 Agent 网关；
- 审计期实测 30+ 项检查通过；
- 发现若干缺口（见 §8）。

**经用户确认后采纳归档为 G1 基线**（决策：「采纳为基线，一路跑到 G4」），执行路径为：
恢复归档 → 修缺口 → 装 systemd → 补 N4 实测 → 8 项验收 → 本报告。

### 0.1 「必修缺口」的实际收敛结果（诚实记录）

审计时曾列出 4 项「必须修复」，实际执行后**只有 2 项是真缺陷**：

| 审计结论 | 实际结果 |
|---|---|
| ① hermes profile delete --force flag 不存在 | **真缺陷**，已修（§8.1） |
| ② files.js 分类依赖 multipart 字段顺序 | **真缺陷**，已修（§8.2） |
| ③ systemd unit 未安装 | 属实：已安装并 enable（§8.3） |
| ④ hermes gateway start/stop/uninstall 需 --system | **假设被实测推翻，已撤回**（§8.4） |

> §8.4 的两个假设经实机验证不成立，属审计阶段的误判。按「不得静默跳过」原则，此处显式记录撤回，
> 而非悄悄把「已修」写进结论。

---

## 1. 交付概览

### 1.1 目录与模块

    /opt/team-console/
    ├── server/                      Node/Express 代理层（:8787，含 /mcp）
    │   ├── src/  14 个模块 / 1213 行
    │   ├── .env                    600  · 仅 JWT_SECRET
    │   └── node_modules/
    ├── team-console/                Vite + Vue3 + TS + Pinia + Tailwind 前端脚手架
    │   ├── src/   11 个文件 / 226 行
    │   └── dist/  已构建（8 个文件，供 :3000 静态服务）
    ├── data/                        conversations.db · files.json
    ├── agents.json                  600  · 5 个 Agent（4 预设 + 1 测试）
    ├── team-console.service         systemd unit（服务器副本）
    └── reports/                     本报告

模块行数（wc -l）：

| 模块 | 行 | 职责 |
|---|---|---|
| conversations.js | 172 | 4.6 会话 · 增量拉取 · @Agent 拉入 · 撤回 |
| agents.js | 143 | 4.4 Agent 管理（创建/编辑/删除） |
| mcp.js | 124 | 4.11 MCP 网关（Streamable HTTP） |
| lazystart.js | 110 | 4.2 懒启动进程管理 |
| auth.js | 104 | 4.3 认证（JWT httpOnly cookie） |
| chat.js | 103 | 4.1 /api/chat（SSE 流式透传） |
| files.js | 95 | 4.5 文件与资料库 |
| util.js | 64 | 原子写 / 文件锁 / 清洗 |
| config.js | 60 | 路径与常量 |
| registry.js | 58 | agents.json 读写 |
| db.js | 53 | node:sqlite 连接与建表 |
| index.js | 52 | Express 装配 + 静态服务 |
| kanban.js | 43 | 4.1 看板只读 + 命令 |
| poll.js | 32 | 4.1/4.7 通知轮询 |
| **合计** | **1213** | |

### 1.2 运行时

| 项 | 值 |
|---|---|
| Node | **v26.8.2**（npm 11.19.1） |
| 依赖 | express ^5.2.1 · jsonwebtoken ^9.0.3 · multer ^2.3.0 · cookie-parser ^1.4.7 |
| SQLite | node:sqlite 内置 DatabaseSync（WAL） |

> SPEC 写的是 Node 20 LTS，实机为 **26.8.2**。代码依赖 node:sqlite（Node ≥22 才有），
> 因此**不能降级到 Node 20**。此为环境事实差异，非缺陷，已记录（§9）。

### 1.3 systemd 托管

/etc/systemd/system/team-console.service —— enabled，开机自启：

    [Unit]
    Description=CloudLoom Team Console Proxy (API 8787 + MCP + static 3000)
    After=network-online.target
    Wants=network-online.target
    StartLimitIntervalSec=0
    [Service]
    Type=simple
    User=root
    Group=root
    ExecStart=/usr/local/bin/node /opt/team-console/server/src/index.js
    WorkingDirectory=/opt/team-console/server
    EnvironmentFile=/opt/team-console/server/.env
    Restart=always
    RestartSec=3
    StandardOutput=journal
    StandardError=journal
    [Install]
    WantedBy=multi-user.target

---

## 2. 验收结果总表

| # | 验收项（执行稿 1.4） | 结果 | 证据 |
|---|---|---|---|
| 1 | 注册首个账号成管理员；第二个待批准；批准后可登录 | 通过 | §3.1 |
| 2 | 成员 A 私聊 B：后端增量拉取正确 | 通过 | §3.2 |
| 3 | 上传 ≤10MB 可下载；加网盘链接；管理员可删 | 通过 | §3.3 |
| 4 | 消息 5 分钟内撤回；撤回后显示「已撤回」 | 通过 | §3.4 |
| 5 | 懒启动：首次 /api/chat 拉起（60s 内可对话）→ 空闲自动停止 | 通过 | §3.5 |
| 6 | N4 验证完成，结论（A/B）写入部署说明 | 通过（**方案 A**） | §5 |
| 7 | MCP 骨架：握手成功；kanban_list/file_search 可调用；memory_search 返回「服务未就绪」 | 通过 | §7 |
| 8 | reboot 后后端服务自动恢复 | 通过 | §3.8 |

---

## 3. 逐项验收证据

> 说明：本机不落地任何项目文件，全部验证经由
> `ssh -o BatchMode=yes root@<服务器IP> '<cmd>'` 在服务器上执行。

### 3.1 验收 1 · 注册审批流

全新库上「首个注册者即管理员」（审计期空库验证）：

```bash
curl -s -H 'Content-Type:application/json' \
  -d '{"username":"admin","password":"<TEST_PWD>","display_name":"负责人"}' \
  http://127.0.0.1:8787/api/register
# → {"ok":true,"user":{...,"role":"admin"}}      ← 首个即 admin  ✅
```

末态回归（非空库，验证「第二个注册后待批准 → 批准后可登录」）：

```bash
curl -s -H 'Content-Type:application/json' \
  -d '{"username":"reg28569","password":"<TEST_PWD>","display_name":"回归测试员"}' \
  http://127.0.0.1:8787/api/register
# → {"ok":true,"status":null}

curl -s -H 'Content-Type:application/json' \
  -d '{"username":"reg28569","password":"<TEST_PWD>"}' http://127.0.0.1:8787/api/login
# → {"error":"账号待管理员批准"}          ← 未批准不可登录 ✅

curl -s -b adm.jar -X POST http://127.0.0.1:8787/api/members/<id>/approve
# → {"ok":true,"status":"active"}         ← 批准

curl -s -c n.jar -H 'Content-Type:application/json' \
  -d '{"username":"reg28569","password":"<TEST_PWD>"}' http://127.0.0.1:8787/api/login
# → {"ok":true,"user":"reg28569"}         ← 批准后可登录 ✅
```

登录响应同时下发 Set-Cookie（凭证形态符合 SPEC 4.3）：

    Set-Cookie: tc_token=<REDACTED>; Max-Age=604800; Path=/; Expires=...; HttpOnly; SameSite=Lax

当前成员（回归临时用户已于 §3.9 清理）：admin/admin、zhang/member、li/member、wang/member，均 active。

### 3.2 验收 2 · 私聊 + 增量拉取

```bash
CID=$(curl -s -b adm.jar -H 'Content-Type:application/json' \
  -d '{"type":"dm","member_ids":["<zhang_id>"]}' \
  http://127.0.0.1:8787/api/conversations | jq -r .conversation_id)
# → 6cfb3293-3105-48c0-9b55-e536b0c0cdee

# 发 2 条
curl -s -b adm.jar -H 'Content-Type:application/json' -d '{"content":"回归消息 1"}' \
  http://127.0.0.1:8787/api/conversations/$CID/messages
curl -s -b adm.jar -H 'Content-Type:application/json' -d '{"content":"回归消息 2"}' \
  http://127.0.0.1:8787/api/conversations/$CID/messages

# 全量
curl -s -b adm.jar http://127.0.0.1:8787/api/conversations/$CID/messages
# → {"ok":true,"n":2,"max_seq":6}

# 增量（since=5）
curl -s -b adm.jar "http://127.0.0.1:8787/api/conversations/$CID/messages?since=5"
# → {"ok":true,"n":1,"contents":["回归消息 2"]}     ← 只回增量 ✅

# 未读数（zhang 视角）
curl -s -b zhang.jar http://127.0.0.1:8787/api/conversations
# → {...,"unread":2,"members":["张策划","负责人"]}  ← 未读红点数 ✅

# 已读上报后
curl -s -b zhang.jar -H 'Content-Type:application/json' -d '{"seq":999}' \
  http://127.0.0.1:8787/api/conversations/$CID/read
# → {"ok":true}
# 再拉 → {"unread":0}                              ← 清零 ✅
```

DM 去重也生效：对同一 2 人重复 `POST /api/conversations` 返回 `{existed:true}`，不新建。
另外，非会话成员读取该会话返回 `403 不在该会话中`（隔离性正确）。

### 3.3 验收 3 · 文件 / 网盘链接 / 下载 / 删除

```bash
FID=$(curl -s -b adm.jar -F "file=@r.txt" -F "category=美术" \
  http://127.0.0.1:8787/api/files | jq -r .file.id)
# → {"ok":true,"name":"r(1).txt","category":"美术","size":19}   ← 分类正确落位 ✅

curl -s -b adm.jar -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:8787/api/files/$FID/download
# → 200                                                          ← 可下载 ✅

# 网盘链接（字段名为 name，非 title）
LID=$(curl -s -b adm.jar -H 'Content-Type:application/json' \
  -d '{"name":"回归网盘链接","url":"https://pan.example.com/s/reg","category":"资料库"}' \
  http://127.0.0.1:8787/api/links | jq -r .file.id)
# → {"ok":true,"kind":"link","name":"回归网盘链接","url":"..."} ✅

curl -s -b adm.jar -o /dev/null -w '%{http_code}' http://127.0.0.1:8787/api/files/$LID/download
# → 400   ← 链接条目不走下载，提示直接访问 url ✅

# 超限（D14）
head -c 11000000 /dev/urandom > big.bin
curl -s -b adm.jar -F "file=@big.bin" http://127.0.0.1:8787/api/files
# → {"error":"文件超过 10MB 上限（大文件请走网盘链接，D14）"} ✅

# 删除权限
curl -s -b zhang.jar -X DELETE http://127.0.0.1:8787/api/files/$FID -o /dev/null -w '%{http_code}'
# → 403   ← 非管理员被拒 ✅
curl -s -b adm.jar -X DELETE http://127.0.0.1:8787/api/files/$FID
# → {"ok":true,"deleted":"<id>"} ；磁盘文件同时 unlink（残留数 0）✅
```

重复上传同名文件会自动改名（`r.txt` → `r(1).txt`），不覆盖既有文件。

### 3.4 验收 4 · 5 分钟撤回（双向验证）

```bash
NEW=$(curl -s -b adm.jar -H 'Content-Type:application/json' \
  -d '{"content":"回归-窗口内撤回"}' \
  http://127.0.0.1:8787/api/conversations/$CID/messages | jq -r .message.id)

curl -s -b adm.jar -X POST http://127.0.0.1:8787/api/messages/$NEW/recall
# → {"ok":true,"recalled_at":"2026-09-13T15:03:42.029Z"}          ← 窗口内成功 ✅

curl -s -b adm.jar http://127.0.0.1:8787/api/conversations/$CID/messages
# → {"recalled":true,"content":"",...}                            ← 「已撤回」✅
```

负向（三种拒绝路径全部实测）：

| 场景 | 响应 |
|---|---|
| 重复撤回 | `{"error":"已撤回过"}` |
| 非发送者撤回（zhang 撤 admin 的） | `{"error":"仅发送者本人可撤回"}` |
| 超 5 分钟（受控：将该消息 created_at 回拨 6 分钟） | `{"error":"超过 5 分钟，无法撤回（D18）"}` ✅ |

> 第三条为**受控测试**：直接改写该条测试消息的 created_at 以触达窗口外分支，
> 免去等待 5 分钟。改写对象仅为本测试新建的消息，不涉及既有数据。

### 3.5 验收 5 · 懒启动（唤醒 + 空闲自动停止）

**唤醒**（重启后冷态，testbot 端口 8650 无监听）：

```bash
curl -s -b adm.jar -H 'Content-Type:application/json' \
  -d '{"agent":"testbot","messages":[{"role":"user","content":"只回复 LAZY-OK2"}],"stream":false}' \
  http://127.0.0.1:8787/api/chat
# → {"ok":true,"content":"LAZY-OK2"}     拉起耗时 8s（≪ 60s 上限）✅
#   :8650 监听数 0 → 1
```

**空闲自动停止**（用临时 drop-in 把阈值压到 90s / 扫描 20s 以加速验证）：

    [2026-09-13 23:04:08] 唤醒 testbot，last_active = 15:04:08.417Z
    [2026-09-13 23:06:0x] [lazystart] 空闲超 2min，已停止: testbot
                          → running=false，:8650 监听 0，unit inactive  ✅

验证要点：

- last_active **全程停在唤醒时刻** —— 说明轮询 `/api/agents` 不会刷新空闲计时器，空闲判定未被观测行为干扰；
- 停止后**预设 4 网关不受影响**（cehua/chengxu/pingshen/zhiban 均 active），符合 D5「预设常驻、自建懒启动」；
- 临时 drop-in 已删除并 daemon-reload，IDLE_STOP_MS 覆盖数 = 0，服务恢复默认 30min 阈值（§3.5.1）。

> 补充说明：首次轮询只等到 90s，扫到 running=true 就结束了，未覆盖停止时刻。
> 经查 `lazystart.js` 的扫描间隔为 20s、阈值 90s，停止发生在约 135s 处；
> 延长观察后即取到上述停止日志，**该验收项为实测通过，非推断**。

#### 3.5.1 临时改动还原确认

    drop-in 目录存在: 否（已清理）
    Environment 覆盖: ''
    IDLE_STOP_MS 覆盖处数: 0
    unit 片段: 0 个
    服务: active / enabled

### 3.6 验收 6 · N4 验证

见 §5，结论 **方案 A**。

### 3.7 验收 7 · MCP 骨架

见 §7。

### 3.8 验收 8 · reboot 后自动恢复

**做法**：`nohup bash -c 'sleep 3; /sbin/reboot' &` 触发重启，随后轮询 `uptime -s` 判断真实重启
（避免刚断连时误判为「已恢复」）。

    触发前启动时刻: 2026-09-13 22:51:34
    [05s] 离线   [10s] 离线   [15s] 新启动时刻: 2026-09-13 23:01:14  ✅ 已重启

重启后逐项复验（**对最终配置**，含已恢复的前端 dist）：

| 检查 | 结果 |
|---|---|
| caddy / team-console / 4 预设网关 | 全部 active + enabled，启动于 23:01:23~24 |
| hermes-gateway-testbot | inactive + disabled ← 懒启动正确语义 |
| 监听端口 | :80 :443 :3000 :8642-8645 :8787（8642-8645 仅 127.0.0.1） |
| 数据持久化 | users 4 · conversations 1 · messages 4 · 看板 tasks 4 · 资料库 4 条 |
| 登录 | {"ok":true,"user":"admin"} |
| 预设对话 | {"ok":true,"model":"cehua","content":"恢复完成"} |
| 懒启动冷启 | testbot 0 → 1 监听，8s，LAZY-OK2 |
| MCP | 握手成功，serverInfo={"name":"cloudloom-mcp-gateway","version":"1.0.0"} |
| 静态前端 | https://127.0.0.1/ → 200，/login SPA fallback → 200 |
| Caddy 降级链路 | /api/health → 200，/assets/index-*.js → 200 |
| hermes 定时任务 | 3 个 active，调度器运行中，下次 2026-09-14 06:00（画像） |

**关于「重启后首次聊天失败」的澄清**：首次重启后 10s 内立刻发起 `/api/chat` 得到空响应 ——
原因是 4 个网关的 API Server 尚未就绪（端口已监听但 /health 未通），**非缺陷**。约 20s 后
直接探测四端口 /health 全部 200，重试聊天即正常。此为开机后短暂窗口，不影响验收。

### 3.9 测试数据清理

回归测试产生的临时用户与文件已清除，末态与后续阶段衔接：

    剩余成员: admin, li, wang, zhang
    资料库:   4 个 file 条目 ↔ 磁盘 4 个文件（一一对应）
              + 1 个 link 条目（回归网盘链接）

产出/ 下 6 个文件为 S0 看板任务产物，系统通知/晨报-20260913.md 为值班 Agent 产出，
均**不在**资料库清单内（符合设计）。

---

## 4. agents.json 当前内容（脱敏）

```json
{
  "cehua":    { "port": 8642, "api_server_key": "7b2b…（48 位，脱敏）", "name": "策划Agent",
                "description": "世界观、剧情、数值", "preset": true, "enabled": true, "created_at": null },
  "chengxu":  { "port": 8643, "api_server_key": "f93b…（脱敏）", "name": "程序Agent",
                "description": "架构设计、代码实现、技术评审", "preset": true, "enabled": true, "created_at": null },
  "pingshen": { "port": 8644, "api_server_key": "a65f…（脱敏）", "name": "评审Agent",
                "description": "独立只读审查（只评判不动手）", "preset": true, "enabled": true, "created_at": null },
  "zhiban":   { "port": 8645, "api_server_key": "c344…（脱敏）", "name": "值班Agent",
                "description": "晨报、周复盘、阻塞提醒、催办、D36 复核兜底", "preset": true, "enabled": true, "created_at": null },
  "testbot":  { "port": 8650, "api_server_key": "0848…（脱敏）", "name": "测试Agent",
                "description": "阶段1懒启动验收用测试 Agent", "preset": false, "enabled": true,
                "created_at": "2026-09-13T12:56:04.731Z" }
}
```

- 端口分配符合 SPEC C3/D5：预设 8642-8645（S0 既定），自建 Agent 从 **8650** 起。
- 权限：agents.json `600`、server/.env `600`，均**未入 git**（本机无项目文件）。
- 密钥来源：预设 4 个沿用 S0 生成值；testbot 为阶段 1 创建时新生成。
- 请求示例（与上游网关的鉴权方式）：

```bash
curl -H 'Content-Type:application/json' \
     -H "Authorization: Bearer <agent.api_server_key>" \
     -d '{"messages":[{"role":"user","content":"..."}],"stream":false}' \
     http://127.0.0.1:8642/v1/chat/completions
```

---

## 5. N4 验证结论 —— **方案 A（system 角色注入）**

### 5.1 背景

SPEC 第八节要求：@Agent 拉入会话时，注入的会话片段以 **A（system 角色消息）** 还是
**B（user 消息前缀）** 形式下发，**必须由实测决定**，不得臆断。这决定了
`conversations.js::triggerAgent()` 的实现方式。

### 5.2 实测设计

- **不可猜标记**：`N4-VERIFY-9271-KX`（此前任何会话中均未出现）
- **负对照**：不给任何上下文，直接问暗号 → 应回答「我不知道」
- **受测 A**：messages[0].role = "system" 携带标记
- **对照 B**：messages[0].role = "user" 以「【上下文】…【问题】…」前缀携带同一标记
- **流式复核**：方案 A 走 stream:true，逐块重组后校验

### 5.3 实测结果（hermes 网关 :8642，profile cehua）

| # | 用例 | 模型 | 回复 | 含标记 |
|---|---|---|---|---|
| ① | 负对照（无上下文） | cehua | 我不知道 | 否 |
| ② | **方案 A**：system 注入（非流式） | cehua | N4-VERIFY-9271-KX | **是** |
| ③ | 方案 B：user 前缀（对照） | cehua | N4-VERIFY-9271-KX | 是 |
| ④ | **方案 A**：stream:true 重组校验 | cehua | N4-VERIFY-9271-KX | **是** |

### 5.4 结论

- **Hermes API Server 采纳外部的 system 角色消息**（非流式与流式均生效）→ **方案 A 可用**；
- 方案 B 同样可行，但 A 语义更正确（会话片段不应混入用户指令流），且能避免与用户文本互相污染；
- 负对照通过，说明标记确实来自注入而非模型臆测。

**落地结论：采用方案 A**，与现有实现一致 ——
`conversations.js:154` `callAgent(agentId, [{role:'system', content: system}, {role:'user', content: user}])`，
**无需改动**。该结论已按 1.2 第 9 条要求写入本节作为部署说明的一部分。

> 附：SPEC 八、约束要求 N4 必须**先于** 4.6 的注入逻辑落地完成。本阶段实际顺序为「归档实现先存在、
> N4 后补验证」，但验证结论与实现一致（方案 A），**无需返工**，故不影响 G1。

---

## 6. 前端脚手架状态

/opt/team-console/team-console/（Vite + Vue3 + TS + Pinia + Tailwind），**11 个源文件 / 226 行**：

| 文件 | 说明 |
|---|---|
| index.html · vite.config.ts · tsconfig*.json · postcss.config.js · tailwind.config.js | 构建配置 |
| package.json · package-lock.json · node_modules/（131MB） | 依赖（vue 3.5 / vue-router 4.6 / pinia 4.0 / vite 8.3 / tailwindcss 3.4 / typescript 6.0） |
| src/main.ts · src/App.vue | 入口 |
| src/router.ts | 路由骨架 |
| src/stores/auth.ts | Pinia 认证 store |
| src/api.ts | API 客户端（**不含任何密钥**，符合约束） |
| src/layouts/MainLayout.vue | 主布局三栏空壳 |
| src/views/LoginView.vue | 登录页 |
| src/views/PlaceholderView.vue | 占位路由 |
| src/style.css · src/assets/* | 样式与静态资源 |
| dist/（8 文件，已构建） | 供 :3000 静态服务 |

**构建产物已恢复并接入链路**（经 Caddy 验证）：

    https://127.0.0.1/                         → 200   （index.html）
    https://127.0.0.1/login                    → 200   （SPA fallback）
    https://127.0.0.1/assets/index-CWpuf-Qj.js → 200

> 范围符合 1.2「只搭登录页 + 主布局空壳」；业务页面留待阶段 2/3。

---

## 7. MCP 骨架说明（SPEC D28）

### 7.1 端点

- 路径：`http://127.0.0.1:8787/mcp`（与 /api **同端口、同进程**，`index.js:28`）
- 传输：**Streamable HTTP**（JSON-RPC 2.0），协议版本 **`2025-06-18`**
- 鉴权：**Bearer = 复用 /api 的 JWT**（tc_token 同源），无 token 直接拒绝

### 7.2 已暴露工具（5 个）

| 工具 | 状态 | 包装目标 |
|---|---|---|
| kanban_list | **已实现** | GET /api/kanban |
| file_search | **已实现** | GET /api/files |
| memory_search | 留位 | GET /api/memories（阶段 2） |
| memory_add | 留位 | POST /api/memories（阶段 2） |
| task_create | 留位 | POST /api/tasks（阶段 2） |

留位工具当前返回：`服务未就绪：该工具为留位接口，将在阶段 2 接入真实实现（<name>）`。

### 7.3 握手与调用验证方式

用**官方 SDK** 作外部客户端（`@modelcontextprotocol/sdk` **v1.30.0**，位于 `/root/mcpclient/`）——
即真实的第三方 MCP 客户端，而非自造握手：

```bash
TOKEN=$(curl -s -H 'Content-Type:application/json' \
  -d '{"username":"admin","password":"<TEST_PWD>"}' \
  http://127.0.0.1:8787/api/login | jq -r .token)
cd /root/mcpclient && node client.mjs "$TOKEN"
```

实测输出：

    ── 1. 握手 ──
      ✅ initialize 成功
      serverInfo: {"name":"cloudloom-mcp-gateway","version":"1.0.0"}

    ── 2. tools/list ──  工具数: 5
      • kanban_list     列出团队共享看板任务（包装 GET /api/kanban）
      • file_search     检索资料库文件与网盘链接（包装 GET /api/files）
      • memory_search   …【留位：阶段 2 填充】
      • memory_add      …【留位：阶段 2 填充】
      • task_create     …【留位：阶段 2 填充】

    ── 3. tools/call kanban_list ──  → 返回 4 张看板卡 JSON（含 t_375a1a5c 对话框架/chengxu/blocked）✅
    ── 3. tools/call file_search ──  → 返回资料库条目 JSON（art.txt/美术/…) ✅
    ── 3. tools/call memory_search ─ 服务未就绪：该工具为留位接口，将在阶段 2 接入真实实现 ✅（符合预期）

    ── 4. 无 token 连接 ──
      ✅ 被拒: Streamable HTTP error: {"error":"未登录"}      ← 鉴权生效 ✅

### 7.4 已刻意为阶段 1 移除了 hermes mcp add 注册（给阶段 3 的提醒）

审计期曾用 `hermes mcp add cloudloom ...` 把本网关注册进 Hermes，**验证可行后已主动移除**，原因：

1. 该命令会把一个**有效期仅 7 天的 JWT** 写入 `~/.hermes/.env`（MCP_CLOUDLOOM_API_KEY），
   7 天后会**静默失效**，反成阶段 2/3 的隐形故障源；
2. 阶段 1 的 3 个工具尚为留位，注册后 Agent 一旦调用会看到「服务未就绪」字样，污染回复。

**阶段 3 收尾时**需以**长效凭证**（而非 7 天 JWT）重新注册。
当前状态：`hermes mcp list` → `No MCP servers configured.`
（即 4.11.2「默认关闭、本期只做暴露侧」符合 SPEC）。

---

## 8. 缺陷修复记录（diff）

### 8.1 D1 · hermes profile delete 的 flag 不存在（真缺陷）

**现象**：agents.js 删除 Agent 时调用 `hermes profile delete <id> --force`，该 flag 在
Hermes v0.19.0 **不存在**（实测 `hermes profile delete --help` 只有 `-y/--yes`），导致删除走
catch 分支、profile 残留。

**修复**（server/src/agents.js:136-138，备份 agents.js.bak-stage1fix）：

```diff
-    try { hermes(['profile', 'delete', id, '--force'], 60000); }
-    catch { try { hermes(['profile', 'delete', id], 60000); }
-            catch (e2) { console.error('[agents] profile delete 失败:', e2.message); } }
+    // 阶段1收口修复(D1)：hermes profile delete 无 --force，正确 flag 为 -y/--yes
+    try { hermes(['profile', 'delete', id, '-y'], 60000); }
+    catch (e2) { console.error('[agents] profile delete 失败:', e2.message); }
```

### 8.2 D2 · 文件分类依赖 multipart 字段顺序（真缺陷）

**现象**：files.js 用 multer.diskStorage，其 destination() 回调在 **multipart 文本字段尚未
解析完** 时读取 req.body.category。若客户端把 file 字段排在 category 之前，
分类会**静默丢失**（落为默认「资料库」），且不报错。

**修复**（server/src/files.js:20-25，备份 files.js.bak-stage1fix）—— 改用 memoryStorage：

```diff
-const storage = multer.diskStorage({
-  destination(req, file, cb) {
-    const cat = sanitizeCategory(req.body?.category);   // ← 此时 req.body 可能还是空
-    ...
-  }, ... });
+// 阶段1收口修复(D2)：改用 memoryStorage。
+// 原 diskStorage.destination() 在 multipart 文本字段尚未解析时读 req.body.category，
+// 若客户端把 file 字段排在 category 之前，分类会静默丢失（落为默认「资料库」）。
+// memoryStorage 保证进入 handler 时 req.body 已全部解析，分类与字段顺序无关（≤10MB 可接受）。
+const storage = multer.memoryStorage();
+const upload = multer({ storage, limits: { fileSize: C.UPLOAD_MAX_BYTES } });
```

handler 内相应改为写 `req.file.buffer`。回归验证：
`-F "file=@r.txt" -F "category=美术"` → `category:"美术"` 正确落位（§3.3）。
≤10MB 内存占用可接受。

### 8.3 systemd unit 安装（属实）

新建 /etc/systemd/system/team-console.service（内容见 §1.3），`systemctl daemon-reload` +
`enable --now`。重启后自启已在 §3.8 验证。

### 8.4 两个误判假设的撤回（重点）

审计阶段曾判定以下两处「必须修复」，**实机验证后均不成立，已撤回，未做任何代码改动**：

| 假设 | 实测 |
|---|---|
| hermes gateway start 需加 --system | `hermes gateway start` 会**自动识别**系统级 unit → 输出「✓ System service started」，4s 后 /health 通过 |
| hermes gateway stop / uninstall 同理 | stop →「✓ System service stopped」；uninstall 正常删除 /etc/systemd/system/hermes-gateway-testbot.service |

结论：lazystart.js 的调用方式**本来就是对的**。此处显式记录，避免后续误改。

### 8.5 本阶段其他动作（非缺陷修复）

- **恢复前端脚手架**：归档审计时只恢复了 server/ 与 data/，遗漏 team-console/（前端脚手架）。
  阶段 1 交付物第 4 项要求其存在，且阶段 2 必须**在其上增量开发**（铁律 2「不重写」），
  故从归档补回 src/ + dist/ + 配置，chown root:root。
- **静态服务重启**：`index.js:43` 的 `fs.existsSync(C.STATIC_DIR)` 在**进程启动时求值一次**，
  因此 `npm run build` 之后必须 `systemctl restart team-console` 才会生效（见 §10.5）。

---

## 9. 遗留问题与已知缺口

### 9.1 明确未做（属阶段 2/3 范围，非遗漏）

| 项 | 归属 |
|---|---|
| 4.8 任务中心 / 4.9 记忆库 / 4.10 融合闭环 | 阶段 2 |
| memory_search / memory_add / task_create 真实实现 | 阶段 2（留位签名见 §10.4） |
| 前端业务页面（任务/记忆/看板/画像/资料库/设置 Tab） | 阶段 2/3 |
| 移动端适配、PWA、Caddy 完整路由 | 阶段 3 |
| 对外 HTTPS 正式证书（域名未就绪，走降级路径） | 阶段 4（SPEC 约束 B2） |

### 9.2 SPEC 4.6 相关：部分能力尚未落地（建议阶段 2 复核）

| 缺口 | 说明 |
|---|---|
| 「可被拉入」开关 | 4.6 提到管理员可控制某 Agent 是否可被 @ 拉入；当前 triggerAgent 只判 enabled !== false，**无独立开关** |
| 「共享完整会话」二次确认 | 目前仅存在于注入提示文本中（`如需完整上下文，提示对方显式「共享完整会话」`），**后端无对应通路** |
| 咨询写入 Agent 记忆 / 提问者画像 | 4.6 提及，**阶段 2 随记忆库一并实现** |

> 这三项属「4.6 的完整形态」，阶段 1 的范围（1.2 第 7 条）只要求「@ 通知解析 + 5 分钟撤回」，
> 故**不阻塞 G1**，但需在阶段 2 补齐或明确降级。

### 9.3 工程质量提示（非阻塞）

| 项 | 说明 |
|---|---|
| acquireLock 忙等 | 自旋等待文件锁会**阻塞事件循环**。当前锁竞争只发生在低频写（agents.json / files.json），可接受；阶段 3 若出现高并发写需改为异步 |
| Cookie 缺 secure | tc_token 未带 Secure。当前为 http://127.0.0.1 访问，加了反而不可用；**阶段 4 上 HTTPS 后必须补**（记入待办） |
| Node 版本 | SPEC 写 Node 20 LTS，实机 **26.8.2**；代码依赖 node:sqlite（≥22），**不可降级** |
| uninstall 残留 | hermes gateway uninstall 会留下 hermes-gateway-*.service.d/ 空目录（无害） |
| 静态服务启动期求值 | 见 §8.5 第二条 |
| sweep 日志措辞 | 打印 `空闲超 ${round(IDLE_STOP_MS/60000)}min`，阈值非整数分钟时（如 90s）会显示「2min」，措辞略粗 |

---

## 10. 给阶段 2 的注意事项

### 10.1 路由约定

阶段 1 已占用（**26 个 REST + 1 个 MCP**）：

    POST /api/register      POST /api/login        POST /api/logout      GET  /api/me
    GET  /api/members       POST /api/members/:id/approve    POST /api/members/:id/disable
    GET  /api/agents        POST /api/agents       PUT  /api/agents/:id  DELETE /api/agents/:id
    POST /api/chat          GET  /api/kanban       POST /api/kanban-command
    GET  /api/poll          GET  /api/files        POST /api/files       POST /api/links
    GET  /api/files/:id/download                   DELETE /api/files/:id
    GET  /api/conversations POST /api/conversations
    GET  /api/conversations/:id/messages           POST /api/conversations/:id/messages
    POST /api/conversations/:id/read               POST /api/messages/:id/recall
    /mcp  （Streamable HTTP）

阶段 2 新增 /api/tasks*、/api/memories* 等，**不得与上表冲突**；
铁律「禁止发明 SPEC 接口边界清单外的后端 API」仍然适用。

### 10.2 端口占用

| 端口 | 用途 | 绑定 |
|---|---|---|
| 80 / 443 | Caddy（降级路径：IP + 自签证书） | * |
| 3000 | 前端静态（Caddy 非 /api 反代至此） | 127.0.0.1 |
| 8642-8645 | 4 个预设 Agent 网关 | 127.0.0.1 |
| **8650-8999** | **自建 Agent 懒启动预分配区间** | 127.0.0.1 |
| 8787 | 后端 API + /mcp | 127.0.0.1 |
| 2019 | Caddy admin | 127.0.0.1 |

### 10.3 .env 已有项

/opt/team-console/server/.env（600）当前**仅 1 项**：JWT_SECRET（64 位 hex，脱敏）。
阶段 2 新增密钥一律追加至此文件并保持 600，**不入 git、不进前端、报告中脱敏**。

系统级另有 /etc/hermes.env（S0 建，含 HERMES_KANBAN_BOARD=/root/.hermes/kanban.db）。

### 10.4 MCP 留位接口签名（阶段 2 填充用）

阶段 1 已用 `registerImpl()` 预留钩子，**阶段 2 只需注册实现，不必改动 MCP 传输层**：

| 工具 | 输入（建议） | 输出 | 需接入 |
|---|---|---|---|
| memory_search | `{ q: string, limit?: number }` | 记忆条目数组 | GET /api/memories（**须按调用者 ACL 过滤**） |
| memory_add | `{ content: string, scope?: 'private'\|'team'\|'restricted', tags?: string[] }` | 新建记忆条目 | POST /api/memories |
| task_create | `{ title: string, description?: string, agent?: string, refs?: string[] }` | 任务对象 | POST /api/tasks |

> **硬要求**：MCP 调用必须经过与 /api **相同的 JWT 认证与 ACL 过滤**（执行稿 1.4 第 4 条）。
> 已有基础：/mcp 已复用 tc_token 同一 JWT 并在无 token 时返回 `{"error":"未登录"}`（§7.3）。

### 10.5 其他约定

1. **.env / agents.json 权限固定 600**，改后请复查 `stat -c '%a %n'`；
2. data/ 下 conversations.db 用 WAL（-wal/-shm 同目录），**备份需连同 WAL**；
3. node:sqlite 的 DatabaseSync 为**同步 API**，勿在请求热路径上跑大查询；
4. 静态前端构建后**必须重启** team-console（§8.5）；
5. 懒启动的 lastActive **只由 /api/chat 与 touch() 更新**，读取 /api/agents 不会重置空闲计时（§3.5），
   阶段 2 如需「保活」须显式调 touch()；
6. 阶段 2 的 reboot 验收（2.4 第 9 条）可复用本报告 §3.8 的方法（uptime -s 轮询判真实重启）。

---

## 11. 附录 · 验收环境快照

    节点        root@<服务器IP>  (Ubuntu 24.04 LTS)
    Node        v26.8.2 / npm 11.19.1
    Hermes      v0.19.0（4 预设 profile + testbot）
    systemd     caddy · team-console · hermes-gateway-{cehua,chengxu,pingshen,zhiban}  均 enabled
    启动时刻    2026-09-13 23:01:14（验收 8 重启后）
    数据        users 4 · conversations 1 · messages 4 · kanban tasks 4 · 资料库 4 file + 1 link
    定时任务    zhiban profile：晨报 0 9 * * * / 周复盘 0 10 * * 1 / 画像 0 6 * * *
    MCP 客户端  /root/mcpclient（@modelcontextprotocol/sdk v1.30.0）
    验收执行    2026-09-13 全程经 ssh 非交互执行；本机未落地任何项目文件

### 9.4 验收账号口令（安全提示）

§3 中 curl 示例里的 `<TEST_PWD>` 为阶段 1 验收期 4 个测试账号（admin/zhang/li/wang）的**统一口令**，
按「报告中脱敏」的要求此处不落明文，实际值由项目负责人另行掌握。

> ⚠️ **建议**：这 4 个账号是验收用测试账号，口令强度与「多人共用同一口令」均不符合正式使用要求。
> 正式投用前应**删除或改密**，并为每位真实成员单独开户（首个注册者自动成为管理员）。

---

**阶段 1 结论：8/8 验收项通过，G1 门禁达成，可进入阶段 2。**
