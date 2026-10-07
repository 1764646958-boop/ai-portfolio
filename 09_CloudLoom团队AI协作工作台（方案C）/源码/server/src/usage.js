'use strict';
// S4.1 / C2：用量记账与成本估算（全项目唯一落账点）
// 为什么需要它：/api/chat、看板指令、@Agent 拉入、任务执行——四条路径每次都会真的调用一次上游 LLM，
//              但在 C2 之前没有任何账目，负责人无法回答「本周花了多少、花在谁/哪个 Agent 身上」。
// 本模块只做三件事：
//   ① 把一次调用的 usage 落进 conversations.db 的 usage_log 表（加法式新表，不动既有表）；
//   ② 按 config.js 里可配的单价折算成本（美元为基准，另存人民币展示值）；
//   ③ 上游未回 usage 时（流式兜底）按字符数估算，并标 estimated=1 以便区分。
// 铁律：记账失败绝不影响业务——所有出口 try/catch，只写 stderr，不抛给调用方。
const C = require('./config');
const { db } = require('./db');
const { nowIso } = require('./util');

// 单价（美元 / 百万 tokens）：常量在 config.js，价目变动只改那一处（或用环境变量覆盖）
function priceOf() {
  return { i: C.PRICE_IN_PER_M, o: C.PRICE_OUT_PER_M, cr: C.PRICE_CACHE_READ_PER_M };
}

// 把 messages 拍平成纯文本（仅用于「上游没给 usage 时」的字符估算）
function textOf(messages) {
  try {
    if (!Array.isArray(messages)) return '';
    return messages.map((m) => (m && typeof m.content === 'string' ? m.content : '')).join('\n');
  } catch { return ''; }
}

// 字符转 token 估算：中日韩表意字与拉丁字符信息密度不同，分别用经验系数（config 可配）
// 这是兜底路径，只有上游明确没回 usage 才会走；正常路径一律用上游真实 usage。
function estimateTokens(text) {
  const s = String(text == null ? '' : text);
  let cjk = 0;
  for (const ch of s) { const c = ch.codePointAt(0); if (c >= 0x2e80 && c <= 0x9fff) cjk++; }
  const other = s.length - cjk;
  return Math.ceil(cjk / C.USAGE_EST_CHARS_PER_TOKEN_CJK + other / C.USAGE_EST_CHARS_PER_TOKEN_ASCII);
}

function costOf(u) {
  const p = priceOf();
  const x = u || {};
  const usd = ((x.promptTokens || 0) / 1e6) * p.i
            + ((x.completionTokens || 0) / 1e6) * p.o
            + ((x.cacheReadTokens || 0) / 1e6) * p.cr;
  return { usd, cny: usd * C.USD_CNY };
}

// 上游 usage 转统一三元组；DeepSeek 用 prompt_cache_hit_tokens 表示命中缓存的输入（单价低两个数量级）
function splitUsage(usage) {
  if (!usage || (usage.prompt_tokens == null && usage.completion_tokens == null)) return null;
  const p = +usage.prompt_tokens || 0;
  const c = +usage.completion_tokens || 0;
  const hit = (usage.prompt_cache_hit_tokens != null)
    ? usage.prompt_cache_hit_tokens
    : (usage.prompt_tokens_details ? usage.prompt_tokens_details.cached_tokens : 0);
  return { promptTokens: p, completionTokens: c, cacheReadTokens: +hit || 0 };
}

// 落账：actor=发起成员 id（系统自身触发为 null）；source 取值 chat|task|mention|kanban|zhiban-review
function logUsage(opts) {
  const o = opts || {};
  try {
    let u = splitUsage(o.usage);
    let estimated = 0;
    if (!u) {
      u = {
        promptTokens: estimateTokens(o.promptText),
        completionTokens: estimateTokens(o.completionText),
        cacheReadTokens: 0,
      };
      estimated = 1;
    }
    const c = costOf(u);
    db.prepare('INSERT INTO usage_log (ts, actor, agent_id, source, model, prompt_tokens, completion_tokens, cache_read_tokens, est_cost_usd, est_cost, estimated) VALUES (?,?,?,?,?,?,?,?,?,?,?)')
      .run(nowIso(), o.actor || null, o.agentId || null, o.source || 'agent', o.model || null,
           u.promptTokens, u.completionTokens, u.cacheReadTokens, c.usd, c.cny, estimated);
    return { promptTokens: u.promptTokens, completionTokens: u.completionTokens, cacheReadTokens: u.cacheReadTokens, usd: c.usd, cny: c.cny, estimated };
  } catch (e) {
    console.error('[usage] 记账失败（已忽略，不影响业务）：' + e.message);
    return null;
  }
}

module.exports = { logUsage, costOf, estimateTokens, textOf, splitUsage, priceOf };
