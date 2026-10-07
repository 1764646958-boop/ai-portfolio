# Session 3.1 · 微修复包（C-1 / C-2 / C-13 / C-14）—— Claude Code 执行稿（合并版）

> **运行方式**：本机 Claude Code（同 S1-S3 模式）：`cd D:\learn\saishi\chcz\CloudLoom` → `claude` → 粘贴下面的【提示词】全文。
> **前置**：S1-S3 已交付并通过独立复核（`reports/Session3-部署报告.md` 第九节 + `reports/Session1-3-独立复核记录.md`）。
> **目标**：把 4 个高价值遗留打成一个**最小改动**修复包，在成员正式启用（S4 后）前完成。
> **铁律**：加法式/最小改动 + 备份 + diff + 回归 + 报告；不重写、不扩散。

## 【提示词】（粘贴全文）

```text
【任务：CloudLoom 微修复包 S3.1 —— 修复 4 个遗留问题】

你是执行代理（Claude Code，本机运行）。通过 SSH 远程操作服务器（root@<服务器IP>，免密已配）完成修复。项目根：/opt/team-console。

先读：reports/Session3-部署报告.md 第九节（C-1/C-2/C-13/C-14 条目）与第 7 节相关 diff 记录，理解现有工程纪律后再动手。

### 修复 1（C-1 · 高）：恢复逻辑时机
- 位置：server/src/index.js —— 当前 `tasks.recoverStale({ boot: true })` 与 `tasks.startSweeper()` 在 `app.listen` 之前执行（约 L33-34；API listen 约 L47，静态 listen 约 L58）。
- 问题：第二个实例启动瞬间会把所有 running 任务误判为孤儿重排。
- 修复：把恢复/扫描启动移到 **listen 回调之后**（服务器就绪后执行一次）；保持单实例行为不变，不改变 recoverStale/sweeper 自身逻辑。

### 修复 2（C-2 · 高）：端口分配探测
- 位置：server/src/registry.js `allocatePort()`（约 L52；调用方 server/src/agents.js:61）。
- 问题：只查 agents.json 查重，不做真实占用探测 → 可能分配到已被占用的端口，首次唤醒必失败。
- 修复：候选端口先做**实际绑定探测**（临时 bind/listen 后释放，或等效 ss 检测），被占用则继续下一候选；保留 agents.json 查重；全部失败时给出明确错误。
- 验收：构造"占用一个候选端口"的场景，证明新建 Agent 会跳过它并成功分配到可用端口。

### 修复 3（C-14 · 潜在）：lastActive 回写
- 位置：server/src/chat.js（约 L59-66：`if (!(await lazy.isRunning(agentId))) { …ensureRunning… }`）。
- 问题：已在运行的实例不回写 lastActive；重启竞态下可能被扫描误停。
- 修复：`isRunning` 命中（运行中）时补一次 `touch(id)` 回写（一行级；如 lazy 未导出 touch 则补最小实现）。
- 验收：证明运行中会话会刷新 lastActive；懒启动 30min 停止逻辑回归不受影响。

### 修复 4（C-13 · 可用性）：聊天默认会话
- 位置：team-console/src/views/ChatView.vue onMounted（约 L90-91：`else if (!chat.activeConv && chat.convs.length) await chat.open(chat.convs[0].id)`）。
- 问题：每次挂载自动打开"最近更新"会话，顺序随他人发言漂移 → 易把消息误发到群聊。
- 修复：记住**用户上次打开的会话**（localStorage 存 conversation id；无记录或已无权时回退现有逻辑）；进入会话后滚动到底部、显著高亮当前会话。
- 验收：刷新后回到上次会话；误发群聊路径消除；`vue-tsc -b && vite build` 通过。

### 工程要求（沿用既有纪律）
1. 改动前备份到 /root/e2e/backups/（.bak-s31-* 后缀）；每项记录 diff 摘要。
2. 不触碰其他模块；不重跑 hermes gateway install；不卸载 tirith；密钥只进 .env / agents.json（600）且不入 git。
3. 后端改动后 `systemctl restart team-console`；前端 `vue-tsc -b && vite build`（dist/ 由 Caddy 托管）。
4. 回归：复跑 e2e3.mjs（应 42 PASS / 0 FAIL）+ 每项最小验证证据（命令 + 原始输出）。
5. 产出：`reports/Session3.1-微修复报告.md`（每项：问题 / 改动 / diff 摘要 / 验证证据 / 剩余风险），并 scp 回本机 D:\learn\saishi\chcz\CloudLoom\reports\ 留档。
6. 结束汇总：4 项修复结果 + 回归结果 + 剩余风险。

完成后由助手做独立复核（同 S0/S3 标准）。
```

## 附
- 只想单点修复时用分项版：`Session3.1-微修复包-分项版.md`
