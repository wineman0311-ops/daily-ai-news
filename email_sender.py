#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Email 發送模組
將每週 AI 快報轉換為 HTML 郵件，透過公司 SMTP 伺服器發送給全體同仁。

必要環境變數：
  EMAIL_HOST       - SMTP 伺服器位址（如 mail.company.com）
  EMAIL_PORT       - SMTP 埠號（587 = STARTTLS，465 = SSL，25 = 無加密）
  EMAIL_USER       - 登入帳號（通常是完整 email 地址）
  EMAIL_PASSWORD   - 登入密碼
  EMAIL_FROM       - 寄件人名稱與地址（如 "AI 快報小秘書 <bot@company.com>"）
  EMAIL_RECIPIENTS - 收件人清單，逗號分隔（如 "a@co.com,b@co.com"）

可選環境變數：
  EMAIL_USE_TLS    - 是否啟用 STARTTLS（預設 true，建議保留）
  EMAIL_USE_SSL    - 是否使用 SSL（埠 465 時設 true，預設 false）
  EMAIL_SUBJECT_PREFIX - 郵件主旨前綴（預設 "【AI 週報】"）
"""

import os
import re
import smtplib
import html as html_lib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from datetime             import datetime
from pathlib              import Path


# ── 載入 .env（本地開發用）────────────────────────────────────
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()


# ── 設定 ─────────────────────────────────────────────────────
def _cfg(key, default=""):
    return os.environ.get(key, default).strip()

EMAIL_HOST       = _cfg("EMAIL_HOST")
EMAIL_PORT       = int(_cfg("EMAIL_PORT", "587"))
EMAIL_USER       = _cfg("EMAIL_USER")
EMAIL_PASSWORD   = _cfg("EMAIL_PASSWORD")
EMAIL_FROM       = _cfg("EMAIL_FROM") or EMAIL_USER
EMAIL_USE_TLS    = _cfg("EMAIL_USE_TLS",  "true").lower()  != "false"
EMAIL_USE_SSL    = _cfg("EMAIL_USE_SSL",  "false").lower() == "true"
SUBJECT_PREFIX   = _cfg("EMAIL_SUBJECT_PREFIX", "【AI 週報】")

_raw_recipients  = _cfg("EMAIL_RECIPIENTS", "")
EMAIL_RECIPIENTS = [r.strip() for r in _raw_recipients.split(",") if r.strip()]


# ═════════════════════════════════════════════════════════════
# Telegram HTML → Email HTML 轉換
# ═════════════════════════════════════════════════════════════

def _tg_to_email_html(tg_text: str) -> str:
    """
    將 Telegram HTML 格式的報告轉為適合 Email 的完整 HTML 文件。
    Telegram 支援：<b> <i> <a href="..."> <code> <pre>
    """
    t = tg_text

    # 將 ─── 分隔線換成 <hr>
    t = re.sub(r"─{3,}", "<hr>", t)

    # 換行轉 <br>
    t = t.replace("\n", "<br>\n")

    # Emoji 章節標題加大（🚀 🔥 💡 開頭的行）
    t = re.sub(
        r"(<br>\n)(([🚀🔥💡🆕📌⏰✅❌⚠️])[^\n<]*<b>[^<]+</b>)",
        r"\1<div class='section-title'>\2</div>",
        t,
    )

    now   = datetime.now()
    year  = now.year
    month = now.month
    date  = now.strftime("%Y/%m/%d")

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每週 AI 快報 {date}</title>
</head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft JhengHei',sans-serif;">

<!-- Wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F1F5F9;padding:32px 0;">
<tr><td align="center">

  <!-- Card -->
  <table width="620" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:620px;width:100%;">

    <!-- Header -->
    <tr>
      <td style="background:linear-gradient(135deg,#1E293B 0%,#0F172A 60%,#1E1B4B 100%);padding:36px 40px 32px;text-align:center;">
        <div style="font-size:13px;font-weight:600;color:#93C5FD;letter-spacing:1px;margin-bottom:12px;">
          🤖 &nbsp;每週 AI 快報小秘書
        </div>
        <div style="font-size:28px;font-weight:800;color:#FFFFFF;line-height:1.3;margin-bottom:8px;">
          {year}年{month}月 AI 週報
        </div>
        <div style="font-size:14px;color:#94A3B8;">
          {date} · 每週一自動發送
        </div>
      </td>
    </tr>

    <!-- Body -->
    <tr>
      <td style="padding:32px 40px 24px;">
        <div style="
          font-size:15px;
          line-height:1.8;
          color:#334155;
        ">
          <!-- 報告內容 -->
          <style>
            .section-title {{
              font-size:17px;
              font-weight:800;
              color:#0F172A;
              margin:24px 0 10px;
            }}
            hr {{
              border:none;
              border-top:1px solid #E2E8F0;
              margin:20px 0;
            }}
            a {{
              color:#2563EB;
              text-decoration:none;
            }}
            code {{
              background:#F1F5F9;
              color:#7C3AED;
              font-family:monospace;
              padding:2px 6px;
              border-radius:4px;
              font-size:13px;
            }}
          </style>
          {t}
        </div>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="background:#F8FAFC;border-top:1px solid #E2E8F0;padding:20px 40px;text-align:center;">
        <div style="font-size:12px;color:#94A3B8;line-height:1.7;">
          此郵件由 AI 快報 Bot 每週一自動發送 · 如不想收到請聯絡管理員
          <br>
          資料來源：Reddit · Product Hunt · 機器之心 · 量子位
        </div>
      </td>
    </tr>

  </table>
  <!-- /Card -->

</td></tr>
</table>
<!-- /Wrapper -->

</body>
</html>"""
    return html


# ═════════════════════════════════════════════════════════════
# SMTP 發送
# ═════════════════════════════════════════════════════════════

def send_weekly_report(report_text: str) -> bool:
    """
    將 Telegram HTML 格式的報告轉為 HTML 郵件，
    透過公司 SMTP 發送給 EMAIL_RECIPIENTS 中的所有人。

    回傳 True 表示成功，False 表示設定不足或發送失敗。
    """
    # 檢查設定是否完整
    missing = [k for k, v in [
        ("EMAIL_HOST",       EMAIL_HOST),
        ("EMAIL_USER",       EMAIL_USER),
        ("EMAIL_PASSWORD",   EMAIL_PASSWORD),
        ("EMAIL_RECIPIENTS", _raw_recipients),
    ] if not v]

    if missing:
        print(f"  ⚠️ Email 未設定（缺少：{', '.join(missing)}），略過發送", flush=True)
        return False

    if not EMAIL_RECIPIENTS:
        print("  ⚠️ EMAIL_RECIPIENTS 為空，略過發送", flush=True)
        return False

    # 組建郵件
    now     = datetime.now()
    subject = f"{SUBJECT_PREFIX}{now.strftime('%Y/%m/%d')} AI 產業趨勢週報"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = ", ".join(EMAIL_RECIPIENTS)

    # 純文字版本（fallback）
    plain = re.sub(r"<[^>]+>", "", report_text)
    msg.attach(MIMEText(plain, "plain", "utf-8"))

    # HTML 版本
    email_html = _tg_to_email_html(report_text)
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    # 發送
    try:
        print(f"  📧 Email 發送中（{len(EMAIL_RECIPIENTS)} 位收件人，"
              f"SMTP {EMAIL_HOST}:{EMAIL_PORT}）...", flush=True)

        if EMAIL_USE_SSL:
            server = smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, timeout=30)
        else:
            server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=30)
            if EMAIL_USE_TLS:
                server.starttls()

        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_RECIPIENTS, msg.as_string())
        server.quit()

        print(f"  ✅ Email 發送成功 → {', '.join(EMAIL_RECIPIENTS)}", flush=True)
        return True

    except smtplib.SMTPAuthenticationError:
        print("  ❌ Email 發送失敗：帳號或密碼錯誤", flush=True)
    except smtplib.SMTPConnectError:
        print(f"  ❌ Email 發送失敗：無法連線至 {EMAIL_HOST}:{EMAIL_PORT}", flush=True)
    except Exception as e:
        print(f"  ❌ Email 發送失敗：{e}", flush=True)

    return False


def is_configured() -> bool:
    """檢查 Email 設定是否完整（用於啟動時印出狀態）"""
    return bool(EMAIL_HOST and EMAIL_USER and EMAIL_PASSWORD and EMAIL_RECIPIENTS)
