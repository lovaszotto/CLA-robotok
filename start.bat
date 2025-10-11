@echo off
chcp 65001 >nul
echo ================================================
echo      CLA Robot Kezelo - Flask Szerver
echo ================================================
echo.

:: Konyvtar valtas a script helyere
cd /d "%~dp0"

:: Python kornyezet ellenorzese
echo [1/3] Python kornyezet ellenorzese...
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe --version
if %errorlevel% neq 0 (
    echo HIBA: Python nem talalhato!
    pause
    exit /b 1
)

:: Flask telepitettsegének ellenorzese
echo [2/3] Flask csomag ellenorzese...
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe -c "import flask; print('Flask telepitve:', flask.__version__)"
if %errorlevel% neq 0 (
    echo Flask telepitese...
    C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe -m pip install flask
)

:: Repository adatok frissitese
echo [3/3] Repository adatok lekerése...
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe fetch_github_repos.py lovaszotto

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
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe flask_app.py

:: Szerver leallitasa utan
echo.
echo Flask szerver leállt.
pause