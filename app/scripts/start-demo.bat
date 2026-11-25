@echo off
chcp 65001 >nul
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-demo.ps1"
echo.
echo 按任意键关闭本窗口（服务会继续在后台运行）
pause >nul