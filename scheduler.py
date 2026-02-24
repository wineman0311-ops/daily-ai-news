#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每週 AI 快報 - 容器排程器
作為 Docker 容器的主進程持續運行，每週一 08:00 自動觸發報告發送。
"""

import schedule
import time
import sys
from datetime import datetime

import daily_ai_news


def job():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now}] 🚀 開始執行每週 AI 快報...", flush=True)
    try:
        daily_ai_news.main()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 本週快報發送完成", flush=True)
    except SystemExit as e:
        # daily_ai_news.main() 失敗時會呼叫 sys.exit(1)，在此攔截避免容器崩潰
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 發送失敗（exit code {e.code}），下週一將自動重試", flush=True)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 未預期錯誤：{e}", flush=True)


if __name__ == "__main__":
    # 支援 --run-now 參數：立即執行一次（用於手動測試）
    if "--run-now" in sys.argv:
        print("🔧 手動觸發模式：立即執行一次", flush=True)
        job()
        sys.exit(0)

    print("=" * 52, flush=True)
    print("  🤖 每週 AI 快報 排程器啟動", flush=True)
    print(f"  時區：Asia/Taipei（容器 TZ 環境變數）", flush=True)
    print(f"  排程：每週一 08:00", flush=True)
    print(f"  啟動時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("=" * 52, flush=True)

    # 設定每週一 08:00 執行
    schedule.every().monday.at("08:00").do(job)

    # 顯示下次執行時間
    next_run = schedule.next_run()
    print(f"\n⏰ 下次執行時間：{next_run.strftime('%Y-%m-%d %H:%M:%S')} (週一)", flush=True)
    print("📡 排程器運行中，每 30 秒檢查一次...\n", flush=True)

    while True:
        schedule.run_pending()
        time.sleep(30)
