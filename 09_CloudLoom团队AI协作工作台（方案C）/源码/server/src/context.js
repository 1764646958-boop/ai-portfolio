'use strict';
// S4.1 / C3：上下文窗口策略（长会话省钱）
// 问题：SPEC M1 要求每次 /api/chat 携带完整会话历史；会话越长，单次请求的输入 token 线性膨胀，
//       30 轮之后每一轮都在为「早已说完的旧话」反复付费。
// 策略：默认只保留最近 N 轮（C.CHAT_HISTORY_MAX_ROUNDS，默认 12），并补一条系统说明「更早对话已省略」。
//       可选（env 开关 C.CHAT_SUMMARY_ENABLED，默认关）：被裁掉的早期部分由本 Agent 生成一次摘要，
//       按 conversation+agent 存进 context_summaries 表复用，之后用「摘要 + 最近 N 轮」。
// 硬约束（C3-2）：任务中心的任务上下文注入、D35 修正记录注入、@Agent 拉入的片段注入都必须留在窗口内。
//       这三种注入都出现在**首条 system 消息**或**最后一条 user 消息**里，而本策略只裁「更早的历史」，
//       所以天然满足；另有 KEEP_MARKERS 兜底：命中标记的消息一律不裁。
const C = require('./config');
const { db } = require('./db');
const { readRegistry } = require('./registry');
const { nowIso } = require('./util');

// 这些标记出现即视为「必须保留在窗口内」的注入内容（C3-2 的三类 + 恢复重试约束）
const KEEP_MARKERS = ['【任务】', '【任务上下文】', '【修正记录】', '【上下文提示】', '【重试约束】', '【当前问题】'];

function isKeep(msg) {
  if (!msg || typeof msg.content !== 'string') return false;
  if (msg.role === 'system') return true;                  // 系统说明/注入片段：永远保留
  return KEEP_MARKERS.some((m) => msg.content.includes(m));
}

function roundsLimit() {
  const n = +C.CHAT_HISTORY_MAX_ROUNDS;
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;   // 0 或负数 = 关闭裁剪（实测对照用）
}

// 纯函数：裁出「最近 N 轮」。返回 {messages, dropped}
function windowOf(messages) {
  const limit = roundsLimit();
  if (!limit) return { messages, dropped: 0 };
  const keep = [];
  const rest = [];
  for (const m of messages) (isKeep(m) ? keep : rest).push(m);
  const maxMsgs = limit * 2;                                // 一轮 ≈ user + assistant
  if (rest.length <= maxMsgs) return { messages, dropped: 0 };
  const tail = rest.slice(-maxMsgs);
  const droppedMsgs = rest.slice(0, rest.length - maxMsgs);
  // 保持原顺序：被保留的系统消息按原位置插回（此处把所有 keep 放前面，与原语义一致）
  const out = keep.concat(tail);
  return { messages: out, dropped: droppedMsgs.length, droppedMsgs, tail, keep };
}

const OMIT_NOTE = '【上下文说明】为保证响应速度与成本，更早的对话已省略；如需追溯请让对方复述关键结论。';

function cacheGet(convId, agentId) {
  try {
    return db.prepare('SELECT * FROM context_summaries WHERE conversation_id = ? AND agent_id = ?').get(convId, agentId);
  } catch { return null; }
}
function cachePut(convId, agentId, droppedCount, summary) {
  try {
    db.prepare('INSERT INTO context_summaries (conversation_id, agent_id, dropped_count, summary, created_at) VALUES (?,?,?,?,?) ON CONFLICT(conversation_id, agent_id) DO UPDATE SET dropped_count = excluded.dropped_count, summary = excluded.summary, created_at = excluded.created_at')
      .run(convId, agentId, droppedCount, summary, nowIso());
  } catch (e) { console.error('[context] 摘要缓存写入失败：' + e.message); }
}

// 让被裁剪的那部分交给「本 Agent」自摘要（可选路径；默认关）。任何失败都退回纯裁剪，不影响主流程。
async function summarize(agentId, droppedMsgs) {
  const reg = readRegistry();
  const agent = reg[agentId];
  if (!agent) throw new Error('Agent 不存在：' + agentId);
  const body = droppedMsgs.map((m) => (m.role === 'user' ? '用户：' : m.role === 'assistant' ? '你：' : '系统：') + String(m.content || '')).join('\n');
  const r = await fetch('http://127.0.0.1:' + agent.port + '/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + agent.api_server_key },
    body: JSON.stringify({
      stream: false,
      messages: [
        { role: 'system', content: '你在为一个长会话生成「早期部分摘要」，供后续轮次延续上下文。只输出要点，不要寒暄，不超过 200 字。' },
        { role: 'user', content: '以下是需要压缩的早期对话：\n' + body.slice(0, 60000) },
      ],
    }),
  });
  if (!r.ok) throw new Error('摘要上游返回 ' + r.status);
  const j = await r.json();
  return String(j.choices?.[0]?.message?.content || '').trim();
}

// 主入口：按策略返回真正发往网关的 messages
// 返回 { messages, dropped, note, summaryUsed, changed }
async function applyWindow(messages, opts) {
  const o = opts || {};
  const w = windowOf(messages);
  if (!w.dropped) return { messages, dropped: 0, note: null, summaryUsed: false, changed: false };

  const out = w.keep.slice();
  let summaryUsed = false;
  if (C.CHAT_SUMMARY_ENABLED && o.conversationId && o.agentId) {
    try {
      const row = cacheGet(o.conversationId, o.agentId);
      let text = row && row.summary;
      if (!row || row.dropped_count > w.dropped) {         // 缓存只覆盖更短的早期部分 → 重新生成一次
        text = await summarize(o.agentId, w.droppedMsgs);
        cachePut(o.conversationId, o.agentId, w.dropped, text);
      }
      if (text) {
        out.push({ role: 'system', content: '【早期对话摘要（已省略原始记录）】\n' + text });
        summaryUsed = true;
      }
    } catch (e) {
      console.error('[context] 摘要失败，退回纯裁剪：' + e.message);
    }
  }
  if (!summaryUsed) out.push({ role: 'system', content: OMIT_NOTE });
  out.push(...w.tail);
  console.log('[context] ' + (o.agentId || '?') + ' 上下文裁剪：' + messages.length + ' → ' + out.length + ' 条（省略早期 ' + w.dropped + ' 条' + (summaryUsed ? '，改用摘要' : '') + '）');
  return { messages: out, dropped: w.dropped, note: summaryUsed ? 'summary' : OMIT_NOTE, summaryUsed, changed: true };
}

module.exports = { applyWindow, windowOf, OMIT_NOTE, KEEP_MARKERS };
