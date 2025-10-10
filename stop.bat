@echo off
echo ================================================
echo     CLA Robot Kezelő - Szerver Leállítása
echo ================================================
echo.

:: Flask szerverek leállítása
echo Flask szerverek keresése és leállítása...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Robot Kezelő*" 2>nul
taskkill /F /IM python.exe /FI "COMMANDLINE eq *flask_app.py*" 2>nul

:: Port 5000-en futó folyamatok leállítása
echo Port 5000 felszabadítása...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000') do (
    taskkill /F /PID %%a 2>nul
)

echo.
echo Flask szerver leállítva!
echo Minden port felszabadítva.
echo.
pause