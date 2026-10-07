# Session 0 · 环境与基础设施 —— Claude Code 执行稿（CloudLoom）

> **运行方式**：推荐在本地（Windows，有代理）运行 Claude Code；本稿所有命令**默认在服务器上执行**，你应通过
> `ssh root@<服务器IP> '<命令>'` 远程执行（文件传输用 `scp`）。若你直接跑在服务器上，则本地执行即可。
> **本稿为一次性完整执行设计**：按步骤做、每步验证、失败即停并报告。不要跳过任何验证。

---

## 0. 你的角色与总目标

你是资深 DevOps 工程师。目标：把一台**全新**的腾讯云轻量服务器（Ubuntu 24.04 LTS + 预装 Docker 29.6.1，2核4G）
配置成 CloudLoom（内部代号「方案 C」）的完整基础设施，并通过本批验收。

**开工前必读**：`/opt/team-console/SPEC.md`（完整读，重点章节：二、环境与前置；五、第 1 阶段；五、第 2 阶段；五、第 7 阶段；五、第 8 阶段）。

**范围铁律（不得越界）**：
- ❌ 不写任何 Node 后端代码（Session 1 的事）
- ❌ 不写任何前端代码（Session 2/3 的事）
- ❌ 不安装 Open WebUI（已弃用）
- ❌ 不偏离 SPEC 第四节决策清单；不确定的参数以 `hermes --help` 实际输出为准

## 1. 环境信息（已确认，勿再询问）

| 项 | 值 |
|---|---|
| 服务器 | `root@<服务器IP>`（Ubuntu 24.04 LTS + Docker 29.6.1，2核4G，60GB） |
| 域名 | `<域名>` —— ⚠️ **命名审核/实名/备案均未就绪，当前不可解析**（HTTPS 验收延后，见 Step 8） |
| 工作目录 | `/opt/team-console`（SPEC.md 已放于此） |
| 团队 | 楚华成章 ｜ 项目代号 CloudLoom |
| Agent Profiles | `cehua`(策划,8642) / `chengxu`(程序,8643) / `pingshen`(评审,8644) / `zhiban`(值班,8645) —— **注意拼写是 cehua** |

**开工前置核对（先做）**：① 打开 `/root/.hermes/.env` 确认 `DEEPSEEK_API_KEY` 已由管理员填入真实值（**缺则暂停报告，不得编造**）；② SMTP 四项已配置（缺则：Step 6-7 邮件验证挂起待补，报告列待办）；③ 本地已配置免密 SSH（Claude Code 的 Bash 非交互，ssh 密码提示会卡住）—— 未配置时先在本地终端执行一次 `ssh-copy-id root@<服务器IP>`（连接可加 `-o StrictHostKeyChecking=accept-new`）。

## 2. 执行步骤（逐条执行 + 验证；每条完成后把「命令 + 结果」记入日志）

### Step 1 系统基础环境
- `apt update && apt upgrade -y`；安装 `curl git python3 python3-venv python3-pip`
- Node 20 LTS（nodesource 源）→ `node -v` 验证 v20+
- Docker 复查：`docker --version` 应为 29.6.1（镜像预装；缺失才补装）
- ✅ 验证：逐条打印版本号

### Step 2 安装 Hermes + DeepSeek
- 安装：`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
- PATH：hermes 可能在 `~/.local/bin`，按安装脚本提示写进 `/root/.bashrc` 并 `source`
- 配置：`hermes config set model.provider deepseek` / `model.base_url https://api.deepseek.com` / `model.default deepseek-chat`
- **API Key：由管理员写入 `/root/.hermes/.env`**（`DEEPSEEK_API_KEY=sk-...`）。**你不许编造 key**；写入后执行 `hermes chat -q "回复OK两个字"` 验证连通
- ✅ 验证：`hermes doctor` 无致命错误 + chat 返回 OK

### Step 3 创建 4 个 Agent Profile
- 按 SPEC 第 2 阶段创建 `cehua/chengxu/pingshen/zhiban`，端口 8642-8645
- 每个 profile 生成独立 `API_SERVER_KEY`（`openssl rand -hex 24`），**记入报告（脱敏）**
- ✅ 验证：`curl http://127.0.0.1:8642/health` 及 8643/8644/8645 全部返回 ok

### Step 4 覆盖 SOUL.md（v3.2 必须含「行为边界」）
- 按 SPEC 第 2 阶段的四份人格**整体覆盖**（`--clone` 会继承默认人格，必须完全重写，不留残渣）
- 每份 SOUL.md 必须含「行为边界」小节四处：**可自主 / 需升级人审 / 禁止 / 失败兜底**（D34）
- ✅ 验证：`hermes -p cehua -q "介绍你的职责"` 返回策划人格；4 个 profile 各问一次，风格应互不相同

### Step 5 Kanban 共享
- 按 SPEC：写 `/etc/hermes.env`，创建 4 个 gateway 的 systemd 服务单元（统一 `EnvironmentFile=/etc/hermes.env`）并 `systemctl enable` 开机自启
- ✅ 验证：`systemctl status` 4 单元 active；`hermes kanban list` 正常输出

### Step 6-7 Kanban 任务 + cron + Skill
- Kanban 初始化 + 4 个示例任务
- cron：晨报 09:00 / 周复盘 周一 10:00 / 画像 06:00，均绑定 `zhiban`
- Skill（N1）：`hermes skills search/install` 安装 1 个示例技能 → `hermes skills list` 可见
- ✅ 验证：手动触发晨报一次 → `~/team-files/系统通知/` 生成晨报文件 + 邮箱实际收到（SMTP 缺失则邮件项挂起记待办，见开工前置核对）

### Step 8 Caddy + HTTPS（⚠️ 域名未就绪的降级路径）
- 安装 Caddy；Caddyfile：`/` → 占位 `:3000`，`/api/*` → 占位 `:8787`（后续批次填充）
- 域名 `<域名>` **当前不可解析**（命名审核/实名/备案未就绪）——本次**只做**：
  `IP + 自签证书` 内部连通验证（如 `curl -k https://127.0.0.1`）
- **正式证书签发 + `https://域名` 验收 → 标记「延期补做」**，写入报告待办清单（Session 4 收口）
- ✅ 验证：Caddy 服务运行中 + 自签 HTTPS 本地可达

### Step 9 腾讯云自动快照
- 控制台操作；若无法自动完成，输出**操作指引**（路径 + 建议策略：每日快照 / 保留 7 天）

## 3. 本批验收标准（全部通过才能交接；域名两项除外）

1. `curl http://127.0.0.1:8642/health` 及 8643/8644/8645 全部 ok
2. `hermes -p cehua -q "介绍你的职责"` 返回策划人格
3. `hermes kanban list` 可见 4 个初始任务
4. 手动触发晨报 cron：生成文件 + 收到邮件
5. ~~`https://域名` 返回 Caddy 页面~~ → **⏳ 延期补做**（域名未就绪；不得因此阻塞交接）
6. `reboot` 后 caddy + 4 个 gateway 全部自动恢复
7. 输出《环境部署报告》

## 4. 交付物（写成文件）

写入 **`/opt/team-console/reports/Session0-环境部署报告.md`**，必须含：
1. 服务器 IP / 域名 / 4 端口与 API_SERVER_KEY（**脱敏**：前 4 位 + 长度）
2. 4 个 Profile 拼音名 ↔ 显示名对照表
3. systemd 单元清单（路径 / 状态 / 开机自启）
4. cron 列表、Kanban 路径、`~/.hermes/.env` 已配置项、已安装的示例技能（N1）
5. reboot 自检结果
6. **延后项清单**（域名 HTTPS、证书）＋ 给 Session 1 的注意事项（端口占用、目录约定等）

## 5. 结束动作

在对话中输出：报告文件路径 + 验收结论摘要（含延后项），然后**停止**——不要顺手开始 Session 1 的工作。
