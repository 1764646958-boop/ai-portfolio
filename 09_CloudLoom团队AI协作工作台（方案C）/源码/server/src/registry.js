'use strict';
// Agent 注册表：agents.json 读写（4.4）· 端口预分配（8650+，文件锁 M4）
const fs = require('fs');
const C = require('./config');
const { nowIso, genKey, acquireLock, writeJsonAtomic } = require('./util');

// 4 个预设 Agent（Session 0 已部署）的显示名与职责（D22）
const PRESET_META = {
  cehua: { name: '策划Agent', description: '世界观、剧情、数值' },
  chengxu: { name: '程序Agent', description: '架构设计、代码实现、技术评审' },
  pingshen: { name: '评审Agent', description: '独立只读审查（只评判不动手）' },
  zhiban: { name: '值班Agent', description: '晨报、周复盘、阻塞提醒、催办、D36 复核兜底' },
};

function normalize(id, raw) {
  const meta = PRESET_META[id] || {};
  return {
    port: raw.port,
    api_server_key: raw.api_server_key,
    name: raw.name || meta.name || id,
    description: raw.description || meta.description || '',
    preset: raw.preset !== undefined ? raw.preset : id in PRESET_META,
    enabled: raw.enabled !== undefined ? raw.enabled : true,
    created_at: raw.created_at || null,
    // S4.0 / B4：可选头像透传。原字段白名单会丢弃 avatar，使前端永远只能回退占位图（真实 URL 无法覆盖）。
    avatar: raw.avatar || null,
  };
}

// 读注册表（每次读盘，保证与管理员工具/其他进程一致）
function readRegistry() {
  let raw;
  try { raw = JSON.parse(fs.readFileSync(C.AGENTS_JSON, 'utf8')); }
  catch (e) { throw new Error('agents.json 读取失败: ' + e.message); }
  const out = {};
  for (const [id, v] of Object.entries(raw)) out[id] = normalize(id, v);
  return out;
}

// 带锁整体改写（atomic + 600）。mutate(registry) 返回 truthy 才落盘。
function updateRegistry(mutate) {
  const release = acquireLock(C.REGISTRY_LOCK);
  try {
    let raw = {};
    try { raw = JSON.parse(fs.readFileSync(C.AGENTS_JSON, 'utf8')); } catch { }
    const reg = {};
    for (const [id, v] of Object.entries(raw)) reg[id] = normalize(id, v);
    const result = mutate(reg);
    if (result !== false) writeJsonAtomic(C.AGENTS_JSON, reg, 0o600);
    return result;
  } finally { release(); }
}


// C-2 修复（S3.1）：候选端口除 agents.json 查重外，再做真实占用探测 ——
// 读 /proc/net/tcp{,6} 中处于 LISTEN(0A) 的本地端口，跳过被未登记进程占用的候选，
// 避免把已占用端口分配给新 Agent 导致首次唤醒必失败（等价于临时 bind 探测的只读实现）。
function listeningPorts() {
  const set = new Set();
  for (const f of ['/proc/net/tcp', '/proc/net/tcp6']) {
    let txt = '';
    try { txt = fs.readFileSync(f, 'utf8'); } catch { continue; }
    for (const line of txt.split('\n').slice(1)) {
      const cols = line.trim().split('\t').join(' ').split(/ +/).filter(Boolean);
      if (cols.length < 4 || cols[3] !== '0A') continue;
      const hex = (cols[1] || '').split(':')[1];
      if (hex) set.add(parseInt(hex, 16));
    }
  }
  return set;
}
function allocatePort(reg) {
  const used = new Set(Object.values(reg).map(a => a.port));
  const listening = listeningPorts();
  for (let p = C.CUSTOM_PORT_MIN; p <= C.CUSTOM_PORT_MAX; p++) {
    if (used.has(p) || listening.has(p)) continue; // 已登记 或 已被占用 → 跳过
    return p;
  }
  throw new Error('端口池耗尽（8650-8999）或全部候选端口均已被占用');
}

module.exports = { readRegistry, updateRegistry, allocatePort, PRESET_META, nowIso, genKey };
