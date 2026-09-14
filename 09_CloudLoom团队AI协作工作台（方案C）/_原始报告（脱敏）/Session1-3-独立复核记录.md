> 📄 **作品集展示副本（已脱敏）**：服务器地址 / 主机名 / 域名 / 邮箱 / 凭据 / 令牌均已替换为占位符；
> 完整原报告不随作品集仓库分发。指标与结论未作任何修改。

# Session 1-3 独立复核记录（助手实测）

- 时间：2026-09-14 12:05-12:08（CST）
- 方式：助手**直接 SSH 登录服务器实测**（不依赖执行方自述），与 S0 复核同标准
- 对象：Claude Code 执行批（S1-S3 + 收尾补齐项；报告见 `reports/Session1/2/3`）

## 一、实测结果（全部通过）

| 项 | 实测 | 结论 |
|---|---|---|
| 报告与交付物 | S1 33.5K / S2 32.3K / S3 35.1K（254 行）；`docs/`×4 + `HERMES.md` 在位；本地 `reports\` 副本齐全（含 reboot-verify.txt） | ✓ |
| 端口监听 | 80 / 443 / 3000 / 8787 / 8642-8645 全部监听中；**8650 无监听**（符合懒启动设计） | ✓ |
| 系统单元 | caddy、team-console、4×hermes-gateway-* 均 active；hermes-gateway-testbot = disabled / inactive | ✓ |
| 健康检查 | `/api/health`=200；:443=200；:3000=200；4 网关 `/health`=200 | ✓ |
| 数据面（带鉴权令牌） | **tasks=100 / agents=5 / members=5 / conversations=3**；未带令牌实测 401（鉴权在岗） | ✓ |
| 稳定性 | uptime 10h22m（01:43 reboot 后无额外重启）；02:00 起 journal 无任何 error/fatal | ✓ |
| 懒启动佐证 | journal 逐字：`Sep 14 01:32:30 [lazystart] 空闲超 30min，已停止: testbot`（与报告一致） | ✓ |
| 敏感值 | 6 份交付物 sk-/邮箱全号模式**独立重扫 = 0 命中**；仅 Session0 报告 1 处 QQ 全号（待处理，见下） | ✓ |
| 权限 / 磁盘 | agents.json = 600；磁盘 45G 可用（21%） | ✓ |

## 二、复核结论

- **G3 判定（17/19 通过 + 2 项环境性待补）予以确认**；未发现"声明通过而实际未通过"的项
- 报告亮点核实：5 项缺陷修复带 diff 备份、4 项 FAIL 属测试脚本态误伤（非产品缺陷）的复判定性成立、14 项遗留与 3 处 SPEC 偏差均如实记录
- **无法远程证实项**：备案进度、自动快照（需腾讯云控制台）
- **待处理小尾巴**：`Session0-环境部署报告.md` 内 1 处 QQ 邮箱全号（成文于脱敏纪律之前；建议掩码）

## 三、关联决策（详见对话）

UMask=0077（本机实测当前 0022、User=root）/ 自动快照参数 / SPEC v3.3 微修订（Node 22+、轮询 8s、placeholder）/ 验收残留清理时机 / 值班自检提示词修正 / 晨报邮箱确认。

## 四、服务现状快照（实测值）

```
User=root  UMask=0022  MemoryMax=infinity   （team-console.service）
tasks=100  agents=5  members=5  conversations=3
uptime 10h22m；load 0.06/0.03/0.00；磁盘 12G/59G 已用
```

## 五、后续处置记录（2026-09-14 下午，助手执行）

| 项 | 处置 | 验证 |
|---|---|---|
| UMask=0077 | 新增 systemd drop-in `/etc/systemd/system/team-console.service.d/umask.conf` → daemon-reload → 重启服务 | 重启后新建 `*-shm` 权限实测 **600**；`systemctl show` UMask=0077；health=200 ✓ |
| 值班自检提示词 | 修正 3 个文件（zhiban 的 `zhiban-team-report` 技能）：`references/report-shapes.md`、`templates/校验说明-restricted可选成员正例.md`、`references/workbench-feature-verification.md`（5 处口径替换） | 均留备份 `.bak-20260914*`；"which himalaya" 残留=2（均为更正性表述）✓ |
| QQ 全号掩码 | `Session0-环境部署报告.md`（服务器+本地）、`Session0-T2补记.md`（本地）→ `1764****` | 全量重扫=**0**；双端 md5 一致（6fd9efcf…）✓ |
| 本地隧道 | `ssh -N -L 8443:127.0.0.1:443`（助手已拉起）；一键脚本：CloudLoom 目录 `打开工作台.cmd` | https://localhost:8443 实测 200 ✓ |
| SPEC v3.3 草案 | 落盘：本地 + 服务器 `docs/SPEC-v3.3-微修订草案-20260914.md` | md5 双端一致（d7322579…）✓ |
| 微修复包提示词 | 落盘：`prompts/工具版/Session3.1-微修复包-合并版.md` + `分项版` | md5 双端一致（12202ca8… / 3ac02cc3…）✓ |
| 待用户控制台 | 备案查询 / 安全组放行 80/443 / 自动快照（建议每日+保留 5~7，含 `s1s3-verified` 基线） | 待办 |

> 处置原则：所有改动先备份；报告/文档类文件均做双端 md5 一致性校验。
