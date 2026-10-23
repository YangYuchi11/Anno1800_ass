@echo off
chcp 65001 >nul
title Anno 1800 Trade Copilot Launcher

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [提示] 正在请求管理员权限以支持游戏内热键监听与键鼠自动操作...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

set "PYTHON=py -3"
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"

echo [1/2] 正在检查并安装 Python 依赖库...
%PYTHON% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [2/2] 正在启动《纪元1800》全自动贸易指挥中心...
%PYTHON% anno_copilot.py
pause
