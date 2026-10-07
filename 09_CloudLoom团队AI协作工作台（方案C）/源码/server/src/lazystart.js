'use strict';
// 4.2 懒启动进程管理（C3/D5）：探活 / 拉起 / 60s 超时 / 空闲 30min 停止 / 8650+ 预分配
const { execFile } = require('child_process');
const C = require('./config');
const { readRegistry } = require('./registry');

// 实例运行表（内存）：profile -> { port, running, managed: 'systemd'|'lazy', lastActive, starting: Promise|null }
const instances = new Map();

function table() {
  const reg = readRegistry();
  for (const [id, a] of Object.entries(reg)) {
    if (!instances.has(id)) {
      instances.set(id, { port: a.port, running: false, managed: a.preset ? 'systemd' : 'lazy', lastActive: 0, starting: null });
    } else {
      instances.get(id).port = a.port;
    }
  }
  return { reg, instances };
}

async function probe(port, timeoutMs = C.PROBE_TIMEOUT_MS) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(`http://127.0.0.1:${port}/health`, { signal: ctrl.signal });
    return r.ok;
  } catch { return false; } finally { clearTimeout(t); }
}

function isRunning(id) {
  const inst = instances.get(id);
  if (!inst) return Promise.resolve(false);
  return probe(inst.port);
}

function runCmd(args, timeoutMs = 20000) {
  return new Promise((resolve, reject) => {
    execFile(C.HERMES_BIN, args, { timeout: timeoutMs, env: process.env }, (err, stdout, stderr) => {
      if (err) return reject(new Error(`hermes ${args.join(' ')} 失败: ${stderr || err.message}`));
      resolve(stdout);
    });
  });
}

// 确保实例在跑：不在跑则拉起，轮询 /health 上限 60s；失败显式报错，不静默重试
async function ensureRunning(id) {
  const { reg } = table();
  const agent = reg[id];
  if (!agent) { const e = new Error('Agent 不存在'); e.code = 'NO_AGENT'; throw e; }
  if (agent.enabled === false) { const e = new Error(`Agent「${agent.name}」已停用`); e.code = 'DISABLED'; throw e; }
  const inst = instances.get(id);
  if (await probe(inst.port)) { inst.running = true; inst.lastActive = Date.now(); return { woke: false }; }
  inst.running = false;
  if (inst.starting) return inst.starting; // 并发合并

  inst.starting = (async () => {
    await runCmd(['-p', id, 'gateway', 'start'], 30000);
    const deadline = Date.now() + C.START_TIMEOUT_MS;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 1000));
      if (await probe(inst.port)) {
        inst.running = true; inst.lastActive = Date.now();
        return { woke: true };
      }
    }
    throw new Error('Agent 启动失败，请管理员检查（60s 内 /health 未就绪）');
  })().finally(() => { inst.starting = null; });

  return inst.starting;
}

function touch(id) {
  const inst = instances.get(id);
  if (inst) inst.lastActive = Date.now();
}

// 后台任务（每 5 分钟）：自建 Agent（lazy）空闲 >30 分钟 → 停止；预设 4 个常驻（D5）
async function sweep() {
  try {
    table();
    for (const [id, inst] of instances) {
      inst.running = await probe(inst.port);
      if (!inst.running) continue;
      if (inst.managed === 'lazy' && Date.now() - inst.lastActive > C.IDLE_STOP_MS) {
        try {
          await runCmd(['-p', id, 'gateway', 'stop'], 30000);
          inst.running = false;
          console.log(`[lazystart] 空闲超 ${Math.round(C.IDLE_STOP_MS / 60000)}min，已停止: ${id}`);
        } catch (e) { console.error(`[lazystart] 停止 ${id} 失败:`, e.message); }
      }
    }
  } catch (e) { console.error('[lazystart] sweep 异常:', e.message); }
}

async function initTable() {
  table();
  for (const [id, inst] of instances) {
    inst.running = await probe(inst.port);
    if (inst.running) inst.lastActive = Date.now();
  }
  console.log('[lazystart] 实例表初始化:', [...instances.entries()].map(([k, v]) => `${k}:${v.running ? 'up' : 'down'}`).join(' '));
}

function statusOf(id) {
  const inst = instances.get(id);
  return inst ? { running: inst.running, managed: inst.managed, last_active: inst.lastActive ? new Date(inst.lastActive).toISOString() : null } : null;
}

module.exports = { ensureRunning, isRunning, touch, sweep, initTable, statusOf, probe };
