'use strict';
// 4.1/4.7 GET /api/poll：读 ~/team-files/系统通知/ 目录，按 mtime 增量（N2/D19，前端 3-5s 轮询）
const express = require('express');
const fs = require('fs');
const path = require('path');
const C = require('./config');
const { authRequired } = require('./auth');

const router = express.Router();

router.get('/poll', authRequired, (req, res) => {
  const since = parseInt(req.query.since || '0', 10) || 0; // ms 时间戳
  const out = [];
  let entries = [];
  try { entries = fs.readdirSync(C.NOTIFY_DIR, { withFileTypes: true }); } catch { }
  for (const ent of entries) {
    if (!ent.isFile()) continue; // 画像/ 子目录由画像 Tab 单独读，不进通知流
    const fp = path.join(C.NOTIFY_DIR, ent.name);
    let st; try { st = fs.statSync(fp); } catch { continue; }
    const mtime = Math.floor(st.mtimeMs);
    if (since && mtime <= since) continue;
    let preview = '';
    if (/\.(md|txt|json)$/i.test(ent.name) && st.size <= 512 * 1024) {
      try { preview = fs.readFileSync(fp, 'utf8').slice(0, 300); } catch { }
    }
    out.push({ name: ent.name, mtime, size: st.size, preview });
  }
  out.sort((a, b) => b.mtime - a.mtime);
  res.json({ ok: true, now: Date.now(), files: out });
});

module.exports = { router };
