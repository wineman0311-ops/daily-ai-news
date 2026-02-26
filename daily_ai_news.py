#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每週 AI 快報 v2 - 深度分析版
結合 Reddit、Product Hunt、機器之心、量子位 的原始資料，
透過 Claude API 生成專業深度分析，每週一早上自動發送至 Telegram。

安裝依賴：pip install anthropic
執行方式：python daily_ai_news.py          # 正式發送
          python daily_ai_news.py --test   # 僅預覽，不發送
"""

import sys
import os
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# ── 檢查 anthropic 套件 ───────────────────────────────────────
try:
    import anthropic
except ImportError:
    print("❌ 缺少 anthropic 套件，請先執行：pip install anthropic")
    sys.exit(1)

# ── 從 .env 載入環境變數（若尚未設定）───────────────────────────
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

# =====================================================================
# 設定區：優先讀取環境變數，其次讀取 .env 檔
# 請將實際金鑰填入同目錄的 .env 檔（參考 .env.example）
# =====================================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BOT_TOKEN         = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# 支援多個 Chat ID，以逗號分隔，例如：112966076,987654321
_raw_ids  = os.environ.get("TELEGRAM_CHAT_ID", "")
CHAT_IDS  = [cid.strip() for cid in _raw_ids.split(",") if cid.strip()]
CHAT_ID   = CHAT_IDS[0] if CHAT_IDS else ""   # 向下相容

# claude-haiku：快速、低成本（每次報告約 $0.001～0.003 美元）
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
TIMEOUT      = 25

# 報告快取（每次生成後存檔，/preview 優先從此讀取）
DATA_DIR          = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))
REPORT_CACHE_FILE = DATA_DIR / "report_cache.json"
# =====================================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}


# ─────────────────────────────────────────────────────────────
# HTTP 工具
# ─────────────────────────────────────────────────────────────
def http_get(url, extra=None):
    h = dict(HEADERS)
    if extra:
        h.update(extra)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            cs = r.headers.get_content_charset() or "utf-8"
            return r.read().decode(cs, errors="replace")
    except Exception as e:
        print(f"  ⚠️  [{url[:55]}] {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────────────────────
# 資料收集：Reddit
# ─────────────────────────────────────────────────────────────
def fetch_reddit(top_n=8):
    subs = ["artificial", "MachineLearning", "LocalLLaMA", "ChatGPT", "singularity"]
    posts = []
    for sub in subs:
        raw = http_get(
            f"https://www.reddit.com/r/{sub}/hot.json?limit=5",
            extra={"Accept": "application/json"},
        )
        if not raw:
            continue
        try:
            for c in json.loads(raw)["data"]["children"]:
                p = c["data"]
                if p.get("stickied"):
                    continue
                posts.append({
                    "source":   f"Reddit r/{sub}",
                    "title":    p["title"][:150],
                    "url":      f"https://reddit.com{p['permalink']}",
                    "score":    p.get("score", 0),
                    "comments": p.get("num_comments", 0),
                })
        except Exception as e:
            print(f"  ⚠️  Reddit [{sub}]: {e}", file=sys.stderr)
    posts.sort(key=lambda x: x["score"], reverse=True)
    return posts[:top_n]


# ─────────────────────────────────────────────────────────────
# 資料收集：RSS（Product Hunt / 機器之心 / 量子位）
# ─────────────────────────────────────────────────────────────
def fetch_rss(url, source_name, max_items=5, ai_filter=False):
    AI_KW = [
        "ai", "llm", "gpt", "chatbot", "machine learning", "agent",
        "artificial intelligence", "automation", "model", "neural",
        "人工智能", "機器學習", "大模型", "生成式", "智能",
    ]
    raw = http_get(url)
    if not raw:
        return []
    items = []
    try:
        root = ET.fromstring(raw.replace("xmlns=", "xmlnamespace="))
        channel = root.find("channel")
        if channel is not None:
            src_items = channel.findall("item")
            def get_title(el): return (el.findtext("title") or "").strip()
            def get_link(el):  return (el.findtext("link")  or "").strip()
            def get_desc(el):  return (el.findtext("description") or "").strip()[:250]
        else:
            ns = "http://www.w3.org/2005/Atom"
            src_items = root.findall(f"{{{ns}}}entry")
            def get_title(el): return (el.findtext(f"{{{ns}}}title") or "").strip()
            def get_link(el):
                lel = el.find(f"{{{ns}}}link")
                return lel.get("href", "") if lel is not None else ""
            def get_desc(el):  return (el.findtext(f"{{{ns}}}summary") or "").strip()[:250]

        for item in src_items:
            t = get_title(item)
            l = get_link(item)
            d = get_desc(item)
            if ai_filter and not any(k in (t + d).lower() for k in AI_KW):
                continue
            if t and l:
                items.append({"source": source_name, "title": t[:150],
                              "url": l, "summary": d})
            if len(items) >= max_items:
                break
    except ET.ParseError as e:
        print(f"  ⚠️  RSS [{source_name}]: {e}", file=sys.stderr)
    return items


# ─────────────────────────────────────────────────────────────
# Claude API：生成深度分析報告
# ─────────────────────────────────────────────────────────────
def generate_report(raw_data: dict) -> str:
    now   = datetime.now()
    date  = now.strftime("%Y/%m/%d")
    year  = now.year
    month = now.month

    # 整理原始資料文字
    ctx = []
    if raw_data.get("reddit"):
        ctx.append("【Reddit 熱門貼文（依讚數排序）】")
        for p in raw_data["reddit"]:
            ctx.append(f"- [{p['source']}] {p['title']}  ⬆️{p['score']} 💬{p['comments']}  {p['url']}")
    if raw_data.get("producthunt"):
        ctx.append("\n【Product Hunt 今日 AI 工具】")
        for p in raw_data["producthunt"]:
            ctx.append(f"- {p['title']} | {p.get('summary','')} | {p['url']}")
    if raw_data.get("jiqizhixin"):
        ctx.append("\n【機器之心 最新文章】")
        for p in raw_data["jiqizhixin"]:
            ctx.append(f"- {p['title']} | {p['url']}")
    if raw_data.get("qbitai"):
        ctx.append("\n【量子位 最新文章】")
        for p in raw_data["qbitai"]:
            ctx.append(f"- {p['title']} | {p['url']}")

    context = "\n".join(ctx) if ctx else "（本週外部資料抓取受限，請以你對 AI 產業的最新知識補充）"

    prompt = f"""你是一位頂尖的 AI 產業分析師，專門為繁體中文軟體開發團隊撰寫深度 AI 趨勢週報。

【讀者背景】
本報告的讀者是一家 43 人的軟體公司，其中：
- 16 位 Web 產品工程師（關注：AI API 整合、前端 AI 框架、LLM 應用開發、生產力工具）
- 6 位 C++ 產品工程師（關注：推論效能、邊緣部署、CUDA/NPU 加速、llama.cpp、ONNX）
- 其餘為 PM、QA、設計、管理層（關注：產業動態、競品機會、AI 策略）

本週發送日期：{date}（{year}年{month}月）

以下是本週從 Reddit、Product Hunt、機器之心、量子位收集到的原始資料：

{context}

請根據上述資料，結合你對 AI 產業的最新知識，用繁體中文撰寫一份深度每週 AI 快報。
嚴格按照以下格式輸出（使用 Telegram HTML 格式，勿輸出任何額外說明文字）：

這是本週最新 AI 發展趨勢與工具整理，由小秘書 Bot 每週一自動發送。

🚀 <b>{year}年{month}月：本週 AI 產業核心動態</b>

• <b>【趨勢主題一】</b>：一句話摘要
  • <b>具體新聞一</b>：2-3 句詳細說明，含影響、亮點、數據
  • <b>具體新聞二</b>：2-3 句詳細說明
  • <b>具體新聞三</b>：2-3 句詳細說明

• <b>【趨勢主題二】</b>：一句話摘要
  • <b>具體新聞一</b>：2-3 句詳細說明
  • <b>具體新聞二</b>：2-3 句詳細說明

• <b>【趨勢主題三】</b>：一句話摘要
  • <b>具體新聞一</b>：2-3 句詳細說明
  • <b>具體新聞二</b>：2-3 句詳細說明

─────────────────────
🌐 <b>Web 團隊本週精選</b>（前端 / API / LLM 應用）

• <b>工具或框架名稱</b> <i>【立即可用】</i>
  爆紅亮點：說明為何在 Reddit/PH 引爆討論，核心功能是什麼
  對 Web 團隊的價值：具體說明能解決什麼開發痛點或加速哪個工作流程
  🔗 <a href="URL">了解更多</a>

• <b>工具或框架名稱</b> <i>【值得評估】</i>
  爆紅亮點：說明
  對 Web 團隊的價值：說明
  🔗 <a href="URL">了解更多</a>

• <b>工具或框架名稱</b> <i>【持續觀察】</i>
  爆紅亮點：說明
  對 Web 團隊的價值：說明
  🔗 <a href="URL">了解更多</a>

─────────────────────
⚙️ <b>C++ 團隊本週精選</b>（推論 / 邊緣部署 / 硬體加速）

• <b>工具或框架名稱</b> <i>【立即可用】</i>
  爆紅亮點：說明
  對 C++ 團隊的價值：具體說明效能提升、部署場景或整合難度
  🔗 <a href="URL">了解更多</a>

• <b>工具或框架名稱</b> <i>【值得評估】</i>
  爆紅亮點：說明
  對 C++ 團隊的價值：說明
  🔗 <a href="URL">了解更多</a>

─────────────────────
💡 <b>深度觀察：對我們團隊的影響</b>

1. <b>觀察主題一</b>：
3-4 句深度分析，說明此趨勢對 Web 或 C++ 產品團隊的實際影響與具體應對建議。

2. <b>觀察主題二</b>：
3-4 句深度分析，聚焦競品機會或團隊可採取的行動。

3. <b>觀察主題三</b>：
3-4 句深度分析，提出獨到洞見而非只是摘要新聞。

─────────────────────
⏰ 週報發送時間：{date} {now.strftime('%H:%M')}（每週一）

輸出規則（必須遵守）：
1. 僅使用 Telegram 支援的 HTML 標籤：<b> <i> <a href="..."> <code> <pre>
2. 一般文字中若出現 & < > 必須轉義為 &amp; &lt; &gt;
3. URL 必須使用本週資料中真實存在的連結；若無合適連結，使用該工具官網
4. 【立即可用】= 今天就能試用；【值得評估】= 需 1 週評估；【持續觀察】= 尚在早期
5. Web 與 C++ 各選最相關的工具，若本週資料不足可補充你的知識
6. 深度觀察要聚焦軟體開發公司視角，有具體行動建議
7. 全文繁體中文
"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=3500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


# ─────────────────────────────────────────────────────────────
# 報告快取：生成後存檔，/preview 優先讀取不重呼 API
# ─────────────────────────────────────────────────────────────
def save_report_cache(report: str):
    """將本期報告存入快取檔"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache = {
        "generated_at": datetime.now().isoformat(),
        "report":        report,
    }
    with open(REPORT_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"  💾 報告已存入快取（{REPORT_CACHE_FILE}）", flush=True)


def load_report_cache() -> str | None:
    """讀取快取報告，回傳報告文字；無快取時回傳 None"""
    if not REPORT_CACHE_FILE.exists():
        return None
    try:
        with open(REPORT_CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("report")
    except Exception:
        return None


def get_cache_info() -> dict | None:
    """讀取快取元資訊（生成時間等），無快取時回傳 None"""
    if not REPORT_CACHE_FILE.exists():
        return None
    try:
        with open(REPORT_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Telegram 發送（支援多個 Chat ID）
# ─────────────────────────────────────────────────────────────
def _split_chunks(text, max_len=4000):
    """將長文字切分成不超過 max_len 的片段"""
    if len(text) <= max_len:
        return [text]
    lines, chunks, buf = text.split("\n"), [], ""
    for line in lines:
        if len(buf) + len(line) + 1 > max_len:
            chunks.append(buf)
            buf = line
        else:
            buf = (buf + "\n" + line) if buf else line
    if buf:
        chunks.append(buf)
    return chunks


def _send_one_chunk(chat_id, text):
    """向單一 Chat ID 發送一則訊息"""
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id":                  chat_id,
        "text":                     text,
        "parse_mode":               "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"  ❌ HTTP {e.code}: {body}", file=sys.stderr)
        return {"ok": False}
    except Exception as e:
        print(f"  ❌ {e}", file=sys.stderr)
        return {"ok": False}


def send_telegram(text, target_ids=None, max_len=4000):
    """向指定 target_ids 發送訊息；未指定時使用環境變數的 CHAT_IDS"""
    ids     = target_ids if target_ids is not None else CHAT_IDS
    chunks  = _split_chunks(text, max_len)
    results = []

    for chat_id in ids:
        print(f"  📨 發送至 Chat ID: {chat_id}")
        for i, chunk in enumerate(chunks, 1):
            res = _send_one_chunk(chat_id, chunk)
            results.append(res)
            ok  = res.get("ok")
            mid = res.get("result", {}).get("message_id", "?")
            print(f"    {'✅' if ok else '❌'} 第 {i}/{len(chunks)} 則（msg_id={mid}）")

    return results


# ─────────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────────
def main(override_chat_ids=None):
    """
    override_chat_ids: 由外部（bot.py）傳入的收件人清單。
                       None 時使用環境變數 TELEGRAM_CHAT_ID。
    """
    test_mode = "--test" in sys.argv
    target    = override_chat_ids if override_chat_ids is not None else CHAT_IDS

    print(f"\n{'='*54}")
    print(f"  🤖 每週 AI 快報 v2 {'【測試模式】' if test_mode else ''}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*54}\n")

    # 檢查必要設定
    missing = [k for k, v in [
        ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
        ("TELEGRAM_BOT_TOKEN", BOT_TOKEN),
    ] if not v]
    if override_chat_ids is None and not _raw_ids:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        print(f"❌ 缺少必要設定：{', '.join(missing)}")
        print("   請在同目錄建立 .env 檔（參考 .env.example）")
        sys.exit(1)
    print(f"  📋 發送對象：{len(target)} 個 Chat ID（{', '.join(target)}）")

    # 收集原始資料
    print("📡 收集各來源資料中...")
    raw = {}
    print("  → Reddit（r/artificial / MachineLearning / LocalLLaMA / ChatGPT / singularity）")
    raw["reddit"]      = fetch_reddit(top_n=8)
    print("  → Product Hunt（AI 工具篩選）")
    raw["producthunt"] = fetch_rss("https://www.producthunt.com/feed",
                                   "Product Hunt", max_items=6, ai_filter=True)
    print("  → 機器之心 jiqizhixin.com")
    raw["jiqizhixin"]  = fetch_rss("https://www.jiqizhixin.com/rss",
                                   "機器之心", max_items=5)
    print("  → 量子位 qbitai.com")
    raw["qbitai"]      = fetch_rss("https://www.qbitai.com/feed",
                                   "量子位", max_items=5)

    total = sum(len(v) for v in raw.values())
    print(f"\n  📊 共收集 {total} 則原始資料\n")

    # 呼叫 Claude 生成深度報告
    print("🧠 Claude 生成深度分析報告中（約 10～20 秒）...")
    report = generate_report(raw)
    print(f"  ✅ 報告生成完成（{len(report)} 字元）\n")

    # 存入快取，供後續 /preview 直接讀取
    save_report_cache(report)

    # 發送 Email（若已設定 EMAIL_HOST 等環境變數）
    try:
        import email_sender
        if email_sender.is_configured():
            email_sender.send_weekly_report(report)
    except Exception as e:
        print(f"  ⚠️ Email 模組發生錯誤：{e}", flush=True)

    if test_mode:
        print("─── 報告預覽 " + "─" * 40)
        print(report)
        print("─" * 54)
        print("\n✅ 測試完成（未發送至 Telegram）")
        return

    print("📤 發送至 Telegram...")
    results = send_telegram(report, target_ids=target)
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{'✅' if ok == len(results) else '⚠️'} 完成！成功 {ok}/{len(results)} 則")
    if ok < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
