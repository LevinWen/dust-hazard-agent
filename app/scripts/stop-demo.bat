@echo off
chcp 65001 >nul
echo 正在停止 A5 Demo 服务...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8791" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo 已停止进程 %%a
)
echo.
echo 说明：花生壳隧道是常驻服务，不需要停；如需停可执行 hsk-cli engine stop 或去服务里停 OrayHskNG。
echo 按任意键关闭
pause >nul