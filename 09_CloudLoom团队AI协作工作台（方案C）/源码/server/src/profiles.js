'use strict';
// 5.x 画像 Tab 数据面（M3 / D20 / D21）
// 依据：SPEC.md:562「画像 Tab（M3）：成员卡片，读 cron 画像 JSON，后端按请求者过滤（普通成员只见自己，管理员全见）」
//       SPEC.md:649「画像 Tab：普通成员只见自己，管理员全见（M3）」
// 过滤必须在后端完成——若把全量 JSON 下发给前端再由前端裁剪，等于数据已出边界，不满足 ACL 要求。
// 合规说明：本文件是 SPEC 阶段功能**明文要求**、但 §三「接口边界」未逐条列出的只读补充，
//           仅新增 GET /api/profiles；不改动、不复用、不覆盖任何既有路由与既有文件。
// 安全取向：fail-closed —— 解析失败或无法判定条目归属时，该内容只对管理员可见。
const express = require('express');
const fs = require('fs');
const path = require('path');
const C = require('./config');
const { authRequired } = require('./auth');

const router = express.Router();
const PROFILE_DIR = path.join(C.NOTIFY_DIR, '画像');
// 「条目归属」判定键：仅人类成员身份键。画像 JSON 里 agent 维度的条目不对普通成员开放（fail-closed）。
const ID_KEYS = ['username', 'user', 'member', 'name', 'display_name', '成员', '成员账号', '账号', '姓名'];

function idTokens(entry) {
  const out = [];
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return out;
  for (const k of Object.keys(entry)) {
    if (!ID_KEYS.includes(k) && !ID_KEYS.includes(String(k).toLowerCase())) continue;
    if (typeof entry[k] === 'string') out.push(entry[k]);
  }
  return out;
}

// 严格相等或包含（画像可能写「成员：张三（zhang）」这类组合串）；无身份键 → 不归属任何人
// 词边界判定：id 两侧若是字母/数字/._- 则属于更长标识符，不算本人（zhang 不命中 zhangwei，li 不命中 lily）
function hasId(t, id) {
  const isWord = (c) => c !== "" && /[0-9A-Za-z_.-]/.test(c)
  let i = t.indexOf(id)
  while (i !== -1) {
    const before = i > 0 ? t[i - 1] : ""
    const after = i + id.length < t.length ? t[i + id.length] : ""
    if (!isWord(before) && !isWord(after)) return true
    i = t.indexOf(id, i + 1)
  }
  return false
}
function belongsTo(entry, user) {
  const ids = [user.username, user.display_name].filter(Boolean).map(String);
  if (!ids.length) return false;
  return idTokens(entry).some((t) => ids.some((id) => hasId(t, id)));
}

// 拆出「可独立判定归属」的条目列表：顶层数组，或顶层对象里的数组字段
function entryLists(obj) {
  const lists = [];
  if (Array.isArray(obj)) { lists.push({ key: null, entries: obj }); return lists; }
  if (!obj || typeof obj !== 'object') return lists;
  for (const k of Object.keys(obj)) if (Array.isArray(obj[k])) lists.push({ key: k, entries: obj[k] });
  return lists;
}

router.get('/profiles', authRequired, (req, res) => {
  const isAdmin = req.user.role === 'admin';
  let names = [];
  try { names = fs.readdirSync(PROFILE_DIR).filter((n) => /\.json$/i.test(n) && !n.startsWith('.')); }
  catch { /* 目录不存在 → 空列表（前端显示引导文案） */ }
  const files = [];
  // S4.1 / C6-2②：按**修改时间**倒序（而非文件名字典序）—— 作业补跑/改名后字典序会把旧文件排到最前，
  // 前端与 API 需要的是「最新那一份」，故以 mtime 为准；mtime 相同再退回名字倒序，保证顺序稳定可复现。
  const withStat = [];
  for (const name of names) {
    const fp = path.join(PROFILE_DIR, name);
    let st; try { st = fs.statSync(fp); } catch { continue; }
    withStat.push({ name, fp, st });
  }
  withStat.sort((a, b) => (b.st.mtimeMs - a.st.mtimeMs) || (a.name < b.name ? 1 : a.name > b.name ? -1 : 0));
  for (const { name, fp, st } of withStat) {
    const item = {
      file: name, mtime: Math.floor(st.mtimeMs), size: st.size,
      parse_error: null, sections: [], entries_count: 0,
    };
    let obj = null;
    try { obj = JSON.parse(fs.readFileSync(fp, 'utf8')); } catch (e) { item.parse_error = e.message; }
    if (obj !== null) {
      if (isAdmin) {
        item.scope = 'all';
        item.data = obj;                                        // 管理员：全量原文（前端可折叠查看）
        item.sections = entryLists(obj).map((l) => ({ key: l.key, entries: l.entries }));
        item.entries_count = item.sections.reduce((n, s) => n + s.entries.length, 0);
      } else {
        item.scope = 'self';                                    // 普通成员：仅本人条目
        item.sections = entryLists(obj)
          .map((l) => ({ key: l.key, entries: l.entries.filter((e) => belongsTo(e, req.user)) }))
          .filter((l) => l.entries.length);
        item.entries_count = item.sections.reduce((n, s) => n + s.entries.length, 0);
      }
    } else if (isAdmin) {
      item.scope = 'all';
    }
    files.push(item);
  }
  res.json({
    ok: true,
    restricted: !isAdmin,
    note: isAdmin ? null : '普通成员仅可见本人的画像条目（M3）；完整画像请联系管理员。',
    files,
  });
});

module.exports = { router, PROFILE_DIR, belongsTo };
