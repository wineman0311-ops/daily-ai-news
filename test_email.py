#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_email.py — 本機 Email 發送測試腳本
用途：不呼叫 Claude API，直接用假資料測試 SMTP 發送是否正常

執行方式：
  python test_email.py
"""

import os
import sys
from pathlib import Path

# ── 載入 .env ─────────────────────────────────────────────────
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("⚠️  找不到 .env 檔，請先建立（參考 .env.example）")
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

import email_sender

# ── 假報告內容（模擬 Claude 輸出格式）────────────────────────
SAMPLE_REPORT = """這是本週最新 AI 發展趨勢與工具整理，由小秘書 Bot 每週一自動發送。

🚀 <b>2026年2月：本週 AI 產業核心動態</b>

• <b>【推理模型成本崩潰】</b>：思考鏈技術進入大規模商用
  • <b>OpenAI o3-mini 正式開放</b>：每百萬 token 僅 $1.1，速度提升 60%
  • <b>Google Gemini 2.0 Flash Thinking</b>：AIME 2024 得分 80%，正面挑戰 GPT-4o

• <b>【AI Agent 進入生產環境】</b>：從 demo 到實際工作流自動化
  • <b>Cursor 0.45 多文件 Agent</b>：可跨 10 個文件重構，Product Hunt 本週 #1

─────────────────────
🛠️ <b>本週研發精選工具</b>（前端 / API / LLM 應用 / 推論效能 / 邊緣部署）

• <b>Vercel AI SDK 4.0</b> <i>【立即可用】</i>
  爆紅亮點：支援 streaming UI、多模型切換，Product Hunt #2，Hacker News 430 留言
  對研發的價值：可直接在 Next.js / React 中建立 AI 功能，減少 60% 樣板程式碼
  🔗 <a href="https://sdk.vercel.ai">了解更多</a>

• <b>llama.cpp b3700</b> <i>【立即可用】</i>
  爆紅亮點：ARM NEON 與 AVX-512 優化，90B 模型 4-bit 推論速度提升 23%
  對研發的價值：純 C++ 實作、MIT 授權、零外部依賴，可直接嵌入現有產品
  🔗 <a href="https://github.com/ggerganov/llama.cpp">了解更多</a>

• <b>Windsurf（Codeium）</b> <i>【值得評估】</i>
  爆紅亮點：Flow 引擎記憶整個 Repo 上下文，大量 Cursor 用戶轉移
  對研發的價值：多人協作效果顯著，建議安排 1 週 PoC
  🔗 <a href="https://codeium.com/windsurf">了解更多</a>

─────────────────────
💡 <b>深度觀察：對我們團隊的影響</b>

1. <b>AI 輔助編碼正在重塑工程師核心職能</b>：
Cursor、Windsurf 讓單人產出速度提升 3-5 倍，真正挑戰在於架構判斷力。

2. <b>C++ 產品的 AI 整合窗口正在打開</b>：
llama.cpp 讓在 C++ 應用內嵌入推論引擎的門檻大幅降低，現在是評估的最佳時機。

3. <b>Web 產品沒有 AI 功能將成為負面訊號</b>：
Vercel AI SDK 4.0 顯示 Web AI 功能已從差異化優勢走向基本配備。

─────────────────────
⏰ 週報發送時間：2026/02/27 08:00（每週一）"""


def main():
    print("=" * 50)
    print("  📧 Email 發送測試")
    print("=" * 50)

    # 檢查設定
    if not email_sender.is_configured():
        print("\n❌ Email 環境變數未設定，請在 .env 加入以下設定：\n")
        print("  EMAIL_HOST=你的SMTP伺服器")
        print("  EMAIL_PORT=587")
        print("  EMAIL_USER=你的帳號")
        print("  EMAIL_PASSWORD=你的密碼")
        print("  EMAIL_FROM=AI快報小秘書 <bot@company.com>")
        print("  EMAIL_RECIPIENTS=收件人@company.com")
        print("\n設定完成後再次執行此腳本即可。")
        sys.exit(1)

    cfg = email_sender._get_config()
    print(f"\n✅ 設定讀取成功")
    print(f"  SMTP 伺服器：{cfg['host']}:{cfg['port']}")
    print(f"  寄件人：{cfg['from_addr']}")
    print(f"  收件人：{', '.join(cfg['recipients'])}")
    print(f"  TLS：{cfg['use_tls']} / SSL：{cfg['use_ssl']}")
    print(f"\n📤 發送測試 Email 中...")

    success = email_sender.send_weekly_report(SAMPLE_REPORT)

    print()
    if success:
        print("✅ 測試成功！請檢查收件匣是否收到 Email。")
    else:
        print("❌ 發送失敗，請確認 SMTP 設定是否正確。")
        print("   常見問題：")
        print("   - 密碼使用應用程式密碼（非登入密碼）")
        print("   - Port 587 搭配 EMAIL_USE_TLS=true")
        print("   - Port 465 搭配 EMAIL_USE_SSL=true")


if __name__ == "__main__":
    main()
