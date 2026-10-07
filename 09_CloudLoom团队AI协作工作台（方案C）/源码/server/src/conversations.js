'use strict';
// 4.6 团队会话（D9/D18）：conversations.db · 私聊/群聊 · 增量拉取 · @Agent 拉入（N4=方案A system 注入）· 5 分钟撤回
const express = require('express');
const C = require('./config');
const { db } = require('./db');
const { authRequired } = require('./auth');
const { readRegistry } = require('./registry');
const { callAgent } = require('./chat');
const { nowIso, uuid } = require('./util');

const router = express.Router();

const isMember = (convId, uid) => !!db.prepare('SELECT 1 FROM conversation_members WHERE conversation_id = ? AND member_id = ?').get(convId, uid);
const memberNames = () => {
  const m = {};
  for (const u of db.prepare('SELECT id, username, display_name FROM users').all()) m[u.id] = u.display_name || u.username;
  return m;
};

function maskMessage(row, names) {
  const recalled = !!row.recalled_at;
  return {
    seq: row.seq, id: row.id, conversation_id: row.conversation_id,
    sender_id: row.sender_id, sender_type: row.sender_type,
    sender_name: row.sender_type === 'agent' ? (readRegistry()[row.sender_id]?.name || row.sender_id) : (names[row.sender_id] || row.sender_id),
    content: recalled ? '' : row.content,
    type: recalled ? 'text' : row.type,
    created_at: row.created_at, recalled_at: row.recalled_at, recalled,
    meta: row.meta ? JSON.parse(row.meta) : null,
  };
}

// 会话列表（含未读数）
router.get('/conversations', authRequired, (req, res) => {
  const convs = db.prepare(`
    SELECT c.* FROM conversations c
    JOIN conversation_members cm ON cm.conversation_id = c.id
    WHERE cm.member_id = ? ORDER BY c.updated_at DESC`).all(req.user.id);
  const names = memberNames();
  const unreadStmt = db.prepare('SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ? AND seq > ? AND sender_id != ?');
  const lastStmt = db.prepare('SELECT * FROM messages WHERE conversation_id = ? ORDER BY seq DESC LIMIT 1');
  const membersStmt = db.prepare('SELECT member_id FROM conversation_members WHERE conversation_id = ?');
  res.json({
    ok: true,
    conversations: convs.map(c => {
      const last = lastStmt.get(c.id);
      const mySeq = db.prepare('SELECT last_read_seq FROM conversation_members WHERE conversation_id = ? AND member_id = ?').get(c.id, req.user.id).last_read_seq;
      return {
        id: c.id, type: c.type, title: c.title, created_by: c.created_by, created_at: c.created_at, updated_at: c.updated_at,
        members: membersStmt.all(c.id).map(m => ({ id: m.member_id, name: names[m.member_id] || m.member_id })),
        unread: unreadStmt.get(c.id, mySeq, req.user.id).n,
        last_message: last ? maskMessage(last, names) : null,
        last_read_seq: mySeq,
      };
    }),
  });
});

// 建会话（dm 去重）
router.post('/conversations', authRequired, (req, res) => {
  const { type, member_ids, title } = req.body || {};
  if (!['dm', 'group'].includes(type)) return res.status(400).json({ error: 'type 须为 dm|group' });
  const ids = [...new Set([req.user.id, ...(Array.isArray(member_ids) ? member_ids : [])])];
  if (type === 'dm' && ids.length !== 2) return res.status(400).json({ error: '私聊需且仅需 2 人' });
  if (type === 'group' && ids.length < 2) return res.status(400).json({ error: '群聊至少 2 人' });
  for (const id of ids) {
    const u = db.prepare("SELECT id FROM users WHERE id = ? AND status = 'active'").get(id);
    if (!u) return res.status(400).json({ error: `成员 ${id} 不存在或未激活` });
  }
  if (type === 'dm') {
    const mine = db.prepare(`
      SELECT c.id FROM conversations c
      JOIN conversation_members a ON a.conversation_id = c.id AND a.member_id = ?
      JOIN conversation_members b ON b.conversation_id = c.id AND b.member_id = ?
      WHERE c.type = 'dm'`).get(ids[0], ids[1]);
    if (mine) return res.json({ ok: true, conversation_id: mine.id, existed: true });
  }
  const id = uuid(), now = nowIso();
  const names = memberNames();
  const autoTitle = title || (type === 'dm' ? ids.map(i => names[i]).join(' ↔ ') : `群聊（${ids.length}人）`);
  db.prepare('INSERT INTO conversations (id,type,title,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?)').run(id, type, autoTitle, req.user.id, now, now);
  for (const mid of ids) db.prepare('INSERT INTO conversation_members (conversation_id,member_id,last_read_seq,joined_at) VALUES (?,?,0,?)').run(id, mid, now);
  res.json({ ok: true, conversation_id: id });
});

// 增量拉取（since=已见最大 seq；缺省返回最近 50 条）
router.get('/conversations/:id/messages', authRequired, (req, res) => {
  if (!isMember(req.params.id, req.user.id)) return res.status(403).json({ error: '不在该会话中' });
  const since = parseInt(req.query.since || '0', 10) || 0;
  const limit = Math.min(parseInt(req.query.limit || '50', 10) || 50, 200);
  let rows;
  if (since > 0) {
    rows = db.prepare('SELECT * FROM messages WHERE conversation_id = ? AND seq > ? ORDER BY seq ASC LIMIT ?').all(req.params.id, since, limit);
  } else {
    rows = db.prepare('SELECT * FROM (SELECT * FROM messages WHERE conversation_id = ? ORDER BY seq DESC LIMIT ?) ORDER BY seq ASC').all(req.params.id, limit);
  }
  const names = memberNames();
  const maxSeq = rows.length ? rows[rows.length - 1].seq : since;
  res.json({ ok: true, messages: rows.map(r => maskMessage(r, names)), max_seq: maxSeq });
});

// 已读上报（未读红点清零）
router.post('/conversations/:id/read', authRequired, (req, res) => {
  if (!isMember(req.params.id, req.user.id)) return res.status(403).json({ error: '不在该会话中' });
  // 上界钳制：seq 不得超过该会话最大 seq，否则（前端异常或脏数据）会让该会话未读永久为 0
  const maxSeq = db.prepare('SELECT COALESCE(MAX(seq), 0) AS n FROM messages WHERE conversation_id = ?').get(req.params.id).n;
  const seq = Math.min(Math.max(parseInt(req.body?.seq, 10) || 0, 0), maxSeq);
  db.prepare('UPDATE conversation_members SET last_read_seq = MAX(last_read_seq, ?) WHERE conversation_id = ? AND member_id = ?').run(seq, req.params.id, req.user.id);
  res.json({ ok: true });
});

// 发消息（成员-成员不调 LLM）；@Agent → 异步拉入（答完即走）
router.post('/conversations/:id/messages', authRequired, (req, res) => {
  const convId = req.params.id;
  if (!isMember(convId, req.user.id)) return res.status(403).json({ error: '不在该会话中' });
  const { content, type } = req.body || {};
  if (!content || !String(content).trim()) return res.status(400).json({ error: 'content 必填' });
  const msgType = ['text', 'file', 'link'].includes(type) ? type : 'text';
  const id = uuid(), now = nowIso();
  db.prepare('INSERT INTO messages (id,conversation_id,sender_id,sender_type,content,type,created_at,recalled_at,meta) VALUES (?,?,?,?,?,?,?,NULL,NULL)')
    .run(id, convId, req.user.id, 'member', String(content), msgType, now);
  db.prepare('UPDATE conversations SET updated_at = ? WHERE id = ?').run(now, convId);
  const seq = db.prepare('SELECT seq FROM messages WHERE id = ?').get(id).seq;
  db.prepare('UPDATE conversation_members SET last_read_seq = ? WHERE conversation_id = ? AND member_id = ?').run(seq, convId, req.user.id);

  // @Agent 解析：匹配 profile id 或显示名（如 @cehua / @策划Agent）
  const reg = readRegistry();
  const mentioned = new Set();
  for (const m of String(content).matchAll(/@([^\s@，。,.\uff1a:]+)/g)) {
    const token = m[1];
    for (const [pid, a] of Object.entries(reg)) {
      if ((token === pid || token === a.name || token === a.name.replace(/Agent$/, '')) && a.enabled !== false) mentioned.add(pid);
    }
  }
  for (const pid of mentioned) triggerAgent(convId, pid, req.user, String(content)).catch(e => console.error(`[@Agent ${pid}]`, e.message));

  const names = memberNames();
  res.json({ ok: true, message: maskMessage(db.prepare('SELECT * FROM messages WHERE id = ?').get(id), names), mentioned_agents: [...mentioned] });
});

// @Agent 拉入：只收最近 20 条 / 24h 片段，回复一次即离开（D9 · N4=方案A system 注入）
async function triggerAgent(convId, agentId, fromUser, question) {
  const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const slice = db.prepare('SELECT * FROM messages WHERE conversation_id = ? AND created_at >= ? ORDER BY seq DESC LIMIT 20').all(convId, since).reverse();
  const names = memberNames();
  const reg = readRegistry();
  const agentName = reg[agentId]?.name || agentId;
  const fragment = slice.map(r => `[${r.sender_type === 'agent' ? (reg[r.sender_id]?.name || r.sender_id) : (names[r.sender_id] || r.sender_id)}] ${r.recalled_at ? '（已撤回）' : r.content}`).join('\n');
  const system = [
    `【上下文提示】你（${agentName}）被团队成员在会话中 @ 拉入做一次临时咨询。`,
    '以下是该会话最近 24h 内最多 20 条的片段，仅供你参考，不代表你的设定，也不要泄露给其他无关场景：',
    fragment,
    '规则：只回答当前问题；答完即走，不要承诺持续跟进；如需完整上下文，提示对方显式「共享完整会话」。',
  ].join('\n');
  const user = `【当前问题】${fromUser.display_name || fromUser.username}: ${question}`;
  // S4.1 / C2：@Agent 拉入会真的调用一次 Agent，费用记在发起 @ 的成员名下
  const out = await callAgent(agentId, [{ role: 'system', content: system }, { role: 'user', content: user }], { actor: fromUser.id, source: 'mention' });
  const now = nowIso();
  db.prepare('INSERT INTO messages (id,conversation_id,sender_id,sender_type,content,type,created_at,recalled_at,meta) VALUES (?,?,?,?,?,?,?,NULL,?)')
    .run(uuid(), convId, agentId, 'agent', out.content, 'text', now, JSON.stringify({ via: 'mention', reply_to: fromUser.username }));
  db.prepare('UPDATE conversations SET updated_at = ? WHERE id = ?').run(now, convId);
}

// 5 分钟撤回（D18，仅发送者本人）
router.post('/messages/:id/recall', authRequired, (req, res) => {
  const m = db.prepare('SELECT * FROM messages WHERE id = ?').get(req.params.id);
  if (!m) return res.status(404).json({ error: '消息不存在' });
  if (m.sender_id !== req.user.id || m.sender_type !== 'member') return res.status(403).json({ error: '仅发送者本人可撤回' });
  if (m.recalled_at) return res.status(400).json({ error: '已撤回过' });
  if (Date.now() - new Date(m.created_at).getTime() > C.RECALL_WINDOW_MS) return res.status(400).json({ error: '超过 5 分钟，无法撤回（D18）' });
  db.prepare('UPDATE messages SET recalled_at = ? WHERE id = ?').run(nowIso(), m.id);
  res.json({ ok: true, recalled_at: nowIso() });
});

module.exports = { router };
