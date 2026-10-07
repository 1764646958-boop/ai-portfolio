#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S4.1 / C1：0-token 数据快照（每日一档，不花一分钱）

定位：把「每天该看的数字」用**纯脚本**汇总成一份 markdown，替代原先每天 06:00 的那次画像 LLM 作业。
      数字类信息不需要 LLM；LLM 只在每周一的《周报》里做「判断与建议」。
铁律：本脚本**不调用任何 LLM**。外部动作只有两类：
      ① 只读打开各 SQLite 库；② 一次 DeepSeek 余额 HTTP 查询（GET /user/balance）。
      因此它产生的 token 消耗恒为 0，可由「没有任何 usage_log 新行」验证。

用法：
    python3 /opt/team-console/ops/digest.py              # 写 系统通知/快照-YYYYMMDD.md，stdout 一行回执
    python3 /opt/team-console/ops/digest.py --stdout     # 全文打到 stdout
    python3 /opt/team-console/ops/digest.py --cost-only  # 只输出「本周花费」段（供周报作业引用）
"""
import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
NOW = datetime.now(TZ)
DAY = NOW.strftime('%Y%m%d')
NOTIFY = '/root/team-files/系统通知'
KANBAN_DB = '/root/.hermes/kanban.db'
TASKS_DB = '/opt/team-console/data/tasks.db'
CONV_DB = '/opt/team-console/data/conversations.db'
MEM_DB = '/opt/team-console/data/team-memory.db'
HERMES_ENV = '/root/.hermes/.env'
SINCE = (NOW - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')
DONE_STATES = ('done', 'completed', 'archived', 'cancelled', 'canceled')
PRICE_NOTE = '输入 $0.14/M、输出 $0.28/M、缓存命中 $0.0028/M（config.js 可配，与 Hermes 自身计费同源）'


def q(dbpath, sql, args=()):
    """只读查询；库/表缺失一律返回 None，绝不让整份快照失败（诚实标注「未能读取」）。"""
    try:
        con = sqlite3.connect('file:%s?mode=ro' % dbpath, uri=True)
        try:
            return list(con.execute(sql, args))
        finally:
            con.close()
    except Exception:
        return None


def env_value(name):
    try:
        for line in open(HERMES_ENV, encoding='utf-8'):
            m = line.strip()
            if m.startswith(name + '='):
                return m.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def balance():
    """DeepSeek 余额（原样返回货币与可用性；失败返回 {'error': ...}）。"""
    key = env_value('DEEPSEEK_API_KEY')
    if not key:
        return None
    try:
        req = urllib.request.Request('https://api.deepseek.com/user/balance',
                                     headers={'Authorization': 'Bearer ' + key})
        doc = json.load(urllib.request.urlopen(req, timeout=15))
        info = (doc.get('balance_infos') or [{}])[0]
        return {'total': info.get('total_balance'), 'currency': info.get('currency'),
                'available': doc.get('is_available')}
    except Exception as e:
        return {'error': str(e)[:120]}


def section_kanban():
    rows = q(KANBAN_DB, 'SELECT status, COUNT(*) FROM tasks GROUP BY status')
    out = ['## 一、看板（Kanban）']
    if rows is None:
        return out + ['- 本次未能读取 kanban 库。']
    if not rows:
        return out + ['- 看板为空（无任务）。']
    out.append('- 状态分布：' + '｜'.join('%s=%d' % (s or '?', n) for s, n in sorted(rows, key=lambda r: -r[1])))
    todo = q(KANBAN_DB, 'SELECT id, status, assignee, priority, title FROM tasks WHERE status NOT IN (%s) ORDER BY status, priority'
                        % ','.join(['?'] * len(DONE_STATES)), DONE_STATES)
    if todo:
        out.append('')
        out.append('| 状态 | 负责人 | 优先级 | 任务 | 编号 |')
        out.append('|---|---|---|---|---|')
        for tid, st, who, pri, title in todo[:20]:
            out.append('| %s | %s | %s | %s | %s |' % (st, who or '-', pri or '-', (title or '').replace('|', '/')[:40], tid))
    else:
        out.append('- 当前没有未完成的任务。')
    return out


def section_taskcenter():
    out = ['', '## 二、任务中心（自建 tasks.db）']
    rows = q(TASKS_DB, 'SELECT status, COUNT(*) FROM tasks GROUP BY status')
    if rows is None:
        return out + ['- 本次未能读取任务库。']
    out.append('- 状态分布：' + ('｜'.join('%s=%d' % (s or '?', n) for s, n in rows) if rows else '（空）'))
    pend = q(TASKS_DB, "SELECT COUNT(*) FROM tasks WHERE status IN ('pending','running') OR approval_status='pending'")
    if pend:
        out.append('- 在办/待审批合计：%d 条' % pend[0][0])
    return out


def section_unread():
    out = ['', '## 三、聊天未读']
    rows = q(CONV_DB, """SELECT u.username, COALESCE(SUM(CASE WHEN m.seq > cm.last_read_seq THEN 1 ELSE 0 END), 0) AS unread
                         FROM users u
                         LEFT JOIN conversation_members cm ON cm.member_id = u.id
                         LEFT JOIN messages m ON m.conversation_id = cm.conversation_id
                         GROUP BY u.id ORDER BY unread DESC""")
    if rows is None:
        return out + ['- 本次未能读取会话库。']
    tot = q(CONV_DB, 'SELECT COUNT(*) FROM conversations')
    msg = q(CONV_DB, 'SELECT COUNT(*) FROM messages')
    out.append('- 会话数 %s ｜ 消息数 %s' % (tot[0][0] if tot else '?', msg[0][0] if msg else '?'))
    for name, n in rows:
        out.append('- %s：未读 %d 条' % (name, n or 0))
    return out


def section_week():
    out = ['', '## 四、本周（近 7 天）新增']
    mem = q(MEM_DB, 'SELECT COUNT(*) FROM memories WHERE created_at >= ?', (SINCE,))
    mems = q(MEM_DB, 'SELECT type, COUNT(*) FROM memories WHERE created_at >= ? GROUP BY type', (SINCE,))
    out.append('- 新增记忆：%s 条%s' % (mem[0][0] if mem else '?',
               ('（' + '｜'.join('%s=%d' % r for r in mems) + '）') if mems else ''))
    tk = q(TASKS_DB, 'SELECT COUNT(*) FROM tasks WHERE created_at >= ?', (SINCE,))
    out.append('- 新增任务（任务中心）：%s 条' % (tk[0][0] if tk else '?'))
    kb = q(KANBAN_DB, 'SELECT COUNT(*) FROM tasks WHERE created_at >= ?', (SINCE,))
    out.append('- 新增任务（看板）：%s 条' % (kb[0][0] if kb else '?'))
    return out


def section_cost(full=True):
    """本周花费估算 + 分布 Top5。

    口径说明（重要）：usage_log.prompt_tokens 是上游返回的**输入总量**，其中命中缓存的部分在 DeepSeek
    侧单价低两个数量级；上游响应未带缓存字段时无法拆分，故此处 est_cost 是**上界估算**（宁可高估不高估漏）。
    """
    out = ['', '## 五、本周花费（估算，上界口径）']
    rows = q(CONV_DB, """SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0),
                                COALESCE(SUM(cache_read_tokens),0), COALESCE(SUM(est_cost),0),
                                COALESCE(SUM(est_cost_usd),0), COALESCE(SUM(estimated),0)
                         FROM usage_log WHERE ts >= ?""", (SINCE,))
    if rows is None:
        return out + ['- 本次未能读取用量表。']
    n, pt, ct, crt, cny, usd, est = rows[0]
    if not n:
        return out + ['- 近 7 天没有记录到任何 Agent 调用（usage_log 无新行）。']
    out.append('- 调用 %d 次 ｜ 输入 %s tokens ｜ 输出 %s tokens ｜ 缓存命中 %s tokens' % (n, format(pt, ','), format(ct, ','), format(crt, ',')))
    out.append('- 估算花费：**¥%.4f**（$%.4f）｜其中按字符估算的调用 %d 次' % (cny, usd, est))
    out.append('- 单价口径：' + PRICE_NOTE)
    if full:
        for title, key, col in (('按 Agent', 'agent_id', 'Agent'), ('按成员', 'actor', '成员')):
            if key == 'actor':   # 成员列显示用户名而非 UUID
                sql = """SELECT COALESCE(u.username, '(已删除成员)') AS k, COUNT(*), COALESCE(SUM(ul.est_cost),0)
                         FROM usage_log ul LEFT JOIN users u ON u.id = ul.actor
                         WHERE ul.ts >= ? GROUP BY k ORDER BY 3 DESC LIMIT 5"""
            else:
                sql = """SELECT COALESCE(agent_id,'(未知)') AS k, COUNT(*), COALESCE(SUM(est_cost),0)
                         FROM usage_log WHERE ts >= ? GROUP BY k ORDER BY 3 DESC LIMIT 5"""
            r = q(CONV_DB, sql, (SINCE,))
            if r:
                out += ['', '**%s Top5**' % title, '', '| %s | 次数 | 估算花费 |' % col, '|---|---|---|']
                for k, c, cost in r:
                    out.append('| %s | %d | ¥%.4f |' % (k, c, cost))
    return out


def section_balance():
    b = balance()
    out = ['', '## 六、DeepSeek 余额']
    if not b:
        return out + ['- 未找到 DEEPSEEK_API_KEY，未能查询余额。']
    if 'error' in b:
        return out + ['- 余额查询失败：%s' % b['error']]
    out.append('- 当前余额：**%s %s**（is_available=%s）' % (b.get('total'), b.get('currency'), b.get('available')))
    return out


def build(full=True):
    lines = ['# 值班数据快照 · %s' % NOW.strftime('%Y-%m-%d %H:%M'), '',
             '> 本文件由 ops/digest.py 自动生成：**纯脚本、0 次 LLM 调用**（不产生任何 token 费用）。',
             '> 需要「判断与建议」而非数字时，请看每周一 09:00 的《周报》（AI 版）。', '']
    if full:
        lines += section_kanban() + section_taskcenter() + section_unread() + section_week()
    lines += section_cost(full=full) + section_balance()
    lines += ['', '---',
              '*生成时间 %s ｜ 数据窗口：近 7 天（滚动）｜ 花费为估算上界，口径见上*' % NOW.strftime('%Y-%m-%d %H:%M:%S %z')]
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stdout', action='store_true', help='全文输出到 stdout')
    ap.add_argument('--cost-only', action='store_true', help='只输出本周花费段')
    ap.add_argument('--out-dir', default=NOTIFY)
    a = ap.parse_args()
    if a.cost_only:
        sys.stdout.write('\n'.join(section_cost(full=True)) + '\n')
        return 0
    text = build(full=True)
    if a.stdout:
        sys.stdout.write(text)
        return 0
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, '快照-%s.md' % DAY)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    sys.stdout.write('快照已生成：%s（%d 字节，0 次 LLM 调用）\n' % (path, len(text.encode())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
