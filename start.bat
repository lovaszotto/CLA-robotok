@echo off
chcp 65001 >nul
echo ================================================
echo      CLA Robot Kezelo - Flask Szerver
echo ================================================
echo.

:: Konyvtar valtas a script helyere
cd /d "%~dp0"

:: Aktualis konyvtar kiirasa
echo Aktualis munkakonyvtar: %CD%
echo.

:: Virtualis kornyezet ellenorzese
echo [1/3] Virtualis kornyezet ellenorzese...

if not exist "rf_env\Scripts\python.exe" (
    echo HIBA: Virtualis kornyezet nem talalhato!
    echo Futtassa eloszor a telepito.bat fajlt!
    pause
    exit /b 1
)
rf_env\Scripts\python.exe --version

:: Flask telepitettsegének ellenorzese
echo [2/3] Flask csomag ellenorzese...
rf_env\Scripts\python.exe -c "import importlib.metadata; print('Flask telepitve:', importlib.metadata.version('flask'))"
if %errorlevel% neq 0 (
    echo Flask telepitese virtualis kornyezetbe...
    rf_env\Scripts\pip.exe install flask
)

:: Repository adatok frissitese
echo [3/3] Repository adatok lekerése...
rf_env\Scripts\python.exe fetch_github_repos.py lovaszotto

echo.
echo ================================================
echo Flask szerver inditasa...
echo A weboldal automatikusan megnyilik a bongeszoben
echo ================================================
echo.
echo Szerver cime: http://localhost:5000
echo Leallitashoz nyomj CTRL+C-t
echo.

:: Flask szerver inditasa
start "Robot Kezelo" http://localhost:5000
rf_env\Scripts\python.exe flask_app.py

:: Szerver leallitasa utan
echo.
echo Flask szerver leállt.
