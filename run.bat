@echo off
chcp 65001 >nul
cd /d "%~dp0"
python app.py
if errorlevel 1 (
  echo.
  echo 启动失败。请先运行：pip install -r requirements.txt
  pause
)
