'use strict';
// 4.8 办公任务中心（D23，v3.2 扩展 D35 审批修正 / D36 不确定性升级）+ 4.10 融合闭环沉淀
const express = require('express');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { DatabaseSync } = require('node:sqlite');
const C = require('./config');
const { authRequired } = require('./auth');
const { readRegistry } = require('./registry');
const { callAgent } = require('./chat');
const { readFiles } = require('./files');
const { nowIso, uuid } = require('./util');

const router = express.Router();
fs.mkdirSync(C.DATA_DIR, { recursive: true });

const db = new DatabaseSync(C.TASKS_DB);
db.exec(`
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  ref_files TEXT,                    -- JSON 数组（files.json 条目 id）
  ref_memories TEXT,                 -- JSON 数组（memories.id）
  status TEXT NOT NULL DEFAULT 'queued',   -- queued|running|waiting_approval|done|failed
  requires_approval INTEGER NOT NULL DEFAULT 0,
  approval_status TEXT,              -- pending|approved|rejected|modified
  approved_by TEXT,
  correction_note TEXT,
  progress TEXT,
  error TEXT,
  created_by TEXT NOT NULL,          -- username
  created_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS task_corrections (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  action TEXT NOT NULL,              -- approve|reject|modify
  note TEXT NOT NULL,
  decided_by TEXT NOT NULL,          -- username
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outputs (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_size INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_creator ON tasks(created_by);
CREATE INDEX IF NOT EXISTS idx_corr_agent ON task_corrections(agent_id, created_at);
CREATE INDEX IF NOT EXISTS idx_out_task ON outputs(task_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_out_path ON outputs(file_path);
`);

// 4.8 表结构之外的 3 个附加列（4.10 需要：沉淀记忆要「任务摘要+关键决策/结论」与创建者可选可见性；
// meta 存 D36 复核轨迹）。均为新增列，不影响 SPEC 已定义的列与语义。
for (const col of ['result_summary TEXT', 'memory_visibility TEXT', 'meta TEXT', 'started_at TEXT']) {
  try { db.exec(`ALTER TABLE tasks ADD COLUMN ${col}`); } catch { /* 已存在 */ }
}

// 任务级执行超时：办公任务含工具调用/写文件，远长于会话默认 180s。可用 TASK_TIMEOUT_MS 覆盖。
const TASK_TIMEOUT_MS = parseInt(process.env.TASK_TIMEOUT_MS, 10) || 600000;

const STATUSES = ['queued', 'running', 'waiting_approval', 'done', 'failed'];
const jsonArr = (s) => { try { return JSON.parse(s || '[]'); } catch { return []; } };

// ── D36：三类敏感内容强制人审（描述 + 引用资料名 + 引用记忆标题）────────────────
const APPROVAL_RULES = [
  { kind: '金额', words: ['金额', '预算', '报价', '费用', '成本', '定价', '价格', '付款', '支付', '发票', '万元', '合同额'] },
  { kind: '对外承诺', words: ['对外', '承诺', '合同', '签约', '客户', '甲方', '乙方', '发布', '公告', '公开', '上线通知'] },
  { kind: '删除数据', words: ['删除', '清除', '销毁', '清空', '卸载', '覆盖', 'drop', 'delete', 'truncate'] },
];
// 词例外：出现这些完整词时，其中的命中词不算数（如「客户端」不应因「客户」触发对外承诺）
const WORD_EXCEPTIONS = { '客户': ['客户端'] };
function hitWord(text, w) {
  const exs = WORD_EXCEPTIONS[w] || [];
  for (let from = 0; ;) {
    const i = text.indexOf(w, from);
    if (i < 0) return false;
    if (!exs.some((e) => text.startsWith(e, i))) return true;
    from = i + 1;
  }
}
function detectSensitive(text) {
  const t = String(text || '').toLowerCase();
  const hits = [];
  for (const r of APPROVAL_RULES) {
    for (const w of r.words) {
      if (hitWord(t, w.toLowerCase()) && !hits.includes(r.kind)) hits.push(r.kind);
    }
  }
  return hits;
}
function publicTask(t, extra = {}) {
  if (!t) return null;
  return {
    id: t.id, title: t.title, description: t.description, agent_id: t.agent_id,
    ref_files: jsonArr(t.ref_files), ref_memories: jsonArr(t.ref_memories),
    status: t.status, requires_approval: !!t.requires_approval,
    approval_status: t.approval_status || null, approved_by: t.approved_by || null,
    correction_note: t.correction_note || null, progress: t.progress || null,
    error: t.error || null, result_summary: t.result_summary || null,
    memory_visibility: t.memory_visibility || 'team',
    created_by: t.created_by, created_at: t.created_at, completed_at: t.completed_at || null,
    ...extra,
  };
}
function listOutputs(taskId) {
  return db.prepare('SELECT * FROM outputs WHERE task_id = ? ORDER BY created_at ASC').all(taskId)
    .map((o) => ({ id: o.id, task_id: o.task_id, file_name: o.file_name, file_size: o.file_size, created_at: o.created_at }));
}
function listCorrections(taskId) {
  return db.prepare('SELECT * FROM task_corrections WHERE task_id = ? ORDER BY created_at ASC').all(taskId)
    .map((c) => ({ id: c.id, action: c.action, note: c.note, decided_by: c.decided_by, created_at: c.created_at }));
}
// 队列位次：同 agent 队列中排在该任务之前的 queued 数
function queueAhead(t) {
  if (t.status !== 'queued') return 0;
  const row = db.prepare('SELECT rowid AS rid FROM tasks WHERE id = ?').get(t.id);
  if (!row) return 0;
  // 「前面还有 N 人」= 该 agent 正在执行的任务 + 队列中排在我前面的任务
  const r = db.prepare("SELECT COUNT(*) AS n FROM tasks WHERE agent_id = ? AND (status = 'running' OR (status = 'queued' AND rowid < ?))")
    .get(t.agent_id, row.rid);
  return r ? r.n : 0;
}
function metaOf(t) { try { return JSON.parse(t.meta || '{}'); } catch { return {}; } }
function setMeta(t, patch) {
  const m = { ...metaOf(t), ...patch };
  db.prepare('UPDATE tasks SET meta = ? WHERE id = ?').run(JSON.stringify(m), t.id);
  return m;
}

// ── 指令组装（SPEC 4.8）：【办公任务】【引用资料】【引用记忆】【相关修正记录】【行为边界】【交付要求】
const REF_FILE_PREVIEW = 1200;
function extractBoundary(agentId) {
  try {
    const p = path.join(C.PROFILES_DIR, agentId, 'SOUL.md');
    if (!fs.existsSync(p)) return '';
    const txt = fs.readFileSync(p, 'utf8');
    const i = txt.indexOf('【行为边界】');
    if (i < 0) return '';
    const rest = txt.slice(i);
    const j = rest.indexOf('\n## ', 1);
    return (j > 0 ? rest.slice(0, j) : rest).trim();
  } catch { return ''; }
}
function buildRefFiles(ids) {
  const all = readFiles();
  const picked = [];
  for (const id of ids) {
    const e = all.find((x) => x.id === id);
    if (!e) continue;
    const line = [`- ${e.name}（${e.category}）`];
    if (e.path && fs.existsSync(e.path) && fs.statSync(e.path).isFile() && fs.statSync(e.path).size < 200000) {
      try { line.push('  摘要：' + fs.readFileSync(e.path, 'utf8').slice(0, REF_FILE_PREVIEW).replace(/\s+/g, ' ')); }
      catch { /* 二进制等读不出则只给路径 */ }
    }
    if (e.url) line.push(`  链接：${e.url}`);
    if (e.path) line.push(`  路径：${e.path}`);
    picked.push(line.join('\n'));
  }
  return picked;
}
function buildRefMemories(ids) {
  const { db: mdb } = require('./memories');
  const out = [];
  for (const id of ids) {
    const m = mdb.prepare('SELECT * FROM memories WHERE id = ?').get(id);
    if (!m) continue;
    out.push(`- 【${m.type}】${m.title}\n  ${String(m.content).replace(/\s+/g, ' ').slice(0, 1500)}`);
  }
  return out;
}
// D35：同 agent 近 30 天最近的审批修正记录（最多 5 条）
function buildCorrections(agentId) {
  const since = new Date(Date.now() - 30 * 86400000).toISOString();
  return db.prepare("SELECT * FROM task_corrections WHERE agent_id = ? AND created_at > ? ORDER BY created_at DESC LIMIT 5")
    .all(agentId, since).reverse();
}
function buildInstruction(task) {
  const parts = [];
  parts.push(`【办公任务】${task.title}\n${task.description}`);
  const rf = buildRefFiles(jsonArr(task.ref_files));
  parts.push('【引用资料】\n' + (rf.length ? rf.join('\n') : '（无）'));
  const rm = buildRefMemories(jsonArr(task.ref_memories));
  parts.push('【引用记忆】\n' + (rm.length ? rm.join('\n') : '（无）'));
  const cs = buildCorrections(task.agent_id);
  parts.push('【相关修正记录】\n' + (cs.length
    ? cs.map((c) => `- [${c.action}] ${c.note}（${c.decided_by}，${c.created_at.slice(0, 10)}）`).join('\n')
    : '（无）'));
  const bd = extractBoundary(task.agent_id);
  if (bd) parts.push(bd);
  if (metaOf(task).retry) {
    const pre = metaOf(task).pre_retry_files || [];
    parts.push([
      '【重试约束】本任务是系统重启后的重试，执行可能与中断前重复。',
      `1. 产物目录中中断前已有的文件：${pre.length ? pre.join('、') : '（无）'}`,
      '2. **严禁覆盖或删除上述任何文件**。',
      '3. 若你要写的目标文件名与上述文件同名，请另存为 `<原名>-retry-<HHMMSS>`'
        + '（HHMMSS 取当前时间，例：报告.md → 报告-retry-181230.md），并在回复中说明产物文件名。',
    ].join('\n'
));
  }
  parts.push([
    '【交付要求】',
    `1. 产物写入目录：${path.join(C.OUTPUT_DIR, task.id)}/（请在回复中说明产物文件名）`,
    '2. 回复末尾必须给出结论摘要（3-5 行）',
    '3. 若因能力、资料或权限不足确实无法完成，请说明原因',
    '4. 若无法高置信完成，请说明存疑之处',
    '5. 回复的最后一行必须是交付状态标记，三选一，格式严格如下（不要加引号、不要改写原文）：',
    '   【交付状态】完成',
    '   【交付状态】无法完成：<一句原因>',
    '   【交付状态】低置信：<一句存疑说明>',
  ].join('\n'));
  return parts.join('\n\n');
}

// ── 产物扫描：读出 ~/team-files/产出/<task_id>/ 下的文件并登记 ──────────────
const MANIFEST_NAME = 'MANIFEST.json';

// S4.1 / C6-8：B5-①「不覆盖」的字节级兜底——产物目录同步落 MANIFEST.json（文件名 + sha256 + 大小 + mtime）。
// 用途：回滚/比对时按 manifest 校验「这个文件是否就是当时那一份」；按负责人决策不做全量字节快照（体积不可控）。
function writeManifest(task, dir) {
  const files = [];
  const walk = (d) => {
    let ents = [];
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const ent of ents) {
      const fp = path.join(d, ent.name);
      if (ent.isDirectory()) { walk(fp); continue; }
      if (ent.name === MANIFEST_NAME) continue;   // S4.1/C6-8：清单本身不是产物
      if (ent.name === MANIFEST_NAME) continue;
      let st, buf;
      try { st = fs.statSync(fp); buf = fs.readFileSync(fp); } catch { continue; }
      files.push({
        file: path.relative(dir, fp).split(path.sep).join('/'),
        size: st.size,
        sha256: crypto.createHash('sha256').update(buf).digest('hex'),
        mtime: new Date(st.mtimeMs).toISOString(),
      });
    }
  };
  walk(dir);
  const doc = { task_id: task.id, generated_at: nowIso(), algorithm: 'sha256', files };
  const tmp = path.join(dir, MANIFEST_NAME + '.tmp');
  fs.writeFileSync(tmp, JSON.stringify(doc, null, 2), 'utf8');
  fs.renameSync(tmp, path.join(dir, MANIFEST_NAME));
  return files.length;
}

function scanOutputs(task) {
  const dir = path.join(C.OUTPUT_DIR, task.id);
  if (!fs.existsSync(dir)) return 0;
  let n = 0;
  const walk = (d) => {
    let ents = [];
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const ent of ents) {
      const fp = path.join(d, ent.name);
      if (ent.isDirectory()) { walk(fp); continue; }
      let st; try { st = fs.statSync(fp); } catch { continue; }
      if (db.prepare('SELECT id FROM outputs WHERE file_path = ?').get(fp)) continue;
      db.prepare('INSERT INTO outputs (id, task_id, file_path, file_name, file_size, created_at) VALUES (?,?,?,?,?,?)')
        .run(uuid(), task.id, fp, ent.name, st.size, nowIso());
      n++;
    }
  };
  walk(dir);
  try { writeManifest(task, dir); } catch (e) { console.error('[tasks] MANIFEST 写入失败（不影响产物登记）：' + e.message); }
  return n;
}

// ── D36 回复分类 ─────────────────────────────────────────────────────────
const RE_NEGATED = /不写|不说|不会说|不会|不用|不标注|不做|不提|避免|并非|不是|不属于|而非|不能称/;   // 否定语境 → 该命中视为无效
// 首选解析 【交付状态】标记（取最后一次出现：Agent 可能引用原文或自我否定，
// 例如「我不写『无法完成』」，纯关键词匹配会被这类句子误导）
const RE_STATUS = /【交付状态】\s*(完成|无法完成|低置信)\s*[：:]?\s*([^\n]*)/g;

function classifyReply(reply) {
  const text = String(reply || '');
  let m; let last = null;
  const re = new RegExp(RE_STATUS.source, 'g');
  while ((m = re.exec(text)) !== null) last = m;
  if (last) return { verdict: last[1], note: String(last[2] || '').trim().slice(0, 300), source: 'marker' };
  const hit = (re2) => {
    const mm = re2.exec(text);
    if (!mm) return false;
    const ctx = text.slice(Math.max(0, mm.index - 26), mm.index + 2);   // +2：RE_UNABLE 会消耗前置字符（[^如若]），窗口需覆盖它
    return !RE_NEGATED.test(ctx);
  };
  if (hit(RE_UNABLE)) return { verdict: '无法完成', note: '', source: 'heuristic' };
  if (hit(RE_LOWCONF)) return { verdict: '低置信', note: '', source: 'heuristic' };
  return { verdict: '完成', note: '', source: 'heuristic' };
}
const RE_UNABLE = /(?:^|[^如若])无法完成|做不到|不能完成|无法交付|不具备[^\n]{0,8}能力|超出[^\n]{0,8}能力/;
const RE_LOWCONF = /无法高置信完成|低置信|不能高置信|不确定是否|存在存疑|无法确认/;

async function zhibanReview(task, reply) {
  const prompt = [
    '你是值班复核 Agent（zhiban）。同事 Agent 对自己交付的任务给出了不确定声明，请判断该任务是否已可交付。',
    `【任务标题】${task.title}`,
    `【任务描述】${task.description}`,
    `【同事回复】${String(reply).slice(0, 2000)}`,
    '只输出一行 JSON，不要其他文字：{"verdict":"pass","reason":"一句理由"}（verdict 只能是 pass 或 reject）',
  ].join('\n\n');
  try {
    const r = await callAgent('zhiban', [{ role: 'user', content: prompt }], { timeoutMs: 120000, actor: task.created_by || null, source: 'zhiban-review' });
    const m = String(r.content || '').match(/\{[\s\S]*?\}/);
    if (!m) return { verdict: 'unknown', reason: '复核回复无法解析' };
    const j = JSON.parse(m[0]);
    if (j.verdict === 'reject') return { verdict: 'reject', reason: String(j.reason || '值班复核未通过').slice(0, 300) };
    if (j.verdict === 'pass') return { verdict: 'pass', reason: String(j.reason || '').slice(0, 300) };
    return { verdict: 'unknown', reason: '复核结论非 pass/reject' };
  } catch (e) {
    return { verdict: 'unknown', reason: '复核调用失败：' + e.message };
  }
}

// ── 4.10 融合闭环：完成 → 沉淀记忆 ────────────────────────────────────────
function precipitate(task, { correctionSummary } = {}) {
  try {
    const { precipitateTaskMemory } = require('./memories');
    const m = metaOf(task);
    let visibility = task.memory_visibility === 'private' || task.memory_visibility === 'restricted' ? task.memory_visibility : 'team';
    const allowMembers = Array.isArray(m.memory_allow_members) ? m.memory_allow_members : [];
    let note = null;
    if (visibility === 'restricted' && !allowMembers.length) { visibility = 'private'; note = 'restricted 未指定成员，已按 private 沉淀'; }
    const outputFiles = db.prepare('SELECT file_name FROM outputs WHERE task_id = ?').all(task.id).map((o) => o.file_name);
    const r = precipitateTaskMemory(task, { agentName: task.agent_id, correctionSummary, visibility, allowMembers, outputFiles });
    if (r && r.skipped) return { skipped: true, memory_id: r.id };
    const memoryId = r && r.memory ? r.memory.id : null;
    setMeta(task, note ? { memory_id: memoryId, memory_note: note } : { memory_id: memoryId });
    return { skipped: false, memory_id: memoryId };
  } catch (e) {
    setMeta(task, { memory_error: e.message });
    return { error: e.message };
  }
}

// ── 执行引擎：每 Agent 单飞 + 队列（同 agent 同时只跑 1 个任务）──────────────
const running = new Set();   // agent_id 正在执行

function finishFailed(task, err, metaPatch, summary) {
  const r = db.prepare("UPDATE tasks SET status='failed', error=?, progress=?, result_summary=?, completed_at=? WHERE id=? AND status='running'")
    .run(String(err).slice(0, 1000), '执行失败', summary ? String(summary).slice(0, 4000) : null, nowIso(), task.id);
  if (!r.changes) { console.log(`[tasks] 任务 ${task.id} 已被取消/状态变更，失败结果不改写`); return; }
  if (metaPatch) setMeta(task, metaPatch);
  console.log(`[tasks] 失败 ${task.id} (${task.agent_id}): ${String(err).slice(0, 160)}`);
}

function finishSuccess(task, reply, nOut, metaPatch) {
  const need = !!task.requires_approval;
  const status = need ? 'waiting_approval' : 'done';
  const r = db.prepare("UPDATE tasks SET status=?, approval_status=?, progress=?, result_summary=?, completed_at=? WHERE id=? AND status='running'")
    .run(status, need ? 'pending' : null, `完成，登记产物 ${nOut} 个`, String(reply).slice(0, 4000),
      need ? null : nowIso(), task.id);
  if (!r.changes) { console.log(`[tasks] 任务 ${task.id} 已被取消/状态变更，完成结果不改写（不沉淀）`); return; }
  if (metaPatch) setMeta(task, metaPatch);
  if (need) { console.log(`[tasks] 待审批 ${task.id}`); return; }
  const row = db.prepare('SELECT * FROM tasks WHERE id = ?').get(task.id);
  const p = precipitate(row);
  console.log(`[tasks] 完成 ${task.id}，沉淀记忆 ${p.memory_id || p.error || 'skipped'}`);
}

async function execute(task) {
  // S4.0 / B5-①：重试任务在整段执行期间保持「系统重启后恢复（可能与中断前重复执行）」标注。
  // 否则该文案会被紧随其后的本行覆盖为「正在执行」，用户在任务运行期间看不到恢复事实。
  const retryRun = !!metaOf(task).retry;
  db.prepare("UPDATE tasks SET status='running', progress=?, started_at=? WHERE id=?")
    .run(retryRun ? RECOVER_PROGRESS : '正在执行', nowIso(), task.id);
  let instr;
  try { instr = buildInstruction(task); }
  catch (e) { return finishFailed(task, '指令组装失败：' + e.message); }
  console.log(`[tasks] 执行 ${task.id} → ${task.agent_id}（指令 ${instr.length} 字）`);
  let out;
  // S4.1 / C2：任务执行同样入账（actor = 建单人，便于按成员统计花费）
  try { out = await callAgent(task.agent_id, [{ role: 'user', content: instr }], { timeoutMs: TASK_TIMEOUT_MS, actor: task.created_by || null, source: 'task' }); }
  catch (e) {
    const aborted = e.name === 'AbortError' || /aborted|timeout/i.test(e.message || '');
    const secs = Math.round(TASK_TIMEOUT_MS / 1000);
    return finishFailed(task, aborted
      ? `Agent 执行超时（超过 ${secs} 秒未返回），已中止；建议拆分任务或稍后重试`
      : `执行失败：${e.message}`);
  }
  const reply = String(out.content || '').trim();
  if (!reply) return finishFailed(task, '执行失败：Agent 返回空回复');
  const nOut = scanOutputs(task);

  const cls = classifyReply(reply);
  const meta = { delivery_status: cls };
  // D36-① 明确「无法完成」+ 原因 → 失败兜底
  if (cls.verdict === '无法完成') {
    return finishFailed(task, `Agent 声明无法完成：${cls.note || '（未给原因）'}`, meta, reply);
  }
  // D36-② 低置信 → 值班 Agent 复核后再交付
  if (cls.verdict === '低置信') {
    const rev = await zhibanReview(task, reply);
    meta.zhiban_review = rev;
    if (rev.verdict === 'reject') return finishFailed(task, `值班复核未通过：${rev.reason}`, meta, reply);
    if (rev.verdict === 'unknown') {
      // 复核不可用时保守处理：强制转人工审批，不自动交付
      const t2 = { ...task, requires_approval: 1 };
      db.prepare('UPDATE tasks SET requires_approval = 1 WHERE id = ?').run(task.id);
      meta.force_approval_reason = `低置信且复核不可用：${rev.reason}`;
      return finishSuccess(t2, reply, nOut, meta);
    }
  }
  finishSuccess(task, reply, nOut, meta);
}

function pump(agentId) {
  if (running.has(agentId)) return;
  const next = db.prepare("SELECT * FROM tasks WHERE agent_id = ? AND status = 'queued' ORDER BY created_at ASC, rowid ASC LIMIT 1").get(agentId);
  if (!next) return;
  running.add(agentId);
  execute(next)
    .catch((e) => { try { finishFailed(next, '执行异常：' + e.message); } catch { /* ignore */ } })
    .finally(() => {
      running.delete(agentId);
      setImmediate(() => pump(agentId));
    });
}
// 进程内无排队任务时清理 running 标记（重启后状态自愈）
// 中断恢复：只回收「确实已中断」的任务（started_at 早于 任务超时+5 分钟，或历史行无 started_at），
// 不触碰正常执行中的任务。必须由服务进程显式调用——单纯 require 本模块不得改动任务状态、
// 不得启动执行器（否则诊断脚本/第二实例会把正在执行的任务抢跑，造成双执行）。
// ── S4.0 / B5-①：重启恢复的「可见 + 不覆盖」────────────────────────────────
// 语义（写入 SPEC v3.3）：保留「重启即恢复」，但恢复必须 ①可见（进度标注 + 系统通知）
// ②不覆盖：产物目录固定 ~/team-files/产出/<task_id>/，重试时若目标文件名已存在，
//   另存为 <原名>-retry-<HHMMSS>，绝不覆盖中断前的产物。
const RECOVER_PROGRESS = '系统重启后恢复（可能与中断前重复执行）';
function stampCompact(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}
// 回收单个中断任务：回 queued + 进度标注 + meta.retry 置位（并记录中断前已有产物清单）
function requeueInterrupted(r) {
  const dir = path.join(C.OUTPUT_DIR, r.id);
  let files = [];
  try { files = fs.readdirSync(dir, { withFileTypes: true }).filter((e) => e.isFile()).map((e) => e.name); } catch { }
  let prev = {};
  try { prev = JSON.parse(r.meta || '{}'); } catch { }
  const meta = { ...prev, retry: true, recovered_at: nowIso(), pre_retry_files: files };
  return db.prepare("UPDATE tasks SET status = 'queued', progress = ?, started_at = NULL, meta = ? WHERE id = ? AND status = 'running'")
    .run(RECOVER_PROGRESS, JSON.stringify(meta), r.id).changes;
}
// 恢复通知：写一条系统通知（工作台通知中心读 NOTIFY_DIR 顶层文件）
function notifyRecovery(rows, src) {
  if (!rows.length) return;
  try {
    fs.mkdirSync(C.NOTIFY_DIR, { recursive: true });
    const body = [
      '# 任务已从系统重启中恢复',
      '',
      `- 时间：${nowIso()}`,
      `- 来源：${src}`,
      `- 恢复任务数：${rows.length}`,
      '',
      '> 这些任务在执行中被系统重启打断，已自动重新排队继续。',
      '> **重试可能与中断前重复执行**：产物目录中中断前已有的文件不会被覆盖；',
      '> 若目标文件名已冲突，重试会另存为 `<原名>-retry-<HHMMSS>`。',
      '',
      ...rows.map((r) => `- 任务 ${r.id}（${r.agent_id}）`),
    ].join('\n'
);
    fs.writeFileSync(path.join(C.NOTIFY_DIR, `任务恢复-${stampCompact(new Date())}.md`), body, 'utf8');
  } catch (e) { console.error('[tasks] 恢复通知写入失败:', e.message); }
}

function recoverStale(opts = {}) {
  // boot=true：进程刚启动，本进程内不可能存在在跑的任务 → 用 30s 短宽限回收上一进程遗留的 running；
  // 默认（诊断脚本 require / 周期巡检）：只回收确实超时的（任务超时 + 5 分钟），绝不触碰正常执行中的任务。
  const grace = opts.boot ? 30000 : TASK_TIMEOUT_MS + 300000;
  const cutoff = new Date(Date.now() - grace).toISOString();
  const stale = db.prepare("SELECT id, agent_id, meta FROM tasks WHERE status = 'running' AND (started_at IS NULL OR started_at < ?)").all(cutoff);
  for (const r of stale) requeueInterrupted(r);
  if (stale.length) console.log(`[tasks] 中断恢复：${stale.length} 个任务重新排队`);
  notifyRecovery(stale, opts.boot ? '启动恢复（boot，30s 宽限）' : '周期巡检（超时阈值）');
  for (const r of db.prepare("SELECT DISTINCT agent_id AS a FROM tasks WHERE status = 'queued'").all()) setImmediate(() => pump(r.a));
  return stale.length;
}
// 周期巡检：崩溃/重启遗留的 running 任务无需人工介入，自动回到队列（默认 60s 一轮）
// 巡检专用（服务进程内调用）：进程内 running 集合 = 本进程正在执行的任务。
// DB 标着 running 但本进程并未执行它 → 必然是被中断的孤儿任务，立即回收重排，不等超时阈值。
function recoverOrphans() {
  const rows = db.prepare("SELECT id, agent_id, meta FROM tasks WHERE status = 'running'").all();
  const orphans = rows.filter((r) => !running.has(r.agent_id));
  for (const r of orphans) requeueInterrupted(r);
  if (orphans.length) console.log(`[tasks] 孤儿任务自动重排：${orphans.length} 个`);
  notifyRecovery(orphans, '周期巡检（孤儿任务，进程内未在执行）');
  for (const r of db.prepare("SELECT DISTINCT agent_id AS a FROM tasks WHERE status = 'queued'").all()) setImmediate(() => pump(r.a));
  return orphans.length;
}

function startSweeper(intervalMs = 60000) {
  const t = setInterval(() => { try { recoverOrphans(); } catch (e) { console.error("[tasks] 巡检异常", e.message); } }, intervalMs);
  if (t.unref) t.unref();
  return t;
}


// ═══ API ═══════════════════════════════════════════════════════════════
function agentExists(id) {
  try {
    const reg = readRegistry();   // readRegistry 返回 { <agent_id>: {...} } 形式的对象
    if (!reg || typeof reg !== 'object') return false;
    if (Object.prototype.hasOwnProperty.call(reg, id)) return true;
    const list = Array.isArray(reg) ? reg : Object.values(reg);
    return list.some((a) => a && a.id === id);
  } catch { return false; }
}

// 任务创建核心逻辑（HTTP 路由与 MCP task_create 共用，4.11）
function createTask(b, user) {
  b = b || {};
  const title = String(b.title || '').trim();
  const description = String(b.description || '').trim();
  const agentId = String(b.agent_id || '').trim();
  if (!title) return { error: 'title 必填', status: 400 };
  if (!description) return { error: 'description 必填', status: 400 };
  if (!agentId) return { error: 'agent_id 必填', status: 400 };
  if (!agentExists(agentId)) return { error: `Agent 不存在：${agentId}`, status: 400 };
  const refFiles = Array.isArray(b.ref_files) ? b.ref_files.map(String) : [];
  const refMems = Array.isArray(b.ref_memories) ? b.ref_memories.map(String) : [];
  const vis = ['team', 'private', 'restricted'].includes(b.memory_visibility) ? b.memory_visibility : 'team';
  if (vis === 'restricted' && !(Array.isArray(b.memory_allow_members) && b.memory_allow_members.length))
    return { error: 'restricted 可见性需至少指定 1 位 memory_allow_members', status: 400 };

  // D36：描述 + 引用资料名 + 引用记忆标题中的敏感内容强制人审
  let scanText = title + ' ' + description;
  try {
    const all = readFiles();
    for (const id of refFiles) { const e = all.find((x) => x.id === id); if (e) scanText += ' ' + e.name; }
    const { db: mdb } = require('./memories');
    for (const id of refMems) { const m = mdb.prepare('SELECT title FROM memories WHERE id = ?').get(id); if (m) scanText += ' ' + m.title; }
  } catch { /* 引用查不到不影响主流程 */ }
  const hits = detectSensitive(scanText);
  const requiresApproval = hits.length ? 1 : (b.requires_approval ? 1 : 0);

  const id = uuid(); const at = nowIso();
  db.prepare(`INSERT INTO tasks (id,title,description,agent_id,ref_files,ref_memories,status,requires_approval,
    approval_status,progress,created_by,created_at,memory_visibility,meta)
    VALUES (?,?,?,?,?,?,'queued',?,NULL,?,?,?,?,?)`)
    .run(id, title, description, agentId, JSON.stringify(refFiles), JSON.stringify(refMems),
      requiresApproval, '已排队', user.username, at, vis,
      JSON.stringify({ approval_forced_by: hits, memory_allow_members: b.memory_allow_members || [] }));
  const t = db.prepare('SELECT * FROM tasks WHERE id = ?').get(id);
  setImmediate(() => pump(agentId));
  console.log(`[tasks] 新建 ${id} by ${user.username} → ${agentId}${requiresApproval ? '（需人审：' + hits.join('/') + '）' : ''}`);
  return { ok: true, task: publicTask(t, { queue_ahead: queueAhead(t) }), approval_forced_by: hits };
}

// POST /api/tasks 发起任务（D23/D36）
router.post('/tasks', authRequired, (req, res) => {
  const r = createTask(req.body, req.user);
  if (r.error) return res.status(r.status || 400).json({ error: r.error });
  res.status(201).json(r);
});


// GET /api/tasks 任务列表
router.get('/tasks', authRequired, (req, res) => {
  const { status, agent_id: agentId } = req.query;
  const lim = Math.min(parseInt(req.query.limit, 10) || 100, 500);
  if (status && !STATUSES.includes(status)) return res.status(400).json({ error: `status 须为 ${STATUSES.join('|')}` });
  const where = []; const args = [];
  if (status) { where.push('status = ?'); args.push(status); }
  if (agentId) { where.push('agent_id = ?'); args.push(agentId); }
  const rows = db.prepare(`SELECT * FROM tasks ${where.length ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY created_at DESC LIMIT ?`)
    .all(...args, lim);
  res.json({ ok: true, n: rows.length, tasks: rows.map((t) => publicTask(t, { queue_ahead: queueAhead(t) })) });
});

// GET /api/tasks/:id 任务详情（含产物与修正记录）
router.get('/tasks/:id', authRequired, (req, res) => {
  const t = db.prepare('SELECT * FROM tasks WHERE id = ?').get(req.params.id);
  if (!t) return res.status(404).json({ error: '任务不存在' });
  res.json({ ok: true, task: publicTask(t, { queue_ahead: queueAhead(t), outputs: listOutputs(t.id), corrections: listCorrections(t.id), meta: metaOf(t) }) });
});

// POST /api/tasks/:id/approval 审批（D35/D36）：approve 通过 | modify 带修正意见返工 | reject 驳回
router.post('/tasks/:id/approval', authRequired, (req, res) => {
  const b = req.body || {};
  const action = String(b.action || '').trim();
  const note = String(b.note || '').trim();
  if (!['approve', 'modify', 'reject'].includes(action)) return res.status(400).json({ error: 'action 须为 approve|modify|reject' });
  if (!note) return res.status(400).json({ error: 'note 必填（审批意见/修正理由）' });
  const t = db.prepare('SELECT * FROM tasks WHERE id = ?').get(req.params.id);
  if (!t) return res.status(404).json({ error: '任务不存在' });
  if (t.created_by !== req.user.username && req.user.role !== 'admin')
    return res.status(403).json({ error: '仅任务创建者或管理员可审批' });
  if (t.status !== 'waiting_approval')
    return res.status(400).json({ error: `任务当前状态为 ${t.status}，不可审批` });

  const cid = uuid(); const at = nowIso();
  db.prepare('INSERT INTO task_corrections (id,task_id,agent_id,action,note,decided_by,created_at) VALUES (?,?,?,?,?,?,?)')
    .run(cid, t.id, t.agent_id, action, note, req.user.username, at);

  if (action === 'approve') {
    db.prepare(`UPDATE tasks SET status='done', approval_status='approved', approved_by=?, correction_note=?, progress=?, completed_at=? WHERE id=?`)
      .run(req.user.username, note, '审批通过', at, t.id);
    const row = db.prepare('SELECT * FROM tasks WHERE id = ?').get(t.id);
    const p = precipitate(row, { correctionSummary: note });
    console.log(`[tasks] 审批通过 ${t.id} by ${req.user.username}，沉淀记忆 ${p.memory_id || p.error}`);
    return res.json({ ok: true, action, task: publicTask(row, { queue_ahead: 0, outputs: listOutputs(t.id), corrections: listCorrections(t.id) }), correction_id: cid, precip: p });
  }
  if (action === 'modify') {
    db.prepare(`UPDATE tasks SET status='queued', approval_status='modified', correction_note=?, progress=? WHERE id=?`)
      .run(note, '按审批修正意见重新排队', t.id);
    const row = db.prepare('SELECT * FROM tasks WHERE id = ?').get(t.id);
    setImmediate(() => pump(t.agent_id));
    console.log(`[tasks] 审批返工 ${t.id} by ${req.user.username}`);
    return res.json({ ok: true, action, task: publicTask(row, { queue_ahead: queueAhead(row), outputs: listOutputs(t.id), corrections: listCorrections(t.id) }), correction_id: cid });
  }
  db.prepare(`UPDATE tasks SET status='failed', approval_status='rejected', correction_note=?, error=?, progress=?, completed_at=? WHERE id=?`)
    .run(note, `审批驳回：${note}`, '审批驳回', at, t.id);
  const row = db.prepare('SELECT * FROM tasks WHERE id = ?').get(t.id);
  console.log(`[tasks] 审批驳回 ${t.id} by ${req.user.username}`);
  res.json({ ok: true, action, task: publicTask(row, { queue_ahead: 0, outputs: listOutputs(t.id), corrections: listCorrections(t.id) }), correction_id: cid });
});

// POST /api/tasks/:id/cancel 取消任务
router.post('/tasks/:id/cancel', authRequired, (req, res) => {
  const t = db.prepare('SELECT * FROM tasks WHERE id = ?').get(req.params.id);
  if (!t) return res.status(404).json({ error: '任务不存在' });
  if (t.created_by !== req.user.username && req.user.role !== 'admin')
    return res.status(403).json({ error: '仅任务创建者或管理员可取消' });
  if (!['queued', 'running', 'waiting_approval'].includes(t.status))
    return res.status(400).json({ error: `任务已结束（${t.status}），不可取消` });
  db.prepare(`UPDATE tasks SET status='failed', progress=?, error=?, completed_at=? WHERE id=? AND status IN ('queued','running','waiting_approval')`)
    .run('已取消', `已由 ${req.user.username} 取消`, nowIso(), t.id);
  const row = db.prepare('SELECT * FROM tasks WHERE id = ?').get(t.id);
  console.log(`[tasks] 取消 ${t.id} by ${req.user.username}`);
  res.json({ ok: true, task: publicTask(row) });
});

// GET /api/tasks/:id/outputs/:oid/download 下载产物
router.get('/tasks/:id/outputs/:oid/download', authRequired, (req, res) => {
  const o = db.prepare('SELECT * FROM outputs WHERE id = ? AND task_id = ?').get(req.params.oid, req.params.id);
  if (!o) return res.status(404).json({ error: '产物不存在' });
  if (!fs.existsSync(o.file_path)) return res.status(404).json({ error: '产物文件已丢失' });
  res.download(o.file_path, o.file_name);
});

module.exports = { router, db, pump, startSweeper, recoverOrphans, createTask, buildInstruction, detectSensitive, classifyReply, publicTask, running, recoverStale };
