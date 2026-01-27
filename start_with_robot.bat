@echo off
echo ================================================
echo   CLA Robot Kezelő - Teljes Inicializálás
echo ================================================
echo.

:: Könyvtár váltás a script helyére
cd /d "%~dp0"

:: Opcionális GitHub token betöltése (rate limit elkerüléséhez)
:: Hozz létre egy github_token.txt fájlt a mappában, és az első sorba írd a tokened.
if not defined GITHUB_TOKEN (
    if exist "github_token.txt" (
        set /p GITHUB_TOKEN=<"github_token.txt"
    )
)
if not defined GH_TOKEN (
    if defined GITHUB_TOKEN (
        set "GH_TOKEN=%GITHUB_TOKEN%"
    )
)

:: 1. Robot Framework teszt futtatása
echo [1/4] Robot Framework teszt futtatása...
robot CLA-Developer.robot
if %errorlevel% neq 0 (
    echo FIGYELEM: Robot Framework teszt hibával zárult!
    echo Folytatás...
)

:: 2. Python környezet ellenőrzése
echo [2/4] Python környezet ellenőrzése...
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe --version
if %errorlevel% neq 0 (
    echo HIBA: Python nem található!
    pause
    exit /b 1
)

:: 3. Flask telepítettségének ellenőrzése
echo [3/4] Függőségek ellenőrzése...
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe -c "import importlib.metadata; print('Flask telepítve:', importlib.metadata.version('flask'))"
if %errorlevel% neq 0 (
    echo Flask telepítése...
    C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe -m pip install flask
)

:: 4. Repository adatok frissítése
echo [4/4] Repository adatok frissítése...
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe fetch_github_repos.py lovaszotto

echo.
echo ================================================
echo Minden elkészült! Flask szerver indítása...
echo ================================================
echo.
echo - Robot Framework teszt lefutott
echo - HTML fájl generálva
echo - Repository adatok frissítve  
echo - Flask szerver indul...
echo.
echo Szerver címe: http://localhost:5000
echo Leállításhoz nyomj CTRL+C-t
echo.

:: Weboldal megnyitása és Flask szerver indítása
start "CLA Robot Kezelő" http://localhost:5000
C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe flask_app.py

:: Szerver leállítása után
echo.
echo Flask szerver leállt.
pause