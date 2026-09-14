# -*- coding: utf-8 -*-
"""李倍旭 · AI 应用作品集 —— PDF 生成脚本（2026-09 六段式版）
设计：reportlab + 等线（Deng）；六段式决策叙事；双旗舰 + 特色 + 佐证结构。
用法：python generate_portfolio.py
输出：同目录 李倍旭-AI作品集（2026-09）.pdf
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, KeepTogether, HRFlowable)

HERE = os.path.dirname(os.path.abspath(__file__))
# 设 PORTFOLIO_PUBLIC=1 生成「公开版」（仅邮箱、无手机号），用于公开仓库/网页分发
PUBLIC = os.environ.get('PORTFOLIO_PUBLIC') == '1'
OUT = os.path.join(HERE, '李倍旭-AI作品集（2026-09·公开版）.pdf' if PUBLIC
                   else '李倍旭-AI作品集（2026-09）.pdf')

# ---------- 字体（等线，回退黑体） ----------
FONT_DIR = r'C:\Windows\Fonts'


def reg(name, fname, fallback='simhei.ttf'):
    p = os.path.join(FONT_DIR, fname)
    if not os.path.exists(p):
        p = os.path.join(FONT_DIR, fallback)
    pdfmetrics.registerFont(TTFont(name, p))


reg('Deng', 'Deng.ttf')
reg('Deng-Bold', 'Dengb.ttf')
pdfmetrics.registerFontFamily('Deng', normal='Deng', bold='Deng-Bold',
                              italic='Deng', boldItalic='Deng-Bold')

ACCENT = colors.HexColor('#2C5F8D')
DARK = colors.HexColor('#1A1A1A')
GRAY = colors.HexColor('#6B7280')
LIGHT = colors.HexColor('#F4F6F8')
LINE = colors.HexColor('#D6DBE1')


def st(name, size, leading, color=DARK, bold=False, align=TA_LEFT):
    return ParagraphStyle(name, fontName='Deng-Bold' if bold else 'Deng',
                          fontSize=size, leading=leading, textColor=color, alignment=align)


S_NAME = st('name', 19, 23, DARK, True)
S_SUB = st('sub', 11, 14.5, ACCENT, True)
S_CONTACT = st('contact', 8.3, 12, GRAY)
S_BODY = st('body', 9.3, 14.6, DARK, align=TA_JUSTIFY)
S_H2 = st('h2', 11.5, 15, ACCENT, True)
S_PTITLE = st('ptitle', 11.8, 15.5, DARK, True)
S_META = st('meta', 8.3, 11.6, GRAY)
S_LABEL = st('label', 9.3, 14.6, DARK)
S_METRIC = st('metric', 9, 13.4, DARK)
S_CELL = st('cell', 8.5, 12.2, DARK)
S_CELLB = st('cellb', 8.5, 12.2, DARK, True)
S_CELLH = st('cellh', 8.5, 12.2, colors.white, True)
S_NOTE = st('note', 7.8, 11, GRAY, align=TA_CENTER)

content_w = A4[0] - 30 * mm


def sec(title):
    return [Spacer(1, 9), Paragraph(title, S_H2),
            HRFlowable(width='100%', thickness=1, color=ACCENT, spaceBefore=2, spaceAfter=6)]


def project(title, meta, items):
    """项目块：标题 + 元信息 + 六段式；标题与首段用 KeepTogether 防孤立"""
    body = [Paragraph('<b><font color="#2C5F8D">%s｜</font></b>%s' % (lb, tx), S_LABEL) for lb, tx in items]
    head = [Spacer(1, 12), Paragraph(title, S_PTITLE), Paragraph(meta, S_META), Spacer(1, 4)]
    out = [KeepTogether(head + body[:1])]
    for p in body[1:]:
        out += [p, Spacer(1, 2.2)]
    return out


def metricbox(text):
    t = Table([[Paragraph(text, S_METRIC)]], colWidths=[content_w])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('LINEBEFORE', (0, 0), (0, -1), 2.4, ACCENT),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return [Spacer(1, 3), t, Spacer(1, 3)]


def table(data, widths, header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ('GRID', (0, 0), (-1, -1), 0.4, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5.5),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
    ]
    if header:
        style += [('BACKGROUND', (0, 0), (-1, 0), ACCENT)]
    t.setStyle(TableStyle(style))
    return [t]


# ==================== 内容 ====================
F = []

# —— 封面区 ——
F += [Paragraph('李倍旭 · AI 应用作品集', S_NAME),
      Spacer(1, 3),
      Paragraph('AI Native 的落地者 ｜ 交付 · 评测 · 赋能', S_SUB),
      Spacer(1, 4),
      Paragraph('把模糊的业务问题翻译成可验证、可交付、可复制的 AI 系统，并对效果与 ROI 负责。', S_BODY),
      Spacer(1, 4),
      Paragraph('南京大学 · 商学院 · 国际经济与贸易（本科，2027 届）　｜　'
                + ('' if PUBLIC else '电话 (+86) 173-8943-6266　｜　')
                + '邮箱 231098011@smail.nju.edu.cn　｜　'
                'GitHub 1764646958-boop（Li Eric Beixu）', S_CONTACT),
      HRFlowable(width='100%', thickness=1.2, color=ACCENT, spaceBefore=7, spaceAfter=4)]

F += sec('能力定位')
F.append(Paragraph(
    '以「AI 应用落地」为主线的复合型实践者：既能走进业务一线做机会诊断（18 个业务漏斗筛选、SIPOC 拆解、'
    '三维 ROI 测算），也能亲手把方案做成可运行、可评测、可复现的系统 —— 用「规则决策 + LLM 翻译」交付门店导购 Agent，'
    '为开放 Agent 生态设计质量评估与分发策略，并用 Godot + 自建 LLM 服务完成 AI 原生游戏；'
    '并把「AI 协作开发」本身工程化 —— 以批次交付 + 独立复核 + 成本治理，为 3 人工作室自建团队协作平台。'
    '形成「业务 → 方案 → 工程 → 评测 → 赋能」的完整闭环。', S_BODY))

F += sec('核心技能')
F += table([
    [Paragraph('编程与工程', S_CELLB),
     Paragraph('Python、FastAPI、JavaScript / 前端、Godot（GDScript）、Shader、微信小程序', S_CELL)],
    [Paragraph('AI 工程', S_CELLB),
     Paragraph('Agent 编排（ReAct / 多阶段管道）、RAG（Dense）、Prompt 工程、LLM 护栏与降级、'
               '记忆架构（TencentDB Agent Memory 四层渐进记忆）', S_CELL)],
    [Paragraph('数据与评估', S_CELLB),
     Paragraph('XGBoost 建模与时序验证、评测集与分层验证（L1-L4）、金标准锚点与校准度、指标口径设计', S_CELL)],
    [Paragraph('产品与业务', S_CELLB),
     Paragraph('业务漏斗与 SIPOC 诊断、ROI 建模、SOP 与赋能文档、合规边界设计、指标体系与口径切换', S_CELL)],
    [Paragraph('AI 协作工程', S_CELLB),
     Paragraph('规格拆批与提示词工程、独立复核机制（不上自述 / 亲手重现）、AI 成本治理（用量台账 / 作业降频 / 0-token 脚本快照）、'
               '远程执行与断线自恢复（SSH 隧道 / 工具通道切换）', S_CELL)],
], [22 * mm, content_w - 22 * mm], header=False)

F += sec('作品索引')
F += table([
    [Paragraph('作品', S_CELLH), Paragraph('类型', S_CELLH),
     Paragraph('我的角色', S_CELLH), Paragraph('一句话', S_CELLH)],
    [Paragraph('① 商品智能导购 Agent（FDE08）', S_CELLB), Paragraph('旗舰 · 交付', S_CELL),
     Paragraph('独立全栈 + 决策人', S_CELL), Paragraph('LLM 只做翻译、代码做决策：16/16 场景与 10 条验收行为全过', S_CELL)],
    [Paragraph('② WorkBuddy 生态策略', S_CELLB), Paragraph('旗舰 · 策略', S_CELL),
     Paragraph('策略设计主导', S_CELL), Paragraph('让长尾资产被看见：质量框架 + 分发链路 + 原型 + 口径切换', S_CELL)],
    [Paragraph('③ 《防线》AI 原生游戏', S_CELLB), Paragraph('特色 · 工程纵深', S_CELL),
     Paragraph('LLM 服务 + Shader + 叙事', S_CELL), Paragraph('Godot 工程 + 五引擎 LLM 服务 + 四层渐进记忆', S_CELL)],
    [Paragraph('④ 卡旺卡门店 AI（实习）', S_CELLB), Paragraph('佐证 · 真实客户', S_CELL),
     Paragraph('AI 优化岗（主导）', S_CELL), Paragraph('18 漏斗诊断 → ROI 501.81% / 961.26% → 双 Agent MVP', S_CELL)],
    [Paragraph('⑤ 跨境 e 盾 · 合规风控', S_CELLB), Paragraph('佐证 · 行业合规', S_CELL),
     Paragraph('后端 Agent 核心', S_CELL), Paragraph('规则做确定性决策，LLM 只做审计解释，隔离幻觉', S_CELL)],
    [Paragraph('⑥ XGBoost 出品时间预测', S_CELLB), Paragraph('补位 · 数据评估', S_CELL),
     Paragraph('独立建模', S_CELL), Paragraph('171 万样本，MAE 3.27 分钟，误差 ≤5 分钟覆盖 81%', S_CELL)],
    [Paragraph('⑦ CloudLoom 团队 AI 协作工作台', S_CELLB), Paragraph('系统 · 工程方法', S_CELL),
     Paragraph('发起人 / 规格·决策·验收', S_CELL), Paragraph('3 人工作室自建协作系统；19 项验收、42 项断言、定时作业成本 −93.3%', S_CELL)],
], [44 * mm, 24 * mm, 34 * mm, content_w - 102 * mm])
F += [Spacer(1, 5), Paragraph(
    '阅读方式｜每个项目按「业务问题 → 为什么用 AI → 架构与护栏 → 评测与复盘 → 指标 → 角色边界」六段式呈现：'
    '先讲问题与取舍，再讲系统与证据。', S_META)]

# —— ① 旗舰一 ——
F += project('① 商品智能导购 Agent（澄初个护）· 字节 FDE 实习生考试 08 题',
             '个人独立完成 ｜ 2026.09 ｜ 独立 Web 原型（FastAPI + 原生前端，含公网隧道与飞书 bot 映射）', [
    ('业务问题', '顾客自己都说不清需求，又怕被施压、怕被坑；门店一边要转化，一边要守住广告法、功效宣称与医疗边界；'
                 '品牌手册没写的（促销 / 线上价 / 退换 / 渠道授权）一旦被“编”出来，就是合规事故。'),
    ('为什么用 AI', '需求理解是开放语义（“想买个洗面奶但皮肤不舒服”枚举不出来），必须靠模型；'
                    '但推荐哪个 SKU、报多少钱、合不合规绝不能用概率模型 —— 于是把责任劈开：<b>LLM 只做翻译，代码做决策</b>。'),
    ('架构与护栏', '状态机 + 三大门控（敏感 / 政策 / 注入）先于生成；推荐由确定性规则与知识库决定；'
                   '<b>所有外发金额必须等于事实价或事实价之和</b>（子集和校验，如 388 = P101+P203）；'
                   '红线场景一律走硬模板，不调用模型。'),
    ('评测与复盘', '10 条可检查行为（BC-1~10）+ 16 个场景测试全部通过；v1 是“大段提示词让模型自己决定推荐与价格”，'
                   'demo 能跑但安全、价格、合规全押模型状态 —— 主动推翻、重构成 v2 确定性门控版。'),
    ('指标', '16/16 场景与 BC-1~10 全部通过；断网 / 无 API key 仍可完整演示；在线响应 600ms 内，离线兜底不白屏。'),
    ('我的角色', '全栈 + 决策人：需求解读、知识库搭建、规则引擎、LLM 适配层、前后端、测试验收、文档与 SOP 全链路独自完成。'),
])
F += metricbox('<b>沉淀与赋能｜</b>把方案抽象成可复制套路（状态机 + 门控 + 品牌口径 + 输出契约），'
               '产出 SOP、话术模板、禁区清单与验收清单；换品牌只需替换知识库与口径 —— 这正是 FDE 要的“经验沉淀 + 生态赋能”。')

# —— ② 旗舰二 ——
F += project('② WorkBuddy 开放 Agent 生态 · 资产质量与分发策略（腾讯线作业）',
             '策略设计主导 ｜ 2026.09 ｜ 四项交付物 + 加分项（含可交互原型与常数回溯校准脚本）', [
    ('业务问题', '用户用自然语言描述需求后，连续 3 次匹配失败即放弃并退回关键词搜索；仅 8% 创作者在两周内获得超过 100 次调用；'
                 '头部资产被反复推荐，达标长尾“有质无市”—— 冷启动死锁。'),
    ('为什么这样分工', '需求理解与语境适配必须靠语义模型；而评分组合、门禁阈值、分发排序、探索配比必须可复算、可审计、扛量、防作弊。'
                       '由此给出「模型 / 规则 / 人」分工第一性原理：<b>语义归模型、确定性归规则、不可逆决策归人</b>。'),
    ('架构与护栏', '资产质量评估框架（双因子：语境适配 × 基础质量；双轨评分：内容可推断 + 行为已验证，'
                   '按证据量做贝叶斯收缩）+ 10 阶段分发链路 + 三层门禁（绝对下限 / 相对竞争 / 稀缺豁免）'
                   '+ 五支柱采信（金标准锚点、多源交叉验证、抗注入、行为真伪过滤、透明申诉与人工兜底）。'),
    ('评测与复盘', '预设长尾需求「清蒸鲈鱼配什么清酒」：传统按调用量排序命中 51,200 次调用的头部（几乎零契合），'
                   '本框架命中仅 84 次调用的 SakePairingAdvisor（语境适配 100%）；更硬核的对照是与头部语义持平（均约 97%）时，'
                   '仍凭基础质量与生态增益选中长尾 —— 证明结果由框架信号决定，而非语义搜索本身。'
                   '常数 k / β / α 用离线回溯脚本标定（seed 固定、可复现），不拍脑袋。'),
    ('指标与口径', '北极星「生态健康度」（长尾命中 × 多样性 × 采纳 × 校准）；'
                   '长尾曝光覆盖率、三次未命中率、搜索回归率、头部份额、质量分校准度；'
                   '<b>稀疏期 ↔ 稳态期口径切换</b>（点估计 + 置信区间 → 均值 / 分位 / 行为校准），'
                   '切换走影子指标 + 灰度 + 归因保护，并设护栏防止指标劫持（Goodhart）。'),
    ('我的角色', '定位与体系设计主导：质量框架、链路分工、可交互原型、指标口径方案、反马太策略（检测 → 探索 UCB → 稀缺加权 α 封顶 → '
                 '打散重复推荐 → 稀缺豁免，含作用信号与副作用护栏）。'),
])

# —— ③ 特色 ——
F += project('③ 《防线》DEFENSE LINE · AI 原生心理叙事游戏',
             '团队成员 A（LLM 服务 + Shader + 叙事 + 音乐）｜ 3 人协作 ｜ 2026 腾讯游戏创作大赛 · AI 原生游戏赛道（9 月提交）', [
    ('业务问题', '以“记忆”为本体的叙事：NPC 要记得住、会遗忘、还会被植入假记忆 —— 预设分支树撑不起这种连续性，必须由实时大模型驱动。'),
    ('架构与护栏', 'Godot 4.7 工程（34 个 GDScript / 13 个场景 / 6 个 Shader）；我交付自建 LLM 服务（Python，五端点：'
                   '记忆分析 / 对话生成 / 假记忆生成 / 战斗对话 / 名字生成），与游戏侧按接口契约对接；'
                   '信任偏移规则、压迫参数、QTE 参数全部外置为配置，便于调参与复核。'),
    ('评测与复盘', '接口契约先行 + 分周里程碑（W1 方案锁定 → W2 核心循环 → W3 记忆考古与战斗 → W4 完整 Demo 与外部试玩 → W5 品质收口）；'
                   '假记忆引擎配套评测脚本，避免“看起来对”。'),
    ('资产', '54 份过程文档：接口契约、Shader 技术路径研究、云 GPU 部署 SOP、作曲 Brief、演示分镜、17 页 PPT 框架；'
             '接入 TencentDB Agent Memory 四层渐进记忆（原始对话 / 原子记忆 / 场景归纳 / 用户画像）。'),
    ('角色边界', '我负责 LLM 服务、Shader、叙事与音乐；核心系统与 UI 由队友负责 —— 团队作品，明确标注个人贡献范围。'),
])

# —— ④ 佐证 ——
F += project('④ 卡旺卡门店 AI（实习）· 真实客户交付',
             'AI 优化岗（课题制实习）｜ 2026.7-2026.9 ｜ 茶饮连锁 · 系统开发与优化项目组', [
    ('业务问题', '18 个候选业务经两阶段漏斗（六维评分 + 一线访谈）锁定「新开店建设」与「文件答疑」两个场景；'
                 'SIPOC 拆解 10 个业务节点，建立三维 ROI 模型（<b>501.81% / 961.26%</b>），沉淀《AI 工作流落地 SOP 手册》。'),
    ('架构与护栏', '门店声音 Agent：清洗 → 标签匹配 → 信号检测 → 双源融合 → 建议卡 五级流水线；'
                   'NL2SQL Agent（LangGraph + FastAPI + Milvus）双层 Guard：硬规则字段校验 + LLM 语义审查 + 重试闭环。'),
    ('评测与复盘', 'L1-L4 分层验证：门店声音 9/9、NL2SQL 14/14 通过；<b>实测修复 11 个缺陷</b>并记录 badcase 归因；'
                   '内置 12 类对抗注入模式检测。'),
    ('指标', 'LLM 响应缓存使接口时延 15.64s → 0.07s（约 220 倍加速）；多任务并行使对比查询 >150s → 9.2s；重复查询 0.56s（缓存命中）。'),
])

# —— ⑤ 佐证 ——
F += project('⑤ 跨境 e 盾 · RegTech 合规风控平台',
             '成员 A（后端 Agent 核心）｜ 2025.8 至今 ｜ 工行杯省级二等奖 · 国家级大创立项', [
    ('业务问题', '中小微外贸企业面对制裁名单、反洗钱、出口管制、汇率波动与欺诈风险，缺少可解释、可审计的合规判断能力。'),
    ('为什么用 AI', '合规判定必须确定性：制裁名单引擎（OFAC / EU / UN + 中国出口管制，RapidFuzz 模糊匹配）、AML 规则引擎（YAML 驱动）、'
                    '依赖合规扫描（pip-audit CVE + CycloneDX SBOM）全部由规则承担；<b>LLM 只做脱敏后的中文审计解释</b>，'
                    '把幻觉隔离在解释层，决策层保持确定性。'),
    ('评测与复盘', '规划固定 API 管线 → ReAct Agent 升级路径；v2.5 采用受约束管道（Planner → Guardrail → Executor → HITL → Critic → 证据溯源），'
                   '以人工接管（HITL）与证据溯源保证可审计；自研 ReAct 约 150 行，不依赖 LangChain 框架。'),
])

# —— ⑥ 补位 ——
F += project('⑥ XGBoost 出品时间预测模型', '独立建模（卡旺卡实习期间）｜ 2026.08 ｜ 服务顾客预估 / 门店排班 / 外卖履约', [
    ('业务问题', '点单到出杯的时间直接决定顾客预估体验、门店排班效率与外卖履约质量。'),
    ('方法', '171 万条训练样本（时序划分，禁止随机 shuffle）、24 个特征、覆盖 308 家门店；'
             '排队特征用事件驱动算法 O(N log N) 精确计算。'),
    ('评测与指标', '外部测试集 MAE 3.27 分钟 / RMSE 4.93 / R² 0.6901，误差 ≤5 分钟覆盖 81% 订单；'
                   '预订单独立建模使 MAE 30.92 → 9.90（-68%）。'),
    ('商业判断', '门店偏差校准 + P35 保守偏移（+1.1min，capped@3min），68.6% 的预测偏高 —— 宁可高估，也不让顾客等得更久。'),
])

# —— ⑦ 系统工程方法 ——
F += project('⑦ CloudLoom · 团队 AI 协作工作台（原「方案C」）',
             '发起人 / 规格与技术决策 / 验收与独立复核（编码由 AI 编码代理执行）｜ 2026.09 ｜ 自研系统 · 7 批次交付 · 5 轮独立复核', [
    ('业务问题', '3 人异地工作室：AI 用得散（每次重讲背景）、任务没容器（谁在做什么靠人记）、团队记忆留不住（群里定的决策过几天找不到）。'
                 '目标不是再买一个 SaaS，而是验证：小团队能否自建「数字员工办公室 + 团队记忆容器」。'),
    ('为什么用 AI / 边界', '办公任务（汇总 / 起草 / 分析 / 复核）是一等公民，但必须明确分工：<b>语义归模型、确定性归规则、不可逆决策归人</b>；'
                          '并显式划定「不做通用 Agent 治理平台」的边界，只做小团队的协作与记忆容器。'),
    ('架构与护栏', '单页工作台 7 Tab（聊天 / 看板 / 任务 / 画像 / 资料库 / 记忆 / 设置）+ 自研代理层（兼 MCP 网关）'
                   '+ 4 个常驻 Agent（仅绑 localhost）+ <b>自建 Agent 懒启动</b>（空闲 30 分钟自动停机）+ SQLite 记忆库（FTS5 + 可见性 ACL）；'
                   '三类高风险任务（涉金额 / 对外承诺 / 删数据）<b>强制人审</b>；审批动作落库形成「成员改了什么，Agent 记住」的反馈闭环；'
                   '产物带 MANIFEST.json（sha256）校验；重启恢复「可见 + 不覆盖」。'),
    ('评测与复盘', '19 项端到端验收（17 项通过、2 项环境性延期并显式标注，<b>不以「已知问题」蒙混</b>）+ 真实浏览器 42 项断言每批回归'
                   '+ 缺陷分级编号管理（C-1…C-14）。复盘出「只有真跑才会发现」的坑：Express 5 的 listen 回调兼作 error 监听导致第二实例误判孤儿任务、'
                   'FTS5 外部表不随主表级联删除、删除 Agent 残留 systemd drop-in、定时作业失败静默无告警。'),
    ('指标', '定时 LLM 作业 <b>15 次/周 → 1 次/周（−93.3%）</b>、预计花费 <b>−94.5%</b>（一次周报实测 ≈¥0.069）；'
             '新增每日 <b>0-token 脚本快照</b>、用量台账（tokens + 估算花费）、长会话上下文瘦身（默认带最近 12 轮）；'
             '懒启动 wake 0.2s / ready 4.3s / 首字 8.5s；终态零残留（测试数据全清、健康 200、journal 零报错）。'),
    ('角色边界', '我负责规格（36 条决策清单）、技术取舍、验收标准与 <b>5 轮「不上自述、直接实测」的独立复核</b>（关键项亲手重现：'
                 '第二实例闸门、30 分钟停机、看门狗实弹告警、0-token 快照、用量记账）；<b>代码实现由 AI 编码代理完成</b>'
                 '（Kimi Code → 限额后切换 Claude Code，本机运行 + SSH 远程操作服务器）。'),
])
F += metricbox('<b>方法沉淀｜</b>把规格拆成「可独立执行、可独立验收」的批次：每份任务书都带锚点、禁区、验收标准与留档要求，'
               '并让「报告即交接」——换工具、换人、断线重来都能无缝接上。这套「人定规格与验收 → AI 执行 → 人独立复核」的工程方法，'
               '是本项目最想展示的能力：<b>AI 可以写代码，但验收权必须留在人手里</b>。')

# —— 映射 + 经历 ——
F += sec('能力 — 岗位映射（JD 语言 → 我的证据）')
F += table([
    [Paragraph('要求', S_CELLH), Paragraph('我的证据', S_CELLH)],
    [Paragraph('需求洞察与方案设计', S_CELLB),
     Paragraph('18 业务漏斗 + SIPOC 10 节点 + 三维 ROI 501.81% / 961.26%；08 题从五方角色拆解需求', S_CELL)],
    [Paragraph('端到端交付能力', S_CELLB),
     Paragraph('08 导购从 0 到可演示、可验收；断网兜底 + 公网隧道，现场稳定可跑', S_CELL)],
    [Paragraph('LLM 深度与权衡', S_CELLB),
     Paragraph('规则决策 + LLM 翻译的分工论证；何时用模型、何时用规则、何时留给人；成本与延迟意识', S_CELL)],
    [Paragraph('数据与评估（核心）', S_CELLB),
     Paragraph('BC 断言 + 16 场景 + L1-L4 分层验证 + 金标准锚点与校准度 + 稀疏期 / 稳态期口径切换', S_CELL)],
    [Paragraph('失败复盘与护栏', S_CELLB),
     Paragraph('v1 → v2 自我推翻重构；11 个缺陷修复与 badcase 归因；注入 / 敏感 / 医疗 / 政策门控', S_CELL)],
    [Paragraph('抽象沉淀与赋能', S_CELLB),
     Paragraph('SOP + 话术模板 + 禁区清单 + 验收清单；跨行业复制（个护 → 茶饮）', S_CELL)],
    [Paragraph('AI 项目工程化与成本', S_CELLB),
     Paragraph('CloudLoom：批次化交付 + 独立复核机制 + 用量台账 + 定时作业降频（成本 −93.3%）+ 运维看门狗（异常 15 分钟内可见）', S_CELL)],
    [Paragraph('协作与沟通', S_CELLB),
     Paragraph('接口契约 + 周里程碑 + A/B/C 分工（《防线》）；把复杂技术讲成“LLM 当翻译、代码当决策”', S_CELL)],
], [38 * mm, content_w - 38 * mm])

F += sec('实习与教育')
F += table([
    [Paragraph('时间', S_CELLH), Paragraph('单位', S_CELLH), Paragraph('岗位 / 内容', S_CELLH)],
    [Paragraph('2026.7-2026.9', S_CELL), Paragraph('安徽卡旺卡餐饮有限公司', S_CELLB),
     Paragraph('AI 优化岗（课题制实习）：业务 AI 化诊断与 DataAgent 工作流交付（2 个 Agent MVP）+ XGBoost 预测模型', S_CELL)],
    [Paragraph('2026.1-2026.2', S_CELL), Paragraph('德勤华永会计师事务所（南京分所）', S_CELLB),
     Paragraph('审计与鉴证：参与大型能源集团年报及现场审计，执行收入、成本等关键数据抽样复核与底稿整理', S_CELL)],
    [Paragraph('2023.9-2027.6', S_CELL), Paragraph('南京大学 · 商学院', S_CELLB),
     Paragraph('国际经济与贸易（本科）：国际贸易实务、大数据经济学、统计学、计量经济学、文本挖掘与大语言模型等', S_CELL)],
], [26 * mm, 46 * mm, content_w - 72 * mm])

F += sec('获奖与荣誉')
F += table([
    [Paragraph('“创青春”第四届全国大学生乡村振兴大赛', S_CELLB), Paragraph('主体赛 金奖', S_CELL)],
    [Paragraph('“创想中国”全国大学生创新创业大赛', S_CELLB), Paragraph('全国总决赛 一等奖', S_CELL)],
    [Paragraph('第四届全国大学生技术创新创业大赛', S_CELLB), Paragraph('二等奖', S_CELL)],
    [Paragraph('“工行杯”金融科技创新大赛 / 国家级大学生创新创业训练计划', S_CELLB),
     Paragraph('省级二等奖 ｜ 国家级大创立项', S_CELL)],
], [content_w - 52 * mm, 52 * mm], header=False)

F += [KeepTogether(sec('求职意向') + [Paragraph(
    'AI 应用 / FDE / AI 产品方向实习（2027 届，可转正）。期待把「把业务问题翻译成可验证的 AI 系统」这件事做成日常业务 —— '
    '既愿意走进现场摸清真实流程，也愿意为效果、成本与合规负责到底。', S_BODY)])]

F += sec('附录 · 作品材料清单与关键验证证据')
F += table([
    [Paragraph('作品', S_CELLH), Paragraph('可提供的材料', S_CELLH), Paragraph('关键验证证据', S_CELLH)],
    [Paragraph('① 商品智能导购 Agent', S_CELLB),
     Paragraph('源码（规则层 / LLM 适配层 / 编排层，5 模块）、自动测试、SOP 与话术模板、演示脚本', S_CELL),
     Paragraph('16 场景 + BC-1~10 全部通过；断网无 key 可跑', S_CELL)],
    [Paragraph('② WorkBuddy 生态策略', S_CELLB),
     Paragraph('4 份方案文档 + 加分项策略、可交互原型、常数回溯校准脚本', S_CELL),
     Paragraph('长尾命中对照实证；常数回测 seed 固定可复现', S_CELL)],
    [Paragraph('③ 《防线》AI 原生游戏', S_CELLB),
     Paragraph('Godot 工程、自建 LLM 服务源码、54 份过程文档（接口契约 / 周报 / 技术路径）', S_CELL),
     Paragraph('五端点服务与游戏侧联调；分周里程碑验收', S_CELL)],
    [Paragraph('④ 卡旺卡门店 AI（实习）', S_CELLB),
     Paragraph('业务诊断报告、AI 工作流落地 SOP 手册、Agent 源码与验证报告', S_CELL),
     Paragraph('L1-L4 分层验证 9/9 与 14/14；11 个缺陷修复与归因记录', S_CELL)],
    [Paragraph('⑤ 跨境 e 盾 · 合规风控', S_CELLB),
     Paragraph('后端源码、方案文档、风险规则库（制裁 / AML / 依赖合规）', S_CELL),
     Paragraph('规则引擎确定性判定 + 审计解释层隔离幻觉', S_CELL)],
    [Paragraph('⑥ XGBoost 出品时间预测', S_CELLB),
     Paragraph('建模代码、特征工程、误差分析与保守偏移设计说明', S_CELL),
     Paragraph('外部测试集 MAE 3.27 分钟 / R² 0.6901', S_CELL)],
    [Paragraph('⑦ CloudLoom 团队 AI 协作工作台', S_CELLB),
     Paragraph('七批次交付报告（已脱敏）、成员接入手册、前端开发者说明、故障排查表、运维看门狗与轮换脚本', S_CELL),
     Paragraph('19 项验收 + 42 项断言回归 + 5 轮独立复核记录；定时作业成本 −93.3%', S_CELL)],
], [32 * mm, content_w - 32 * mm - 46 * mm, 46 * mm])

F += sec('现场演示（均可当场跑通）')
F += [
    Paragraph('① <b>商品智能导购 Agent</b>：离线自测（16 场景 / BC-1~10）或 Web 演示 —— 断网也有确定性兜底，演示零风险。', S_LABEL),
    Spacer(1, 2),
    Paragraph('② <b>WorkBuddy 可交互原型</b>：零安装双击即开，现场对比「传统排序 vs 本框架」的长尾命中差异。', S_LABEL),
    Spacer(1, 2),
    Paragraph('③ <b>《防线》</b>：Godot 工程 + 本地 LLM 服务（五端点）联合运行，展示记忆分析与对话生成链路。', S_LABEL),
    Spacer(1, 2),
    Paragraph('⑦ <b>CloudLoom 协作工作台</b>：现场登录工作台，演示七个 Tab、群聊 @Agent 拉入、任务审批人审与记忆沉淀链路；'
              '离线也可讲透 —— 验收报告 + 独立复核记录 + 降耗前后账单。', S_LABEL),
]

F += sec('证据链与核实方式（怎么验证上面的结论）')
F += [
    Paragraph('① <b>可跑即证</b>：08 导购的 16 场景与 BC-1~10 断言、回归脚本可现场复跑；'
              'WorkBuddy 常数回溯脚本 seed 固定、结果可复现。', S_LABEL),
    Spacer(1, 2),
    Paragraph('② <b>报告即证据</b>：CloudLoom 的 19 项验收、42 项断言回归、7 个批次交付与 5 轮独立复核均留原始报告'
              '（含命令与原始输出），可按批次追溯。', S_LABEL),
    Spacer(1, 2),
    Paragraph('③ <b>边界即承诺</b>：团队作品标注个人角色边界；客户内部资料与团队敏感材料不随作品集分发，'
              '可按需当面演示或提供脱敏版本。', S_LABEL),
    Spacer(1, 2),
    Paragraph('④ <b>结构可查</b>：全部作品的文件结构、索引与整理日志见作品集仓库「00_作品集总览 / 作品集索引与结构说明.md」。', S_LABEL),
]

F += [Spacer(1, 14), Paragraph(
    '本作品集全部指标与结论均来自项目原始文档、测试输出与验证报告，未作虚构；团队作品已标注个人角色边界。'
    '　更新：2026-09-14', S_NOTE)]


# ==================== 页脚 ====================
def footer(canv, doc):
    canv.saveState()
    canv.setFont('Deng', 7.6)
    canv.setFillColor(GRAY)
    canv.drawString(15 * mm, 9 * mm, '李倍旭 · AI 应用作品集（2026-09）')
    canv.drawRightString(A4[0] - 15 * mm, 9 * mm, '第 %d 页' % doc.page)
    canv.setStrokeColor(LINE)
    canv.setLineWidth(0.4)
    canv.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
    canv.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4,
                      leftMargin=15 * mm, rightMargin=15 * mm,
                      topMargin=13 * mm, bottomMargin=16 * mm,
                      title='李倍旭 · AI 应用作品集（2026-09）', author='李倍旭')
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='main')
doc.addPageTemplates([PageTemplate(id='all', frames=[frame], onPage=footer)])
doc.build(F)
print('生成成功：', OUT)
