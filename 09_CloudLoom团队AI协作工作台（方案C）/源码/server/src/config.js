'use strict';
// CloudLoom 代理层配置（SPEC v3.2 · 4.x）
const fs = require('fs');
const path = require('path');

const BASE = '/opt/team-console';
const SERVER_DIR = path.join(BASE, 'server');

// .env 极简解析（密钥只进 .env，全局铁律 4）
function loadEnv(file) {
  try {
    for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
      if (!m) continue;
      let v = m[2];
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
      if (!(m[1] in process.env)) process.env[m[1]] = v;
    }
  } catch { /* .env 缺失时依赖进程环境 */ }
}
loadEnv(path.join(SERVER_DIR, '.env'));

module.exports = {
  BASE,
  SERVER_DIR,
  DATA_DIR: path.join(BASE, 'data'),
  AGENTS_JSON: path.join(BASE, 'agents.json'),
  REGISTRY_LOCK: path.join(BASE, 'data', '.registry.lock'),
  CONVERSATIONS_DB: path.join(BASE, 'data', 'conversations.db'),
  TASKS_DB: path.join(BASE, 'data', 'tasks.db'),
  MEMORY_DB: path.join(BASE, 'data', 'team-memory.db'),
  FILES_JSON: path.join(BASE, 'data', 'files.json'),
  TEAM_FILES: '/root/team-files',
  NOTIFY_DIR: '/root/team-files/系统通知',
  OUTPUT_DIR: '/root/team-files/产出',
  KANBAN_DB: process.env.HERMES_KANBAN_BOARD || '/root/.hermes/kanban.db',
  HERMES_BIN: '/usr/local/bin/hermes',
  PROFILES_DIR: '/root/.hermes/profiles',
  PORT: 8787,
  STATIC_PORT: 3000, // Caddy 已将非 /api 流量反代至此（Session0 约定）
  STATIC_DIR: path.join(BASE, 'team-console', 'dist'),
  HOST: '127.0.0.1',
  JWT_SECRET: process.env.JWT_SECRET || '',
  COOKIE_NAME: 'tc_token',
  COOKIE_MAX_AGE: 7 * 24 * 3600 * 1000,
  // 懒启动（4.2）
  PROBE_TIMEOUT_MS: 1500,
  START_TIMEOUT_MS: 60000,
  IDLE_STOP_MS: +process.env.IDLE_STOP_MS || 30 * 60 * 1000,
  SWEEP_INTERVAL_MS: +process.env.SWEEP_INTERVAL_MS || 5 * 60 * 1000,
  CUSTOM_PORT_MIN: 8650,
  CUSTOM_PORT_MAX: 8999,
  UPLOAD_MAX_BYTES: 10 * 1024 * 1024, // D14
  RECALL_WINDOW_MS: 5 * 60 * 1000,    // D18
  // ── C2（S4.1）用量计费常量 ────────────────────────────────────────────────
  // 单价单位：美元 / 百万 tokens。与 Hermes 自身的计费表同源（agent/usage_pricing.py 的
  // official_docs_snapshot —— DeepSeek 官方价目 2026-07 快照；deepseek-chat / deepseek-reasoner
  // 自 2026-07-24 起别名 deepseek-v4-flash 的非思考/思考模式，费率相同），便于与 Hermes 侧对账。
  // 价目变动时只改这一处（或用同名环境变量覆盖），周报/快照的估算随之更新。
  PRICE_IN_PER_M: +process.env.PRICE_IN_PER_M || 0.14,
  PRICE_OUT_PER_M: +process.env.PRICE_OUT_PER_M || 0.28,
  PRICE_CACHE_READ_PER_M: +process.env.PRICE_CACHE_READ_PER_M || 0.0028,
  USD_CNY: +process.env.USD_CNY || 7.2,       // 展示用固定汇率（非实时行情，仅用于把估算美元折成人民币）
  // 上游未回 usage 时的字符转 token 经验系数（兜底路径用；中日韩表意字与拉丁字符分开计）
  USAGE_EST_CHARS_PER_TOKEN_CJK: +process.env.USAGE_EST_CHARS_PER_TOKEN_CJK || 1.5,
  USAGE_EST_CHARS_PER_TOKEN_ASCII: +process.env.USAGE_EST_CHARS_PER_TOKEN_ASCII || 4,
  // ── C3（S4.1）上下文窗口策略 ──────────────────────────────────────────────
  // 默认保留最近 12 轮（一轮≈user+assistant）；设为 0 或负数 = 关闭裁剪（仅供实测对照）。
  CHAT_HISTORY_MAX_ROUNDS: +process.env.CHAT_HISTORY_MAX_ROUNDS || 12,
  // 可选：被裁掉的早期部分改由本 Agent 生成一次摘要并缓存复用（默认关；开启后每次摘要本身也要花 token）
  CHAT_SUMMARY_ENABLED: process.env.CHAT_SUMMARY_ENABLED === '1',
};

if (!module.exports.JWT_SECRET) {
  console.error('[config] JWT_SECRET 未配置（server/.env），服务拒绝启动');
  process.exit(1);
}
