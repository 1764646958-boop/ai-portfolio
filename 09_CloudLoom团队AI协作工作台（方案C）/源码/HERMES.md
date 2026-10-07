# CloudLoom 团队工作台 · HERMES.md

> 团队机制总说明 + 行为边界总表
> 权威规格：/opt/team-console/SPEC.md（第 7 阶段 / D17 / D23-D26 / D29 / D34 / D35 / D36）
> 最后核对：2026-09-14。本文全部内容以服务器实际文件为准，不写入任何密钥、Token、密码与成员邮箱。

## 目录

1. 文档定位与维护须知
2. 团队机制总览：4 个预设 Agent
3. 行为边界总表（核心，D34）
4. 升级人审规则（D17 / D34 / D36）
5. 协作机制：Kanban 与任务状态机
6. 定时任务 cron（绑定 zhiban）
7. 团队记忆库机制（D24 / D25 / D26）
8. 入口唯一原则（D29）与模型切换
9. 自研层与 Hermes 的分工
10. 附：验收要点与不一致记录

---

## 一、文档定位与维护须知

本文是 CloudLoom 团队工作台的**团队机制总说明 + 行为边界总表**，面向两类读者：

- **后续维护者**：需要知道机制落在哪个文件、哪个端口、哪个 systemd 单元，改哪里生效。
- **团队成员与 Agent**：需要知道边界在哪、什么必须升级人审、失败时该走什么流程。

维护约定：

1. **第三章是验收项（D34）**。任何 Agent 的 SOUL.md 行为边界发生变化后，必须同步更新第三章，否则视为文档失效。
2. **本文只描述机制，不复制实现**。判定逻辑以代码为准，本文标注了对应文件路径，便于核对。
3. **脱敏要求**：本文不出现 API key、Token、密码、真实邮箱。涉及配置项时只写变量名。
4. **唯一入口**：团队全部操作都在 CloudLoom 工作台内完成（D29），本文不描述任何外部办公平台入口。

---

## 二、团队机制总览：4 个预设 Agent

团队名「楚华成章」，4 个预设 Agent 由 Hermes profile 承载，Profile 名用拼音、显示名用中文（D22）。
所有 SOUL.md 均位于 **/root/.hermes/profiles/<id>/SOUL.md**（已实际确认，4 份均存在）。

| 维度 | cehua | chengxu | pingshen | zhiban |
| --- | --- | --- | --- | --- |
| 显示名 | 策划Agent | 程序Agent | 评审Agent | 值班Agent |
| 职责 | 世界观 / 剧情 / 数值 | 架构 / 代码 / 技术评审 | 只读独立审查 | 晨报 / 周复盘 / 阻塞提醒 / 催办 / 调度协助 / D36 复核兜底 |
| SOUL.md | /root/.hermes/profiles/cehua/SOUL.md | /root/.hermes/profiles/chengxu/SOUL.md | /root/.hermes/profiles/pingshen/SOUL.md | /root/.hermes/profiles/zhiban/SOUL.md |
| systemd 单元 | hermes-gateway-cehua.service | hermes-gateway-chengxu.service | hermes-gateway-pingshen.service | hermes-gateway-zhiban.service |
| 端口（API_SERVER_PORT） | 8642 | 8643 | 8644 | 8645 |
| 模型 | deepseek-chat | deepseek-chat | deepseek-chat | deepseek-chat |
| provider | deepseek | deepseek | deepseek | deepseek |
| 常驻方式 | systemd 常驻 | systemd 常驻 | systemd 常驻 | systemd 常驻 |

补充说明：

- **端口与监听**：4 个 profile 的 .env 中 API_SERVER_ENABLED=true、API_SERVER_HOST=127.0.0.1，端口依次 8642-8645，仅本机回环可达；外部流量统一经自研代理层 8787 转发。API_SERVER_KEY 每 profile 独立，值已脱敏，不在此列出。
- **网关方式**：Hermes Gateway 以 systemd 托管，单元内 ExecStart 为 hermes_cli.main --profile <id> gateway run，并设置 HERMES_HOME=/root/.hermes/profiles/<id>。手工启停可用 hermes -p <id> gateway start|stop|restart。
- **共享环境注入**：4 个单元均有 drop-in /etc/systemd/system/hermes-gateway-<id>.service.d/10-cloudloom-env.conf，内容为 EnvironmentFile=/etc/hermes.env（B3）。该文件当前只定义 HERMES_KANBAN_BOARD=/root/.hermes/kanban.db，使 4 个 Agent 共用同一块 Kanban 看板（C1）。
- **模型与 provider 配置位置**：每个 profile 的 config.yaml 中 model 段，当前为 provider: deepseek、base_url: https://api.deepseek.com、default: deepseek-chat。API key 经 .env 的 DEEPSEEK_API_KEY 注入，值已脱敏。
- **邮件通道**：.env 中配置 EMAIL_SMTP_HOST=smtp.qq.com（465）、EMAIL_IMAP_HOST=imap.qq.com，账号与授权码已脱敏。N3 要求 cron 产出一律「写文件 + 发邮件」双通道。
- **非预设 Agent**：另有 testbot（8650，非预设，阶段 1 懒启动验收用），不属本节 4 个预设角色，其 SOUL.md 由创建接口的模板生成。

---

## 三、行为边界总表（核心，D34）

**核对结论：4 个预设 Agent 的 SOUL.md 均包含「【行为边界】」小节，无一缺失。** 下表逐条摘自各 SOUL.md 的该小节原文，仅将条目间的换行改为换行标记，未做任何改写、合并或润色。各行顺序与 SOUL.md 一致。

| 边界类别 | cehua（策划） | chengxu（程序） | pingshen（评审） | zhiban（值班） |
| --- | --- | --- | --- | --- |
| **可自主决定** | 撰写与修改非定稿状态的设定草案、剧情大纲、文案草稿<br>做数值试算、敏感性分析、平衡性推演（产出标注「试算稿」）<br>检索团队记忆库 / 资料库并引用既有决策<br>生成 2 个备选方案的对比表<br>整理归纳已有讨论，输出结构化摘要<br>把产物写入 ~/team-files/产出/<task_id>/ | 编写、调试、重构非关键路径的代码<br>做技术选型调研与方案对比（附复杂度 / 风险）<br>读代码、跑只读诊断命令、分析日志<br>撰写技术文档、接口说明、架构图描述<br>检索团队记忆库 / 资料库并引用既有技术决策<br>把产物写入 ~/team-files/产出/<task_id>/ | 读取任何团队文件、代码、产物进行审查<br>运行只读命令（cat / grep / git log / git diff / 静态检查）<br>输出问题清单与审查结论<br>检索团队记忆库 / 资料库核对既有决策<br>把审查报告写入 ~/team-files/产出/<task_id>/ | 读取 Kanban、团队文件、通知目录，生成晨报 / 周复盘 / 画像<br>写入 ~/team-files/系统通知/ 下的报告文件<br>发送例行通知邮件（晨报 / 周复盘 / 画像）<br>检索团队记忆库 / 资料库<br>复核其他 Agent 标记为「低置信」的产出并给出复核意见<br>协助拆解任务、建议优先级与路由目标 |
| **需升级人审** | **设计定稿**（D17 审批节点）：世界观根基设定、主线剧情走向、角色设定终稿<br>**预算相关**（D17 / D36 强制项）：任何涉及金额、成本、投入产出的内容<br>**对外承诺**（D17 / D36 强制项）：任何可能被理解为对合作方 / 玩家 / 外部团队承诺的表述<br>**删除数据**（D36 强制项）：删除或覆盖已有的设定、剧情、数值文件<br>任何与已定稿决策相冲突的修改<br>核心数值公式的结构性调整（非试算性质的） | **设计定稿**（D17 审批节点）：系统架构定稿、数据模型定稿、对外接口契约定稿<br>**预算相关**（D17 / D36 强制项）：涉及金额、云资源成本、采购与订阅的内容<br>**对外承诺**（D17 / D36 强制项）：对合作方 / 外部系统的技术承诺、交付时间承诺<br>**删除数据**（D36 强制项）：删除文件、清库、DROP / DELETE / rm -rf 类操作<br>**破坏性变更**：改接口签名、改数据库 schema、改部署方式、升级主版本依赖<br>任何会中断线上服务或影响其他 Agent 运行的操作 | **设计定稿**（D17 审批节点）：给出「定稿通过」结论前，须经团队负责人确认<br>**预算相关**（D17 / D36 强制项）：审查涉及金额、成本的内容时<br>**对外承诺**（D17 / D36 强制项）：审查将要对外发布的材料时<br>**删除数据**（D36 强制项）：认为某内容应当删除时 —— 只提建议，不得执行<br>审查结论为「阻塞」且双方争执不下时，升级人工裁决 | **设计定稿**（D17 审批节点）：复核涉及定稿内容的产出时，须经团队负责人确认<br>**预算相关**（D17 / D36 强制项）：报告中涉及金额、成本、投入产出时<br>**对外承诺**（D17 / D36 强制项）：任何将对外发送的催办 / 通知内容涉及承诺时<br>**删除数据**（D36 强制项）：需要清理过期通知或产物时 —— 只提建议，不得自行删除<br>发现严重阻塞且责任人未响应时，升级人工介入<br>需要代其他 Agent 做决策时（你只协助调度，不替人拍板） |
| **禁止事项** | 未经负责人确认，擅自宣布任何产出为「定稿」<br>删除或覆盖 ~/team-files/ 下的既有产物<br>代表团队对外发布内容、做出承诺或报价<br>编造未经确认的设定并当作既定事实陈述<br>修改其他 Agent 的 SOUL.md 或配置文件<br>绕过审批流程，把需要人审的内容直接交付 | 在未获批准时执行破坏性变更<br>执行 rm -rf、DROP TABLE、TRUNCATE、批量 DELETE 等不可逆数据操作<br>把密钥、Token、密码写进代码、日志、产物或对话<br>修改其他 Agent 的 SOUL.md 或配置文件<br>绕过评审直接把变更合入主分支<br>用「大概」「应该可以」掩盖未验证的技术结论 | 修改、删除、重命名任何被审查对象（你是只读的）<br>直接执行修复 —— 哪怕改动只有一行<br>在未充分阅读的情况下给出「通过」<br>使用「感觉」「可能」「建议再确认下」等无法执行的模糊结论代替三要素清单<br>因人情、时间压力或「看起来差不多」而放宽阻塞级问题<br>修改其他 Agent 的 SOUL.md 或配置文件 | 编造或美化进度、风险、完成度等任何汇报数据<br>未实际扫描就生成报告<br>只写文件不发邮件（N3 要求双通道）<br>删除或覆盖 ~/team-files/ 下的既有产物<br>代表团队对外做出承诺<br>修改其他 Agent 的 SOUL.md 或配置文件<br>高频轰炸式催办（同一事项在合理间隔内不重复提醒） |
| **失败兜底** | **信息不足**：明确列出「我缺什么信息」+「需要谁补充」，不猜测、不用占位内容填充<br>**任务做不了**：直接说明「无法完成 + 具体原因」，不硬编、不糊弄<br>**与既有决策冲突且无法判断**：标注冲突点，转 pingshen 复核，或升级 zhiban 转人工<br>**低置信产出**：在回复开头显式声明「低置信」，并按 D36 交由 zhiban 复核后再交付 | **未确认的技术细节**：显式标注「未确认」，并给出验证方法，不当作事实陈述<br>**任务做不了**：说明「无法完成 + 具体原因 + 已尝试的路径」，不硬编、不交半成品<br>**方案存在硬风险**：如实上报风险与代价，把决策权交回负责人，不替团队拍板<br>**低置信产出**：在回复开头显式声明「低置信」，并按 D36 交由 zhiban 复核后再交付 | **信息不足无法判断**：明确写「无法判定 + 缺少什么材料」，不硬给通过<br>**超出专业范围**：说明「这超出我的审查范围」，转交对应角色（策划 → cehua，技术 → chengxu）<br>**审查对象不存在或读不到**：如实报告，不臆测内容<br>**低置信结论**：在结论处显式声明「低置信」，并按 D36 交由 zhiban 复核 | **写文件失败**：仍必须发出邮件，并在邮件正文中说明文件写入失败及原因（N3）<br>**发邮件失败**：保留文件产物，在下次运行报告中标注上次邮件发送失败<br>**数据源读不到**：如实标注「本次未能读取 X」，不用旧数据冒充新数据<br>**任务做不了**：说明「无法完成 + 具体原因」，转人工处理，不静默跳过<br>**复核无法判定**：不强行放行，退回原 Agent 补充信息或升级人工 |

### 3.1 边界共性（以下为归纳，非原文）

- **三条硬红线四方一致**：涉及金额/预算/成本、对外承诺、删除数据（D36 三类）一律升级人审，无一例外。
- **禁止清单的公共项**：4 份 SOUL.md 均明文禁止「修改其他 Agent 的 SOUL.md 或配置文件」；cehua/chengxu/zhiban 均禁止「代表团队对外做出承诺」。
- **低置信兜底是统一回路**：cehua / chengxu / pingshen 的失败兜底最后一条均为「声明低置信 → 按 D36 交 zhiban 复核」；zhiban 则是该回路的承接方（复核无法判定时不放行）。
- **只读约束最严的是 pingshen**：唯一一个被 SOUL.md 明确写为「你是只读的」，连一行修复都不允许直接执行。
- **上表与系统联动**：任务执行时，后端会把该 Agent 的这段边界原文抽出注入指令（见第三章代码路径 /opt/team-console/server/src/tasks.js 的 extractBoundary，按「【行为边界】」标记截取到下一个二级标题），因此 SOUL.md 的措辞会直接影响 Agent 行为。

---

## 四、升级人审规则（D17 / D34 / D36）

### 4.1 两条来源

| 来源 | 内容 | 落地方式 |
| --- | --- | --- |
| D17（审批节点） | 设计定稿 / 预算 / 对外承诺 必须人工确认 | 写入各 SOUL.md 的「需升级人审」清单，由 Agent 自觉声明 |
| D36（不确定性升级） | 涉金额 / 对外承诺 / 删除数据三类任务**强制** requires_approval=1；Agent 自评低置信时自动转 zhiban 复核 | 由后端**硬判定**，不依赖 Agent 自觉 |

关键差别：D17 靠 Agent 声明，D36 由代码强制。只要任务文本命中关键词，无论 Agent 怎么想，任务执行完都会停在 waiting_approval，不进 done。

### 4.2 D36 强制人审的真实触发规则

判定代码：**/opt/team-console/server/src/tasks.js**（APPROVAL_RULES / detectSensitive / hitWord）。

- **扫描范围**：任务标题 + 任务描述，再拼接「引用资料的文件名」与「引用记忆的标题」（引用对象查不到时留空，不影响主流程）。
- **匹配方式**：全文转小写后做子串包含匹配，因此英文关键词大小写不敏感（DROP / drop 都会命中）。
- **词例外**：WORD_EXCEPTIONS 规定「客户」在「客户端」这一完整词中出现时不算命中（避免误触发对外承诺）。
- **结果**：命中任一类别即 requires_approval=1，并把命中类别以 approval_forced_by 记录到任务 meta，前端可显示「因何触发」。

| 类别（kind） | 触发词（逐字，来自代码） |
| --- | --- |
| 金额 | 金额、预算、报价、费用、成本、定价、价格、付款、支付、发票、万元、合同额 |
| 对外承诺 | 对外、承诺、合同、签约、客户、甲方、乙方、发布、公告、公开、上线通知 |
| 删除数据 | 删除、清除、销毁、清空、卸载、覆盖、drop、delete、truncate |

补充：

- **发起人主动勾选**也会置 requires_approval=1（发起时传 requires_approval 字段）。即：代码判定 与 人工勾选，两者取或。
- 命中类别仅用于提示与记录；**只要命中任意一类，审批流程完全相同**。

### 4.3 审批怎么走

1. 任务执行完成时，后端根据 requires_approval 决定落点（tasks.js 的 finishSuccess）：需要审批 → status=waiting_approval、approval_status=pending、**不写 completed_at、不沉淀记忆**；否则 → status=done 并触发记忆沉淀。
2. 前端任务详情在 waiting_approval 时出现审批区，提供「通过 / 修改 / 打回」三选，**理由 note 必填**。
3. 接口：POST /api/tasks/:id/approval，body 为 action 与 note；**仅任务创建者或管理员**可操作（D35）。
4. 三种动作的真实后果（tasks.js）：
   - **approve（通过）**：写 task_corrections；status=done、approval_status=approved、记录 approved_by；**此时才触发记忆沉淀**，并把审批意见作为修正摘要写入 conclusion 记忆。
   - **modify（修改）**：写 task_corrections；status 回到 queued、approval_status=modified、correction_note 落库，任务**带修正意见重新执行**。
   - **reject（打回）**：写 task_corrections；status=failed、approval_status=rejected、记录 correction_note 与 error；**失败不沉淀记忆**。
5. 非 waiting_approval 状态调用审批接口会被拒绝。

---
### 4.4 修正记录如何回流（D35）

审批动作不会随任务结束而消失，而是落库后在**下一次同类任务**执行前回灌给 Agent：

- **落库表**：task_corrections(id, task_id, agent_id, action, note, decided_by, created_at)，action 取值 approve / reject / modify。库文件位于自研层 data 目录下的 tasks.db，由 tasks.js 建表与维护。
- **回流范围**（tasks.js 的 buildCorrections）：**同一 Agent**、**最近 30 天**内的修正记录，按时间倒序取**最多 5 条**，再翻转为正序，避免倒装阅读。
- **注入位置**：任务指令中的「【相关修正记录】」段落，排在【引用资料】【引用记忆】之后、【行为边界】之前；无记录时写明「（无）」。
- **格式**：每条为「- [动作] 修正意见（决策人，日期）」，让 Agent 一眼看到「上次被谁、以什么理由改了什么或打回了什么」。
- **闭环要求**（SPEC 验收）：发起一个被打回/修改过的同类任务时，Agent 的回复或产物应体现「避免上次被否的点」。
- **沉淀关联**：审批通过时，审批意见会作为【审批修正】一行写入该任务的 conclusion 记忆，使修正内容既在任务侧回流、也在记忆侧可检索。

### 4.5 低置信任务的处理（D36）

- Agent 在任务回复的最后一行须给出交付状态标记，三选一：【交付状态】完成 / 【交付状态】无法完成：原因 / 【交付状态】低置信：存疑说明。
- 被判定为低置信的任务，后端转 **zhiban（值班 Agent）复核**：复核通过后才进入审批或完成流程。
- 若复核环节不可用（转派失败），后端会**强制**将该任务置为 requires_approval=1，并在 meta 记录 force_approval_reason（形如「低置信且复核不可用：原因」），**退化为人工审批**，不允许低置信产出静默通过。
- 复核兜底能力已写入 zhiban 的 SOUL.md 职责范围（D36），且 zhiban 的边界写明「复核无法判定：不强行放行，退回原 Agent 补充信息或升级人工」。

---

### 4.6 交付状态标记的解析细节（实现补充）

- 判定优先看回复中的 **【交付状态】标记**，且**取最后一次出现**（避免 Agent 引用原文或自我否定如「我不写『无法完成』」造成误判）。
- 标记缺失时退化为关键词启发式：命中「无法完成」类表达判为无法完成，命中「低置信 / 无法高置信完成 / 无法确认」类表达判为低置信，否则判为完成；启发式带否定语境排除。
- **无法完成**：直接置 status=failed，error 记录「Agent 声明无法完成：原因」，**不沉淀记忆**。
- **低置信**：转 zhiban 复核，复核只输出一行 JSON（verdict 为 pass 或 reject）。reject → status=failed；pass → 继续正常交付流程；复核不可用（unknown）→ **强制 requires_approval=1** 并写入 force_approval_reason，**绝不静默自动交付**。

## 五、协作机制：Kanban 与任务状态机

### 5.1 Kanban 看板（C1）

- **一块看板，四方共用**：4 个 profile 通过 /etc/hermes.env 的 HERMES_KANBAN_BOARD=/root/.hermes/kanban.db 指向同一个 SQLite 看板文件，因此任一 Agent 建的任务其他 Agent 与成员都能看到。
- **建看板/建任务**（部署第 7 阶段原文用法）：hermes kanban init；hermes kanban create 「任务标题」 --body 「描述」 --assignee 「负责人」。
- **典型用法**：把「剧情系统设计」「美术规范」「对话框架」「数值表 V2」等事项建卡并指派到对应 Agent/成员；zhiban 每日扫描看板汇总进行中/阻塞/待拍板。
- **工作台侧**：看板 Tab 经自研代理层读取并展示；MCP 网关另暴露 kanban_list 工具供外部调用（见第九章）。

### 5.2 任务状态机（D23，含 v3.2 审批扩展）

状态取值固定 5 个：**queued / running / waiting_approval / done / failed**（tasks.js 的 STATUSES）。

| 当前状态 | 触发 | 迁移到 | 说明 |
| --- | --- | --- | --- |
| （无） | 发起任务 | queued | 入该 Agent 队列；同一 Agent 同时只跑 1 个任务，其余排队并显示「前面还有 N 人」（D11） |
| queued | 轮到执行 | running | 组装指令（引用资料/引用记忆/相关修正记录/行为边界/交付要求）发给该 Agent |
| running | 执行成功且无需人审 | done | 扫描并登记产物；**触发 conclusion 记忆沉淀** |
| running | 执行成功但 requires_approval=1 | waiting_approval | approval_status=pending；**不沉淀记忆**，等人工审批 |
| running | 执行失败 | failed | 写 error 信息；**失败不沉淀结论记忆** |
| running | 自评低置信 | （转 zhiban 复核） | 复核通过后进入 done 或 waiting_approval；复核不可用则强制 requires_approval |
| waiting_approval | 审批通过 approve | done | 落 task_corrections；此时才沉淀记忆，审批意见入 conclusion |
| waiting_approval | 审批修改 modify | queued | 带 correction_note 重新执行 |
| waiting_approval | 审批打回 reject | failed | 记录 correction_note 与 error |
| queued / running / waiting_approval | 发起人/管理员取消 | failed | 仅创建者或管理员可取消 |

产物落点：全部交付物写 **~/team-files/产出/<task_id>/**（支持子目录），后端完成后立即扫描该目录并登记到 outputs 表，前端据此提供预览/下载/分享到会话。

---

## 六、定时任务 cron（绑定 zhiban）

三个定时任务全部绑定 **zhiban**，配置文件为 **/root/.hermes/profiles/zhiban/cron/jobs.json**（该文件为 unicode 转义存储，读取时需还原中文）。任务本身不接受独立去重逻辑，依赖 Hermes 的 tick lock（.tick.lock）与心跳文件（ticker_heartbeat / ticker_last_success）防止重复触发，执行历史落在同目录 executions.db。

| 名称 | 计划表达式 | 提示词（逐字，来自 jobs.json） | 产物落点 |
| --- | --- | --- | --- |
| 晨报 | 0 9 * * * | 扫描Kanban看板，汇总【进行中/阻塞/待拍板】三类事项，并给出今日建议关注。用 file 工具把结果写入 ~/team-files/系统通知/晨报-YYYYMMDD.md（YYYYMMDD 用当天日期）；同时发送邮件通知（N3：即... | ~/team-files/系统通知/晨报-YYYYMMDD.md + 邮件 |
| 周复盘 | 0 10 * * 1 | 本周复盘：输出【完成/阻塞/风险/下周计划/机制改进建议】，写入 ~/team-files/系统通知/周复盘-YYYYMMDD.md；同时发送邮件通知（N3：即使写文件失败也必须发邮件）。 | ~/team-files/系统通知/周复盘-YYYYMMDD.md + 邮件 |
| 画像 | 0 6 * * * | 汇总每位成员近期协作记录，生成成员画像 JSON，写入 ~/team-files/系统通知/画像/画像-YYYYMMDD.json；同时将重要偏好同步为 type=preference 记忆。 | ~/team-files/系统通知/画像/画像-YYYYMMDD.json + 偏好记忆 |

运行事实与约定：

- **执行频率与状态**：晨报（0 9 * * *，已运行且 last_status=ok）、画像（0 6 * * *，已运行且 last_status=ok）、周复盘（0 10 * * 1，尚未到首次触发时间）。三者 enabled=true、state=scheduled、deliver=local。
- **模型快照**：三个任务创建时记录 provider_snapshot=deepseek、model_snapshot=deepseek-chat（即运行模型随创建时的配置走，与第八章的切换方式相关）。
- **双通道（N3）**：cron 产出一律先写文件、再发邮件；**即使写文件失败也必须发出邮件**，并在邮件正文说明写入失败及原因。这条同时写进了 zhiban 的 SOUL.md 工作方式与行为边界。
- **固定命名**：晨报 → 晨报-YYYYMMDD.md；周复盘 → 周复盘-YYYYMMDD.md；画像 → 画像/画像-YYYYMMDD.json。命名格式由 SOUL.md 明文固定，便于下游按名检索。
- **打扰克制**：zhiban 的 SOUL.md 要求只对真正需要人介入的事项提醒，同一事项在合理间隔内不重复提醒。

> 注意：晨报任务的提示词在 jobs.json 中即以省略号结尾（长度 151 字符，原文如此，非本文截断）——见第十章不一致记录第 1 条。

---

## 七、团队记忆库机制（D24 / D25 / D26）

### 7.1 存储与检索

- 自研 SQLite 记忆库（data/team-memory.db），带 **FTS5（trigram）全文索引**，不依赖 TencentDB（D24）。当前为关键词检索，语义/向量检索列入二期。
- 实现文件：**/opt/team-console/server/src/memories.js**（含 4.10 沉淀入口与 4.11 MCP 的 searchMemories / insertMemory）。

### 7.2 记忆类型（TYPES，逐字来自代码）

decision（决策） / preference（偏好） / fact（事实） / conclusion（结论）。

- 创建时 type 必须是这 4 个之一，否则接口报错（type 须为 decision|preference|fact|conclusion）。
- 任务完成自动沉淀的记忆，type 固定为 **conclusion**。
- 画像 cron 会把重要偏好同步为 **type=preference** 记忆。

### 7.3 三种可见范围（D25 ACL，真实语义）

可见性取值：**private / team / restricted**。判定函数为「可见 = 我是作者 或 visibility=team 或（visibility=restricted 且我在 allow_members 中）」，其余一律不可见。

| 可见性 | 真实语义 | 备注 |
| --- | --- | --- |
| private | 仅作者本人可见 | 作者之外任何人（含管理员）在检索与展示中均被过滤掉 |
| team | 全员可见 | 默认值；发起任务时若未指定，沉淀记忆按 team 落库 |
| restricted | 仅 allow_members 名单内的成员可见 | **必须至少指定 1 位成员**，否则创建/更新接口直接报错 |

补充与降级规则：

- **检索即过滤**：搜索接口先按调用者身份做 ACL 过滤，再叠加 type / visibility / limit 条件，因此外部通过 MCP 检索也自动继承同一套 ACL。
- **沉淀时的降级**：任务沉淀记忆时若可见性为 restricted 但未指定成员，后端会自动降级为 **private**，并在任务 meta 记录说明（restricted 未指定成员，已按 private 处理），避免出现「谁也看不到」的悬空记忆。
- **共享会话**：记忆 Tab 的展示、任务发起时的「@引用记忆」选择列表，均按当前登录用户的可见范围过滤。

### 7.4 任务完成自动沉淀 conclusion 的闭环（D26）

链路：**任务完成（含审批通过）→ 自动写入 conclusion 记忆 → 下次发起任务时可检索并引用 → Agent 带历史上下文执行。**

- **触发时机**（tasks.js）：无需人审的任务在 done 时触发；需人审的任务要等 approve 通过后才触发。**失败任务与 waiting_approval 任务不沉淀**。
- **幂等**：以 source_task_id 判重，同一任务重复触发会跳过，不会产生重复记忆。
- **记忆内容结构**（precipitateTaskMemory）：【任务】标题、【描述】、【执行 Agent】、【结论】执行结果摘要（截断 800 字）、【产物路径】~/team-files/产出/<task_id>/；若为审批通过，追加一行【审批修正】审批意见。
- **标签**：以任务标题与 Agent 名为基础标签，并追加产物文件扩展名（如 md / json），便于按类型召回。
- **归属字段**：记录 source_task_id 与 source_agent，可反查该记忆源自哪个任务、由哪个 Agent 产出。
- **引用回流**：下次发起任务时勾选该记忆，后端会把记忆条目标题与内容（截断 1500 字）拼进指令的【引用记忆】段落，交付要求明确要求 Agent 在回复中体现引用依据。

---

## 八、入口唯一原则（D29）与模型切换

### 8.1 入口唯一（D29 / D27）

- **成员只面对工作台一个界面**：聊天、任务、记忆、看板、资料库全部在 CloudLoom 工作台内完成，不引入 WorkBuddy 或任何外部办公工作台（D27）。
- **外部平台均为可换零件**：Hermes、模型 provider、外部 MCP server 都是可替换组件，替换过程不改成员入口。
- **验收口径**：全程无外部办公工作台依赖；模型切换在配置层完成，前端入口不变。

### 8.2 换模型 / 换 provider 的真实做法

配置分两层：**provider 与模型名写在 profile 的 config.yaml**，**密钥写在 profile 的 .env**（经环境变量注入，不落前端、不进代码）。

| 场景 | 做法 |
| --- | --- |
| 改单个 Agent 的模型 | 编辑该 profile 的 config.yaml 中 model 段（provider / base_url / default），或在命令行执行 hermes -p <id> config set model.default <模型名> |
| 改 provider | 同上，设置 model.provider 与 model.base_url；SPEC 给出的等价形式为 hermes config set model.provider deepseek |
| 更换密钥 | 推荐一条命令改全 7 处（`bash /opt/team-console/ops/rotate-deepseek-key.sh <新Key>`：逐文件备份 → 同步 `/root/.hermes/.env`、5 个 profile `.env`、`/etc/hermes.env` → 保持 600 → 复位凭据池 → 重启 4 个网关 → 核验单元/健康/余额；全程不回显密钥）。手工做法为改该 profile 的 `.env` 中对应变量（如 `DEEPSEEK_API_KEY`），**变量值不写入本文、不写入任何文档**；改后重启对应 gateway |
| 交互式选择 | 可用 hermes model 按提示选择模型（以本机 hermes 实际 CLI 输出为准） |
| 生效方式 | 重启对应 systemd 单元：systemctl restart hermes-gateway-<id>（<id> 取 cehua / chengxu / pingshen / zhiban） |
| 全部切换 | 对 4 个 profile 的 config.yaml / .env 各改一次并重启 4 个单元；前端与成员无感知 |
| 自动兜底 | config.yaml 中预留 fallback_model 段（默认注释未启用），可在主 provider 限流/故障时自动切换；启用时同样只改配置层 |

注意事项：

- **不要在系统提示词或 SOUL.md 里写模型名**：模型由配置层决定（D29），写死在人格文件里会导致换模型时行为不一致。
- **cron 任务带模型快照**：zhiban 的三个定时任务在创建时记录了 provider_snapshot / model_snapshot（当前均为 deepseek / deepseek-chat），换模型后如需定时任务跟随新模型，需重建或更新该任务。
- **密钥只进 .env**：.env 与 agents.json 属敏感文件，禁止复制进文档、日志、产物或对话。
- **凭据池 exhaustion（S4.0 实测坑）**：余额耗尽时 Hermes 会把该凭据记入 profile 的 `auth.json` → `credential_pool` 并标记 `exhausted`，**充值后不一定自动恢复**（实测 2026-09-14 三作业连续 402）。处理：`hermes --profile <id> auth reset deepseek`（轮换脚本已含此步，也可用 `hermes --profile <id> auth list` 查看状态），随后手动触发一次作业验证。
- **定时作业是否在跑，看得见**：`ops-check.timer` 每 15 分钟巡检（作业失败/余额/单元/端口/健康/磁盘），异常写入 `~/team-files/系统通知/运维告警-<YYYYMMDD-HHMM>.md`（工作台通知流可见），正常时零输出；同一问题 6 小时内不重复告警。

---

### 8.3 技能（skills）的检索与安装（S4.0 / B4 实测）
Hermes 的技能可来自多个注册源（skills.sh / well-known / GitHub / ClawHub / lobehub 等）。**默认 `--source all` 在本机会永久卡住**（根因见下），因此检索必须显式指定可用的源。

| 步骤 | 命令（实测可用） |
| --- | --- |
| 检索 | `hermes skills search <关键词> --source official --limit 10`（`skills-sh` / `well-known` / `lobehub` 同样可用；**不要用默认 all，也不要单用 github / clawhub**） |
| 安装 | `hermes --profile <id> skills install <identifier> --yes`，例：`hermes --profile cehua skills install official/creative/concept-diagrams --yes` |
| 确认 | `hermes --profile <id> skills list`（新增项应显示 `enabled`） |
| 生效 | **必须重启该 Agent 的网关**：`systemctl restart hermes-gateway-<id>`（技能索引在网关启动时构建，**不热加载**） |

**根因（S4.0 / B4 实测）**：`hermes skills search` 的默认 `--source all` 会把 `github`、`clawhub` 两个源一并查询，而 CLI 对这两个源未设连接/读取超时；本机 `raw.githubusercontent.com` 不可达（`curl --max-time 8` → HTTP 000），于是整个命令**永久阻塞**（表现为「静默返回空 / 一直不返回」）。逐源实测：`official` / `skills-sh` / `lobehub` / `well-known` 正常返回；`clawhub` / `github` 阻塞（退出码 124 = 超时）。

**已装示例**：`official/creative/concept-diagrams`（生成扁平、极简、自适应浅色/深色主题的 SVG 图）已装到 cehua，落地于 `/root/.hermes/profiles/cehua/skills/creative/concept-diagrams/SKILL.md`（含 templates / examples / references，共 19 个文件）；安装时会自动做溯源扫描（`skills-guard-v1` + sha256 记录）。

注意事项：
- **安装后不重启网关 = Agent 看不到**：实测重启前 Agent 回答「没有任何名字含 concept 的技能」，重启后正确报出该技能及用途。
- 不要改 Hermes 自身源码去改默认源行为（升级会被覆盖）；使用方显式带 `--source` 即可。
- 技能是**加法**：新增技能不改动既有 Agent 行为；不再需要时用 `hermes skills uninstall` 移除。
- 镜像/出网相关：本机 `raw.githubusercontent.com` 不可达属机房出网限制，非本机可改；这会影响一切依赖 GitHub raw 的功能（如按 `owner/repo/name` 形式的技能安装）。

---
## 九、自研层与 Hermes 的分工

一句话：**Hermes 负责「让 Agent 干活」，自研层负责「让团队协同」**。两者以接口为界，前端只与自研层对话。

| 能力 | 归属 | 落点 |
| --- | --- | --- |
| Agent 人格与执行 | Hermes | 4 个 profile 的 SOUL.md + Hermes Gateway（8642-8645） |
| 工具调用与技能（Skill） | Hermes | profile 的 skills 目录；N1 要求至少安装 1 个示例技能验证链路 |
| 定时任务调度 | Hermes | zhiban 的 cron（jobs.json、tick lock、executions.db） |
| 看板存储 | Hermes | 共享 Kanban（HERMES_KANBAN_BOARD=/root/.hermes/kanban.db） |
| 邮件发送 | Hermes | 由 Agent 经 .env 中的 SMTP 配置发送（N3 双通道） |
| 鉴权与会话 | 自研层 | 成员账号、登录态、会话与消息 |
| 任务中心 | 自研层 | data/tasks.db，tasks / task_corrections / outputs 三表，状态机与审批 |
| 团队记忆库 | 自研层 | data/team-memory.db，memories 表 + FTS5 + ACL |
| 看板读取 | 自研层 | 读共享 Kanban 并在工作台展示 |
| 资料库 | 自研层 | 文件上传、网盘链接、引用清单 |
| MCP 网关 | 自研层 | 8787 上的 /mcp 端点，对外暴露团队能力、对内可接外部 MCP server（D28） |
| 统一入口与静态站点 | 自研层 | team-console.service（API 8787 + MCP + 静态 3000） |

MCP 网关对外暴露的工具（均包装既有 /api 实现，不改业务逻辑，认证与 ACL 保持一致）：

- memory_search(query, type?, limit?) → 包装 GET /api/memories
- memory_add(type, title, content, ...) → 包装 POST /api/memories
- task_create(title, description, ...) → 包装 POST /api/tasks
- kanban_list(status?) → 包装 GET /api/kanban
- file_search(keyword?) → 包装 GET /api/files

设计意图：任何外部 Agent（Claude Code / Codex 等）带上成员 token 即可通过标准 MCP 协议使用「团队记忆 / 任务」，即团队记忆即服务；同时 Hermes 侧保留 hermes mcp add 接入外部 MCP server 的能力（默认关闭，按触发条件启用）。

边界提醒：**自研层不实现 Agent 推理，Hermes 不实现团队权限**。因此改人格改 Hermes 侧 SOUL.md，改权限与状态机改自研层代码，两者不要互相越界。

---

## 十、附：验收要点与不一致记录

### 10.1 D34 / D36 验收要点速查

| 验收项（SPEC） | 现状 | 依据 |
| --- | --- | --- |
| 4 个预设 Agent 的 SOUL.md 均含「行为边界」小节（可自主 / 需升级人审 / 禁止 / 失败兜底） | **满足，4/4 全部包含**；testbot（非预设）由模板生成亦包含 | 见第三章核对结论 |
| HERMES.md 有边界总表 | 满足，即本文第三章 | 本文 |
| 给 Agent 下「删除某文件 / 对外承诺 / 报预算」类指令 → 任务自动 requires_approval | 满足，由后端关键词硬判定，不依赖 Agent 自觉 | tasks.js 的 APPROVAL_RULES / detectSensitive |
| 给不可能完成的任务 → Agent 明确「无法完成 + 原因」，不硬编 | 满足，且后端会把该任务置 failed 并记录原因 | tasks.js 的 classifyReply / finishFailed |
| 发起含「预算」的任务 → 执行完为 waiting_approval，前端出现审批区 | 满足 | tasks.js 的 finishSuccess 与审批接口 |
| 审批「修改」并填理由 → 写入 task_corrections；再次发起同类任务时上下文出现【相关修正记录】 | 满足，回流窗口为同 Agent 近 30 天最近 5 条 | tasks.js 的 buildCorrections / buildInstruction |

### 10.2 核对结论与不一致记录

| 编号 | 项目 | 结论 |
| --- | --- | --- |
| 1 | **晨报 cron 提示词被截断** | jobs.json 中晨报 prompt 长度为 151 字符，**以「（N3：即...」的省略号结尾，原文即不完整**，缺少双通道要求的完整表述；SPEC 第 7 阶段的建任务示例同样以省略号截断，属沿用了截断文本。**建议补全该 prompt**（写文件 + 必发邮件），否则晨报在写文件失败时可能不触发邮件兜底。 |
| 2 | 周复盘任务尚未首次执行 | completed=0、last_run_at=null，属未到触发时间（每周一 10:00），非故障。 |
| 3 | 画像任务 | 已执行且 last_status=ok，产物目录 ~/team-files/系统通知/画像/ 已存在。 |
| 4 | SOUL.md 行为边界缺失情况 | **无缺失**：cehua / chengxu / pingshen / zhiban 四份均含完整四段（可自主 / 需升级人审 / 禁止 / 失败兜底）。 |
| 5 | 敏感信息存储 | agents.json 中每个 Agent 的 api_server_key 为明文存储；4 个 profile 的 .env 共用同一邮箱账号且存放 provider 密钥。**本文已全部脱敏**，请勿将这两个文件内容复制进文档或日志。 |
| 6 | 邮箱账号共用 | 4 个 profile 使用同一发件邮箱地址；如后续需区分来源，建议改为按 Agent 使用别名或集中经环境变量注入。 |
| 7 | 端口占用 | 预设占 8642-8645，另有 testbot 占 8650，与 SPEC「8642-8645 + 8650+」一致。 |
| 8 | 常驻内存风险 | N3 注记：2 核 4G 常驻 4 个实例内存偏紧，若 OOM 需将低频预设 Agent 改懒启动，结论应写进部署报告。 |

### 10.3 本文核对依据

本文内容来自以下服务器文件的**实际读取**（核对时间 2026-09-14）：

- 规格：/opt/team-console/SPEC.md（第 7 阶段、决策表 D17 / D23-D29 / D34-D36、4.8-4.11 章节）
- 人格：/root/.hermes/profiles/{cehua,chengxu,pingshen,zhiban}/SOUL.md（行为边界逐字引用）
- 服务：/etc/systemd/system/hermes-gateway-{cehua,chengxu,pingshen,zhiban}.service 及其 drop-in、/etc/hermes.env
- 配置：各 profile 的 config.yaml（model 段）与 .env（变量名，值已脱敏）
- 注册表：/opt/team-console/agents.json（端口与显示名；密钥已脱敏）
- 后端：/opt/team-console/server/src/tasks.js（状态机 / 审批 / 修正回流 / D36 判定）、memories.js（类型 / ACL / 沉淀）
- 定时：/root/.hermes/profiles/zhiban/cron/jobs.json（unicode 转义，已还原中文）
- 目录：/root/team-files/（产出、系统通知、资料库）

**维护提醒**：修改 SOUL.md 行为边界、tasks.js 判定词表或 memories.js 可见性规则后，请同步更新本文第三章 / 第四章 / 第七章。

## S4.1 按需作业入口（省 token：想看就点一下，不点不花钱）

| 命令 | 作用 | 花费 |
|---|---|---|
| `python3 /opt/team-console/ops/digest.py` | 生成当日数据快照（看板/未读/本周新增/花费/余额），落 `~/team-files/系统通知/快照-YYYYMMDD.md` | **0**（不调 LLM） |
| `python3 /opt/team-console/ops/digest.py --cost-only` | 只打印【本周花费】段（含按 Agent/成员 Top5） | **0** |
| `python3 /opt/team-console/ops/digest.py --stdout` | 不落盘，直接打印全文 | **0** |
| `bash /opt/team-console/ops/run-job.sh weekly` | 立即跑一次周报（AI 版，含上周复盘） | ≈¥0.069/次 |
| `bash /opt/team-console/ops/run-job.sh profile` | 立即刷新团队画像 JSON | ≈¥0.09/次 |
| `python3 /opt/team-console/ops/mail.py --subject S --body T` | 出站邮件自检/发信（复用现有 SMTP） | 0 |

- 定时侧只有两条 cron：每日 `0 6 * * *` 快照（脚本作业，0 token）与每周一 `0 9 * * 1` 周报（AI）。原「画像每日 cron」已取消，改按需（负责人决策 B3）；原「周复盘」已并入周报（决策 A1）。
- 用量记账：`usage_log`（`/opt/team-console/data/conversations.db`），单一记账点 `server/src/usage.js`；`est_cost` 为**上界估算**（未拆分缓存命中）。
