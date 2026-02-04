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
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /R /C:":5000 .*LISTENING"') do (
    taskkill /F /PID %%a 2>nul
)

:: Várjunk kicsit, amíg a port ténylegesen felszabadul
setlocal EnableDelayedExpansion
set /a tries=0
:WAIT_PORT_FREE
set "HAS_LISTENER="
for /f "tokens=1" %%L in ('netstat -aon ^| findstr /R /C:":5000 .*LISTENING"') do (
    set "HAS_LISTENER=1"
)
if defined HAS_LISTENER (
    set /a tries+=1
    if !tries! GEQ 15 goto PORT_WAIT_DONE
    timeout /t 1 /nobreak >nul
    goto WAIT_PORT_FREE
)
:PORT_WAIT_DONE
endlocal

echo.
echo Flask szerver leállt!
echo Minden port felszabadítva.
echo.