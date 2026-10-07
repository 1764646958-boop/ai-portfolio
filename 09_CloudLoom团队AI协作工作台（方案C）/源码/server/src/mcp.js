'use strict';
// 4.11 MCP 网关（D28）· Streamable HTTP · Bearer 复用 JWT（与 /api 相同认证与 ACL）
// 阶段 1 骨架：暴露 kanban_list / file_search；memory_search / memory_add / task_create 留接口位（阶段 2 填充）
const express = require('express');
const crypto = require('crypto');
const { authRequired } = require('./auth');
const { queryKanban } = require('./kanban');
const { readFiles } = require('./files');

const router = express.Router();

const PROTOCOL_VERSION = '2025-06-18';
const SERVER_INFO = { name: 'cloudloom-mcp-gateway', version: '1.0.0' };
const NOT_READY = '服务未就绪：该工具为留位接口，将在阶段 2 接入真实实现';

// 工具描述（阶段 2 起 5 个工具均为真实实现）
const TOOLS = [
  {
    name: 'kanban_list',
    description: '列出团队共享看板任务（包装 GET /api/kanban）',
    inputSchema: { type: 'object', properties: { status: { type: 'string', description: '按状态过滤，如 blocked/todo/doing/done' } } },
  },
  {
    name: 'file_search',
    description: '检索资料库文件与网盘链接（包装 GET /api/files）',
    inputSchema: { type: 'object', properties: { keyword: { type: 'string', description: '文件名关键词' }, category: { type: 'string' } } },
  },
  {
    name: 'memory_search',
    description: '检索团队记忆库（包装 GET /api/memories，按调用者 ACL 过滤）',
    inputSchema: { type: 'object', properties: { query: { type: 'string' }, type: { type: 'string' }, limit: { type: 'number' } }, required: ['query'] },
  },
  {
    name: 'memory_add',
    description: '写入团队记忆（包装 POST /api/memories，ACL 与 /api 一致）',
    inputSchema: {
      type: 'object',
      properties: { type: { type: 'string' }, title: { type: 'string' }, content: { type: 'string' }, tags: { type: 'string' }, visibility: { type: 'string' }, allow_members: { type: 'array', items: { type: 'string' } } },
      required: ['type', 'title', 'content'],
    },
  },
  {
    name: 'task_create',
    description: '创建办公任务（包装 POST /api/tasks，D36 敏感内容自动转人审）',
    inputSchema: {
      type: 'object',
      properties: { title: { type: 'string' }, description: { type: 'string' }, agent_id: { type: 'string' }, ref_files: { type: 'array', items: { type: 'string' } }, ref_memories: { type: 'array', items: { type: 'string' } }, requires_approval: { type: 'boolean' } },
      required: ['title', 'description', 'agent_id'],
    },
  },
];

const textResult = (text, isError = false) => ({ content: [{ type: 'text', text }], isError });

// 阶段 2 将由 tasks/memories 模块注入真实实现（保持工具签名不变）
const impl = {
  kanban_list: (args) => textResult(JSON.stringify(queryKanban(args?.status), null, 2)),
  file_search: (args) => {
    let list = readFiles();
    if (args?.category) list = list.filter(e => e.category === args.category);
    if (args?.keyword) { const s = String(args.keyword).toLowerCase(); list = list.filter(e => e.name.toLowerCase().includes(s)); }
    return textResult(JSON.stringify(list.map(({ id, kind, name, category, url, size, mime, uploader, created_at }) => ({ id, kind, name, category, url, size, mime, uploader, created_at })), null, 2));
  },
  memory_search: () => textResult(NOT_READY + '（memory_search）', true),
  memory_add: () => textResult(NOT_READY + '（memory_add）', true),
  task_create: () => textResult(NOT_READY + '（task_create）', true),
};

// 供阶段 2 覆盖留位实现
function registerImpl(name, fn) { impl[name] = fn; }

function jsonrpc(id, result, error) {
  const out = { jsonrpc: '2.0', id: id ?? null };
  if (error) out.error = error; else out.result = result;
  return out;
}

function handleMessage(msg, user) {
  if (!msg || msg.jsonrpc !== '2.0' || !msg.method) return { response: jsonrpc(msg?.id, null, { code: -32600, message: 'Invalid Request' }) };
  const { id, method, params } = msg;
  if (method.startsWith('notifications/')) return { notification: true };
  switch (method) {
    case 'initialize':
      return {
        response: jsonrpc(id, {
          protocolVersion: params?.protocolVersion || PROTOCOL_VERSION,
          capabilities: { tools: { listChanged: false } },
          serverInfo: SERVER_INFO,
          instructions: 'CloudLoom 团队能力 MCP 网关（记忆/任务/看板/资料库）。认证：Bearer 复用工作台 JWT；ACL 与 /api 一致。',
        }),
        setSession: true,
      };
    case 'ping': return { response: jsonrpc(id, {}) };
    case 'tools/list': return { response: jsonrpc(id, { tools: TOOLS }) };
    case 'tools/call': {
      const name = params?.name;
      const fn = impl[name];
      if (!fn) return { response: jsonrpc(id, null, { code: -32602, message: `未知工具: ${name}` }) };
      try { return { response: jsonrpc(id, fn(params?.arguments || {}, user)) }; }
      catch (e) { return { response: jsonrpc(id, textResult('工具执行失败: ' + e.message, true)) }; }
    }
    default:
      return { response: jsonrpc(id, null, { code: -32601, message: `Method not found: ${method}` }) };
  }
}

router.post('/', authRequired, (req, res) => {
  const body = req.body;
  const sessionId = req.headers['mcp-session-id'] || crypto.randomUUID();
  res.setHeader('Mcp-Session-Id', sessionId);
  if (Array.isArray(body)) {
    const results = body.map(m => handleMessage(m, req.user)).filter(r => !r.notification);
    if (!results.length) return res.status(202).end();
    return res.json(results.map(r => r.response));
  }
  const r = handleMessage(body, req.user);
  if (r.notification) return res.status(202).end();
  res.json(r.response);
});

// Streamable HTTP：无 SSE GET 需求时返回 405（协议允许）
router.get('/', (req, res) => res.status(405).json({ error: 'Method Not Allowed：本端点仅支持 POST（Streamable HTTP）' }));

module.exports = { router, registerImpl };

// ═══ 阶段 2（4.11）：留位工具接入真实实现 ═══════════════════════════════════
// 认证与 ACL 与 /api 完全一致：dispatch 已把 req.user 作为第 2 参数传入，此处直接复用。
registerImpl('memory_search', (args, user) => {
  const { searchMemories } = require('./memories');
  const rows = searchMemories(String(args?.query || ''), user, {
    type: args?.type,
    limit: Math.min(parseInt(args?.limit, 10) || 20, 50),
  });
  return textResult(JSON.stringify({ n: rows.length, memories: rows }, null, 2));
});

registerImpl('memory_add', (args, user) => {
  // insertMemory 返回的已是 publicMemory 形状（tags 为数组），勿二次映射
  const { insertMemory } = require('./memories');
  const memory = insertMemory({
    type: args?.type,
    title: args?.title,
    content: args?.content,
    tags: args?.tags,
    visibility: args?.visibility,
    allow_members: args?.allow_members,
  }, user);
  return textResult(JSON.stringify({ ok: true, memory }, null, 2));
});

registerImpl('task_create', (args, user) => {
  const { createTask } = require('./tasks');
  const r = createTask({
    title: args?.title,
    description: args?.description,
    agent_id: args?.agent_id,
    ref_files: args?.ref_files,
    ref_memories: args?.ref_memories,
    requires_approval: args?.requires_approval,
  }, user);
  if (r.error) return textResult('task_create 失败：' + r.error, true);
  return textResult(JSON.stringify({ ok: true, task: r.task, approval_forced_by: r.approval_forced_by }, null, 2));
});
