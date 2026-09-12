#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预测 vs 真实值 可视化分析
========================
用法: python visualize.py [输入CSV] [输出图片路径]
     若不指定输入，则自动对 test_sample.csv 做预测并画图
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import os, sys, warnings
warnings.filterwarnings('ignore')

# ============================================================
# 0. 设置中文字体
# ============================================================
plt.rcParams['font.size'] = 11
plt.rcParams['axes.unicode_minus'] = False
# Try to find a Chinese font
for fn in ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'Arial Unicode MS']:
    try:
        plt.rcParams['font.sans-serif'] = [fn]
        fig = plt.figure()
        fig.text(0.5, 0.5, 'test', fontfamily=fn)
        plt.close(fig)
        break
    except:
        continue

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from predict import predict_pipeline

# ============================================================
# 1. 获取数据
# ============================================================
if len(sys.argv) >= 2:
    csv_path = sys.argv[1]
else:
    csv_path = os.path.join(SCRIPT_DIR, 'test_sample.csv')
    if not os.path.exists(csv_path):
        print("Usage: python visualize.py <input.csv> [output.png]")
        sys.exit(1)

output_img = sys.argv[2] if len(sys.argv) >= 3 else os.path.join(SCRIPT_DIR, 'prediction_analysis.png')

print(f"Input:  {csv_path}")
print(f"Output: {output_img}")

# Run prediction pipeline to get results with ground truth
result_df, eval_dict = predict_pipeline(csv_path, model_dir=SCRIPT_DIR)

if eval_dict is None:
    print("ERROR: CSV must contain '制作完成时间' column for evaluation")
    sys.exit(1)

# Prepare data
df = result_df.copy()
# Need actual production time
df['完成'] = pd.to_datetime(df['制作完成时间'], errors='coerce')
df['点完'] = pd.to_datetime(df['点单完成时间'], errors='coerce')
df['实际'] = (df['完成'] - df['点完']).dt.total_seconds() / 60
df = df[(df['实际'] > 0) & (df['实际'] <= 180)].copy()

y_true = df['实际'].values
y_pred = df['预测出品时间_分钟'].values
residuals = y_true - y_pred

n = len(df)
mae = np.mean(np.abs(residuals))
rmse = np.sqrt(np.mean(residuals**2))
r2 = 1 - np.sum(residuals**2) / np.sum((y_true - y_true.mean())**2)

print(f"\nData: {n} valid samples, MAE={mae:.2f}, RMSE={rmse:.2f}, R2={r2:.3f}")

# ============================================================
# 2. 创建 3x3 图像矩阵
# ============================================================
fig, axes = plt.subplots(3, 3, figsize=(18, 16))
fig.suptitle(f'Prediction vs Actual Analysis (n={n:,}, MAE={mae:.2f}min, R2={r2:.3f})',
             fontsize=15, fontweight='bold', y=0.98)

# Color palette
blue = '#1a73e8'
orange = '#e37400'
green = '#188038'
red = '#c5221f'
gray = '#999999'

# --- Plot 1: Scatter (predicted vs actual) ---
ax = axes[0, 0]
ax.scatter(y_true, y_pred, alpha=0.15, s=4, c=blue, edgecolors='none')
lims = [0, max(y_true.max(), y_pred.max()) * 1.05]
ax.plot(lims, lims, '--', color=red, linewidth=1.5, alpha=0.7, label='Perfect')
ax.set_xlim(lims)
ax.set_ylim(lims)
ax.set_xlabel('Actual (min)')
ax.set_ylabel('Predicted (min)')
ax.set_title('Scatter: Predicted vs Actual')
ax.legend(loc='upper left')
# Add R2 and MAE annotation
ax.text(0.95, 0.05, f'MAE={mae:.2f}\nR2={r2:.3f}', transform=ax.transAxes,
        ha='right', va='bottom', fontsize=10, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

# --- Plot 2: Residual histogram ---
ax = axes[0, 1]
rng = max(abs(residuals.min()), abs(residuals.max()))
bins = np.linspace(-rng, rng, 61)
ax.hist(residuals, bins=bins, color=blue, alpha=0.7, edgecolor='white', linewidth=0.3)
ax.axvline(0, color=red, linewidth=1.5, linestyle='--')
ax.axvline(np.mean(residuals), color=orange, linewidth=1.5, linestyle='-', label=f'Mean={np.mean(residuals):+.2f}')
ax.axvline(np.median(residuals), color=green, linewidth=1.5, linestyle='-', label=f'Median={np.median(residuals):+.2f}')
ax.set_xlabel('Residual (Actual - Predicted, min)')
ax.set_ylabel('Count')
ax.set_title('Residual Distribution')
ax.legend(fontsize=8)

# --- Plot 3: Error by order type ---
ax = axes[0, 2]
if '订单类型' in df.columns:
    types = df.groupby('订单类型')['实际'].agg(['count', 'mean'])
    types = types[types['count'] >= 5].sort_values('mean')
    type_mae = {}
    for ot in types.index:
        sub = df[df['订单类型'] == ot]
        type_mae[ot] = np.mean(np.abs(sub['实际'].values - sub['预测出品时间_分钟'].values))
    labels = list(types.index)
    x = np.arange(len(labels))
    ax.bar(x - 0.15, [types.loc[l, 'mean'] for l in labels], 0.3, label='Actual Mean', color=blue, alpha=0.7)
    ax.bar(x + 0.15, [type_mae[l] for l in labels], 0.3, label='MAE', color=orange, alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=9)
    ax.set_ylabel('Minutes')
    ax.set_title('Actual Mean vs MAE by Order Type')
    ax.legend(fontsize=8)

# --- Plot 4: Error by cup count ---
ax = axes[1, 0]
cup_bins = [(1,1),(2,2),(3,5),(6,10),(11,99)]
cup_labels = ['1','2','3-5','6-10','11+']
cup_mae, cup_mean = [], []
for lo, hi in cup_bins:
    sub = df[(df['cups'] >= lo) & (df['cups'] <= hi)] if 'cups' in df.columns else df[(df['杯数'] >= lo) & (df['杯数'] <= hi)]
    if len(sub) >= 5:
        cup_mae.append(np.mean(np.abs(sub['实际'].values - sub['预测出品时间_分钟'].values)))
        cup_mean.append(sub['实际'].mean())
    else:
        cup_mae.append(0)
        cup_mean.append(0)
x = np.arange(len(cup_labels))
ax.bar(x - 0.15, cup_mean, 0.3, label='Actual Mean', color=blue, alpha=0.7)
ax.bar(x + 0.15, cup_mae, 0.3, label='MAE', color=orange, alpha=0.7)
ax.set_xticks(x)
ax.set_xticklabels(cup_labels)
ax.set_xlabel('Cups')
ax.set_ylabel('Minutes')
ax.set_title('Error by Cup Count')
ax.legend(fontsize=8)

# --- Plot 5: Error by hour ---
ax = axes[1, 1]
if 'hour' in df.columns:
    hours = sorted(df['hour'].unique())
    h_mae, h_count = [], []
    for h in hours:
        sub = df[df['hour'] == h]
        h_mae.append(np.mean(np.abs(sub['实际'].values - sub['预测出品时间_分钟'].values)))
        h_count.append(len(sub))
    ax2 = ax.twinx()
    bars = ax.bar(hours, h_count, alpha=0.3, color=gray, label='Count')
    ax2.plot(hours, h_mae, 'o-', color=blue, linewidth=2, markersize=4, label='MAE')
    ax2.axhline(y=mae, color=red, linestyle='--', linewidth=1, alpha=0.5, label=f'Overall MAE={mae:.1f}')
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Order Count', color=gray)
    ax2.set_ylabel('MAE (min)', color=blue)
    ax.set_title('Error by Hour of Day')
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1+lines2, labels1+labels2, fontsize=7, loc='upper left')

# --- Plot 6: Cumulative error distribution ---
ax = axes[1, 2]
abs_res = np.abs(residuals)
sorted_err = np.sort(abs_res)
cumulative = np.arange(1, len(sorted_err)+1) / len(sorted_err) * 100
ax.plot(sorted_err, cumulative, color=blue, linewidth=2)
ax.axvline(2, color=green, linestyle='--', alpha=0.5, label='2 min')
ax.axvline(5, color=orange, linestyle='--', alpha=0.5, label='5 min')
ax.axvline(10, color=red, linestyle='--', alpha=0.5, label='10 min')
# Annotate percentiles
for thr in [2, 5, 10]:
    pct = (abs_res <= thr).sum() / len(abs_res) * 100
    ax.annotate(f'{pct:.0f}%', xy=(thr, pct), xytext=(thr+2, pct+5),
                arrowprops=dict(arrowstyle='->', color=gray), fontsize=9)
ax.set_xlabel('Absolute Error (min)')
ax.set_ylabel('Cumulative %')
ax.set_title('Cumulative Error Distribution')
ax.legend(fontsize=8)

# --- Plot 7: Residual vs Predicted (heteroscedasticity) ---
ax = axes[2, 0]
ax.scatter(y_pred, residuals, alpha=0.15, s=4, c=blue, edgecolors='none')
ax.axhline(0, color=red, linewidth=1.5, linestyle='--')
# Add LOESS-like smoothing
from numpy.polynomial.polynomial import Polynomial
try:
    mask = y_pred <= np.percentile(y_pred, 95)
    x_s, y_s = y_pred[mask], residuals[mask]
    idx = np.argsort(x_s)
    window = max(50, len(x_s)//100)
    x_smoothed = np.convolve(x_s[idx], np.ones(window)/window, mode='valid')
    y_smoothed = np.convolve(y_s[idx], np.ones(window)/window, mode='valid')
    ax.plot(x_smoothed, y_smoothed, color=orange, linewidth=2, label='Trend')
except:
    pass
ax.set_xlabel('Predicted (min)')
ax.set_ylabel('Residual (Actual - Predicted, min)')
ax.set_title('Residual vs Predicted')
ax.legend(fontsize=8)

# --- Plot 8: Actual vs Predicted density ---
ax = axes[2, 1]
bins = np.linspace(0, np.percentile(y_true, 98), 50)
ax.hist(y_true, bins=bins, alpha=0.5, color=blue, label=f'Actual (mean={y_true.mean():.1f})', density=True)
ax.hist(y_pred, bins=bins, alpha=0.5, color=orange, label=f'Predicted (mean={y_pred.mean():.1f})', density=True)
ax.set_xlabel('Minutes')
ax.set_ylabel('Density')
ax.set_title('Distribution: Actual vs Predicted')
ax.legend(fontsize=8)

# --- Plot 9: Summary text ---
ax = axes[2, 2]
ax.axis('off')
summary_lines = [
    'SUMMARY',
    '='*40,
    f'Samples:        {n:,}',
    f'MAE:            {mae:.2f} min',
    f'RMSE:           {rmse:.2f} min',
    f'R2:             {r2:.4f}',
    f'',
    f'Actual Mean:    {y_true.mean():.2f} min',
    f'Predicted Mean: {y_pred.mean():.2f} min',
    f'Residual Mean:  {np.mean(residuals):+.2f} min',
    f'Residual Std:   {np.std(residuals):.2f} min',
    f'',
    f'Error within 2min:  {(abs_res<=2).sum()/n*100:.1f}%',
    f'Error within 5min:  {(abs_res<=5).sum()/n*100:.1f}%',
    f'Error within 10min: {(abs_res<=10).sum()/n*100:.1f}%',
    f'',
    f'Overestimate:  {(residuals<0).sum()/n*100:.1f}%',
    f'Underestimate: {(residuals>0).sum()/n*100:.1f}%',
]
y_pos = 0.95
for line in summary_lines:
    ax.text(0.05, y_pos, line, transform=ax.transAxes, fontfamily='monospace',
            fontsize=10, verticalalignment='top')
    y_pos -= 0.045

plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(output_img, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f'\nImage saved: {output_img}')
print('Done!')
