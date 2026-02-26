#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每週 AI 快報 - Telegram Bot 主程式
同時運行：
  1. Telegram Bot（接收訂閱 / 取消訂閱 / 預覽指令）
  2. 排程器（依設定時間自動發送週報給所有訂閱者）

環境變數：
  TELEGRAM_BOT_TOKEN  - Bot Token（必填）
  ANTHROPIC_API_KEY   - Claude API Key（必填）
  SCHEDULE_DAY        - 星期幾發送，預設 monday
  SCHEDULE_TIME       - 發送時間 HH:MM，預設 08:00
  DATA_DIR            - 訂閱者資料目錄，預設 ./data（Zeabur 請掛載 Volume）
  TZ                  - 時區，預設 Asia/Taipei
"""

import os
import sys
import json
import asyncio
import threading
import schedule
import time
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path

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

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import daily_ai_news
import subscribers as sub_mgr

# ── 設定 ─────────────────────────────────────────────────────
BOT_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SCHEDULE_DAY  = os.environ.get("SCHEDULE_DAY",  "monday").strip().lower()
SCHEDULE_TIME = os.environ.get("SCHEDULE_TIME", "08:00").strip()
TZ            = os.environ.get("TZ", "Asia/Taipei")

# 新場關鍵字 log 路徑（與訂閱者資料同目錄）
DATA_DIR      = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))
XINCHANG_LOG  = DATA_DIR / "xinchang.log"
KEYWORD       = "新場"

# 版本追蹤
VERSION_FILE      = Path(__file__).parent / "version.json"   # 隨程式碼部署
LAST_VERSION_FILE = DATA_DIR / "last_version.txt"            # 記錄上次啟動版本

DAY_ZH = {
    "monday": "週一", "tuesday": "週二", "wednesday": "週三",
    "thursday": "週四", "friday": "週五", "saturday": "週六", "sunday": "週日",
}
DAY_VALID = list(DAY_ZH.keys())

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.WARNING,
)


# ═════════════════════════════════════════════════════════════
# Telegram Bot 指令處理
# ═════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    username   = update.effective_user.username
    first_name = update.effective_user.first_name or "朋友"
    day_zh     = DAY_ZH.get(SCHEDULE_DAY, SCHEDULE_DAY)

    # 第一次加入時自動訂閱
    is_new = sub_mgr.subscribe(chat_id, username, first_name)

    if is_new:
        # 全新使用者：自動訂閱 + 歡迎說明
        await update.message.reply_text(
            f"👋 <b>嗨，{first_name}！歡迎使用每週 AI 快報小秘書 🤖</b>\n\n"
            "我每週自動彙整來自 Reddit、Product Hunt、機器之心、量子位的最新 AI 資訊，"
            "並透過 Claude AI 深度分析後發送給您。\n\n"
            "✅ <b>已自動為您開啟訂閱！</b>\n"
            f"📅 每{day_zh} {SCHEDULE_TIME}（{TZ}）您將收到 AI 週報。\n\n"
            "📌 <b>可用指令：</b>\n"
            "  /subscribe   — 訂閱每週 AI 快報\n"
            "  /unsubscribe — 取消訂閱\n"
            "  /status      — 查看訂閱狀態與人數\n"
            "  /preview     — 立即取得最新一期快報（約需 30 秒）\n\n"
            "💡 如不想繼續接收，可隨時輸入 /unsubscribe 取消。",
            parse_mode="HTML",
        )
        print(f"[新訂閱] {first_name}（@{username}，{chat_id}）", flush=True)
    else:
        # 已訂閱使用者：顯示指令說明
        await update.message.reply_text(
            f"👋 <b>嗨，{first_name}！</b>\n\n"
            "您已訂閱每週 AI 快報 ✅\n\n"
            "📌 <b>可用指令：</b>\n"
            "  /subscribe   — 訂閱每週 AI 快報\n"
            "  /unsubscribe — 取消訂閱\n"
            "  /status      — 查看訂閱狀態與人數\n"
            "  /preview     — 立即取得最新一期快報（約需 30 秒）\n\n"
            f"⏰ <b>發送時間：</b>每{day_zh} {SCHEDULE_TIME}（{TZ}）",
            parse_mode="HTML",
        )


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    username   = update.effective_user.username
    first_name = update.effective_user.first_name or ""
    day_zh     = DAY_ZH.get(SCHEDULE_DAY, SCHEDULE_DAY)

    is_new = sub_mgr.subscribe(chat_id, username, first_name)
    if is_new:
        await update.message.reply_text(
            f"✅ <b>訂閱成功！</b>\n\n"
            f"您將在每{day_zh} {SCHEDULE_TIME} 收到 AI 週報。\n"
            "輸入 /unsubscribe 可隨時取消。",
            parse_mode="HTML",
        )
        print(f"[訂閱] {first_name}（@{username}，{chat_id}）", flush=True)
    else:
        await update.message.reply_text(
            "ℹ️ 您已訂閱，無需重複操作。\n"
            "輸入 /unsubscribe 可取消訂閱。"
        )


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    username   = update.effective_user.username
    first_name = update.effective_user.first_name or ""

    removed = sub_mgr.unsubscribe(chat_id)
    if removed:
        await update.message.reply_text(
            "✅ 已取消訂閱，您將不再收到每週快報。\n"
            "如需重新訂閱，輸入 /subscribe 即可。"
        )
        print(f"[取消訂閱] {first_name}（@{username}，{chat_id}）", flush=True)
    else:
        await update.message.reply_text(
            "ℹ️ 您尚未訂閱。\n"
            "輸入 /subscribe 開始訂閱每週 AI 快報。"
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id   = update.effective_chat.id
    subscribed = sub_mgr.is_subscribed(chat_id)
    count      = sub_mgr.get_count()
    day_zh     = DAY_ZH.get(SCHEDULE_DAY, SCHEDULE_DAY)

    status_icon = "✅ 已訂閱" if subscribed else "❌ 未訂閱"
    await update.message.reply_text(
        f"📊 <b>訂閱狀態：</b>{status_icon}\n"
        f"⏰ <b>發送時間：</b>每{day_zh} {SCHEDULE_TIME}\n"
        f"🌏 <b>時區：</b>{TZ}\n"
        f"👥 <b>目前訂閱人數：</b>{count} 人",
        parse_mode="HTML",
    )


async def cmd_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    優先從快取讀取本期報告發送給當前使用者；
    無快取時才呼叫 Claude API 生成（並存入快取供下次使用）。
    """
    if not sub_mgr.is_subscribed(update.effective_chat.id):
        await update.message.reply_text(
            "⚠️ 請先訂閱才能使用預覽功能。\n輸入 /subscribe 開始訂閱。"
        )
        return

    chat_id = str(update.effective_chat.id)
    loop    = asyncio.get_running_loop()

    # ── 優先讀取快取 ──────────────────────────────────────────
    cache_info = daily_ai_news.get_cache_info()
    if cache_info and cache_info.get("report"):
        generated_at = cache_info.get("generated_at", "")[:16].replace("T", " ")
        await update.message.reply_text(
            f"📋 讀取本期快取報告（生成於 {generated_at}）…"
        )
        cached_report = cache_info["report"]

        def send_cached():
            try:
                daily_ai_news.send_telegram(cached_report, target_ids=[chat_id])
            except Exception as e:
                print(f"[preview cache send error] {e}", flush=True)

        await loop.run_in_executor(None, send_cached)
        return

    # ── 無快取：重新生成並存入快取 ───────────────────────────
    await update.message.reply_text(
        "⏳ 本期快報尚未生成，正在向 Claude AI 取得資料，約需 20～40 秒，請稍候…"
    )

    def generate_and_send():
        try:
            daily_ai_news.main(override_chat_ids=[chat_id])
        except SystemExit:
            pass
        except Exception as e:
            print(f"[preview generate error] {e}", flush=True)

    await loop.run_in_executor(None, generate_and_send)


# ═════════════════════════════════════════════════════════════
# 新場關鍵字監聽
# ═════════════════════════════════════════════════════════════

def _log_xinchang(entry: str):
    """將新場訊息寫入 log 檔"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(XINCHANG_LOG, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理所有未知指令，回覆無此指令並附上說明"""
    day_zh = DAY_ZH.get(SCHEDULE_DAY, SCHEDULE_DAY)
    await update.message.reply_text(
        "❓ <b>無此指令</b>\n\n"
        "📌 <b>可用指令列表：</b>\n"
        "  /start       — 啟動 Bot 並查看說明\n"
        "  /subscribe   — 訂閱每週 AI 快報\n"
        "  /unsubscribe — 取消訂閱\n"
        "  /status      — 查看訂閱狀態與人數\n"
        "  /preview     — 立即取得最新一期快報\n\n"
        f"⏰ <b>發送時間：</b>每{day_zh} {SCHEDULE_TIME}（{TZ}）",
        parse_mode="HTML",
    )


async def msg_xinchang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """偵測對話中含有「新場」的訊息，存 log 後回貼到對話"""
    msg  = update.message
    text = msg.text or ""

    if KEYWORD not in text:
        return  # 不含關鍵字，略過

    user       = msg.from_user
    username   = f"@{user.username}" if user.username else user.first_name
    chat_title = msg.chat.title or "私聊"
    ts         = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 寫入 log ──────────────────────────────────────────────
    log_entry = (
        f"[{ts}] "
        f"對話：{chat_title} | "
        f"發話人：{username}（id={user.id}）| "
        f"內容：{text}"
    )
    _log_xinchang(log_entry)
    print(f"[新場紀錄] {log_entry}", flush=True)

    # ── 回貼到對話 ────────────────────────────────────────────
    await msg.reply_text(
        f"📌 <b>新場訊息已記錄</b>\n\n"
        f"🕐 時間：{ts}\n"
        f"👤 發話人：{username}\n"
        f"💬 內容：{text}\n\n"
        f"<i>已儲存至 xinchang.log</i>",
        parse_mode="HTML",
    )


# ═════════════════════════════════════════════════════════════
# 版本更新廣播
# ═════════════════════════════════════════════════════════════

def _load_version_info() -> dict:
    """讀取 version.json，回傳 {version, date, notes}；讀取失敗時回傳空 dict"""
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_last_version() -> str:
    """讀取上次啟動時儲存的版本號，無記錄時回傳空字串"""
    try:
        return LAST_VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _save_last_version(version: str):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_VERSION_FILE.write_text(version, encoding="utf-8")


async def _on_startup(app):
    """
    Bot 啟動後呼叫（post_init hook）。
    若版本號與上次不同，向所有訂閱者發送更新說明。
    """
    info = _load_version_info()
    if not info:
        return

    current  = info.get("version", "")
    last     = _get_last_version()
    _save_last_version(current)

    if not current or current == last:
        return  # 版本相同，無需廣播

    # 組版本通知訊息
    date  = info.get("date", "")
    notes = info.get("notes", [])
    lines = "\n".join(f"  {n}" for n in notes) if notes else "  （無詳細說明）"

    msg = (
        f"🆕 <b>Bot 已更新至 v{current}</b>（{date}）\n\n"
        f"<b>本次更新內容：</b>\n{lines}"
    )

    chat_ids = sub_mgr.get_chat_ids()
    if not chat_ids:
        print(f"[版本廣播] v{last} → v{current}，目前無訂閱者，略過發送", flush=True)
        return

    print(f"[版本廣播] v{last} → v{current}，發送給 {len(chat_ids)} 位訂閱者…", flush=True)
    for cid in chat_ids:
        try:
            await app.bot.send_message(
                chat_id    = cid,
                text       = msg,
                parse_mode = "HTML",
            )
        except Exception as e:
            print(f"  ⚠️ 發送至 {cid} 失敗：{e}", flush=True)
    print(f"  ✅ 版本廣播完成", flush=True)


# ═════════════════════════════════════════════════════════════
# 排程器（背景執行緒）
# ═════════════════════════════════════════════════════════════

def _cleanup_xinchang_log():
    """每月1日執行：刪除 xinchang.log 中上個月的記錄"""
    if not XINCHANG_LOG.exists():
        return

    now        = datetime.now()
    last_month = now - relativedelta(months=1)
    prefix     = last_month.strftime("[%Y-%m-")   # 例如 "[2026-01-"

    with open(XINCHANG_LOG, "r", encoding="utf-8") as f:
        lines = f.readlines()

    kept    = [l for l in lines if not l.startswith(prefix)]
    removed = len(lines) - len(kept)

    with open(XINCHANG_LOG, "w", encoding="utf-8") as f:
        f.writelines(kept)

    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"[{ts}] 🗑️ xinchang.log 清理完成："
        f"刪除 {last_month.strftime('%Y年%m月')} 共 {removed} 筆，"
        f"保留 {len(kept)} 筆",
        flush=True,
    )


def _weekly_job():
    chat_ids = sub_mgr.get_chat_ids()
    now      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] 🚀 執行週報，訂閱人數：{len(chat_ids)}", flush=True)

    if not chat_ids:
        print("  ⚠️ 目前無訂閱者，跳過發送", flush=True)
        return

    try:
        daily_ai_news.main(override_chat_ids=chat_ids)
    except SystemExit:
        pass
    except Exception as e:
        print(f"  ❌ 週報發送失敗：{e}", flush=True)


def _run_scheduler():
    if SCHEDULE_DAY not in DAY_VALID:
        print(f"❌ SCHEDULE_DAY 無效：'{SCHEDULE_DAY}'，可用值：{DAY_VALID}", flush=True)
        sys.exit(1)

    getattr(schedule.every(), SCHEDULE_DAY).at(SCHEDULE_TIME).do(_weekly_job)

    # 每月 1 日 00:05 清理上個月的新場 log
    schedule.every().day.at("00:05").do(
        lambda: _cleanup_xinchang_log() if datetime.now().day == 1 else None
    )

    day_zh   = DAY_ZH.get(SCHEDULE_DAY, SCHEDULE_DAY)
    next_run = schedule.next_run()
    print(f"⏰ 排程：每{day_zh} {SCHEDULE_TIME} | 下次：{next_run.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"🗑️ 排程：每月 1 日 00:05 自動清除上月新場 log", flush=True)

    while True:
        schedule.run_pending()
        time.sleep(30)


# ═════════════════════════════════════════════════════════════
# 主程式
# ═════════════════════════════════════════════════════════════

def main():
    if not BOT_TOKEN:
        print("❌ 缺少 TELEGRAM_BOT_TOKEN", flush=True)
        sys.exit(1)

    # --run-now：立即向所有訂閱者發送（手動觸發）
    if "--run-now" in sys.argv:
        print("🔧 手動觸發：立即向所有訂閱者發送週報", flush=True)
        _weekly_job()
        return

    # 排程器在背景執行緒運行
    t = threading.Thread(target=_run_scheduler, daemon=True)
    t.start()

    day_zh = DAY_ZH.get(SCHEDULE_DAY, SCHEDULE_DAY)
    print("=" * 54, flush=True)
    print("  🤖 AI 快報 Bot 啟動", flush=True)
    print(f"  排程：每{day_zh} {SCHEDULE_TIME}（{TZ}）", flush=True)
    print(f"  訂閱人數：{sub_mgr.get_count()} 人", flush=True)
    print(f"  啟動時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("=" * 54, flush=True)

    # 建立 Bot 應用（post_init：啟動後檢查版本並廣播更新）
    app = Application.builder().token(BOT_TOKEN).post_init(_on_startup).build()
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("subscribe",   cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(CommandHandler("status",      cmd_status))
    app.add_handler(CommandHandler("preview",     cmd_preview))

    # 未知指令：回覆無此指令 + 指令說明（必須在所有 CommandHandler 之後）
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    # 監聽所有一般文字訊息，偵測「新場」關鍵字
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_xinchang))

    print("📡 Bot 開始接收訊息...\n", flush=True)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
