@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ================================================
echo      CLA Robot Kezelo - Flask Szerver
echo ================================================
echo.

:: Konyvtar valtas a script helyere
cd /d "%~dp0"

:: Splash képernyő megnyitása azonnal (háttérkép látszódjon az inicializálás alatt is)
if exist "%~dp0splash.html" (
    start "CLA-ssistant" "%~dp0splash.html"
)

:: Inditas elott allitsuk le a korabbi peldanyokat (port 5000 felszabaditasa)
call "%~dp0stop.bat"

:: Aktualis konyvtar kiirasa
echo Aktualis munkakonyvtar: %CD%
echo.

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
    if exist "repos_response.json" (
        echo FIGYELEM: repo frissites sikertelen, de a meglévő repos_response.json alapján folytatjuk.
    ) else (
        echo HIBA: fetch_github_repos.py futtatasa sikertelen es nincs repos_response.json!
        pause
        exit /b 4
    )
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

:: Flask szerver inditasa (kulon ablakban, hogy ne alljon le a terminal bezarasakor)
if not exist "%~dp0splash.html" (
    explorer http://localhost:5000
)
start "Robot Kezelő - Flask" /MIN /D "%~dp0" "%~dp0.venv\Scripts\python.exe" "%~dp0flask_app.py"
if %errorlevel% neq 0 (
    echo HIBA: a Flask szerver inditasa sikertelen!
    pause
    exit /b 5
)

echo.
echo A szerver egy kulon ablakban fut.
echo Leallitashoz futtasd: stop.bat
echo.
exit /b 0

:: (A szerver most kulon ablakban fut, ide nem fog visszaterni.)

