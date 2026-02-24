# ── 基礎映像 ─────────────────────────────────────────────────
FROM python:3.11-slim

# ── 時區設定（台北時間 UTC+8）────────────────────────────────
ENV TZ=Asia/Taipei
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── 工作目錄 ─────────────────────────────────────────────────
WORKDIR /app

# ── 安裝 Python 依賴 ─────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 複製程式碼（.env 已在 .gitignore 中排除，不會被複製）────
COPY . .

# ── 環境變數（由 Zeabur Dashboard 設定，這裡僅為預設提示）───
# ANTHROPIC_API_KEY=  ← 請在 Zeabur 環境變數中設定
# TELEGRAM_BOT_TOKEN= ← 請在 Zeabur 環境變數中設定
# TELEGRAM_CHAT_ID=   ← 請在 Zeabur 環境變數中設定

# ── 啟動排程器 ───────────────────────────────────────────────
CMD ["python", "-u", "scheduler.py"]
