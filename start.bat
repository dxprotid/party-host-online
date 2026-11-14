@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 server.py
) else (
    python server.py
)
if errorlevel 1 (
    echo.
    echo Could not start the server. Install Python 3.10+ from python.org
    echo During installation enable "Add Python to PATH".
)
pause
