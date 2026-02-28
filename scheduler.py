#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每週 AI 快報 - 容器排程器
作為 Docker 容器的主進程持續運行，依環境變數設定的時間自動觸發報告發送。

排程相關環境變數：
  SCHEDULE_DAY   - 第一次發送：星期幾，預設 monday
                   可選：monday / tuesday / wednesday / thursday / friday / saturday / sunday
  SCHEDULE_TIME  - 第一次發送：執行時間（HH:MM），預設 08:00
  SCHEDULE_DAY_2 - 第二次發送：星期幾（選填，不設定 = 每週只發一次）
  SCHEDULE_TIME_2- 第二次發送：執行時間（HH:MM），預設 08:00（SCHEDULE_DAY_2 有效時才生效）
  TZ             - 時區，預設 Asia/Taipei
"""

import os
import schedule
import time
import sys
from datetime import datetime
from pathlib import Path

# ── 從 .env 載入環境變數（本地開發用）───────────────────────────
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

import daily_ai_news

# ── 排程參數（從環境變數讀取）────────────────────────────────────
SCHEDULE_DAY   = os.environ.get("SCHEDULE_DAY",   "monday").strip().lower()
SCHEDULE_TIME  = os.environ.get("SCHEDULE_TIME",  "08:00").strip()
SCHEDULE_DAY_2 = os.environ.get("SCHEDULE_DAY_2", "").strip().lower()   # 空字串 = 不啟用
SCHEDULE_TIME_2= os.environ.get("SCHEDULE_TIME_2","08:00").strip()

# 中文星期對照（用於 log 顯示）
DAY_ZH = {
    "monday":    "週一", "tuesday":  "週二", "wednesday": "週三",
    "thursday":  "週四", "friday":   "週五", "saturday":  "週六",
    "sunday":    "週日",
}

# schedule 套件支援的星期屬性對照
DAY_MAP = {
    "monday":    "monday",    "tuesday":  "tuesday",  "wednesday": "wednesday",
    "thursday":  "thursday",  "friday":   "friday",   "saturday":  "saturday",
    "sunday":    "sunday",
}


def job():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] 🚀 開始執行 AI 快報...", flush=True)
    try:
        daily_ai_news.main()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 快報發送完成", flush=True)
    except SystemExit as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 發送失敗（exit code {e.code}），下次排程時自動重試", flush=True)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 未預期錯誤：{e}", flush=True)


def setup_schedule():
    """依環境變數動態設定排程（支援每週最多兩次）"""
    # ── 第一次排程（必填）────────────────────────────────────────
    day_key = DAY_MAP.get(SCHEDULE_DAY)
    if not day_key:
        print(f"❌ SCHEDULE_DAY 設定無效：'{SCHEDULE_DAY}'", flush=True)
        print(f"   可用值：{', '.join(DAY_MAP.keys())}", flush=True)
        sys.exit(1)

    try:
        datetime.strptime(SCHEDULE_TIME, "%H:%M")
    except ValueError:
        print(f"❌ SCHEDULE_TIME 格式錯誤：'{SCHEDULE_TIME}'（應為 HH:MM，例如 08:00）", flush=True)
        sys.exit(1)

    getattr(schedule.every(), day_key).at(SCHEDULE_TIME).do(job)
    day1_zh = DAY_ZH.get(SCHEDULE_DAY, SCHEDULE_DAY)
    print(f"⏰ 第一排程：每{day1_zh} {SCHEDULE_TIME}", flush=True)

    # ── 第二次排程（選填）────────────────────────────────────────
    day2_zh = None
    if SCHEDULE_DAY_2:
        day_key2 = DAY_MAP.get(SCHEDULE_DAY_2)
        if not day_key2:
            print(f"⚠️ SCHEDULE_DAY_2 無效：'{SCHEDULE_DAY_2}'，第二排程已略過", flush=True)
        else:
            try:
                datetime.strptime(SCHEDULE_TIME_2, "%H:%M")
            except ValueError:
                print(f"⚠️ SCHEDULE_TIME_2 格式錯誤：'{SCHEDULE_TIME_2}'，第二排程已略過", flush=True)
            else:
                getattr(schedule.every(), day_key2).at(SCHEDULE_TIME_2).do(job)
                day2_zh = DAY_ZH.get(SCHEDULE_DAY_2, SCHEDULE_DAY_2)
                print(f"⏰ 第二排程：每{day2_zh} {SCHEDULE_TIME_2}", flush=True)

    return day1_zh, day2_zh


if __name__ == "__main__":
    # 支援 --run-now：立即執行一次（用於手動測試）
    if "--run-now" in sys.argv:
        print("🔧 手動觸發模式：立即執行一次", flush=True)
        job()
        sys.exit(0)

    tz = os.environ.get("TZ", "Asia/Taipei")
    day1_zh, day2_zh = setup_schedule()

    # 組合排程說明文字
    sched_desc = f"每{day1_zh} {SCHEDULE_TIME}"
    if day2_zh:
        sched_desc += f" 及 每{day2_zh} {SCHEDULE_TIME_2}"

    print("=" * 54, flush=True)
    print("  🤖 AI 快報 排程器啟動", flush=True)
    print(f"  時區：{tz}", flush=True)
    print(f"  排程：{sched_desc}", flush=True)
    print(f"  啟動時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("=" * 54, flush=True)

    next_run = schedule.next_run()
    print(f"\n⏰ 下次執行：{next_run.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("📡 排程器運行中，每 30 秒檢查一次...\n", flush=True)

    while True:
        schedule.run_pending()
        time.sleep(30)
