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
import asyncio
import threading
import schedule
import time
import logging
from datetime import datetime
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
DATA_DIR  = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))
XINCHANG_LOG = DATA_DIR / "xinchang.log"
KEYWORD   = "新場"

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
    """立即生成並發送給當前使用者（不影響其他訂閱者）"""
    if not sub_mgr.is_subscribed(update.effective_chat.id):
        await update.message.reply_text(
            "⚠️ 請先訂閱才能使用預覽功能。\n輸入 /subscribe 開始訂閱。"
        )
        return

    await update.message.reply_text("⏳ 正在生成本週 AI 快報，約需 20～40 秒，請稍候...")

    chat_id = str(update.effective_chat.id)
    loop = asyncio.get_event_loop()

    def blocking():
        try:
            daily_ai_news.main(override_chat_ids=[chat_id])
        except SystemExit:
            pass
        except Exception as e:
            print(f"[preview error] {e}", flush=True)

    await loop.run_in_executor(None, blocking)


# ═════════════════════════════════════════════════════════════
# 新場關鍵字監聽
# ═════════════════════════════════════════════════════════════

def _log_xinchang(entry: str):
    """將新場訊息寫入 log 檔"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(XINCHANG_LOG, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


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
# 排程器（背景執行緒）
# ═════════════════════════════════════════════════════════════

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

    day_zh   = DAY_ZH.get(SCHEDULE_DAY, SCHEDULE_DAY)
    next_run = schedule.next_run()
    print(f"⏰ 排程：每{day_zh} {SCHEDULE_TIME} | 下次：{next_run.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

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

    # 建立 Bot 應用
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("subscribe",   cmd_subscribe))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe))
    app.add_handler(CommandHandler("status",      cmd_status))
    app.add_handler(CommandHandler("preview",     cmd_preview))

    # 監聽所有一般文字訊息，偵測「新場」關鍵字
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_xinchang))

    print("📡 Bot 開始接收訊息...\n", flush=True)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
