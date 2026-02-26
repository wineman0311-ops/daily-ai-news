"""
email_sender.py — 週報 Email 發送模組
透過公司 SMTP 伺服器將 Telegram 週報轉為 HTML Email 發送給全體同仁

環境變數（皆為選填，未設定則跳過 Email 功能）：
  EMAIL_HOST            SMTP 伺服器位址（e.g. smtp.company.com）
  EMAIL_PORT            SMTP port（預設 587）
  EMAIL_USER            SMTP 登入帳號
  EMAIL_PASSWORD        SMTP 登入密碼
  EMAIL_FROM            寄件人顯示名稱與地址（e.g. AI快報小秘書 <bot@company.com>）
  EMAIL_RECIPIENTS      收件人清單，以逗號分隔（e.g. all@company.com,hr@company.com）
  EMAIL_USE_TLS         是否使用 STARTTLS（預設 true）
  EMAIL_USE_SSL         是否使用 SSL（預設 false，與 TLS 二選一）
  EMAIL_SUBJECT_PREFIX  主旨前綴（預設 【AI 週報】）
"""

import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


# ── 設定讀取 ────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """檢查 Email 功能所需的最低環境變數是否已設定"""
    required = ["EMAIL_HOST", "EMAIL_USER", "EMAIL_PASSWORD", "EMAIL_FROM", "EMAIL_RECIPIENTS"]
    return all(os.getenv(k) for k in required)


def _get_config() -> dict:
    return {
        "host":       os.getenv("EMAIL_HOST", ""),
        "port":       int(os.getenv("EMAIL_PORT", "587")),
        "user":       os.getenv("EMAIL_USER", ""),
        "password":   os.getenv("EMAIL_PASSWORD", ""),
        "from_addr":  os.getenv("EMAIL_FROM", ""),
        "recipients": [r.strip() for r in os.getenv("EMAIL_RECIPIENTS", "").split(",") if r.strip()],
        "use_tls":    os.getenv("EMAIL_USE_TLS", "true").lower() == "true",
        "use_ssl":    os.getenv("EMAIL_USE_SSL", "false").lower() == "true",
        "subject_prefix": os.getenv("EMAIL_SUBJECT_PREFIX", "【AI 週報】"),
    }


# ── Telegram HTML → Email HTML 轉換 ─────────────────────────────────────────

def _tg_to_email_html(tg_text: str) -> str:
    """
    將 Telegram HTML 格式的週報轉換為完整的 HTML Email，
    包含漸層標題、研發精選工具區塊（合併）、深度觀察、頁尾。
    """
    now = datetime.now()
    date_str = now.strftime("%Y/%m/%d")
    month_str = now.strftime("%Y年%-m月")

    # ── 解析 Telegram 文字，拆出各段落 ──────────────────────────────────────
    lines = tg_text.strip().splitlines()

    core_lines   = []   # 核心動態
    tools_lines  = []   # 研發精選（原 Web + C++ 合併）
    insight_lines = []  # 深度觀察

    section = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # 偵測段落
        if "核心動態" in stripped or "產業核心" in stripped:
            section = "core"
            continue
        if any(k in stripped for k in ["本週精選", "Web 團隊", "C++ 團隊", "研發精選", "Web團隊", "C++團隊"]):
            section = "tools"
            continue
        if "深度觀察" in stripped:
            section = "insight"
            continue

        if section == "core":
            core_lines.append(stripped)
        elif section == "tools":
            tools_lines.append(stripped)
        elif section == "insight":
            insight_lines.append(stripped)

    # ── 把 Telegram <b>/<i>/<a> 轉為 email-safe HTML ────────────────────────
    def tg2html(text: str) -> str:
        # <b> → <strong>
        text = re.sub(r"<b>(.*?)</b>", r"<strong>\1</strong>", text, flags=re.DOTALL)
        # <i> → <em>
        text = re.sub(r"<i>(.*?)</i>", r"<em>\1</em>", text, flags=re.DOTALL)
        # <a href="...">text</a> → 保留（email client 支援）
        return text

    def render_lines_as_bullets(line_list: list[str]) -> str:
        """將文字行列表渲染為 HTML 段落列表"""
        html = ""
        for ln in line_list:
            ln = tg2html(ln)
            # 頂層標題（以 • 或 【 開頭）
            if ln.startswith("•") or ln.startswith("【"):
                html += f'<div class="trend-main">{ln.lstrip("•").strip()}</div>'
            # 子項目（以 – 或 - 開頭）
            elif ln.startswith("–") or ln.startswith("-"):
                html += f'<div class="trend-sub"><span>{ln.lstrip("–-").strip()}</span></div>'
            # 編號觀察（1. 2. 3.）
            elif re.match(r"^\d+\.", ln):
                html += f'<div class="insight-title">{ln}</div>'
            else:
                html += f'<p style="font-size:13.5px;color:#475569;line-height:1.7;margin:0 0 10px;">{ln}</p>'
        return html

    def render_tools(line_list: list[str]) -> str:
        """
        渲染研發精選工具區塊。
        解析格式：工具名稱 + 標籤 + 描述 + 連結，
        若解析失敗則 fallback 為純文字段落。
        """
        badge_map = {
            "立即可用": ('<span class="badge-use">立即可用</span>', "#16A34A"),
            "值得評估": ('<span class="badge-eval">值得評估</span>', "#D97706"),
            "持續觀察": ('<span class="badge-watch">持續觀察</span>', "#94A3B8"),
        }

        html = ""
        i = 0
        while i < len(line_list):
            ln = tg2html(line_list[i].strip())

            # 嘗試識別工具標題行（含標籤關鍵字）
            matched_badge = None
            matched_color = "#94A3B8"
            for key, (badge_html, color) in badge_map.items():
                if key in ln:
                    matched_badge = badge_html
                    matched_color = color
                    ln = ln.replace(key, "").replace("【", "").replace("】", "").strip()
                    break

            if matched_badge:
                desc_lines = []
                link_html = ""
                i += 1
                while i < len(line_list):
                    next_ln = tg2html(line_list[i].strip())
                    # 遇到下一個工具標題就停
                    if any(k in line_list[i] for k in badge_map):
                        break
                    if next_ln.startswith("🔗") or "http" in next_ln:
                        # 提取連結
                        url_match = re.search(r'href="([^"]+)"', next_ln)
                        link_text = re.sub(r"<[^>]+>", "", next_ln).replace("🔗", "").strip()
                        if url_match:
                            link_html = f'<div class="tool-link">🔗 <a href="{url_match.group(1)}" style="color:#2563EB;">{link_text}</a></div>'
                        else:
                            link_html = f'<div class="tool-link">{next_ln}</div>'
                    else:
                        desc_lines.append(next_ln)
                    i += 1

                desc_html = "".join(
                    f'<div class="tool-desc">{d}</div>' for d in desc_lines if d
                )
                html += f"""
        <div class="tool-item" style="border-left-color:{matched_color};">
          <div class="tool-name">{ln} {matched_badge}</div>
          {desc_html}
          {link_html}
        </div>"""
            else:
                # 非工具行，直接輸出
                html += f'<p style="font-size:13.5px;color:#475569;line-height:1.7;margin:0 0 8px;">{ln}</p>'
                i += 1

        return html

    # ── 組裝 HTML ─────────────────────────────────────────────────────────────
    core_html    = render_lines_as_bullets(core_lines)    if core_lines    else "<p style='color:#94A3B8;font-size:13px;'>（本週無核心動態資料）</p>"
    tools_html   = render_tools(tools_lines)              if tools_lines   else "<p style='color:#94A3B8;font-size:13px;'>（本週無工具資料）</p>"
    insight_html = render_lines_as_bullets(insight_lines) if insight_lines else "<p style='color:#94A3B8;font-size:13px;'>（本週無深度觀察）</p>"

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 週報 {date_str}</title>
</head>
<body style="margin:0;padding:0;background-color:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft JhengHei',Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#F1F5F9;padding:32px 0;">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" border="0"
       style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);max-width:620px;">

  <!-- ── 標題 Header ── -->
  <tr>
    <td style="background:linear-gradient(135deg,#1E293B 0%,#0F172A 60%,#1E1B4B 100%);
               padding:36px 40px 32px;text-align:center;">
      <div style="display:inline-block;background:rgba(59,130,246,.2);
                  border:1px solid rgba(59,130,246,.4);
                  color:#93C5FD;font-size:12px;font-weight:600;letter-spacing:.5px;
                  padding:3px 14px;border-radius:20px;margin-bottom:14px;">
        🤖 &nbsp;每週 AI 快報小秘書
      </div>
      <h1 style="color:#ffffff;font-size:26px;font-weight:800;
                 margin:0 0 8px;line-height:1.3;">
        {month_str} AI 週報
      </h1>
      <p style="color:#94A3B8;font-size:13px;margin:0;">
        {date_str} &nbsp;·&nbsp; 每週一自動發送
      </p>
    </td>
  </tr>

  <!-- ── 內文 ── -->
  <tr>
    <td style="padding:32px 40px 8px;">

      <!-- 引言 -->
      <p style="color:#64748B;font-size:14px;line-height:1.7;
                border-left:3px solid #E2E8F0;padding-left:12px;margin:0 0 24px;">
        這是本週最新 AI 發展趨勢與工具整理，由小秘書 Bot 從 Reddit、Product Hunt、機器之心、量子位自動收集，並透過 Claude AI 深度分析後發送。
      </p>

      <!-- 核心動態 -->
      <div style="display:flex;align-items:center;gap:10px;margin:24px 0 12px;">
        <span style="font-size:20px;">🚀</span>
        <span style="font-size:16px;font-weight:800;color:#0F172A;">
          {month_str}：本週 AI 產業核心動態
        </span>
      </div>
      <style>
        .trend-main{{font-size:14px;font-weight:700;color:#1E293B;margin-bottom:6px;padding-left:0;}}
        .trend-main::before{{content:"• ";color:#3B82F6;}}
        .trend-sub{{padding-left:18px;margin-bottom:5px;font-size:13.5px;color:#475569;line-height:1.65;}}
        .trend-sub::before{{content:"– ";color:#CBD5E1;}}
        .tool-item{{border-left:3px solid #E2E8F0;padding-left:12px;margin-bottom:16px;}}
        .tool-item:last-child{{margin-bottom:4px;}}
        .tool-name{{font-size:14px;font-weight:700;color:#0F172A;margin-bottom:5px;}}
        .tool-desc{{font-size:13px;color:#475569;line-height:1.6;margin-bottom:4px;}}
        .tool-link{{font-size:12px;color:#2563EB;margin-top:4px;}}
        .badge-use{{background:#DCFCE7;color:#15803D;font-size:10px;padding:1px 7px;
                    border-radius:8px;font-weight:700;margin-left:6px;}}
        .badge-eval{{background:#FEF9C3;color:#854D0E;font-size:10px;padding:1px 7px;
                     border-radius:8px;font-weight:700;margin-left:6px;}}
        .badge-watch{{background:#F1F5F9;color:#475569;font-size:10px;padding:1px 7px;
                      border-radius:8px;font-weight:700;margin-left:6px;}}
        .insight-title{{font-size:14px;font-weight:700;color:#0F172A;margin-bottom:5px;margin-top:12px;}}
      </style>
      {core_html}

      <!-- 分隔線 -->
      <hr style="border:none;border-top:1px dashed #E2E8F0;margin:20px 0;">

      <!-- 研發精選工具（合併） -->
      <div style="display:flex;align-items:center;gap:10px;margin:24px 0 14px;">
        <span style="font-size:20px;">🛠️</span>
        <span style="font-size:16px;font-weight:800;color:#0F172A;">本週研發精選工具</span>
      </div>
      <div style="border:1px solid #E2E8F0;border-radius:12px;padding:16px 16px 4px;">
        {tools_html}
      </div>

      <!-- 分隔線 -->
      <hr style="border:none;border-top:1px dashed #E2E8F0;margin:20px 0;">

      <!-- 深度觀察 -->
      <div style="display:flex;align-items:center;gap:10px;margin:24px 0 12px;">
        <span style="font-size:20px;">💡</span>
        <span style="font-size:16px;font-weight:800;color:#0F172A;">深度觀察：對我們團隊的影響</span>
      </div>
      {insight_html}

      <hr style="border:none;border-top:1px dashed #E2E8F0;margin:20px 0;">
      <p style="font-size:12px;color:#94A3B8;text-align:right;margin:0 0 24px;">
        ⏰ 週報發送時間：{date_str}（每週一）
      </p>

    </td>
  </tr>

  <!-- ── 頁尾 ── -->
  <tr>
    <td style="background:#F8FAFC;border-top:1px solid #E2E8F0;
               padding:20px 40px;text-align:center;
               font-size:12px;color:#94A3B8;line-height:1.7;">
      此郵件由 <strong>AI 快報 Bot</strong> 每週一自動發送 &nbsp;·&nbsp; 如不想收到請聯絡管理員
      <br>
      資料來源：Reddit &nbsp;·&nbsp; Product Hunt &nbsp;·&nbsp; 機器之心 &nbsp;·&nbsp; 量子位
    </td>
  </tr>

</table>
</td></tr>
</table>

</body>
</html>"""

    return html


# ── 發送函式 ─────────────────────────────────────────────────────────────────

def send_weekly_report(report_text: str) -> bool:
    """
    將週報文字轉為 HTML Email 並透過公司 SMTP 發送。
    返回 True 表示成功，False 表示失敗（失敗時會 print 錯誤訊息）。
    """
    if not is_configured():
        print("  ⚠️  Email 未設定（缺少環境變數），跳過發送。", flush=True)
        return False

    cfg = _get_config()
    now = datetime.now()
    date_str = now.strftime("%Y/%m/%d")

    subject = f"{cfg['subject_prefix']}{date_str} AI 產業趨勢週報"

    # 組裝 MIME 郵件（純文字 + HTML 兩個 part，client 優先顯示 HTML）
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg["from_addr"]
    msg["To"]      = ", ".join(cfg["recipients"])

    # 純文字 fallback（移除 HTML 標籤）
    plain_text = re.sub(r"<[^>]+>", "", report_text)
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))

    # HTML 版本
    html_body = _tg_to_email_html(report_text)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # 發送
    try:
        print(f"  📧 發送週報 Email 至 {len(cfg['recipients'])} 位收件人…", flush=True)

        if cfg["use_ssl"]:
            # SSL（通常 port 465）
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"]) as server:
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_addr"], cfg["recipients"], msg.as_string())
        else:
            # STARTTLS（通常 port 587）或純文字（port 25）
            with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
                server.ehlo()
                if cfg["use_tls"]:
                    server.starttls()
                    server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_addr"], cfg["recipients"], msg.as_string())

        print("  ✅ Email 發送成功！", flush=True)
        return True

    except Exception as e:
        print(f"  ❌ Email 發送失敗：{e}", flush=True)
        return False
