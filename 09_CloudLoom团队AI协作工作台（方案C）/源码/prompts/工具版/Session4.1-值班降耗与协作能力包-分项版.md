# Session 4.1 · 值班降耗与协作能力包 —— 分项版（C1–C6 逐批粘贴）

> **用法**：每次只跑一批，把该批代码块全文粘进 Claude（`cd D:\learn\saishi\chcz\CloudLoom` → `claude`）。
> **建议顺序**：**C1 单独先跑**（直接省 token 钱）→ C2 → C4 → C3 → C5 → **C6（收口，源自 S4.0 复核）**。
> 完整版（一次跑全部）：`Session4.1-值班降耗与协作能力包-合并版.md`

---

## C1（核心）定时作业降耗重构 —— 15 次/周 → 1 次/周 + 0-token 快照（周报周一 09:00 · 画像按需 · AI 版）

```text
【任务：CloudLoom S4.1-C1 定时作业降耗】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

现状：/root/.hermes/profiles/zhiban/cron/jobs.json 三个作业——晨报 44cf46376cff `0 9 * * *`（7 次/周）、
周复盘 ec6e303a9e33 `0 10 * * 1`（1 次/周）、画像 <实读id> `0 6 * * *`（7 次/周）= 15 次 LLM 作业/周；
负责人自费 DeepSeek 余额，要求降耗。

要求：
1. 新增"0-token 数据快照"（脚本，不调 LLM）：/opt/team-console/ops/digest.py 读 kanban.db / tasks.db /
   conversations.db（team-memory.db 视需要）生成 markdown——进行中与阻塞任务、待拍板、未读会话数、
   当周新增记忆与任务数、**当前 DeepSeek 余额** → 写 /root/team-files/系统通知/快照-<YYYYMMDD>.md；
   用 Hermes cron 的 no_agent=true + script（或 systemd timer）每日 1 次；此路径 0 token。
2. LLM 作业改周报制（**参数已由负责人确认，勿自行调整**）：晨报（每日）→ **周报 `0 9 * * 1`（每周一 09:00）**〔A1〕，
   提示词改为【上周完成/阻塞/风险/本周计划/待拍板 + 花费估算】，**保留 AI 版**〔C1：要判断与建议，不做纯脚本版〕；
   周复盘（`0 10 * * 1`）并入周报（删独立作业，避免同日跑两次）；画像（`0 6 * * *`）→ **取消定时、改为按需**〔B3〕，
   需要时跑 run-job.sh profile 生成。合计 LLM 作业 15 次/周 → **1 次/周（-93%）**。
3. 按需触发入口：/opt/team-console/ops/run-job.sh <weekly|profile|digest>；用法写进《成员接入手册》与 HERMES.md。
4. 实测给数字：手动触发一次周报 → 用 C2 的 usage 记录**本次 tokens 与估算花费**，写进报告（"一次周报≈¥X"）。
5. 画像按需路径独立可用：run-job.sh profile 一条命令生成画像 JSON 且 /api/profiles 正确读取；
   可选在设置页加「立即生成画像」按钮。**决策变更留痕**：docs 记一条（D15 晨报每日→周报每周一；
   D21 画像每日 cron→按需触发）+ 同步 SPEC 变更记录，避免后人按旧规格复现。
6. 验收：①快照跑通且无任何 LLM 调用（无 usage 记录）②jobs.json before/after 对照表（周报 `0 9 * * 1` /
   复盘已并入 / 画像已停且**无 next_run**）③手动触发周报成功（文件 + 邮件 + usage 有记录）
   ④run-job.sh 三参数均通（**画像按需单独验证**）⑤next_run / systemctl list-timers 正常。

纪律：改前备份（jobs.json 等）；diff 留档；密钥不回显；最小改动；报告落 reports/Session4.1-降耗与能力报告.md（C1 段）并 scp 回本机。
```

---

## C2（核心）用量记账与成本可见

```text
【任务：CloudLoom S4.1-C2 用量记账与成本可见】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

现状：全项目没有任何 token/花费记账（源码 grep usage|cost 无命中）→ 花钱不可见，是"烧 token"问题根因之一。

要求：
1. server/src/chat.js 两条返回路径（非流式 ~L29、SSE 流式）采集上游 usage（prompt_tokens/completion_tokens）；
   流式若缺 usage，用 stream_options 或在报告中说明改用何种估算方式。
2. 新表 usage_log：ts / actor(成员id) / agent_id / model / prompt_tokens / completion_tokens / est_cost
   （单价常量放 server/src/config.js，可配）；任务中心（tasks.js 触发 Agent 的路径）同样落账。
3. 周报与快照中体现：**本周花费估算 + 按 Agent/成员分布 Top5**。
4. 余额阈值告警：并入 S4.0-B1 看门狗（若 B1 未装则就地实现同等检查）。
5. 验收：一次真实对话后 usage_log 有新行且数值与上游 usage 一致；周报/快照含花费段落；
   给出"4 个预设 Agent 各一次对话的 tokens 对照表"。

纪律：备份 / diff / 不回显密钥 / 报告落 Session4.1 报告（C2 段）并 scp 回本机。
```

---

## C3 上下文瘦身（长会话省钱）

```text
【任务：CloudLoom S4.1-C3 上下文瘦身】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

现状：SPEC M1 —— API Server 无状态，每轮请求带完整历史 → 长会话成本近似平方增长。

要求：
1. server/src/chat.js 发往网关前加**上下文窗口策略**（默认开、参数可配）：默认保留最近 N 轮（建议 N=12，
   C.CHAT_HISTORY_MAX_ROUNDS）+ 一条「更早对话已省略」说明；可选 env 开关（默认关）走"摘要 + 最近 N 轮"
   （摘要缓存按 conversation+agent 存库）。
2. **不得破坏**任务上下文注入、D35 修正记录注入、@Agent 片段注入——必须保留在窗口内。
3. 验收：30 轮会话 → 请求体 tokens 明显下降（给前后数字）；关键追问行为有证据；e2e3 回归 42 PASS / 0 FAIL。
4. 策略写进 SPEC v3.3（衔接 S4.0-B7）与《故障排查表》。

纪律：备份 / diff / 报告落 Session4.1 报告（C3 段）并 scp 回本机。
```

---

## C4 三项能力端到端实测与修补

```text
【任务：CloudLoom S4.1-C4 协作能力实测与修补】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

背景（代码已核）：① POST /api/agents 需 admin（agents.js:51）——会 profile create --clone-from cehua + 写 .env(600)
 + SOUL.md + gateway install --system --no-start-now + 共享看板 drop-in；POST /api/register 开放注册、需 admin 批准（auth.js:44/105）
 ② 私聊/群聊（conversations.js:60；dm 去重 / group≥2 人）+ 成员互聊**不调 LLM** + @Agent 异步拉入（L113-136）
 ③ POST /api/chat 仅 authRequired（chat.js:38）→ 任意登录成员可唤起任意 enabled Agent

要求：逐条端到端实测，失败即修：
1. 新建 Agent 全流程：创建 → GET /api/agents 出现 → 懒启动唤醒 → 真实对话 200 → **删除** → 端口回收 + profile/unit 清理；
   每步给证据（含耗时）
2. 注册-批准：新账号注册 → pending → 管理员界面「设置→成员管理」批准 → 登录成功 → 停用后 401
3. 协作：建 3 人私聊 + 3 人群聊 → 发消息（确认**不产生 usage_log 记录**＝不烧 token）→ 群聊 @<agent> 拉起 Agent 作答
   → 非成员访问 403 → 未读游标正常
4. 任意成员唤起任意 Agent：用**普通成员** token 分别调 4 个预设 Agent 各一次 → 全 200 且 usage 入账
5. 文档：《成员接入手册》补"三种协作方式 + @Agent 用法 + 谁能用哪个 Agent + 新建 Agent 步骤"；限制如实写明
6. 验收：每步命令 + 原始输出入报告；发现的缺陷全部修复或明确标注未修原因

纪律：删除类操作逐条细看；改前备份；报告落 Session4.1 报告（C4 段）并 scp 回本机。
```

---

## C5（可选，仅出方案不改代码）Agent 权限粒度

```text
【任务：CloudLoom S4.1-C5 Agent 权限粒度方案（只出方案，不改代码）】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

现状：Agent 只有 enabled 全开/全关，没有"某成员只能用某 Agent"的粒度。

要求：在报告中给出方案对比（**不要实现**）：① 维持现状 ② agents.json 加 allowed_members 字段 + 前端过滤
（工作量、风险、对现有 e2e 脚本的影响）；写明推荐建议与触发条件（例如"团队扩员后才需要"）。
```

---

## C6（追加，源自 S4.0 独立复核）收口：夹具修复 + 7 项决策默认实现 + 遗留收口

```text
【任务：CloudLoom S4.1-C6 收口（源自 S4.0 独立复核）】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

背景：S4.0 八批已交付并经助手独立复核通过（终态零残留；B1 看门狗由助手亲手演练：异常→告警文件→工作台
/api/poll 读到→静默复核→痕迹清理）。以下为复核后确认的收口项，**默认决策如下；若负责人另有指示以其为准**。

1. e2e3 夹具修复（现 41 PASS / 1 FAIL）：FAIL 是 main.innerText().length > 200 在"任务表已清空"时必然不成立
   （夹具假设；e2e3.mjs mtime 00:43 早于 S4.0，未被改）。二选一：①断言改为"容器存在 + 结构完整"；
   ②用例内先 seed 一条测试数据再断言（用后清理）。验收：终态下 e2e3 = 42 PASS / 0 FAIL；
   ⚠️ 跑完必须复原终态并复核（users=1、其余计数=0），不留测试残留。
2. 画像产物命名/结构稳定：① 作业 prompt 写死文件名；② profiles.js 改取目录内 mtime 最新（非字典序最大）。
   验收：跑一次画像作业，命名合规且 /api/profiles 正确读取。
3. 周报发邮件：在 C1 的周报 prompt 加"同时发邮件给负责人（复用现有 SMTP，纯出站）"。验收：手动触发 → 邮件到达。
4. 看门狗站外通道：ops-check 有新告警时同时发邮件（无告警不发）。验收：OPS_BALANCE_THRESHOLD=9999 制造告警 →
   邮件到达 → 还原并清理（删 /root/team-files/系统通知/运维告警-*.md 与 /opt/team-console/ops/.ops-check-state.json）。
5. JWT 登出吊销 → token_version 方案：users 表加 token_version（默认 1），JWT 带 tv，登出时 +1 → 该用户旧 Cookie
   立即失效。验收：登录 → 留旧 Cookie → 登出 → 旧 Cookie 调 /api/me 应 401（现为 200）；重登正常；e2e3 通过。
6. Secure 与 http 回退 → 保持 Secure: true，不做 http 回退；《故障排查表》写明"登录必须走 HTTPS"+ 本地隧道做法。
7. 密钥台账制度 → 新增 docs/密钥台账.md（7 处位置 + sha256 前 12 位指纹 + 轮换命令 + 90 天周期 + 负责人）；
   不引入外部密钥托管。
8. B5-① "不覆盖"的字节级兜底 → 产物落盘时写 MANIFEST.json（文件名 + sha256 + 时间）；不做全量字节快照。
   验收：产出后 MANIFEST.json 与文件 sha256 一致。
9. 遗留收口：a) 回滚脚本在 /tmp 隔离副本演练（绝不触碰生产库）并记录结果；b) 画像叙述残留不清理，
   docs 写明"此为 B2 补跑成功证据本体，属审计链，勿删"。

纪律：改前备份；diff 留档；不回显密钥；报告落 Session4.1-降耗与能力报告.md（C6 段）并 scp 回本机。
```

---

## 跑完的交接

把 Claude 汇总发出来 → 助手按 S3/S3.1 标准独立复核（会亲手验证：快照 0-token、用量记账真落库、
新建 Agent 真能跑通并清理干净、普通成员真能唤起全部 Agent）。
