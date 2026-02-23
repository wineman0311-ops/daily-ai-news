#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot 連線測試腳本
只發送一則測試訊息，確認 Bot Token 和 Chat ID 設定正確
"""

import urllib.request
import urllib.error
import json
from datetime import datetime

BOT_TOKEN = "8537663949:AAHocRSeMiXxMnFxDytRBemmutDYEoRKJjE"
CHAT_ID   = "112966076"

def send_test_message():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = (
        "✅ <b>連線測試成功！</b>\n\n"
        "🤖 每日 AI 快報小秘書已就緒\n"
        f"⏰ 測試時間：{now}\n\n"
        "明天起每天早上 08:00 自動發送 AI 快報給您 🎉"
    )

    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id":                  CHAT_ID,
        "text":                     message,
        "parse_mode":               "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")

    print(f"📤 正在發送測試訊息至 Chat ID: {CHAT_ID} ...")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                msg_id = result["result"]["message_id"]
                print(f"✅ 發送成功！Message ID: {msg_id}")
                print("📱 請檢查您的 Telegram，應已收到測試訊息")
            else:
                print(f"❌ 發送失敗：{result}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"❌ HTTP 錯誤 {e.code}：{body}")
        if e.code == 401:
            print("   → Bot Token 無效，請確認 Token 是否正確")
        elif e.code == 400:
            print("   → Chat ID 無效，請確認 Chat ID 是否正確")
    except Exception as e:
        print(f"❌ 連線錯誤：{e}")
        print("   → 請確認網路連線正常，且未被防火牆封鎖")

if __name__ == "__main__":
    send_test_message()
