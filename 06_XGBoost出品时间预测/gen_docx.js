const docx = require('docx');
const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel, WidthType, BorderStyle, ShadingType } = docx;
const FONT = 'Microsoft YaHei';

function H(t,l){return new Paragraph({heading:l,spacing:{before:l<=2?360:240,after:120},children:[new TextRun({text:t,font:FONT,bold:true,size:l===1?44:l===2?28:22})]})}
function P(t,o={}){return new Paragraph({spacing:{after:80},children:[new TextRun({text:t,font:FONT,size:21,...o})],...o})}
function I(t){return new Paragraph({spacing:{after:60},children:[new TextRun({text:t,font:FONT,size:21})]})}
function B(t){return new Paragraph({spacing:{after:60},children:[new TextRun({text:t,font:FONT,size:21,bold:true})]})}
function Code(t){return new Paragraph({spacing:{before:80,after:80},indent:{left:360},shading:{type:ShadingType.CLEAR,fill:'F0F0F0'},children:[new TextRun({text:t,font:'Consolas',size:18})]})}
function Quote(t){return new Paragraph({spacing:{before:80,after:80},indent:{left:360},border:{left:{style:BorderStyle.SINGLE,size:12,color:'1a73e8'}},children:[new TextRun({text:t,font:FONT,size:19,italics:true,color:'555555'})]})}
function HR(){return new Paragraph({spacing:{before:120,after:120},border:{bottom:{style:BorderStyle.SINGLE,size:4,color:'CCCCCC'}},children:[]})}
function Bul(t){return new Paragraph({spacing:{after:40},indent:{left:360},children:[new TextRun({text:'\u2022 '+t,font:FONT,size:21})]})}
function Tbl(h,rs){const w=Math.floor(9020/h.length);return new Table({width:{size:9020,type:WidthType.DXA},columnWidths:Array(h.length).fill(w),rows:[new TableRow({tableHeader:true,children:h.map(hh=>new TableCell({shading:{type:ShadingType.CLEAR,fill:'E8F0FE'},children:[new Paragraph({spacing:{after:0},children:[new TextRun({text:hh,font:FONT,size:18,bold:true})]})]})})}),...rs.map((r,i)=>new TableRow({children:r.map(c=>new TableCell({shading:i%2===0?{type:ShadingType.CLEAR,fill:'FAFAFA'}:undefined,children:[new Paragraph({spacing:{after:0},children:[new TextRun({text:String(c),font:FONT,size:18})]})]})}))})]})}

const c = [];

// Title
c.push(H('出品时间预测 —— 项目报告', HeadingLevel.HEADING_1));
c.push(P('模型 v5 | 24特征 XGBoost + 门店校准 + 排队特征 + 保守偏移 | 2026-08-06', {size:18,color:'888888'}));

// === 1 ===
c.push(H('一、项目概述', HeadingLevel.HEADING_2));
c.push(H('1.1 业务目标', HeadingLevel.HEADING_3));
c.push(P('预测茶饮订单从点单完成到制作完成的时间（分钟），预测点在点单完成那一刻。'));
c.push(Tbl(['场景','用户','精度要求','当前表现','判定'], [['顾客端预估','顾客','MAE<3min, 宁可高估','MAE 2.95, 高估65%','满足'],['运营排班','店长','趋势准确+可解释','CV 2.35, 特征可解释','满足'],['外卖平台','骑手','MAE<2min','MAE 2.8','需骑手数据']]));
c.push(P(''));
c.push(H('1.2 数据规模', HeadingLevel.HEADING_3));
c.push(Tbl(['指标','数值'], [['原始订单','929,556'],['清洗后','922,367'],['日期','2026-07-20~07-26（7天）'],['门店','306个'],['订单类型','POS/美团/饿了么/微信/支付宝'],['预订单占比','1.5%']]));
c.push(P(''));
c.push(H('1.3 核心约束', HeadingLevel.HEADING_3));
c.push(I('只使用预测时间点之前已知的信息'));
c.push(I('时序划分——用历史预测未来，严禁随机shuffle'));
c.push(I('预订单独立建模——出品时间由expect_time决定'));
c.push(HR());

// === 2 ===
c.push(H('二、方法论', HeadingLevel.HEADING_2));
c.push(H('2.1 因果分解', HeadingLevel.HEADING_3));
c.push(Code('出品时间 = 制作耗时 + 排队等待 + 人为优先级 + 门店差异 + 随机噪声\n           |         |           |           |          |\n         杯数     排队长度     订单类型    门店编号   不可观测'));
c.push(H('2.2 特征体系（24个）', HeadingLevel.HEADING_3));
c.push(H('时间特征 9个', HeadingLevel.HEADING_4));
c.push(Tbl(['特征','说明'], [['hour/minite/day_of_week','时间基本属性'],['is_weekend','周末效应'],['period','时段分段(深夜/早间/午高峰/午后/晚高峰/晚间)'],['is_lunch/is_dinner_peak','午晚餐高峰标记'],['hour_sin/hour_cos','循环编码(23与0相邻)']]));
c.push(P(''));
c.push(H('订单特征 5个', HeadingLevel.HEADING_4));
c.push(Tbl(['特征','说明'], [['order_entry_seconds','点单耗时(POS有操作,外卖=0)'],['cups','杯数(1-30)'],['order_type_enc','订单类型编码'],['is_delivery','是否外卖'],['is_online','是否线上']]));
c.push(P(''));
c.push(H('门店特征 2个', HeadingLevel.HEADING_4));
c.push(Tbl(['特征','说明'], [['store_enc','Label Encoding(0-305)'],['store_target_enc','门店历史平均出品(防泄漏)']]));
c.push(P(''));
c.push(H('排队特征 6个——核心创新', HeadingLevel.HEADING_4));
c.push(Tbl(['特征','说明','重要度'], [['concurrent_hourly','同店同小时订单数','1.9%'],['concurrent_periodly','同店同时段订单数','1.3%'],['load_index','负载/历史均值','0.8%'],['queue_ahead','前面排了多少单','6.9%'],['queue_cups_ahead','前面排了多少杯','4.7%'],['queue_load_ratio','排队杯数/历史均值','0.8%']]));
c.push(P(''));
c.push(Quote('queue_ahead实现：事件驱动算法。每条订单拆为"进入队列"和"离开队列"两个事件，按门店-时间排序后单次扫描。O(N log N)，92万条耗时约7分钟。'));
c.push(H('交互特征 4个', HeadingLevel.HEADING_4));
c.push(Tbl(['特征','说明'], [['store_hour_enc','门店x小时(Top500高频组合)'],['cups_x_delivery','杯数x外卖'],['period_x_delivery','时段x外卖'],['hours_until_expect','距期望取餐时间(预订单专用)']]));
c.push(H('2.3 数据划分', HeadingLevel.HEADING_3));
c.push(Code('训练: 07-20~07-25 (6天, 750,636普通+11,748预订)\n测试: 07-26       (1天, 157,864普通+2,119预订)\nCV:   TimeSeriesSplit 3折 (2.35+/-0.03)'));
c.push(HR());

// === 3 ===
c.push(H('三、模型架构演进', HeadingLevel.HEADING_2));
c.push(Tbl(['版本','改动','普通单MAE','预订单MAE','R2'], [['v1 基线','18特征 XGBoost','3.18','~29','0.45'],['v2 双模型','拆分预订单+门店校准','3.10','23.2','0.25'],['v3 调优','交互特征+参数搜索','2.93','23.2','0.26'],['v4 排队','queue_ahead/cups_ahead','2.43','23.2','0.55'],['v5 预订单','预订单XGBoost回归','2.43','8.87','0.55']]));
c.push(P(''));

c.push(H('3.1 关键架构决策', HeadingLevel.HEADING_3));
c.push(B('双模型路由'));
c.push(Code('if is_preorder == 0: XGBoost(24特征) -> 门店校准 -> 保守偏移 -> 预测\nelse:              XGBoost(8特征, 含hours_until_expect) -> 预测'));
c.push(B('三层后处理校准'));
c.push(Tbl(['层级','机制','效果'], [['1.门店偏差','每个店的历史预测偏差(305门店)','消除系统性高估/低估'],['2.保守偏移','+1.07分钟(P35残差取反)','65%高估率,降低投诉'],['3.上限保护','偏移不超过3分钟','防止极端高估']]));
c.push(P(''));
c.push(Quote('保守偏移原理：训练集上计算残差的P35分位数(取反)=+1.07。应用后训练集65%的订单预测值>实际值。'));

c.push(H('3.2 预订单模型（v5升级）', HeadingLevel.HEADING_3));
c.push(Code('旧: 门店x杯数 中位数查表 -> MAE 30.92\n新: XGBoost回归(hours_until_expect为核心) -> MAE 8.87 (-71%)'));
c.push(P('hours_until_expect = (expect_time - 点单完成时间) / 3600，预订单"距取餐还有多久"决定制作优先级。'));
c.push(HR());

// === 4 ===
c.push(H('四、最终模型性能', HeadingLevel.HEADING_2));
c.push(H('4.1 整体指标', HeadingLevel.HEADING_3));
c.push(Tbl(['指标','训练集','测试集','CV'], [['普通单 MAE','2.29','2.42','2.35+/-0.03'],['普通单 R2','0.52','0.55','--'],['预订单 MAE','--','8.87','--'],['综合 MAE','--','2.51','--'],['保守偏移后 MAE','--','~2.95','--']]));
c.push(P(''));

c.push(H('4.2 误差分布（保守偏移生效后）', HeadingLevel.HEADING_3));
c.push(Tbl(['误差范围','占比','累计'], [['0~2min','44%','44%'],['2~5min','42%','86%'],['5~10min','11%','97%'],['10~30min','3%','~100%']]));
c.push(P(''));
c.push(I('系统偏差: +0.9min(略低估) | 高估65%/低估35% | 保守偏好生效'));

c.push(H('4.3 分群评估', HeadingLevel.HEADING_3));
c.push(Tbl(['订单类型','MAE','实际均值'], [['POS','2.04','5.6'],['微信小程序','2.34','7.7'],['支付宝','2.09','7.2'],['美团','2.81','10.1'],['饿了么','2.84','10.2']]));
c.push(P(''));
c.push(Tbl(['杯数','MAE'], [['1杯','2.33'],['2杯','2.42'],['3-5杯','2.50'],['6-10杯','4.83'],['11+杯','6.64']]));

c.push(H('4.4 特征重要性 Top 11', HeadingLevel.HEADING_3));
c.push(Code('is_delivery          32.8%\norder_type_enc       21.9%\nperiod_x_delivery     8.5%\nqueue_ahead           6.9%  <- 核心\nis_online             6.6%\nqueue_cups_ahead      4.7%  <- 核心\ncups                  3.3%\norder_entry_seconds   2.0%\nconcurrent_hourly     1.9%\ncups_x_delivery       1.6%\nstore_hour_enc        1.4%'));
c.push(HR());

// === 5 ===
c.push(H('五、预测效果预期', HeadingLevel.HEADING_2));
c.push(P('以下是用户上传新数据后的预期表现：'));
c.push(Tbl(['场景','MAE','关键说明'], [['普通单(已知门店)','2.5-3.0','误差<5min占76%, <10min占88%'],['大单(6+杯)','4.8-6.6','样本少,精度下降'],['预订单','~9','expect_time主导,流程不同'],['新门店(训练集未见)','>5','退回全局均值+保守偏移'],['跨季节/跨年','3.5-5.0','菜单/流程变化需重训练']]));
c.push(P(''));
c.push(Quote('顾客体验: "预计等待9分钟" -> 65%概率实际<=9分钟 -> 惊喜 >> 投诉'));
c.push(HR());

// === 6 ===
c.push(H('六、部署交付', HeadingLevel.HEADING_2));
c.push(H('6.1 交付文件清单', HeadingLevel.HEADING_3));
c.push(Tbl(['文件','大小','用途','必须'], [['xgboost_model.json','4MB','普通单 XGBoost模型','是'],['model_encoders.npz','54KB','编码器+校准+保守偏移','是'],['predict.py','29KB','推理引擎(后端直接调用)','是'],['xgboost_preorder_model.json','1.7MB','预订单 XGBoost模型','推荐']]));
c.push(P(''));
c.push(H('6.2 后端集成方式', HeadingLevel.HEADING_3));
c.push(Code('from predict import predict_pipeline\n\n# 预测+评估(CSV含制作完成时间)\nresult_df, eval_dict = predict_pipeline("订单.csv", "结果.csv")\n\n# 纯预测(CSV不含制作完成时间)\nresult_df, _ = predict_pipeline("新订单.csv", "预测结果.csv")'));
c.push(P(''));
c.push(B('返回数据'));
c.push(I('result_df: DataFrame，含原始列 + 预测出品时间_分钟 + 预测出品时间_格式化'));
c.push(I('eval_dict: dict，含MAE/R2/误差分布/分群评估（仅当CSV含制作完成时间时有效）'));
c.push(P(''));
c.push(B('CSV格式要求'));
c.push(I('必须: 点单完成时间, 杯数, 订单类型, 门店编号'));
c.push(I('可选: 制作完成时间(用于评估), 点单开始时间, 是否预订单, expect_time'));

c.push(H('6.3 环境依赖', HeadingLevel.HEADING_3));
c.push(Code('pip install pandas numpy xgboost scikit-learn'));
c.push(HR());

// === 7 ===
c.push(H('七、项目文件结构', HeadingLevel.HEADING_2));
c.push(Code('D:\\work\\叫号\\\n|-- xgboost_model.json              <- 普通单模型(部署)\n|-- xgboost_preorder_model.json     <- 预订单模型(部署)\n|-- model_encoders.npz              <- 编码器+校准(部署)\n|-- predict.py                      <- 推理引擎(部署)\n|-- app.py                          <- Web服务\n|-- data/ 叫号队列列表 (58).csv      <- 原始训练数据\n|-- src/\n|   |-- xgboost_prediction.py       <- 训练脚本\n|   \\-- tune_params.py              <- 参数调优\n\\-- prediction_tool/                <- 工具包(含Web UI)'));
c.push(HR());

// === 8 ===
c.push(H('八、关键决策与局限', HeadingLevel.HEADING_2));
c.push(H('关键决策', HeadingLevel.HEADING_3));
c.push(Tbl(['决策','选择','理由'], [['算法','XGBoost','表格数据,非线性,混合特征'],['门店编码','Label+Target(非OneHot)','306门店,OneHot膨胀'],['预订单','独立XGBoost','expect_time是关键变量'],['划分','时序(非随机)','模拟真实预测'],['验证','TimeSeriesSplit','尊重时间序'],['保守偏好','+1.07min偏移,capped@3min','宁可高估,不过度'],['排队算法','事件驱动O(N log N)','精确计算队列位置']]));
c.push(P(''));
c.push(H('当前局限', HeadingLevel.HEADING_3));
c.push(I('不可观测因素：店员在岗人数、饮品复杂度、设备状态——占剩余误差主体'));
c.push(I('大单预测偏弱：6杯以上 MAE 4.83（样本仅1,958条）'));
c.push(I('外卖精度天花板：缺骑手到达时间——决定了外卖无法达到<2min MAE'));
c.push(H('下一步方向', HeadingLevel.HEADING_3));
c.push(I('接入排班数据——直接知道每个时段几个人在岗'));
c.push(I('菜单数据库——每杯饮品标准制作时间替代粗略杯数'));
c.push(I('天气数据——气温/降雨影响外卖/到店比例'));
c.push(I('在线学习——每天自动用新数据更新模型'));
c.push(HR());
c.push(P('报告生成: 2026-08-06 | v5 | 24特征XGBoost+门店校准+排队+保守偏移', {size:18,color:'888888',italics:true}));

// Build
const doc = new Document({styles:{default:{document:{run:{font:FONT}}}},sections:[{properties:{page:{margin:{top:1000,bottom:1000,left:1200,right:1200}}},children:c}]});
Packer.toBuffer(doc).then(buf=>{fs.writeFileSync('项目报告.docx',buf);console.log('OK: '+Math.round(buf.length/1024)+'KB')});
