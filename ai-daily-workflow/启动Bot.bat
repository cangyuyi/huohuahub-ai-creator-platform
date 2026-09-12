@echo off
chcp 65001 >nul
title AI日报 - 微信Bot
echo ============================================
echo   AI日报 - 微信Bot
echo ============================================
echo.
echo 正在启动Bot...
echo.

cd /d "%~dp0"
set HTTP_PROXY=
set HTTPS_PROXY=
"C:\Users\18196\AppData\Local\Programs\Python\Python312\python.exe" -u ai_news_bot.py

echo.
echo Bot已停止。按任意键退出...
pause >nul
