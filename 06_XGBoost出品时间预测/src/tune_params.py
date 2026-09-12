#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XGBoost 参数调优脚本
====================
在普通单数据上搜索最优参数，使用 TimeSeriesSplit 交叉验证。
"""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.metrics import mean_absolute_error
import xgboost as xgb
import os, sys, time, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "叫号队列列表 (58).csv")
RANDOM_STATE = 42

print("=" * 60)
print("XGBoost 参数调优")
print("=" * 60)

# ============================================================
# 1. 加载 + 清洗（复用训练脚本逻辑）
# ============================================================
print("\n[1] 加载数据...")
for enc in ['utf-8-sig','gbk','gb2312','gb18030']:
    try:
        df = pd.read_csv(DATA_PATH, encoding=enc, low_memory=False)
        break
    except: continue

df['点完'] = pd.to_datetime(df['点单完成时间'], errors='coerce')
df['做完'] = pd.to_datetime(df['制作完成时间'], errors='coerce')
df['开始'] = pd.to_datetime(df['点单开始时间'], errors='coerce')
df = df.dropna(subset=['点完','做完'])
df['出品'] = (df['做完'] - df['点完']).dt.total_seconds() / 60
df = df[(df['出品']>0)&(df['出品']<=180)]
df['杯数'] = pd.to_numeric(df['杯数'],errors='coerce').fillna(1).clip(1,30).astype(int)
df['cups'] = df['杯数']  # alias for feature name consistency
df['is_preorder'] = df['是否预订单？'].apply(
    lambda x: 0 if pd.isna(x) or str(x).strip() in ('','nan','NaN') else 1)
df['date'] = df['点完'].dt.date

# Only regular orders
df = df[df['is_preorder']==0].copy()
print(f"  普通单: {len(df):,}")

# ============================================================
# 2. 特征工程（精简版，与训练脚本一致）
# ============================================================
print("\n[2] 特征工程...")
dt = df['点完']
df['hour'] = dt.dt.hour
df['minute'] = dt.dt.minute
df['day_of_week'] = dt.dt.dayofweek
df['is_weekend'] = (df['day_of_week']>=5).astype(int)

def get_period(h):
    if h<=5: return 0
    elif h<=9: return 1
    elif h<=13: return 2
    elif h<=16: return 3
    elif h<=19: return 4
    else: return 5

df['period'] = df['hour'].apply(get_period)
df['is_lunch_peak'] = df['hour'].between(11,13).astype(int)
df['is_dinner_peak'] = df['hour'].between(17,19).astype(int)
df['hour_sin'] = np.sin(2*np.pi*df['hour']/24)
df['hour_cos'] = np.cos(2*np.pi*df['hour']/24)
df['order_entry_seconds'] = (df['点完']-df['开始']).dt.total_seconds().fillna(0).clip(0,300)

from sklearn.preprocessing import LabelEncoder
le_order = LabelEncoder()
df['order_type_enc'] = le_order.fit_transform(df['订单类型'].astype(str))
df['is_delivery'] = df['订单类型'].isin(['美团','饿了么']).astype(int)
df['is_online'] = (df['订单类型']!='POS').astype(int)

le_store = LabelEncoder()
df['store_enc'] = le_store.fit_transform(df['门店编号'].astype(str))

# Concurrent features (simplified)
df['date_hour'] = df['点完'].dt.strftime('%Y-%m-%d %H')
df['concurrent_hourly'] = df.groupby(['门店编号','date_hour'])['date_hour'].transform('count')
df['date_period'] = df['date'].astype(str)+'_'+df['period'].astype(str)
df['concurrent_periodly'] = df.groupby(['门店编号','date_period'])['date_period'].transform('count')
avg = df.groupby(['门店编号','period'])['concurrent_periodly'].transform('mean')
df['load_index'] = (df['concurrent_periodly']/(avg+1e-6)).clip(0,10)

# --- NEW FEATURES ---
# Store-hour interaction: some stores are slow at specific hours
df['store_hour_interact'] = df['store_enc'].astype(str) + '_' + df['hour'].astype(str)
le_interact = LabelEncoder()
df['store_hour_interact_enc'] = le_interact.fit_transform(df['store_hour_interact'])
# Cap high-cardinality features (keep top 500, rest = -1)
vc = df['store_hour_interact_enc'].value_counts()
top500 = vc.head(500).index
df['store_hour_enc'] = df['store_hour_interact_enc'].apply(lambda x: x if x in top500 else -1)

# Cup x delivery interaction
df['cups_x_delivery'] = df['杯数'] * df['is_delivery']

# Period x delivery
df['period_x_delivery'] = df['period'] * df['is_delivery']

FEATURES = [
    'hour','minute','day_of_week','is_weekend','period',
    'is_lunch_peak','is_dinner_peak','hour_sin','hour_cos',
    'order_entry_seconds',
    'cups',
    'order_type_enc','is_delivery','is_online',
    'store_enc',
    'concurrent_hourly','concurrent_periodly','load_index',
    'store_hour_enc',
    'cups_x_delivery','period_x_delivery',
]
print(f"  特征数: {len(FEATURES)}")

# ============================================================
# 3. Train/Test split (time-based)
# ============================================================
print("\n[3] 数据划分...")
dates = sorted(df['date'].unique())
test_date = dates[-1]
train_dates = dates[:-1]
df_train = df[df['date'].isin(train_dates)].copy()
df_test = df[df['date']==test_date].copy()
print(f"  Train: {len(df_train):,}  Test: {len(df_test):,}")

# Target encoding
store_mean = df_train.groupby('门店编号')['出品'].mean()
df_train['store_target_enc'] = df_train['门店编号'].map(store_mean).fillna(df_train['出品'].mean())
df_test['store_target_enc'] = df_test['门店编号'].map(store_mean).fillna(df_train['出品'].mean())
FEATURES.append('store_target_enc')
print(f"  特征数(含target_enc): {len(FEATURES)}")

X_train = df_train[FEATURES].values.astype(np.float32)
y_train = df_train['出品'].values
X_test = df_test[FEATURES].values.astype(np.float32)
y_test = df_test['出品'].values

from sklearn.impute import SimpleImputer
imp = SimpleImputer(strategy='median')
X_train = imp.fit_transform(X_train)
X_test = imp.transform(X_test)

# ============================================================
# 4. Randomized Search (on 30% sample for speed)
# ============================================================
print("\n[4] RandomizedSearchCV...")
np.random.seed(RANDOM_STATE)
sample_idx = np.random.choice(len(X_train), int(len(X_train)*0.3), replace=False)
X_sample = X_train[sample_idx]
y_sample = y_train[sample_idx]

# TimeSeriesSplit CV
tscv = TimeSeriesSplit(n_splits=3)

param_dist = {
    'learning_rate': [0.01, 0.02, 0.03, 0.05],
    'max_depth': [4, 5, 6, 7],
    'min_child_weight': [5, 10, 15, 20],
    'subsample': [0.7, 0.8, 0.85, 0.9],
    'colsample_bytree': [0.6, 0.7, 0.8, 0.9],
    'reg_alpha': [0.1, 0.3, 0.5, 1.0, 2.0],
    'reg_lambda': [0.5, 1.0, 2.0, 5.0],
    'gamma': [0.0, 0.1, 0.2, 0.5],
}

base = xgb.XGBRegressor(
    objective='reg:squarederror',
    n_estimators=500,  # fixed for CV (no early stopping in grid search)
    random_state=RANDOM_STATE,
    n_jobs=-1,
    verbosity=0,
)

search = RandomizedSearchCV(
    base, param_dist,
    n_iter=40,
    cv=tscv,
    scoring='neg_mean_absolute_error',
    verbose=1,
    random_state=RANDOM_STATE,
    n_jobs=-1,
)

t0 = time.time()
search.fit(X_sample, y_sample)
elapsed = time.time() - t0
print(f"\n  搜索耗时: {elapsed:.0f}s")
print(f"  Best CV MAE: {-search.best_score_:.3f}")
print(f"  Best params: {search.best_params_}")

# ============================================================
# 5. Retrain with best params on FULL data
# ============================================================
print("\n[5] 用最优参数全量训练...")
best_params = search.best_params_.copy()
best_params.update({
    'objective': 'reg:squarederror',
    'n_estimators': 2000,
    'early_stopping_rounds': 100,
    'random_state': RANDOM_STATE,
    'n_jobs': -1,
    'verbosity': 0,
})

model = xgb.XGBRegressor(**best_params)
model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

y_pred_train = model.predict(X_train)
y_pred_test = model.predict(X_test)
train_mae = mean_absolute_error(y_train, y_pred_train)
test_mae = mean_absolute_error(y_test, y_pred_test)
from sklearn.metrics import r2_score
test_r2 = r2_score(y_test, y_pred_test)

print(f"  Train MAE: {train_mae:.3f}  Test MAE: {test_mae:.3f}  R2: {test_r2:.4f}")
print(f"  Best n_estimators: {model.get_booster().best_iteration}")

# ============================================================
# 6. Feature importance
# ============================================================
print("\n[6] 特征重要性 Top 15:")
imp = model.feature_importances_
imp_df = pd.DataFrame({'feature':FEATURES,'pct':imp/imp.sum()*100}).sort_values('pct',ascending=False)
for _, row in imp_df.head(15).iterrows():
    bar = '#'*int(row['pct'])
    print(f"  {row['feature']:<25s} {row['pct']:5.1f}% {bar}")

# ============================================================
# 7. Compare with current params
# ============================================================
print("\n[7] 对比当前参数...")
current_params = {
    'learning_rate': 0.03, 'max_depth': 5, 'min_child_weight': 10,
    'subsample': 0.85, 'colsample_bytree': 0.8,
    'reg_alpha': 0.5, 'reg_lambda': 2.0, 'gamma': 0.1,
    'objective': 'reg:squarederror', 'n_estimators': 2000,
    'early_stopping_rounds': 100, 'random_state': RANDOM_STATE,
    'n_jobs': -1, 'verbosity': 0,
}
cur_model = xgb.XGBRegressor(**current_params)
cur_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
cur_pred = cur_model.predict(X_test)
cur_mae = mean_absolute_error(y_test, cur_pred)

print(f"  当前参数 Test MAE: {cur_mae:.3f}")
print(f"  最优参数 Test MAE: {test_mae:.3f}")
print(f"  改善: {cur_mae - test_mae:+.3f} 分钟 ({(cur_mae-test_mae)/cur_mae*100:+.1f}%)")

# ============================================================
# 8. Save recommendation
# ============================================================
print("\n[8] 推荐参数:")
for k, v in best_params.items():
    if k not in ['objective','n_estimators','early_stopping_rounds','random_state','n_jobs','verbosity']:
        print(f"  {k}: {v}")

# Save to JSON for the training script
out = {k: v for k, v in best_params.items()
       if k not in ['objective','n_estimators','early_stopping_rounds','random_state','n_jobs','verbosity']}
with open('tuned_params.json', 'w') as f:
    json.dump(out, f, indent=2)
print("\n  参数已保存至: tuned_params.json")
print("\n[OK] 调优完成!")
