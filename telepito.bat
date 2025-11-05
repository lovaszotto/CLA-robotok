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

REM Telepitesi konyvtar bekeres
echo Adja meg a telepitesi konyvtar eleresi utjat:
echo (pl: C:\DuplikacioEllenorzo vagy D:\MyProjects\DuplikacioSystem)
echo. 
REM Automatikus telepitesi konyvtar beallitasa: az aktualis folder nevében a DownloadedRobots kifejezést InstalledRobots-ra cseréljük
set "CURDIR=%CD%"
set "TARGET_DIR=%CURDIR:DownloadedRobots=InstalledRobots%"
echo [INFO] Alapértelmezett telepítési konyvtár: %TARGET_DIR%

REM Ha nem letezik a konyvtar, hozzuk letre
if not exist "%TARGET_DIR%" (
    echo [INFO] Telepitesi konyvtar letrehozasa: %TARGET_DIR%
    mkdir "%TARGET_DIR%"
)


echo.
echo Telepitesi cel: %TARGET_DIR%
echo.

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

REM Konyvtar letrehozasa ha nem letezik
if not exist "%TARGET_DIR%" (
    echo Konyvtar letrehozasa: %TARGET_DIR%
    mkdir "%TARGET_DIR%"
    if errorlevel 1 (
        echo HIBA: Nem sikerult letrehozni a konyvtarat!
        pause
        exit /b 1
    )
) else (
    echo Konyvtar mar letezik: %TARGET_DIR%
)

echo.
echo Fajlok masolasa...

REM CLA-ssistant robot fajlok masolasa

REM Fo robot fajl masolasa
copy "CLA-ssistant_main.robot" "%TARGET_DIR%\"

REM Python segédfájlok másolása
if exist "do-selected.robot" copy "do-selected.robot" "%TARGET_DIR%\"
if exist "fetch_github_repos.py" copy "fetch_github_repos.py" "%TARGET_DIR%\"
if exist "flask_app.py" copy "flask_app.py" "%TARGET_DIR%\"
if exist "parse_repos.py" copy "parse_repos.py" "%TARGET_DIR%\"
if exist "repository_branches_table.html" copy "repository_branches_table.html" "%TARGET_DIR%\"
if exist "repos_response.json" copy "repos_response.json" "%TARGET_DIR%\"
if exist "save_json_utf8.py" copy "save_json_utf8.py" "%TARGET_DIR%\"
if exist "start_with_robot.bat" copy "start_with_robot.bat" "%TARGET_DIR%\"
if exist "stop.bat" copy "stop.bat" "%TARGET_DIR%\"
if exist "log.html" copy "log.html" "%TARGET_DIR%\"
if exist "output.xml" copy "output.xml" "%TARGET_DIR%\"
if exist "report.html" copy "report.html" "%TARGET_DIR%\"
if exist "PIPE" copy "PIPE" "%TARGET_DIR%\"

REM Konfiguracios fajlok masolasa
if exist "start.bat" copy "start.bat" "%TARGET_DIR%\"

REM Markdown dokumentacio fajlok masolasa
if exist "README.md" copy "README.md" "%TARGET_DIR%\"

REM Setup script masolasa
if exist "Setup-CLAssistant.bat" copy "Setup-CLAssistant.bat" "%TARGET_DIR%\"

REM Libraries mappa masolasa
if exist "libraries" (
    echo Konyvtarak konyvtar masolasa...
    xcopy "libraries" "%TARGET_DIR%\libraries" /E /I /Y
)

REM Resources mappa masolasa
if exist "resources" (
    echo Eroforras konyvtar masolasa...
    xcopy "resources" "%TARGET_DIR%\resources" /E /I /Y
)

REM Tests mappa masolasa
if exist "tests" (
    echo Tests konyvtar masolasa...
    xcopy "tests" "%TARGET_DIR%\tests" /E /I /Y
)

REM Results mappa masolasa (ha van eredmeny)
if exist "results" (
    echo Results konyvtar masolasa...
    xcopy "results" "%TARGET_DIR%\results" /E /I /Y
)

REM __pycache__ mappa kihagyasa (Python cache fajlok)

echo Fajlok sikeresen masolva.

REM CLA-ssistant specifikus fajlok ellenorzese
echo CLA-ssistant fajlok ellenorzese...

if not exist "%TARGET_DIR%\CLA-ssistant_main.robot" (
    echo CLA-ssistant_main.robot hianyzo, ujra letrehozas...
    copy "CLA-ssistant_main.robot" "%TARGET_DIR%\"
)

if not exist "%TARGET_DIR%\fetch_github_repos.py" (
    echo fetch_github_repos.py hianyzo, ujra letrehozas...
    copy "fetch_github_repos.py" "%TARGET_DIR%\"
)

if not exist "%TARGET_DIR%\parse_repos.py" (
    echo parse_repos.py hianyzo, ujra letrehozas...
    copy "parse_repos.py" "%TARGET_DIR%\"
)

REM Results konyvtar letrehozasa
if not exist "%TARGET_DIR%\results" (
    echo Results konyvtar letrehozasa...
    mkdir "%TARGET_DIR%\results"
)

echo.

REM Atlepunk a cel konyvtarba
cd /d "%TARGET_DIR%"

REM Virtualis kornyezet letrehozasa
echo Virtualis kornyezet letrehozasa...
if not exist "rf_env" (
    python -m venv rf_env
    if errorlevel 1 (
        echo HIBA: Virtualis kornyezet letrehozasa sikertelen!
        pause
        exit /b 1
    )
    echo Virtualis kornyezet sikeresen letrehozva.
) else (
    echo Virtualis kornyezet mar letezik.
)
echo.

REM Virtualis kornyezet aktivalasa es csomagok telepitese
echo CLA-ssistant csomagok telepitese...
REM rf_env\Scripts\activate (nem szükséges, pip elérési út miatt)
rf_env\Scripts\pip.exe install --upgrade pip
rf_env\Scripts\pip.exe install robotframework
rf_env\Scripts\pip.exe install robotframework-seleniumlibrary
rf_env\Scripts\pip.exe install requests
rf_env\Scripts\pip.exe install flask
rf_env\Scripts\pip.exe install selenium
rf_env\Scripts\pip.exe install webdriver-manager

if errorlevel 1 (
    echo HIBA: Csomagok telepitese sikertelen!
    pause
    exit /b 1
)


echo.
echo =========================================
echo CLA-SSISTANT TELEPITES SIKERES!
echo.
echo Telepitesi hely: %TARGET_DIR%
echo.
echo Telepitett komponensek:
echo - Robot Framework (automatizalasi keretrendszer)
echo - Selenium Library (weboldal automatizalas)
echo - Requests (HTTP API kliensek)
echo - Flask (webes szerver)
echo - Selenium WebDriver (bongeszo vezerlese)
echo - WebDriver Manager (driver automatikus kezeles)
echo - CLA-ssistant robot fajlok
echo - GitHub API Python scriptek
echo - Repository kezelo eszkozok
echo - start.bat futtato script
echo.
echo Hasznalat:
echo 1. Konzol modu: Menjen a telepitesi konyvtarba: %TARGET_DIR%
echo    Es futtassa: start.bat
echo 2. Python script modu: 
echo    rf_env\Scripts\python.exe fetch_github_repos.py lovaszotto
echo    rf_env\Scripts\python.exe parse_repos.py
echo.
echo Konfiguracio: 
echo - GitHub repository tulajdonos: lovaszotto
echo - Fo robot fajl: CLA-ssistant_main.robot
echo - Python segédfájlok: fetch_github_repos.py, parse_repos.py
echo - Eredmenyek: results\ konyvtar
echo - Dokumentacio: README.md
echo.
echo Repository kezeles: CLA-ssistant_main.robot
echo =========================================
echo.
echo github_api.bat fajl letrehozasa GitHub API inditashoz...

REM github_api.bat fajl letrehozasa
echo @echo off > github_api.bat
echo REM ========================================= >> github_api.bat
echo REM  CLA-SSISTANT - GITHUB API KEZELO >> github_api.bat
echo REM ========================================= >> github_api.bat
echo echo. >> github_api.bat
echo echo ========================================= >> github_api.bat
echo echo   GITHUB REPOSITORY LISTA LEKERES >> github_api.bat
echo echo   API Owner: lovaszotto >> github_api.bat
echo echo ========================================= >> github_api.bat
echo echo. >> github_api.bat
echo. >> github_api.bat
echo echo GitHub repository lista lekerese... >> github_api.bat
echo rf_env\Scripts\python.exe fetch_github_repos.py lovaszotto >> github_api.bat
echo echo. >> github_api.bat
echo echo Repository-k es branch-ek feldolgozasa... >> github_api.bat
echo rf_env\Scripts\python.exe parse_repos.py >> github_api.bat
echo echo. >> github_api.bat
echo echo Eredmeny HTML generalva: repository_branches_table.html >> github_api.bat
echo pause >> github_api.bat

echo.
echo =========================================
echo TELEPITES BEFEJEZVE - start.bat INDITAS
echo =========================================
echo.

REM start.bat automatikus inditasa
if exist "start.bat" (
    echo start.bat megtalalva, automatikus inditas...
    echo CLA-ssistant Flask szerver inditasa...
    echo.
    call "start.bat"
) else (
    echo FIGYELMEZETES: start.bat nem talalhato!
    echo Manualis inditashoz futtassa: start.bat
    pause
)


