'use strict';
// CloudLoom 代理层入口：8787 = API + MCP 网关；3000 = 前端静态（Caddy 反代约定，Session0 §9.1）
const express = require('express');
const cookieParser = require('cookie-parser');
const fs = require('fs');
const path = require('path');
const C = require('./config');
const lazy = require('./lazystart');

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '2mb' }));
app.use(cookieParser());

app.get('/api/health', (req, res) => res.json({ ok: true, service: 'team-console', time: new Date().toISOString() }));

app.use('/api', require('./auth').router);
app.use('/api', require('./chat').router);
app.use('/api', require('./kanban').router);
app.use('/api', require('./files').router);
app.use('/api', require('./conversations').router);
app.use('/api', require('./agents').router);
app.use('/api', require('./poll').router);
// 阶段 3 画像 Tab（M3）：只读 GET /api/profiles，后端按请求者过滤（见 profiles.js 头部合规说明）
if (fs.existsSync(path.join(__dirname, 'profiles.js'))) app.use('/api', require('./profiles').router);
// 阶段 2 模块（tasks / memories）挂载点：tasks.js / memories.js 就绪后在此 use
if (fs.existsSync(path.join(__dirname, 'tasks.js'))) app.use('/api', require('./tasks').router);
if (fs.existsSync(path.join(__dirname, 'memories.js'))) app.use('/api', require('./memories').router);
// 任务执行器由服务进程独占启动：单纯 require tasks.js 不会启动执行器或改动任务状态（D23 队列单飞）
// 启动自愈：boot 恢复上一进程遗留的 running（30s 宽限）+ 60s 周期巡检；仍由服务进程独占，require 本身无副作用

// C-1 修复（S3.1）：恢复/巡检不再于 listen 之前执行；改为 API 绑定成功后的回调内触发一次。
// 第二实例绑定必然失败（EADDRINUSE），其 listening 回调不执行 —— 因此不再出现
// 「启动瞬间把上一进程仍在 running 的任务误判为孤儿并重排」的跨实例双写。
const tasksMod = fs.existsSync(path.join(__dirname, 'tasks.js')) ? require('./tasks') : null;
function startTaskRuntime() {
  if (!tasksMod) return;
  tasksMod.recoverStale({ boot: true });
  tasksMod.startSweeper();
  startLazyRuntime();
}

app.use('/mcp', require('./mcp').router);

app.use('/api', (req, res) => res.status(404).json({ error: '接口不存在' }));
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error('[server]', err);
  if (res.headersSent) return;
  res.status(err.status || 500).json({ error: err.message || '服务器内部错误' });
});


app.listen(C.PORT, C.HOST, (err) => {
  // C-1 修复（S3.1，第二版）：express 5 的 app.listen 会把回调同时注册为 error 监听
  // （express/lib/application.js: server.once('error', done)），端口被占用时回调照样被调用、入参是错误对象。
  // 因此必须在回调内判断 err，否则第二实例仍会执行恢复/巡检（实测 EADDRINUSE 下回调被触发）。
  if (err) {
    console.error(`[team-console] API 监听失败（${err.code ? err.code : err.message}）：本进程不启动任务恢复/巡检`);
    return;
  }
  console.log(`[team-console] API 监听 http://${C.HOST}:${C.PORT}（含 /mcp）`);
  startTaskRuntime(); // C-1：确认本进程真正持有 API 端口后再恢复/巡检
});

// 前端静态（3000）：SPA fallback 到 index.html；dist 不存在时返回占位提示
const staticApp = express();
staticApp.disable('x-powered-by');
if (fs.existsSync(C.STATIC_DIR)) {
  staticApp.use(express.static(C.STATIC_DIR));
  // S4.0 / B6-①：SPA 回退收窄。原实现对**所有**未命中路径一律回 index.html（200 + text/html），
  // 两个后果：① 缺失的静态资源（如 /assets/x.js）返回 HTML，浏览器按 JS 解析后报
  // "Unexpected token '<'"，把"文件缺失"伪装成"代码报错"，极难定位；
  // ② 直接访问 3000 端口的 /api/xxx 也返回首页 HTML，掩盖后端路由错误。
  // 现规则：/api 前缀 → 404 JSON；带扩展名（视为静态资源）→ 404 纯文本；其余（前端路由）→ index.html。
  staticApp.use((req, res) => {
    if (req.method !== 'GET' && req.method !== 'HEAD') return res.status(404).type('txt').send('404 Not Found');
    if (req.path === '/api' || req.path.startsWith('/api/')) return res.status(404).json({ error: '接口不存在' });
    if (path.extname(req.path)) return res.status(404).type('txt').send('404 Not Found');
    res.sendFile(path.join(C.STATIC_DIR, 'index.html'));
  });
} else {
  staticApp.use((req, res) => res.status(503).send('前端尚未构建（team-console/dist 缺失）'));
}
staticApp.listen(C.STATIC_PORT, C.HOST, (err) => {
  // C-1 修复（S3.1，第二版）：与本进程 API 监听同样区分成功/失败，避免日志谎报就绪
  if (err) {
    console.error(`[team-console] 前端静态监听失败（${err.code ? err.code : err.message}）`);
    return;
  }
  console.log(`[team-console] 前端静态监听 http://${C.HOST}:${C.STATIC_PORT}`);
});

// 懒启动：实例表初始化 + 每 5 分钟空闲清扫
// C-1 修复（S3.1，第二版）：实例表初始化与空闲清扫也只在确认持有 API 端口后启动，
// 避免第二实例同样写入共享实例表、执行停服清扫（实测第二实例会走到这一行）。
function startLazyRuntime() {
  lazy.initTable().then(() => setInterval(lazy.sweep, C.SWEEP_INTERVAL_MS));
}
