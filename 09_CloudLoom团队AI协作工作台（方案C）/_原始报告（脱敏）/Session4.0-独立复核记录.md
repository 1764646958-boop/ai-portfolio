> 📄 **作品集展示副本（已脱敏）**：服务器地址 / 主机名 / 域名 / 邮箱 / 凭据 / 令牌均已替换为占位符；
> 完整原报告不随作品集仓库分发。指标与结论未作任何修改。

# Session 4.0 独立复核记录

- **复核对象**：`Session4.0-加固改进报告.md`（B1–B8 八批加固改进）
- **复核时间**：2026-09-14 18:5x ～ 19:0x CST（服务器本地时间）
- **复核方式**：**不引用交付报告的自述**，直接对服务器实测重取；尽量换一条与批次证据不同的路径复现，避免"重读自己的记录"式伪复核
- **复核环境**：`ssh root@<服务器IP>`；全程只读为主，必要的写操作（临时账号、瞬态单元、/tmp 探针）**均已当场清理并复核无残留**
- **密钥/凭据**：复核期间新建的临时账号口令只存在于瞬时 shell 变量、**未落盘**，用完即删；全程未回显任何密钥

---

## 一、逐项复核结果

| # | 复核项 | 独立手段 | 实测结果 | 判定 |
| --- | --- | --- | --- | --- |
| R1 | B5-② 崩溃循环限速 | `systemctl show` 读**生效值**（而非看配置文件） | `StartLimitIntervalUSec=5min`、`StartLimitBurst=10`、`Restart=always`；`DropInPaths` 含 `limits.conf` | ✅ 成立 |
| R2 | B5-④ 最小沙箱 | 以**同一组约束**另建瞬态单元，逐条实测读写 | 生效值 `ProtectSystem=full`/`ProtectHome=read-only`/`PrivateTmp=yes`/`NoNewPrivileges=yes`/`ReadWritePaths` 3 条；**4 条应拒全部被拒**（`/etc`、`/root/.ssh`、`/usr/local/bin`、`/root/.bashrc`）；**4 条应放行全部可写**（`/root/team-files`、`/root/.hermes`、`/etc/systemd/system`、`/opt/team-console/data`）；`PrivateTmp` 对照成立（单元内写 `/tmp`，主机 `/tmp` 不可见）；探针无残留 | ⚠️ 成立，但**发现报告 1 处事实错误**（见二） |
| R3 | B5-③ Caddy 日志轮转 | 读配置 + 观察当前文件增长与保留链 | 配置含 `daily/rotate 14/compress/delaycompress/missingok/notifempty/copytruncate` 并**注释写明了为何不用 postrotate**（本机 Caddy 不重开日志）；`.log` 1,117,105 B（持续写入**规范路径**）、`.1` 1339 B、`.2.gz` 303,054 B | ✅ 成立 |
| R4 | B3 登录安全 | **自建临时账号**走完整注册→批准→登录→登出，直接看响应与 Cookie 属性 | 登录响应体键=`ok,user`（**含 token 字段=false**）；`Set-Cookie` = `Max-Age=604800; Path=/; Expires=…; HttpOnly; **Secure**; SameSite=Lax`；带 Cookie `/api/me`=**200**、无 Cookie=**401**；`logout` 的 `clearCookie` 实测含 `Secure`；临时账号已删（剩余 1 个） | ✅ 成立 |
| R5 | B6-① SPA 回退收窄 | 13 条路径实测（生产路径经 Caddy https） | 缺失资源 **404**：`/api/notexist`→`application/json`、`/assets/notexist.js` 与 `/notfound.png`→`text/plain`；SPA 路由 `/ /chat /kanban /tasks /settings`→**200 text/html**；真实资源 `/manifest.webmanifest`→**200** `application/manifest+json`、`/sw.js`→200、`/avatar-placeholder.png`→200 png；`/api/health`→200、`/mcp`→405 | ✅ 成立 |
| R6 | B1 运维看门狗 | 手动运行 + 读状态 + 读排程 | 手动运行 **rc=0、stdout 0 字节**、状态文件 `issues: {}`；`ops-check.timer` **enabled**、NEXT=`19:00:23` | ✅ 成立 |
| R7 | "未修改任何测试用例"声明 | 读测试文件 **mtime**（比读 diff 更直接） | `e2e3.mjs` mtime = **2026-09-14 00:43** —— 早于本轮全部工作（17:37 起）；`ck(` 断言行 **42 处**，与"42 项断言 / 41 PASS / 1 FAIL"自洽 | ✅ 成立 |
| R8 | B7 补录的 6 条接口确实存在 | 查**路由定义文件:行号** + **实际挂载后的响应** | `PUT /api/me`（`auth.js:86`）→400（参数无效）；`POST /api/members/:id/disable`（`auth.js:117`）→404（**处理器自身的"成员不存在"**）；`GET /api/profiles`（`profiles.js:58`）→200；`GET /api/memories/suggest`（`memories.js:213`）→200；`POST /api/tasks/:id/approval`（`tasks.js:555`）→400；`GET /api/health`（`index.js:15`）→200。**对照实验**：对**真实存在**的 id 调 disable → `{"ok":true}` **200**，证明 404 不是"路由缺失"；6 条均能在 `SPEC.md` 中命中 | ✅ 成立 |
| R9 | B5-① 重启恢复语义 | 代码机制静态核验 + **旁证** | `tasks.js` 中 `RECOVER_PROGRESS`(404)、`requeueInterrupted`(410)、`pre_retry_files`(201/416)、`【重试约束】`(203)、`notifyRecovery`(421)、boot/巡检两条调用链(449/451/461/463)、执行期保持标注(344) 全部在位；备份 tar 内**确有 3 条** `任务恢复-20260914-18{1401,1438,1515}.md`（**旁证**批次内确实发生过恢复并留证，后被 B8 按纪律删除） | ✅ 成立（静态+旁证级，见三） |
| R10 | B8 数据终态 | 独立重新计数（不引用既有结果） | `users` = `[{admin, admin, active}]`；`conversations`/`messages`/`conversation_members`/`tasks`/`outputs`/`task_corrections`/`memories`/**`memory_fts`** 全 = **0** | ✅ 成立 |
| R11 | **FTS 泄漏是否真的堵住** | 用**已删除的测试关键词**去搜记忆库 | 搜「校验」→**0 条**；「restricted」→**0 条**；「策划」→**0 条**；「沙箱」→**0 条** | ✅ 成立。**这是本轮最强判据**：若只清 `memories` 而不清 `memory_fts`，此处必然非 0 |
| R12 | SPEC 身份与版本 | 直接算哈希 + 读生成头 + 数行数 | `/opt/team-console/SPEC.md` sha256 `9b2805663408089c8b40c85bb18230f4c3b9cd5dbbadb8640222a37ea70d019b`（与本地导出一致）、生成头 `v3.3`、**813 行** | ✅ 成立 |

---

## 二、复核发现的修正项（1 处）

**报告 §5.4 把 `ProtectKernelTunables` 列为沙箱组成项 —— 与事实不符。**

- 实测 `systemctl show team-console -p ProtectKernelTunables` → **`no`**（即 systemd 默认值，未被设置）。
- `sandbox.conf` 原文的 `[Service]` 段**恰好 5 个指令**：`NoNewPrivileges=yes`、`PrivateTmp=yes`、`ProtectSystem=full`、`ProtectHome=read-only`、`ReadWritePaths=…`（3 条）。**没有** `ProtectKernelTunables`。
- 同时更正另一处表述：`ReadWritePaths` **只有 3 条**（`/root/.hermes`、`/root/team-files`、`/etc/systemd/system`），报告初稿曾把 `/opt/team-console` 也列进去 —— 实际它可写是因为 `ProtectSystem=full` 只保护 `/usr`/`/boot`/`/etc`（保护 `/opt` 需 `strict`），属"天然可写"，**不在** `ReadWritePaths` 中。
- **已更正交付报告**并注明更正来源。影响面：仅为"沙箱由哪几个指令构成"的描述准确性问题，**沙箱的实际防护效果不变**（R2 实测的 4 拒/4 放行即由这 5 个指令决定）。

### 附带记录：复核工具自身也出过错
R2 的**第一版**探针把属性值未加引号地拼进 `systemd-run`，被 shell 词分割 → 目录 `/root/team-files` 被当成可执行文件，7 条探针**全部返回同一句假失败**。若不复看输出、只看"有没有报错"，会得出"沙箱把所有路径都拦了"的**完全错误结论**。修正（用数组传参 + `--pipe` 取子进程 stdout）后重测，才得到上表结论。记录于此，说明本复核的每个数字都经过"输出是否真的来自被测对象"的自查。

---

## 三、本次复核**未覆盖**的部分（如实声明）

1. **未做 `rollback.sh` 实弹恢复演练**：仅做了脚本存在性与备份内容核对。理由与交付报告 §8.6-2 相同 —— 真跑一次会把刚验净的终态搅回"291 任务/292 记忆"的测试世界，再清理一遍既无新证据又引入新风险。故回滚能力的结论是"**静态验证级**"，不是"**实跑过级**"。
2. **未重跑 B5-① 的行为级复现**（构造中断 → 重启 → 取恢复轨迹）：会重新引入 B8 刚清掉的合成任务与恢复通知。该项为"代码机制 + 证据旁证"级复核。
3. **未重跑 B5-④ 最重的那条链路**（沙箱内由 `hermes` CLI 拉起 testbot 网关、8650 监听数 0→1）：批次内有实测留证，本次复核只覆盖了沙箱的读写边界。
4. **未逐一重排 `docs/` 下的行号引用**（已知漂移风险，B3/B7 已在文档中写明提示）。
5. **未复核前端构建产物与源码的一致性**（`dist` 与 `src` 的对应关系），仅验证了 `dist` 经 Caddy 的对外行为。
6. **未复核 Hermes 侧数据**（`kanban.db`、各 profile 的 `state.db`、cron 输出）是否仍含测试期痕迹 —— 该范围 B8 明确未清理（见交付报告 §8.6-1），本次也不越界。

---

## 四、结论

- B1–B8 的**关键声明在独立重测下全部成立**：限速、沙箱、日志轮转、登录安全、SPA 回退、看门狗、测试未被改动、6 条接口真实存在、数据终态与 FTS 泄漏、SPEC 身份 —— 共 12 项，11 项直接成立、1 项（沙箱构成描述）成立但**发现并更正 1 处事实错误**。
- **未发现功能性问题**：所有对外行为（HTTP 状态码/响应类型/Cookie 属性/搜索命中数）均与交付报告所述一致。
- 最值得强调的一项：**R11 的 FTS 判据** —— 用已删除的测试关键词搜索返回 0 条，证明 B8 复查中发现的那个"删数据不删索引"的泄漏是**真的被堵住了**，而不是靠"查询计数为 0"掩盖过去的。
- 遗留的未覆盖项（第三节 6 条）已逐条声明，其中"回滚未实弹演练"与"B5-① 未行为级重跑"是需要业主知悉的两条。

---

*复核记录生成：2026-09-14 19:0x CST ｜ 复核方式：直连服务器实测 ｜ 对应交付物：`Session4.0-加固改进报告.md`*
