# Session 4.0 · 加固改进包（P0–P2 全量）—— Claude Code 执行稿（合并版）

> **运行方式**：本机 Claude Code（同 S1-S3/S3.1 模式）：`cd D:\learn\saishi\chcz\CloudLoom` → `claude` → 粘贴下方【提示词】全文。
> （若你直接在服务器上跑 Claude，去掉提示词里的 `ssh` 前缀、本地执行即可，其余不变。）
> **前置**：S0–S3.1 已交付并通过独立复核（`reports/Session3-部署报告.md` §九、`reports/Session3.1-独立复核记录.md`）。
> **来源**：2026-09-14 助手实测复核产出的《方案C现状对照与待改进清单》（想法记录 2026-09-14）。
> **铁律**：最小改动 / 改前备份 / 留 diff / 每批回归 / 报告双端留档。**禁止用"已知问题"蒙混任何验收项。**
> **风险提示**：B3（登录安全）与 B5（systemd 沙箱）改动面大，审批时逐条细看；**B8（清场）建议等 S4 域名收尾完成后再跑**。

## 批次总览

| 批次 | 级别 | 内容 | 风险 |
|---|---|---|---|
| B1 | P0 | 运维看门狗：作业失败 + 余额 + 单元/端口/磁盘 → 自动系统通知（LLM 无关） | 低 |
| B2 | P0 | 三个定时作业手动触发验证 + 密钥位置收敛（轮换脚本 + 文档） | 低 |
| B3 | P1 | 登录安全：响应体移除 token、Cookie 加 Secure | **中高** |
| B4 | P1 | 技能安装链路（N1/T3）+ Agent 头像占位 | 低 |
| B5 | P2 | 稳定性四件：重启恢复语义、Restart 限流+告警、Caddy 日志轮转、oomd + 沙箱 | **高** |
| B6 | P2 | 前端细节：SPA 404、通知 primed 时机、会话记忆按用户隔离 | 中 |
| B7 | P2 | SPEC v3.3 换版（docx → 重导 SPEC.md → diff → 同步） | 中 |
| B8 | P1 | 启用前清场（测试数据清理 + 备份可回滚） | **中高（建议 S4 后）** |

---

## 【提示词】（粘贴全文）

```text
【任务：CloudLoom 加固改进包 S4.0 —— 把"待改进清单"逐项落地】

你是执行代理（Claude Code）。主路径：本机运行 + SSH 远程操作服务器
（ssh -o BatchMode=yes root@<服务器IP> '<命令>'，免密已配）；若你直接在服务器上运行，去掉 ssh 前缀、本地执行即可。

▍位置
· 项目根：/opt/team-console（服务器）
· 权威规格：/opt/team-console/SPEC.md（v3.2）。与本文冲突时以**本文**为准（本文是 S3/S3.1 之后的现实对齐）
· 现状基线：/opt/team-console/reports/Session3-部署报告.md（§九 遗留 C-1..C-14）、Session3.1-微修复报告.md、Session3.1-独立复核记录.md
· SPEC v3.3 草案：/opt/team-console/docs/SPEC-v3.3-微修订草案-20260914.md（B7 用它）
· 本机留档：D:\learn\saishi\chcz\CloudLoom\reports\（报告 scp 回来）

▍总纪律（沿用 S0–S3.1，违反即视为未完成）
1. 改前备份 → /root/e2e/backups/<文件>.bak-s40-<YYYYMMDD-HHMMSS>；每项留 diff → /root/e2e/s40-diffs/
2. 最小改动、加法优先；不重写既有模块、不扩散范围
3. 不重跑 hermes gateway install；不卸载 tirith；**不动 UMask=0077 drop-in**；不碰决策清单第四节
4. 密钥纪律：只进 .env / agents.json（600）；核验脚本只输出结论、**不回显密钥**；临时脚本跑完即删
5. 每批次：改完立即验证（/api/health=200、端口监听、journal 无新报错）+ 回归 e2e3.mjs（应 42 PASS / 0 FAIL）；失败先诊断修复，禁止静默跳过
6. 每批次产出报告章节（问题/改动/diff 摘要/验证证据/剩余风险），最终合并为 reports/Session4.0-加固改进报告.md 并 scp 回本机
7. 时间/上下文不足时：按批次交付，报告里明确"未完成批次"，**不要半成品落地**

════════ B1（P0）运维看门狗 ════════
【问题】2026-09-14 06:00 画像 / 09:00 晨报 / 10:00 周复盘 三个定时作业全部失败
（RuntimeError: HTTP 402: Insufficient Balance；证据 /root/.hermes/profiles/zhiban/cron/executions.db 三行 failed），
但 deliver=local → 完全静默，无人知晓。
【目标】"作业失败 / 余额不足 / 服务异常"能在 15 分钟内出现在工作台通知里，且不依赖 LLM。
【实现】
1. 新脚本 /opt/team-console/ops/ops-check.py（Python3 标准库），检查：
   a) zhiban 定时作业：executions.db 最近 6h 内 status=failed 的行（含 last_error 摘要）+ jobs.json 的 last_status
   b) DeepSeek 余额：用 /root/.hermes/.env 的 DEEPSEEK_API_KEY 调 https://api.deepseek.com/user/balance，total_balance < 5（可配）→ 告警
   c) 单元状态：team-console / caddy / hermes-gateway-{cehua,chengxu,pingshen,zhiban} 是否 active；team-console 是否 start-limit-hit
   d) 端口：80/443/3000/8787/8642-8645 是否监听
   e) 健康：http://127.0.0.1:8787/api/health 是否 200
   f) 磁盘：/ 使用率 > 85% → 告警
2. 告警只写"有异常"：输出 markdown 到 /root/team-files/系统通知/运维告警-<YYYYMMDD-HHMM>.md
   （含时间/项/证据/建议动作）；**正常时零输出**（沉默即正常）。用 /opt/team-console/ops/.ops-check-state.json
   去重：同一问题 6h 只告警一次，恢复后清状态。
3. 调度用 systemd timer（不依赖 Hermes）：ops-check.service + ops-check.timer，每 15 分钟，enable --now。
4. 验收：①手动跑一次 → 正常时零输出、无新通知文件 ②人为制造异常（临时把余额阈值调到 999）
   → 通知文件出现且内容正确 → 还原 ③systemctl list-timers 有下次触发、journal 有记录
   ④确认该 .md 能被工作台通知读到（前端轮询 8s）

════════ B2（P0）定时作业验证 + 密钥收敛 ════════
【问题 1】三个作业"到点自动跑成功"从未验证：历史成功的晨报均为人工 direct 触发；09-14 首次到点触发即因余额失败。
【要求】余额已由负责人充值（实测 ¥15.81、is_available=true，deepseek-chat/v4-flash/reasoner 均 200）。
逐一**手动触发**三个作业并验证产出（job_id 以 jobs.json 实读为准；晨报 44cf46376cff / 周复盘 ec6e303a9e33 / 画像 <实读>）：
   · 触发方式：zhiban profile 下的 hermes CLI（hermes cron list / run，以实际 --help 为准）
   · 验收：晨报 → /root/team-files/系统通知/晨报-<日期>.md + 邮件到达；周复盘 → 对应文件；
     画像 → 系统通知/画像/画像-<日期>.json（generated_at 正确）；executions.db 新行 completed + 耗时 + 文件大小
   · 失败则诊断到根因（模型/余额/权限/超时）并修复；09-15 09:00 的自动触发由助手次日复核
【问题 2】DeepSeek key 分散在 5 处，轮换必漏：/root/.hermes/.env + 4 个 profile .env；/etc/hermes.env 反而没有。
【要求】
   · 写 /opt/team-console/ops/rotate-deepseek-key.sh：接受新 key（参数或交互），备份后同步写入 5 处 .env（保持 600），
     重启相关单元，打印"改了哪几处 + 各单元健康检查"；**不回显 key 原文**
   · /etc/hermes.env 增加 DEEPSEEK_API_KEY 作单元层兜底（确认 unit 已引用 EnvironmentFile）；**不删除** profile .env
   · 更新《部署前置清单-管理员操作.md》+ HERMES.md：密钥位置清单 + 一条命令完成轮换
   · 验收：用当前 key 跑一次脚本（值不变）→ 5 处仍同 key（只比对长度/前缀）→ 单元 active + health 200 + 一次真实 chat 200

════════ B3（P1）登录安全 ════════
【问题】auth.js 登录响应体回传 token（JWT 可被 JS 读取，削弱 httpOnly 防 XSS 意图）；Cookie 缺 Secure。
【要求】
1. 先核查前端如何用登录结果（team-console/src/**：是否读 body.token / 存 localStorage / 发 Authorization 头）
2. 决策（已定，不再询问）：响应体**只返回 user 信息**；认证走 httpOnly Cookie（SameSite=Lax）**+ Secure**。
   若前端依赖 body token → 改纯 Cookie 模式并删除相关 localStorage 读写
3. Secure Cookie 仅 HTTPS 发送 → 验收必须走 https（Caddy 443 / 本机隧道 https://localhost:8443），
   不要用 http://127.0.0.1:3000 判断成败
4. 兼容：外部 MCP 客户端若曾依赖 body token → 改用 Cookie 或既有 mint 工具自铸 token；更新《前端开发者说明》认证段
5. 验收：登录 200 且响应体无 token 字段；Cookie 含 HttpOnly+Secure+SameSite；刷新页面仍在线（新增 1 条用例）；
   退出后数据面 401；e2e3 回归 42 PASS / 0 FAIL

════════ B4（P1）技能链路 + 头像占位 ════════
【问题 1】技能安装链路未通（N1/T3）：hermes skills search/install 静默返回空（exit 0 零输出），已排除纯网络原因。
【要求】诊断根因（子命令/注册表索引来源/代理/权限），给出**当前可用路径**并实测装 1 个示例技能：
   官方 CLI 可用则用官方；不可用则用本地路径安装（skills 目录 + SKILL.md 结构，hermes skills list 能列出即算通）。
   产出：可用路径写进 HERMES.md + 报告记录根因。验收：hermes skills list 可见 + 一次真实对话调用成功（附证据）
【问题 2】头像占位缺失：SPEC 提及的 assets/agents/placeholder.png 不存在，avatar 全链路 null，界面用 emoji 顶。
【要求】决策（已定）：**补占位图**。生成 128x128 素净灰底占位 PNG 放前端静态约定位置；
   avatar 为空时前端回退该图；agents.json 不改（保留管理员后续填 URL 能力）。
   验收：5 个 Agent 头像位均显示占位图（DOM/截图证据）+ 填真实 URL 能覆盖

════════ B5（P2）稳定性四件（⚠️ 沙箱部分高风险，逐条细看审批）════════
【问题 1】恢复逻辑无宽限期：服务重启即把在途任务重排重跑，可能与中断前重复执行（S3.1 实测反复出现）。
【要求】决策（已定）：**保留"重启即恢复"，但做到"可见 + 不覆盖"**：
   · 恢复时 progress 标注「系统重启后恢复（可能与中断前重复执行）」+ 写一条系统通知（任务 id/标题/负责 Agent）
   · 产物目录 ~/team-files/产出/<task_id>/；若目标文件已存在 → 新文件名追加 -retry-<HHMMSS>，**不覆盖既有产物**
   · 语义写进 SPEC v3.3（B7）与《故障排查表》
   · 验收：构造 running 任务 → 重启 team-console → 四条证据（重新排队 / 标注 / 系统通知 / 产物不覆盖）
【问题 2】Restart=always + StartLimitIntervalSec=0：连续崩溃会无限重启吃满 2 核（C-7）。
【要求】加限流：StartLimitIntervalSec=300、StartLimitBurst=10（可论证调整）；达限流后由 B1 看门狗检测并告警；
   偶发单次崩溃仍自动重启。验收：systemctl show 参数生效；kill 一次后自动回 active；reset-failed 并记录操作
【问题 3】Caddy 日志无轮转（C-11）。
【要求】加 /etc/logrotate.d/caddy（每日、保留 14 份、压缩）；logrotate -d 干跑通过 + -f 实跑一次验证产物
【问题 4】未装 systemd-oomd（C-4）；team-console 以 root 无沙箱（C-5）。
【要求】
   · 装并启用 systemd-oomd（apt + enable --now），确认 status 正常
   · 给 team-console.service 加**最小沙箱** drop-in（NoNewPrivileges=yes、PrivateTmp=yes、ProtectSystem=full、
     ProtectHome=read-only、ReadWritePaths=<按实际最小化>），**保留既有 UMask=0077 drop-in**
   · ⚠️ 改前备份 drop-in；改后立即验证 health=200 + 数据面读写（新建记忆 / 上传文件 / 发起任务）+ e2e3 回归；
     任何失败**立即回滚**并记录原因
   · 验收：systemctl show 参数符合预期 + 上述功能全绿

════════ B6（P2）前端细节 ════════
【问题 1】SPA fallback 吞未知路径（C-12）：/api/不存在 也返回首页。
【要求】只对非 /api、非静态资源的 GET 回退 index.html；/api/* 未匹配 → 404 JSON {"error":"not found"}；
   静态资源未匹配 → 404 文本。验收：curl 三条证据（/api/definitely-not-exist → 404 JSON；/no-such-page → 200 HTML；
   /assets/nope.js → 404）+ e2e3 回归
【问题 2】通知 primed 置位时机致旧通知被弹一次（C-3）。
【要求】首载把既有通知设为"已读基线"（不弹），只弹基线之后新增；刷新不重复弹。
   验收：清空状态 → 加载（不弹）→ 新增一条通知文件 → 8s 内弹出且红点 +1
【问题 3】会话记忆单浏览器全局一份，多成员共用一台设备会串（C-13 衍生）。
【要求】localStorage 键按当前用户隔离（如 cloudloom:<user_id>:lastConvId）。
   验收：同浏览器先 A 后 B 登录 → 各自回到自己上次会话；e2e3 回归

════════ B7（P2）SPEC v3.3 换版 ════════
【问题】3 处 SPEC 与实现不符 + 6 条超边界接口未追认（详见 docs/SPEC-v3.3-微修订草案-20260914.md）。
【要求】按草案**最小修订**：
   1. 源 docx：本机 D:\learn\saishi\chcz\CloudLoom\方案C-最终Prompt-v3.2.docx → 另存 v3.3（4 处修订 + 1 处备查注记），
      **其余内容零改动**（docx 可能被 Word 占用，先关闭；也可用 python-docx 改文本，同样要求 diff 最小）
   2. D:\learn\saishi\chcz\CloudLoom\docx2spec.py 重导出 SPEC.md → 与 v3.2 版 diff，确认只有预期行变化（diff 留档）
   3. 同步服务器 /opt/team-console/SPEC.md（先备份旧版）→ 服务器重转 diff = 0
   4. 验收：diff 只含预期行；服务器 SPEC.md 与重导出件一致；报告附 diff 摘要

════════ B8（P1，⚠️ 建议 S4 域名收尾完成后再执行；现在跑必须先备份）════════
【问题】验收残留：测试账号 uicheck（停用）、zhang/li/wang（测试成员）、12+ 测试任务、测试会话/文件、MCP 自检任务；
成员清单仍是占位（张三/李四/王五/赵六）。
【要求】
   1. 全量备份：conversations.db / tasks.db / team-memory.db（sqlite .backup 或 cp + sha256）+ agents.json +
      资料库上传目录 → /root/e2e/backups/s40-cleanup-<日期>/
   2. 清理：删除 uicheck 与测试成员（**保留 admin**）；删除明显测试任务（标题含 测试/自检/uicheck/阶段3 等
      或开发期样例）；删除测试会话与测试上传文件；MCP 自检任务按 S3 报告建议删除
   3. ⚠️ e2e3.mjs 的"成员视角"用例可能依赖 member 账号 → 若删除会破坏回归，则改为"停用 + 改名标注测试"并在报告说明
   4. 成员清单：更新《部署前置清单-管理员操作》为真实 3 人（负责人=管理员 / 成员B / 成员C），
      写明"成员自助注册 → 管理员在 设置→成员管理 批准"流程；同步 .docx
   5. 验收：清理前后对照表（数量 + 示例）+ 一条回滚命令 + e2e3 回归 42 PASS / 0 FAIL + 工作台界面无测试残留

▍交付
· 报告：/opt/team-console/reports/Session4.0-加固改进报告.md（按批次：问题/改动/diff 摘要/验证证据/剩余风险/未完成项），
  并 scp 回本机 D:\learn\saishi\chcz\CloudLoom\reports\
· 结束汇总：各批次结果 + 回归结果 + 剩余风险 + 待负责人决策项
· 完成后由助手做独立复核（同 S3/S3.1 标准：不上自述、直接实测；关键项由助手亲手复现）
```

## 附
- 单批次执行用分项版：`Session4.0-加固改进包-分项版.md`
- 来源分析：`D:\learn\saishi\chcz\想法记录\2026-09-14-方案C现状对照与待改进清单.md`
