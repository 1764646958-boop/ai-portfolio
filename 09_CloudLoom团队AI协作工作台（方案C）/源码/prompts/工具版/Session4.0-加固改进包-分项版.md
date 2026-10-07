# Session 4.0 · 加固改进包 —— 分项版（B1–B8 逐批粘贴）

> **用法**：每次只跑一批，把该批的代码块全文粘进 Claude（本机 `cd D:\learn\saishi\chcz\CloudLoom` → `claude`）。
> 建议顺序 B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8（B8 等 S4 域名收尾后再跑）。
> 完整版（一次跑全部）：`Session4.0-加固改进包-合并版.md`
> **审批策略**：常规文件/测试放行；systemd、对外端口、密钥、删除类逐条细看（B3/B5/B8 尤其）。

---

## 共用纪律（每批块里已内联，不必单独粘贴）

改前备份到 `/root/e2e/backups/<文件>.bak-s40-<时间戳>`；留 diff 到 `/root/e2e/s40-diffs/`；
最小改动、加法优先；不重跑 `hermes gateway install`、不卸载 tirith、**不动 UMask=0077 drop-in**；
密钥只进 `.env`（600）且**不回显**、临时脚本跑完即删；
每批改完立即验证（`/api/health`=200、端口监听、journal 无新报错）+ 回归 `e2e3.mjs`（应 **42 PASS / 0 FAIL**）；
报告章节落 `/opt/team-console/reports/Session4.0-加固改进报告.md` 并 scp 回本机 `reports\`。

---

## B1（P0）运维看门狗 —— 作业失败/余额/服务异常自动告警

```text
【任务：CloudLoom S4.0-B1 运维看门狗】
你是执行代理（Claude Code，本机 + SSH 远程：ssh -o BatchMode=yes root@<服务器IP> '<命令>'；若在服务器上跑则去掉 ssh 前缀）。
项目根 /opt/team-console；权威规格 /opt/team-console/SPEC.md。

背景：2026-09-14 06:00 画像 / 09:00 晨报 / 10:00 周复盘 三个定时作业全部失败
（RuntimeError: HTTP 402: Insufficient Balance，证据 /root/.hermes/profiles/zhiban/cron/executions.db），
但 deliver=local → 完全静默，无人知晓。目标：此类问题 15 分钟内出现在工作台通知里，且不依赖 LLM。

实现：
1. 新脚本 /opt/team-console/ops/ops-check.py（Python3 标准库）检查：
   a) zhiban 定时作业：executions.db 最近 6h 内 status=failed 行（含 last_error 摘要）+ jobs.json 的 last_status
   b) DeepSeek 余额：用 /root/.hermes/.env 的 DEEPSEEK_API_KEY 调 https://api.deepseek.com/user/balance，
      total_balance < 5（可配）→ 告警
   c) 单元：team-console / caddy / hermes-gateway-{cehua,chengxu,pingshen,zhiban} 是否 active；是否 start-limit-hit
   d) 端口：80/443/3000/8787/8642-8645 是否监听
   e) 健康：http://127.0.0.1:8787/api/health 是否 200
   f) 磁盘：/ 使用率 > 85%
2. 只有异常才输出：写 markdown 到 /root/team-files/系统通知/运维告警-<YYYYMMDD-HHMM>.md（时间/项/证据/建议动作）；
   正常时零输出。状态文件 /opt/team-console/ops/.ops-check-state.json 去重：同一问题 6h 只告警一次，恢复后清状态。
3. systemd timer 调度（不依赖 Hermes）：ops-check.service + ops-check.timer 每 15 分钟，enable --now。
4. 验收（逐条给证据）：①手动跑 → 正常时零输出且无新通知 ②临时把余额阈值调 999 制造异常 → 通知文件出现且内容正确
   → 还原 ③systemctl list-timers 有下次触发 + journal 有记录 ④确认该 .md 能被工作台通知读到（前端轮询 8s）

纪律：改前备份；diff 留档；不重跑 hermes gateway install；不卸 tirith；密钥不回显；
报告落 reports/Session4.0-加固改进报告.md（B1 段）并 scp 回本机。结束汇总结果。
```

---

## B2（P0）定时作业验证 + 密钥收敛

```text
【任务：CloudLoom S4.0-B2 定时作业验证 + DeepSeek 密钥收敛】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

问题 1：三个作业"到点自动跑成功"从未验证（历史成功均为人工 direct 触发；09-14 首次自动触发因余额失败）。
余额已充值（实测 ¥15.81、is_available=true；deepseek-chat/v4-flash/reasoner 均 200）。
要求：逐一**手动触发**三个作业并验证产出。job_id 以 /root/.hermes/profiles/zhiban/cron/jobs.json 实读为准
（晨报 44cf46376cff / 周复盘 ec6e303a9e33 / 画像 <实读>）；用 zhiban profile 的 hermes CLI 触发（cron list / run，以 --help 为准）。
验收：晨报 → /root/team-files/系统通知/晨报-<日期>.md + 邮件到达；周复盘 → 对应文件；
画像 → 系统通知/画像/画像-<日期>.json（generated_at 正确）；executions.db 新行 completed + 耗时 + 文件大小。
失败先诊断根因（模型/余额/权限/超时）并修复。

问题 2：DeepSeek key 分散 5 处，轮换必漏：/root/.hermes/.env + 4 个 profile .env；/etc/hermes.env 反而没有。
要求：
 · 写 /opt/team-console/ops/rotate-deepseek-key.sh：接受新 key（参数或交互），备份后同步写入 5 处 .env（600），
   重启相关单元，打印"改了哪几处 + 各单元健康检查"；不回显 key 原文
 · /etc/hermes.env 增加 DEEPSEEK_API_KEY 作单元层兜底（确认 unit 已引用 EnvironmentFile）；不删除 profile .env
 · 更新《部署前置清单-管理员操作.md》+ HERMES.md：密钥位置清单 + 一条命令轮换
 · 验收：用当前 key 跑一次脚本（值不变）→ 5 处仍同 key（只比对长度/前缀）→ 单元 active + health 200 + 真实 chat 200

纪律：最小改动；改前备份；diff 留档；密钥不回显；报告落 Session4.0-加固改进报告.md（B2 段）并 scp 回本机。
```

---

## B3（P1）登录安全（⚠️ 改动面大，审批逐条看）

```text
【任务：CloudLoom S4.0-B3 登录安全：响应体去 token + Cookie 加 Secure】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

问题：server/src/auth.js 登录响应体回传 token（JWT 可被 JS 读取，削弱 httpOnly 防 XSS 意图）；Cookie 缺 Secure。

要求：
1. 先核查前端如何使用登录结果（team-console/src/**：是否读 body.token / 存 localStorage / 发 Authorization 头），把结论写进报告。
2. 决策（已定，不再询问）：响应体**只返回 user 信息，不返回 token**；认证走 httpOnly Cookie（SameSite=Lax）+ **Secure**。
   若前端依赖 body token → 改为纯 Cookie 模式并删除相关 localStorage 读写。
3. Secure Cookie 仅在 HTTPS 发送 → 验收必须走 https（Caddy 443 / 本机隧道 https://localhost:8443），
   不要用 http://127.0.0.1:3000 判断成败。
4. 兼容：外部 MCP 客户端若曾依赖 body token → 改用 Cookie 或既有 mint 工具自铸；更新《前端开发者说明》认证段。
5. 验收：登录 200 且响应体**无 token 字段**；Cookie 含 HttpOnly+Secure+SameSite；刷新页面仍在线（新增 1 条用例）；
   退出后数据面 401；**e2e3 回归 42 PASS / 0 FAIL**。

纪律：改前备份；diff 留档；不重跑 hermes gateway install；不卸 tirith；密钥不回显；
报告落 Session4.0-加固改进报告.md（B3 段）并 scp 回本机。
```

---

## B4（P1）技能安装链路 + Agent 头像占位

```text
【任务：CloudLoom S4.0-B4 技能链路（N1/T3）+ 头像占位】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

问题 1：技能安装链路未通（SPEC 执行步骤 N1）：hermes skills search/install 静默返回空（exit 0 零输出），已排除纯网络原因。
要求：诊断根因（子命令/注册表索引来源/代理/权限），给出**当前可用路径**并实测装 1 个示例技能：
 官方 CLI 可用则用官方；不可用则用本地路径安装（skills 目录 + SKILL.md 结构，hermes skills list 能列出即算通）。
 产出：可用路径写进 HERMES.md + 报告记录根因。验收：hermes skills list 可见 + 一次真实对话调用成功（附证据）。

问题 2：头像占位缺失：SPEC 提及的 assets/agents/placeholder.png 不存在，avatar 全链路 null，界面用 emoji 顶。
要求：决策（已定）**补占位图**：生成 128x128 素净灰底占位 PNG 放前端静态约定位置；avatar 为空时前端回退该图；
 agents.json 不改（保留管理员后续填 URL 能力）。验收：5 个 Agent 头像位均显示占位图（DOM/截图证据）+ 填真实 URL 能覆盖。

纪律：改前备份；diff 留档；前端改动后 vue-tsc -b && vite build 必须 0；e2e3 回归 42 PASS / 0 FAIL；
报告落 Session4.0-加固改进报告.md（B4 段）并 scp 回本机。
```

---

## B5（P2）稳定性四件（⚠️ 沙箱高风险）

```text
【任务：CloudLoom S4.0-B5 稳定性四件套】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

问题 1：恢复逻辑无宽限期：服务重启即把在途任务重排重跑，可能与中断前重复执行（S3.1 实测反复出现）。
要求：决策（已定）**保留"重启即恢复"，但做到"可见 + 不覆盖"**：
 · 恢复时 progress 标注「系统重启后恢复（可能与中断前重复执行）」+ 写一条系统通知（任务 id/标题/负责 Agent）
 · 产物目录 ~/team-files/产出/<task_id>/；目标文件已存在 → 新文件名追加 -retry-<HHMMSS>，**不覆盖既有产物**
 · 语义写进 SPEC v3.3（见 B7）与《故障排查表》
 · 验收：构造 running 任务 → 重启 team-console → 四条证据（重新排队 / 标注 / 系统通知 / 产物不覆盖）

问题 2：Restart=always + StartLimitIntervalSec=0：连续崩溃会无限重启吃满 2 核（C-7）。
要求：加限流 StartLimitIntervalSec=300、StartLimitBurst=10（可论证调整）；达限流后由 B1 看门狗检测告警；
 偶发单次崩溃仍自动重启。验收：systemctl show 参数生效；kill 一次后自动回 active；reset-failed 并记录操作。

问题 3：Caddy 日志无轮转（C-11）。要求：加 /etc/logrotate.d/caddy（每日、保留 14 份、压缩）；
 logrotate -d 干跑通过 + -f 实跑一次验证产物。

问题 4：未装 systemd-oomd（C-4）；team-console 以 root 无沙箱（C-5）。
要求：
 · 装并启用 systemd-oomd（apt + enable --now），确认 status 正常
 · 给 team-console.service 加**最小沙箱** drop-in（NoNewPrivileges=yes、PrivateTmp=yes、ProtectSystem=full、
   ProtectHome=read-only、ReadWritePaths=<按实际最小化>），**保留既有 UMask=0077 drop-in**
 · ⚠️ 改前备份 drop-in；改后立即验证 health=200 + 数据面读写（新建记忆 / 上传文件 / 发起任务）+ e2e3 回归；
   任何失败**立即回滚**并记录原因
 · 验收：systemctl show 参数符合预期 + 上述功能全绿

纪律：改前备份；diff 留档；报告落 Session4.0-加固改进报告.md（B5 段）并 scp 回本机。
```

---

## B6（P2）前端细节

```text
【任务：CloudLoom S4.0-B6 前端细节三件】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

问题 1（C-12）：SPA fallback 吞未知路径：/api/不存在 也返回首页。
要求：只对非 /api、非静态资源的 GET 回退 index.html；/api/* 未匹配 → 404 JSON {"error":"not found"}；
 静态资源未匹配 → 404 文本。验收：curl 三条证据（/api/definitely-not-exist → 404 JSON；/no-such-page → 200 HTML；
 /assets/nope.js → 404）+ e2e3 回归。

问题 2（C-3）：通知 primed 置位时机致旧通知被弹一次。
要求：首载把既有通知设为"已读基线"（不弹），只弹基线之后新增；刷新不重复弹。
 验收：清空状态 → 加载（不弹）→ 新增一条通知文件 → 8s 内弹出且红点 +1。

问题 3（C-13 衍生）：会话记忆单浏览器全局一份，多成员共用一台设备会串。
要求：localStorage 键按用户隔离（如 cloudloom:<user_id>:lastConvId）。
 验收：同浏览器先 A 后 B 登录 → 各自回到自己上次会话；e2e3 回归。

纪律：前端改动后 vue-tsc -b && vite build 必须 0（dist 由 Caddy 托管，构建物时间须晚于改动）；
 改前备份；diff 留档；报告落 Session4.0-加固改进报告.md（B6 段）并 scp 回本机。
```

---

## B7（P2）SPEC v3.3 换版

```text
【任务：CloudLoom S4.0-B7 SPEC v3.3 换版】
你是执行代理（Claude Code；本机文件 + SSH 同步服务器）。项目根（服务器）/opt/team-console；本机 D:\learn\saishi\chcz\CloudLoom。

问题：3 处 SPEC 与实现不符 + 6 条超边界接口未追认，依据 /opt/team-console/docs/SPEC-v3.3-微修订草案-20260914.md。
要求（最小修订）：
1. 源 docx：D:\learn\saishi\chcz\CloudLoom\方案C-最终Prompt-v3.2.docx → 另存 v3.3（4 处修订 + 1 处备查注记），
   **其余内容零改动**（docx 可能被 Word 占用 → 先关闭；也可用 python-docx 改文本，同样要求 diff 最小）
2. 用 D:\learn\saishi\chcz\CloudLoom\docx2spec.py 重导出 SPEC.md → 与 v3.2 版 diff，确认只有预期行变化（diff 留档）
3. 同步服务器 /opt/team-console/SPEC.md（先备份旧版）→ 服务器重转 diff = 0
4. 验收：diff 只含预期行；服务器 SPEC.md 与重导出件一致；报告附 diff 摘要

纪律：diff 留档；报告落 Session4.0-加固改进报告.md（B7 段）并 scp 回本机。
```

---

## B8（P1，⚠️ 建议 S4 域名收尾完成后再跑；现在跑必须先备份）

```text
【任务：CloudLoom S4.0-B8 启用前清场】
你是执行代理（Claude Code，本机 + SSH 远程 root@<服务器IP>；若在服务器上跑则去 ssh 前缀）。项目根 /opt/team-console。

问题：验收残留：测试账号 uicheck（停用）、zhang/li/wang（测试成员）、12+ 测试任务、测试会话/文件、MCP 自检任务；
成员清单仍是占位（张三/李四/王五/赵六）。

要求：
1. 全量备份：conversations.db / tasks.db / team-memory.db（sqlite .backup 或 cp + sha256）+ agents.json +
   资料库上传目录 → /root/e2e/backups/s40-cleanup-<日期>/
2. 清理：删除 uicheck 与测试成员（**保留 admin**）；删除明显测试任务（标题含 测试/自检/uicheck/阶段3 或开发期样例）；
   删除测试会话与测试上传文件；MCP 自检任务按 S3 报告建议删除
3. ⚠️ e2e3.mjs 的"成员视角"用例可能依赖 member 账号 → 若删除会破坏回归，则改为"停用 + 改名标注测试"并在报告说明
4. 成员清单：更新《部署前置清单-管理员操作》为真实 3 人（负责人=管理员 / 成员B / 成员C），
   写明"成员自助注册 → 管理员在 设置→成员管理 批准"流程；同步 .docx
5. 验收：清理前后对照表（数量 + 示例）+ 一条回滚命令 + **e2e3 回归 42 PASS / 0 FAIL** + 工作台界面无测试残留

纪律：删除类操作逐条细看；改前备份；报告落 Session4.0-加固改进报告.md（B8 段）并 scp 回本机。
```

---

## 跑完的交接

把 Claude 的汇总发出来 → 助手按 S3/S3.1 标准做**独立复核**（不上自述、直接实测；B1 看门狗会由助手亲手制造一次异常验证、B3 登录会走隧道实测）。
