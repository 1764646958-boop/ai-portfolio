'use strict';
// 4.3 认证与成员（D2/D7）：register(首个即管理员)/login/me/members/approve · JWT httpOnly cookie
const express = require('express');
const jwt = require('jsonwebtoken');
const C = require('./config');
const { db } = require('./db');
const { nowIso, uuid, hashPassword, verifyPassword } = require('./util');

const router = express.Router();

function signToken(user) {
  // S4.1 / C6-5：令牌内带 token_version(tv)。登出会把库中该值 +1，从而让旧令牌立即失效。
  return jwt.sign({ uid: user.id, username: user.username, role: user.role, tv: Number(user.token_version ?? 1) }, C.JWT_SECRET, { expiresIn: '7d' });
}
function setCookie(res, token) {
  // S4.0 / B3：补 Secure（SPEC:290 要求 httpOnly cookie；C-10 缺口）。注意：Secure 下浏览器仅在 HTTPS 携带本 Cookie，
  // 因此工作台必须以 HTTPS（Caddy 443）访问；直连 http://IP:3000 或 http://127.0.0.1:8787 只能用于本机诊断（curl），不作为用户入口。
  res.cookie(C.COOKIE_NAME, token, { httpOnly: true, sameSite: 'lax', secure: true, maxAge: C.COOKIE_MAX_AGE, path: '/' });
}
function publicUser(u) {
  return { id: u.id, username: u.username, display_name: u.display_name, role: u.role, status: u.status, avatar: u.avatar, notify_enabled: !!u.notify_enabled, created_at: u.created_at };
}

// Bearer 或 Cookie 取 JWT（Bearer 供 MCP/外部客户端复用，D28）
function extractToken(req) {
  const h = req.headers.authorization || '';
  if (h.startsWith('Bearer ')) return h.slice(7);
  return req.cookies?.[C.COOKIE_NAME] || null;
}
function authRequired(req, res, next) {
  const token = extractToken(req);
  if (!token) return res.status(401).json({ error: '未登录' });
  try {
    const payload = jwt.verify(token, C.JWT_SECRET);
    const u = db.prepare('SELECT * FROM users WHERE id = ?').get(payload.uid);
    if (!u) return res.status(401).json({ error: '账号不存在' });
    // S4.1 / C4-2：被停用/待批准的会话按「登录态失效」返回 401（原为 403；403 保留给「权限不足」语义）
    if (u.status !== 'active') return res.status(401).json({ error: '账号待批准或已停用' });
    // S4.1 / C6-5：登出吊销——令牌版本与库中不一致即失效；老令牌缺 tv 字段按 1 处理（与库默认值一致）
    if (Number(payload.tv ?? 1) !== Number(u.token_version ?? 1)) return res.status(401).json({ error: '登录态已失效（已登出）' });
    req.user = u;
    next();
  } catch { return res.status(401).json({ error: '登录态无效或已过期' }); }
}
function adminRequired(req, res, next) {
  if (req.user?.role !== 'admin') return res.status(403).json({ error: '仅管理员可操作' });
  next();
}

router.post('/register', (req, res) => {
  const { username, password, display_name } = req.body || {};
  if (!username || !password) return res.status(400).json({ error: 'username 与 password 必填' });
  if (!/^[a-zA-Z0-9_.-]{2,32}$/.test(username)) return res.status(400).json({ error: '用户名需为 2-32 位字母数字._-' });
  if (String(password).length < 6) return res.status(400).json({ error: '密码至少 6 位' });
  const exists = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
  if (exists) return res.status(409).json({ error: '用户名已被注册' });
  const count = db.prepare('SELECT COUNT(*) AS n FROM users').get().n;
  const isFirst = count === 0;
  const u = {
    id: uuid(), username, display_name: (display_name || username).slice(0, 32),
    pass_hash: hashPassword(password),
    role: isFirst ? 'admin' : 'member',
    status: isFirst ? 'active' : 'pending', // D7：首个即管理员，之后需批准
    avatar: null, notify_enabled: 1, created_at: nowIso(),
  };
  db.prepare('INSERT INTO users (id,username,display_name,pass_hash,role,status,avatar,created_at) VALUES (?,?,?,?,?,?,?,?)')
    .run(u.id, u.username, u.display_name, u.pass_hash, u.role, u.status, u.avatar, u.created_at);
  if (isFirst) {
    setCookie(res, signToken(u));
    return res.json({ ok: true, user: publicUser(u), message: '首个账号，已成为管理员' });
  }
  res.json({ ok: true, pending: true, message: '注册成功，待管理员批准后可登录' });
});

router.post('/login', (req, res) => {
  const { username, password } = req.body || {};
  const u = db.prepare('SELECT * FROM users WHERE username = ?').get(username || '');
  if (!u || !verifyPassword(password || '', u.pass_hash)) return res.status(401).json({ error: '用户名或密码错误' });
  if (u.status === 'pending') return res.status(403).json({ error: '账号待管理员批准' });
  if (u.status !== 'active') return res.status(403).json({ error: '账号已停用' });
  setCookie(res, signToken(u));
  // S4.0 / B3：响应体只返回用户信息，不再回传 token（前端本就只用 Cookie；原 token 字段使 JWT 变成 JS 可读，见《前端开发者说明》风险 B2）
  res.json({ ok: true, user: publicUser(u) });
});

router.get('/me', authRequired, (req, res) => res.json({ user: publicUser(req.user) }));

// 设置 Tab（SPEC.md:571「设置 Tab：个人信息、通知开关、退出登录」）：通知开关需持久化到 users.notify_enabled
// 合规说明：SPEC 阶段功能明文要求、§三「接口边界」未逐条列出 → 加法式新增 PUT /api/me，不改动既有路由
router.put('/me', authRequired, (req, res) => {
  const { notify_enabled, display_name } = req.body || {};
  const fields = [], args = [];
  if (notify_enabled !== undefined) { fields.push('notify_enabled = ?'); args.push(notify_enabled ? 1 : 0); }
  if (display_name !== undefined) {
    const d = String(display_name).trim().slice(0, 32);
    if (!d) return res.status(400).json({ error: 'display_name 不能为空' });
    fields.push('display_name = ?'); args.push(d);
  }
  if (!fields.length) return res.status(400).json({ error: '无可更新字段（notify_enabled / display_name）' });
  args.push(req.user.id);
  db.prepare(`UPDATE users SET ${fields.join(', ')} WHERE id = ?`).run(...args);
  res.json({ ok: true, user: publicUser(db.prepare('SELECT * FROM users WHERE id = ?').get(req.user.id)) });
});

// S4.0 / B3：清除 Cookie 时属性与下发时一致（sameSite/secure/path），否则部分浏览器不会真正清除
// S4.1 / C6-5：登出不仅清本地 Cookie，还把该用户 token_version +1 —— 服务端吊销，旧 Cookie 立即 401
router.post('/logout', (req, res) => {
  try {
    const token = extractToken(req);
    if (token) {
      const payload = jwt.verify(token, C.JWT_SECRET);
      db.prepare('UPDATE users SET token_version = COALESCE(token_version, 1) + 1 WHERE id = ?').run(payload.uid);
    }
  } catch { /* 令牌缺失/无效也照常清 Cookie，保持登出幂等 */ }
  res.clearCookie(C.COOKIE_NAME, { path: '/', httpOnly: true, sameSite: 'lax', secure: true });
  res.json({ ok: true });
});

router.get('/members', authRequired, (req, res) => {
  const rows = db.prepare('SELECT * FROM users ORDER BY created_at ASC').all();
  res.json({ members: rows.map(publicUser) });
});

router.post('/members/:id/approve', authRequired, adminRequired, (req, res) => {
  const u = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
  if (!u) return res.status(404).json({ error: '成员不存在' });
  db.prepare("UPDATE users SET status = 'active' WHERE id = ?").run(u.id);
  res.json({ ok: true, user: publicUser({ ...u, status: 'active' }) });
});

// 成员停用/启用（管理员）——账号体系可扩展（D2）所需的最小管理面
router.post('/members/:id/disable', authRequired, adminRequired, (req, res) => {
  const u = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
  if (!u) return res.status(404).json({ error: '成员不存在' });
  if (u.id === req.user.id) return res.status(400).json({ error: '不能停用自己' });
  db.prepare("UPDATE users SET status = 'disabled' WHERE id = ?").run(u.id);
  res.json({ ok: true });
});

module.exports = { router, authRequired, adminRequired, publicUser };
