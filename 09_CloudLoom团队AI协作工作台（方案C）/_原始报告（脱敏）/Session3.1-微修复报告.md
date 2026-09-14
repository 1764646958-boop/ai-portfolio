> 📄 **作品集展示副本（已脱敏）**：服务器地址 / 主机名 / 域名 / 邮箱 / 凭据 / 令牌均已替换为占位符；
> 完整原报告不随作品集仓库分发。指标与结论未作任何修改。

# Session 3.1 微修复报告 —— C-1 / C-2 / C-14 / C-13

- **任务**：CloudLoom 微修复包 S3.1（修复 Session 3 复核遗留 4 项）
- **执行**：远程执行代理（Claude Code 本机运行），全程 SSH 操作 `root@<服务器IP>`
- **窗口**：2026-09-14 15:38 ～ 15:52（服务器本地时间，CST）
- **环境**：项目根 `/opt/team-console`；Node v26.8.2；Express 5.2.1；Vue 3 + Vite 8.3.0
- **服务终态**：`team-console.service` = `active`，`MainPID=243726`，`NRestarts=0`

> 与执行稿冲突时以 `SPEC.md` 为准。本报告不含任何明文密钥、JWT 或邮箱地址。

---

## 0. 本次范围与工程纪律

| 纪律项 | 落实方式 | 证据 |
| --- | --- | --- |
| 改动前备份 | 5 个待改文件逐个备份到 `/root/e2e/backups/`，后缀 `.bak-s31-*`（index.js 因分三轮回补，另有 `-s31b/-s31c/-s31d`） | §7 备份清单 |
| 逐项 diff | 每轮回补后立即生成 `diff -u`，共 9 个 diff 文件 | `/root/e2e/s31-diffs/` |
| 不触碰其他模块 | S3.1 期间被修改的源文件恰为 5 个，无第 6 个 | §5.3 `find` 输出 |
| 不重跑 hermes gateway install | 未执行任何 `hermes ... install` | — |
| 不卸载 tirith | 未触碰 tirith | — |
| 密钥纪律 | 未新增/未读取明文密钥；校验用 JWT 仅存在于内存变量（长度 233），未落盘 | §3 证据 1 首行 |
| 本机不落地项目文件 | 本机仅落地本报告 | 本地 `reports/` 目录 |
| 服务重启 | 后端改动后 `systemctl restart team-console`；前端 `vue-tsc -b && vite build`（dist 由 Caddy 托管） | §5.2 |

---

## 1. C-1（高）恢复/巡检启动时机 —— **已修复（含一次实测推翻与返工）**

### 1.1 问题

`server/src/index.js` 在 `app.listen` 之前就执行 `tasks.recoverStale({ boot: true })` 与 `tasks.startSweeper()`，并在模块顶层无条件启动 `lazy.initTable().then(setInterval(lazy.sweep, ...))`。这意味着**任何**在该机器上启动的第二个进程（例如 systemd 重启过程中的重叠、人工误启）都会：

1. 以 30s 宽限期把上一进程仍在 `running` 的任务判为中断 → 重排；
2. 把任务真正**再执行一遍**（同一个任务被两个进程先后跑）；
3. 另起一个 5 分钟空闲清扫定时器，写共享的懒启动实例表。

实测（修复前）第二实例输出——**缺陷可见**：

```
$ cd /opt/team-console/server; timeout 8 node src/index.js
[team-console] API 监听 http://127.0.0.1:8787（含 /mcp）
[tasks] 中断恢复：1 个任务重新排队
[team-console] 前端静态监听 http://127.0.0.1:3000
[tasks] 执行 291a96d3-08e5-4d15-8338-3119b0deeda1 → zhiban（指令 1158 字）
[lazystart] 实例表初始化: cehua:up chengxu:up pingshen:up zhiban:up testbot:down
```

而 `ss -ltnp` 此刻只显示 1 个监听者（systemd 的 238630）——即第二实例根本没在服务，却已经动了共享状态。

### 1.2 关键根因（第一版修复被实测推翻）

第一版按执行稿把恢复/巡检移进 `app.listen` 的回调，并在注释里断言「第二实例绑定必然失败（EADDRINUSE），回调不执行」。**实测推翻了该假设**：第二实例的回调照样触发、恢复照样执行。

判别实验（隔离变量）：

```
$ node -e 'http.createServer().listen(8787,"127.0.0.1",cb)'   # 原生 http
server error 事件: EADDRINUSE                                  # ← 内核确实拒绝重复 bind
$ node -e 'express().listen(8787,"127.0.0.1",cb)'             # 同一 app 路径
listen 回调触发 pid=240844                                     # ← 回调仍被调用，且无 error 事件
```

根因在 Express 5 自身（`node_modules/express/lib/application.js:598-606`）：

```js
app.listen = function listen() {
  var server = http.createServer(this)
  var args = slice.call(arguments)
  if (typeof args[args.length - 1] === 'function') {
    var done = args[args.length - 1] = once(args[args.length - 1])
    server.once('error', done)        // ← 回调被同时注册为 error 监听
  }
  return server.listen.apply(server, args)
}
```

绑定失败时 Express **用错误对象调用用户回调**（因此既不抛异常、也仍然"看起来监听成功"）。原回调签名 `() => {...}` 忽略入参 → 第二实例照样执行恢复。

### 1.3 改动（`server/src/index.js`，3 处）

1. 恢复/巡检 + 懒启动收进就绪闸门函数，由 listen 回调在**确认持有 API 端口后**调用一次：

```js
const tasksMod = fs.existsSync(path.join(__dirname, 'tasks.js')) ? require('./tasks') : null;
function startTaskRuntime() {
  if (!tasksMod) return;
  tasksMod.recoverStale({ boot: true });
  tasksMod.startSweeper();
  startLazyRuntime();          // C-1：实例表初始化与空闲清扫同样只在就绪后启动
}
...
app.listen(C.PORT, C.HOST, (err) => {
  // express 5 会把回调同时注册为 error 监听，端口占用时回调照样被调用、入参是错误对象
  if (err) {
    console.error(`[team-console] API 监听失败（${err.code ? err.code : err.message}）：本进程不启动任务恢复/巡检`);
    return;
  }
  console.log(`[team-console] API 监听 http://${C.HOST}:${C.PORT}（含 /mcp）`);
  startTaskRuntime();          // C-1：确认本进程真正持有 API 端口后再恢复/巡检
});
```

2. 懒启动改为闸门内启动（原为模块顶层无条件启动）：

```js
function startLazyRuntime() {
  lazy.initTable().then(() => setInterval(lazy.sweep, C.SWEEP_INTERVAL_MS));
}
```

3. 静态监听日志同步区分成功/失败，避免日志谎报就绪（未持有端口时不再打印"已监听"）。

> `recoverStale` / `startSweeper` / `sweep` 的内部实现**未做任何修改**，只改调用时机与调用者。

### 1.4 diff 摘要

| diff 文件 | 规模 | 内容 |
| --- | --- | --- |
| `s31-diffs/index.js.diff` | 35 行 | 第一版：恢复/巡检移入回调 + 闸门函数 |
| `s31-diffs/index.js.s31b.diff` | 21 行 | 第二版：回调改为 err 感知（根因修正） |
| `s31-diffs/index.js.s31c.diff` | 20 行 | 懒启动 initTable+sweep 收入闸门 |
| `s31-diffs/index.js.s31d.diff` | 18 行 | 静态监听日志区分成功/失败 |
| `s31-diffs/index.js.cumulative.diff` | 64 行（+36 / −8） | 对 S3 基线（`index.js.bak-s31-20260914-153825`）的累计 diff |

### 1.5 验证证据

**（1）修复后同一实验 —— 第二实例不再动任何共享状态**（`/root/e2e/s31b-second.log`）：

```
[team-console] API 监听失败（EADDRINUSE）：本进程不启动任务恢复/巡检
[team-console] 前端静态监听失败（EADDRINUSE）
```

无 `[tasks] 中断恢复`、无 `[tasks] 执行 …`、无 `[lazystart] 实例表初始化`；进程自行退出（退出码 0，不再靠 `timeout` 杀死）。

**（2）正向对照 —— 端口持有者（主实例）在重启后照常执行被闸门保护的启动逻辑**：

```
$ systemctl restart team-console; journalctl -u team-console -n 7
[team-console] API 监听 http://127.0.0.1:8787（含 /mcp）
[team-console] 前端静态监听 http://127.0.0.1:3000
[tasks] 执行 4d588d40-413a-4c15-b3ea-65a0fd4fe0a4 → zhiban（指令 1158 字）
[lazystart] 实例表初始化: cehua:up chengxu:up pingshen:up zhiban:up testbot:down
```

同一份二进制：持有端口 → 恢复/巡检/实例表初始化全部正常；未持有端口 → 全部跳过。单实例行为不变。

**（3）数据面未被污染**：判别测试期间构造的 `running` 行（`87d1bca2-08e5-…`）在测试后逐字段还原（`status=done`、`started_at=2026-09-14T07:43:54.520Z`、`progress=完成，登记产物 1 个`），整表快照比对无差异。

### 1.6 测试副作用（如实披露）

第一版修复（当时回调未判 err）的实测过程中，第二实例**真的把被构造出来的任务跑了一遍**（`291a96d3` 与随后的 `87d1bca2`，均由重启时的中断恢复投递）。这两行随后按快照还原为 `done`，任务本身是 e2e 产生的 1158 字办公任务，重跑只新增了一条记忆沉淀记录，无数据丢失；`done=240 / failed=9` 均为终态，无残留在途行。

### 1.7 剩余风险

- 闸门以「是否持有 8787」为唯一就绪信号。若 8787 被**无关进程**占用，本进程不会启动恢复/巡检（但它本来也无法对外服务），属可接受降级；日志会明确打印 EADDRINUSE。
- 第二实例现在会自行退出（退出码 0）。这是行为变化，但仅发生在异常启动路径，且严格优于原先的空转。

---

## 2. C-2（高）端口分配探测 —— **已修复**

### 2.1 问题

`server/src/registry.js` 的 `allocatePort()` 只做 agents.json 登记去重，不探测候选端口是否**已被真实占用**。若 8650-8999 中某端口被别的进程监听而未被登记，新建 Agent 会分到已被占用的端口 → 网关启动失败/端口冲突。

### 2.2 改动（`server/src/registry.js`，+25 / −3）

新增同步的 LISTEN 端口扫描（解析 `/proc/net/tcp` 与 `/proc/net/tcp6` 的 `st == 0A` 行），分配时同时排除「已登记」与「正在监听」：

```js
function listeningPorts() {
  const set = new Set();
  for (const f of ['/proc/net/tcp', '/proc/net/tcp6']) {
    let txt = '';
    try { txt = fs.readFileSync(f, 'utf8'); } catch { continue; }
    for (const line of txt.split('\n').slice(1)) {
      const cols = line.trim().split('\t').join(' ').split(/ +/).filter(Boolean);
      if (cols.length < 4 || cols[3] !== '0A') continue;
      const hex = (cols[1] || '').split(':')[1];
      if (hex) set.add(parseInt(hex, 16));
    }
  }
  return set;
}
function allocatePort(reg) {
  const used = new Set(Object.values(reg).map(a => a.port));
  const listening = listeningPorts();
  for (let p = C.CUSTOM_PORT_MIN; p <= C.CUSTOM_PORT_MAX; p++) {
    if (used.has(p) || listening.has(p)) continue;   // 已登记 或 已被占用 → 跳过
    return p;
  }
  throw new Error('端口池耗尽（8650-8999）或全部候选端口均已被占用');
}
```

保持**同步**是有意为之：调用方 `agents.js:61` 在同步的 `updateRegistry(reg => {...})` 变更回调内使用该函数。加锁/异步探测会破坏该调用约定。

### 2.3 diff 摘要

`s31-diffs/registry.js.diff`，37 行（+25 / −3）。

### 2.4 验证证据（`/root/e2e/s31-c2-port.cjs` + `s31-c2-pool.cjs`，真实 registry + 真实监听）

```
已登记 Agent 端口: 8642,8643,8644,8645,8650
① 基线（除登记端口外无占用）: allocatePort = 8651
② 登记去重（伪造一份含 8651 的登记表）: allocatePort = 8652   ← 应跳过已登记的 8651     ✔
③ 真实占用 8651（未登记，用 net 监听）: allocatePort = 8652   ← 应跳过 8651             ✔
④ 再真实占用 8652: allocatePort = 8653   ← 应跳过 8651/8652                            ✔
⑤ 两个监听释放后: allocatePort = 8651   ← 应回到 8651                                  ✔
候选池 8650-8999 共 350 个：本进程新占用 349 个，另有 1 个已被既有进程占用（含 team-console API 8787）
⑥ 全池占满: 显式抛错 ✔ 端口池耗尽（8650-8999）或全部候选端口均已被占用                 ✔
清理本进程监听后基线: allocatePort = 8651                                              ✔
```

③ 即执行稿要求的场景：**占用一个候选端口 → 新分配跳过它、拿到空闲端口**。

### 2.5 剩余风险

- 探测依赖 Linux `/proc`（目标平台固定为 Linux，可接受）。
- 存在 TOCTOU 窗口：探测与网关真实 bind 之间理论上可被抢占。窗口在毫秒级且创建 Agent 是低频人工操作，风险低；若 S4 要求更强保证，可在网关启动失败时回退重试下一个端口。
- 候选池 8650-8999 与 team-console 自身 API 端口 8787 重叠。因为「新建 Agent」必须经由该 API（即 8787 必处于 LISTEN 状态），探测必然跳过它，实际不可达；作为设计观察记录在 §6。

---

## 3. C-14（潜在）lastActive 回写 —— **已修复**

### 3.1 问题

`server/src/chat.js` 只在「实例原本不在跑」的唤醒分支里写 `lastActive`（`ensureRunning` 内部回写）；当实例已在运行时，`isRunning()` 是**只探活不回写**的，于是长时间活跃的会话其 `lastActive` 一直停留在首次唤醒时刻，30 分钟后空闲巡检会把**正在使用**的实例停掉。

### 3.2 改动（`server/src/chat.js`，+3 / −1）

```js
if (!(await lazy.isRunning(agentId))) {
  ...唤醒...
} else {
  lazy.touch(agentId); // C-14 修复（S3.1）：已在运行的实例同样回写 lastActive，避免空闲巡检把在用实例误停
}
```

`lazy.touch` 已由 `lazystart.js` 导出（`module.exports = { ensureRunning, isRunning, touch, sweep, initTable, statusOf, probe }`），无需补实现。`lazystart.js` **本次零改动**。

### 3.3 diff 摘要

`s31-diffs/chat.js.diff`，11 行（+3 / −1）。

### 3.4 验证证据（`/root/e2e/s31-c14-lastactive.cjs`，走真实 HTTP API + 真实 8787 服务）

`/api/agents` 的 `status.last_active`（由 `agents.js:45` 暴露 `lazy.statusOf`）作为可观测量：

```
JWT 仅存在于内存变量（长度 233），未落盘
① 基线: running=false last_active=null
   第 1 次 /api/chat（唤醒路径）: HTTP 200 耗时 15822ms
② 唤醒后: running=true last_active=2026-09-14T07:47:29.894Z
③ 空闲 4s（对照，期间无任何 chat 调用）: last_active=2026-09-14T07:47:29.894Z
PASS 对照：无 chat 调用时 last_active 不变（证明回写来自 chat 路径而非后台）
   第 2 次 /api/chat（已在运行路径）: HTTP 200 耗时 2921ms
④ 第 2 次对话后: running=true last_active=2026-09-14T07:47:36.828Z
PASS running 会话在第 2 次对话时刷新 lastActive（C-14 修复点） | 07:47:29.894Z → 07:47:36.828Z
PASS 实例保持 running（未被巡检误停） | running=true
小结: 3 PASS / 0 FAIL
```

对照组（③）是关键：**没有** chat 调用时 `last_active` 纹丝不动，证明 ④ 的推进确实来自 chat 路径的回写（而非后台定时器/探活顺带写的）。

### 3.5 「30min 停止逻辑无回归」论证

1. **停止逻辑所在文件未被本次改动触碰**：`lazystart.js` mtime = `2026-09-13 20:58:22`（S3 期版本），sha256 = `fdcc10f91c86f56597853c99d8d2e5e12991dbc3f231dee9efba9f6a5d55aba6`；S3.1 只改了 `chat.js` 的调用侧。
2. S3 第 10 项已在真实服务上观测到完整停机链路：`[lazystart] 空闲超 30min，已停止: testbot`（01:32:29，距 lastActive 01:02:28 为 30min1s，`ExecMainStatus=0`），并含再唤醒全流程。
3. **变更后已在真实服务上复现完整停机事件**（本次校验结束后续观察）：最后一次 `touch` 为 15:47:36，清扫相位为每 5 分钟 :42，于 **16:20:44** 触发
   `[lazystart] 空闲超 30min，已停止: testbot`（距 lastActive 30min 8s），随后 `ss -ltn` 中 8650 端口不再监听（计数 0）。
   即 C-14 改动之后，30 分钟空闲停止逻辑仍按阈值正常触发（证据：`/root/e2e/j-stop.txt`、`/root/e2e/ss-stop.txt`）。

### 3.6 剩余风险

- 实际受影响面只有 `managed === 'lazy'` 的实例（当前仅 testbot）；4 个预设 Agent 为 `managed === 'systemd'`，本来就不受空闲巡检停服。
- 本次校验结束时 testbot 处于 `running`，将按其固有 30 分钟阈值被自动停掉（正常设计行为）。

---

## 4. C-13（可用性）聊天默认会话 —— **已修复**

### 4.1 问题

`ChatView.vue` 挂载时若无活跃会话，一律打开 `chat.convs[0]`（服务端按"最近更新"排序）。会话顺序会随任意成员发言漂移，用户刷新页面后会被带到**另一个**会话，随后发出的消息就落到错误的（曾实测为群聊）会话里。

### 4.2 改动

**`team-console/src/views/ChatView.vue`**（+53 行区间，见 `s31-diffs/ChatView.vue.diff`）：

```ts
const streamRef = ref<InstanceType<typeof ChatStream> | null>(null)
const LAST_CONV_KEY = 'cloudloom:lastConvId'
function rememberConv(id: string) { try { localStorage.setItem(LAST_CONV_KEY, id) } catch {} }
function recallConv(): string { try { return localStorage.getItem(LAST_CONV_KEY) || '' } catch { return '' } }
// 上次打开且仍在有权列表中（已无权则自然回退）→ 否则回退「最近更新」会话
function pickConvId(): string {
  const last = recallConv()
  if (last && chat.convs.some((c) => c.id === last)) return last
  return chat.convs.length ? chat.convs[0].id : ''
}
// 进入会话后滚动到底部（ChatStream 已 expose scrollToEnd）
async function openConvAndScroll(id: string) {
  if (!id) return
  await chat.open(id)
  await streamRef.value?.scrollToEnd()
}
```

`onMounted` 改为 `else if (!chat.activeConv) await openConvAndScroll(pickConvId())`；新增 `watch(() => chat.activeConv, (id) => { if (id) rememberConv(id) })`；`<ChatStream>` 增加 `ref="streamRef"`。

**`team-console/src/components/SideBar.vue`**（13 行，见 `s31-diffs/SideBar.vue.diff`）：当前会话由浅底改为醒目高亮 —— 基类加 `border-l-2 border-transparent`，选中态 `bg-blue-100 dark:bg-gray-600 border-blue-500 font-medium`。

### 4.3 验证证据

**（1）`/root/e2e/s31-c13-conv.mjs`（真实浏览器，Caddy HTTPS 入口，admin 登录态）：9 PASS / 0 FAIL**

```
会话清单（服务端顺序 = 最近更新优先）:
  [0] 负责人 ↔ 张策划 (dm, 9 条消息)
  [1] 阶段3验收群-E2E1789318997034 (group, 4 条消息)
  [2] 阶段3验收群-E2E1789318624175 (group, 7 条消息)
目标会话（非第 0 个，消息最多者）= 阶段3验收群-E2E1789318624175
PASS 左侧会话区渲染 | 会话数=3
PASS 对照：清空记录后按旧逻辑落在 convs[0]（证明旧行为会跳错会话） | 落点=负责人 ↔ 张策划 / convs[0]=负责人 ↔ 张策划 / 目标=阶段3验收群-E2E1789318624175
PASS 点击目标会话后高亮切换 | 高亮=阶段3验收群-E2E1789318624175
PASS 高亮唯一（仅一个会话处于选中态） | 选中数=1
PASS 记住到 localStorage | cloudloom:lastConvId=b5c1f555 期望=b5c1f555
PASS 刷新后回到上次会话（C-13 修复点） | 刷新后高亮=阶段3验收群-E2E1789318624175 期望=阶段3验收群-E2E1789318624175
PASS 旧逻辑落点仍是别的会话（误发群聊路径确实存在过） | convs[0]=负责人 ↔ 张策划
PASS 进入会话后滚动到底部 | scrollTop=0 scrollHeight=725 clientHeight=725
PASS 会话标题在界面可见 | 匹配元素数=2
小结: 9 PASS / 0 FAIL
```

第 2 条与第 7 条是同一个浏览器里的**对照**：清空记忆后落点确为 `convs[0]`（= `负责人 ↔ 张策划`，与目标会话不同）——即旧逻辑的误跳真实存在；写入记忆后刷新则稳定回到目标会话。

**（2）`/root/e2e/s31-c13-scroll.mjs`（视口压到 1280×420 强制内容溢出，复验"滚到底部"）：3 PASS / 0 FAIL**

```
滚动容器: {"cls":"flex-1 overflow-y-auto px-4 py-3 space-y-3","st":359,"sh":604,"ch":245}
PASS 刷新后回到上次会话
PASS 内容超出视口（可滚动，前提成立） | sh=604 ch=245
PASS 进入会话即滚到底部 | scrollTop=359 距底部=0
```

（首轮 9 项测试里该断言 `scrollHeight == clientHeight` 属空真，故追加了这条强制溢出的复验。）

**（3）构建门**：`vue-tsc -b` 退出码 0；`vite build` 退出码 0（`✓ built in 1.75s`），`dist/index.html` 时间戳 2026-09-14 15:48:50；随后用最终构建产物复跑了 (1)，结果不变（9 PASS / 0 FAIL）。

### 4.4 剩余风险

- 记忆存于 `localStorage`：清空浏览器数据/隐私模式/换设备时回退到旧逻辑（仍会落在 `convs[0]`），只是不再"记住"。
- 记录存在但该会话已被删除或当前用户已无权时，`pickConvId` 自动回退到 `convs[0]`（不会打开无权会话）。
- 记忆是"全局一份"：同一浏览器上多用户切换会互相覆盖（当前部署为单席位，风险可忽略；S4 若引入多席位登录须改为按用户隔离的 key）。

---

## 5. 回归与整体验收

### 5.1 全量界面回归 `e2e3.mjs`

```
$ cd /root/e2e && node e2e3.mjs
== 阶段3 界面端到端: 42 PASS / 0 FAIL ==
```

FAIL 计数 = 0，与 Session 3 基线一致。（本次运行期间未重启服务、未并发其他操作；上一轮该脚本在 169 行 `fetch('/manifest.webmanifest')` 处崩溃，系当时正被本代理的服务重启打断所致，非产品缺陷。）

### 5.2 服务与构建终态

| 项 | 结果 |
| --- | --- |
| `systemctl is-active team-console` | `active` |
| `API /api/health`（127.0.0.1:8787） | 200 |
| 前端静态（127.0.0.1:3000） | 200 |
| `NRestarts` / `MainPID` | 0 / 243726 |
| 后端语法门 `node --check` | 退出码 0（每轮回补后均执行） |
| 前端 `vue-tsc -b` | 退出码 0 |
| 前端 `vite build` | 退出码 0（1.75s） |

### 5.3 改动范围核查（S3.1 期间被修改的源文件）

```
$ find /opt/team-console/server/src /opt/team-console/team-console/src -type f -newermt "2026-09-14 15:00"
/opt/team-console/server/src/registry.js          ← C-2
/opt/team-console/server/src/chat.js              ← C-14
/opt/team-console/team-console/src/views/ChatView.vue      ← C-13
/opt/team-console/team-console/src/components/SideBar.vue  ← C-13
/opt/team-console/server/src/index.js             ← C-1
```

恰为题设的 4 项修复所涉 5 个文件，无越界改动。

### 5.4 未改动声明

`server/src/lazystart.js`、`server/src/tasks.js`、`server/src/agents.js`、`server/src/mcp.js`、`server/src/auth.js`、`server/src/config.js`、`server/src/util.js` 及前端其余组件**本次均未改动**（`lazystart.js` mtime/hash 见 §3.5）。

---

## 6. 遗留风险与观察（本次不修，附理由）

1. **`recoverOrphans()` 无宽限期且每分钟执行**：它会把「不在本进程运行表内的 running 任务」立即重排。本次实测中，服务重启会中断在跑任务 → 恢复逻辑重排并重跑（日志 `[tasks] 中断恢复：1 个任务重新排队` 后紧跟 `[tasks] 执行 …`）。这是既有设计行为、非本次缺陷，但会造成"重启即重跑在途任务"。**建议 S4 评估加宽限期或引入执行租约**（本次未改，符合"只修遗留 4 项"的范围约束）。
2. **端口池与自身 API 端口重叠**：候选池 8650-8999 含 8787。因新建 Agent 必经该 API（此刻 8787 必在 LISTEN），探测必然跳过，实际不可达；但若将来调整 API/静态端口落入池内，需重新评估。
3. **C-2 的 TOCTOU 与 Linux 依赖**：见 §2.5。
4. **C-13 的记忆粒度**：单浏览器全局一份，多席位场景需按用户隔离（见 §4.4）。
5. **e2e 产生的任务仍在正常消化**：校验结束时 `done=240 / failed=9 / queued=2 / running=2`，队列由 tasks 运行器顺序处理，无卡死（`running` 行开始时间落在 TASK_TIMEOUT_MS=600s 之内）。
6. **测试窗口内的服务重启副作用**：本次校验共重启 `team-console` 3 次（15:43:54 / 15:45:42 及此前一次），每次都会中断在途任务并按恢复逻辑重排——这正是 C-1 要防的场景，也再次说明第 1 条建议的价值。

---

## 7. 证据索引（服务器路径）

| 类别 | 路径 |
| --- | --- |
| 备份（改前） | `/root/e2e/backups/index.js.bak-s31-20260914-153825`、`.bak-s31b-20260914-154329`、`.bak-s31c-20260914-154348`、`.bak-s31d-20260914-154535`、`registry.js.bak-s31-20260914-153825`、`registry.js.bak-s31c2-20260914-154629`、`chat.js.bak-s31-20260914-1538{25,29}`、`ChatView.vue.bak-s31-20260914-153856`、`SideBar.vue.bak-s31-20260914-1538{56,902}` |
| diff | `/root/e2e/s31-diffs/`（9 个：index.js 四段 + cumulative、registry.js、chat.js、ChatView.vue、SideBar.vue） |
| C-1 判别 | `/root/e2e/s31-c1-prep.cjs`、`s31b-c1-prep.cjs`、`s31-c1-check.cjs`、`s31-c1-second.log`（修复前，含恢复+执行）、`s31-c1-second2.log`（修复前，仅移时机）、`s31b-second.log`（修复后）、`s31-c1-orig.json`、`s31-c1-before.txt` / `-after.txt` / `-snap.diff`、`j-owner.txt`、`j-after.txt` |
| C-1 根因 | `/opt/team-console/server/node_modules/express/lib/application.js:598-606`；`/root/e2e/port-probe.cjs`、`port-probe3.cjs`、`port-probe4.cjs`、`port-probe5.cjs` |
| C-2 | `/root/e2e/s31-c2-port.cjs`、`s31-c2-pool.cjs` |
| C-14 | `/root/e2e/s31-c14-lastactive.cjs`；`lazystart.js` sha256 = `fdcc10f91c86f56597853c99d8d2e5e12991dbc3f231dee9efba9f6a5d55aba6` |
| C-13 | `/root/e2e/s31-c13-conv.mjs`、`s31-c13-scroll.mjs`、截图 `/root/e2e/shots/s31-c13-*.png` |
| 回归/构建 | `/root/e2e/e2e3.mjs`、`/root/e2e/e2e3-s31.log`、`/root/e2e/s31-build.log` |
| 任务表快照 | `/root/e2e/s31-state.cjs` |

---

## 8. 结论

| 项 | 级别 | 结论 | 关键证据 |
| --- | --- | --- | --- |
| C-1 恢复/巡检时机 | 高 | **已修复**（第一版假设被实测推翻，第二版基于 Express 5 根因修正） | 修复前后第二实例日志对照 + 主实例正向对照 |
| C-2 端口分配探测 | 高 | **已修复** | ①–⑥ 六项判定全通过（含真实占用跳过与池耗尽显式报错） |
| C-14 lastActive 回写 | 潜在 | **已修复** | `/api/agents` 实测 `last_active` 推进 + 无调用对照；停止逻辑文件零改动 |
| C-13 聊天默认会话 | 可用性 | **已修复** | 9 PASS / 0 FAIL（含旧逻辑误跳对照）+ 溢出视口滚动复验 3 PASS |
| 回归 `e2e3.mjs` | — | **42 PASS / 0 FAIL** | `== 阶段3 界面端到端: 42 PASS / 0 FAIL ==` |
| 前端构建门 | — | **通过** | `vue-tsc -b` 0 / `vite build` 0（1.75s） |

**待决策事项**：§6 第 1 条（`recoverOrphans` 无宽限期，"重启即重跑在途任务"）是否纳入 S4 处理。
