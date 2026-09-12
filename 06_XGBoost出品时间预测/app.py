#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, uuid
from flask import Flask, request, jsonify, send_file, render_template

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from predict import predict_pipeline

# 模板目录: 优先用同级 templates/，否则用 prediction_tool/templates/
_tmpl = os.path.join(SCRIPT_DIR, 'templates')
if not os.path.isdir(_tmpl):
    _tmpl = os.path.join(SCRIPT_DIR, 'prediction_tool', 'templates')

app = Flask(__name__, template_folder=_tmpl)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
UPLOAD_DIR = os.path.join(SCRIPT_DIR, 'web_uploads')
RESULT_DIR = os.path.join(SCRIPT_DIR, 'web_results')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/predict', methods=['POST'])
def api_predict():
    if 'file' not in request.files:
        return jsonify({'error': 'no file'}), 400
    file = request.files['file']
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.csv', '.xlsx', '.xls'):
        return jsonify({'error': '需要 .csv 或 .xlsx 文件'}), 400
    task_id = uuid.uuid4().hex[:8]
    in_path = os.path.join(UPLOAD_DIR, f'{task_id}_{file.filename}')
    file.save(in_path)
    out_path = os.path.join(RESULT_DIR, f'{task_id}_out.csv')
    try:
        result_df, eval_dict = predict_pipeline(in_path, out_path, SCRIPT_DIR)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    import pandas as pd, numpy as np
    pref = ['订单编号','订单类型','门店编号','门店名称','杯数','点单完成时间','预测出品时间_分钟','预测出品时间_格式化','is_preorder']
    cols = [c for c in pref if c in result_df.columns]
    preview = result_df[cols].head(200)
    records = []
    for _, row in preview.iterrows():
        r = {}
        for c in cols:
            v = row[c]
            if pd.isna(v): r[c] = ''
            elif isinstance(v, float): r[c] = round(v, 1)
            elif isinstance(v, np.integer): r[c] = int(v)
            else: r[c] = str(v)
        records.append(r)
    pc = '预测出品时间_分钟'
    return jsonify({
        'task_id': task_id, 'total_rows': len(result_df),
        'preview_rows': len(records), 'columns': cols, 'data': records,
        'download_url': f'/api/download/{task_id}',
        'summary': {'pred_mean':round(result_df[pc].mean(),1),'pred_median':round(result_df[pc].median(),1),'pred_min':round(result_df[pc].min(),1),'pred_max':round(result_df[pc].max(),1)},
        'evaluation': eval_dict,
    })

@app.route('/api/download/<task_id>')
def api_download(task_id):
    path = os.path.join(RESULT_DIR, f'{task_id}_out.csv')
    if not os.path.exists(path): return jsonify({'error':'not found'}), 404
    return send_file(path, as_attachment=True, download_name=f'result_{task_id}.csv', mimetype='text/csv')

if __name__ == '__main__':
    print('='*50)
    print('http://localhost:5000')
    print('='*50)
    app.run(host='0.0.0.0', port=5000, debug=True)
