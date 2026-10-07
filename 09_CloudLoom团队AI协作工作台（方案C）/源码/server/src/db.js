'use strict';
// SQLite（node:sqlite 内置）· conversations.db（4.6 三表 + users 认证表）
const { DatabaseSync } = require('node:sqlite');
const fs = require('fs');
const C = require('./config');

fs.mkdirSync(C.DATA_DIR, { recursive: true });

const db = new DatabaseSync(C.CONVERSATIONS_DB);
db.exec(`
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  pass_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',        -- admin | member
  status TEXT NOT NULL DEFAULT 'pending',     -- pending | active | disabled
  avatar TEXT,
  notify_enabled INTEGER NOT NULL DEFAULT 1,
  -- S4.1 / C6-5：登出吊销计数（登出时 +1，使该用户所有旧 JWT 立即失效）
  token_version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,                          -- dm | group
  title TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversation_members (
  conversation_id TEXT NOT NULL,
  member_id TEXT NOT NULL,
  last_read_seq INTEGER NOT NULL DEFAULT 0,
  joined_at TEXT NOT NULL,
  PRIMARY KEY (conversation_id, member_id)
);
CREATE TABLE IF NOT EXISTS messages (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT UNIQUE NOT NULL,
  conversation_id TEXT NOT NULL,
  sender_id TEXT NOT NULL,                     -- 用户 id 或 agent profile id
  sender_type TEXT NOT NULL DEFAULT 'member',  -- member | agent
  content TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'text',           -- text | file | link
  created_at TEXT NOT NULL,
  recalled_at TEXT,
  meta TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, seq);
-- S4.1 / C2：用量记账表（新表；不改动既有表结构，写入见 usage.js）
-- est_cost     = 人民币元（负责人视角的主字段）
-- est_cost_usd = 美元（单价基准货币，便于与 Hermes/上游账单对账）
-- estimated    = 1 表示上游未回 usage、按字符数估算（流式兜底）；0 表示上游真实 usage
CREATE TABLE IF NOT EXISTS usage_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor TEXT,
  agent_id TEXT,
  source TEXT,
  model TEXT,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0,
  est_cost_usd REAL NOT NULL DEFAULT 0,
  est_cost REAL NOT NULL DEFAULT 0,
  estimated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage_log(ts);
CREATE INDEX IF NOT EXISTS idx_usage_agent_ts ON usage_log(agent_id, ts);
CREATE INDEX IF NOT EXISTS idx_usage_actor_ts ON usage_log(actor, ts);
-- S4.1 / C3：长会话上下文摘要缓存（仅当 CHAT_SUMMARY_ENABLED=1 时使用）
-- dropped_count = 该摘要覆盖的「被省略消息条数」；当前需要省略的条数不超过它时可直接复用，避免反复花 token 摘要
CREATE TABLE IF NOT EXISTS context_summaries (
  conversation_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  dropped_count INTEGER NOT NULL DEFAULT 0,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (conversation_id, agent_id)
);
`);

// S4.1 / C6-5：老库补列（CREATE TABLE IF NOT EXISTS 不会改既有表结构，故用幂等 ALTER）
try {
  const ucols = db.prepare('PRAGMA table_info(users)').all().map((c) => c.name);
  if (!ucols.includes('token_version')) {
    db.exec('ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1');
    console.log('[db] 迁移：users 增加 token_version（默认 1）');
  }
} catch (e) { console.error('[db] users.token_version 迁移失败（不影响启动）：' + e.message); }

module.exports = { db };
