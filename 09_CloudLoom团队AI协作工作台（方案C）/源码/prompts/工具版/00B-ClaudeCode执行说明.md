# CloudLoom · Claude Code 执行说明（本机 + SSH 远程模式）

> **用途**：用本机 Claude Code 执行 S1-S4（合并稿）开发任务的备用/替代通道。
> **触发背景**：2026-09-13 晚 Kimi 触发 **5 小时用量限额**（403，窗口结束后自动恢复）；Claude Code 本机远程模式在 S0 已验证可行（S0 批即本模式完成）。
> **原则**：所有产出（代码 / 报告 / 验收）仍在服务器上，验收标准不变。

## 一、可行性（为什么没问题）

- 本机 → 服务器 **免密 SSH 已配好**（`ssh root@<服务器IP>` 直登）
- 执行稿正文**与工具无关**：Claude 读取服务器上的稿子、按「阶段 1→4」执行即可
- 本机 Claude Code 已就绪：`claude`（2.1.251，2026-09-13 在用）

## 二、使用步骤（3 步）

1. 本机终端（PowerShell / Git-Bash 均可）：
   ```
   cd D:\learn\saishi\chcz\CloudLoom
   claude
   ```
2. 把下方【粘贴用提示词】全文粘进 Claude
3. 批准策略：**常规文件/测试操作可放行；涉及 systemd、对外端口、密钥、删除类操作逐条细看**（别开全自动）

## 三、粘贴用提示词

```text
【任务：CloudLoom 系统开发（远程执行 · 阶段 1→4）】

你是执行代理（Claude Code，本机运行）。请通过 SSH 远程操作服务器完成开发。

▍位置（都在服务器上）
· 服务器：root@<服务器IP>（本机已配免密 SSH，直接 ssh 即可）
· 权威规格：/opt/team-console/SPEC.md —— 与执行稿冲突时以 SPEC 为准
· 执行稿：/opt/team-console/prompts/工具版/Session1-4-KimiCode合并执行稿.md

▍要求
1. 先 ssh 读取执行稿全文、SPEC 决策清单部分、项目现状（含 reports/Session0-环境部署报告.md）
2. 按「阶段 1→2→3→4」连续执行：开发、部署、逐项验收（含 curl 自测）；所有操作在服务器上完成（你从本机用 ssh 执行），本机不落地任何项目文件
3. 每阶段产出报告 → 服务器 /opt/team-console/reports/（文件名按执行稿），并 scp 回本机 D:\learn\saishi\chcz\CloudLoom\reports\ 留档
4. 验收项逐条跑通；失败先诊断修复，禁止静默跳过；不确定的参数以实际输出为准
5. 全部结束（或遇到必须用户决策的阻塞）时，汇总：各阶段验收结果 + 遗留问题 + 待决策事项

▍背景与硬约束
· 前一代理（Kimi）执行到阶段 1 起步时因用量限额中断，未写入任何文件——你从干净状态开始
· 执行稿正文与工具无关（遇 /compact 等表述按你对应能力理解）
· S0 已完成：Node / Hermes / 4 个 Agent 网关（8642-8645，仅 127.0.0.1）/ Caddy 均已就绪
· 不重跑 hermes gateway install；不卸载 tirith；密钥只进 .env / agents.json（600）且不入 git
· 域名未就绪 → 走降级路径（对外 HTTPS 延期，不得 IP 直连对外）
· ssh 命令用非交互式（ssh -o BatchMode=yes root@<服务器IP> '<命令>'）；常驻服务用服务器侧 nohup/tmux，别让 ssh 挂住
```

## 四、注意事项

- **报告即交接**：每阶段报告写到服务器 `reports/`，之后换任何工具执行都能无缝接上（不依赖聊天记录）
- **Kimi 侧**：5 小时窗口结束后额度自动恢复；原会话留在 tmux `cloudloom`（可 `kimi -r` 恢复），先不用管
- **断点续跑**：若 Claude 侧也中断（限额/网络），已产出的报告与代码就是断点——换回 Kimi 或重开 Claude 都能接着干
- **复核**：跑完把 Claude 的汇总发出来，由助手独立抽查验收（同 S0 流程）
