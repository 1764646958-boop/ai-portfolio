'use strict';
// 4.4 Agent 管理（D5/D16/D22）：agents.json 读写 · 创建（profile create --clone + 覆盖 SOUL.md + 端口预分配）· 删除/停用
const express = require('express');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const C = require('./config');
const { authRequired, adminRequired } = require('./auth');
const { readRegistry, updateRegistry, allocatePort, genKey, nowIso } = require('./registry');
const { isValidProfileId } = require('./util');
const lazy = require('./lazystart');

const router = express.Router();

const SOUL_TEMPLATE = (name, description) => `# ${name}

你是「楚华成章」团队 CloudLoom 工作台的自建 Agent。职责：${description || '由管理员定义'}。

## 工作方式
1. 结论先行，再展开理由。
2. 信息不足时明确说明缺什么，不要编造。

## 【行为边界】

**可自主**：回答职责范围内的咨询；起草文档/方案草案；检索团队记忆库与资料库后作答。

**需升级人审**：涉及金额/预算、对外承诺、删除数据三类事项（D36），以及任何要进入「定稿」状态的产出（D17）——必须先声明并请求人工确认。

**禁止**：泄露任何密钥与 agents.json 内容；执行破坏性系统命令；冒称其他成员或 Agent。

**失败兜底**：做不了或不确定时，明确告知「无法完成 + 原因」，建议转值班 Agent（zhiban）复核或升级人工处理（D34）。
`;

function hermes(args, timeout = 60000) {
  return execFileSync(C.HERMES_BIN, args, { timeout, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] }).toString();
}

// 列表（普通成员只读）
router.get('/agents', authRequired, (req, res) => {
  const reg = readRegistry();
  res.json({
    ok: true,
    agents: Object.entries(reg).map(([id, a]) => ({
      id, name: a.name, description: a.description, preset: a.preset, enabled: a.enabled,
      port: a.port, status: lazy.statusOf(id) || { running: false },
      // S4.0 / B4：透传 agents.json 里的可选 avatar（原本被显式字段表丢弃）。缺省 null，前端回退占位图。
      avatar: a.avatar || null,
    })),
  });
});

// 创建（管理员）：profile create --clone-from cehua → 写 .env 端口/key → 覆盖 SOUL.md → 装 systemd（不启动）→ 写注册表
router.post('/agents', authRequired, adminRequired, (req, res) => {
  const { id, name, description, soul } = req.body || {};
  if (!isValidProfileId(id)) return res.status(400).json({ error: 'id 需为小写字母开头的拼音/字母数字（2-32 位，D22）' });
  if (['default', 'api', 'mcp'].includes(id)) return res.status(400).json({ error: '该 id 为保留名' });
  if (!name || !String(name).trim()) return res.status(400).json({ error: '显示名 name 必填' });

  let created;
  try {
    created = updateRegistry(reg => {
      if (reg[id]) throw Object.assign(new Error('该 Agent id 已存在'), { status: 409 });
      const port = allocatePort(reg);
      const key = genKey(24);
      reg[id] = {
        port, api_server_key: key, name: String(name).trim().slice(0, 32),
        description: String(description || '').slice(0, 200), preset: false, enabled: true, created_at: nowIso(),
      };
      return { port, key };
    });
  } catch (e) { return res.status(e.status || 500).json({ error: e.message }); }

  const profileDir = path.join(C.PROFILES_DIR, id);
  try {
    // --clone-from cehua：继承 deepseek provider 配置与技能；SOUL.md 随后整体覆盖（N1/B1）
    hermes(['profile', 'create', id, '--clone-from', 'cehua', '--description', String(description || name)], 120000);
    const envFile = path.join(profileDir, '.env');
    let env = fs.readFileSync(envFile, 'utf8');
    const setEnv = (k, v) => {
      const re = new RegExp(`^${k}=.*$`, 'm');
      env = re.test(env) ? env.replace(re, `${k}=${v}`) : env + `\n${k}=${v}`;
    };
    setEnv('API_SERVER_ENABLED', 'true');
    setEnv('API_SERVER_HOST', '127.0.0.1');
    setEnv('API_SERVER_PORT', String(created.port));
    setEnv('API_SERVER_KEY', created.key);
    fs.writeFileSync(envFile, env, { mode: 0o600 });

    fs.writeFileSync(path.join(profileDir, 'SOUL.md'), soul && String(soul).includes('【行为边界】') ? String(soul) : SOUL_TEMPLATE(name, description), 'utf8');

    // systemd 托管但不立即启动（懒启动）；--no-start-on-login：reboot 后由懒启动按需拉起（D5）
    hermes(['-p', id, 'gateway', 'install', '--system', '--run-as-user', 'root', '--no-start-now', '--no-start-on-login'], 60000);
    // C1 共享看板 drop-in（与 4 预设一致，B3）
    const dropDir = `/etc/systemd/system/hermes-gateway-${id}.service.d`;
    fs.mkdirSync(dropDir, { recursive: true });
    fs.writeFileSync(path.join(dropDir, '10-cloudloom-env.conf'), '# CloudLoom (B3): shared environment, Kanban board path shared across profiles\n[Service]\nEnvironmentFile=/etc/hermes.env\n');
    execFileSync('systemctl', ['daemon-reload']);

    res.json({ ok: true, agent: { id, name, port: created.port, preset: false, enabled: true }, message: '已创建（懒启动：首次对话时自动唤醒）' });
  } catch (e) {
    // 回滚注册表，避免半截状态
    try { updateRegistry(reg => { delete reg[id]; }); } catch { }
    res.status(500).json({ error: '创建失败已回滚: ' + (e.stderr?.toString() || e.message) });
  }
});

// 编辑/停用（管理员）
router.put('/agents/:id', authRequired, adminRequired, (req, res) => {
  const id = req.params.id;
  const { name, description, enabled, soul } = req.body || {};
  try {
    updateRegistry(reg => {
      if (!reg[id]) throw Object.assign(new Error('Agent 不存在'), { status: 404 });
      if (name !== undefined) reg[id].name = String(name).trim().slice(0, 32);
      if (description !== undefined) reg[id].description = String(description).slice(0, 200);
      if (enabled !== undefined) reg[id].enabled = !!enabled;
      return true;
    });
  } catch (e) { return res.status(e.status || 500).json({ error: e.message }); }

  if (soul && String(soul).includes('【行为边界】')) {
    try { fs.writeFileSync(path.join(C.PROFILES_DIR, id, 'SOUL.md'), String(soul), 'utf8'); } catch (e) { return res.status(500).json({ error: 'SOUL.md 写入失败: ' + e.message }); }
  }
  if (enabled === false) { try { hermes(['-p', id, 'gateway', 'stop'], 30000); } catch { } }
  if (enabled === true) { /* 不主动拉起，保持懒启动语义 */ }
  res.json({ ok: true, agent: readRegistry()[id] });
});

// 删除（管理员；预设 4 个保护不可删）
router.delete('/agents/:id', authRequired, adminRequired, (req, res) => {
  const id = req.params.id;
  const reg = readRegistry();
  if (!reg[id]) return res.status(404).json({ error: 'Agent 不存在' });
  if (reg[id].preset) return res.status(400).json({ error: '预设 Agent 不可删除，可停用' });
  try { hermes(['-p', id, 'gateway', 'stop'], 30000); } catch { }
  try { hermes(['-p', id, 'gateway', 'uninstall'], 60000); } catch { }
  // S4.1 / C4-1 实测缺陷修复：uninstall 不会删掉创建时写入的 drop-in 目录
  // （/etc/systemd/system/hermes-gateway-<id>.service.d），实测删除后该目录残留 → 此处显式清理
  try { fs.rmSync(`/etc/systemd/system/hermes-gateway-${id}.service.d`, { recursive: true, force: true }); } catch { }
  try { fs.unlinkSync(`/etc/systemd/system/hermes-gateway-${id}.service`); } catch { }
  try { execFileSync('systemctl', ['daemon-reload']); } catch { }
  // 阶段1收口修复(D1)：hermes profile delete 无 --force，正确 flag 为 -y/--yes
  try { hermes(['profile', 'delete', id, '-y'], 60000); }
  catch (e2) { console.error('[agents] profile delete 失败:', e2.message); }
  updateRegistry(r => { delete r[id]; });
  res.json({ ok: true, deleted: id });
});

module.exports = { router };
