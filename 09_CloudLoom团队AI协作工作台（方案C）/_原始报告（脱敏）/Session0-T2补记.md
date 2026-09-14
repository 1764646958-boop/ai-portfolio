> 📄 **作品集展示副本（已脱敏）**：服务器地址 / 主机名 / 域名 / 邮箱 / 凭据 / 令牌均已替换为占位符；
> 完整原报告不随作品集仓库分发。指标与结论未作任何修改。


---

## 附：T2 邮件通道 —— 已解决（2026-09-13 晚 · 管理员助手补记）

- **原挂起原因**：邮件平台启用需四项齐备（`EMAIL_ADDRESS / EMAIL_PASSWORD / EMAIL_IMAP_HOST / EMAIL_SMTP_HOST`，见 `check_email_requirements`），当时缺 `EMAIL_IMAP_HOST`。
- **处理**：`EMAIL_IMAP_HOST=imap.qq.com` 已补入 `/root/.hermes/.env` 及 4 个 profile 独立 `.env`（cehua/chengxu/pingshen/zhiban），4 个 gateway 已重启并全部恢复健康。
- **入站安全边界（代码级核实）**：未配置任何 allowlist（`EMAIL_ALLOWED_USERS` / `GATEWAY_ALLOWED_USERS` 均未设）时，适配器对**所有入站邮件默认拒绝**（`adapter.py` `_dispatch_message` 的 default-deny 分支），且自发送件被 self-message 过滤 —— 即当前为**纯出站发信**，不存在「收件箱被交给 Agent 处理」的影响。若未来希望指定地址可与 Agent 邮件互动，再显式配置 `EMAIL_ALLOWED_USERS` 即可启用。
- **实测（复跑晨报 cron `44cf46376cff`）**：晨报文件重新生成（`/root/team-files/系统通知/晨报-20260913.md`，4745 字节，19:40）；**QQ 邮箱收件箱实测收到新晨报邮件**（主题：【晨报】2026-09-13 看板扫描：4 张卡全阻塞，项目停摆待输入；发件人：值班Agent zhiban <<负责人邮箱>>），收件箱接件时间实测 **19:40:46 +0800**（原始 Received 头：发自本服务器 <服务器IP>，19:40:45），发送链路完整打通。
- **结论**：§6 验收项 4（晨报：文件 + 邮件）自本补记起 **✅ 全部通过**；T2 关闭。
