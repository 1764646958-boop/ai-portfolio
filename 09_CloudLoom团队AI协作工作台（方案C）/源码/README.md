# CloudLoom · 源码与运行脚本

> **本目录是 CloudLoom 团队 AI 协作工作台的实际部署源码**（快照：2026-09-14），从服务器部署目录导出。
> 配套技术说明见上一级：`01_技术与架构概览.md` / `02_工程数据与验收指标.md` / `03_开发过程与AI协作工程化.md` / `04_源码级实现细节.md`。

## 一、目录结构

```
server/                 后端代理层（Node.js + Express 5）—— 19 个模块 / 2,700 行
  src/tasks.js          办公任务中心：状态机 / 队列单飞 / 敏感内容人审 / 修正闭环 / 复核 / 产物登记 / 重启恢复（653 行，最大模块）
  src/memories.js       团队记忆库：FTS5(trigram) 检索 / 三级 ACL / 任务→记忆沉淀入口
  src/mcp.js            MCP 网关（Streamable HTTP，协议 2025-06-18）：5 个工具
  src/auth.js           认证：scrypt / JWT Cookie / authRequired
  src/lazystart.js      自建 Agent 懒启动：探活 / 拉起 / 空闲停机
  src/usage.js          用量记账与成本估算（全项目唯一落账点）
  src/index.js          进程入口：API 8787（含 /mcp）+ 前端静态 3000 + 就绪闸门
  …                     另有 conversations / agents / chat / context / files / profiles / registry / config / util / kanban / poll

team-console/           前端单页工作台（Vue 3 + TypeScript）—— 20 个文件 / 2,409 行
  src/views/            7 个 Tab：聊天 / 看板 / 任务 / 画像 / 资料库 / 记忆 / 设置
  src/components/       流式消息渲染、导航侧栏
  src/stores/           会话与认证状态

tools/                  辅助脚本
ops/                    运维脚本：看门狗（零 LLM）/ 按需作业 / 邮件 / 值班摘要
prompts/                ★ 给 AI 编码代理的执行稿（见 §二）
  工具版/                按工具通道分批的执行稿（合并版 + 分项版）
  历史单篇/              早期逐 Session 提示词
docs/                   运行手册：SPEC 微修订草案 / 成员接入手册 / 前端开发者说明 / 故障排查表 / 二期备忘
SPEC.md                 唯一权威规格（与执行稿冲突时以它为准）
HERMES.md               运行环境说明
team-console.service    systemd 单元
```

**代码规模**：**5,109 行 / 39 个源文件**（后端 2,700 行 19 模块 · 前端 2,409 行 20 文件）；后端运行时依赖**仅 4 个**（express / cookie-parser / jsonwebtoken / multer），数据层用 Node 内置 `node:sqlite`——**零外部中间件**。

## 二、为什么把 `prompts/` 也放进来

`prompts/工具版/` 是这个项目**最值得看的部分**——它不是"任务清单"，而是 harness 的原始形态。每一批执行稿都写清了：

1. **位置与权威**：项目根、规格文件、当前基线报告（"先读它再动手"）
2. **锚点**：文件 + 行号 + 现状代码片段（防止 AI 自行选点）
3. **要求**：最小改动 / 加法优先 / 不重写既有模块 / 不扩散范围
4. **禁区**：不重跑 `gateway install`、不卸载关键组件、密钥只进 `.env` 且**不回显**
5. **验收**：逐条可执行（命令 + 期望输出），必须附**原始输出**
6. **回归**：每批跑一次端到端脚本（42 断言）
7. **留档**：报告章节（问题 / 改动 / diff 摘要 / 验证证据 / 剩余风险）
8. **失败处理**："先诊断再继续，禁止静默跳过"、**"禁止用『已知问题』蒙混任何验收项"**

配合 `04_源码级实现细节.md` 一起看，能完整还原 **"人定规格与验收 → AI 执行 → 人独立复核"** 这条链。

## 三、本地运行

```bash
# 后端（API 8787，同时是 MCP 网关 /mcp）
cd server && npm install && node src/index.js

# 前端（构建产物由 3000 端口静态服务）
cd team-console && npm install && npm run build
```

依赖：`server/.env` 需提供 `JWT_SECRET`；Agent 运行依赖 Hermes（4 个预设 profile）。

## 四、⚠️ 本目录的发布边界（重要）

导出时按**公开发布标准**做过体检，以下内容**已排除、不在本目录**：

| 排除项 | 原因 |
|---|---|
| `.env`、`agents.json` | 含真实密钥（`JWT_SECRET`、5 个 Agent 的 `api_server_key`） |
| `data/`（6.2 MB） | 含真实账号、消息、团队记忆、任务与用量数据 |
| `reports/`（432 KB） | 含服务器信息的**未脱敏原版**报告；已脱敏版本见上一级 `_原始报告（脱敏）/` |
| `_backup-20260913/` | 历史副本（138 MB） |
| `node_modules/`、`dist/`、`package-lock.json` | 体积型依赖与构建产物 |

同时做过**脱敏替换（83 处）**：

- 服务器**公网 IP / 主机名 / 域名** → 占位符
- 协作成员**真实姓名** → 角色代称（负责人 / 成员 B / 成员 C）

> **口径**：本目录的代码与文档**不含任何凭据、真实服务器地址或个人身份信息**。
> 如需完整运行环境与原始报告，可当面演示或按需提供脱敏版本。

---

*本目录与上一级四份技术文档共同构成 CloudLoom 作品的完整材料；整理与体检记录参见上一级 `README.md` 与作品集 `00_作品集总览/整理日志.md`。*
