@echo off
echo ================================================
echo      CLA Robot Kezelő - Flask Szerver
echo ================================================
echo.

:: Könyvtár váltás a script helyére
cd /d "%~dp0"

:: Python környezet ellenőrzése
echo [1/3] Python környezet ellenőrzése...
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe --version
if %errorlevel% neq 0 (
    echo HIBA: Python nem található!
    pause
    exit /b 1
)

:: Flask telepítettségének ellenőrzése
echo [2/3] Flask csomag ellenőrzése...
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe -c "import flask; print('Flask telepítve:', flask.__version__)"
if %errorlevel% neq 0 (
    echo Flask telepítése...
    C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe -m pip install flask
)

:: Repository adatok frissítése
echo [3/3] Repository adatok lekérése...
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe fetch_github_repos.py lovaszotto

echo.
echo ================================================
echo Flask szerver indítása...
echo A weboldal automatikusan megnyílik a böngészőben
echo ================================================
echo.
echo Szerver címe: http://localhost:5000
echo Leállításhoz nyomj CTRL+C-t
echo.

:: Flask szerver indítása
start "Robot Kezelő" http://localhost:5000
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe flask_app.py

:: Szerver leállítása után
echo.
echo Flask szerver leállt.
pause