'use strict';
// 4.9 团队共享记忆库（D24/D25）· data/team-memory.db + FTS5(trigram) · ACL(private|team|restricted)
// 同时提供 4.10 的沉淀入口 precipitateTaskMemory() 与 4.11 MCP 的 searchMemories/insertMemory
const express = require('express');
const fs = require('fs');
const { DatabaseSync } = require('node:sqlite');
const C = require('./config');
const { authRequired } = require('./auth');
const { nowIso, uuid } = require('./util');

const router = express.Router();

fs.mkdirSync(C.DATA_DIR, { recursive: true });

const db = new DatabaseSync(C.MEMORY_DB);
db.exec(`
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,                      -- decision | preference | fact | conclusion
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  tags TEXT,                               -- 逗号分隔
  author TEXT NOT NULL,                    -- username
  visibility TEXT NOT NULL DEFAULT 'team', -- private | team | restricted
  allow_members TEXT,                      -- JSON 数组（restricted 时用，存 username）
  source_task_id TEXT,
  source_agent TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mem_author ON memories(author);
CREATE INDEX IF NOT EXISTS idx_mem_vis ON memories(visibility);
CREATE INDEX IF NOT EXISTS idx_mem_src ON memories(source_task_id);
`);

// FTS5 虚拟表（D24：中文用 trigram）。⚠️ trigram 只能索引 ≥3 字符的片段，
// 因此 1-2 字的中文查询（如「数值」）在 FTS 上必然 0 命中 —— 由 searchMemories 的 LIKE 兜底覆盖。
let FTS_TOKENIZER = 'trigram';
try {
  db.exec(`CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(memory_id UNINDEXED, title, content, tags, tokenize='trigram')`);
} catch (e) {
  FTS_TOKENIZER = 'unicode61';
  console.error('[memories] trigram 不可用，降级 unicode61:', e.message);
  db.exec(`CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(memory_id UNINDEXED, title, content, tags, tokenize='unicode61')`);
}
// 兼容已存在的旧表：若曾经建过不同 tokenizer 的表则沿用（不重建，避免丢索引）

const ftsInsert = (m) => db.prepare('INSERT INTO memory_fts (memory_id, title, content, tags) VALUES (?,?,?,?)')
  .run(m.id, m.title || '', m.content || '', m.tags || '');
const ftsDelete = (id) => db.prepare('DELETE FROM memory_fts WHERE memory_id = ?').run(id);
const ftsQuote = (s) => '"' + String(s).replace(/"/g, '""') + '"'; // 短语化，避免 MATCH 语法错误

// FTS 索引补偿：内存表为空但 memories 有数据（如首次升级）时重建
try {
  const ftsN = db.prepare('SELECT COUNT(*) AS n FROM memory_fts').get().n;
  const memN = db.prepare('SELECT COUNT(*) AS n FROM memories').get().n;
  if (ftsN < memN) {
    db.exec('DELETE FROM memory_fts');
    for (const m of db.prepare('SELECT * FROM memories').all()) ftsInsert(m);
    console.log(`[memories] FTS 索引重建: ${memN} 条`);
  }
} catch (e) { console.error('[memories] FTS 索引检查失败:', e.message); }

const TYPES = ['decision', 'preference', 'fact', 'conclusion'];
const VISIBILITIES = ['private', 'team', 'restricted'];

// allow_members 归一化为 username（前端可能传 user id）
function normalizeAllowMembers(list) {
  const conv = new DatabaseSync(C.CONVERSATIONS_DB, { readOnly: true });
  const out = [];
  try {
    for (const raw of Array.isArray(list) ? list : []) {
      const s = String(raw || '').trim();
      if (!s) continue;
      const u = conv.prepare('SELECT username FROM users WHERE id = ? OR username = ?').get(s, s);
      const name = u ? u.username : s;
      if (!out.includes(name)) out.push(name);
    }
  } catch { /* 用户库不可读时按原样保留 */ }
  finally { conv.close(); }
  return out;
}

// D25 ACL：可见 = author=我 或 visibility=team 或（restricted 且我在 allow_members）
function canSee(user, m) {
  if (m.author === user.username) return true;
  if (m.visibility === 'team') return true;
  if (m.visibility === 'restricted') {
    try { return (JSON.parse(m.allow_members || '[]')).includes(user.username); } catch { return false; }
  }
  return false; // private 且非作者
}
const canEdit = (user, m) => m.author === user.username || user.role === 'admin';

const parseTags = (t) => {
  if (Array.isArray(t)) return t.map(x => String(x).trim()).filter(Boolean).join(',');
  return String(t || '').split(/[,，]/).map(s => s.trim()).filter(Boolean).join(',');
};

const publicMemory = (m) => ({
  id: m.id, type: m.type, title: m.title, content: m.content,
  tags: m.tags ? m.tags.split(',').filter(Boolean) : [],
  author: m.author, visibility: m.visibility,
  allow_members: (() => { try { return JSON.parse(m.allow_members || '[]'); } catch { return []; } })(),
  source_task_id: m.source_task_id, source_agent: m.source_agent, created_at: m.created_at,
});

const byCreatedDesc = (a, b) => (a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0);

// ---- 写入（供 POST /api/memories 与 4.10 沉淀 / MCP memory_add 复用）----
function insertMemory(input, user) {
  const type = String(input?.type || '').trim();
  if (!TYPES.includes(type)) throw new Error(`type 须为 ${TYPES.join('|')}`);
  const title = String(input?.title || '').trim();
  const content = String(input?.content || '').trim();
  if (!title) throw new Error('title 必填');
  if (!content) throw new Error('content 必填');
  let visibility = String(input?.visibility || 'team').trim();
  if (!VISIBILITIES.includes(visibility)) visibility = 'team';
  const allow = visibility === 'restricted' ? normalizeAllowMembers(input?.allow_members) : [];
  if (visibility === 'restricted' && !allow.length) throw new Error('restricted 可见性需至少指定 1 位 allow_members');
  const m = {
    id: uuid(), type, title: title.slice(0, 200), content,
    tags: parseTags(input?.tags), author: user.username, visibility,
    allow_members: JSON.stringify(allow),
    source_task_id: input?.source_task_id || null,
    source_agent: input?.source_agent || null,
    created_at: nowIso(),
  };
  db.prepare('INSERT INTO memories (id,type,title,content,tags,author,visibility,allow_members,source_task_id,source_agent,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)')
    .run(m.id, m.type, m.title, m.content, m.tags, m.author, m.visibility, m.allow_members, m.source_task_id, m.source_agent, m.created_at);
  ftsInsert(m);
  return publicMemory(m);
}

// ---- 检索（ACL 过滤 + trigram FTS 排序 + LIKE 兜底）----
function searchMemories(q, user, { type, visibility, limit = 20 } = {}) {
  const lim = Math.max(1, Math.min(+limit || 20, 200));
  let rows = db.prepare('SELECT * FROM memories').all().filter(m => canSee(user, m));
  if (type) rows = rows.filter(m => m.type === type);
  if (visibility) rows = rows.filter(m => m.visibility === visibility);

  const needle = String(q || '').trim();
  if (!needle) return rows.sort(byCreatedDesc).slice(0, lim).map(publicMemory);

  let ranked = [];
  if ([...needle].length >= 3) {
    try {
      const ids = db.prepare('SELECT memory_id FROM memory_fts WHERE memory_fts MATCH ? ORDER BY bm25(memory_fts) LIMIT ?')
        .all(ftsQuote(needle), lim * 2).map(r => r.memory_id);
      const order = new Map(ids.map((id, i) => [id, i]));
      ranked = rows.filter(m => order.has(m.id)).sort((a, b) => order.get(a.id) - order.get(b.id));
    } catch (e) { console.error('[memories] FTS 查询失败，回落 LIKE:', e.message); }
  }
  // LIKE 兜底：① 1-2 字查询 trigram 必然 0 命中；② FTS 结果不足时补齐
  const hit = new Set(ranked.map(m => m.id));
  const lower = needle.toLowerCase();
  const like = rows.filter(m => !hit.has(m.id) && (
    (m.title || '').toLowerCase().includes(lower) ||
    (m.content || '').toLowerCase().includes(lower) ||
    (m.tags || '').toLowerCase().includes(lower)
  )).sort(byCreatedDesc);
  return [...ranked, ...like].slice(0, lim).map(publicMemory);
}

// ---- 4.10 融合闭环：任务完成后自动沉淀 conclusion 记忆 ----
// 失败任务不沉淀（SPEC 4.10）；已沉淀过则幂等跳过
function precipitateTaskMemory(task, { agentName, correctionSummary, visibility = 'team', allowMembers = [], outputFiles } = {}) {
  const existing = db.prepare('SELECT id FROM memories WHERE source_task_id = ?').get(task.id);
  if (existing) return { skipped: true, id: existing.id };
  const outDir = `${C.OUTPUT_DIR}/${task.id}`;
  const lines = [
    `【任务】${task.title}`,
    task.description ? `【描述】${task.description}` : null,
    `【执行 Agent】${agentName || task.agent_id}`,
    `【结论】${String(task.result_summary || task.description || '').slice(0, 800)}`,
    `【产物路径】${outDir}/`,
  ].filter(Boolean);
  if (correctionSummary) lines.push(`【审批修正】${correctionSummary}`);
  const tags = [task.title, agentName || task.agent_id];
  // outputs 表在 tasks.db，本模块的 db 指向 team-memory.db —— 跨库查询必然失败，
  // 故由调用方（tasks.js）把产物文件名传进来；未传时跳过（不静默依赖错误查询）。
  const names = Array.isArray(outputFiles) ? outputFiles : [];
  for (const name of names) {
    const ext = String(name).split('.').pop();
    if (ext && ext !== name && !tags.includes(ext)) tags.push(ext);
  }
  const mem = insertMemory({
    type: 'conclusion',
    title: `任务结论：${task.title}`.slice(0, 200),
    content: lines.join('\n'),
    tags,
    visibility,
    allow_members: allowMembers,
    source_task_id: task.id,
    source_agent: task.agent_id,
  }, { username: task.created_by || 'system' });
  return { skipped: false, memory: mem };
}

module.exports = {
  router, insertMemory, searchMemories, precipitateTaskMemory,
  publicMemory, canSee, canEdit, FTS_TOKENIZER, db,
};

// ================= HTTP API（SPEC 4.9）=================
router.post('/memories', authRequired, (req, res) => {
  try { res.json({ ok: true, memory: insertMemory(req.body || {}, req.user) }); }
  catch (e) { res.status(400).json({ error: e.message }); }
});

// ⚠️ /memories/suggest 必须注册在 /memories/:id 之前，否则会被 :id 捕获
router.get('/memories/suggest', authRequired, (req, res) => {
  res.json({ ok: true, memories: searchMemories(req.query.q || '', req.user, { limit: 10 }) });
});

router.get('/memories', authRequired, (req, res) => {
  const { q, type, visibility, limit } = req.query;
  res.json({ ok: true, memories: searchMemories(q, req.user, { type, visibility, limit }) });
});

router.get('/memories/:id', authRequired, (req, res) => {
  const m = db.prepare('SELECT * FROM memories WHERE id = ?').get(req.params.id);
  if (!m) return res.status(404).json({ error: '记忆不存在' });
  if (!canSee(req.user, m)) return res.status(403).json({ error: '无权访问该记忆（D25 ACL）' });
  res.json({ ok: true, memory: publicMemory(m) });
});

router.put('/memories/:id', authRequired, (req, res) => {
  const m = db.prepare('SELECT * FROM memories WHERE id = ?').get(req.params.id);
  if (!m) return res.status(404).json({ error: '记忆不存在' });
  if (!canEdit(req.user, m)) return res.status(403).json({ error: '仅作者或管理员可修改' });
  const { type, title, content, tags, visibility, allow_members } = req.body || {};
  const next = {
    type: TYPES.includes(type) ? type : m.type,
    title: title !== undefined ? String(title).trim().slice(0, 200) : m.title,
    content: content !== undefined ? String(content) : m.content,
    tags: tags !== undefined ? parseTags(tags) : m.tags,
    visibility: VISIBILITIES.includes(visibility) ? visibility : m.visibility,
  };
  if (!next.title) return res.status(400).json({ error: 'title 不能为空' });
  let allow = '[]';
  if (next.visibility === 'restricted') {
    const src = allow_members !== undefined ? allow_members : JSON.parse(m.allow_members || '[]');
    allow = JSON.stringify(normalizeAllowMembers(src));
    if (JSON.parse(allow).length === 0) return res.status(400).json({ error: 'restricted 可见性需至少指定 1 位 allow_members' });
  }
  db.prepare('UPDATE memories SET type=?, title=?, content=?, tags=?, visibility=?, allow_members=? WHERE id=?')
    .run(next.type, next.title, next.content, next.tags, next.visibility, allow, m.id);
  ftsDelete(m.id);
  ftsInsert(db.prepare('SELECT * FROM memories WHERE id = ?').get(m.id));
  res.json({ ok: true, memory: publicMemory(db.prepare('SELECT * FROM memories WHERE id = ?').get(m.id)) });
});

router.delete('/memories/:id', authRequired, (req, res) => {
  const m = db.prepare('SELECT * FROM memories WHERE id = ?').get(req.params.id);
  if (!m) return res.status(404).json({ error: '记忆不存在' });
  if (!canEdit(req.user, m)) return res.status(403).json({ error: '仅作者或管理员可删除' });
  ftsDelete(m.id);
  db.prepare('DELETE FROM memories WHERE id = ?').run(m.id);
  res.json({ ok: true, deleted: m.id });
});
