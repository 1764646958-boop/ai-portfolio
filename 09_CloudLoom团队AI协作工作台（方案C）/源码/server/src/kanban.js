'use strict';
// 4.1 GET /api/kanban（只读 SQLite，C1 共享看板） + POST /api/kanban-command（指令转聊天消息）
const express = require('express');
const { DatabaseSync } = require('node:sqlite');
const C = require('./config');
const { authRequired } = require('./auth');
const { callAgent } = require('./chat');

const router = express.Router();

// 只读查询共享看板（每次新连接保证新鲜；只读不写）
function queryKanban(status) {
  const db = new DatabaseSync(C.KANBAN_DB, { readOnly: true });
  try {
    let sql = 'SELECT id,title,body,assignee,status,priority,created_by,created_at,started_at,completed_at,block_kind,result FROM tasks';
    const args = [];
    if (status) { sql += ' WHERE status = ?'; args.push(status); }
    sql += ' ORDER BY created_at DESC';
    const tasks = db.prepare(sql).all(...args);
    const commentStmt = db.prepare('SELECT id,author,body,created_at FROM task_comments WHERE task_id = ? ORDER BY created_at ASC');
    for (const t of tasks) t.comments = commentStmt.all(t.id);
    return tasks;
  } finally { db.close(); }
}

router.get('/kanban', authRequired, (req, res) => {
  try {
    res.json({ ok: true, board: C.KANBAN_DB, tasks: queryKanban(req.query.status) });
  } catch (e) { res.status(500).json({ error: '看板读取失败: ' + e.message }); }
});

// 看板写操作走 Agent 指令（kanban_* 工具），默认值班 Agent（zhiban）
router.post('/kanban-command', authRequired, async (req, res) => {
  const { command, agent } = req.body || {};
  if (!command || typeof command !== 'string') return res.status(400).json({ error: 'command 必填' });
  const agentId = agent || 'zhiban';
  try {
    const out = await callAgent(agentId, [{ role: 'user', content: command }], { actor: req.user.id, source: 'kanban' });
    res.json({ ok: true, agent: agentId, reply: out.content });
  } catch (e) { res.status(502).json({ error: e.message }); }
});

module.exports = { router, queryKanban };
