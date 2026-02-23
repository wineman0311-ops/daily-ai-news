# ================================================================
# 每週 AI 快報 - Windows 排程安裝腳本 (PowerShell)
# 使用 Windows 工作排程器，每週一早上 08:00 自動執行
#
# 執行方式（以系統管理員身分開啟 PowerShell）：
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup_windows.ps1
# ================================================================

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       每週 AI 快報 - Windows 排程安裝       ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 取得腳本所在目錄 ──────────────────────────────────────────
$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "daily_ai_news.py"
$LogFile      = Join-Path $ScriptDir "ai_news.log"

# ── 確認 daily_ai_news.py 存在 ────────────────────────────────
if (-Not (Test-Path $PythonScript)) {
    Write-Host "❌ 找不到 daily_ai_news.py，請確認兩個檔案在同一資料夾" -ForegroundColor Red
    exit 1
}

# ── 尋找 Python 可執行檔 ─────────────────────────────────────
$PythonBin = $null

# 優先使用 Python Launcher (py.exe)
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $PythonBin = (Get-Command "py").Source
    Write-Host "✅ 找到 Python Launcher：$PythonBin" -ForegroundColor Green
}
# 其次用 python
elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $PythonBin = (Get-Command "python").Source
    Write-Host "✅ 找到 Python：$PythonBin" -ForegroundColor Green
}
# 最後試 python3
elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $PythonBin = (Get-Command "python3").Source
    Write-Host "✅ 找到 Python3：$PythonBin" -ForegroundColor Green
}
else {
    Write-Host "❌ 找不到 Python，請先安裝 Python 3" -ForegroundColor Red
    Write-Host "   下載：https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "   安裝時記得勾選「Add Python to PATH」" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ 腳本路徑：$PythonScript" -ForegroundColor Green
Write-Host "✅ 日誌路徑：$LogFile" -ForegroundColor Green
Write-Host ""

# ── 建立 Windows Task Scheduler 排程 ─────────────────────────
$TaskName    = "WeeklyAINewsReport"
$TaskDesc    = "每週一早上 8:00 自動抓取 AI 週報並發送至 Telegram"

# 設定動作：執行 python daily_ai_news.py >> ai_news.log 2>&1
# 使用 cmd /c 以便重新導向輸出到 log
$ActionExe  = "cmd.exe"
$ActionArgs = "/c `"$PythonBin`" `"$PythonScript`" >> `"$LogFile`" 2>&1"

$Action   = New-ScheduledTaskAction  -Execute $ActionExe -Argument $ActionArgs -WorkingDirectory $ScriptDir
$Trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "08:00"
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `       # 若開機時錯過，開機後補執行
    -WakeToRun:$false `
    -RunOnlyIfNetworkAvailable:$true

# 以目前使用者身分執行（不需輸入密碼）
$Principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

try {
    # 若已存在則先刪除
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "♻️  已移除舊排程，重新建立中..." -ForegroundColor Yellow
    }

    Register-ScheduledTask `
        -TaskName  $TaskName `
        -Action    $Action `
        -Trigger   $Trigger `
        -Settings  $Settings `
        -Principal $Principal `
        -Description $TaskDesc `
        -Force | Out-Null

    Write-Host ""
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  ✅ 排程安裝成功！" -ForegroundColor Green
    Write-Host "  📅 執行時間：每週一早上 08:00" -ForegroundColor White
    Write-Host "  📋 工作名稱：$TaskName" -ForegroundColor White
    Write-Host "  📝 日誌檔案：$LogFile" -ForegroundColor White
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
}
catch {
    Write-Host "❌ 排程安裝失敗：$_" -ForegroundColor Red
    Write-Host ""
    Write-Host "🔧 請以【系統管理員身分】重新執行此腳本：" -ForegroundColor Yellow
    Write-Host "   1. 右鍵點擊 PowerShell → 以系統管理員身分執行" -ForegroundColor Yellow
    Write-Host "   2. cd 到腳本所在目錄" -ForegroundColor Yellow
    Write-Host "   3. 執行：Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass" -ForegroundColor Yellow
    Write-Host "   4. 執行：.\setup_windows.ps1" -ForegroundColor Yellow
    exit 1
}

# ── 提示後續操作 ──────────────────────────────────────────────
Write-Host "💡 立即測試（不發送 Telegram）：" -ForegroundColor Yellow
Write-Host "   python `"$PythonScript`" --test" -ForegroundColor White
Write-Host ""
Write-Host "💡 立即發送一次：" -ForegroundColor Yellow
Write-Host "   python `"$PythonScript`"" -ForegroundColor White
Write-Host ""
Write-Host "💡 查看日誌：" -ForegroundColor Yellow
Write-Host "   Get-Content `"$LogFile`" -Tail 20 -Wait" -ForegroundColor White
Write-Host ""
Write-Host "💡 在工作排程器 GUI 中管理：" -ForegroundColor Yellow
Write-Host "   taskschd.msc  →  工作排程器程式庫  →  $TaskName" -ForegroundColor White
Write-Host ""
