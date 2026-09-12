#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
茶饮门店出品时间预测 —— XGBoost 基线模型
============================================
基于《出品时间预测建模思路.md》的要求实现：
  - 目标：预测出品时间（点单完成 → 制作完成，单位：分钟）
  - 预测时间点：点单完成那一刻（只用此刻之前已知的信息）
  - 特征工程：时间特征 + 订单特征 + 门店特征 + 构造特征
  - 数据划分：按时序划分（前6天训练，最后1天测试）
  - 验证策略：TimeSeriesSplit 滚动窗口交叉验证
  - 评估：MAE / RMSE / R² + 分群评估 + 残差分析
"""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
import xgboost as xgb

import os
import sys
import time as time_module

# ============================================================
# 0. 全局设置
# ============================================================
DATA_PATH = r"D:\work\叫号\data\combined_train.csv"
OUTPUT_DIR = r"D:\work\叫号"
RANDOM_STATE = 42

print("=" * 70)
print("茶饮门店出品时间预测 —— XGBoost 模型")
print("=" * 70)


# ============================================================
# 1. 数据加载
# ============================================================
print("\n[1/7] 数据加载...")
t0 = time_module.time()

# 自动探测编码：先试 UTF-8-SIG，失败则试 GBK
for _enc in ['utf-8-sig', 'gbk', 'gb2312', 'gb18030']:
    try:
        df = pd.read_csv(DATA_PATH, encoding=_enc, low_memory=False, dtype={
            '订单编号': str,
            '订单显示编号': str,
            '顾客昵称': str,
            '顾客手机号': str,
            '取单号': str,
            '杯数': float,
            '订单类型': str,
            '门店编号': str,
            '门店名称': str,
            '点单开始时间': str,
            '点单完成时间': str,
            '制作完成时间': str,
            '点单时间': str,
            '出品时间': str,
            '是否预订单？': str,
            'expect_time': str,
            '订单上PAD时间': str,
        })
        break
    except (UnicodeDecodeError, UnicodeError):
        continue
else:
    raise RuntimeError("无法识别文件编码，请将CSV另存为 UTF-8 格式")

n_raw = len(df)
print(f"  原始数据行数: {n_raw:,}")
print(f"  原始列数: {len(df.columns)}")
print(f"  列名: {list(df.columns)}")

# ============================================================
# 2. 数据清洗
# ============================================================
print("\n[2/7] 数据清洗...")

# --- 2.1 解析时间字段 ---
print("  解析时间字段...")
df['点单开始时间_dt'] = pd.to_datetime(df['点单开始时间'], errors='coerce')
df['点单完成时间_dt'] = pd.to_datetime(df['点单完成时间'], errors='coerce')
df['制作完成时间_dt'] = pd.to_datetime(df['制作完成时间'], errors='coerce')

# 检查解析失败的占比
bad_start = df['点单开始时间_dt'].isna().sum()
bad_complete = df['点单完成时间_dt'].isna().sum()
bad_make = df['制作完成时间_dt'].isna().sum()
print(f"  点单开始时间解析失败: {bad_start} ({bad_start/n_raw*100:.2f}%)")
print(f"  点单完成时间解析失败: {bad_complete} ({bad_complete/n_raw*100:.2f}%)")
print(f"  制作完成时间解析失败: {bad_make} ({bad_make/n_raw*100:.2f}%)")

# 删除时间解析失败的行
df = df.dropna(subset=['点单完成时间_dt', '制作完成时间_dt']).copy()
print(f"  删除时间解析失败后: {len(df):,} 行")

# --- 2.1b 点单耗时（秒）：从点单开始到点单完成的时间差 ---
df['order_entry_seconds'] = (
    df['点单完成时间_dt'] - df['点单开始时间_dt']
).dt.total_seconds().fillna(0).clip(0, 300)
n_nonzero_entry = (df['order_entry_seconds'] > 0).sum()
print(f"  点单耗时 > 0 的订单: {n_nonzero_entry:,} ({n_nonzero_entry/len(df)*100:.1f}%)")
print(f"  点单耗时统计: mean={df['order_entry_seconds'].mean():.1f}秒, "
      f"P50={df['order_entry_seconds'].median():.1f}秒, "
      f"P99={df['order_entry_seconds'].quantile(0.99):.1f}秒")

# --- 2.2 计算目标变量：出品时间（分钟）---
print("  计算目标变量...")
df['出品时间_分钟'] = (
    df['制作完成时间_dt'] - df['点单完成时间_dt']
).dt.total_seconds() / 60.0

# 过滤异常值：出品时间 <= 0 或 > 180 分钟
bad_target = (df['出品时间_分钟'] <= 0) | (df['出品时间_分钟'] > 180)
n_bad_target = bad_target.sum()
df = df[~bad_target].copy()
print(f"  过滤出品时间异常值 (≤0 or >180min): {n_bad_target} 行")
print(f"  过滤后: {len(df):,} 行")

# --- 2.3 清洗杯数 ---
df['杯数'] = pd.to_numeric(df['杯数'], errors='coerce')
bad_cups = df['杯数'].isna()
df = df[~bad_cups].copy()
df['杯数'] = df['杯数'].clip(1, 30).astype(int)
print(f"  过滤杯数异常: {bad_cups.sum()} 行, 最终 {len(df):,} 行")

# --- 2.4 预订单标记 ---
# 检查 是否预订单？ 列：非空且非 "nan" 即为预订单
df['is_preorder'] = df['是否预订单？'].apply(
    lambda x: 0 if pd.isna(x) or str(x).strip() in ('', 'nan', 'NaN') else 1
)
n_preorder = df['is_preorder'].sum()
print(f"  预订单数量: {n_preorder:,} ({n_preorder/len(df)*100:.2f}%)")

# --- 2.4b 解析 expect_time（预订单的期望取餐时间）---
df['expect_time_dt'] = pd.to_datetime(df['expect_time'], errors='coerce')
# 计算距离期望取餐还有多少小时（仅预订单有效）
df['hours_until_expect'] = (
    df['expect_time_dt'] - df['点单完成时间_dt']
).dt.total_seconds() / 3600.0
df['hours_until_expect'] = df['hours_until_expect'].fillna(-1).clip(-1, 48)

# --- 2.5 提取日期（用于时序划分）---
df['date'] = df['点单完成时间_dt'].dt.date
print(f"  数据日期范围: {df['date'].min()} ~ {df['date'].max()}")
print(f"  日期分布:")
for d, cnt in df['date'].value_counts().sort_index().items():
    print(f"    {d}: {cnt:,} 单")

print(f"  数据清洗耗时: {time_module.time() - t0:.1f}s")


# ============================================================
# 3. 特征工程（严格遵循建模思路文档 §五）
# ============================================================
print("\n[3/7] 特征工程...")
t0 = time_module.time()

# --- 3.1 时间特征（从点单完成时间拆出 11 个特征）---
print("  构建时间特征...")
dt = df['点单完成时间_dt']

df['hour'] = dt.dt.hour
df['minute'] = dt.dt.minute
df['day_of_week'] = dt.dt.dayofweek  # 0=Mon, 6=Sun
df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)

# 时段分段：深夜(0-5) / 早间(6-9) / 午高峰(10-13) / 午后(14-16) / 晚高峰(17-19) / 晚间(20-23)
def get_period(h):
    if 0 <= h <= 5:
        return 0   # 深夜
    elif 6 <= h <= 9:
        return 1   # 早间
    elif 10 <= h <= 13:
        return 2   # 午高峰
    elif 14 <= h <= 16:
        return 3   # 午后
    elif 17 <= h <= 19:
        return 4   # 晚高峰
    else:
        return 5   # 晚间

df['period'] = df['hour'].apply(get_period)
df['is_lunch_peak'] = df['hour'].between(11, 13).astype(int)
df['is_dinner_peak'] = df['hour'].between(17, 19).astype(int)

# 循环编码（让 23 和 0 在空间中相邻）
df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)

print(f"  时段分布:")
period_names = {0: '深夜(0-5)', 1: '早间(6-9)', 2: '午高峰(10-13)',
                3: '午后(14-16)', 4: '晚高峰(17-19)', 5: '晚间(20-23)'}
for p, cnt in df['period'].value_counts().sort_index().items():
    print(f"    {period_names[p]}: {cnt:,} 单")

# --- 3.2 杯数特征 ---
print("  构建杯数特征...")
df['cups'] = df['杯数'].clip(1, 30)
print(f"  杯数分布: mean={df['cups'].mean():.2f}, median={df['cups'].median():.0f}, "
      f"max={df['cups'].max():.0f}")

# --- 3.3 订单类型特征 ---
print("  构建订单类型特征...")
# 原始类别编码
le_order = LabelEncoder()
df['order_type_enc'] = le_order.fit_transform(df['订单类型'].astype(str))
print(f"  订单类型: {dict(zip(le_order.classes_, le_order.transform(le_order.classes_)))}")

# 外卖标记
df['is_delivery'] = df['订单类型'].isin(['美团', '饿了么']).astype(int)
# 线上渠道标记
df['is_online'] = (df['订单类型'] != 'POS').astype(int)
print(f"  外卖占比: {df['is_delivery'].mean()*100:.1f}%")
print(f"  线上渠道占比: {df['is_online'].mean()*100:.1f}%")

# --- 3.4 门店特征 ---
print("  构建门店特征...")
# Label Encoding
le_store = LabelEncoder()
df['store_enc'] = le_store.fit_transform(df['门店编号'].astype(str))
n_stores = len(le_store.classes_)
print(f"  门店数量: {n_stores}")

# Target Encoding（安全做法：按时序分组后逐日计算历史均值，避免未来信息泄漏）
# 这里简化处理：先对整个数据集计算，训练时只用训练集重算
# 为防泄漏，我们将在训练/测试拆分后分别处理
df['store_target_enc'] = np.nan  # 占位，稍后填充

# --- 3.5 构造特征：并发与负载 ---
print("  构建并发与负载特征...")

# 3.5.1 同门店同日同小时订单数（反映当前繁忙程度）
df['date_hour'] = df['点单完成时间_dt'].dt.strftime('%Y-%m-%d %H')
concurrent = df.groupby(['门店编号', 'date_hour']).size().reset_index(name='concurrent_hourly')
df = df.merge(concurrent, on=['门店编号', 'date_hour'], how='left')
print(f"  同门店同日同小时并发量: mean={df['concurrent_hourly'].mean():.1f}, "
      f"max={df['concurrent_hourly'].max():.0f}")

# 3.5.2 同门店同日同时段订单数（反映半天负载水平）
df['date_period'] = df['date'].astype(str) + '_' + df['period'].astype(str)
concurrent_period = df.groupby(['门店编号', 'date_period']).size().reset_index(name='concurrent_periodly')
df = df.merge(concurrent_period, on=['门店编号', 'date_period'], how='left')
print(f"  同门店同日同时段并发量: mean={df['concurrent_periodly'].mean():.1f}, "
      f"max={df['concurrent_periodly'].max():.0f}")

# 3.5.3 门店负载指数 = 当前并发量 / 该门店该时段的历史平均并发量
# （安全计算：用每日全局均值近似历史均值，避免行级泄漏）
store_period_avg = df.groupby(['门店编号', 'period'])['concurrent_periodly'].transform('mean')
df['load_index'] = df['concurrent_periodly'] / (store_period_avg + 1e-6)
df['load_index'] = df['load_index'].clip(0, 10)
print(f"  负载指数: mean={df['load_index'].mean():.2f}, std={df['load_index'].std():.2f}")

# 3.5.4 交互特征（新）
print("  构建交互特征...")
# 门店×小时交互：某些门店在特定时段表现不同
df['store_hour_key'] = df['store_enc'].astype(str) + '_' + df['hour'].astype(str)
# 只保留高频组合（Top 500），低频归为 -1
vc = df['store_hour_key'].value_counts()
top500 = set(vc.head(500).index)
df['store_hour_enc'] = df['store_hour_key'].apply(lambda x: hash(x) % 10000 if x in top500 else -1)

# 杯数×外卖交互：外卖大单可能更慢
df['cups_x_delivery'] = df['cups'] * df['is_delivery']

# 时段×外卖交互：外卖在高峰期可能更慢
df['period_x_delivery'] = df['period'] * df['is_delivery']

print(f"  store_hour 高频组合: {len(top500)}, cups_x_delivery均值: {df['cups_x_delivery'].mean():.1f}")

# 3.5.5 排队位置特征（核心新增）
print("  构建排队位置特征...")
t_q = time_module.time()
# 事件驱动算法：每条订单有"进入队列"(点单完成)和"离开队列"(制作完成)两个事件
# 当新订单进入时，queue_ahead = 当前仍在队列中的订单数
events = []
for i, (_, row) in enumerate(df.iterrows()):
    events.append((row['门店编号'], row['点单完成时间_dt'], 0, i))  # 0=进入
    events.append((row['门店编号'], row['制作完成时间_dt'], 1, i))  # 1=离开
events.sort(key=lambda x: (x[0], x[1], x[2]))  # 按门店→时间→事件类型排序

queue_ahead = np.zeros(len(df), dtype=int)
queue_cups_ahead = np.zeros(len(df), dtype=float)
active_per_store = {}   # store -> set of active order indices
active_cups = {}        # store -> total cups of active orders

for store, ts, evt, idx in events:
    cups_i = df.iloc[idx]['cups']
    if evt == 0:  # 订单进入队列
        if store in active_per_store:
            queue_ahead[idx] = len(active_per_store[store])
            queue_cups_ahead[idx] = active_cups.get(store, 0)
        else:
            active_per_store[store] = set()
            active_cups[store] = 0
        active_per_store[store].add(idx)
        active_cups[store] = active_cups.get(store, 0) + cups_i
    else:  # 订单离开队列（制作完成）
        if store in active_per_store and idx in active_per_store[store]:
            active_per_store[store].discard(idx)
            active_cups[store] = max(0, active_cups.get(store, 0) - cups_i)

df['queue_ahead'] = queue_ahead
df['queue_cups_ahead'] = queue_cups_ahead
# 排队负载比 = 当前排队杯数 / 该店该时段历史平均值（避免量纲影响）
df['queue_load_ratio'] = df['queue_cups_ahead'] / (df.groupby(['门店编号', 'period'])['queue_cups_ahead'].transform('mean') + 1e-6)
df['queue_load_ratio'] = df['queue_load_ratio'].clip(0, 10)

n_queued = (df['queue_ahead'] > 0).sum()
print(f"  排队>0的订单: {n_queued:,} ({n_queued/len(df)*100:.1f}%)")
print(f"  queue_ahead: mean={df['queue_ahead'].mean():.1f}, max={df['queue_ahead'].max():.0f}")
print(f"  queue_cups_ahead: mean={df['queue_cups_ahead'].mean():.1f}, max={df['queue_cups_ahead'].max():.0f}")
print(f"  排队特征耗时: {time_module.time() - t_q:.1f}s")

print(f"  特征工程耗时: {time_module.time() - t0:.1f}s")

# ============================================================
# OPTIMIZATION P0: 预订单与普通单分开
# ============================================================
print("\n[3b] 拆分普通单 / 预订单...")
df_regular = df[df['is_preorder'] == 0].copy()
df_preorder = df[df['is_preorder'] == 1].copy()
print(f"  普通单: {len(df_regular):,} 条  |  预订单: {len(df_preorder):,} 条")

# --- 普通单特征列表（去掉 is_preorder，全部为0无意义）---
FEATURE_COLS_REGULAR = [
    'hour', 'minute', 'day_of_week', 'is_weekend', 'period',
    'is_lunch_peak', 'is_dinner_peak', 'hour_sin', 'hour_cos',
    'order_entry_seconds',
    'cups',
    'order_type_enc', 'is_delivery', 'is_online',
    'store_enc',
    'concurrent_hourly', 'concurrent_periodly', 'load_index',
    'store_hour_enc',
    'cups_x_delivery', 'period_x_delivery',
    'queue_ahead', 'queue_cups_ahead', 'queue_load_ratio',
]
# 共 24 个特征

# --- 预订单特征列表（用 expect_time 信息）---
FEATURE_COLS_PREORDER = [
    'cups', 'store_enc', 'order_type_enc',
    'hour', 'period', 'hours_until_expect',
]
# 共 6 个特征

TARGET_COL = '出品时间_分钟'
print(f"  普通单特征: {len(FEATURE_COLS_REGULAR)} 个")
print(f"  预订单特征: {len(FEATURE_COLS_PREORDER)} 个")


# ============================================================
# 4. 数据划分（对普通单按时序，预订单全量使用）
# ============================================================
print("\n[4/7] 数据划分（普通单按时序 / 预订单全量）...")

dates_sorted = sorted(df['date'].unique())
print(f"  共 {len(dates_sorted)} 个日期: {dates_sorted}")

test_date = dates_sorted[-1]
train_dates = dates_sorted[:-1]

# 普通单
reg_train = df_regular[df_regular['date'].isin(train_dates)].copy()
reg_test = df_regular[df_regular['date'] == test_date].copy()
print(f"  普通单 — 训练: {len(reg_train):,}  测试: {len(reg_test):,}")

# 预订单
pre_train = df_preorder[df_preorder['date'].isin(train_dates)].copy()
pre_test = df_preorder[df_preorder['date'] == test_date].copy()
print(f"  预订单 — 训练: {len(pre_train):,}  测试: {len(pre_test):,}")

# --- Target Encoding for regular orders ---
print("  计算门店 Target Encoding（普通单）...")
store_mean_target = reg_train.groupby('门店编号')[TARGET_COL].mean()
reg_train['store_target_enc'] = reg_train['门店编号'].map(store_mean_target)
reg_test['store_target_enc'] = reg_test['门店编号'].map(store_mean_target)
global_mean = reg_train[TARGET_COL].mean()
reg_test['store_target_enc'] = reg_test['store_target_enc'].fillna(global_mean)
reg_train['store_target_enc'] = reg_train['store_target_enc'].fillna(global_mean)

# 预订单也用同样的编码
pre_train['store_target_enc'] = pre_train['门店编号'].map(store_mean_target).fillna(global_mean)
pre_test['store_target_enc'] = pre_test['门店编号'].map(store_mean_target).fillna(global_mean)

# 实际可用特征
actual_features_reg = [f for f in FEATURE_COLS_REGULAR if f in reg_train.columns]
actual_features_pre = [f for f in FEATURE_COLS_PREORDER if f in pre_train.columns]
print(f"  普通单特征: {len(actual_features_reg)} 个")
print(f"  预订单特征: {len(actual_features_pre)} 个")

X_train_reg = reg_train[actual_features_reg].values
y_train_reg = reg_train[TARGET_COL].values
X_test_reg = reg_test[actual_features_reg].values
y_test_reg = reg_test[TARGET_COL].values

# Fill NaN
for arr in [X_train_reg, X_test_reg]:
    if np.any(np.isnan(arr)):
        from sklearn.impute import SimpleImputer
        arr[:] = SimpleImputer(strategy='median').fit_transform(arr)

print(f"  普通单 X_train: {X_train_reg.shape}  X_test: {X_test_reg.shape}")


# ============================================================
# 5. 训练（双模型 + 门店校准）
# ============================================================
print("\n[5/7] 模型训练...")
t0 = time_module.time()

# --- 5.1 XGBoost参数（P2: 调优） ---
base_params = {
    'objective': 'reg:squarederror',
    'learning_rate': 0.05,       # tuned: 0.05 (higher LR, more trees)
    'max_depth': 7,              # tuned: 7 (deeper trees for interactions)
    'min_child_weight': 20,      # tuned: 20 (more conservative leaves)
    'subsample': 0.8,            # tuned: 0.8
    'colsample_bytree': 0.7,     # tuned: 0.7 (more column subsampling)
    'reg_alpha': 0.1,            # tuned: 0.1 (lighter L1)
    'reg_lambda': 5.0,           # tuned: 5.0 (stronger L2)
    'gamma': 0.2,                # tuned: 0.2 (min split gain)
    'n_estimators': 1500,
    'early_stopping_rounds': 80,
    'random_state': RANDOM_STATE,
    'n_jobs': -1,
    'verbosity': 0,
}

print("  普通单模型参数:")
for k, v in base_params.items():
    print(f"    {k}: {v}")

# --- 5.2 训练普通单模型 ---
print("\n  [普通单] 训练 XGBoost...")
model = xgb.XGBRegressor(**base_params)
model.fit(
    X_train_reg, y_train_reg,
    eval_set=[(X_train_reg, y_train_reg), (X_test_reg, y_test_reg)],
    verbose=False,
)
actual_iters = model.get_booster().best_iteration
print(f"    实际迭代: {actual_iters}")
print(f"    训练耗时: {time_module.time() - t0:.1f}s")

# --- 5.3 门店级偏差校准（P1） ---
print("\n  [P1] 计算门店级校准系数...")
reg_train_eval = reg_train.copy()
reg_train_eval['pred_raw'] = model.predict(X_train_reg)
reg_train_eval['residual'] = reg_train_eval[TARGET_COL] - reg_train_eval['pred_raw']

# 每个门店的平均偏差（至少30条才做校准）
store_bias = reg_train_eval.groupby('门店编号').agg(
    bias=('residual', 'mean'),
    n=('residual', 'count'),
    std=('residual', 'std'),
).query('n >= 30')

# 截断极端偏差
store_bias['bias_clipped'] = store_bias['bias'].clip(-10, 10)
store_bias_dict = store_bias['bias_clipped'].to_dict()

n_calibrated = len(store_bias_dict)
uncorrected_bias = reg_train_eval['residual'].mean()
corrected_bias = (reg_train_eval['residual'] - reg_train_eval['门店编号'].map(store_bias_dict).fillna(0)).mean()
print(f"    校准门店数: {n_calibrated}")
print(f"    校准前系统偏差: {uncorrected_bias:+.2f}分钟 -> 校准后: {corrected_bias:+.2f}分钟")

# --- 保守偏移：宁可高估但不过度（P35残差取反，上限3分钟）---
TARGET_OVER_RATE = 0.65
residuals_after_cal = reg_train_eval["residual"] - reg_train_eval["门店编号"].map(store_bias_dict).fillna(0)
conservative_offset = max(0.5, min(-np.percentile(residuals_after_cal, 35), 3.0))
over_rate = (residuals_after_cal + conservative_offset < 0).sum() / len(residuals_after_cal)
print(f"    保守偏移: +{conservative_offset:.1f}min -> 高估率={over_rate*100:.0f}%")

# --- 5.4 预订单模型（简单位数预测） ---
# --- 5.4 预订单模型（XGBoost 回归，利用 expect_time） ---
print("\n  [预订单] 训练 XGBoost 回归模型...")
FEATURE_COLS_PREORDER = [
    'cups', 'store_enc', 'order_type_enc',
    'hour', 'period', 'hours_until_expect',
    'concurrent_hourly', 'load_index',
]
actual_features_pre = [f for f in FEATURE_COLS_PREORDER if f in pre_train.columns]
print(f"    预订单特征: {len(actual_features_pre)} 个")

X_pre_train = pre_train[actual_features_pre].values.astype(np.float32)
y_pre_train = pre_train[TARGET_COL].values
X_pre_test = pre_test[actual_features_pre].values.astype(np.float32)
y_pre_test = pre_test[TARGET_COL].values

from sklearn.impute import SimpleImputer as SI2
for arr in [X_pre_train, X_pre_test]:
    if np.any(np.isnan(arr)):
        arr[:] = SI2(strategy='median').fit_transform(arr)

pre_params = {
    'objective': 'reg:squarederror',
    'learning_rate': 0.03, 'max_depth': 4, 'min_child_weight': 15,
    'subsample': 0.8, 'colsample_bytree': 0.7,
    'reg_alpha': 1.0, 'reg_lambda': 5.0, 'gamma': 0.2,
    'n_estimators': 1000, 'early_stopping_rounds': 50,
    'random_state': RANDOM_STATE, 'n_jobs': -1, 'verbosity': 0,
}

pre_model = xgb.XGBRegressor(**pre_params)
pre_model.fit(
    X_pre_train, y_pre_train,
    eval_set=[(X_pre_train, y_pre_train), (X_pre_test, y_pre_test)],
    verbose=False,
)
pre_iters = pre_model.get_booster().best_iteration

y_pre_pred_test = pre_model.predict(X_pre_test)
pre_mae = mean_absolute_error(y_pre_test, y_pre_pred_test)

train_pre_mae = mean_absolute_error(y_pre_train, pre_model.predict(X_pre_train))
print(f"    迭代: {pre_iters}, Train MAE: {train_pre_mae:.2f}min, Test MAE: {pre_mae:.2f}min")
pre_imp = pre_model.feature_importances_
for k, v in sorted(zip(actual_features_pre, pre_imp), key=lambda x: -x[1]):
    print(f"      {k:<25s} {v/pre_imp.sum()*100:5.1f}%")

# ============================================================
# 6. 综合评估
# ============================================================
print("\n[6/7] 综合评估...")
print("=" * 70)

# --- 6.1 整体指标 ---
y_train_pred_raw = model.predict(X_train_reg)
y_test_pred_raw = model.predict(X_test_reg)

# 应用门店校准
y_train_pred = np.array([
    p - store_bias_dict.get(s, 0)
    for p, s in zip(y_train_pred_raw, reg_train['门店编号'])
])
y_test_pred = np.array([
    p - store_bias_dict.get(s, 0)
    for p, s in zip(y_test_pred_raw, reg_test['门店编号'])
])

train_mae = mean_absolute_error(y_train_reg, y_train_pred)
test_mae = mean_absolute_error(y_test_reg, y_test_pred)
train_rmse = np.sqrt(mean_squared_error(y_train_reg, y_train_pred))
test_rmse = np.sqrt(mean_squared_error(y_test_reg, y_test_pred))
train_r2 = r2_score(y_train_reg, y_train_pred)
test_r2 = r2_score(y_test_reg, y_test_pred)

print("\n--- 整体指标（普通单 + 校准后）---")
print(f"  {'指标':<15} {'训练集':>12} {'测试集':>12} {'差值':>12}")
print(f"  {'-'*51}")
print(f"  {'MAE (分钟)':<15} {train_mae:>12.3f} {test_mae:>12.3f} {test_mae-train_mae:>+12.3f}")
print(f"  {'RMSE (分钟)':<15} {train_rmse:>12.3f} {test_rmse:>12.3f} {test_rmse-train_rmse:>+12.3f}")
print(f"  {'R2':<15} {train_r2:>12.4f} {test_r2:>12.4f} {test_r2-train_r2:>+12.4f}")

# 预订单单独指标
print(f"\n--- 预订单指标 ---")
print(f"  预订单测试 MAE: {pre_mae:.2f} 分钟  (样本: {len(pre_test):,})")

# 综合指标（普通单+预订单，各自用各自的模型）
combined_actual = np.concatenate([y_test_reg, pre_test[TARGET_COL].values])
combined_pred = np.concatenate([y_test_pred, y_pre_pred_test])
combined_mae = mean_absolute_error(combined_actual, combined_pred)
combined_rmse = np.sqrt(mean_squared_error(combined_actual, combined_pred))
combined_r2 = r2_score(combined_actual, combined_pred)
print(f"\n--- 综合指标（普通单+预订单，分开预测）---")
print(f"  MAE:  {combined_mae:.2f} 分钟")
print(f"  RMSE: {combined_rmse:.2f} 分钟")
print(f"  R2:   {combined_r2:.4f}")

# --- 6.2 误差分布 ---
residuals = y_test_reg - y_test_pred
print("\n--- 误差分布（普通单测试集，校准后）---")
print(f"  均值: {np.mean(residuals):.3f} 分钟  (校准前={y_test_reg.mean()-y_test_pred_raw.mean():.3f})")
print(f"  中位数: {np.median(residuals):.3f} 分钟")
for p in [10, 25, 50, 75, 90]:
    print(f"  P{p}: {np.percentile(residuals, p):.3f} 分钟")

over = (residuals < 0).sum()
under = (residuals > 0).sum()
print(f"  高估 (预测>实际): {over:,} ({over/len(residuals)*100:.1f}%)")
print(f"  低估 (预测<实际): {under:,} ({under/len(residuals)*100:.1f}%)")

# --- 6.3 特征重要性 ---
print("\n--- 特征重要性（普通单模型，Top 15）---")
importance = model.feature_importances_
importance_df = pd.DataFrame({
    'feature': actual_features_reg,
    'importance_pct': importance / importance.sum() * 100,
}).sort_values('importance_pct', ascending=False)

for i, row in importance_df.head(15).iterrows():
    bar = '#' * int(row['importance_pct'] * 2)
    print(f"  {row['feature']:<25s} {row['importance_pct']:6.2f}% {bar}")

# --- 6.4 分群评估（普通单） ---
print("\n--- 分群评估（普通单测试集）---")
df_test_eval = reg_test.copy()
df_test_eval['pred'] = y_test_pred
df_test_eval['actual'] = y_test_reg
df_test_eval['residual'] = residuals

print("\n  [按订单类型]")
for ot in sorted(df_test_eval['订单类型'].dropna().unique()):
    sub = df_test_eval[df_test_eval['订单类型'] == ot]
    if len(sub) < 10: continue
    print(f"    {ot:<12s} {len(sub):>6,}条  MAE={mean_absolute_error(sub['actual'],sub['pred']):.2f}分  "
          f"实际={sub['actual'].mean():.1f}分  预测={sub['pred'].mean():.1f}分")

print("\n  [按杯数]")
for lo, hi, label in [(1,1,'1杯'),(2,2,'2杯'),(3,5,'3-5杯'),(6,10,'6-10杯'),(11,99,'11+杯')]:
    sub = df_test_eval[(df_test_eval['cups']>=lo)&(df_test_eval['cups']<=hi)]
    if len(sub) < 10: continue
    print(f"    {label:<10s} {len(sub):>6,}条  MAE={mean_absolute_error(sub['actual'],sub['pred']):.2f}分  "
          f"实际={sub['actual'].mean():.1f}分  预测={sub['pred'].mean():.1f}分")

# --- 6.5 过拟合诊断 ---
print("\n--- 过拟合诊断 ---")
mae_gap = test_mae - train_mae
print(f"  Train MAE: {train_mae:.3f}  |  Test MAE: {test_mae:.3f}  |  Gap: {mae_gap:+.3f}")
if test_mae > train_mae * 1.5:
    print("  [WARN] 可能过拟合")
elif test_mae < train_mae * 1.1:
    print("  [OK] 泛化良好")
else:
    print("  [INFO] 轻微过拟合")


# ============================================================
# 7. 交叉验证
# ============================================================
print("\n[7/7] TimeSeriesSplit 交叉验证（普通单）...")
train_dates_sorted = sorted(reg_train['date'].unique())
n_dates = len(train_dates_sorted)

if n_dates >= 4:
    fold_boundaries = [b for b in range(n_dates//3, n_dates-1)][-5:]
    print(f"  生成 {len(fold_boundaries)} folds")
    cv_scores = []
    for bi, boundary in enumerate(fold_boundaries):
        tr_mask = reg_train['date'].isin(train_dates_sorted[:boundary+1])
        val_mask = reg_train['date'].isin(train_dates_sorted[boundary+1:boundary+2])
        if not val_mask.any(): continue
        Xf_tr = reg_train.loc[tr_mask, actual_features_reg].values
        yf_tr = reg_train.loc[tr_mask, TARGET_COL].values
        Xf_val = reg_train.loc[val_mask, actual_features_reg].values
        yf_val = reg_train.loc[val_mask, TARGET_COL].values
        fm = xgb.XGBRegressor(**base_params)
        fm.fit(Xf_tr, yf_tr, eval_set=[(Xf_val, yf_val)], verbose=False)
        cv_scores.append(mean_absolute_error(yf_val, fm.predict(Xf_val)))
        print(f"  Fold {bi+1}: {train_dates_sorted[0]}~{train_dates_sorted[boundary]} -> "
              f"{train_dates_sorted[boundary+1]}  MAE={cv_scores[-1]:.3f}")
    if cv_scores:
        print(f"\n  CV MAE: {np.mean(cv_scores):.3f} ± {np.std(cv_scores):.3f}")
        print(f"  Test MAE: {test_mae:.3f}")
else:
    print("  天数不足，跳过CV")

# ============================================================
# 8. 保存模型
# ============================================================
print("\n" + "=" * 70)
print("保存模型...")

model_path = os.path.join(OUTPUT_DIR, 'xgboost_model.json')
model.save_model(model_path)
print(f"  普通单模型: {model_path}")

encoder_path = os.path.join(OUTPUT_DIR, 'model_encoders.npz')
np.savez(
    encoder_path,
    order_classes=le_order.classes_,
    store_classes=le_store.classes_,
    feature_names=actual_features_reg,
    feature_names_preorder=actual_features_pre,
    store_target_enc=store_mean_target.to_dict(),
    global_mean_target=global_mean,
    store_bias=store_bias_dict,
    conservative_offset=conservative_offset,
    preorder_feature_names=actual_features_pre,
)
print(f"  编码器+校准: {encoder_path}")

# Save pre-order model
pre_model_path = os.path.join(OUTPUT_DIR, 'xgboost_preorder_model.json')
pre_model.save_model(pre_model_path)
print(f"  预订单模型: {pre_model_path}")
print(f"  编码器+校准: {encoder_path}")

importance_df.to_csv(os.path.join(OUTPUT_DIR, 'evaluation_results.csv'),
                     index=False, encoding='utf-8-sig')

# ============================================================
# 9. 总结
# ============================================================
print("\n" + "=" * 70)
print("优化后模型总结")
print("=" * 70)
print(f"""
  架构:
    普通单: XGBoost ({len(actual_features_reg)}特征) + 门店偏差校准 ({n_calibrated}门店)
    预订单: XGBoost ({len(actual_features_pre)}特征, expect_time回归)

  普通单表现:
    训练集 MAE: {train_mae:.3f}分钟  |  R2: {train_r2:.4f}
    测试集 MAE: {test_mae:.3f}分钟  |  R2: {test_r2:.4f}
    系统偏差:   {np.mean(residuals):+.3f}分钟 (校准前={y_test_reg.mean()-y_test_pred_raw.mean():+.3f})

  预订单表现:
    测试 MAE:   {pre_mae:.2f}分钟

  综合:
    MAE: {combined_mae:.2f}分钟  |  R2: {combined_r2:.4f}
""")

print("[OK] 脚本执行完毕！")
