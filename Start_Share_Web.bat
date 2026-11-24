@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "D:\AI_Agent_NCKH"
title AI Sinh De Tin 10 - Chia Se Cong Khai (Cloudflare Tunnel)
.\venv\Scripts\python.exe -u launch_public.py
echo.
pause
