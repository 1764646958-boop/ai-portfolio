'use strict';
const fs = require('fs');
const crypto = require('crypto');

const nowIso = () => new Date().toISOString();
const uuid = () => crypto.randomUUID();
const genKey = (bytes = 24) => crypto.randomBytes(bytes).toString('hex');

// scrypt 口令散列（格式: scrypt$N$r$p$salt$hash）
function hashPassword(pw) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(pw, salt, 64, { N: 16384, r: 8, p: 1 }).toString('hex');
  return `scrypt$16384$8$1$${salt}$${hash}`;
}
function verifyPassword(pw, stored) {
  try {
    const [alg, N, r, p, salt, hash] = stored.split('$');
    if (alg !== 'scrypt') return false;
    const calc = crypto.scryptSync(pw, salt, 64, { N: +N, r: +r, p: +p });
    return crypto.timingSafeEqual(calc, Buffer.from(hash, 'hex'));
  } catch { return false; }
}

// 原子写 JSON（tmp + rename）
function writeJsonAtomic(file, obj, mode = 0o600) {
  const tmp = `${file}.tmp-${process.pid}-${Date.now()}`;
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2), { mode });
  fs.renameSync(tmp, file);
  try { fs.chmodSync(file, mode); } catch { }
}
function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
}

// 文件锁（M4 防竞态）：O_EXCL 创建锁文件， stale 60s 自动回收
function acquireLock(lockPath, { staleMs = 60000, retries = 50, waitMs = 100 } = {}) {
  for (let i = 0; ; i++) {
    try {
      const fd = fs.openSync(lockPath, 'wx', 0o600);
      fs.writeSync(fd, JSON.stringify({ pid: process.pid, at: Date.now() }));
      fs.closeSync(fd);
      return () => { try { fs.unlinkSync(lockPath); } catch { } };
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      try {
        const st = fs.statSync(lockPath);
        if (Date.now() - st.mtimeMs > staleMs) { fs.unlinkSync(lockPath); continue; }
      } catch { continue; }
      if (i >= retries) throw new Error('获取文件锁超时: ' + lockPath);
      const until = Date.now() + waitMs;
      while (Date.now() < until) { } // 短自旋（低频管理操作）
    }
  }
}

const sanitizeName = (name, fallback = 'file') => {
  const s = String(name || '').replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').replace(/^\.+/, '').trim();
  return s || fallback;
};
const sanitizeCategory = (cat) => sanitizeName(cat, '资料库').slice(0, 64);

const isValidProfileId = (id) => /^[a-z][a-z0-9]{1,31}$/.test(id || '');

module.exports = { nowIso, uuid, genKey, hashPassword, verifyPassword, writeJsonAtomic, readJson, acquireLock, sanitizeName, sanitizeCategory, isValidProfileId };
