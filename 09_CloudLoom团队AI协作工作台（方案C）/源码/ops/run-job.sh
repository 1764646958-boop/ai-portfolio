#!/bin/bash
# S4.1 / C1：按需触发入口 ——「想看就点一下，不点不花钱」
# 背景：作业改周报制后（每周 1 次 LLM），日常不再有 LLM 定时作业；需要即时判断时用本脚本手动触发一次。
# 三个动作：
#   weekly  —— 立即跑一次《周报（含上周复盘）》（LLM 作业，会产生 token 花费）
#   profile —— 立即生成一次成员画像 JSON（LLM 作业，已取消定时，仅按需触发）
#   digest  —— 生成数据快照（纯脚本，0 token，随时可跑）
# 用法：  bash /opt/team-console/ops/run-job.sh <weekly|profile|digest>
set -u
HERMES=/usr/local/bin/hermes
WEEKLY_JOB=44cf46376cff
PROFILE_JOB=367f1c9db36f
case "${1:-}" in
  weekly)
    echo "[run-job] 触发《周报（含上周复盘）》…（LLM 作业：会产生 token 花费）"
    "$HERMES" --profile zhiban cron run "$WEEKLY_JOB"
    ;;
  profile)
    # 画像已取消定时（不再有 next_run），按需路径**独立于 cron**：直接执行提示词文件一次。
    # 与 cron 执行同源（同一 profile、同一提示词文本），但不再有任何排程。
    echo "[run-job] 按需生成成员画像…（LLM 作业：会产生 token 花费）"
    "$HERMES" --profile zhiban -z "$(cat /opt/team-console/ops/on-demand/画像.md)" --usage-file /tmp/run-job-profile-usage.json
    echo "[run-job] 本次用量（tokens）："
    /usr/bin/python3 -c "import json;d=json.load(open('/tmp/run-job-profile-usage.json'));print(' ', json.dumps(d, ensure_ascii=False)[:400])" 2>/dev/null || echo "  （用量文件不可读）"
    rm -f /tmp/run-job-profile-usage.json
    ;;
  digest)
    echo "[run-job] 生成数据快照（纯脚本，0 token）…"
    /usr/bin/python3 /opt/team-console/ops/digest.py
    ;;
  *)
    echo "用法: bash $0 <weekly|profile|digest>"
    echo "  weekly  = 立即生成一次周报（LLM，有花费）"
    echo "  profile = 立即生成一次成员画像（LLM，有花费；已取消每日定时）"
    echo "  digest  = 生成数据快照（0 token，无花费）"
    exit 2
    ;;
esac
