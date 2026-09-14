> 📄 **作品集展示副本（已脱敏）**：服务器地址 / 主机名 / 域名 / 邮箱 / 凭据 / 令牌均已替换为占位符；
> 完整原报告不随作品集仓库分发。指标与结论未作任何修改。

# Session 4.0 加固改进报告 —— 「待改进清单」C-1…C-14 逐项落地

- **任务**：CloudLoom 加固改进包 S4.0（把「待改进清单」逐项落地），分 B1–B8 八批交付
- **执行**：远程执行代理（Claude Code 本机运行），全程 `ssh root@<服务器IP>` 非交互式操作
- **窗口**：2026-09-14 17:37 ～ 19:05（服务器本地时间 CST，分批执行、每批即时验证）
- **环境**：项目根 `/opt/team-console`；Ubuntu 24.04.5；`/usr/local/bin/node` v26.8.2；Express 5.2.1；Vue 3 + Vite
- **基线**：`Session3-部署报告.md` §九（C-1…C-14）、`Session3.1-微修复报告.md`、`Session3.1-独立复核记录.md`
- **服务终态**：`team-console.service` = `active(running)`，`MainPID=313342`，`NRestarts=0`；`/api/health` = 200

> 权威规格为 `/opt/team-console/SPEC.md`（本次由 v3.2 换版至 **v3.3**，见 B7）；与执行稿冲突时以 SPEC 为准。
> 本报告不含任何明文密钥、JWT 或邮箱地址（邮箱已脱敏为「本账号邮箱」）；密钥一律只输出长度与指纹。

---

## 0. 批次总览

| 批次 | 优先级 | 主题 | 结论 | 关键证据 |
| --- | --- | --- | --- | --- |
| B1 | P0 | 运维看门狗（定时巡检 + 异常告警落工作台） | ✅ 完成 | 正常态 rc=0 静默；人为异常 rc=1 出告警；**17:41:35 首次运行即检出 4 项真实异常** |
| B2 | P0 | 定时作业补跑验证 + 密钥收敛 | ✅ 完成 | 三作业全部 completed（105.9s/112.4s/200.1s）；7 处密钥指纹一致；周复盘邮件 IMAP 实测到达 |
| B3 | P1 | 登录安全（C-10 Cookie Secure + 登录不回 token） | ✅ 完成 | Set-Cookie 实测含 `Secure`；响应体键=`[ok,user]`，无 `token` |
| B4 | P1 | 技能链路可用化 + Agent 头像占位 | ✅ 完成 | `skills install` 成功并重启网关后 Agent 可见；头像 6 PASS/0 FAIL + 覆盖 7 PASS/0 FAIL |
| B5 | P2 | 稳定性四件（恢复可见/启动限速/日志轮转/最小沙箱） | ✅ 完成 | 恢复标注可见 + 既有产物 sha256 前后一致；限速演示 10 次后 failed；轮转无 NUL 空洞；沙箱内 hermes CLI 可用 |
| B6 | P2 | 前端细节三件（SPA 回退收窄/通知基线/会话记忆分用户） | ✅ 完成 | 缺失资源 404 不再返回 HTML；通知 6 PASS/0 FAIL；会话键 8 PASS/0 FAIL |
| B7 | P2 | SPEC v3.2 → v3.3 换版（含 6 条接口边界补录） | ✅ 完成 | 本地与服务器 sha256 一致；行号引用同步 3 处；回归 42 PASS/0 FAIL |
| B8 | P1 | 验收残留清理 + 清单口径收敛 | ✅ 完成 | 账号 5→1、任务 291→0、记忆 292→0（含 FTS）；清理后 e2e3 41 PASS/1 FAIL（唯一 FAIL 已定性） |

**未完成批次：无。** 八批全部落地并验证（B8 的一处**有意未做**的动作见 §8.5）。

### 0.1 工程纪律落实

| 纪律项 | 落实方式 | 证据 |
| --- | --- | --- |
| 改前备份 | 每个被改文件先备份到 `/root/e2e/backups/`，后缀 `.bak-s40*` | 各批次 §改动 内逐项列出 |
| 逐项留 diff | 全部 diff 落 `/root/e2e/s40-diffs/`（32 个文件：`.diff` 13 个 + `.txt` 证据 19 个） | §11 证据索引 |
| 最小改动、加法优先 | 既有模块只做定点增补：B3/B4/B5/B6 的代码改动合计 12 处，无重写、无模块搬迁 | 各批次 diff |
| 不重跑 `hermes gateway install` | 全程未执行任何 `hermes … install` | — |
| 不卸载 tirith | 未触碰 tirith | — |
| 不动 `UMask=0077` drop-in | 未触碰；B5-② 新增的是**独立** `limits.conf` | B5-② |
| 不碰决策清单第四节 | 未触碰 | — |
| 密钥纪律 | 只进 `.env`/`agents.json`（600）；核验脚本只输出长度+指纹；临时脚本用完即删 | B2 §四（7 处指纹一致） |
| 不发明接口 | 仅实现 SPEC 明确要求的路由；B7 补录的 6 条均先核对代码确实存在才写入规格 | §7.3 |
| 非交互式 SSH / 常驻服务 | 长任务一律 `nohup` + 日志落盘（画像作业重跑） | §8.4 |
| 域名未就绪的降级路径 | 全程走自签 HTTPS（`https://127.0.0.1`），**未做 IP 直连对外** | §9 |

---

## 1. B1（P0）运维看门狗

### 1.1 问题
清单 C-9 一类：服务器只有"事后翻 journal"的排障路径，没有主动巡检；磁盘/余额/单元/端口的异常要等人发现。且 B2 暴露的"三作业连续 402 失败"正是**整晚无人知晓**的典型。

### 1.2 改动（四个新增文件，**未修改任何既有文件**）
| 文件 | 大小 | sha256 |
| --- | --- | --- |
| `/opt/team-console/ops/ops-check.py` | 18172 | `94c23e2659fd24ce…91b938` |
| `/etc/systemd/system/ops-check.service` | 378 | `5167949448c42408…4a744b` |
| `/etc/systemd/system/ops-check.timer` | 216 | `9547424dfb749755…c36097` |
| `/opt/team-console/ops/.ops-check-state.json` | 71 | `3c2ba6dfe6305ec3…bdede7b` |

- `service`：`Type=oneshot`、`SuccessExitStatus=0 1`（**1 表示"检测到异常"而非失败**）、`Nice=10` + `IOSchedulingClass=idle`（不干扰业务）。
- `timer`：`OnCalendar=*:0/15` + `AccuracySec=30s` + `RandomizedDelaySec=30` + `Persistent=true`。
- 巡检项：作业失败、API 余额、systemd 单元、端口监听、`/api/health`、磁盘占用；异常写 `~/team-files/系统通知/运维告警-<时间>.md`（工作台可见），正常**零输出**；同日同类告警 6h 去重。

**一次实测推翻与返工**：timer 首版含 `OnBootSec=2min`，`systemctl list-timers` 实测 `NEXT` 为空（systemd 判定 `OnBootSec` 已耗尽、不再排程）→ 改为**仅 `OnCalendar`**，NEXT 随即正常。首版留存 `ops-check.timer.bak-s40-20260914-174143`，diff `B1-ops-check.timer.diff`。

### 1.3 验证证据（四条，全部实跑）
1. **正常态**：手动运行退出码 0、stdout 为空、无新通知文件；状态文件 `issues` 被清空为 `{}`。
2. **人为异常**（`OPS_BALANCE_THRESHOLD=999`）：退出码 1，生成 `运维告警-20260914-1751.md`，内容含「当前余额=32.93 CNY  is_available=True」「阈值 999.0」；同日重跑被 6h 去重**静默**（rc=0、无新文件）；测试文件已删、状态快照已还原。
3. **排程与触发**：`list-timers` NEXT=`2026-09-14 18:00:20`（含抖动）；`journalctl -u ops-check.service` 可见 17:41:35 与 17:45:01 两次触发。
4. **工作台可见**：`GET /api/poll?since=0`（管理员）返回 6 个通知文件，含 `运维告警-20260914-1741.md`（size=2162，预览正确）。

**真实战果**：2026-09-14 **17:41:35 首次运行即检出 4 项真实异常**（三个定时作业 402 失败 + 凭据 `exhausted`），产出 `运维告警-20260914-1741.md`；经 B2 修复后状态自动清除（终态 `.ops-check-state.json` = `issues: {}`，last_run 18:45:01）。

### 1.4 剩余风险
- **告警只有站内通道**：异常落在工作台可见的文件里，**不推送**邮件/短信/IM。值班人不上工作台就看不到 —— 若要求"离线也能收到"，需另加外发通道（属新功能，未在本批实施）。
- 巡检周期 15 分钟：突发的短时异常（如瞬时端口闪断）可能落在两次巡检之间。
- 阈值类参数（余额、磁盘）通过环境变量注入，实际口径记在脚本与 `docs/故障排查表.md`；改阈值需改 unit 或环境文件。

---

## 2. B2（P0）定时作业验证 + 密钥收敛

### 2.1 问题与根因（实测）
**现象**：zhiban 三个定时作业在 09-14 06:00 / 09:00 / 10:00 连续失败，`last_error = RuntimeError: HTTP 402: Insufficient Balance`。
**根因两条**：① 账户余额耗尽；② Hermes 已把该凭据记入 `auth.json` 的 `credential_pool`（`last_status=exhausted`、`last_error_code=402`、`last_error_reset_at=None`）—— **充值后不会自动恢复**，作业会继续静默失败。
**排查副产品**：7 处 `.env` 的密钥指纹**完全一致**（sha256 前 12 位 `<密钥指纹>`、长度 35），不存在"旧密钥残留"；唯一缺口是 `/etc/hermes.env`（网关单元的 `EnvironmentFile`）**当时没有该键**。

### 2.2 改动清单（7 项，每项有备份/diff）
| # | 改动 | 备注 |
| --- | --- | --- |
| 1 | 复位凭据池 `hermes --profile zhiban auth deepseek reset` | 实测 `Reset status on 1 deepseek credentials`；diff `B2-auth.json.diff`（5 个键 → null） |
| 2 | 新增 `ops/rotate-deepseek-key.sh`（111 行） | `bash -n` 通过；一键备份 → 同步全部 `.env` → 保持 600 → 复位凭据池 → 重启 4 网关 → 核验，**全程不回显密钥** |
| 3 | `/etc/hermes.env` 补 `DEEPSEEK_API_KEY`（原缺失），600 | 备份 `.env.bak-s40key-20260914-175321` |
| 4 | `HERMES.md` 更新「更换密钥」+ 2 条注意事项 | diff `B2-HERMES.md.diff` |
| 5 | `docs/故障排查表.md` 追加附录 D | diff `B2-故障排查表.md.diff` |
| 6 | 本机《部署前置清单-管理员操作》新增「密钥轮换与已充值却仍报 402 处理」 | 纯本机文档（服务器上不存在该文件） |
| 7 | 画像产物名对齐（`…-补跑1755.json` → canonical 名） | 原因见 2.4-1 |

### 2.3 验证证据
| 作业 | 计划 | 补跑窗口 | 产物 | 结果 |
| --- | --- | --- | --- | --- |
| 晨报 `44cf46376cff` | `0 9 * * *` | 17:42:09 → 17:43:55（105.9s） | `晨报-20260914.md` 6687 B | completed |
| 周复盘 `ec6e303a9e33` | `0 10 * * 1` | 17:45:08 → 17:47:01（112.4s） | `周复盘-20260914.md` 16078 B | completed；**邮件 IMAP 实测到达**（主题「【周复盘】2026-09-14 楚华成章团队周复盘」，发件人=本账号） |
| 画像 `367f1c9db36f` | `0 6 * * *` | 17:47:06 → 17:50:26（200.1s） | `画像-20260914.json` 24913 B | completed |

- `jobs.json`：三作业 `last_status=ok`、`last_error=None`、`next_run_at` 正常（09-15 09:00 / 09-21 10:00 / 09-15 06:00）；`executions.db` 新增 3 条 `status=completed`（历史 402 失败行**保留未改**）。
- **轮换脚本验收**（值不变，只比长度与指纹）：`--check` → 7 处指纹一致（终态复核：**含 `/etc/hermes.env` 在内 7/7 均为 `<密钥指纹>` 长度 35**）；轮换执行 → 6 处"未变化"、1 处"已更新"，更新文件数=1；4 个网关重启后 `ActiveState=active`；`/api/health`=200。
- **真实会话**：`POST /api/chat {agent=cehua}` → HTTP 200（7.6s，content=链路正常）。余额探测 可用=True、`total_balance=32.53 CNY`。

### 2.4 剩余风险（含需业主决策项）
1. **画像产物 schema 不稳定**：本次出现 2 次 `finish_reason=length`（模型输出被截断），且 Agent 自行把文件名写成 `画像-20260914-补跑1755.json`；`profiles.js` 取目录内**字典序最大**的 `画像-*.json`，带后缀的名字排序反而更小 —— 补跑产物不会自动顶上。本次人工对齐命名。根治建议二选一：改 prompt 写死文件名，或改 `profiles.js` 取 mtime 最新（**属代码改动，未擅自实施**）。本次 B8 重跑已观察到**同一作业两次输出结构不同**（一次含 `board_snapshot`，一次为 `team_level_findings/preferences_synced_to_memory/limitations`），进一步印证该风险。
2. **晨报没有邮件**：晨报 prompt 只要求写文件（`deliver=local`），故当日无晨报邮件；如需晨报邮件须改 prompt（未擅自改）。
3. **余额**：32.53 元，本轮三次补跑约耗 1.35 元、B8 画像重跑约耗 0.45 元；看门狗阈值已是 5 元。日常用量下需关注。
4. **密钥仍是 7 处明文副本**（均 600）：已有"一键轮换"脚本，但**没有**密钥托管/轮换周期制度。
5. `auth.json` 的 `credential_pool` 在余额恢复后本可由 Hermes 自动重试，本次为消除歧义显式复位；脚本已内置该步，复发时按脚本走即可。

---

## 3. B3（P1）登录安全

### 3.1 问题
- **C-10**：登录 Cookie 未设 `Secure`（`auth.js` 的 setCookie 只有 `httpOnly/sameSite/maxAge/path`）。
- **偏差 B2**（前端开发者说明·风险表）：登录响应体回传 `token`，使 JWT 变成 JS 可读，削弱 httpOnly 的防护意图；而 `SPEC.md` 原本就写明 `/api/login` 是「JWT httpOnly cookie」—— **回传 token 属实现偏差**，不是规格要求。

### 3.2 改动（`server/src/auth.js`，3 处；备份 `auth.js.bak-s40-20260914-175634`，diff `B3-auth.js.diff`）
1. `setCookie` 新增 `secure: true`（`auth.js:17-19`，含 2 行说明注释）。
2. `POST /api/login` 响应体由 `{ ok, user, token }` → **`{ ok, user }`**（`auth.js:79`）—— 前端本就零 token 依赖（全量 `src/` grep 无 `token`，取会话完全靠 Cookie），故无兼容性影响。
3. `POST /api/logout` 的 `clearCookie` 属性与下发一致（`path/httpOnly/sameSite/secure`），否则部分浏览器不会真正清除（`auth.js:101-102`）。

**未改动**：register 分支原本就不回传 token；Bearer 兼容（`extractToken`）保留 —— MCP/外部客户端不受影响。

### 3.3 验证证据（全部经 Caddy HTTPS 443，非 `http://127.0.0.1:3000`）
1. `POST /api/login` → HTTP 200，响应体键=`[ok,user]`，**含 token 字段=False**；`user` 字段=`[avatar,created_at,display_name,id,notify_enabled,role,status,username]`（无口令哈希等敏感字段）。
2. `Set-Cookie` 属性实测=`[Max-Age=604800, Path=/, Expires=…, HttpOnly, **Secure**, SameSite=Lax]`（Cookie 值未回显）。
3. **刷新保持会话**（新增用例）：带该 Cookie `GET /api/me` → 200，user=uicheck。
4. `POST /api/logout` → 200 `{ok:true}`；退出后无 Cookie `GET /api/me` → 401。
5. 服务健康：重启后 `/api/health`=200、8787 在听、`journal --since -2min` 无 error/throw（grep 计数 0）。

### 3.4 文档同步（9 处 + 1 处）
`docs/前端开发者说明.md`（备份 `.bak-s40b3-175716`）：更新 auth.js 统计行 121→125、接口表 3/6 的返回与行号、§3.2 补 `secure: true` 并加"本次改动使登录后行号 +2~+4"提示块、Bearer 示例改为"专用签发的 token"、「登录态异常」条补 HTTPS 要求、风险表 B2 条标注**【已于 S4.0/B3 修复】**。
`docs/故障排查表.md` §6：说明登录不再回传 token。

### 3.5 剩余风险
1. **无状态 JWT 不随登出吊销**：退出后**重放旧 Cookie 仍返回 200**（实测第 6 步）。浏览器侧"退出即失效"成立（Cookie 被清），但被窃取的 Cookie 在 7 天有效期内仍可用。根治需服务端会话/吊销名单或缩短 TTL —— **属设计决策，未擅自实施**。
2. **`Secure` 使 http 直连（3000/8787）无法保持登录态**：已在两份文档写明"工作台必须走 HTTPS"。若业主希望保留 http 回退（IP 直连应急），需另行决策（可改为按请求协议条件设置 `Secure`）。
3. 文档中其余 `auth.js:NN` 行号引用未逐一重排（改动插入了注释，登录后行号 +2~+4），已在 §3.2 写明该提示。

---

## 4. B4（P1）技能链路 + 头像占位

### 4.1 问题 1：`hermes skills search/install` 看似"静默返回空"
**现象**：`hermes skills search git` 打印 `Searching for: git` 后**永久阻塞**（20s 超时、退出码 124，stdout 仅 20 字节）。
**逐源定位**（`--limit 3`，各 18s）：`official` / `skills-sh` / `lobehub` / `well-known` → 退出码 0、24 行正常；**`clawhub` / `github` → 退出码 124（阻塞）**。
**根因**：默认 `--source all` 会一并查 github/clawhub，而该 CLI 对这两个源未设连接/读取超时。出网实测：`skills.sh` 308(1s 通)、`clawhub.ai` 200(2s 通但 CLI 用的接口路径不通)、`github.com` 200(8s 慢通)、**`raw.githubusercontent.com` HTTP 000(8s 超时不通)** —— github 源取 `SKILL.md` 正是走这里（属机房出网限制）。

**当前可用落地路径（已实测）**：
```bash
hermes skills search <关键词> --source official --limit 10             # 检索：必须显式指定源
hermes --profile cehua skills install official/creative/concept-diagrams --yes
systemctl restart hermes-gateway-cehua                                 # ★ 不重启网关，Agent 看不到新技能
hermes --profile cehua skills list | grep concept                      # 核验
```
安装实测：退出码 0，落地 19 个文件，产出溯源扫描 `Scan provenance: fresh` + `sha256:b437e789…f2105`。
**真实对话验证（同一提示词，重启前后对比）**：重启前 Agent 答"我当前可用技能里没有任何名字含 concept 的技能"（1.29s）→ 重启后答出技能名与描述（4.57s）—— 证明**技能索引在网关启动时构建、进程内不热加载**。

### 4.2 问题 2：Agent 头像占位图
**问题**：前端全套 `.vue` 源码**不含任何头像渲染**（grep 零命中），`/api/agents` 也不返回 `avatar` —— 5 个 Agent 卡片没有头像槽位、缺图也没有回退。
**改动（加法为主，4 处）**：
1. 新增 `public/avatar-placeholder.png`（128×128 纯灰 `#9E9E9E`，252 B，sha256 `7e889971…cdfbd`；用 Python 标准库手写 PNG）+ `dist/` 同源副本（`public/` 是 Vite 静态约定目录，重建不丢）。
2. `src/views/SettingsView.vue`：Agent 接口补可选字段 `avatar?: string | null`；卡片新增头像槽位，`src` 取 `a.avatar`，为空回退 `/avatar-placeholder.png`（diff `B4-SettingsView.vue.diff`，2 处）。
3. `server/src/agents.js`：`GET /api/agents` 的响应字段白名单补 `avatar: a.avatar || null`。
4. **`server/src/registry.js`（关键）**：`normalize()` 的字段白名单同样丢弃 `avatar`（读写两条路径都过它），**只改 (3) 无效** —— 实测只改 (3) 时 `/api/agents` 仍返回 `avatar=null`。补 `avatar: raw.avatar || null` 后覆盖测试全通过。该改动同时使 `avatar` 在管理员通过 UI 更新 Agent 时**不会被静默抹掉**。

**验收**：基线 `s40-avatar-check.mjs base` → **6 PASS / 0 FAIL**（5 张卡片各含 1 个槽位、`src` 均为占位图、`naturalWidth/Height=128×128` 真实加载、无失败请求/无 JS 错误）；覆盖（临时给 cehua 配 `avatar=/favicon.svg`）→ **7 PASS / 0 FAIL**（策划 Agent 变为 `/favicon.svg` 48×46，其余 4 个不变）。HTTPS 可达：`curl -sk https://localhost/avatar-placeholder.png` → 200 `image/png` 252 B（经 8787 返回 404 属预期：8787 是 API 服务，静态资源由 Caddy 直出 `dist`）。
**`agents.json` 未被改动**：测试期临时值测毕已还原，sha256 前 16 位 `13a055b77575f183`（与测试前一致），权限 600。

### 4.3 剩余风险
1. `source=all` 的默认行为**未改变**（未改 Hermes 源码，也不应改）—— 使用方须显式带 `--source`。
2. `raw.githubusercontent.com` 不可达属**机房出网限制**，非本机可改；`clawhub` 阻塞原因未深究（非交付必需）。
3. `npm run build` 重建了 `dist` 全部产物，`assets` 文件名哈希整体变化（如 `SettingsView-joVy9YPd.js`）；已回归 e2e3 验证 SPA 六 Tab 正常。回退解包 `dist.bak-s40-20260914-180749.tar.gz` 即可。
4. 本次只覆盖 **Agent 卡片**槽位（验收口径即 5 个 Agent）；**用户头像**（顶栏/成员列表，`users.avatar` 字段已存在）未加槽位，属范围外。
5. 占位图为纯灰；若后续要按 Agent 区分配色需另议（当前保持最小改动）。

---

## 5. B5（P2）稳定性四件

### 5.1 B5-① 重启恢复：保留「重启即恢复」，补「可见 + 不覆盖」
**问题**：S3.1/C-1 已实现重启后把遗留 `running` 任务重排，但 ① 进度文案被 `execute()` 立即覆盖为「正在执行」，用户全程看不到"这是重启恢复、可能重复执行"；② 无系统通知；③ 重试若与中断前产物同名会**直接覆盖**。
**改动**（`server/src/tasks.js`，5 处；diff `B5-tasks.js.diff`）：新增 `RECOVER_PROGRESS` 常量与 `requeueInterrupted()` / `notifyRecovery()`；`recoverStale`（boot，30s 宽限）与 `recoverOrphans`（60s 孤儿巡检）均改走该路径并写通知；`buildInstruction` 在 `meta.retry` 为真时插入**【重试约束】**段（列出中断前已有文件、严禁覆盖删除、同名须另存为 `<原名>-retry-<HHMMSS>`）；`execute()` 在执行期间保持恢复标注（**该处为实测发现的缺口，后补**）。
**验证（构造真实中断 → 重启 → 取证，三轮）**：
- E1 恢复发生：journal `18:15:15 [tasks] 中断恢复：1 个任务重新排队`；任务被 cehua 真实重跑并 `status=done`。
- E2 标注可见（0.15s 轮询轨迹）：`+0.01s 正在执行` → `+0.31s 系统重启后恢复（可能与中断前重复执行）` → `+3.77s 完成，登记产物 1 个`。
- E3 系统通知：`任务恢复-20260914-181515.md`（464 B，600）含时间/来源/**恢复任务数**/任务 id 列表与三句风险明示；`GET /api/poll`（admin）实测下发。
- E4 **不覆盖**：中断前产物 `既有产物.md` 的 sha256 在重启+重跑前后**完全一致**（`29c80ed1…b849a`）；Agent 回复中原样复述了【重试约束】第 2、3 条；任务 meta 实测 `retry=true`、`pre_retry_files=['既有产物.md']`。

**剩余风险**：「不覆盖」由两层保证 —— ① 服务端在指令中强制命名规则（Agent 是唯一写方）；② 恢复时把中断前产物清单写入 `meta` 并在通知中明示。服务端**不复制**中断前文件，若 Agent 无视指令强行同名写入，原始内容仍会丢失。该保证本质是**"指令强约束 + 事后可见"，未做字节级快照兜底**；若需硬保证，二期可在恢复时把产物目录快照到 `.retry-snapshot/` 并在结束后比对还原。

### 5.2 B5-② team-console 崩溃循环限速
**问题**：单元原为 `StartLimitIntervalSec=0` —— **完全不限速**；`Restart=always + RestartSec=3` 下若陷入秒级崩溃循环，systemd 会无限重启、刷爆 journal 并掩盖真正的错误（systemd 默认值是 10 次/10 秒，被这一行显式关掉）。
**改动**：纯加法 drop-in `/etc/systemd/system/team-console.service.d/limits.conf`（`StartLimitIntervalSec=300` / `StartLimitBurst=10`），**未改单元本体一行**。
> ⚠️ **避开的坑**：这两个键属于 **[Unit]** 段而非 `[Service]`；写在 `[Service]` 里 systemd **不报错、静默忽略** —— 属"看起来配了、其实没配"。
**验证**：E1 生效参数 `StartLimitIntervalUSec=5min / StartLimitBurst=10`。E2 用临时单元 `s40-limtest`（同参数、进程立即失败）实跑：`NRestarts` 2→4→6→8→10，t=12s 时 `active=failed`，日志出现 `Start request repeated too quickly`；`reset-failed` 后计数归零、可正常再启动；**演示单元当场删除**（`status` 首行 `Unit could not be found`，无残留）。
**剩余风险**：R1 限速后真实崩溃循环会停在 `failed` 而不再自动恢复 —— **这正是设计意图**（避免刷日志掩盖根因），但需有人被告知：兜底是 B1 看门狗（每 15 分钟查单元状态），人工恢复命令 `systemctl reset-failed team-console && systemctl start team-console`。R2 `10 次/300 秒` 对"每分钟崩一次"的慢速循环仍会放行（阈值压太紧会误伤正常发布的连续重启）。

### 5.3 B5-③ Caddy 访问日志轮转
**问题**：`/var/log/caddy/cloudloom-access.log` 无任何轮转配置，实测已 4,966,855 B（≈4.97 MB）且线性增长。
**诊断过程（两种"重开日志"机制在本机 Caddy 上均无效，实测非推测）**：
- 机制 1 `postrotate` 发 `SIGUSR1`：`/proc/898/fd/12` 仍指向改名后的 `.1`（inode 938684）；新 `.log`（inode 958488）恒为 0 字节。
- 机制 2 `systemctl reload caddy`：`ExecReload` rc=0 但 **pid 不变（898）、fd 不变**，仍指向 `.1`。
- **附带发现**：因 Caddy 一直写 `.1`，规范路径上的 `.log` 为 0 字节，被 `notifempty` 判定"空文件不轮转"，导致 `postrotate` 连触发机会都没有（`logrotate -f` 静默跳过）—— 这本身就是"轮转看起来配好了、实际从不动手"的隐患。
**最终方案**：`/etc/logrotate.d/caddy` 用 **`copytruncate`**（`daily / rotate 14 / compress / delaycompress / missingok / notifempty`），Caddy 以 `O_APPEND` 打开，截断后续写仍落在同一 inode。
**验证**：E3 `logrotate -f` rc=0 → `.log` 原地截断（inode 938684 不变、0 字节）、`.1` 保留完整旧内容（4,966,855 B 相等）。E4 **关键判据**：轮转后发 2 次真实 HTTPS 请求 → `.log` 0→1339 B（新请求确实落在规范路径）；**NUL 空洞检查 `wc -c`=1339 与 `tr -d '\0' | wc -c`=1339 完全一致，无空洞**。E5 第二次轮转验证保留链：`.1`（delaycompress 暂不压缩）/ `.2.gz` 303,054 B（压缩比约 16:1）。E6 全程 `/api/health`=200，Caddy 未重启（pid 898 不变）。
**剩余风险**：R1 `copytruncate` 的毫秒窗口内少量日志行可能丢失（不可完全消除，除非改 Caddy 日志驱动）—— 访问日志可接受。R2 单日峰值写入若远超预期仍可能一天涨到百 MB 级，已由 B1 磁盘告警（80%）兜底。R3 若日后升级到支持重开日志的 Caddy 版本可改回 rename+postrotate；原因已写在配置文件里，避免后人误改。

### 5.4 B5-④ 最小沙箱 + systemd-oomd
**问题**：单元以 `User=root` 运行，且**设计上就需要**执行 `systemctl` 与 `hermes` CLI —— Web 层一旦被攻破即等于交出 root + 服务管理能力，爆炸半径是"整机"。2C4G 小机也没有 OOM 防护：内核 OOM killer 会随机挑"分数最高"的进程杀（可能是 hermes 网关或 team-console 本身），无策略、无记录。
**改动一：systemd-oomd**（安装 + 启用，用发行版默认策略、不自造参数）：安装模拟先行核对 —— **仅新增 1 个包、0 个升级**（版本 255.4-1ubuntu8.17，与在跑 systemd 同版本）。**作用域判定（重要）**：被托管的只有 `-.slice`（swap）与 `user@.service`（用户会话）；`team-console`、4 个 hermes 网关、`caddy`、`docker` 都是 **`system.slice` 下的系统单元、不在 oomd 托管范围** → oomd 不会去杀这些服务，它杀的是"有人 SSH 进来跑了个吃内存的东西"这类用户会话进程。当前水位：Swap 1987 MB 已用 0；`/proc/pressure/memory` 三项 avg 全 0.00。
**改动二：最小沙箱**（`/etc/systemd/system/team-console.service.d/sandbox.conf`，纯加法 drop-in）：`[Service]` 段**恰好 5 个指令** —— `NoNewPrivileges=yes` / `PrivateTmp=yes` / `ProtectSystem=full` / `ProtectHome=read-only` / `ReadWritePaths=/root/.hermes /root/team-files /etc/systemd/system`。**放行清单由实测得出，不是照抄模板**：三个放行路径分别对应「产出目录+系统通知」「`kanban.db`/`profiles/*`/sessions/auth.json」「新建 Agent 时写 `hermes-gateway-<id>.service.d/10-cloudloom-env.conf`（**必须放行，否则"新建 Agent"会静默失败**）」。
> 两点如实说明（独立复核时核对）：① 放行清单**只有 3 条**，`/opt/team-console` **不在其中** —— 它可写是因为 `ProtectSystem=full` 只保护 `/usr`/`/boot`/`/etc`（保护 `/opt` 需要 `strict`），故此路径属"天然可写"，不需要也不应列入 `ReadWritePaths`；② 本 drop-in **没有**设置 `ProtectKernelTunables`（单元实际生效值为 `no`，即 systemd 默认）—— 初稿报告曾把它列为沙箱组成项，经复核更正。
**验证（逐条实测）**：① 单元重启后 active；② 写路径逐项实测（含 `/root/team-files/产出/…` 写盘成功）；③ 读接口回归 `/api/health /api/tasks /api/files /api/poll /api/agents /api/me` **全 200**；④ **hermes CLI 沙箱子进程链实测**（最关键路径）：chat 前 8650 监听数=0 → 发消息给 testbot → HTTP 200、`content=沙箱可用` → chat 后 8650 监听数=1（**网关被沙箱内的 hermes CLI 成功拉起**），测后已 `gateway stop` 复原并确认 90s 后仍为 0；⑤ 内核拒绝扫描：journal 全窗口 grep `read-only file system|EROFS|EPERM|EACCES` → **无**（沙箱未拦截任何一次正常业务写入）；⑥ 批次回归 e2e3 → **42 PASS / 0 FAIL**。
> **独立复核追加（2026-09-14 19:0x，由复核方另建瞬态单元实测，非引用本报告）**：以**同一组约束**建瞬态单元逐条实测 —— `/etc`、`/root/.ssh`、`/usr/local/bin`、`/root/.bashrc` 四条**全部被拒**；`/root/team-files`、`/root/.hermes`、`/etc/systemd/system`、`/opt/team-console/data` 四条**全部可写**；单元内写 `/tmp` 后在**主机 `/tmp` 不可见**（`PrivateTmp` 生效）；探针无残留。结论与配置注释逐条吻合。

**剩余风险**：R1 沙箱是**纵深防御、不是安全边界**（进程仍是 root 且按设计能执行 systemctl/hermes）；它真正的价值是砍掉"改 SSH 公钥/换系统二进制/改 `/etc/passwd`/改 root 环境"这几条最典型的持久化与提权路径。R2 `PrivateTmp=yes` 后 `/tmp` 与其他服务**不再共享**；当前代码无 `/tmp` 用法（已 grep 确认），但**将来若有人写"team-console 落临时文件、hermes 网关去读"的跨服务 `/tmp` 协作会静默失效**（已写入证据文件备查）。R3 hermes CLI 在 `/root` 下的写路径只覆盖了 `/root/.hermes`；若升级后它开始写 `/root/.cache`、`/root/.local/state` 等新位置会以 `Read-only file system` 报错（特征明显，补进 `ReadWritePaths` 即可）。R4 oomd 用发行版默认策略，若日后给团队开 SSH 交互使用，压力下用户会话可能被杀 —— 需告知。

---

## 6. B6（P2）前端细节三件

### 6.1 B6-① SPA 回退收窄（**先实测复现，后改**）
**问题**：生产静态资源由 Caddy 直出，`try_files {path} /index.html` 对**所有**未命中路径一律回退 → 缺失的静态资源返回 **200 + text/html**（实测 `curl -sk https://127.0.0.1/assets/notexist.js` → 200 text/html）。后果：浏览器把 HTML 当 JS 解析，报 `Unexpected token '<'` —— **把"文件缺失"伪装成"代码报错"**，排障方向完全错。Node `:3000` 静态服务同样有此回退。
> ⚠️ **关键点**：**只改 Node 侧不能修复用户可见行为** —— 生产路径根本不经过 `:3000`。若只改 Node 就宣布"已修复"，属于典型的"改了但没生效"。**两侧均已改**。
**改动**：Caddyfile 用 `@asset path_regexp \.[A-Za-z0-9]{1,16}$` 把带扩展名的路径交给 `file_server` 直出、不再回退；缺失时由 `@missingAsset` 显式返回 404 纯文本；无扩展名路径保留 SPA 回退。`index.js`（:3000）同步：`/api` 前缀 → 404 JSON；带扩展名 → 404 纯文本；其余 → index.html。
**验证（生产路径，经 Caddy https）**：`/api/notexist` → 404 `application/json`；`/assets/notexist.js`、`/notfound.png` → 404 `text/plain`；SPA 路由 `/ /chat /kanban /tasks /settings /deep/unknown/route` **全部 200 text/html**（回退仍正常）；真实资源逐个回归零失败（`/` 200、`/avatar-placeholder.png` 200 png、**`/manifest.webmanifest` 200** ← PWA 安装条件、重点回归项、`/sw.js` 200、`/assets/index-*.js` 200）；反代契约未受影响（`/api/health` 200、`/mcp` 405 后端返回符合预期）；两次改动均先 `caddy validate` → Valid 再 `systemctl reload`（配置非法时 Caddy 拒绝并继续用旧配置，不中断服务）。
**剩余风险**：R1 规则以"路径是否含扩展名"区分资源与前端路由；当前前端路由均不含点号，安全；**若将来新增带点号的前端路由**（如 `/v1.2/...`）会被判为静态资源而 404（已写进 Caddyfile 注释）。R2 `/favicon.ico` 实测 404 —— 该文件本就不在 `dist` 中（本次只是把它从"200 HTML"纠正为"404"），**非本次引入**；如需图标应补资源文件（列入剩余项，未在本批处理）。R3 Caddy 的 file 匹配器使用绝对路径 `/opt/team-console/team-console/dist{path}`；日后迁移目录需同步修改（已注释）。

### 6.2 B6-② 通知基线时机（首轮只建基线，不轰炸历史）
**问题**：`notify.ts` 的 `tick()` 把 `primed = true` 写在 `try/catch` **之外** → 任何一次失败轮询（应用启动时未登录的 401、网络抖动、服务重启）也会把 `primed` 置真，使"第一个成功的轮询"被误判为"已建过基线"，**把目录里全部历史通知当成新通知推给用户**。且 `MainLayout` 只在 `logout()` 里调 `resetNotify()`，登录后没有重建基线 → **缺陷在正常登录流程中必然发生**。
**复现证据（修复前，目录内 13 条历史通知）**：`FAIL A2 首个成功轮询不弹历史通知 | 弹窗数=3`（例：`阶段3通知实测-…`、`任务恢复-…`×2）、`FAIL A3 首轮后红点为空 | 红点="13"`、`FAIL A5 新通知红点 = 1 | 红点="14"` → **3 PASS / 3 FAIL**。
**改动**：把 `primed = true` **移入 `try` 内**（只有成功拿到 `since` 基线才算已基线化）；catch 分支不置 `primed`、不推进 `since`，留待下次成功轮询建基线。
**验证（同脚本同素材，修复后）**：A1 轮询失败期间不弹窗（0）→ A2 首个成功轮询不弹历史（0）→ A3 首轮后红点为空（`""`）→ A4 新通知 8 秒内弹窗（1，`CloudLoOM 新通知 · s40-notify-probe-…md`）→ A5 新通知红点 = 1 → A6 无 JS 错误 → **6 PASS / 0 FAIL**。
**剩余风险**：R1 基线以"第一个成功的轮询"为界 —— 登录**之前**到达的通知不会被提示（符合本项验收口径；如需补偿应另做"未读历史"入口，属新功能）。R2 弹窗依赖浏览器 Notification 授权，未授权时仅红点计数（原有行为）。

### 6.3 B6-③ 会话记忆按用户区分
**问题**：`ChatView` 用**全局键** `cloudloom:lastConvId` 记住"上次打开的会话" —— 同一浏览器上 A 退出、B 登录后，B 会继承 A 的"上次会话"并直接跳进去（**越权观感**），且容易把消息发错会话（该键本就是 S3.1 为修 C-13"消息误发群聊"而加的，串号会重现同类问题）。
**改动**：新键 `cloudloom:<user_id>:lastConvId`（`user_id` 取自 `/api/me`）；旧全局键**不再读取**（无法判定它属于谁，读了就有串号风险），仅做一次清理。
**验证**（观测手段为**拦截 `/api/conversations/<id>/messages` 请求**客观判定"应用打开了哪个会话"，不依赖 DOM 细节；A=admin、B=zhang，同一浏览器上下文；账号切换走**真实退出路径** `POST /api/logout` 后再注入 B 的会话）：前置 A 可见 3 个会话；A 写入自己的键（`b5c1f555`）；旧全局键已清理（null）；换账号后 A 的键原样保留；**B 不会继承 A 的会话**（B键=`6cfb3293` ≠ A键）；B 写入自己的键且与 A 不同；**核心：A 重新登录后回到自己的上次会话**（首个取消息的会话=`b5c1f555`）；A 的键在 B 使用后仍未被改动 → **8 PASS / 0 FAIL**。
**剩余风险**：R1 键以 `user_id` 为准，若日后支持删除/重建用户，同 id 会继承旧键（概率极低，影响仅"默认打开哪个会话"，无越权风险）。R2 `localStorage` 被禁用时退化为"总是打开最近更新会话"（原有降级逻辑）。另：升级后首次进入聊天会回退到「最近更新」会话（**一次性**，因旧键不再读取）。

**B6 批次回归**：e2e3 → **42 PASS / 0 FAIL**。

---

## 7. B7（P2）SPEC v3.2 → v3.3 换版

### 7.1 问题
换版草稿（4 项修订）与实际交付之间存在**对不上**的地方，若原样发布，权威规格将与代码不符 —— 这比"不改规格"更危险。

### 7.2 对账与处理（逐条）
| 草稿项 | 处理 |
| --- | --- |
| 修订 1：Node 版本 | **实测揭穿自相矛盾**：原写"Node 22+"却给 `setup_20.x` 命令。服务器实际是 `/usr/local/bin/node` **v26.8.2** 生效，而 apt `nodejs` = 20.20.2（正是文档自己的 `setup_20.x` 装出来的）。→ 命令改 `setup_22.x`，并把修订说明改为陈述真实情况 |
| 修订 2：轮询间隔 | 按**实测分档**写入（通知 4s／聊天 4s／任务 5s／看板 8s／会话列表 8s），替换原"统一 30s"的口径 |
| 修订 3：头像 | 原修订被 **B4 的实际决策取代**（`public/avatar-placeholder.png`） |
| 修订 4：接口边界 | 补录 **6 条**（`PUT /api/me`、`POST /api/members/:id/disable`、`GET /api/profiles`、`GET /api/memories/suggest`、`POST /api/tasks/:id/approval`、`GET /api/health`） |
| 备查：login-token 注记 | 已被 **B3 作废**（登录不再回传 token） |
| **新增** | B5-① 的**重启恢复语义**写入 4.8 |

### 7.3 规格诚实性核验
- 修订 4 之外**未新增任何接口**；补录的 6 条**逐条回代码确认存在**后才写入（例如 `POST /api/logout`（`auth.js:102`，清 Cookie）、`PUT /api/me`（`auth.js:86`）、恢复时延 30s/60s（`tasks.js:444`、`455/469`、`index.js:30`））—— **不允许把没实现的接口写进权威规格**。
- 导出链路修正：`docx2spec.py` 原先**硬编码 v3.2**，换版易漏改生成头 → 改为**从源文件名解析版本号**。

### 7.4 验证证据
- 本地 `SPEC-v3.3.md`：**813 行 / 42263 B / sha256 `9b2805663408089c…`**；上传服务器后**两侧 sha256 一致**。
- 服务器 `/opt/team-console/SPEC.md` 由 v3.2 换为 v3.3；旧版备份 `SPEC.md.bak-s40b7-20260914-183733`（旧 sha 前 16 位 `3b78634418a4da35`）；diff `B7-SPEC换版.diff`（9117 B / 139 行，**仅预期行**）。
- **行号引用漂移**：插入内容使 112 行之后的引用全部位移 → 用**内容检索**重算（并用已知正确的 v3.2 数值 547/634/556 反向校验方法可靠）得 562/649/571，`sed` 同步 `profiles.js`（2 处）与 `auth.js`（1 处）注释；各有备份、diff `B7-行号引用同步.diff`（23 行），`node --check` 均通过。
- 回归 e2e3 → **42 PASS / 0 FAIL**。

### 7.5 剩余风险
- 行号引用同步只覆盖 3 处**代码注释**；`docs/` 下其余文档中的行号引用未逐一重排（B3 已在 §3.2 给出"登录后行号 +2~+4"的提示块）。**后续任何插入式改动都会再次引起漂移** —— 若要根治应改为按符号名引用而非行号。
- 换版后的 SPEC 语义（重启恢复）是"指令强约束 + 事后可见"，与 §5.1 剩余风险同源，规格中已如实写明。

---

## 8. B8（P1）验收残留清理

### 8.1 问题
阶段 3 验收在库里留下了大量测试痕迹：4 个测试账号、291 个任务（其中 **265 条**是 ACL 校验循环"校验-restricted-可选成员-正例"刷出来的）、292 条记忆、16 条资料库条目、8 个 `阶段3通知实测-*` 通知。这些在**界面可见**，会让业主把测试数据当成真实团队数据。同时《部署前置清单》的成员口径仍停留在"4 位成员/张三李四"的旧版。

### 8.2 清理前备份（一致性快照）
`/root/e2e/backups/s40-cleanup-20260914-20260914-184009/`（4.7 MB）：
- 三个库用 **`VACUUM INTO`** 取一致性快照（`conversations.db` 57344 B / `tasks.db` 1110016 B / `team-memory.db` 2797568 B）—— 避免直接拷 WAL 模式下的活库；
- `files.json`、`_opt_team-console_agents.json`；
- `产出.tar.gz`、`系统通知.tar.gz`、`上传目录.tar.gz`；
- `before-counts.txt`（**清理前基线**）、`manifest.sha256`、`rollback.sh`。

**清理前基线**：`users 5 / users_member 4 / conversations 4 / messages 24 / tasks 291 / outputs 284 / task_corrections 4 / memories 292 / files_json 16 / 产出目录 284 / 系统通知 16`。

### 8.3 清理动作与清理后终态
| 项 | 前 → 后 | 说明 |
| --- | --- | --- |
| 账号 | 5 → **1** | 保留 `admin`；删 `zhang`/`li`/`wang`/`uicheck` |
| 会话 / 消息 | 4 → 0 / 24 → 0 | 2 个 DM + 2 个「阶段3验收群-E2E*」 |
| 任务中心 | 291 → **0** | 其中 265 条为 ACL 校验循环产物 |
| 产出目录 | 284 → **2** | `t_375a1a5c`、`t_9769084a` 无对应任务，按**"不可归因即不删"**保留 |
| 记忆库 | 292 → **0** | **并单独清空 FTS 索引**（见 8.4-1） |
| 资料库 | 16 → **1** | 仅保留 `方案C-SPEC-v3.3.md`（42263 B，即本 SPEC 的 md 版，供团队随时查阅） |
| 系统通知 | 16 → 5 | 保留 `晨报-20260913/0914.md`、`周复盘-20260914.md`、`画像/`、`运维告警-20260914-1741.md`；删 8 个 `阶段3通知实测-*` 与 3 个 `任务恢复-*` |
| 画像快照 | 2 → 隔离 | 见 8.4-3 |
| 上传目录 | 清空 | 含我 B5 探针 `__s40_probe.txt` |

**终态复核（实测）**：`users=1  conversations=0  messages=0  tasks=0  outputs=0  task_corrections=0  memories=0  memory_fts=0  files.json=1  产出=2  系统通知=5  画像=2`；账号=`admin`；`/api/health`=200；8787 在听；journal 近 12 分钟 **0 条** error/throw。

### 8.4 复查中发现并解决的三个问题（**均由实测暴露，不是事后追述**）
1. **FTS 索引泄漏（真隐患）**：清理后 `memories=0` 但 **`memory_fts=292`** —— `memory_fts` 是**独立** FTS5 表（`fts5(memory_id UNINDEXED, …, tokenize='trigram')`，有自己的 `_content` 影子表），**不随 `memories` 级联删除**。不清它，**记忆搜索仍能搜出已删除的测试内容** —— 这是"naive 清理会照样上线"的典型漏洞。按应用自身惯用法处理（`db.exec('DELETE FROM memory_fts')`，与 `memories.js:58` 同源），并实测探针：搜「张策划」「私密标记」均返回 0。
2. **0 字节 `.db` 文件（我自己造成的）**：`/root/team-files/*.db` 有 3 个 0 字节文件、mtime 很新 —— 排查确认是**我自己**的巡检脚本用 `node:sqlite` 打开时自动创建的空文件（真实数据在 `/opt/team-console/data/`）。已删除并在报告中说明来龙去脉，避免被误读为"数据丢失"。
3. **画像 Tab 的旧世界快照（复查后端点的意外发现）**：`/api/profiles` 读的是 `~/team-files/系统通知/画像/*.json`，而当时那份 `画像-20260914.json` 是**清理前**生成的（含 4 个账号：`admin` + 3 个测试账号，叙述里满是 `ref1`/`阶段3`/`t_9769084a`/`校验-restricted`）。**删数据不等于删叙述** —— 若不清，管理员点开画像 Tab 看到的就是测试期的世界。
   **处理**：① 把旧快照（2 个 JSON + 其派生的 `待同步偏好-20260914-补跑1755.md`）**`mv`（不是 `rm`）** 到备份区 `quarantine-画像-旧快照/`，且**先逐个校验备份 tar 内确实存在**再动；② 按例行计划重跑画像作业（`hermes --profile zhiban cron run 367f1c9db36f`，`nohup` 后台、日志落盘）重建对照清理后数据的画像 —— 实测 `Ran now: succeeded.`，产出 `画像-20260914.json` 13571 B（成员=5 个 Agent + 1 位管理员，测试账号命中 **0**）。此举同时让 e2e3 的 3 条画像断言恢复通过。

### 8.5 验收
- **e2e3：41 PASS / 1 FAIL**。唯一 FAIL 为 `任务列表有历史任务`，其断言实为 `main.innerText().length > 200`；任务表清空后必然不满足，**属测试夹具假设而非缺陷** —— 已用专门探针实测该页正常渲染（含「发起任务」入口、空态「暂无任务」、**0 个 JS 错误**、innerText 40 字符，恰因数据清空而短）。**未修改任何测试用例**。清理前同版本代码为 **42 PASS / 0 FAIL**（即这 1 项 FAIL 完全由"数据被清空"解释）。
- **临时账号流程实测**：注册 `zhang`（预期 `pending`，返回 `注册成功，待管理员批准后可登录`）→ 管理员批准（`status=active`）→ 跑 e2e3 → 终扫。全部脚本：`s40-final-regression.sh`（**自带终扫，不留残留**）、`s40-final-sweep.sh`、`s40-postverify.sh`、`s40-residue-probe.sh`、`s40-empty-tasks.mjs`、`s40-profiles-tab.mjs`。
- **残留扫描（UI 实际调用的 7 个端点）**：`/api/members`、`/api/tasks`、`/api/conversations`、`/api/memories`、`/api/files`、`/api/poll` **残留=无**；`/api/profiles` 命中 `ref1 / 校验-restricted / 沙箱 / 阶段3` —— 见下方"唯一遗留项"。
- **清单与交底稿同步**：《部署前置清单-管理员操作》改为真实 3 人（**李倍旭＝管理员**；孙贤、吕静桐＝成员）、开通走「自助注册 → `pending` → 管理员批准」，并加"原「第 4 位测试账号」口径已作废"；docx 由 md 重新生成（`md2docx.py`，119 段 / 10 表 / 47339 B），实测 `张三`/`李四`/`4 位成员` 等旧口径**已全部消除**。
- **回滚（一条命令）**：`bash /root/e2e/backups/s40-cleanup-20260914-20260914-184009/rollback.sh` —— 恢复三库 + `files.json` + `agents.json`，`rm -f` 残留 `-wal/-shm`，解包三个 tar，重启服务，并打印计数与 `/api/health`。脚本注释已写明 **"服务正持有数据库文件句柄，覆盖后必须重启服务才会读到恢复的数据（本脚本已含重启）"**（这正是直接用 `VACUUM INTO` 快照覆盖活库的坑）。

### 8.6 剩余风险与有意未做的动作
1. **唯一遗留项**：`/api/profiles`（**管理员专属**视图，普通成员看不到）的画像叙述仍会提到 `ref1`/`校验-restricted`/`沙箱`/`阶段3`。原因：值班 Agent **自身的**历史（`/root/.hermes/profiles/zhiban/cron/output/`、`state.db`、Hermes 侧 `/root/.hermes/kanban.db`）记录过那段时期，而**这部分不在 B8 的清理范围**（B8 清的是团队数据）。**未做**的原因有二：① 越界 —— 那些是 Agent 的执行审计轨迹，其中多份正是 B2"作业补跑成功"的**证据本体**，删掉会破坏审计链；② 无必要 —— 其余 6 个端点零残留，且画像会随每日 06:00 例行重建逐步自然更替。若要连叙述也彻底干净：隔离值班 Agent 清理前的 cron 产物后再重跑一次画像作业。
2. **未做"实弹回滚演练"（有意）**：`rollback.sh` 已通过**语法检查（`bash -n`）**、**快照完整性核对**（与 `before-counts.txt` 逐项吻合）、**tar 内容清点**，但**没有**真跑一次恢复 —— 因为那会把刚验证干净的终态重新搅回"291 任务/292 记忆"的测试世界，再清理一遍既无新增证据又引入新风险。**该决定与理由如实记录在此**，请业主知悉：回滚脚本的正确性是"静态验证 + 备份可读"级别，未到"实跑过"级别。
3. **SQLite 空闲页残留**：`strings tasks.db/team-memory.db` 仍能 grep 到 `t_9769084a`/`ref1`/`阶段3` 之类的字节 —— 这是 SQLite 删除行后**不擦除已释放页**的正常行为，**权威判据是行级计数（全部为 0）**。若要物理擦除需 `VACUUM` 全库；本次**未做**（属可选加固，且需要停机窗口）。
4. 产出目录保留的 2 个孤儿目录（`t_375a1a5c`、`t_9769084a`）无对应任务、不可归因，按纪律**保留不删**。

---

## 9. 全局终态与回归

| 检查项 | 结果 |
| --- | --- |
| `team-console.service` | `active(running)`，`MainPID=313342`，`NRestarts=0` |
| `caddy` / `ops-check.timer` | 均 `active`；`ops-check.timer` 已 `enabled`，NEXT=`19:00:23` |
| 端口 | 8787 在听（`ss -lntp` 计数=1）；对外仍只有 80/443 走 Caddy |
| `/api/health` | 200 |
| journal | 近 12 分钟 error/throw/unhandled 计数 **0** |
| 磁盘 / 内存 | `/` 59G 用 12G（**21%**）；Mem 3722 MB 中 used 1111 MB、available 2612 MB |
| 密钥一致性 | **7/7 处**（含 `/etc/hermes.env`）长度=35、指纹 `<密钥指纹>` |
| 看门狗状态 | `issues: {}`（无未决异常），`last_run=2026-09-14 18:45:01` |
| 数据终态 | 账号 1（`admin`）、会话/消息/任务/产出/记忆/FTS 全 0、资料库 1、产出目录 2（孤儿）、通知 5 + 画像 2 |
| e2e3 回归 | **41 PASS / 1 FAIL**（唯一 FAIL 已定性为夹具假设，见 §8.5） |

**降级路径说明（域名未就绪）**：全程以自签证书走 `https://127.0.0.1` 验证（`curl -sk` / Playwright `ignoreHTTPSErrors`），**未做任何 IP 直连对外暴露**；对外 80/443 仍由 Caddy 持有，待备案与域名解析通过后换正式证书即可，无需改代码（B3 的 `Secure` 要求本就依赖 HTTPS，与降级路径一致）。

**边界声明（本次未触碰）**：未重跑 `hermes gateway install`；未卸载 tirith；未改动 `UMask=0077` drop-in；未碰决策清单第四节；未修改 e2e3 任何测试用例；未新增 SPEC「接口边界」清单外的后端 API。

---

## 10. 未完成项与剩余风险汇总

**未完成批次：无。** 八批全部落地并验证。以下为需要业主知悉/决策的事项，按性质分组（详细论证见对应章节）：

**A. 需业主决策（我不擅自实施的）**
1. 无状态 JWT 不随登出吊销 —— 退出后重放旧 Cookie 仍可用（§3.5-1）。根治需服务端会话/吊销名单或缩短 TTL。
2. `Secure` 与"http 直连应急"二选一（§3.5-2）；如需保留 http 回退可改为按请求协议条件设置。
3. 画像产物命名/结构不稳定（§2.4-1）：改 prompt 写死文件名，或改 `profiles.js` 取 mtime 最新。
4. 晨报要不要发邮件（§2.4-2）：需改作业 prompt。
5. 密钥托管与轮换周期制度（§2.4-4）。
6. 看门狗告警的**站外通道**（§1.4）：当前只有工作台内可见。
7. B5-① "不覆盖"是否需要**字节级快照兜底**（§5.1）。

**B. 已记录待后续观察（无需立即动作）**
8. 机房出网限制：`raw.githubusercontent.com` 不可达、`clawhub` 源阻塞 → 检索须显式 `--source`（§4.3）。
9. 崩溃循环限速后停在 `failed`，需人工 `reset-failed`（有 B1 兜底）（§5.2）。
10. `copytruncate` 毫秒窗口可能丢日志行；Caddy 升级后可改回 rename+postrotate（§5.3）。
11. 沙箱是纵深防御非边界；`PrivateTmp` 导致跨服务 `/tmp` 协作会静默失效；hermes 升级后写新路径会 EROFS（§5.4）。
12. 带点号的前端路由会被判为静态资源；`/favicon.ico` 仍 404 未补（§6.1）。
13. 同 id 重建用户会继承旧会话键（§6.3）。
14. 文档行号引用易漂移，建议改按符号名引用（§7.5）。
15. 画像叙述含旧对象名 + 2 个孤儿产出目录保留（§8.6-1、§8.6-4）+ SQLite 空闲页残留（§8.6-3）。
16. 用户头像槽位未做（范围外）、占位图纯灰（§4.3-4/5）。

---

## 11. 交付物与证据索引

**代码/配置（服务器）**
| 路径 | 批次 |
| --- | --- |
| `ops/ops-check.py`、`/etc/systemd/system/ops-check.{service,timer}` | B1 |
| `ops/rotate-deepseek-key.sh`、`/etc/hermes.env`（补键） | B2 |
| `server/src/auth.js` | B3 |
| `server/src/agents.js`、`server/src/registry.js`、`public/avatar-placeholder.png`、`src/views/SettingsView.vue` | B4 |
| `server/src/tasks.js`、`team-console.service.d/limits.conf`、`/etc/logrotate.d/caddy`、`team-console.service.d/sandbox.conf`（+ 启用 systemd-oomd） | B5 |
| `src/lib/notify.ts`、`src/views/ChatView.vue`、`server/src/index.js`、`/etc/caddy/Caddyfile` | B6 |
| `SPEC.md`（v3.3）、`server/src/profiles.js`+`auth.js`（行号注释） | B7 |
| 数据清理 + 清单口径收敛 | B8 |

**文档（服务器）**：`docs/前端开发者说明.md`、`docs/故障排查表.md`（附录 D/E + §6）、`HERMES.md`
**文档（本机）**：`方案C-最终Prompt-v3.3.docx`、`SPEC-v3.3.md`、`部署前置清单-管理员操作.md`/`.docx`、工具 `docx2spec.py` / `md2docx.py`、**本报告**
**证据**：`/root/e2e/s40-diffs/`（13 个 `.diff` + 19 个 `.txt`）、`/root/e2e/backups/`（全部 `.bak-s40*` + 白名单备份目录 + `quarantine-画像-旧快照/`）、`/root/e2e/shots/`（含 `s40-avatar-base.png`、`s40-avatar-override.png`、`13-tasks-empty.png`、`14-profiles-empty.png`）、`/root/e2e/s40-final-e2e3.txt`（最终 e2e3 全量输出）

---

## 12. 附：复现命令

```bash
# 健康与终态
ssh root@<服务器IP> 'curl -sk -o /dev/null -w "%{http_code}\n" https://127.0.0.1/api/health; systemctl is-active team-console caddy ops-check.timer'

# 运维看门狗（正常应零输出、rc=0；异常 rc=1 并在工作台出告警）
ssh root@<服务器IP> '/usr/bin/python3 /opt/team-console/ops/ops-check.py; echo rc=$?; cat /opt/team-console/ops/.ops-check-state.json'

# 密钥一致性（只输出长度与指纹，不回显密钥）
ssh root@<服务器IP> 'bash /opt/team-console/ops/rotate-deepseek-key.sh --check'

# 端到端回归（41 PASS / 1 FAIL；FAIL 为夹具假设，见 §8.5）
ssh root@<服务器IP> 'bash /root/e2e/s40-final-regression.sh'

# 界面残留扫描（7 个端点）
ssh root@<服务器IP> 'bash /root/e2e/s40-residue-probe.sh'

# 回滚到清理前（一条命令；含服务重启）
ssh root@<服务器IP> 'bash /root/e2e/backups/s40-cleanup-20260914-20260914-184009/rollback.sh'
```

---

*报告生成：2026-09-14 19:0x CST ｜ 执行：远程执行代理（Claude Code）｜ 权威规格：`/opt/team-console/SPEC.md`（v3.3）*
