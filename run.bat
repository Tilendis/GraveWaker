@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ==============================
echo   GraveWaker — 数字掘墓人
echo ==============================
echo.
echo 启动中... 浏览器打开 http://localhost:8765
echo 按 Ctrl+C 停止
echo.
"D:\04_Tool\DevTools\Anaconda\Miniconda\envs\bdc\python.exe" app.py
pause
