> 📄 **作品集展示副本（已脱敏）**：服务器地址 / 主机名 / 域名 / 邮箱 / 凭据 / 令牌均已替换为占位符；
> 完整原报告不随作品集仓库分发。指标与结论未作任何修改。

# Session2 · 核心闭环测试报告（阶段 2）

> 项目：CloudLoom（方案 C）· 团队协作工作台
> 服务器：root@<服务器IP>（腾讯云轻量 2C4G · Ubuntu 24.04 LTS）
> 执行时间：2026-09-13 22:30 – 2026-09-14 00:00（CST）
> 依据：`/opt/team-console/SPEC.md`（权威）＋`prompts/工具版/Session1-4-KimiCode合并执行稿.md` §2
> 代码位置：`/opt/team-console/server`（Node v26.8.2 · Express · node:sqlite）· 前端 `/opt/team-console/team-console`（Vue3 + TS + Vite + Pinia + Tailwind）

---

## 一、结论摘要

| 项 | 结果 |
|---|---|
| 阶段 2 验收 10 项 | **9 项实测通过 + 1 项部分**（第 8 项前端：代码/构建/接口对齐完成，服务器无浏览器，真实交互验收移交阶段 3） |
| 后端 4.8 任务中心 | 3 表（tasks / task_corrections / outputs）＋ 6 API，全部 curl 实测通过 |
| 后端 4.9 记忆库 | memories + memory_fts（FTS5 trigram）＋ 5 API，ACL 实测通过 |
| 4.10 融合闭环 | 任务 done/approved → 自动 conclusion 记忆（含【审批修正】），任务引用记忆注入上下文，实测生效 |
| 4.11 MCP 网关 | 5 工具全部可用，**17/17 PASS**（外部客户端 + 按 token 的 ACL 实测） |
| 记忆 ACL（HTTP 侧） | **29/29 PASS**（private/team/restricted × 读/列/搜/改/删） |
| 前端 | 聊天流 + 任务 Tab + 记忆 Tab + 左栏 SideBar 全部完成，`npm run build` 通过（vue-tsc 0 error） |
| 重启自愈 | `reboot` 后服务全自动恢复，中断任务自动重排并跑完（闭环成功） |
| 门禁 G2 | **通过**（第 8 项残留见 §六.3 说明，已列入阶段 3 首项） |

数据留痕（实测当时）：tasks 表 16 行（done 8 / failed 8）、task_corrections 3 行、outputs 14 行、memories 17 行（team 13 / private 3 / restricted 1）。

---

## 二、验收 10 项逐条结果

| # | 验收项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 发起任务（选 Agent + @引用 1 个资料文件）→ queued → running → done；产物可预览/下载/分享 | ✅ | 任务「资料与记忆引用合并验证」（ref_files 1 个 + ref_memories 1 条）→ 产物 `评审说明_资料与记忆引用合并验证.md`（1989B）；下载 HTTP 200；分享 `POST /api/links` 返回 `{ok:true,file:{kind:"link"}}`。该任务引用的记忆命中 D36【金额】→ 初始进 waiting_approval，审批通过后转 done（见 §三.5） |
| 2 | 同一 Agent 连发 2 任务：第 2 个排队并显示"前面还有 1 人" | ✅ | A(running) 时 B 返回 `queue_ahead:1` → 前端显示「前面还有 1 人」；随后 A→done 自动 pump B |
| 3 | 不可能完成的任务 → failed + 错误信息，不卡死 | ✅ | 任务「缺失财报分析摘要」→ `failed`，`error`/`result_summary`=「任务无法完成 —— 团队资料库中不存在《云织项目 2026 年 Q4 财务报表》…」（保留 Agent 原文，非空泛报错） |
| 4 | requires_approval（描述含"预算"）→ waiting_approval → 审批"修改"+理由 → task_corrections 有记录 → 再发同类任务 Agent 上轮修正生效 | ✅ | 「协作工具预算建议」命中 D36【金额】→ 执行完进 `waiting_approval`；`modify` 记录「试算须补充三年期对比，并注明币种与含税口径；产物文件名统一用「试算稿_费用_三年期.md」」；下一轮产物即 `试算稿_费用_三年期.md`（4633B）且回复声明「按 admin 修正记录补了三年期对比、币种（CNY）与含税口径」 |
| 5 | 任务完成后 team-memory.db 自动出现 conclusion 记忆 | ✅ | 每条 done 任务均沉淀：`任务结论：工具费用一年期试算`、`任务结论：重启自愈自检`…（type=conclusion，source_task_id 指向任务，tags 含产物扩展名）；审批场景 content 内含【审批修正】段 |
| 6 | 搜索「数值」能召回相关记忆；private/team/restricted ACL 实测生效 | ✅ | 检索「数值」n=3（含《数值表V2 定稿说明》）；ACL：HTTP 侧 29/29、MCP 侧 17/17（详见 §四、§五） |
| 7 | 任务 2 @引用任务 1 的记忆 → 执行上下文包含它（回复体现"基于上次分析"） | ✅ | 任务 2 ref_memories=[任务1的 conclusion]，执行指令含【引用记忆】段；Agent 回复原文：「我引用的记忆标题是「任务结论：工具费用一年期试算」（取自其【结论】栏：2 人团队、100 元/人/月、无试用期，一年期 2400 元、三年期 7200 元，未税纯线性外推）」 |
| 8 | 前端：登录/注册可用；聊天流式可用；任务/记忆 Tab 完整可用；刷新不丢历史 | ⚠️ **代码完成 + 构建通过 + 接口对齐核对通过**；真实浏览器交互未做（服务器无任何浏览器二进制，已实测确认） | `npm run build` → vue-tsc 0 error，产物 `dist/` 由 3000 端口 200 提供；Tab/Memory/Task 视图与后端路由逐条比对一致；IndexedDB 持久化 + 服务端权威合并已实现。**真实点击验收列入阶段 3（19 项端到端验收）首项** |
| 9 | `reboot` 后服务恢复，闭环仍可跑通 | ✅ | 23:52:13 任务执行中 → 硬重启 → 23:53:36 开机自愈「中断恢复：1 个任务重新排队」→ 23:53:37 重跑 → 23:54:03 完成并沉淀记忆。team-console / caddy 均 enabled+active，8642-8645/8787/3000 全部恢复监听 |
| 10 | MCP 完整：外部客户端 `memory_search` 按成员 token 检索可见记忆（ACL 生效）；`task_create` 创建的任务出现在工作台 | ✅ | `/root/mcpclient/acceptance.mjs`：**17 PASS / 0 FAIL**；ACL 矩阵 admin↔zhang 的 private/team 互不可见性逐条验证；`task_create` 返回的 id 可在 `GET /api/tasks` 查到并被执行 |
---

## 三、核心闭环全流程（交付物 1）

### 3.1 数据模型与接口（严格按 SPEC 4.8/4.9/4.10）

`tasks.db`：**tasks / task_corrections / outputs** 三表（WAL）。
状态机：`queued → running → {done | failed | waiting_approval}`，`waiting_approval --approve--> done` / `--modify--> queued`（重跑）/ `--reject--> failed`；任意非终态可 `cancel`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/tasks` | 发起任务（title/description/agent_id/ref_files/ref_memories/requires_approval/memory_visibility） |
| GET | `/api/tasks?status=&agent_id=&limit=` | 列表（含 `queue_ahead`） |
| GET | `/api/tasks/:id` | 详情（含 outputs / corrections / meta） |
| POST | `/api/tasks/:id/approval` | `{action: approve\|reject\|modify, note}` |
| POST | `/api/tasks/:id/cancel` | 取消（带竞态保护：仅非终态） |
| GET | `/api/tasks/:id/outputs/:oid/download` | 产物下载 |

`team-memory.db`：**memories + memory_fts（FTS5 trigram）**。
`POST/GET /api/memories`、`GET /api/memories/suggest`、`GET /api/memories/:id`、`PUT /api/memories/:id`、`DELETE /api/memories/:id`。

### 3.2 执行指令注入（6 段，实测 2258 字）

实际下发给 Agent 的指令依次为：**【办公任务】→【引用资料】→【引用记忆】→【相关修正记录】→【行为边界】→【交付要求】**。要点：

- 【引用资料】：逐条给出资料库文件名 + 摘要 + 服务器路径（上例注入 `ref1.md` 的定稿摘要与路径）；
- 【引用记忆】：注入被 @ 的记忆全文（上例注入《任务结论：工具费用一年期试算》【结论】栏）；
- 【相关修正记录】：同类任务近 30 天最近 5 条 admin 审批意见（D35）；
- 【行为边界】：**运行时读取** `/root/.hermes/profiles/<agent>/SOUL.md` 的【行为边界】段（可自主 / 需升级人审 / 禁止 三类），随 SOUL 同步更新，不硬编码；
- 【交付要求】第 5 条强制机器可解析标记：`【交付状态】完成` / `【交付状态】无法完成：<原因>` / `【交付状态】低置信：<存疑说明>`（D36-① 判定依据）。

### 3.3 闭环主线（任务 → 记忆 → 引用 → 再沉淀）

| 步 | 动作 | 实测结果 |
|---|---|---|
| ① | 任务 A《工具费用一年期试算》发起（描述含"费用"） | 服务端 `detectSensitive` 命中 **【金额】** → `meta.approval_forced_by=["金额"]`，`requires_approval=1` |
| ② | A 执行完 | 进 `waiting_approval`；**此时不沉淀记忆**（0 条） |
| ③ | admin `modify`：「试算须补充三年期对比，并注明币种与含税口径；产物文件名统一用…」 | `task_corrections` +1；任务重排队 → 重跑 |
| ④ | A 重跑 | 新产物 `试算稿_费用_三年期.md`；Agent 自述「按 admin 修正记录补了三年期对比、币种（CNY）与含税口径」，并按修正意见改了文件名 → **D35 修正闭环生效** |
| ⑤ | admin `approve`：「口径与计算过程可接受，准予作为内部试算稿归档」 | `done` + 沉淀 conclusion 记忆（content 尾部含 **【审批修正】** 段） |
| ⑥ | 任务 B《资料与记忆引用合并验证》@引用 A 的记忆 + 资料库 `ref1.md` | 指令含【引用记忆】【引用资料】；B 回复点名「我引用的记忆标题是「任务结论：工具费用一年期试算」」并复述其口径 → **记忆复用生效** |
| ⑦ | B 亦命中【金额】（引用的记忆内容含预算）→ `waiting_approval` | 证明 D36 不只看任务描述，**也看引用内容**（本例由记忆标题/内容触发） |
| ⑧ | admin `approve` B | `done` + 沉淀《任务结论：资料与记忆引用合并验证》，content 末尾同样带【审批修正】 |

沉淀记忆实测样例（`team-memory.db`）：

```
id    : d7bffeee-bab9-4f42-8720-433ecb128a24
type  : conclusion      visibility: team      author: admin
title : 任务结论：资料与记忆引用合并验证
tags  : 资料与记忆引用合并验证,cehua,md          ← 含产物扩展名（来自 outputs 登记）
content: 【任务】…【描述】…【执行 Agent】cehua…【结论】…【交付状态】完成
         【产物路径】/root/team-files/产出/8ac2175e-…/
         【审批修正】两源引用准确、口径区分清楚，准予作为内部评审稿归档。
```

### 3.4 排队（同 Agent 单飞）与取消

- A(running) 期间发 B：`GET /api/tasks/:id` 返回 `queue_ahead: 1` → 前端显示「前面还有 1 人」；A 完成后自动 pump B（A done → B running → B done，服务日志可查）。
- 实现：进程内 `running` Set 做 **每 Agent 单飞**（D23），`pump` 在 `.finally` 里 `setImmediate` 续跑队列。
- 取消：running 中取消返回「已由 admin 取消」并置 `failed`（带竞态保护 `AND status IN (非终态)`）。

### 3.5 审批三态实测（task_corrections 3 条）

| action | 任务 | note | 结果 |
|---|---|---|---|
| modify | 工具费用一年期试算 | 试算须补充三年期对比，并注明币种与含税口径；产物文件名统一用「试算稿_费用_三年期.md」 | 重排队重跑，产物与口径随之改变（D35 闭环） |
| approve | 工具费用一年期试算 | 口径与计算过程可接受，准予作为内部试算稿归档 | done + 沉淀记忆（含【审批修正】） |
| reject | 工具费用两年期试算 | 两年期口径与已定稿的年度预算模板不一致，不予采纳 | failed + 记录；**后续任务主动声明「两年期口径已被 admin 驳回，未采用」** |

### 3.6 失败兜底（D36-② 与超时）

- 任务《缺失财报分析摘要》→ `failed`，`result_summary` = Agent 原文「任务无法完成 —— 团队资料库中不存在《云织项目 2026 年 Q4 财务报表》…」；**不卡死**，队列继续。
- 低置信交付 → 交 `zhiban` 复核（`meta.zhiban_review = {verdict:"pass", reason:…}`），实测在一次真实任务中自然触发。
- Agent 超时：`TASK_TIMEOUT_MS`（默认 600000ms）主动 abort，中文报错「Agent 执行超时（超过 N 秒未返回），已中止…」，置 `failed` 并保留已有回复。
- 全流程**失败路径也记录 `result_summary`**（审计不留空）。

### 3.7 重启自愈时间线（验收 9，服务端日志原文）

```
23:52:13 [tasks] 执行 ccea0e77-… → cehua（指令 1331 字）
         ← 此处硬重启（systemctl reboot，SSH 断开 65s）
23:53:36 [tasks] 中断恢复：1 个任务重新排队
23:53:37 [team-console] API 监听 http://127.0.0.1:8787（含 /mcp）
23:53:37 [tasks] 执行 ccea0e77-… → cehua（指令 1331 字）
23:54:03 [tasks] 完成 ccea0e77-…，沉淀记忆 18451510-c412-44b0-8a34-c9a2bbb4463c
```

- 重启后 `team-console` / `caddy` 均 `enabled+active`，8642-8645 / 8787 / 3000 / 80 / 443 全部恢复监听，**无需人工介入**；
- 产物 2 个（`rebootcheck.md` 3685B、`rebootcheck_v2.md` 3869B），下载 HTTP 200，记忆已沉淀，`meta.delivery_status={verdict:"完成",source:"marker"}`。

### 3.8 自愈能力加固（本阶段发现并修复的缺陷，详见 §七）

复测时发现：**执行中被重启的任务会一直停在 `running`**（旧实现只在启动时按"超过 超时+5 分钟"回收，中断 3 分钟内的任务无人回收，实测卡在 running 达 3 分 22 秒）。修复后：

- 启动即 `recoverStale({boot:true})`（30s 宽限）回收上一进程遗留的 running；
- 新增 **60s 周期巡检 `recoverOrphans()`**：DB 标 `running` 但**不在本进程执行集合**中的任务 = 必然已中断 → 立即回队重跑。
- 定向验证：注入一条 `status=running, agent_id=nosuch_agent` 的孤儿行 → **29 秒内**被巡检捕获重排，执行后以「Agent「nosuch_agent」不存在」置 failed（不静默、不卡死），夹具已清理。
---

## 四、记忆库检索与 ACL 测试结果（交付物 2）

### 4.1 检索能力（FTS5 trigram + 兜底）

- `memory_fts` 使用 **FTS5 `tokenize='trigram'`**（中文按 3 字符滑窗切分）；trigram 对 **2 字中文**（如「数值」以外的「复核」「重启」）不可用 → 实现里做了 **FTS 命中 + LIKE 兜底** 的混合检索并去重：
  - 3 字以上：「数值表」类查询走 FTS；
  - 2 字：「复核」「重启」等由 LIKE 兜底命中（实测 `q=复核` 命中 team/restricted 记忆，`q=重启` 命中《任务结论：重启自愈自检》）；
  - 排序：FTS 命中优先，其后按 `created_at` 倒序，`limit` 生效。
- 实测样本：`GET /api/memories?q=数值` → 命中 3 条（含《数值表V2 定稿说明》）。

### 4.2 HTTP 侧 ACL 实测（`/root/mcpclient/acl-http.sh` + `acl-http-part2.sh`）—— 29 项全过

样本：admin 建 `P(private)` / `T(team)` / `R(restricted→allow_members=[zhang])`；用 admin / zhang / li 三种身份（Bearer = 同源 JWT）交叉验证：

| 组 | 检查项 | 结果 |
|---|---|---|
| 单条读取 | admin 读 P=200；zhang 读 P=**403**；zhang 读 R=**200**；li 读 R=**403**；zhang 读 T=200 | 5/5 ✅ |
| 列表可见集合 | zhang 列表含 T、含 R、**不含 P**；li 列表含 T、**不含 R**；admin 列表三者全含 | 6/6 ✅ |
| 编辑/删除权 | zhang 改/删 admin 的 T=**403**；li 改 admin 的 T=403；admin 改自己的 T=200 | 4/4 ✅ |
| 检索不泄露 | zhang/li 的 `suggest` 与 `search`（q=复核）命中 T/R 但 **0 条 P**；admin 能搜到 P | 6/6 ✅ |
| 未登录 | 无 token 列记忆/建记忆 = **401** | 2/2 ✅ |
| 造样本与清理 | 3 条样本创建 + 删除均 200，残留 0 条 | 6/6 ✅ |

### 4.3 发现的一个"假失败"（记录在案）

首轮 25 项中有 3 项 FAIL（`q=复核` 检索为空）。诊断结论：**是测试脚本自身的问题，不是服务缺陷** —— `curl` 直传原始 UTF-8 中文不会被 percent-encode，Node HTTP 解析器直接返回 **400**（原始 UTF-8 直传实测状态码 400）。改用 `%E5%A4%8D%E6%A0%B8` 后 7/7 全过。**浏览器与前端代码均走 `encodeURIComponent`，不受影响**（前端 `MemoryView.vue` 用 `URLSearchParams` 编码）。

---

## 五、MCP 网关测试结果（交付物 3）

外部 MCP 客户端：`/root/mcpclient/acceptance.mjs`（Streamable HTTP，`POST /mcp`，协议 `2025-06-18`，Bearer = `/api` 同源 JWT，令牌由 `/root/mcpclient/mint.cjs` 用服务端 `JWT_SECRET` 短期签发、**不落盘**）。
**最近一次运行（重启后复跑）：17 PASS / 0 FAIL。**

| 组 | 检查项 | 结果 |
|---|---|---|
| 握手 | `initialize` → `protocolVersion 2025-06-18`，`tools/list` 返回 5 工具 | ✅ |
| 工具存在 | `kanban_list` / `file_search` / `memory_search` / `memory_add` / `task_create` 全在列 | 5/5 ✅ |
| 实际调用 | `kanban_list` 返回数据；`file_search` 命中 `ref1.md`；`memory_search` 检索「数值」命中 3 条（含《数值表V2 定稿说明》）；`memory_add` 返回 `id`；`task_create` 返回 `{id, status:"queued"}` 且随后可在工作台查到并被真实执行 | 5/5 ✅ |
| ACL（同词不同 token） | admin 能搜到自己的 private `ADMIN-9131`，zhang **搜不到**；zhang 能搜到自己的 private `ZHANG-9132`，admin **搜不到**（管理员非作者亦不可见）；`team` 双方均可见 | 5/5 ✅ |
| 未授权 | 无 token 连接被拒：`{"error":"未登录"}` | ✅ |

补充：`task_create` 经 MCP 创建的任务在 `GET /api/tasks` 可见、参与真实执行与状态机流转（本轮 MCP 建的任务因描述为占位文本，被 Agent 判为「无法完成」并给出原因 → 恰好也验证了失败兜底路径与 D36 强制人审标记 `需审`）。
---

## 六、前端清单（交付物 4）

### 6.1 已完成（1387 行，`npm run build` 通过：vue-tsc 0 error）

| 文件 | 行 | 内容 |
|---|---|---|
| `views/LoginView.vue` | 56 | 登录 / 注册（阶段 1 已有，本阶段沿用） |
| `layouts/MainLayout.vue` | 63 | 三栏骨架：顶栏 7 Tab、左栏挂 `SideBar`、主区 `router-view`、移动端抽屉 + 底部 Tab（D8 骨架） |
| `components/SideBar.vue` | 123 | **左栏真实数据**：会话区（未读红点、最后一条消息摘要、点击切换、8s 轮询未读）+ Agent 区（运行状态点 / 端口 / 「休眠中（首次使用自动唤醒）」）+ 新建会话（选成员 → dm/group） |
| `components/ChatStream.vue` | 145 | 聊天流：消息气泡、`@` 选择器（正则 `@([^\s@]*)$`）、📎 文件上传（FormData field=`file`）、撤回按钮（本人 + 5 分钟内）、自动滚底、懒启动「正在唤醒」脉冲提示 |
| `views/ChatView.vue` | 132 | 双模式：会话流（增量拉取 + 乐观气泡）与 **Agent 直聊（SSE `chatStream`，onStatus/onDelta/onError/onDone）**；4s tick 拉未读与增量 |
| `views/TasksView.vue` | 313 | **任务 Tab 完整功能**：发起表单（标题/描述/Agent/@引用资料库文件/@引用记忆搜索勾选/需人审勾选/产物记忆可见性）、状态徽标（queued/running/**待审批**/done/failed）、`queue_ahead`「前面还有 N 人」、**waiting_approval 审批区（批准/修改后重跑/驳回 + 必填意见）**、修正记录、产物 **预览/下载/分享**、取消任务 |
| `views/MemoryView.vue` | 207 | **记忆 Tab 完整功能**：关键词搜索 + 类型/可见性筛选、卡片列表（类型 + **ACL 徽标**：仅自己/团队可见/指定成员 + 可见成员名单 + 标签 + 来源任务）、新建/编辑/删除（仅作者或管理员可见按钮）、restricted 需选成员（服务端同样校验） |
| `stores/chat.ts` | 138 | 会话/消息/Agent 状态、`openAgent` 直聊模式、增量 `pull(since=maxSeq)`、乐观发送 + 服务端权威合并、IndexedDB 落盘 |
| `stores/auth.ts` | 28 | 登录态（阶段 1 已有） |
| `lib/idb.ts` | 52 | IndexedDB（`cloudloom/conv`）历史持久化，失败静默降级不影响主流程 |
| `api.ts` | 73 | `api()` + **`chatStream()` SSE 解析**（按 `\n\n` 切帧，兼容 `event: status/error` 与 OpenAI `data:` 帧、`[DONE]`、AbortError） |
| `router.ts` | 31 | `chat→ChatView`、`tasks→TasksView`、`memory→MemoryView` 已指向真实视图；kanban/profiles/library/settings 仍为占位 |

构建产物：`dist/` 由 3000 端口提供（`GET /` 200，`/assets/TasksView-*.js` 200）；`index.js` 对 `STATIC_DIR` 只做一次 `existsSync`，替换 dist 后**静态内容即刻生效、无需重启**（本阶段实测）。

### 6.2 与后端接口对齐核对（逐条比对源码，无发明接口）

`/api/conversations`、`/conversations/:id/messages?since=`、`/conversations/:id/read`、`/conversations/:id/messages`（@Agent 触发）、`/messages/:id/recall`、`/agents`、`/poll?since=`、`/files`（上传 field=`file`）、`/links`（`{name,url,category}`）、`/members`、`/tasks`（6 个）、`/memories`（5 个）、`/me`、`/logout` —— 前端只调用上述已存在路由。

### 6.3 未完成 / 未做（明确清单，转阶段 3）

1. **真实浏览器交互验收**（登录→发任务→审批→记忆检索的点击级验证）：服务器**无任何浏览器二进制**（已实测 `chromium/google-chrome/firefox` 均不存在），本阶段只做到「构建通过 + 组件与接口逐条对齐」。**列为阶段 3 第 1 项**。
2. 看板 / 画像 / 资料库 / 设置 / Agent 工坊 5 个 Tab 页面（占位路由）。
3. 移动端 <768px 的完整适配（抽屉与底部 Tab 骨架已在，交互细节未打磨，D8 阶段 3 完成）。
4. PWA（manifest / service worker）与 `/api/poll` 3-5s 通知推送。
5. 聊天流的「产物卡片」内嵌渲染（目前产物在任务 Tab 查看，聊天流仅文本）。
6. 山河云台主题（二期，不做）。
---

## 七、缺陷与修复记录（含 diff 说明）

> 铁律：不改动阶段 1 已验收的后端代码；如需微调必须记录 diff 并说明原因。本阶段对阶段 1 文件的**唯一**改动是 `server/src/index.js`（仅新增行），`mcp.js` 为阶段 1 留位处填充（4 行描述文案 + 3 个 `registerImpl`）。

### 7.1 `server/src/index.js`（阶段 1 已验收文件，diff vs `_backup-20260913`）

```diff
@@ -24,6 +24,13 @@
 if (fs.existsSync(path.join(__dirname, 'tasks.js'))) app.use('/api', require('./tasks').router);
 if (fs.existsSync(path.join(__dirname, 'memories.js'))) app.use('/api', require('./memories').router);
+// 任务执行器由服务进程独占启动：单纯 require tasks.js 不会启动执行器或改动任务状态（D23 队列单飞）
+// 启动自愈：boot 恢复上一进程遗留的 running（30s 宽限）+ 60s 周期巡检；仍由服务进程独占，require 本身无副作用
+if (fs.existsSync(path.join(__dirname, 'tasks.js'))) {
+  const tasks = require('./tasks');
+  tasks.recoverStale({ boot: true });
+  tasks.startSweeper();
+}
 app.use('/mcp', require('./mcp').router);
```

**原因**：① 阶段 2 需要在服务进程内启动任务执行器；② 修复「执行中被重启的任务永久卡在 running」缺陷（§3.8）。**未改动任何既有行**，只在既有挂载块后新增；`require('./tasks')` 本身无副作用（已实测：外部进程 require 后不会改动任何任务状态）。

### 7.2 本阶段新增/修改文件中的缺陷修复

| # | 缺陷（现象） | 根因 | 修复 | 回归验证 |
|---|---|---|---|---|
| 1 | D36-① 把「所以我不写「无法完成」」误判为无法完成 → 任务被错误置 failed 且原因乱码 | 关键词启发式被 Agent 自我否定句命中 | 改为**强制机器可解析标记**【交付状态】+ **取最后一次出现**（marker-first）+ 否定词护栏（不写/不会/不属于/而非…） | 11/11 单元用例通过（含该真实事故文本作回归样本） |
| 2 | 仅 `require('./tasks')` 就重置了正在执行的任务并起第二个执行器（双跑竞态） | 模块加载期副作用 | 移除加载期调用；改为服务进程显式调用 + `AND status='running'` 条件更新 + 按 `started_at` 计龄 | 诊断性 require 后核对：任务仍为 running、日志 0 条「中断恢复」 |
| 3 | 失败任务的 `result_summary` 为空，Agent 原文丢失（审计缺口） | `finishFailed` 未落库回复 | 增加 `summary` 参数落库 | 失败任务详情可取回完整原文 |
| 4 | Agent 调用超时抛英文 `This operation was aborted` | 无超时与文案 | `TASK_TIMEOUT_MS`（默认 600000）+ 中文提示「已中止，可重试」 | 超时任务置 failed 且报错可读 |
| 5 | 沉淀记忆的 tags 丢掉产物扩展名 | 跨库查询 `outputs`（tasks.db）用的是 team-memory.db 连接，抛错被吞 | 由 tasks.js 传入 `outputFiles`，不再跨库查 | tags 实测含 `md` |
| 6 | MCP `memory_add` 崩溃 `m.tags.split is not a function` | `insertMemory` 已返回 `publicMemory`（tags 为数组），实现里二次映射 | 直接返回 `insertMemory` 结果 | acceptance 17/17 |
| 7 | 无害任务被强制人审（「客户端」命中【金额】规则里的「客户」） | 子串误匹配 | `WORD_EXCEPTIONS = {客户:['客户端']}` + 逐次出现位置判定 `hitWord` | 6/6 用例通过 |
| 8 | `queue_ahead` 恒为 0（有任务在跑时） | 只统计了 `queued AND created_at <` | 改为 `running OR (queued AND rowid < mine)` | 「前面还有 1 人」实测出现 |
| 9 | **执行中被重启任务永久卡 running**（实测卡 3m22s） | 仅启动时按「超时+5 分钟」回收，且无周期巡检 | 启动 `recoverStale({boot:true})`（30s 宽限）+ 新增 `recoverOrphans()` 与 `startSweeper()`（60s） | 孤儿夹具 29s 内被重排；真实硬重启后自动跑完全流程（§3.7） |

修复后 `tasks.js` 净增约 23 行（不含文件本身为阶段 2 新增），`memories.js` / `mcp.js` 为阶段 2 新增或留位填充。

---

## 八、给阶段 3 的注意事项（交付物 5）

### 8.1 路由与组件约定（必须沿用，勿新建平行体系）

- 路由集中在 `src/router.ts`，子路由挂在 `layouts/MainLayout.vue` 下；**新增 Tab 只需替换 `PlaceholderView.vue` 为真实视图**，无需改动布局。
- 布局与状态：`stores/auth.ts`（登录态）、`stores/chat.ts`（会话/消息/Agent，含 `mode: 'conv' | 'agent'`）；**新增数据请在对应 store 里加 action，不要在组件里裸写 fetch**。
- 统一请求入口 `api.ts`：`api<T>(path, init)`（自带 `credentials: same-origin`、JSON 解析、错误抛 `Error(message)`）；**SSE 用 `chatStream()`**，不要另写 EventSource（服务端是 POST + `text/event-stream`，EventSource 不支持 POST）。
- 左栏是独立组件 `components/SideBar.vue`，桌面 aside 与移动抽屉**复用同一个组件**（`@picked` 事件用来关抽屉）。
- ID 用后端返回的 uuid 字符串；时间统一 `created_at/updated_at`（ISO 8601 字符串，前端 `replace('T',' ').slice(...)` 显示）。

### 8.2 API 约定与坑

- **中文查询参数必须 `encodeURIComponent` / `URLSearchParams`**：原始 UTF-8 直传会被 Node 直接 400（§4.3）。
- 记忆检索：3 字以上走 FTS5 trigram，2 字走 LIKE 兜底；`/api/memories/suggest` **必须注册在 `/api/memories/:id` 之前**（已如此，新增路由别破坏顺序）。
- 上传 multer 字段名固定 **`file`**；分享 = `POST /api/links {name,url,category}`（登记为 `kind:"link"` 的资料库条目）。
- 任务详情 `GET /api/tasks/:id` 才带 `outputs/corrections/meta`；列表接口不带。
- `waiting_approval` 是可操作态：审批需 `note` 必填；`modify` 会把 note 写入 `task_corrections` 并在下一轮注入【相关修正记录】。
- 服务端 `detectSensitive` 会对**任务描述 + 引用记忆/资料内容**三重判定 D36，前端表单里的「需要人工审批」只是显式勾选，不勾也可能被强制。
- 日志与静态服务：`index.js` 启动时只判定一次 `STATIC_DIR` 是否存在 → **首次构建 dist 后需重启团队服务**；之后替换 dist 内容**无需重启**（实测）。

### 8.3 MCP 与外部集成（阶段 3 收尾项）

- MCP 端点 `POST /mcp`（Streamable HTTP，协议 `2025-06-18`），Bearer 复用 `/api` 的 JWT。
- ⚠️ **当前验收用的 JWT 是 `expiresIn: 7d` 的短期令牌**；若要用 `hermes mcp add` 长期挂接，**必须改用长期凭据**（专用 API key 或长有效期 token），不要把 7 天令牌写进 Agent 配置。
- 验收脚本可直接复用：`/root/mcpclient/acceptance.mjs <adminJWT> <zhangJWT>`、`mint.cjs <username>`（用服务端 `JWT_SECRET` 签短期令牌，仅测试用，勿落盘）。

### 8.4 服务与运维现状

- 服务：`team-console.service`（8787 API + /mcp、3000 静态）、`caddy.service`（80/443，均为 `enabled`）；Agent 网关 8642-8645 仅 `127.0.0.1`。
- 懒启动：自定义 Agent 8650-8999，首次使用唤醒（60s 超时），空闲 30 分钟自动停（5 分钟巡检）。
- 日志：`journalctl -u team-console`（任务/记忆/巡检关键事件都有中文日志前缀 `[tasks]`、`[lazystart]`）。

### 8.5 待清理与建议（见 §九）

- `~/team-files/产出/` 下已有 14 个真实产物（阶段 3 可作为 UI 展示数据，勿误删）。
- `data/*.db-wal` 已增长到 ~857KB（tasks）/424KB（conversations）：功能无影响，**部署前建议做一次 WAL checkpoint**（`PRAGMA wal_checkpoint(TRUNCATE)`）以缩小体积。
- 测试残留：profile `testbot`（阶段 1 懒启动停机测试留下的空壳，无进程、无端口、无 registry 条目）；验收期测试数据（`私密标记*` / `公开标记*` / `MCP写入-*` / `MCP 创建的任务-*`）。**均建议在阶段 3 部署收尾时统一清理**，本阶段保留作为证据，未擅自删除。
---

## 九、遗留问题与待决策事项

### 9.1 遗留问题（本阶段未闭环，均有明确下一步）

| # | 问题 | 影响 | 下一步 |
|---|---|---|---|
| L1 | 第 8 项验收缺少**真实浏览器交互**证据（服务器无浏览器） | 门禁 G2 的唯一软项 | 阶段 3 第 1 项：用真实客户端跑登录→发任务→审批→记忆检索，建议在阶段 3 部署后用 `https` 或本机端口转发 + 本机浏览器验证 |
| L2 | 命名空间里仍有 5 个 Tab 是占位页 | 用户可见 | 阶段 3 范围（看板/画像/资料库/设置/Agent 工坊） |
| L3 | PWA / 通知推送未做 | 移动端体验 | 阶段 3（D8） |
| L4 | MCP 长期凭据未配置（现用 7 天 JWT） | 外部挂接会过期 | 阶段 3 MCP 收尾（§8.3） |
| L5 | `data/*.db-wal` 偏大（857KB / 424KB） | 无功能影响 | 部署前 checkpoint |
| L6 | 测试残留（`testbot` profile、验收标记记忆与任务） | 观感 / 数据洁净 | 阶段 3 部署收尾统一清理（**需确认**） |
| L7 | D36 的 3 类关键词表是硬编码在 `tasks.js` 的常量 | 后续调整需改代码 | 可考虑移入配置（非 SPEC 要求，暂不做） |

### 9.2 待决策（需用户确认）

1. **是否清理测试残留数据**（L6）：包括 `testbot` profile 目录、`私密标记*/公开标记*/MCP写入-*/MCP 创建的任务-*` 等验收痕迹、以及 8 条 failed 的测试任务记录。默认建议：**保留 failed 任务与沉淀记忆（审计价值），清理纯标记类记忆与 `testbot` profile**。
2. **Agent 产物目录规范**：当前产物落 `~/team-files/产出/<task_id>/`（SPEC 要求）。验收中发现 Agent 会把「同名草案」写成 `_v2` 以避免覆盖（行为正确，但目录里会累积多版本）。是否需要在阶段 3 加「产物版本」UI 分组？
3. **D36 关键词表**是否需要与业务方对齐后扩充（当前 3 类：金额 / 对外承诺 / 删除数据）。

---

## 十、复现清单（阶段 3 与后续审计可直接照跑）

```bash
# 1) 服务与端口
systemctl is-active team-console caddy          # active / active
ss -ltn | grep -E ':(8787|3000|8642|8643|8644|8645)\b'

# 2) 任务闭环（Bearer 用 mint.cjs 现场签发，不落盘）
cd /opt/team-console/server && export NODE_PATH=$PWD/node_modules
A=$(node /root/mcpclient/mint.cjs admin)
curl -s -H "Authorization: Bearer $A" "http://127.0.0.1:8787/api/tasks?limit=5" | head -c 400

# 3) 记忆 ACL（29 项）
bash /root/mcpclient/acl-http.sh            # 22 项（读/列/改/删/未授权）
bash /root/mcpclient/acl-http-part2.sh      # 7 项（percent-encoded 中文检索）

# 4) MCP 5 工具 + ACL（17 项）
cd /root/mcpclient && node acceptance.mjs "$A" "$(node mint.cjs zhang)"

# 5) 自愈
journalctl -u team-console | grep -E '中断恢复|孤儿任务自动重排'
```

### 数据快照（报告落笔时）

| 库 | 表 | 行数 |
|---|---|---|
| tasks.db | tasks | 16（done 8 / failed 8） |
| tasks.db | task_corrections | 3（modify / approve / reject 各 1） |
| tasks.db | outputs | 14 |
| team-memory.db | memories | 17（team 13 / private 3 / restricted 1） |

---

**阶段 2 门禁判定：通过（G2 ✅）** —— 10 项验收 9 项实测全过 + 第 8 项完成到「构建 + 接口对齐」层面并已列为阶段 3 首项；交付物 1-5 全部写入本报告。缺陷 9 项均修复并回归，无静默跳过项。
