#!/usr/bin/env bash
# CloudLoom DeepSeek 密钥轮换脚本（S4.0 / B2 密钥收敛）
#
# 用法：
#   bash /opt/team-console/ops/rotate-deepseek-key.sh --check      # 只体检：列出各文件密钥长度与指纹是否一致
#   bash /opt/team-console/ops/rotate-deepseek-key.sh <新密钥>      # 轮换：备份 -> 同步全部 .env -> 600 -> 重启单元 -> 核验
#
# 纪律承诺：
#   * 全程不回显密钥（只打印长度与 sha256 前 12 位指纹）
#   * 改前逐个备份到 /root/e2e/backups/<文件名>.bak-s40key-<时间戳>
#   * 保留原文件其它行不变，写后权限 600
#   * 轮换后自动复位凭据池 exhaustion（否则充值/换密钥后仍可能继续 402）
#   * 核验：各单元 ActiveState、本机 /api/health、DeepSeek 余额接口可用性
set -u
BACKUP_DIR=/root/e2e/backups
TS=$(date +%Y%m%d-%H%M%S)
TARGETS="/root/.hermes/.env /root/.hermes/profiles/cehua/.env /root/.hermes/profiles/chengxu/.env /root/.hermes/profiles/pingshen/.env /root/.hermes/profiles/testbot/.env /root/.hermes/profiles/zhiban/.env /etc/hermes.env"
UNITS="hermes-gateway-cehua hermes-gateway-chengxu hermes-gateway-pingshen hermes-gateway-zhiban"
PROFILES="cehua chengxu pingshen testbot zhiban"

fp() { printf "%s" "$1" | sha256sum | cut -c1-12; }

read_key() {
  local f="$1"
  [ -f "$f" ] || { echo ""; return; }
  sed -n "s@^DEEPSEEK_API_KEY=@@p" "$f" | head -1 | tr -d "\r"
}

if [ "${1:---check}" = "--check" ]; then
  echo "== 密钥一致性体检（只比长度与指纹，不回显密钥）=="
  for f in $TARGETS; do
    if [ ! -f "$f" ]; then echo "  (不存在)      $f"; continue; fi
    k=$(read_key "$f")
    if [ -z "$k" ]; then
      echo "  无该键        $f"
    else
      printf "  长度=%-3s 指纹=%s  %s\n" "${#k}" "$(fp "$k")" "$f"
    fi
  done
  exit 0
fi

KEY="$1"
case "$KEY" in
  sk-*) ;;
  *) echo "拒绝：密钥格式异常（应形如 sk- 开头）"; exit 2 ;;
esac
LEN=${#KEY}
if [ "$LEN" -lt 20 ]; then echo "拒绝：密钥长度异常（长度=$LEN）"; exit 2; fi
echo "== 轮换 DeepSeek 密钥（新密钥长度=$LEN 指纹=$(fp "$KEY")）=="
mkdir -p "$BACKUP_DIR"
changed=0

for f in $TARGETS; do
  if [ ! -f "$f" ]; then echo "  跳过（不存在）：$f"; continue; fi
  old=$(read_key "$f")
  if [ -n "$old" ] && [ "$old" = "$KEY" ]; then echo "  未变化（指纹一致）：$f"; continue; fi
  if ! cp -a "$f" "$BACKUP_DIR/$(basename "$f").bak-s40key-$TS"; then echo "  备份失败，终止：$f"; exit 3; fi
  if grep -q "^DEEPSEEK_API_KEY=" "$f"; then
    sed -i "s@^DEEPSEEK_API_KEY=.*@DEEPSEEK_API_KEY=$KEY@" "$f"
  else
    printf "\nDEEPSEEK_API_KEY=%s\n" "$KEY" >> "$f"
  fi
  chmod 600 "$f"
  new=$(read_key "$f")
  if [ "$new" = "$KEY" ]; then
    echo "  已更新：$f（权限 600，指纹=$(fp "$new")）"
    changed=$((changed + 1))
  else
    echo "  写入校验失败，终止：$f"; exit 4
  fi
done
echo "  本轮更新文件数=$changed  备份后缀=.bak-s40key-$TS"

echo "== 复位凭据池 exhaustion（换密钥后必须做，否则可能继续 402）=="
for p in $PROFILES; do
  out=$(hermes --profile "$p" auth reset deepseek 2>&1 | tail -1)
  echo "  $p: $out"
done

echo "== 重启 Hermes 网关单元 =="
for u in $UNITS; do
  if systemctl restart "$u"; then echo "  已重启：$u"; else echo "  重启失败：$u"; fi
done
sleep 3

echo "== 核验 =="
for u in $UNITS; do
  printf "  %-32s ActiveState=%s\n" "$u" "$(systemctl show -p ActiveState --value "$u")"
done
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/api/health)
echo "  本机 /api/health HTTP=$code"

echo "== DeepSeek 余额探测（用新密钥，仅输出结论）=="
KEY="$KEY" python3 - << "BALEOF"
import json
import os
import urllib.request
k = os.environ["KEY"]
req = urllib.request.Request("https://api.deepseek.com/user/balance",
                             headers={"Authorization": "Bearer " + k})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode())
    b = (d.get("balance_infos") or [{}])[0]
    print("  可用=" + str(d.get("is_available")) + "  total_balance=" + str(b.get("total_balance")) + " " + str(b.get("currency")))
except Exception as e:
    print("  探测失败：" + type(e).__name__ + " " + str(e)[:120])
BALEOF

echo "== 完成。真实会话验证：登录工作台发一条消息，或执行 ops 目录外的核验脚本 =="
