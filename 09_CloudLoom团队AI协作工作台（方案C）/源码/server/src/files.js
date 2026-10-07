'use strict';
// 4.5 文件与资料库（D4/D14）：/api/files（≤10MB multipart）/ /api/links / 下载 / 删除（仅管理员）
const express = require('express');
const fs = require('fs');
const path = require('path');
const multer = require('multer');
const C = require('./config');
const { authRequired, adminRequired } = require('./auth');
const { nowIso, uuid, readJson, writeJsonAtomic, acquireLock, sanitizeName, sanitizeCategory } = require('./util');

const router = express.Router();

const readFiles = () => readJson(C.FILES_JSON, []);
function saveFiles(list) {
  const release = acquireLock(C.REGISTRY_LOCK + '.files');
  try { writeJsonAtomic(C.FILES_JSON, list, 0o600); } finally { release(); }
}
// 阶段3收口修复(D3-文件名)：multer(busboy) 按 latin1 解析 multipart 的 filename，
// 中文名会双重编码成「é¶æ®µ3ä¸ä¼ æµè¯.txt」（UTF-8 字节被当 latin1 再编码为 UTF-8）。
// 还原：取回原始字节 → 按 UTF-8 解码；仅当字节序列本身是合法 UTF-8（编码往返一致）才替换，
// 纯 ASCII 名与非法序列保持原样，避免误伤。修前实测：上传「阶段3上传测试.txt」落盘为乱码。
function decodeUploadName(raw) {
  const s = String(raw || '');
  try {
    const buf = Buffer.from(s, 'latin1');
    const utf8 = buf.toString('utf8');
    if (Buffer.compare(Buffer.from(utf8, 'utf8'), buf) === 0) return utf8;
  } catch { /* 保持原样 */ }
  return s;
}
const publicEntry = (e) => ({ id: e.id, kind: e.kind, name: e.name, category: e.category, url: e.url, size: e.size, mime: e.mime, uploader: e.uploader, created_at: e.created_at });

// 阶段1收口修复(D2)：改用 memoryStorage。
// 原 diskStorage.destination() 在 multipart 文本字段尚未解析时读 req.body.category，
// 若客户端把 file 字段排在 category 之前，分类会静默丢失（落为默认「资料库」）。
// memoryStorage 保证进入 handler 时 req.body 已全部解析，分类与字段顺序无关（≤10MB 可接受）。
const storage = multer.memoryStorage();
const upload = multer({ storage, limits: { fileSize: C.UPLOAD_MAX_BYTES } });

router.post('/files', authRequired, (req, res) => {
  upload.single('file')(req, res, (err) => {
    if (err) {
      const msg = err.code === 'LIMIT_FILE_SIZE' ? '文件超过 10MB 上限（大文件请走网盘链接，D14）' : err.message;
      return res.status(400).json({ error: msg });
    }
    if (!req.file) return res.status(400).json({ error: '缺少文件（multipart 字段名 file）' });
    // 此时 multipart 文本字段已全部解析（见上方 D2 修复说明）
    const cat = sanitizeCategory(req.body?.category);
    const dir = path.join(C.TEAM_FILES, cat);
    fs.mkdirSync(dir, { recursive: true });
    const origName = sanitizeName(decodeUploadName(req.file.originalname));
    const ext = path.extname(origName), base = path.basename(origName, ext);
    let candidate = origName, n = 1;
    while (fs.existsSync(path.join(dir, candidate))) candidate = base + '(' + (n++) + ')' + ext;
    const savePath = path.join(dir, candidate);
    fs.writeFileSync(savePath, req.file.buffer);
    const list = readFiles();
    const entry = {
      id: uuid(), kind: 'file', name: candidate, category: cat,
      path: savePath, url: null, size: req.file.size, mime: req.file.mimetype,
      uploader: req.user.username, uploader_id: req.user.id, created_at: nowIso(),
    };
    list.push(entry); saveFiles(list);
    res.json({ ok: true, file: publicEntry(entry) });
  });
});

router.post('/links', authRequired, (req, res) => {
  const { name, url, category } = req.body || {};
  if (!name || !url) return res.status(400).json({ error: 'name 与 url 必填' });
  if (!/^https?:\/\//i.test(url)) return res.status(400).json({ error: 'url 需为 http(s) 链接' });
  const list = readFiles();
  const entry = {
    id: uuid(), kind: 'link', name: sanitizeName(name).slice(0, 128), category: sanitizeCategory(category),
    path: null, url, size: null, mime: null, uploader: req.user.username, uploader_id: req.user.id, created_at: nowIso(),
  };
  list.push(entry); saveFiles(list);
  res.json({ ok: true, file: publicEntry(entry) });
});

router.get('/files', authRequired, (req, res) => {
  const { q, category, kind } = req.query;
  let list = readFiles();
  if (category) list = list.filter(e => e.category === category);
  if (kind) list = list.filter(e => e.kind === kind);
  if (q) { const s = String(q).toLowerCase(); list = list.filter(e => e.name.toLowerCase().includes(s)); }
  res.json({ ok: true, files: list.map(publicEntry).reverse() });
});

router.get('/files/:id/download', authRequired, (req, res) => {
  const e = readFiles().find(x => x.id === req.params.id);
  if (!e) return res.status(404).json({ error: '条目不存在' });
  if (e.kind === 'link') return res.status(400).json({ error: '链接条目请直接访问 url', url: e.url });
  if (!e.path || !fs.existsSync(e.path)) return res.status(410).json({ error: '文件已不存在于磁盘' });
  res.download(e.path, e.name);
});

router.delete('/files/:id', authRequired, adminRequired, (req, res) => {
  const list = readFiles();
  const idx = list.findIndex(x => x.id === req.params.id);
  if (idx < 0) return res.status(404).json({ error: '条目不存在' });
  const [e] = list.splice(idx, 1);
  if (e.kind === 'file' && e.path) { try { fs.unlinkSync(e.path); } catch { } }
  saveFiles(list);
  res.json({ ok: true, deleted: e.id });
});

module.exports = { router, readFiles };
