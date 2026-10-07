#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CloudLoom 运维看门狗（S4.0 / B1）

沉默即正常：正常时零输出、不产生任何文件。仅在有异常时往工作台通知目录写一份 markdown，
前端通知流（GET /api/poll，8 秒轮询）会自动读到并在工作台展示。

检查项：
  a) zhiban 定时作业：executions.db 近 6 小时 failed / running 卡住 + jobs.json last_status + 凭据池 exhaustion
  b) DeepSeek 余额（默认阈值 5 元，可用环境变量 OPS_BALANCE_THRESHOLD 覆盖）
  c) 关键 systemd 单元 active 且未触发 start-limit-hit
  d) 关键端口监听（80/443/3000/8787/8642-8645）
  e) 本机 http://127.0.0.1:8787/api/health 返回 200
  f) 根分区使用率超过 85%

调度：systemd timer（ops-check.timer，每 15 分钟），不依赖 Hermes、不调用 LLM、只用标准库。
去重：.ops-check-state.json —— 同一问题 6 小时内只告警一次；问题恢复后自动清状态（复发可立即再告警）。
退出码：0 = 本轮无新告警（含"有异常但已被去重"）；1 = 本轮写入了新告警。
"""

import datetime
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import urllib.request

OPS_DIR = "/opt/team-console/ops"
STATE_FILE = os.path.join(OPS_DIR, ".ops-check-state.json")
NOTIFY_DIR = "/root/team-files/系统通知"
HERMES_DIR = "/root/.hermes"
ROOT_ENV = os.path.join(HERMES_DIR, ".env")
ZHIBAN = os.path.join(HERMES_DIR, "profiles", "zhiban")
JOBS_FILE = os.path.join(ZHIBAN, "cron", "jobs.json")
EXEC_DB = os.path.join(ZHIBAN, "cron", "executions.db")
AUTH_FILES = [os.path.join(ZHIBAN, "auth.json")]

UNITS = [
    "team-console.service",
    "caddy.service",
    "hermes-gateway-cehua.service",
    "hermes-gateway-chengxu.service",
    "hermes-gateway-pingshen.service",
    "hermes-gateway-zhiban.service",
]
PORTS = [80, 443, 3000, 8787, 8642, 8643, 8644, 8645]
HEALTH_URL = "http://127.0.0.1:8787/api/health"
DISK_MOUNT = "/"
DISK_MAX_PCT = 85.0
CRON_WINDOW_H = 6
STUCK_H = 2
DEDUP_H = 6
BALANCE_MIN = float(os.environ.get("OPS_BALANCE_THRESHOLD", "5"))
VERBOSE = ("--verbose" in sys.argv) or ("-v" in sys.argv)

OK_STATUSES = ("ok", "success", "completed", "scheduled", "running")
Q = chr(34)
S = chr(39)
NL = chr(10)


def now():
    return datetime.datetime.now().astimezone()


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def issue(key, title, detail, action):
    return {"key": key, "title": title, "detail": detail, "action": action}


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def read_env_key(path, name):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith(name + "="):
                    v = line.split("=", 1)[1].strip()
                    return v.strip(Q).strip(S)
    except Exception:
        return None
    return None


def check_cron():
    out = []
    jobs = []
    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            doc = json.load(f)
        jobs = doc.get("jobs", []) if isinstance(doc, dict) else doc
    except Exception as e:
        out.append(issue("cron:jobs-unreadable", "定时作业清单不可读",
                         JOBS_FILE + " 读取失败：" + type(e).__name__ + " " + str(e)[:150],
                         "检查 zhiban profile 的 cron 目录与文件权限"))
    names = {}
    for j in jobs:
        jid = str(j.get("id", "?"))
        names[jid] = str(j.get("name", jid))
        st = j.get("last_status")
        if st and str(st) not in OK_STATUSES:
            out.append(issue("cron:job:" + jid, "定时作业失败：" + names[jid] + "（" + jid + "）",
                             "last_status=" + str(st) + "  last_run_at=" + str(j.get("last_run_at")) +
                             NL + "错误：" + str(j.get("last_error")) +
                             NL + "下次触发：" + str(j.get("next_run_at")) + "  计划：" + str(j.get("schedule_display")),
                             "先看 journalctl -u hermes-gateway-zhiban -n 100；若是 402 Insufficient Balance 则 "
                             "hermes --profile zhiban auth reset deepseek 后手动触发一次验证"))
        if j.get("enabled") and j.get("state") == "paused":
            out.append(issue("cron:paused:" + jid, "定时作业被暂停：" + names[jid],
                             "state=paused paused_at=" + str(j.get("paused_at")) + " reason=" + str(j.get("paused_reason")),
                             "确认为人为暂停；不是则恢复该作业"))
    try:
        con = sqlite3.connect(EXEC_DB)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT id, job_id, status, claimed_at, started_at, finished_at, error "
                           "FROM executions ORDER BY rowid DESC LIMIT 200").fetchall()
        con.close()
    except Exception as e:
        out.append(issue("cron:db-unreadable", "作业执行库不可读",
                         EXEC_DB + " 读取失败：" + type(e).__name__ + " " + str(e)[:150], "检查文件权限"))
        return out
    t0 = now()
    cutoff = t0 - datetime.timedelta(hours=CRON_WINDOW_H)
    for r in rows:
        st = str(r["status"])
        jid = str(r["job_id"])
        label = names.get(jid, jid)
        if st == "failed":
            t = parse_iso(r["finished_at"]) or parse_iso(r["started_at"]) or parse_iso(r["claimed_at"])
            if t and t.astimezone() >= cutoff:
                out.append(issue("cron:exec-failed:" + jid,
                                 "近 " + str(CRON_WINDOW_H) + " 小时作业执行失败：" + label + "（" + jid + "）",
                                 "执行 id=" + str(r["id"]) + "  时间=" + fmt(t) + NL + "错误：" + str(r["error"]),
                                 "按错误定位；402 余额类需 hermes --profile zhiban auth reset deepseek"))
        elif st == "running":
            t = parse_iso(r["started_at"]) or parse_iso(r["claimed_at"])
            if t and (t0 - t.astimezone()) > datetime.timedelta(hours=STUCK_H):
                out.append(issue("cron:exec-stuck:" + str(r["id"]),
                                 "作业执行超 " + str(STUCK_H) + " 小时仍为 running：" + label,
                                 "执行 id=" + str(r["id"]) + "  开始=" + fmt(t),
                                 "确认 gateway 是否卡死：systemctl restart hermes-gateway-zhiban"))
    for af in AUTH_FILES:
        try:
            with open(af, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except Exception:
            continue
        pool = doc.get("credential_pool") or {}
        for prov, lst in pool.items():
            for e in (lst or []):
                if str(e.get("last_status")) == "exhausted":
                    out.append(issue("cred:exhausted:" + str(prov) + ":" + str(e.get("id")),
                                     "推理凭据被标记耗尽：" + str(prov) + "（" + str(e.get("id")) + "）",
                                     "last_error=" + str(e.get("last_error_code")) + " " + str(e.get("last_error_message")) +
                                     NL + "来源=" + str(e.get("source")) + "  标记时间=" + str(e.get("last_status_at")) +
                                     NL + "reset_at=" + str(e.get("last_error_reset_at")),
                                     "余额已恢复仍报 402 时必须显式复位：hermes --profile zhiban auth reset " + str(prov)))
    return out


def check_balance():
    key = read_env_key(ROOT_ENV, "DEEPSEEK_API_KEY")
    if not key:
        return [issue("balance:nokey", "未找到 DEEPSEEK_API_KEY",
                      ROOT_ENV + " 中没有该键（脚本不回显密钥值）",
                      "按《部署前置清单-管理员操作》写入密钥，权限 600")]
    req = urllib.request.Request("https://api.deepseek.com/user/balance",
                                 headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            doc = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return [issue("balance:api-error", "DeepSeek 余额查询失败",
                      type(e).__name__ + ": " + str(e)[:180] + NL + "（密钥有效性与出网连通性无法确认）",
                      "确认服务器出网与密钥有效性；必要时执行 ops/rotate-deepseek-key.sh")]
    infos = doc.get("balance_infos") or [{}]
    inf = infos[0] if infos else {}
    total = inf.get("total_balance")
    cur = inf.get("currency")
    out = []
    try:
        val = float(total)
    except Exception:
        val = None
    if val is not None and val < BALANCE_MIN:
        out.append(issue("balance:low", "DeepSeek 余额低于阈值 " + str(BALANCE_MIN),
                         "当前余额=" + str(total) + " " + str(cur) + "  is_available=" + str(doc.get("is_available")),
                         "尽快充值，否则定时作业与 Agent 对话会 402 失败"))
    if doc.get("is_available") is False:
        out.append(issue("balance:unavailable", "DeepSeek 账户不可用",
                         "is_available=false 余额=" + str(total) + " " + str(cur), "检查账户状态与充值"))
    return out


def unit_props(u):
    try:
        p = subprocess.run(["systemctl", "show", "-p",
                            "ActiveState,SubState,UnitFileState,NRestarts,Result", u],
                           capture_output=True, text=True, timeout=15)
    except Exception:
        return None
    props = {}
    for line in (p.stdout or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            props[k.strip()] = v.strip()
    return props or None


def check_units():
    out = []
    for u in UNITS:
        props = unit_props(u)
        if not props:
            out.append(issue("unit:missing:" + u, "关键单元不存在或无法查询：" + u,
                             "systemctl show 无输出", "确认单元文件是否存在：systemctl status " + u))
            continue
        active = props.get("ActiveState")
        sub = props.get("SubState")
        bad = (active != "active") or (sub in ("start-limit-hit", "failed", "dead"))
        if bad:
            extra = ""
            if sub == "start-limit-hit" or props.get("Result") == "start-limit-hit":
                extra = NL + "注意：已触发 systemd 启动频率限制（start-limit-hit）"
            out.append(issue("unit:down:" + u, "关键单元未运行：" + u,
                             "ActiveState=" + str(active) + " SubState=" + str(sub) +
                             " UnitFileState=" + str(props.get("UnitFileState")) +
                             " Result=" + str(props.get("Result")) + " NRestarts=" + str(props.get("NRestarts")) + extra,
                             "systemctl status " + u + "；需要时 systemctl reset-failed " + u + " && systemctl restart " + u))
        elif props.get("UnitFileState") == "disabled":
            out.append(issue("unit:notenabled:" + u, "关键单元未设为开机自启：" + u,
                             "UnitFileState=disabled（当前 ActiveState=active）",
                             "systemctl enable " + u))
    return out


def listening_ports():
    ports = set()
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except Exception:
            continue
        for line in lines[1:]:
            cols = line.split()
            if len(cols) < 4 or cols[3] != "0A":
                continue
            try:
                ports.add(int(cols[1].split(":")[1], 16))
            except Exception:
                continue
    return ports


def check_ports():
    have = listening_ports()
    if not have:
        return [issue("ports:unknown", "端口监听状态无法读取",
                      "/proc/net/tcp 解析为空", "确认 /proc 可读；否则改为 systemctl 检查")]
    missing = [p for p in PORTS if p not in have]
    if missing:
        return [issue("ports:missing", "关键端口未监听",
                      "缺失端口：" + ", ".join(str(p) for p in missing) +
                      NL + "当前监听（并集）：" + ", ".join(str(p) for p in sorted(have)),
                      "按端口归属查单元：80/443=Caddy，3000/8787=team-console，8642-8645=预设 Hermes 网关")]
    return []


def check_health():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=10) as r:
            code = r.status
            body = r.read().decode("utf-8", "replace")[:200]
    except Exception as e:
        return [issue("health:down", "本机健康检查失败",
                      HEALTH_URL + " 请求异常 " + type(e).__name__ + ": " + str(e)[:160],
                      "systemctl status team-console；journalctl -u team-console -n 100")]
    if code != 200:
        return [issue("health:code", "本机健康检查非 200",
                      "HTTP " + str(code) + " 响应=" + body, "查 journalctl -u team-console -n 100")]
    return []


def check_disk():
    try:
        u = shutil.disk_usage(DISK_MOUNT)
    except Exception as e:
        return [issue("disk:unreadable", "磁盘用量无法读取", type(e).__name__, "检查挂载点 " + DISK_MOUNT)]
    pct = u.used * 100.0 / u.total
    if pct > DISK_MAX_PCT:
        return [issue("disk:root", "根分区使用率超过 " + str(DISK_MAX_PCT) + "%",
                      "已用 %.1f%%（%.1fG / %.1fG）" % (pct, u.used / 1073741824.0, u.total / 1073741824.0),
                      "清理产出与日志：journalctl --vacuum-size=200M；检查 /root/team-files/产出 与 /root/e2e")]
    return []


CHECKS = [("cron", check_cron), ("balance", check_balance), ("units", check_units),
          ("ports", check_ports), ("health", check_health), ("disk", check_disk)]


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("issues"), dict):
            return d
    except Exception:
        pass
    return {"version": 1, "issues": {}}


def save_state(state):
    state["version"] = 1
    state["last_run"] = fmt(now())
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, STATE_FILE)


def write_alert(items, t, suppressed):
    os.makedirs(NOTIFY_DIR, exist_ok=True)
    path = os.path.join(NOTIFY_DIR, "运维告警-" + t.strftime("%Y%m%d-%H%M") + ".md")
    lines = []
    lines.append("# 运维告警 " + t.strftime("%Y-%m-%d %H:%M"))
    lines.append("")
    lines.append("共 " + str(len(items)) + " 项异常（另有 " + str(suppressed) + " 项在 " +
                 str(DEDUP_H) + " 小时去重窗口内，本次不重复列出）。")
    lines.append("")
    lines.append("> 本文件由 ops-check 看门狗自动生成；系统正常时不会产生本文件，问题恢复后去重状态自动清除。")
    lines.append("")
    for i, it in enumerate(items, 1):
        lines.append("## " + str(i) + ". " + it["title"])
        lines.append("")
        lines.append("- 检查项：" + it["key"])
        lines.append("- 现象与证据：")
        detail_lines = str(it["detail"]).splitlines()
        if not detail_lines:
            detail_lines = ["（无）"]
        for dl in detail_lines:
            lines.append("  - " + dl)
        lines.append("- 建议动作：" + it["action"])
        lines.append("")
    lines.append("---")
    lines.append("生成时间：" + fmt(t) + "  主机：" + socket.gethostname() + "  调度：ops-check.timer（每 15 分钟）")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(NL.join(lines) + NL)
    os.replace(tmp, path)
    return path


def send_alert_mail(path, items, t):
    """S4.1 / C6-4：站外通道——出现新告警时同时发一封邮件（无新告警不会走到这里）。"""
    try:
        subject = "[运维告警] " + t.strftime("%Y-%m-%d %H:%M") + " 共 " + str(len(items)) + " 项"
        body = ["CloudLoom 看门狗发现 " + str(len(items)) + " 项新异常：", ""]
        for i, it in enumerate(items, 1):
            body.append(str(i) + ". " + it["title"])
            body.append("   检查项：" + it["key"])
            body.append("   建议动作：" + it["action"])
        body.append("")
        body.append("完整证据见附件：" + os.path.basename(path))
        body.append("（本邮件由 ops-check 看门狗自动发出，仅在出现新告警时发送。）")
        bf = path + ".mailbody.tmp"
        with open(bf, "w", encoding="utf-8") as f:
            f.write(NL.join(body) + NL)
        r = subprocess.run(["/usr/bin/python3", os.path.join(OPS_DIR, "mail.py"),
                            "--subject", subject, "--body-file", bf, "--attach", path],
                           capture_output=True, text=True, timeout=60)
        os.remove(bf)
        if r.returncode == 0:
            print("[ops-check] 告警邮件已发出：" + (r.stdout or "").strip())
        else:
            print("[ops-check] 告警邮件发送失败（不影响看门狗）：" + (r.stderr or "").strip()[:200], file=sys.stderr)
    except Exception as e:
        print("[ops-check] 告警邮件异常（不影响看门狗）：" + type(e).__name__ + " " + str(e)[:160], file=sys.stderr)


def main():
    all_issues = []
    for name, fn in CHECKS:
        try:
            all_issues.extend(fn())
        except Exception as e:
            all_issues.append(issue("check-error:" + name, "检查项自身异常：" + name,
                                    type(e).__name__ + ": " + str(e)[:200],
                                    "看门狗的该检查项需要修复"))
    state = load_state()
    recs = state["issues"]
    t = now()
    fresh = []
    suppressed = 0
    present = set()
    for it in all_issues:
        k = it["key"]
        present.add(k)
        rec = recs.get(k)
        if rec:
            last = parse_iso(rec.get("last_alert"))
            if last and (t - last.astimezone()) < datetime.timedelta(hours=DEDUP_H):
                rec["last_seen"] = fmt(t)
                suppressed += 1
                continue
            rec["count"] = int(rec.get("count", 1)) + 1
            rec["last_alert"] = fmt(t)
            rec["last_seen"] = fmt(t)
        else:
            recs[k] = {"first_seen": fmt(t), "last_alert": fmt(t), "last_seen": fmt(t), "count": 1}
        fresh.append(it)
    for k in list(recs.keys()):
        if k not in present:
            del recs[k]
    if fresh:
        path = write_alert(fresh, t, suppressed)
        send_alert_mail(path, fresh, t)
        print("[ops-check] 新告警 " + str(len(fresh)) + " 项（去重静默 " + str(suppressed) + " 项），已写入 " + path)
        for it in fresh:
            print("[ops-check]   - " + it["title"])
    elif VERBOSE:
        print("[ops-check] 本轮无新告警（去重静默 " + str(suppressed) + " 项）")
    if VERBOSE:
        for it in all_issues:
            print("[verbose] " + it["key"] + "  ::  " + it["title"])
        if not all_issues:
            print("[verbose] 全部检查项正常")
    save_state(state)
    return 1 if fresh else 0


if __name__ == "__main__":
    sys.exit(main())
