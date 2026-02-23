#!/bin/bash
# ================================================================
# 每週 AI 快報 - Linux 排程安裝腳本
# 使用 cron，每週一早上 08:00 自動執行
#
# 執行方式：
#   chmod +x setup_linux.sh
#   ./setup_linux.sh
# ================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/daily_ai_news.py"
LOG_FILE="$SCRIPT_DIR/ai_news.log"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║       每週 AI 快報 - Linux 排程安裝         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 確認 daily_ai_news.py 存在 ────────────────────────────────
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ 找不到 daily_ai_news.py，請確認兩個檔案在同一資料夾"
    exit 1
fi

# ── 尋找 Python 3 ─────────────────────────────────────────────
PYTHON_BIN=""
for candidate in python3 python /usr/bin/python3 /usr/local/bin/python3; do
    if command -v "$candidate" &>/dev/null; then
        VERSION=$("$candidate" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        if [ "$VERSION" = "3" ]; then
            PYTHON_BIN="$(command -v "$candidate")"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ 找不到 Python 3，請先安裝："
    echo "   Ubuntu/Debian：sudo apt install python3 python3-pip"
    echo "   CentOS/RHEL：  sudo yum install python3 python3-pip"
    exit 1
fi

echo "✅ Python 路徑：$PYTHON_BIN"
echo "✅ 腳本路徑：  $PYTHON_SCRIPT"
echo "✅ 日誌路徑：  $LOG_FILE"
echo ""

# ── 安裝 anthropic 套件 ───────────────────────────────────────
echo "📦 檢查 anthropic 套件..."
if ! "$PYTHON_BIN" -c "import anthropic" 2>/dev/null; then
    echo "   正在安裝 anthropic..."
    "$PYTHON_BIN" -m pip install anthropic --quiet
    echo "   ✅ 安裝完成"
else
    echo "   ✅ anthropic 已安裝"
fi
echo ""

# ── 建立執行包裝腳本 ───────────────────────────────────────────
WRAPPER="$SCRIPT_DIR/run_ai_news.sh"
cat > "$WRAPPER" << EOF
#!/bin/bash
# 自動生成的包裝腳本
cd "$SCRIPT_DIR"
"$PYTHON_BIN" "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>&1
EOF
chmod +x "$WRAPPER"
echo "✅ 包裝腳本已建立：$WRAPPER"

# ── 安裝 Cron Job（每週一 08:00）─────────────────────────────
# cron 格式：分 時 日 月 週（1=週一）
CRON_ENTRY="0 8 * * 1 $WRAPPER"

EXISTING_CRON=$(crontab -l 2>/dev/null || true)

if echo "$EXISTING_CRON" | grep -qF "$PYTHON_SCRIPT"; then
    echo "♻️  偵測到舊排程，正在更新..."
    EXISTING_CRON=$(echo "$EXISTING_CRON" | grep -v "$PYTHON_SCRIPT" | grep -v "$WRAPPER")
fi

# 寫入新 crontab
(echo "$EXISTING_CRON"; echo "$CRON_ENTRY") | grep -v '^$' | crontab -

echo ""
echo "════════════════════════════════════════════════"
echo "  ✅ 排程安裝成功！"
echo "  📅 執行時間：每週一早上 08:00"
echo "  📋 Cron 規則：$CRON_ENTRY"
echo "  📝 日誌檔案：$LOG_FILE"
echo "════════════════════════════════════════════════"
echo ""
echo "目前所有 Cron Jobs："
crontab -l
echo ""
echo "💡 立即測試（不發送 Telegram）："
echo "   $PYTHON_BIN \"$PYTHON_SCRIPT\" --test"
echo ""
echo "💡 立即發送一次："
echo "   $PYTHON_BIN \"$PYTHON_SCRIPT\""
echo ""
echo "💡 即時查看日誌："
echo "   tail -f \"$LOG_FILE\""
echo ""
