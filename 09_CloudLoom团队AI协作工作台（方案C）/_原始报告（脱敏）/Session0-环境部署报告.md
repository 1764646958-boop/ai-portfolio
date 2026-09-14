> 📄 **作品集展示副本（已脱敏）**：服务器地址 / 主机名 / 域名 / 邮箱 / 凭据 / 令牌均已替换为占位符；
> 完整原报告不随作品集仓库分发。指标与结论未作任何修改。

# Session 0 · 环境与基础设施 —— 部署报告

| 项目 | 内容 |
|---|---|
| 团队 | 楚华成章 |
| 项目代号 | CloudLoom（方案 C） |
| 批次 | Session 0 · 环境与基础设施 |
| 执行日期 | 2026-09-13 |
| 服务器 | `root@<服务器IP>`（腾讯云 CVM · Ubuntu 24.04 LTS · 2 核 4G · 60GB SSD） |
| 工作目录 | `/opt/team-console` |
| 状态 | **主体完成**；2 项挂起、2 项延期，详见第 6 节 |

> 本报告所有结论均来自服务器实测输出，未作推测或美化。凡未能验证的项一律显式标注，未用「应该可以」代替证据。

---

## 1. 基础信息

### 1.1 服务器与运行时

| 项 | 值 |
|---|---|
| 公网 IP | `<服务器IP>` |
| 主机名 | `<主机名>` |
| 内网 IP | `10.10.4.12`（NAT 之后，公网访问需经腾讯云 EIP） |
| 系统 | Ubuntu 24.04 LTS |
| 规格 | 2 vCPU / 3.6 GiB 可用内存 / 60 GB 系统盘 |
| 磁盘占用 | 已用 15%（59G 中 49G 可用） |
| Docker | 29.6.1（本批次未使用容器，全部为 systemd 原生部署） |

### 1.2 域名状态 —— ⚠️ 未就绪

| 项 | 值 |
|---|---|
| 域名 | `<团队域名>` |
| 命名审核 / 实名 / 备案 | **均未就绪** |
| 是否可解析 | **否** |
| 影响 | 无法完成 ACME HTTP-01 质询 → 正式证书无法签发 → **验收项 5（`https://域名`）延期补做** |

按执行稿要求，本批次走 **降级路径**：IP + 自签证书，已实测可用（见第 5 节）。**该降级不得阻塞交接。**

### 1.3 Hermes 与模型

| 项 | 值 |
|---|---|
| Hermes 版本 | **v0.19.0（2026.7.20）** |
| 安装路径 | `/usr/local/lib/hermes-agent` |
| 启动器 | `/usr/local/bin/hermes` |
| 模型 provider | `deepseek` |
| base_url | `https://api.deepseek.com` |
| 默认模型 | `deepseek-chat` |
| 真实 LLM 往返 | ✅ 已验证（返回 "OK"，耗时约 6 秒） |

> **供应链说明**：部署期间 `github.com:443` 在本网络被 TCP 层阻断（所有候选 IP 精确 8.000 秒超时）。故 Hermes 通过 **PyPI 官方 sdist 播种**（SHA256 `ac986bede64a2785436676c0ea084ec586574f8cb00a9d047e095b435d3e21c0`，对应上游 tag `v2026.7.20` / commit `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`），缺失的两个文件经 `api.github.com` 获取并**逐字节校验 git blob SHA**。全程未使用任何非官方镜像或未校验来源。

### 1.4 四个 Agent Profile 的 API Server

| Profile | 端口 | `API_SERVER_KEY`（脱敏） | 监听地址 |
|---|---|---|---|
| `cehua` | 8642 | `7b2b****`（长度 48） | `127.0.0.1` |
| `chengxu` | 8643 | `f93b****`（长度 48） | `127.0.0.1` |
| `pingshen` | 8644 | `a65f****`（长度 48） | `127.0.0.1` |
| `zhiban` | 8645 | `c344****`（长度 48） | `127.0.0.1` |

- 密钥由 `openssl rand -hex 24` 生成，每个 profile 独立，**互不相同**。
- **完整密钥存放于 `/opt/team-console/agents.json`（权限 `600`，仅 root 可读）**，不在本报告中明文出现。
- 四个端口**仅绑定 `127.0.0.1`**，未暴露公网 —— 外部调用需经 Caddy 或 SSH 隧道。
- 四个 `/health` 均返回 `{"status": "ok", "platform": "hermes-agent", "version": "0.19.0"}`。

---

## 2. Profile 拼音 ↔ 显示名对照表

| 拼音标识 | 显示名 | 职责范围 | 端口 | SOUL.md 行数 |
|---|---|---|---|---|
| `cehua` | 策划 Agent | 世界观、剧情、数值 | 8642 | 58 |
| `chengxu` | 程序 Agent | 架构设计、代码实现、技术评审 | 8643 | 58 |
| `pingshen` | 评审 Agent | 独立只读审查（**只评判不动手**） | 8644 | 78 |
| `zhiban` | 值班 Agent | 晨报、周复盘、阻塞提醒、催办、D36 复核兜底 | 8645 | 86 |

> ⚠️ 拼写固定为 **`cehua`**（不是 `ceihua` / `cehuA`），所有脚本、systemd 单元、Kanban 指派均以此为准。

### 2.1 SOUL.md 人格与行为边界（D34）核对

四份 SOUL.md 均已覆盖，**每份含且仅含 1 个【行为边界】小节，四处子节全部齐备**：

| Profile | 【行为边界】 | 可自主 | 需升级人审 | 禁止 | 失败兜底 |
|---|---|---|---|---|---|
| `cehua` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `chengxu` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `pingshen` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `zhiban` | ✅ | ✅ | ✅ | ✅ | ✅ |

- 四类边界内容互不雷同，均按各自角色定制（如 `pingshen` 的「禁止」首条为「修改被审查对象」，`zhiban` 的「失败兜底」首条为 N3 双通道降级）。
- D17 审批节点（设计定稿 / 预算 / 对外承诺）、D36 强制项（删除数据 / 低置信复核）在四份文档中均有落点。
- **已验证人格生效**：`hermes -p cehua` 被问「介绍你的职责」时，准确复述策划职责三方向与 6 条工作规矩，零默认人格残留。

---

## 3. systemd 单元清单

| 单元 | 状态 | 说明 |
|---|---|---|
| `caddy.service` | enabled / active | HTTPS 终止与反向代理 |
| `hermes-gateway-cehua.service` | enabled / active | 策划 Agent 网关 |
| `hermes-gateway-chengxu.service` | enabled / active | 程序 Agent 网关 |
| `hermes-gateway-pingshen.service` | enabled / active | 评审 Agent 网关 |
| `hermes-gateway-zhiban.service` | enabled / active | 值班 Agent 网关（承载 cron 调度） |

### 3.1 单元关键参数

- `User=root`（按 SPEC 要求，全会话以 root 运行；Hermes 安全审计会就此告警，属预期）
- `Restart=always`
- `WantedBy=multi-user.target`
- `Environment="HERMES_HOME=/root/.hermes/profiles/<profile>"`
- `ExecStart=/usr/local/lib/hermes-agent/venv/bin/python -m hermes_cli.main --profile <profile> gateway run`

### 3.2 配置持久化设计（重要）

四个网关的共享环境**不使用命令行内联**，而是通过 **systemd drop-in** 注入：

```
/etc/systemd/system/hermes-gateway-{cehua,chengxu,pingshen,zhiban}.service.d/10-cloudloom-env.conf
```

```ini
# CloudLoom (B3): shared environment, Kanban board path shared across profiles
[Service]
EnvironmentFile=/etc/hermes.env
```

**为什么这样做**：Hermes 的 `gateway install` 在重新生成单元时会覆盖主单元文件。把共享变量放进 drop-in，可在服务重新生成后依然保留，避免 Kanban 共享看板路径丢失。

---

## 4. cron、Kanban、环境变量与技能

### 4.1 cron 任务（3 个，全部 active）

| Job ID | 名称 | Cron 表达式 | 含义 | 下次运行 |
|---|---|---|---|---|
| `44cf46376cff` | 晨报 | `0 9 * * *` | 每日 09:00 | 2026-09-14 09:00 |
| `367f1c9db36f` | 画像 | `0 6 * * *` | 每日 06:00 | 2026-09-14 06:00 |
| `ec6e303a9e33` | 周复盘 | `0 10 * * 1` | 每周一 10:00 | 2026-09-14 10:00（周一） |

- `Deliver: local`，`Repeat: ∞`，全部挂在 `zhiban` profile 下。
- 调度器心跳正常（实测 `Ticker heartbeat: 8s ago`，`No jobs due` 判定准确）。
- **手动触发实测**：晨报 job 于 2026-09-13 17:20:50 手动触发，17:22:26 完成，状态 `completed`（run id `1a3e461bf2644f70a882d7a2526c37a0`）。

### 4.2 Kanban 共享看板

| 项 | 值 |
|---|---|
| 看板文件 | `/root/.hermes/kanban.db` |
| 共享方式 | `HERMES_KANBAN_BOARD=/root/.hermes/kanban.db`（经 `/etc/hermes.env` 注入全部 4 个 profile） |
| 初始任务 | 4 个 |

| 任务 ID | 状态 | 指派 | 标题 |
|---|---|---|---|
| `t_6df43027` | blocked | `cehua` | 剧情系统设计 |
| `t_00398c3e` | blocked | `pingshen` | 美术规范 |
| `t_375a1a5c` | blocked | `chengxu` | 对话框架 |
| `t_9769084a` | blocked | `cehua` | 数值表V2 |

> `hermes kanban list` 可见全部 4 个初始任务（验收项 3 ✅）。
> 4 张卡被 `zhiban` 晨报判为 blocked 属**真实状态**：项目基准设定（题材/主线/主角/玩法/分支深度）尚未提供，属既知的上游输入缺失，非部署缺陷。

### 4.3 环境变量

**`/root/.hermes/.env`** —— 已配置的键（**仅列键名，不列值**）：

| 键 | 用途 |
|---|---|
| `DEEPSEEK_API_KEY` | 真实 LLM 密钥（由管理员预置，本批次**未编造**） |
| `EMAIL_SMTP_HOST` | SMTP 主机 |
| `EMAIL_SMTP_PORT` | SMTP 端口（465） |
| `EMAIL_ADDRESS` | 邮箱地址 |
| `EMAIL_PASSWORD` | 邮箱授权码 |

**`/etc/hermes.env`** —— 共享环境（四个网关经 drop-in 加载）：

```
# CloudLoom shared environment for all Hermes profile gateways
# Kanban is shared across profiles (C1) — fixed board path.
HERMES_KANBAN_BOARD=/root/.hermes/kanban.db
```

### 4.4 技能

| 项 | 值 |
|---|---|
| 已启用技能 | **70 个**（全部 builtin，状态 enabled） |
| 涵盖类别 | autonomous-ai-agents / creative / data-science / email / productivity 等 |
| 触发链路 | ✅ **已验证**（见下） |

**触发链路验证（SPEC:677）**：向 `chengxu` 提问要求使用 `architecture-diagram` 技能，该 Agent 准确复述了技能的**强制四段式结构**、`skill_view templates/template.html` 步骤，以及「boundary 最大 Y 与 legend Y 差值 ≥ 20px」「除 Google Fonts 外不引用外部资源」「无 `<script>`」等**具体约束**——证明技能已实际加载并生效，非泛泛而谈。

> ⚠️ **技能注册表检索/安装链路不可用**：`hermes skills search <任意词>` 与 `hermes skills inspect <identifier>` 均**静默返回空结果（exit 0 但零输出）**，涉及 `skills.sh` / ClawHub / `api.github.com` 多条路径。`skills.sh`（308, 0.34s）与 `clawhub.ai`（200, 2.28s）本身可达，故判断为 Hermes 技能中心在该版本/网络组合下未返回结果，而非纯网络阻断。**影响：本批次无法通过 `search/install` 安装示例技能，只能验证「列表可见 + 提问触发」两条**。详见第 6 节待办 T3。

---

## 5. 重启自检结果

### 5.1 测试方法

记录重启前基线 → 下发 `/sbin/reboot` → 轮询 SSH 恢复 → 逐项核验服务、端口、持久化数据。

### 5.2 结果 —— ✅ **通过**

| 检查项 | 结果 |
|---|---|
| 服务器启动时刻 | 2026-09-13 17:51:24 |
| SSH 恢复 | 30 秒内 |
| `caddy` 自动恢复 | ✅ active，启动于 17:51:34（**开机后 10 秒**） |
| `hermes-gateway-cehua` | ✅ active，启动于 17:51:33（**开机后 9 秒**） |
| `hermes-gateway-chengxu` | ✅ active，启动于 17:51:33 |
| `hermes-gateway-pingshen` | ✅ active，启动于 17:51:33 |
| `hermes-gateway-zhiban` | ✅ active，启动于 17:51:33 |
| 端口 `8642-8645` | ✅ 全部监听 `127.0.0.1` |
| 端口 `443` / `80` | ✅ 全部监听 |
| 4 个 `/health` | ✅ 全部返回 `{"status":"ok", ...}` |
| HTTPS 降级路径 | ✅ `https://127.0.0.1/` 返回 502（TLS 正常，上游占位缺位，属预期） |
| Kanban 数据 | ✅ 4 张卡完好 |
| cron 任务 | ✅ 3 个完好，下次运行时间正确 |

**结论：无需人工干预，重启后 10 秒内全部服务自动恢复（验收项 6 ✅）。**

### 5.3 HTTPS 降级路径细节

| 项 | 值 |
|---|---|
| Caddy 版本 | 2.6.2（来自 `mirrors.tencentyun.com` Ubuntu 源，未依赖 GitHub） |
| 站点地址 | `:443`（端口兜底站点，任意 Host / 无 SNI 均可命中） |
| 证书 | 自签，`/etc/caddy/certs/cloudloom.crt` |
| 证书 SAN | `IP:<服务器IP>`、`IP:127.0.0.1`、`DNS:localhost`、`DNS:<团队域名>` |
| 证书指纹 (SHA256) | `C1:80:FF:4C:05:7E:38:FB:F4:C4:33:9F:64:BC:78:5F:7F:E9:EF:47:99:C8:FA:89:08:43:41:5F:14:7A:86:F7` |
| 有效期 | 至 2028-12-16 |
| 反向代理 | `/api/*` → `127.0.0.1:8787`；其余 → `127.0.0.1:3000` |
| 80→443 跳转 | ✅ 返回 308 |
| 实测 | `curl -k https://127.0.0.1/` → **502**（TLS 握手成功；502 = 占位上游无进程监听，**属预期**） |

> **为什么用 `:443` 而不是 `https://<服务器IP>`**：RFC 6066 规定 SNI 不能是 IP 字面量，浏览器与 curl 用 IP 访问时**根本不发 SNI**。Caddy 2.6 无 `default_sni` 选项（该选项 2.7+ 才有），IP 站点在无 SNI 时以 `TLS alert internal error` 拒绝握手。改用端口兜底站点 + 显式自签证书后，任意 Host 均可正常访问。

---

## 6. 验收结论

| # | 验收项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 4 个端口 `/health` 全部返回 ok | ✅ **通过** | 4/4 返回 `{"status":"ok",...}`，重启后复测仍通过 |
| 2 | `hermes -p cehua` 返回策划人格 | ✅ **通过** | 准确复述职责三方向 + 6 条工作规矩，零默认人格残留 |
| 3 | `hermes kanban list` 可见 4 个初始任务 | ✅ **通过** | 4 张卡全部可见，重启后完好 |
| 4 | 手动触发晨报 cron：生成文件 + 收到邮件 | ⚠️ **部分通过** | **文件 ✅**（`晨报-20260913.md`，4215 字节）；**邮件 ⏸ 挂起**（见 T2） |
| 5 | `https://域名` 可访问 | ⏳ **延期补做** | 域名备案未就绪，不可解析；降级路径已实测可用 |
| 6 | `reboot` 后 caddy + 4 gateway 自动恢复 | ✅ **通过** | 开机后 9-10 秒全部恢复，无人工干预 |
| 7 | 输出《环境部署报告》 | ✅ **通过** | 本文件 |

**总计：5 项通过，1 项部分通过，1 项延期。**

### 6.1 验收项 4 详情

**文件通道（✅ 已达成）**：

- 路径：`/root/team-files/系统通知/晨报-20260913.md`
- 大小：4215 字节
- 内容质量：真实反映看板状态，**明确写出「4 张卡全部 blocked，0 进行中、0 完成」并声明「本报告不美化进度」** —— 符合 `zhiban` SOUL.md「告知而非美化」原则。
- 每项结论均可追溯至具体任务 ID 与文件路径。

**邮件通道（⏸ 挂起）**：

- 根因：Hermes 邮件平台的启用条件为 `all([EMAIL_ADDRESS, EMAIL_PASSWORD, EMAIL_IMAP_HOST, EMAIL_SMTP_HOST])`（`plugins/platforms/email/adapter.py:165` 注释明写「缺项则不启用平台」）。当前 `.env` 只有 4 个 SMTP 项，**缺 `EMAIL_IMAP_HOST`**。
- 处理：按执行稿「缺则邮件验证挂起、报告列为待办」的规则处理，**未编造未提供的配置值**。
- 修复方式见 T2。

---

## 7. 延后项清单（Delayed / Deferred）

### T1 · 正式 HTTPS 证书签发与 `https://域名` 验收 —— ⏳ 延期补做

| 项 | 内容 |
|---|---|
| 阻塞原因 | `<团队域名>` 命名审核 / 实名 / 备案未就绪，当前不可解析，无法完成 ACME HTTP-01 质询 |
| 当前替代 | IP + 自签证书降级路径，已实测可用 |
| 域名就绪后操作 | 编辑 `/etc/caddy/Caddyfile`：把站点地址 `:443` 改为 `<团队域名>`，并把 `tls /etc/caddy/certs/cloudloom.crt /etc/caddy/certs/cloudloom.key` 一行**删除**（删掉后 Caddy 会自动向 Let's Encrypt 申请正式证书）。其余反代规则不变。然后 `systemctl reload caddy`。 |
| 验收 | `curl -I https://<团队域名>` 返回 200/502 且证书链可信（不带 `-k`） |

### T2 · 邮件通道 —— ⏸ 挂起（缺 1 项配置）

| 项 | 内容 |
|---|---|
| 阻塞原因 | 缺 `EMAIL_IMAP_HOST`，Hermes 邮件平台未启用 |
| 为何不代填 | 邮箱为 QQ（`EMAIL_SMTP_HOST=smtp.qq.com`），对应 IMAP 主机虽为 `imap.qq.com` 这一标准配对，但该值**用户未提供**；且启用后邮件适配器会**轮询用户收件箱并将邮件线程交给 Agent 处理与回复**，属超出「只发晨报邮件」的范围，需用户知情后决定 |
| 修复方式 | 在 `/root/.hermes/.env` 追加一行 `EMAIL_IMAP_HOST=imap.qq.com`，然后 `systemctl restart hermes-gateway-{cehua,chengxu,pingshen,zhiban}` |
| 复验方式 | `hermes -p zhiban cron run 44cf46376cff`，确认邮箱收到晨报 |
| 备选方案 | 若**只需出站发信、不希望 Agent 读取收件箱**，则需另行确认入站轮询能否单独关停（本批次未验证该路径） |

### T3 · 技能注册表检索/安装链路 —— ⚠️ 不可用

| 项 | 内容 |
|---|---|
| 现象 | `hermes skills search <词>` 与 `hermes skills inspect <id>` 均 **exit 0 但零输出**；`search` 对 `git`/`docker`/`excel`/`document`/`pdf` 五个词均返回 0 行结果 |
| 已排除 | 非纯网络阻断：`skills.sh`（308 / 0.34s）与 `clawhub.ai`（200 / 2.28s）均可达 |
| 影响 | SPEC:611 要求的「`hermes skills search/install` 安装 1 个示例技能验证链路」**未能完成**；仅验证了 SPEC:677 的两条（列表可见 ✅ + 提问触发 ✅） |
| 建议 | 交给 Session 1 或后续批次排查 Hermes 技能中心的 registry 配置与响应解析 |

### T4 · 腾讯云自动快照策略 —— ⏳ 需控制台人工操作

本批次**无法通过 SSH 完成**（腾讯云快照需控制台操作或 API 凭据，二者均未提供）。以下为可直接执行的操作指引：

**路径**：腾讯云控制台 → 轻量应用服务器 / CVM → 选择实例 `<主机名>`（`<服务器IP>`）→ **快照** → **自动快照策略** → 新建策略

**建议策略参数**：

| 参数 | 建议值 | 理由 |
|---|---|---|
| 快照时间 | 每日 **05:00** | 早于 `画像` cron（06:00）与 `晨报` cron（09:00），避免备份到写入中途的状态 |
| 重复日期 | 每天 | 团队处于活跃开发期，日粒度必要 |
| 保留时长 | **7 天** | 覆盖一周工作周期；系统盘仅 60GB、已用 15%，成本可控 |
| 快照类型 | 系统盘（`vda`，60GB） | 当前所有状态（Hermes 安装、profiles、Kanban、Caddy 配置、团队文件）均在同一系统盘 |

**补充建议**：
- 在 Session 1 开始前**手动打一次快照**并命名 `session0-accepted` 作为回滚基线。
- 若后续将 Kanban / 团队产出量级做大，再考虑把 `/root/team-files/` 与 `/root/.hermes/` 单独纳入备份范围。

### T5 · 其他遗留事项

| 项 | 说明 |
|---|---|
| Kanban 4 张卡全部 blocked | 属真实业务状态（项目基准设定未提供），非部署缺陷。需负责人补充题材/主线/主角/玩法/分支深度 5 项输入 |
| `t_00398c3e` 派单疑为错误 | 该任务要求「产出美术规范」，但 `pingshen` 是**只读评审**角色，且团队内无美术 profile —— 建议重派。此项由 `zhiban` 晨报主动发现，非本批次引入 |
| Hermes 安全审计告警「Running as ROOT」 | 按 SPEC 要求全会话以 root 运行，属预期；如后续收紧权限需重新评估 |

---

## 8. 部署期间的关键问题与处理

### 8.1 `github.com` 被 TCP 层阻断

- **现象**：`git clone` 失败（`GnuTLS recv error (-110)`），7 个候选 GitHub IP **全部在精确 8.000 秒超时**。
- **判定**：TCP 层阻断，非 DNS 问题。
- **处理**：改用 PyPI 官方 sdist（经阿里云镜像，速度快）播种安装目录；缺失文件经 `api.github.com`（实测 0.57-1.27 秒，可用）获取并做 **git blob SHA 逐字节校验**；本地建立裸仓库 `/root/hermes-origin.git` 作为 origin，使安装器的更新路径（`git fetch` / `git pull`）无需访问 github.com 即可成功。

### 8.2 终端工具被 tirith 下载阻塞 —— ⚠️ 本批次最严重的隐性故障

- **现象**：手动触发晨报 cron 后，run 长期停在 `running`；600 秒后 `TimeoutError: Cron job '晨报' idle for 601s (limit 600s) — last activity: executing tool: terminal`。
- **根因链**：Hermes 的 `terminal` 工具在执行前会调用 **tirith**（终端命令内容安全扫描器：同形字 URL、管道执行、终端注入等防护）。tirith 不在 PATH 时，Hermes 会**自动从 GitHub Releases 下载**（`_REPO = "sheeki03/tirith"`）。该下载在受限网络下仅约 **10-21 KB/s**，15.8MB 的包需 20 分钟以上；期间 `terminal` 工具**阻塞等待**，最终撞上 cron 的 600 秒 inactivity 上限而失败。
- **影响面**：**所有**使用终端工具的 cron 任务与 Agent 交互都会失败；由于晨报/周复盘/画像三个 cron 都依赖终端工具，等于团队机制整体停摆。
- **排查证据**：`/tmp` 下堆积 **14 个** `tirith-install-*` 临时目录（16:31→16:40 反复重试）；4 个 profile 均写入 `.tirith-install-failed` 熔断标记；进程 fd 指向未完成下载的 `.tar.gz`。
- **处理**：确认 Hermes 的 tirith 解析顺序为 **① PATH 查找 → ② `$HERMES_HOME/bin/tirith` → ③ 联网下载**，因此只要二进制在 PATH 上即可根治（源码注释亦说明「每次都会重跑本地廉价检查，手工安装会被自动拾取，**无需重启**」）。遂经 **`api.github.com` 获取 release 资产（302 重定向至可达的 `release-assets.githubusercontent.com`）**，并用**官方 `checksums.txt` 校验 SHA-256**：
  - 期望值（官方）：`efa6bf414a83dba385d4f13137e8677f850ced9102fe74ebb14c72f31df0dc77`
  - 实测值：**完全一致** ✅（`http=206` 断点续传，15,821,759 字节）
  - 安装至 `/usr/local/bin/tirith`（tirith 0.4.2），清除熔断标记，清理临时目录
- **结果**：晨报 cron 重新触发，**100 秒完成，状态 `completed`** ✅
- **说明**：tirith 属 Hermes 上游设计的自动下载组件（SPEC 与 `/opt/team-console` 均未提及），本批次经用户明确授权后安装，且全程通过官方 checksum 校验。

### 8.3 其他已处理问题

| 问题 | 处理 |
|---|---|
| `hermes -q` 报 `invalid choice` | 该版本顶层用 `-z PROMPT`，`-q` 仅在子命令下有效 |
| `gateway install --system` 被拒 | 需追加 `--run-as-user root`（SPEC 要求以 root 运行） |
| 安装器 `launcher prerequisites not found` | sdist 缺仓库根 `hermes` 入口文件，经 `api.github.com` 获取并**提交**（未提交会被 `git stash --include-untracked` 清掉） |
| 40 个脏文件 | sdist 缺 `.gitignore`，获取上游版本并提交 |
| `git` dubious ownership | 用 `tar --no-same-owner` 重新解压 |
| `caddy reload` 失败 | 曾尝试 `default_sni`（Caddy 2.7+ 才有），2.6.2 不支持；已回滚并改用自签证书方案 |

---

## 9. 给 Session 1 的注意事项

### 9.1 后端监听地址（务必对齐，否则反代 502）

Caddy 已按以下约定配置反向代理，Session 1 的 Node 后端需与之一致：

| 路由 | 应监听 |
|---|---|
| `/api/*` | `127.0.0.1:8787` |
| 其余（前端 / 主服务） | `127.0.0.1:3000` |

> 当前访问 `https://<IP>/` 返回 **502 是预期行为**（占位上游无进程），后端起来后即自动变为正常响应。无需修改 Caddy 配置。

### 9.2 调用 Agent API

- 端点：`http://127.0.0.1:8642`（cehua）/ `8643`（chengxu）/ `8644`（pingshen）/ `8645`（zhiban）
- 四个端口**仅绑定 `127.0.0.1`**：后端在同机可直连；如需外部访问，请走 Caddy 或 SSH 隧道，**不要**把 8642-8645 直接暴露公网。
- 鉴权：`API_SERVER_KEY`，**完整密钥在 `/opt/team-console/agents.json`（权限 600）**。
- ⚠️ **切勿将 `agents.json` 或任何密钥提交进 git 仓库、写入日志或前端代码**（`chengxu` 的 SOUL.md 已将此列为禁止项）。

### 9.3 环境与工具

- **tirith 已安装**于 `/usr/local/bin/tirith`（0.4.2）。**请勿卸载** —— 一旦不在 PATH 上，Hermes 会重新触发从 GitHub 的慢速下载并导致终端工具阻塞 600 秒以上。
- **Hermes 版本为 v0.19.0（2026.7.20）**，CLI 参数与直觉可能不符，**不确定时以 `hermes --help` / 子命令 `--help` 实际输出为准**。
- 全会话以 **root** 运行，无 sudo 限制，但 Hermes 会产生「Running as ROOT」安全审计告警（预期）。

### 9.4 已知未就绪项（会影响 Session 1 的功能）

| 项 | 影响 |
|---|---|
| 邮件通道未启用 | 后端或 Agent **无法发信**，直到 T2 补齐 `EMAIL_IMAP_HOST` |
| 技能注册表不可用 | 无法通过 `search/install` 拉取技能；内置 70 个技能可正常用 |
| 域名不可解析 | 外部无法通过域名访问；`https://<IP>` 有自签证书告警，客户端需 `-k` |
| 看板 4 张卡全部 blocked | 项目基准设定（题材/主线/主角/玩法/分支深度）缺失，是 4 张卡的**共同上游阻塞** |

### 9.5 不要做的事

- ❌ 不要修改 `/etc/hermes.env` 中 `HERMES_KANBAN_BOARD` 的值 —— 四个 profile 共享同一看板是刻意的设计（C1），改掉会导致看板分裂。
- ❌ 不要删除 `/etc/systemd/system/hermes-gateway-*.service.d/10-cloudloom-env.conf` —— 共享环境依赖它，且它能在 Hermes 重新生成主单元后存活。
- ❌ 不要在未确认的情况下重跑 `hermes gateway install` —— 见上一条。
- ❌ 不要覆盖 `/root/.hermes/profiles/*/SOUL.md` —— 四份人格已按 D34 配置并验收通过。

---

## 10. 交付物与备份

| 项 | 路径 |
|---|---|
| 本报告 | `/opt/team-console/reports/Session0-环境部署报告.md` |
| 完整 API 密钥 | `/opt/team-console/agents.json`（权限 600，root-only） |
| Hermes 安装目录 | `/usr/local/lib/hermes-agent` |
| Profile 目录 | `/root/.hermes/profiles/{cehua,chengxu,pingshen,zhiban}/` |
| 共享环境 | `/etc/hermes.env` |
| Kanban 看板 | `/root/.hermes/kanban.db` |
| Caddy 配置 | `/etc/caddy/Caddyfile` |
| 自签证书 | `/etc/caddy/certs/cloudloom.crt` / `.key` |
| 团队文件目录 | `/root/team-files/{系统通知/,系统通知/画像/,产出/,资料库/}` |
| 晨报产物 | `/root/team-files/系统通知/晨报-20260913.md` |

---

*本报告由 Session 0 执行过程实测产出，所有结论均附可复核证据。未完成项已如实标注于第 7 节，未作美化。*

---

## 附：T2 邮件通道 —— 已解决（2026-09-13 晚 · 管理员助手补记）

- **原挂起原因**：邮件平台启用需四项齐备（`EMAIL_ADDRESS / EMAIL_PASSWORD / EMAIL_IMAP_HOST / EMAIL_SMTP_HOST`，见 `check_email_requirements`），当时缺 `EMAIL_IMAP_HOST`。
- **处理**：`EMAIL_IMAP_HOST=imap.qq.com` 已补入 `/root/.hermes/.env` 及 4 个 profile 独立 `.env`（cehua/chengxu/pingshen/zhiban），4 个 gateway 已重启并全部恢复健康。
- **入站安全边界（代码级核实）**：未配置任何 allowlist（`EMAIL_ALLOWED_USERS` / `GATEWAY_ALLOWED_USERS` 均未设）时，适配器对**所有入站邮件默认拒绝**（`adapter.py` `_dispatch_message` 的 default-deny 分支），且自发送件被 self-message 过滤 —— 即当前为**纯出站发信**，不存在「收件箱被交给 Agent 处理」的影响。若未来希望指定地址可与 Agent 邮件互动，再显式配置 `EMAIL_ALLOWED_USERS` 即可启用。
- **实测（复跑晨报 cron `44cf46376cff`）**：晨报文件重新生成（`/root/team-files/系统通知/晨报-20260913.md`，4745 字节，19:40）；**QQ 邮箱收件箱实测收到新晨报邮件**（主题：【晨报】2026-09-13 看板扫描：4 张卡全阻塞，项目停摆待输入；发件人：值班Agent zhiban <<负责人邮箱>>），收件箱接件时间实测 **19:40:46 +0800**（原始 Received 头：发自本服务器 <服务器IP>，19:40:45），发送链路完整打通。
- **结论**：§6 验收项 4（晨报：文件 + 邮件）自本补记起 **✅ 全部通过**；T2 关闭。
