@echo on
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

if not exist ".venv\Scripts\python.exe" (
    echo HIBA: Virtualis kornyezet nem talalhato!
    echo Futtassa eloszor a telepito.bat fajlt!
    pause
    exit /b 1
)
.venv\Scripts\python.exe --version
if %errorlevel% neq 0 (
    echo HIBA: Python nem indult el a virtualis kornyezetbol!
    pause
    exit /b 2
)

:: Flask telepitettsegének ellenorzese
echo [2/3] Flask csomag ellenorzese...
.venv\Scripts\python.exe -c "import importlib.metadata; print('Flask telepitve:', importlib.metadata.version('flask'))"
if %errorlevel% neq 0 (
    echo HIBA: Flask nincs telepitve vagy nem elerheto!
    echo Flask telepitese virtualis kornyezetbe...
    .venv\Scripts\pip.exe install flask
    if %errorlevel% neq 0 (
        echo HIBA: Flask telepitese sikertelen!
        pause
        exit /b 3
    )
)

:: Repository adatok frissitese
echo [3/3] Repository adatok lekerése...
.venv\Scripts\python.exe fetch_github_repos.py lovaszotto
if %errorlevel% neq 0 (
    echo HIBA: fetch_github_repos.py futtatasa sikertelen!
    pause
    exit /b 4
)

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
explorer http://localhost:5000
.venv\Scripts\python.exe flask_app.py
if %errorlevel% neq 0 (
    echo HIBA: flask_app.py futtatasa sikertelen!
    pause
    exit /b 5
)

:: Szerver leallitasa utan
echo.
echo Flask szerver leállt.
echo.

