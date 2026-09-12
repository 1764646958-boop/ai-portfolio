#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
茶饮门店出品时间预测 —— 推理脚本
=================================
加载已训练的 XGBoost 模型，对新订单数据预测出品时间。

用法：
    python predict.py <新数据.csv> [选项]

示例：
    python predict.py 新订单.csv
    python predict.py 新订单.csv -o 结果.csv
    python predict.py 新订单.csv --model-dir ./model_files/

输入CSV必须包含列：点单完成时间, 杯数, 订单类型, 门店编号
可选列：是否预订单？

=========================================
环境要求（一键安装）：
    pip install pandas numpy xgboost scikit-learn
=========================================
"""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import xgboost as xgb
import os
import sys
import argparse

# ============================================================
# 0. 配置 —— 模型文件默认放在本脚本同目录下
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 特征列表（必须与训练时完全一致）
FEATURE_COLS_REGULAR = [
    'hour', 'minute', 'day_of_week', 'is_weekend', 'period',
    'is_lunch_peak', 'is_dinner_peak', 'hour_sin', 'hour_cos',
    'order_entry_seconds',
    'cups', 'order_type_enc', 'is_delivery', 'is_online',
    'store_enc', 'concurrent_hourly', 'concurrent_periodly',
    'load_index',
    'store_hour_enc',
    'cups_x_delivery', 'period_x_delivery',
    'queue_ahead', 'queue_cups_ahead', 'queue_load_ratio',
]
FEATURE_COLS = FEATURE_COLS_REGULAR


def get_period(h):
    """时段分段：深夜/早间/午高峰/午后/晚高峰/晚间"""
    if 0 <= h <= 5:   return 0
    elif 6 <= h <= 9:   return 1
    elif 10 <= h <= 13: return 2
    elif 14 <= h <= 16: return 3
    elif 17 <= h <= 19: return 4
    else:               return 5


def _fmt_min_sec(minutes):
    """将分钟数格式化为 X分Y秒，避免 11分60秒 的舍入问题"""
    if pd.isna(minutes):
        return ""
    total_sec = int(round(minutes * 60))
    m, s = divmod(total_sec, 60)
    return f"{m}分{s}秒"


# ============================================================
# 1. 加载模型和编码器
# ============================================================
def load_model_and_encoders(model_dir):
    """加载 XGBoost 模型、编码器、门店校准系数、预订单查询表"""
    model_path = os.path.join(model_dir, 'xgboost_model.json')
    encoder_path = os.path.join(model_dir, 'model_encoders.npz')

    for fp, name in [(model_path, '模型'), (encoder_path, '编码器')]:
        if not os.path.exists(fp):
            raise FileNotFoundError(
                f"\n  [ERROR] 找不到{name}文件: {fp}\n"
                f"  请确认以下两个文件与 predict.py 在同一目录下:\n"
                f"    - xgboost_model.json\n"
                f"    - model_encoders.npz\n"
                f"  或使用 --model-dir 指定所在目录"
            )

    print(f"  模型: {model_path}")
    model = xgb.XGBRegressor()
    model.load_model(model_path)

    enc = np.load(encoder_path, allow_pickle=True)
    order_classes = enc['order_classes']
    store_classes = enc['store_classes']
    store_target_enc_dict = enc['store_target_enc'].item()
    global_mean_target = float(enc['global_mean_target'])

    # 门店校准系数（P1优化）
    store_bias_dict = enc.get('store_bias', None)
    if store_bias_dict is not None:
        store_bias_dict = store_bias_dict.item()
        print(f"  门店校准: {len(store_bias_dict)} 个门店")

    conservative_offset = float(enc.get('conservative_offset', 0.5))
    print(f"  保守偏移: +{conservative_offset:.1f}min (高估偏好)")

    # 预订单 XGBoost 模型
    pre_model = None
    pre_feature_names = None
    pre_model_path = os.path.join(model_dir, 'xgboost_preorder_model.json')
    if os.path.exists(pre_model_path):
        pre_model = xgb.XGBRegressor()
        pre_model.load_model(pre_model_path)
        print(f"  预订单模型: {pre_model_path}")
        if 'preorder_feature_names' in enc:
            pre_feature_names = list(enc['preorder_feature_names'])

    print(f"  编码器: {encoder_path}")
    print(f"  订单类型: {list(order_classes)}")
    print(f"  门店数量: {len(store_classes)}")

    order_type_map = {cls: idx for idx, cls in enumerate(order_classes)}
    store_map = {cls: idx for idx, cls in enumerate(store_classes)}

    return model, order_type_map, store_map, store_target_enc_dict, global_mean_target, \
        store_bias_dict, conservative_offset, pre_model, pre_feature_names


# ============================================================
# 2. 读取数据
# ============================================================
def load_data(path):
    """读取 CSV 或 Excel，自动适配编码"""
    print(f"\n读取数据: {path}")
    ext = os.path.splitext(path)[1].lower()

    if ext in ('.xlsx', '.xls'):
        df = pd.read_excel(path)
        print(f"  格式: Excel  |  行数: {len(df):,}  |  列数: {len(df.columns)}")
    else:
        for enc in ['utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'utf-8']:
            try:
                df = pd.read_csv(path, encoding=enc, low_memory=False)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            raise RuntimeError("无法识别文件编码，请将文件另存为 UTF-8 CSV 或 Excel 格式")
        print(f"  编码: {enc}  |  行数: {len(df):,}  |  列数: {len(df.columns)}")

    print(f"  编码: {enc}  |  行数: {len(df):,}  |  列数: {len(df.columns)}")

    required = ['点单完成时间', '杯数', '订单类型', '门店编号']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"缺少必要列: {missing}\n  CSV必须包含: {required}")
    return df


# ============================================================
# 3. 特征工程
# ============================================================
def build_features(df, order_type_map, store_map, store_target_enc_dict, global_mean_target):
    """构建全部 18 个特征（与训练脚本完全一致）"""
    print("\n构建特征...")

    # --- 时间特征 ---
    # 兼容多种日期格式：2026-07-26 12:15:30 / 2026/7/26 12:15 / 2026-07-26 12:15 等
    df['点单完成时间_dt'] = pd.to_datetime(df['点单完成时间'], errors='coerce',
                                           dayfirst=False, yearfirst=True)
    n_bad = df['点单完成时间_dt'].isna().sum()
    if n_bad > 0:
        print(f"  [WARN] {n_bad} 行时间解析失败，已丢弃")
        df = df.dropna(subset=['点单完成时间_dt']).copy()

    dt = df['点单完成时间_dt']
    df['hour'] = dt.dt.hour
    df['minute'] = dt.dt.minute
    df['day_of_week'] = dt.dt.dayofweek
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['period'] = df['hour'].apply(get_period)
    df['is_lunch_peak'] = df['hour'].between(11, 13).astype(int)
    df['is_dinner_peak'] = df['hour'].between(17, 19).astype(int)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)

    # --- 点单耗时（秒）：POS点餐需要操作时间，外卖/线上即时 ---
    if '点单开始时间' in df.columns:
        df['点单开始时间_dt'] = pd.to_datetime(df['点单开始时间'], errors='coerce',
                                                dayfirst=False, yearfirst=True)
        df['order_entry_seconds'] = (
            df['点单完成时间_dt'] - df['点单开始时间_dt']
        ).dt.total_seconds().fillna(0).clip(0, 300)
    else:
        df['order_entry_seconds'] = 0

    # --- 杯数 ---
    df['杯数'] = pd.to_numeric(df['杯数'], errors='coerce').fillna(1)
    df['cups'] = df['杯数'].clip(1, 30).astype(int)

    # --- 订单类型 ---
    df['order_type_enc'] = df['订单类型'].map(order_type_map)
    n_unk = df['order_type_enc'].isna().sum()
    if n_unk > 0:
        print(f"  [WARN] {n_unk} 行订单类型不在训练集类别中，标记为 -1")
        print(f"         已知类别: {list(order_type_map.keys())}")
    df['order_type_enc'] = df['order_type_enc'].fillna(-1).astype(int)
    df['is_delivery'] = df['订单类型'].isin(['美团', '饿了么']).astype(int)
    df['is_online'] = (df['订单类型'] != 'POS').astype(int)

    # --- 预订单 expect_time 解析 ---
    if 'expect_time' in df.columns:
        df['expect_time_dt'] = pd.to_datetime(df['expect_time'], errors='coerce',
                                               dayfirst=False, yearfirst=True)
        df['hours_until_expect'] = (
            df['expect_time_dt'] - df['点单完成时间_dt']
        ).dt.total_seconds() / 3600.0
        df['hours_until_expect'] = df['hours_until_expect'].fillna(-1).clip(-1, 48)
    else:
        df['hours_until_expect'] = -1

    # --- 门店 ---
    df['store_enc'] = df['门店编号'].map(store_map)
    n_unk_store = df['store_enc'].isna().sum()
    if n_unk_store > 0:
        print(f"  [WARN] {n_unk_store} 行门店编号不在训练集，标记为 -1（预测可能不准）")
    df['store_enc'] = df['store_enc'].fillna(-1).astype(int)
    df['store_target_enc'] = df['门店编号'].map(store_target_enc_dict)
    df['store_target_enc'] = df['store_target_enc'].fillna(global_mean_target)

    # --- 预订单 ---
    if '是否预订单？' in df.columns:
        df['is_preorder'] = df['是否预订单？'].apply(
            lambda x: 0 if pd.isna(x) or str(x).strip().lower() in ('', 'nan') else 1
        )
    else:
        df['is_preorder'] = 0

    # --- 构造特征：并发与负载 ---
    df['date_hour'] = df['点单完成时间_dt'].dt.strftime('%Y-%m-%d %H')
    cnt_h = df.groupby(['门店编号', 'date_hour']).size().reset_index(name='concurrent_hourly')
    df = df.merge(cnt_h, on=['门店编号', 'date_hour'], how='left')

    df['date'] = df['点单完成时间_dt'].dt.date.astype(str)
    df['date_period'] = df['date'] + '_' + df['period'].astype(str)
    cnt_p = df.groupby(['门店编号', 'date_period']).size().reset_index(name='concurrent_periodly')
    df = df.merge(cnt_p, on=['门店编号', 'date_period'], how='left')

    avg_p = df.groupby(['门店编号', 'period'])['concurrent_periodly'].transform('mean')
    df['load_index'] = (df['concurrent_periodly'] / (avg_p + 1e-6)).clip(0, 10)

    # --- 交互特征 ---
    df['store_hour_enc'] = df.apply(
        lambda r: hash(f"{r['store_enc']}_{r['hour']}") % 10000, axis=1)
    df['cups_x_delivery'] = df['cups'] * df['is_delivery']
    df['period_x_delivery'] = df['period'] * df['is_delivery']

    # --- 排队特征 ---
    has_make_time = '制作完成时间' in df.columns
    if has_make_time:
        # 有完成时间 → 事件驱动精确计算
        df['制作完成时间_dt'] = pd.to_datetime(df['制作完成时间'], errors='coerce',
                                                dayfirst=False, yearfirst=True)
        queue_events = []
        for i, (_, row) in enumerate(df.iterrows()):
            queue_events.append((row['门店编号'], row['点单完成时间_dt'], 0, i))
            if pd.notna(row.get('制作完成时间_dt')):
                queue_events.append((row['门店编号'], row['制作完成时间_dt'], 1, i))
        queue_events.sort(key=lambda x: (x[0], x[1], x[2]))

        q_ahead = np.zeros(len(df), dtype=int)
        q_cups = np.zeros(len(df), dtype=float)
        active_s, active_c = {}, {}
        for store, ts, evt, idx in queue_events:
            ci = df.iloc[idx]['cups']
            if evt == 0:
                if store not in active_s: active_s[store] = set(); active_c[store] = 0
                q_ahead[idx] = len(active_s[store])
                q_cups[idx] = active_c.get(store, 0)
                active_s[store].add(idx)
                active_c[store] = active_c.get(store, 0) + ci
            else:
                if store in active_s and idx in active_s[store]:
                    active_s[store].discard(idx)
                    active_c[store] = max(0, active_c.get(store, 0) - ci)
        df['queue_ahead'] = q_ahead
        df['queue_cups_ahead'] = q_cups
    else:
        # 无完成时间 → 用门店历史均值估算完成时间，模拟"离开"事件
        df_sorted = df.sort_values(['门店编号', '点单完成时间_dt'])
        # 加载门店平均出品时间（已有）
        store_avg_time = store_target_enc_dict  # from encoder
        global_avg = global_mean_target

        queue_events = []
        for i, (_, row) in enumerate(df_sorted.iterrows()):
            queue_events.append((row['门店编号'], row['点单完成时间_dt'], 0, i))
            # 估算完成时间 = 点单完成 + 该店平均出品时间
            avg_make = store_avg_time.get(row['门店编号'], global_avg)
            est_done = row['点单完成时间_dt'] + pd.Timedelta(minutes=float(avg_make))
            queue_events.append((row['门店编号'], est_done, 1, i))
        queue_events.sort(key=lambda x: (x[0], x[1], x[2]))

        q_ahead = np.zeros(len(df_sorted), dtype=int)
        q_cups = np.zeros(len(df_sorted), dtype=float)
        active_s, active_c = {}, {}
        for store, ts, evt, idx in queue_events:
            ci = df_sorted.iloc[idx]['cups']
            if evt == 0:
                if store not in active_s: active_s[store] = set(); active_c[store] = 0
                q_ahead[idx] = len(active_s[store])
                q_cups[idx] = active_c.get(store, 0)
                active_s[store].add(idx)
                active_c[store] = active_c.get(store, 0) + ci
            else:
                if store in active_s and idx in active_s[store]:
                    active_s[store].discard(idx)
                    active_c[store] = max(0, active_c.get(store, 0) - ci)

        # Map back to original index order
        idx_map = {new: old for new, old in enumerate(df_sorted.index)}
        df['queue_ahead'] = [q_ahead[idx_map[i]] for i in range(len(df))]
        df['queue_cups_ahead'] = [q_cups[idx_map[i]] for i in range(len(df))]

    grp_mean = df.groupby(['门店编号', 'period'])['queue_cups_ahead'].transform('mean')
    df['queue_load_ratio'] = (df['queue_cups_ahead'] / (grp_mean + 1e-6)).clip(0, 10)

    # 确保所有特征列存在、无缺失
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0

    # 填充构造特征可能的缺失
    for col in ['concurrent_hourly', 'concurrent_periodly', 'load_index']:
        df[col] = df[col].fillna(0)

    print(f"  特征构建完成，有效行数: {len(df):,}")
    return df


# ============================================================
# 4. 预测（双模型路由：普通单→XGBoost+校准，预订单→中位数查询）
# ============================================================
def run_predict(model, df, store_bias_dict=None, conservative_offset=0.5, pre_model=None, pre_feature_names=None):
    """Execute batch prediction, routing regular vs pre-orders"""
    print("执行预测...")
    mask_regular = df['is_preorder'] == 0
    mask_preorder = df['is_preorder'] == 1
    n_reg, n_pre = mask_regular.sum(), mask_preorder.sum()
    print(f"  普通单: {n_reg:,} 条  |  预订单: {n_pre:,} 条")
    df['预测出品时间_分钟'] = np.nan

    # Regular: XGBoost + calibration
    if n_reg > 0:
        X_reg = df.loc[mask_regular, FEATURE_COLS_REGULAR].values.astype(np.float32)
        if np.any(np.isnan(X_reg)):
            from sklearn.impute import SimpleImputer
            X_reg = SimpleImputer(strategy='median').fit_transform(X_reg)
        preds_raw = model.predict(X_reg)
        if store_bias_dict:
            stores = df.loc[mask_regular, '门店编号']
            corr = np.array([store_bias_dict.get(s, 0) for s in stores])
            df.loc[mask_regular, '预测出品时间_分钟'] = np.maximum(preds_raw - corr + conservative_offset, 0.5)
        else:
            df.loc[mask_regular, '预测出品时间_分钟'] = np.maximum(preds_raw, 0.5)

    # Pre-order: XGBoost regression with expect_time
    if n_pre > 0 and pre_model is not None and pre_feature_names is not None:
        cols_avail = [f for f in pre_feature_names if f in df.columns]
        X_pre = df.loc[mask_preorder, cols_avail].values.astype(np.float32)
        if np.any(np.isnan(X_pre)):
            from sklearn.impute import SimpleImputer
            X_pre = SimpleImputer(strategy='median').fit_transform(X_pre)
        df.loc[mask_preorder, '预测出品时间_分钟'] = np.maximum(pre_model.predict(X_pre), 0.5)
    elif n_pre > 0:
        X_pre = df.loc[mask_preorder, FEATURE_COLS_REGULAR].values.astype(np.float32)
        if np.any(np.isnan(X_pre)):
            from sklearn.impute import SimpleImputer
            X_pre = SimpleImputer(strategy='median').fit_transform(X_pre)
        df.loc[mask_preorder, '预测出品时间_分钟'] = np.maximum(model.predict(X_pre), 0.5)

    df['预测出品时间_格式化'] = [_fmt_min_sec(m) for m in df['预测出品时间_分钟']]
    preds = df['预测出品时间_分钟'].dropna()
    print(f"  预测完成! 共 {len(preds):,} 条")
    print(f"  均值={preds.mean():.1f}min  中位数={np.median(preds):.1f}min  " f"范围=[{preds.min():.1f}, {preds.max():.1f}]min")
    return df

def save_results(df, output_path):
    """保存预测结果 CSV"""
    preferred = [
        '订单编号', '订单显示编号', '取单号', '订单类型', '门店编号', '门店名称',
        '杯数', '点单完成时间', 'is_preorder',
        '预测出品时间_分钟', '预测出品时间_格式化',
    ]
    cols = [c for c in preferred if c in df.columns]
    # 追加其他原列
    for c in df.columns:
        if c not in cols and not c.startswith('date_') and c not in FEATURE_COLS:
            cols.append(c)

    df[cols].to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存至: {output_path}")
    return df[cols]


# ============================================================
# 6. 准确度评估（当数据包含 制作完成时间 时自动触发）
# ============================================================
def run_evaluation(df):
    """对比预测值和真实值，输出全面评估报告"""
    # 计算真实出品时间
    df['制作完成时间_dt'] = pd.to_datetime(df['制作完成时间'], errors='coerce',
                                            dayfirst=False, yearfirst=True)
    df['点单完成时间_dt'] = pd.to_datetime(df['点单完成时间'], errors='coerce',
                                            dayfirst=False, yearfirst=True)
    df['实际出品时间_分钟'] = (
        df['制作完成时间_dt'] - df['点单完成时间_dt']
    ).dt.total_seconds() / 60.0

    valid = df['实际出品时间_分钟'].notna() & (df['实际出品时间_分钟'] > 0) & (df['实际出品时间_分钟'] <= 180)
    df_eval = df[valid].copy()

    if len(df_eval) < 10:
        print("\n  [INFO] 有效真值样本不足10条，跳过评估")
        return

    y_true = df_eval['实际出品时间_分钟'].values
    y_pred = df_eval['预测出品时间_分钟'].values
    residuals = y_true - y_pred

    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)

    print("\n" + "=" * 60)
    print("准确度评估报告")
    print("=" * 60)
    print(f"  有效评估样本: {len(df_eval):,} 条")

    # 整体指标
    print(f"\n  --- 整体指标 ---")
    print(f"  MAE (平均绝对误差):   {mae:.2f} 分钟")
    print(f"  RMSE (均方根误差):    {rmse:.2f} 分钟")
    print(f"  R2 (决定系数):        {r2:.4f}")
    print(f"  实际均值:             {y_true.mean():.2f} 分钟")
    print(f"  预测均值:             {y_pred.mean():.2f} 分钟")

    # 误差分布
    print(f"\n  --- 误差分布 ---")
    print(f"  平均误差 (正=低估):   {np.mean(residuals):+.2f} 分钟")
    print(f"  中位误差:             {np.median(residuals):+.2f} 分钟")
    for p in [10, 25, 50, 75, 90]:
        print(f"  P{p}:                   {np.percentile(residuals, p):+.2f} 分钟")

    over = (residuals < 0).sum()   # 预测 > 实际 = 高估
    under = (residuals > 0).sum()  # 预测 < 实际 = 低估
    print(f"  高估 (告诉顾客更久):  {over:,} ({over/len(df_eval)*100:.1f}%)")
    print(f"  低估 (告诉顾客更快):  {under:,} ({under/len(df_eval)*100:.1f}%)")

    # 误差分段统计
    print(f"\n  --- 误差分段 ---")
    for lo, hi, label in [
        (0, 2, '0~2分钟'),
        (2, 5, '2~5分钟'),
        (5, 10, '5~10分钟'),
        (10, 30, '10~30分钟'),
        (30, 999, '>30分钟'),
    ]:
        cnt = ((np.abs(residuals) >= lo) & (np.abs(residuals) < hi)).sum()
        print(f"  误差 {label:<10s}: {cnt:>6,} 条 ({cnt/len(df_eval)*100:5.1f}%)")

    # 按订单类型分群
    if '订单类型' in df_eval.columns:
        print(f"\n  --- 按订单类型 ---")
        print(f"  {'类型':<12s} {'样本':>6s} {'MAE':>8s} {'实际均值':>8s} {'预测均值':>8s}")
        for ot in sorted(df_eval['订单类型'].dropna().unique()):
            sub = df_eval[df_eval['订单类型'] == ot]
            if len(sub) < 5:
                continue
            print(f"  {ot:<12s} {len(sub):>6,} {mean_absolute_error(sub['实际出品时间_分钟'], sub['预测出品时间_分钟']):>7.2f}分 "
                  f"{sub['实际出品时间_分钟'].mean():>7.1f}分 {sub['预测出品时间_分钟'].mean():>7.1f}分")

    # 按杯数分群
    if 'cups' in df_eval.columns:
        print(f"\n  --- 按杯数 ---")
        print(f"  {'杯数':<12s} {'样本':>6s} {'MAE':>8s} {'实际均值':>8s} {'预测均值':>8s}")
        for lo, hi, label in [(1,1,'1杯'),(2,2,'2杯'),(3,5,'3-5杯'),(6,10,'6-10杯'),(11,99,'11+杯')]:
            sub = df_eval[(df_eval['cups'] >= lo) & (df_eval['cups'] <= hi)]
            if len(sub) < 5:
                continue
            print(f"  {label:<12s} {len(sub):>6,} {mean_absolute_error(sub['实际出品时间_分钟'], sub['预测出品时间_分钟']):>7.2f}分 "
                  f"{sub['实际出品时间_分钟'].mean():>7.1f}分 {sub['预测出品时间_分钟'].mean():>7.1f}分")

    # 按预订单分群
    if 'is_preorder' in df_eval.columns:
        print(f"\n  --- 按是否预订单 ---")
        for po, label in [(0, '普通单'), (1, '预订单')]:
            sub = df_eval[df_eval['is_preorder'] == po]
            if len(sub) < 3:
                continue
            print(f"  {label:<8s} {len(sub):>6,}条  MAE={mean_absolute_error(sub['实际出品时间_分钟'], sub['预测出品时间_分钟']):.2f}分  "
                  f"实际均值={sub['实际出品时间_分钟'].mean():.1f}分  预测均值={sub['预测出品时间_分钟'].mean():.1f}分")

    # 综合评价
    print(f"\n  --- 综合评价 ---")
    if mae < 3:
        print(f"  [OK] MAE < 3分钟，可满足顾客端预估需求")
    elif mae < 5:
        print(f"  [OK] MAE {mae:.1f}分钟，可满足运营排班参考")
    else:
        print(f"  [WARN] MAE {mae:.1f}分钟 > 5分钟，建议检查数据质量或重新训练")

    if r2 > 0.4:
        print(f"  [OK] R2={r2:.3f} > 0.4，模型解释了40%以上的方差")
    else:
        print(f"  [INFO] R2={r2:.3f}，模型解释力有限，考虑增加特征")

    if abs(np.mean(residuals)) < 1.0:
        print(f"  [OK] 平均误差 {np.mean(residuals):.2f}分钟 < 1分钟，无明显系统偏差")
    else:
        direction = '低估' if np.mean(residuals) > 0 else '高估'
        print(f"  [WARN] 平均误差 {np.mean(residuals):+.2f}分钟，模型系统性地{direction}")

    return _eval_summary_dict(df_eval, mae, rmse, r2, residuals)


def _eval_summary_dict(df_eval, mae, rmse, r2, residuals):
    """将评估结果打包为 dict（供 API 返回 JSON）"""
    y_true = df_eval['实际出品时间_分钟']
    y_pred = df_eval['预测出品时间_分钟']
    summary = {
        'n_samples': len(df_eval),
        'mae': round(mae, 2),
        'rmse': round(rmse, 2),
        'r2': round(r2, 4),
        'actual_mean': round(y_true.mean(), 2),
        'pred_mean': round(y_pred.mean(), 2),
        'residual_mean': round(np.mean(residuals), 2),
        'residual_median': round(np.median(residuals), 2),
        'residual_p10': round(np.percentile(residuals, 10), 2),
        'residual_p90': round(np.percentile(residuals, 90), 2),
        'overestimate_pct': round((residuals < 0).sum() / len(residuals) * 100, 1),
        'underestimate_pct': round((residuals > 0).sum() / len(residuals) * 100, 1),
        'error_bands': {},
        'by_order_type': {},
        'by_cups': {},
        'by_preorder': {},
        'verdict': [],
    }
    # Error bands
    for lo, hi, label in [(0,2,'0-2min'),(2,5,'2-5min'),(5,10,'5-10min'),(10,30,'10-30min'),(30,999,'>30min')]:
        cnt = ((np.abs(residuals) >= lo) & (np.abs(residuals) < hi)).sum()
        summary['error_bands'][label] = {'count': int(cnt), 'pct': round(cnt/len(residuals)*100, 1)}

    # By order type
    if '订单类型' in df_eval.columns:
        for ot in sorted(df_eval['订单类型'].dropna().unique()):
            sub = df_eval[df_eval['订单类型'] == ot]
            if len(sub) >= 5:
                summary['by_order_type'][ot] = {
                    'n': len(sub), 'mae': round(mean_absolute_error(sub['实际出品时间_分钟'], sub['预测出品时间_分钟']), 2),
                    'actual_mean': round(sub['实际出品时间_分钟'].mean(), 1),
                    'pred_mean': round(sub['预测出品时间_分钟'].mean(), 1),
                }
    # By cups
    if 'cups' in df_eval.columns:
        for lo, hi, label in [(1,1,'1杯'),(2,2,'2杯'),(3,5,'3-5杯'),(6,10,'6-10杯'),(11,99,'11+杯')]:
            sub = df_eval[(df_eval['cups']>=lo)&(df_eval['cups']<=hi)]
            if len(sub) >= 5:
                summary['by_cups'][label] = {
                    'n': len(sub), 'mae': round(mean_absolute_error(sub['实际出品时间_分钟'], sub['预测出品时间_分钟']), 2),
                    'actual_mean': round(sub['实际出品时间_分钟'].mean(), 1),
                    'pred_mean': round(sub['预测出品时间_分钟'].mean(), 1),
                }
    # By preorder
    if 'is_preorder' in df_eval.columns:
        for po, label in [(0,'普通单'),(1,'预订单')]:
            sub = df_eval[df_eval['is_preorder']==po]
            if len(sub) >= 3:
                summary['by_preorder'][label] = {
                    'n': len(sub), 'mae': round(mean_absolute_error(sub['实际出品时间_分钟'], sub['预测出品时间_分钟']), 2),
                    'actual_mean': round(sub['实际出品时间_分钟'].mean(), 1),
                    'pred_mean': round(sub['预测出品时间_分钟'].mean(), 1),
                }

    # Verdict
    if mae < 3:
        summary['verdict'].append('MAE<3分钟，满足顾客端预估')
    elif mae < 5:
        summary['verdict'].append(f'MAE={mae:.1f}分钟，满足运营参考')
    else:
        summary['verdict'].append(f'MAE={mae:.1f}分钟，建议优化')
    if r2 > 0.4:
        summary['verdict'].append(f'R2={r2:.3f}>0.4，解释力良好')
    else:
        summary['verdict'].append(f'R2={r2:.3f}，解释力有限')
    if abs(np.mean(residuals)) < 1.0:
        summary['verdict'].append('无明显系统偏差')
    else:
        d = '低估' if np.mean(residuals) > 0 else '高估'
        summary['verdict'].append(f'系统性{d}')

    return summary


# ============================================================
# 可编程调用的 pipeline（供 Flask 等外部调用）
# ============================================================
def predict_pipeline(input_path, output_path=None, model_dir=None):
    """完整的预测流水线，返回 (result_df, eval_dict_or_None)"""
    if model_dir is None:
        model_dir = SCRIPT_DIR
    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + '_预测结果.csv'

    model, ot_map, st_map, st_te, gmean, store_bias, cons_off, pre_model, pre_feat = \
        load_model_and_encoders(model_dir)
    df = load_data(input_path)
    df = build_features(df, ot_map, st_map, st_te, gmean)
    df = run_predict(model, df, store_bias, cons_off, pre_model, pre_feat)
    result = save_results(df, output_path)

    eval_dict = None
    if '制作完成时间' in df.columns:
        eval_dict = run_evaluation(df)

    return result, eval_dict


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='茶饮门店出品时间预测 —— 用已有 XGBoost 模型对新订单做推理',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python predict.py 今日订单.csv
  python predict.py 今日订单.csv -o 预测结果.csv
  python predict.py 今日订单.csv --model-dir D:/model/

输入CSV必须含以下列:
  点单完成时间, 杯数, 订单类型, 门店编号
        """
    )
    parser.add_argument('input', help='输入 CSV 文件路径')
    parser.add_argument('-o', '--output', default=None,
                        help='输出 CSV 路径（默认: <输入>_预测结果.csv）')
    parser.add_argument('--model-dir', default=SCRIPT_DIR,
                        help=f'模型文件所在目录（默认: 本脚本所在目录）')
    args = parser.parse_args()

    output = args.output or f"{os.path.splitext(args.input)[0]}_预测结果.csv"

    print("=" * 60)
    print("茶饮门店出品时间预测 —— 推理模式")
    print("=" * 60)

    # 加载模型
    model, ot_map, st_map, st_te, gmean, store_bias, cons_off, pre_model, pre_feat = \
        load_model_and_encoders(args.model_dir)

    # 数据处理 + 预测 + 保存
    df = load_data(args.input)
    df = build_features(df, ot_map, st_map, st_te, gmean)
    df = run_predict(model, df, store_bias, cons_off, pre_model, pre_feat)
    result = save_results(df, output)

    print("\n" + "=" * 60)
    print("预测汇总:")
    print(f"  总订单数:          {len(result):,}")
    print(f"  平均预测出品时间:   {result['预测出品时间_分钟'].mean():.1f} 分钟")
    print(f"  最短/最长:          {result['预测出品时间_分钟'].min():.1f} / "
          f"{result['预测出品时间_分钟'].max():.1f} 分钟")

    # 评估模式：如果数据包含 制作完成时间，自动计算准确度
    if '制作完成时间' in df.columns:
        run_evaluation(df)

    print("\n[OK] 完成!")


if __name__ == '__main__':
    main()
