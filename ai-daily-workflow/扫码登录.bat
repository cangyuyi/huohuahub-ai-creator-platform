@echo off
chcp 65001 >nul
title 微信Bot登录
echo ============================================
echo   微信Bot扫码登录
echo ============================================
echo.
echo 正在获取二维码...
echo.

cd /d "%~dp0"
set HTTP_PROXY=
set HTTPS_PROXY=
"C:\Users\18196\AppData\Local\Programs\Python\Python312\python.exe" -u wechat_login.py

echo.
echo 按任意键退出...
pause >nul
