@echo off
REM =====================================================
REM  CLA-SSISTANT TELEPITO v3.0
REM  GitHub Repository kezelő Robot Framework rendszer
REM  Automatizált Git műveletek és repository kezelés
REM =====================================================
setlocal EnableDelayedExpansion

echo.
echo =====================================================
echo   CLA-SSISTANT TELEPITO v3.0
echo   
echo   Funkcionalitas:
echo   - GitHub repository letoltes es kezeles
echo   - Robot Framework automatizacio  
echo   - Git parancsok vezerles
echo   - Web interfesz tamogatas
echo   - Repository lista lekeres API-val
echo =====================================================
echo.


REM Automatikus telepitesi konyvtar beallitasa: az aktualis folder nevében a DownloadedRobots kifejezést InstalledRobots-ra cseréljük
set "CURDIR=%CD%"
echo [INFO] Alapértelmezett telepítési konyvtár: %TARGET_DIR%


REM Ellenorizzuk a Python megletet es verziot
echo Python verzio ellenorzese...
python --version >nul 2>&1
if errorlevel 1 (
    echo HIBA: Python nincs telepitve vagy nem elerheto a PATH-ban!
    echo.
    echo Megoldasok:
    echo 1. Telepitse a Python 3.8+ verzioit a python.org oldalrol
    echo 2. Vagy hasznaja az Install\python-3.13.7-amd64.exe fajlt
    echo 3. Adja hoza a Python-t a rendszer PATH valtozojához
    echo.
    pause
    exit /b 1
)

echo Python verzio:
python --version

REM Python verzió ellenőrzés (3.8+ ajánlott)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Talalt Python verzio: %PYTHON_VERSION%

echo.
echo Python modullok ellenorzese...
python -c "import sys; print('Python executable:', sys.executable)"
echo.

REM Virtualis kornyezet letrehozasa
echo Virtualis kornyezet letrehozasa...
if not exist ".venv" (
    python -m venv .venv
    if errorlevel 1 (
        echo HIBA: Virtualis kornyezet letrehozasa sikertelen!
        pause
        exit  1
    )
    echo Virtualis kornyezet sikeresen letrehozva.
) else (
    echo Virtualis kornyezet mar letezik.
)
echo.

REM Virtualis kornyezet aktivalasa es csomagok telepitese
echo CLA-ssistant csomagok telepitese...
REM .venv\Scripts\activate (nem szükséges, pip elérési út miatt)
rem .venv\Scripts\pip.exe install --upgrade pip
.venv\Scripts\pip.exe install robotframework
.venv\Scripts\pip.exe install robotframework-seleniumlibrary
.venv\Scripts\pip.exe install requests
.venv\Scripts\pip.exe install flask
.venv\Scripts\pip.exe install selenium
.venv\Scripts\pip.exe install webdriver-manager

if errorlevel 1 (
    echo HIBA: Csomagok telepitese sikertelen!
    pause
    exit  1
)

echo.
echo =========================================
echo CLA-SSISTANT TELEPITES SIKERES!
echo.
echo Telepitesi hely: %TARGET_DIR%
echo.
exit 0


