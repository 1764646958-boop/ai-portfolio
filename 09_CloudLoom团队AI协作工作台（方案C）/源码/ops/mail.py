#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CloudLoom 出站邮件助手（S4.1）
用途：cron/看门狗/周报需要「写文件 + 发邮件」双通道时，统一走这里。
      纯出站 SMTP_SSL，复用 /root/.hermes/.env 中既有凭据，不新增配置、不打印密钥。
用法：
    mail.py --subject "主题" --body "正文"
    mail.py --subject "主题" --body-file 路径 [--attach 文件]...
默认收件人 = EMAIL_ADDRESS（负责人邮箱）；可用 --to 覆盖。
退出码：0 成功；1 失败（stderr 打印原因，不回显凭据）。
"""
import argparse, os, smtplib, sys
from email.message import EmailMessage
from email.utils import formataddr, formatdate

ENV = '/root/.hermes/.env'


def env(name):
    try:
        for line in open(ENV, encoding='utf-8'):
            s = line.strip()
            if s.startswith(name + '='):
                return s.split('=', 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        return None
    return None


def mask(a):
    if not a or '@' not in a:
        return '***'
    n, d = a.split('@', 1)
    return (n[:2] + '***@' + d) if len(n) > 2 else ('***@' + d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--subject', required=True)
    ap.add_argument('--body', default='')
    ap.add_argument('--body-file')
    ap.add_argument('--attach', action='append', default=[])
    ap.add_argument('--to')
    args = ap.parse_args()

    host = env('EMAIL_SMTP_HOST'); port = int(env('EMAIL_SMTP_PORT') or 465)
    user = env('EMAIL_ADDRESS'); pw = env('EMAIL_PASSWORD')
    to = args.to or user
    if not (host and user and pw):
        print('邮件未发送：/root/.hermes/.env 缺少 SMTP 配置', file=sys.stderr)
        return 1

    body = args.body
    if args.body_file:
        body = open(args.body_file, encoding='utf-8').read()

    m = EmailMessage()
    m['From'] = formataddr(('CloudLoom 值班台', user))
    m['To'] = to
    m['Subject'] = args.subject
    m['Date'] = formatdate(localtime=True)
    m.set_content(body or '(无正文)')
    for fp in args.attach:
        with open(fp, 'rb') as f:
            data = f.read()
        m.add_attachment(data, maintype='application', subtype='octet-stream',
                         filename=os.path.basename(fp))
    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as c:
            c.login(user, pw)
            c.send_message(m)
    except Exception as e:
        print('邮件发送失败：%s %s' % (type(e).__name__, str(e)[:160]), file=sys.stderr)
        return 1
    print('邮件已发送 → %s ｜ 主题：%s ｜ 正文 %d 字 ｜ 附件 %d 个'
          % (mask(to), args.subject, len(body or ''), len(args.attach)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
