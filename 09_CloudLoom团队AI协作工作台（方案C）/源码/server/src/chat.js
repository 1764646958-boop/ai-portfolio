'use strict';
// 4.1 POST /api/chat：按 agents.json 路由 + Bearer 注入 + SSE 流式透传 + 懒启动唤醒事件
const express = require('express');
const C = require('./config');
const { authRequired } = require('./auth');
const { readRegistry } = require('./registry');
const lazy = require('./lazystart');
const { logUsage, textOf } = require('./usage');   // S4.1 / C2 用量记账
const ctx = require('./context');                  // S4.1 / C3 上下文窗口策略

const router = express.Router();

// 非流式调用 Agent（kanban-command / @Agent 拉入 / 任务执行复用）
// S4.1 / C2：callAgent 是「非流式」调用的唯一出口（任务执行、@Agent 拉入、看板指令共用），
// 因此把落账集中在这里一处即可覆盖全部非流式路径；actor = 发起成员 id，source 由调用方标注。
async function callAgent(agentId, messages, { timeoutMs = 180000, actor = null, source = 'agent', conversationId = null } = {}) {
  const reg = readRegistry();
  const agent = reg[agentId];
  if (!agent) throw new Error(`Agent「${agentId}」不存在`);
  await lazy.ensureRunning(agentId);
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  // S4.1 / C3：发往网关前套用上下文窗口策略（默认保留最近 12 轮；任务/修正/@Agent 注入一律保留）
  const win = await ctx.applyWindow(messages, { agentId, conversationId });
  try {
    const r = await fetch(`http://127.0.0.1:${agent.port}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${agent.api_server_key}` },
      body: JSON.stringify({ messages: win.messages, stream: false }),
      signal: ctrl.signal,
    });
    lazy.touch(agentId);
    if (!r.ok) throw new Error(`上游 ${agent.port} 返回 ${r.status}: ${(await r.text()).slice(0, 300)}`);
    const j = await r.json();
    const content = j.choices?.[0]?.message?.content || '';
    // S4.1 / C2：按上游返回的 usage 落账（上游没给则按字符数估算，estimated=1）
    logUsage({ actor, source, agentId, model: j.model, usage: j.usage, promptText: textOf(win.messages), completionText: content });
    return { content, model: j.model, usage: j.usage };
  } finally { clearTimeout(t); }
}

function sseWrite(res, event, data) {
  if (event) res.write(`event: ${event}\n`);
  res.write(`data: ${typeof data === 'string' ? data : JSON.stringify(data)}\n\n`);
}

router.post('/chat', authRequired, async (req, res) => {
  const { agent: agentId, messages, stream } = req.body || {};
  if (!agentId) return res.status(400).json({ error: 'agent 必填' });
  if (!Array.isArray(messages) || messages.length === 0) return res.status(400).json({ error: 'messages 必须为非空数组（M1：每次请求携带完整会话历史）' });
  const reg = readRegistry();
  const agent = reg[agentId];
  if (!agent) return res.status(404).json({ error: `Agent「${agentId}」不存在` });
  if (agent.enabled === false) return res.status(403).json({ error: `Agent「${agent.name}」已停用` });

  const wantStream = stream !== false; // 默认 SSE
  if (wantStream) {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    });
    res.write(': ok\n\n');
  }

  try {
    // 懒启动：先探活，不在跑 → 先发「正在唤醒」SSE 事件，再拉起（4.2 / 1.3.3）
    if (!(await lazy.isRunning(agentId))) {
      if (wantStream) sseWrite(res, 'status', { status: 'waking', message: `正在唤醒 ${agent.name}…` });
      await lazy.ensureRunning(agentId);
      if (wantStream) sseWrite(res, 'status', { status: 'ready', message: `${agent.name} 已就绪` });
    } else {
      lazy.touch(agentId); // C-14 修复（S3.1）：已在运行的实例同样回写 lastActive，避免空闲巡检把在用实例误停
    }
  } catch (e) {
    if (wantStream) { sseWrite(res, 'error', { error: e.message }); return res.end(); }
    const code = e.code === 'DISABLED' ? 403 : 502;
    return res.status(code).json({ error: e.message });
  }

  if (!wantStream) {
    try {
      const out = await callAgent(agentId, messages, { actor: req.user.id, source: 'chat', conversationId: req.body && (req.body.conversation_id || req.body.conversationId) || null });
      return res.json({ ok: true, ...out });
    } catch (e) { return res.status(502).json({ error: e.message }); }
  }

  // SSE 流式透传
  const ctrl = new AbortController();
  req.on('close', () => ctrl.abort());
  // S4.1 / C3：流式同样套用上下文窗口（与 callAgent 同一策略、同一函数）
  const win = await ctx.applyWindow(messages, { agentId, conversationId: (req.body && (req.body.conversation_id || req.body.conversationId)) || null });
  try {
    const upstream = await fetch(`http://127.0.0.1:${agent.port}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${agent.api_server_key}` },
      // S4.1 / C2：向上游索取 usage（OpenAI 兼容字段 stream_options.include_usage）。
      // 只加一个请求字段，透传给浏览器的字节流不做任何改动。
      body: JSON.stringify({ messages: win.messages, stream: true, stream_options: { include_usage: true } }),
      signal: ctrl.signal,
    });
    if (!upstream.ok || !upstream.body) {
      sseWrite(res, 'error', { error: `上游 ${agent.port} 返回 ${upstream.status}` });
      return res.end();
    }
    lazy.touch(agentId);
    const decoder = new TextDecoder();
    // S4.1 / C2：流式路径要计费，但**不得**改动透传语义 —— 收到的字节照原样写给浏览器，
    // 另旁路累积一份文本，仅用于解析末帧 usage 与兜底估算。
    let tail = '';
    let outText = '';
    let upUsage = null;
    let upModel = null;
    const NL = String.fromCharCode(10);
    for await (const chunk of upstream.body) {
      const text = decoder.decode(chunk, { stream: true });
      res.write(text);
      tail += text;
      const lines = tail.split(NL);
      tail = lines.pop();                       // 末段可能被 TCP 分片截断，留到下一片再解析
      for (const raw of lines) {
        const line = raw.trim();
        if (!line.startsWith('data:')) continue;
        const payload = line.slice(5).trim();
        if (!payload || payload === '[DONE]') continue;
        try {
          const j = JSON.parse(payload);
          if (j.model) upModel = j.model;
          if (j.usage) upUsage = j.usage;       // include_usage 生效时末帧带 usage
          const ch0 = j.choices && j.choices[0];
          const d = ch0 && ch0.delta && ch0.delta.content;
          if (typeof d === 'string') outText += d;
        } catch { /* 心跳行或非 JSON 行：忽略，不影响透传 */ }
      }
    }
    res.end();
    logUsage({
      actor: req.user.id, source: 'chat', agentId, model: upModel, usage: upUsage,
      promptText: textOf(win.messages), completionText: outText.slice(0, 200000),
    });
  } catch (e) {
    if (!res.writableEnded) { try { sseWrite(res, 'error', { error: e.message }); } catch { } res.end(); }
  }
});

module.exports = { router, callAgent };
