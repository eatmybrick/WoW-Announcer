@echo off
cd /d "%~dp0"

set PY=python
where python >nul 2>&1 || set PY=py
where %PY% >nul 2>&1
if errorlevel 1 (
  echo Python is not installed yet.
  echo Get it from python.org and tick "Add Python to PATH" during install, then double click this file again.
  pause
  exit /b
)

if exist webhook.txt goto run
echo Paste your Discord webhook URL here and press Enter:
set /p HOOK=
>webhook.txt echo %HOOK%

:run
set /p DISCORD_WEBHOOK_URL=<webhook.txt
echo.
echo WoW Forever announcer is running. Leave this window open.
echo Close it to stop the bot.
echo.
%PY% wowforever_news.py --loop 900 --backfill 3
pause
