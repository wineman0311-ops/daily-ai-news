# 每週 AI 快報 🤖

每週一早上 8:00，自動從 Reddit、Product Hunt、機器之心、量子位收集最新 AI 資訊，透過 Claude API 生成深度分析週報，並透過 Telegram Bot 發送。

## 功能特色

- 🌐 **Reddit** — r/artificial、r/MachineLearning、r/LocalLLaMA、r/ChatGPT、r/singularity 熱門貼文
- 🚀 **Product Hunt** — 最新 AI 工具篩選
- 🤖 **機器之心**（jiqizhixin.com）— 中文 AI 專業報導
- ⚡ **量子位**（qbitai.com）— 中文 AI 專業報導
- 🧠 **Claude API** — 生成深度趨勢分析、工具推薦、專業洞察

## 安裝步驟

### 1. 安裝依賴

```bash
pip install anthropic
```

### 2. 設定環境變數

複製 `.env.example` 為 `.env`，填入您的金鑰：

```bash
cp .env.example .env
```

編輯 `.env`：

```
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_CHAT_ID=your-chat-id-here
```

- **Anthropic API Key**：前往 [console.anthropic.com](https://console.anthropic.com) 申請
- **Telegram Bot Token**：向 [@BotFather](https://t.me/BotFather) 申請
- **Telegram Chat ID**：向 [@userinfobot](https://t.me/userinfobot) 查詢

### 3. 測試執行

```bash
# 僅預覽報告，不發送 Telegram
python daily_ai_news.py --test

# 立即發送一次
python daily_ai_news.py
```

## 設定排程

### Linux / macOS（cron）

```bash
chmod +x setup_linux.sh
./setup_linux.sh
```

### Windows（工作排程器）

以系統管理員身分執行 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_windows.ps1
```

## 報告格式

每份週報包含三大區塊：

1. **🚀 本週 AI 產業核心動態** — 趨勢主題與具體新聞深度解析
2. **🔥 爆紅 AI 應用推薦** — 分類工具說明、爆紅亮點與專業價值
3. **💡 深度觀察** — 專業領域轉型挑戰與因應策略

## 費用估算

使用 Claude Haiku 模型，每份週報約 **$0.001～0.003 美元**，每月約 **$0.004～0.012 美元**。
