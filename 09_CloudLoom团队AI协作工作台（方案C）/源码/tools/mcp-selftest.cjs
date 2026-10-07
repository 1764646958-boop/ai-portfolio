// 最小 MCP stdio 服务器：仅用于验证 `hermes mcp add/test` 的发现链路（自检用，不对外提供能力）
// 协议：换行分隔的 JSON-RPC 2.0（MCP stdio 传输）
const readline = require('readline');
const TOOLS = [{
  name: 'ping',
  description: '返回 pong 与回显消息（MCP 接入自检用）',
  inputSchema: { type: 'object', properties: { msg: { type: 'string', description: '要回显的消息' } } },
}];
const send = (o) => process.stdout.write(JSON.stringify(o) + '\n');
const rl = readline.createInterface({ input: process.stdin });
rl.on('line', (line) => {
  const t = line.trim();
  if (!t) return;
  let m;
  try { m = JSON.parse(t); } catch { return; }
  const id = m.id;
  if (m.method === 'initialize') {
    send({ jsonrpc: '2.0', id, result: {
      protocolVersion: '2025-06-18', capabilities: { tools: {} },
      serverInfo: { name: 'cloudloom-selftest', version: '1.0.0' },
    } });
  } else if (m.method === 'notifications/initialized') {
    // 通知无需响应
  } else if (m.method === 'tools/list') {
    send({ jsonrpc: '2.0', id, result: { tools: TOOLS } });
  } else if (m.method === 'tools/call') {
    const a = (m.params && m.params.arguments) || {};
    send({ jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: 'pong: ' + (a.msg || '(no msg)') }] } });
  } else if (id !== undefined) {
    send({ jsonrpc: '2.0', id, error: { code: -32601, message: 'Method not found: ' + m.method } });
  }
});
