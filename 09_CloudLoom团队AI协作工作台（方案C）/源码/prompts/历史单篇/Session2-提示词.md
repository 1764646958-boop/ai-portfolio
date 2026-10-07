# Session 2 · 核心价值模块 — AI Coding 任务提示词（可直接粘贴）

> 用法：把【前置状态】粘贴 Session 1 的《后端 API 自测报告》+ N4 结论后，将**本文件全文**粘贴给 AI Coding 工具。
> 本批做完后：**管理员亲自跑一遍"任务→记忆→引用"闭环**（核心价值，值得人工验证）→ 填进 Session 3 提示词的【前置状态】。

# Session 2 · 核心价值模块（4.8 任务中心 + 4.9 记忆库 + 4.10 闭环 + 前端骨架）

## 你的角色
资深全栈工程师。这是整个系统最核心的一批，实现"办公任务 → 产物交付 → 自动沉淀记忆 → 下次引用"闭环。质量优先，不赶工。

## 规格文件（必读）
`/opt/team-console/SPEC.md`——完整读取，重点章节：四、决策清单（D4/D5/D11/D23/D24/D25/D26/D28）；五、第 4 阶段（4.8/4.9/4.10/**4.11**）；五、第 5 阶段（前端页面与组件）；五、第 9 阶段验收项 11/13/14/16。

## 项目环境
- 后端：`/opt/team-console/server/`（Session 1 已完成，勿改动已验收代码）
- 前端：`/opt/team-console/team-console/`（脚手架已建）
- 前置状态（Session 1 已完成）：【粘贴 Session 1 的《后端 API 自测报告》 + N4 结论 + agents.json】

## 本批次范围（严格限定）
**做：**
1. 实现 4.8 办公任务中心：tasks.db（tasks + outputs + **task_corrections 三表，D35**）、
   6 个 API（含 **POST /api/tasks/:id/approval 审批接口，D35**）、任务状态机
   queued/running/**waiting_approval**/done/failed（D36：涉金额/对外承诺/删数据或发起人勾选 → 需审批）、
   同一 Agent 排队（"前面还有 N 人"）、产物目录 `~/team-files/产出/<task_id>/`、取消功能；
   **执行指令注入【相关修正记录】（同类任务近 30 天最近 5 条）+【行为边界】（该 Agent SOUL 摘要）**
2. 实现 4.9 团队记忆库：team-memory.db（memories + memory_fts，FTS5 trigram）、5 个 API、ACL 过滤（private/team/restricted）、/api/memories/suggest
3. 实现 4.10 融合闭环：任务 approved/无审批直接 done 时自动写 conclusion 记忆
   （type/title/content/tags/visibility/source_task_id，content 含审批修正摘要，D35）；
   任务发起时 ref_memories 注入 Agent 上下文
4. **填充 4.11 MCP 网关（v3.1）**：把 Session 1 留位的 `memory_search`/`memory_add`/
   `task_create` 包装接入真实实现（分别包装 /api/memories 与 /api/tasks）；
   MCP 调用必须经过与 /api 相同的 JWT 认证与 ACL 过滤
5. 前端骨架完成：登录/注册页、主布局三栏（左栏会话区+Agent区、主区聊天流、顶栏 Tab 容器）、聊天流组件（流式 SSE、消息气泡、@ 选择器、📎 上传、撤回按钮、IndexedDB 历史持久化）
6. 前端实现"任务 Tab"和"记忆 Tab"的完整功能（发起任务表单含 @引用文件/@引用记忆、任务列表状态徽标、产物预览/下载/分享、记忆搜索/新建/ACL 徽标）

**不做：**
- ❌ 不实现看板/画像/资料库/设置 Tab 页面（Session 3 的事；但 API 已在 Session 1 就绪，可留占位路由）
- ❌ 不做山河云台主题（二期）
- ❌ 不部署 Caddy 完整路由（Session 3 的事）

## 执行要求
1. 先实现后端三个模块（4.8→4.9→4.10），每个模块 curl 自测通过后再写前端
2. 闭环必须端到端自测：任务 1 完成→记忆出现→任务 2 引用→上下文生效
3. ACL 必须实测：A 建 private，B 检索不到
4. FTS5 中文用 trigram tokenizer（若环境不支持，给出替代并说明）
5. 前端聊天流与后端 /api/chat SSE 对接，懒启动"正在唤醒"提示必须显示

## 本批验收标准（全部通过才能交接）
1. 发起任务（选 Agent + @引用 1 个资料文件）→ queued → running → done；产物出现在列表，可预览/下载/分享
2. 同一 Agent 连发 2 任务，第 2 个排队并显示"前面还有 1 人"
3. 故意给不可能完成的任务 → failed + 错误信息，不卡死；Agent 明确"无法完成+原因"（D36 失败兜底）
4. 发起 requires_approval 任务（描述含"预算"）→ 完成后 waiting_approval → 审批"修改"+理由
   → task_corrections 有记录 → 再发同类任务，Agent 上下文含【相关修正记录】（D35，v3.2 验收）
5. 任务完成后 team-memory.db 自动出现 conclusion 记忆
6. 搜索"数值"能召回相关记忆；private/team/restricted ACL 实测生效
7. 任务 2 发起时 @引用任务 1 的记忆，执行时 Agent 上下文包含它（回复体现"基于上次分析"）
8. 前端：登录/注册可用；聊天流式可用；任务/记忆两个 Tab 完整可用（任务 Tab 含 waiting_approval 状态徽标与审批区）；刷新页面会话历史不丢
9. `reboot` 后服务恢复，闭环仍可跑通
10. **MCP 网关完整（v3.1）**：外部 MCP 客户端调用 `memory_search` 能按成员 token
    检索可见记忆（ACL 生效）；`task_create` 创建的任务出现在工作台任务列表

## 交接物（Session 2 结束必须输出）
1. 《核心闭环测试报告》：任务→记忆→引用 全流程截图/日志
2. 记忆库检索与 ACL 测试结果
3. **MCP 网关测试结果**：5 个工具全部可用、外部调用 ACL 生效的证据
4. 前端已完成页面清单 + 未完成清单
5. 给 Session 3 的注意事项（路由、组件复用、API 约定）

## 约束
- 严格按 4.8/4.9/4.10 的数据结构和 API 定义实现，不得自行简化
- 不改动 Session 1 已验收的后端代码（如需微调，记录 diff 并说明原因）
- 前端不接触密钥；决策清单不得偏离

---
