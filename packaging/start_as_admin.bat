@echo off
chcp 65001 >nul
title Anno 1800 Trade Copilot
cd /d "%~dp0"

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [提示] 正在请求管理员权限（全局热键与模拟鼠标键盘需要）...
    powershell -Command "Start-Process '%~dp0AnnoCopilot.exe' -Verb RunAs"
    exit /b
)

start "" "%~dp0AnnoCopilot.exe"
