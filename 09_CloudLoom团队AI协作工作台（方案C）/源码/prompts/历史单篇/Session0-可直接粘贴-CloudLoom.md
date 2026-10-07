# Session 0 · 环境与基础设施 — AI Coding 任务提示词（CloudLoom 可直接粘贴版）

> **用法**：本稿已填齐（IP / 域名 / 团队名 / 项目代号）——直接复制**全文**粘贴给 AI Coding 工具即可。
> **前置要求**：管理员已完成《部署前置清单-管理员操作》全部 9 步（其中 **ICP 备案为并行项，不阻塞本批**）。
> **本批做完后**：检查《环境部署报告》→ 关键内容填进 `Session1-提示词.md` 的【前置状态】。
> 已预填：团队名「楚华成章」、项目代号「CloudLoom」、4 个 Agent 显示名对照。

---

# Session 0 · 环境与基础设施

## 你的角色
资深 DevOps 工程师。严格按照规格文档执行，不自作主张，每一步验证后再继续。

## 规格文件（必读）
`/opt/team-console/SPEC.md`（方案 C / CloudLoom 完整规格 v3.2）——完整读取，重点章节：二、环境与前置；五、第 1 阶段；五、第 2 阶段；五、第 7 阶段；五、第 8 阶段。

## 项目环境
- 服务器：**Ubuntu Server 24.04 LTS（镜像：Ubuntu 24.04-Docker 29.6.1，预装 Docker）**，2核4G，root SSH，
  公网 IP：**<服务器IP>**
- 域名：**<域名>**（DNS A 记录已配置，待实名审核通过后生效；安全组已放行 80/443）
- 工作目录：`/opt/team-console`（创建之，SPEC.md 已放于此）
- 团队信息：团队名 **楚华成章**；项目代号 **CloudLoom**（用于 HERMES.md 与文件分类）
- 4 个 Agent Profile 显示名对照：`cehua`→策划 / `chengxu`→程序 / `pingshen`→评审 / `zhiban`→值班
- 注意：规格第 1 阶段已针对 24.04 调整（Docker 预装跳过 + Node 20 LTS 安装），按规格执行即可

## 本批次范围（严格限定）
**做：**
1. 系统基础环境（apt 更新、装 curl/git/python3/nodejs/npm/docker）
2. 安装 Hermes 标准版，配置 DeepSeek（占位 key 由管理员填入真实值）
3. 创建 4 个预设 Agent Profile（cehua/chengxu/pingshen/zhiban，端口 8642-8645，各配 API_SERVER_KEY）
4. 为 4 个 Profile 覆盖 SOUL.md 人格（按规格第 2 阶段；**每份 SOUL.md 必须含「行为边界」小节：可自主/需升级人审/禁止/失败兜底，D34**）
5. 配置 Kanban 共享（/etc/hermes.env + 4 个 systemd 单元 EnvironmentFile）
6. Kanban 初始化 + 4 个示例任务
7. cron 配置（晨报 09:00、周复盘 周一 10:00、画像 06:00，绑定 zhiban）
8. Caddy 部署 + 域名 HTTPS（反代规则先指向占位端口 8787/3000，后续批次填充）
   - **若域名实名 / ICP 备案尚未就绪**：先完成 Caddy 安装与反代配置，用「服务器 IP + 自签证书」做内部连通验证；
     正式证书签发与域名 HTTPS 验收留到域名可解析后补做（或并入 Session 3）—— 不要为空等域名而阻塞其余 8 项
9. 腾讯云自动快照开启（控制台操作，若无法自动则输出操作指引）

**不做：**
- ❌ 不写任何 Node 后端代码（Session 1 的事）
- ❌ 不写任何前端代码（Session 2/3 的事）
- ❌ 不安装 Open WebUI（方案已弃用）

## 前置状态
- 全新服务器，无任何项目相关软件
- 管理员已提供：DeepSeek API Key（真实值）、域名、服务器 SSH 凭据
- **管理员已完成《部署前置清单-管理员操作》**（服务器可达、域名解析生效、80/443 放行、DeepSeek key 有效、SMTP 可用、团队信息齐备）——任何一项未完成，先暂停并请管理员补齐再继续
- ICP 备案并行推进中（未通过不影响本批；**Session 3 部署 HTTPS 前必须已通过**）

## 执行要求
1. 每步完成立即验证（curl 探活、hermes chat 试对话、cron 手动触发测试），失败先诊断再继续
2. DeepSeek key 由管理员填入 `~/.hermes/.env`，你负责给出精确的填入命令并验证生效
3. 4 个 gateway 必须 systemd 托管且开机自启；`reboot` 后全部恢复才算完成
4. 开始前先花 2 分钟核对前置状态：服务器可达、域名解析生效、80/443 放行、DeepSeek key 有效、SMTP 可用——任何一项不满足，先报告管理员而不是硬跑

## 本批验收标准（全部通过才能交接）
1. `curl http://127.0.0.1:8642/health` 及 8643/8644/8645 全部返回 ok
2. `hermes -p cehua -q "介绍你的职责"` 返回策划人格（不是默认人格）
3. `hermes kanban list` 能看到 4 个初始任务
4. 手动触发晨报 cron 一次，`~/team-files/系统通知/` 下生成晨报文件，且邮件收到
5. `https://域名` 返回 Caddy 默认页（或 502 但证书有效——说明反代已就位）
   ｜**若域名实名 / 备案未就绪：本项标记「延期补做」，不影响其余 6 项验收与批次交接**
6. `reboot` 后：caddy + 4 个 gateway 自动恢复
7. 输出《环境部署报告》

## 交接物（Session 0 结束必须输出）
1. 《环境部署报告》：服务器 IP、域名、4 个端口与 API_SERVER_KEY、管理员账号创建方式、cron 列表、Kanban 路径、`~/.hermes/.env` 中已配置的项
2. 4 个 Profile 的拼音名与显示名对照表
3. systemd 单元文件清单（路径 + 状态）
4. 给 Session 1 的注意事项（如端口占用、cron 输出目录实际路径等）

## 约束
- 决策清单（SPEC 第四节）不得偏离
- 不确定参数以 `hermes --help` / 实际命令输出为准
- 每个阶段完成即汇报，禁止静默跳过失败

---

## 管理员备注（粘贴前自查，不用粘进对话）
- [ ] SPEC.md 已放到服务器 `/opt/team-console/SPEC.md`（本地源：`CloudLoom\SPEC-v3.2.md`）
- [ ] 服务器公网 IP 已填入 → 用 `verify_prereqs.py` 验过（SSH/80/443/DNS/证书）
- [ ] DeepSeek key 已充值并实测可用
- [ ] SMTP 授权码已实测发信成功
- [ ] 已开启腾讯云自动快照
- [ ] ⏳ ICP 备案已提交（并行项：不阻塞本批，**Session 3 部署 HTTPS 前必须通过**）
