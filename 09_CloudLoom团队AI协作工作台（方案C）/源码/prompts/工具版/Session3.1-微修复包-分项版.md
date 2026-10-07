# Session 3.1 · 微修复包（分项版）—— 4 个独立小提示词

> 用途：只想修其中某一项时，单独粘贴对应提示词给 Claude Code（本机 + SSH 模式）。
> 每项自带工程要求简版；通用约定见合并版。

---

## 1) C-1 · 恢复逻辑时机（server/src/index.js）
```text
【CloudLoom 微修复 · C-1】通过 ssh root@<服务器IP> 操作 /opt/team-console。
修复：server/src/index.js 中 `tasks.recoverStale({ boot: true })` 与 `tasks.startSweeper()` 目前在 app.listen 之前执行（约 L33-34），第二个实例启动瞬间会把 running 任务误判为孤儿。把它们移到 listen 回调之后（就绪后执行一次），保持单实例行为不变、不改 recoverStale/sweeper 自身逻辑。
工程要求：改动前备份到 /root/e2e/backups/（.bak-s31-*）；记录 diff；重启 team-console 并复跑 e2e3.mjs（42 PASS 为基线）；把结果补记入 reports/Session3.1-微修复报告.md。
```

## 2) C-2 · 端口分配探测（server/src/registry.js）
```text
【CloudLoom 微修复 · C-2】通过 ssh root@<服务器IP> 操作 /opt/team-console。
修复：registry.js 的 `allocatePort()`（约 L52，调用方 agents.js:61）只查 agents.json 查重、不探测真实占用。改为候选端口先做实际绑定探测（临时 bind/listen 后释放或等效 ss 检测），被占用则跳过；保留查重；全部失败给明确错误。
验收：构造占用一个候选端口的场景，证明新建 Agent 能自动跳过并分配到可用端口。
工程要求：备份（.bak-s31-*）+ diff + 重启 + e2e3.mjs 回归 + 补记报告。
```

## 3) C-14 · lastActive 回写（server/src/chat.js）
```text
【CloudLoom 微修复 · C-14】通过 ssh root@<服务器IP> 操作 /opt/team-console。
修复：chat.js 约 L59-66，`isRunning()` 命中（实例已在运行）时补一次 `touch(id)` 回写 lastActive（一行级；lazy 无 touch 导出则补最小实现），消除"运行中被扫描误停"的竞态可能。
验收：证明运行中会话刷新 lastActive；懒启动 30min 停止逻辑回归不受影响。
工程要求：备份（.bak-s31-*）+ diff + 重启 + e2e3.mjs 回归 + 补记报告。
```

## 4) C-13 · 聊天默认会话（team-console/src/views/ChatView.vue）
```text
【CloudLoom 微修复 · C-13】通过 ssh root@<服务器IP> 操作 /opt/team-console。
修复：ChatView.vue onMounted（约 L90-91）自动打开 convs[0]（最近更新会话，顺序随他人发言漂移，易误发到群聊）。改为记住用户上次打开的会话（localStorage；无记录/已无权时回退现有逻辑），并滚到底、高亮当前会话。
验收：刷新后回到上次会话；`vue-tsc -b && vite build` 通过；误发群聊路径消除。
工程要求：备份（.bak-s31-*）+ diff + 前端重建 + 相关回归 + 补记报告。
```
