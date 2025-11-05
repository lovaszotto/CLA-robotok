@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Setup-CLAssistant Telepito Script
echo ========================================
echo.

REM Aktualis felhasznalo meghatározasa
set "actualUser=%USERNAME%"
echo Aktualis felhasznalo: %actualUser%
echo.

REM c:\tmp konyvtar ellenorzese es letrehozasa
echo [1/7] c:\tmp konyvtar ellenorzese...
if not exist "c:\tmp" (
    echo   - c:\tmp konyvtar nem letezik, letrehozas...
    mkdir "c:\tmp" >nul 2>&1
    if errorlevel 1 (
        echo   HIBA: Nem sikerult letrehozni a c:\tmp konyvtarat!
        pause
        exit /b 1
    )
    echo   - c:\tmp konyvtar sikeresen letrehozva
) else (
    echo   - c:\tmp konyvtar mar letezik
)
echo.

REM MyRobotFramework fokonyvtar ellenorzese es letrehozasa
set "myRobotPath=c:\users\%actualUser%\MyRobotFramework"
echo [2/7] %myRobotPath% konyvtar ellenorzese...
if not exist "%myRobotPath%" (
    echo   - MyRobotFramework konyvtar nem letezik, letrehozas...
    mkdir "%myRobotPath%" >nul 2>&1
    if errorlevel 1 (
        echo   HIBA: Nem sikerult letrehozni a MyRobotFramework konyvtarat!
        pause
        exit /b 1
    )
    echo   - MyRobotFramework konyvtar sikeresen letrehozva
) else (
    echo   - MyRobotFramework konyvtar mar letezik
)
echo.

REM Alkonyvtarak letrehozasa
echo [3/7] Szukseges alkonyvtarak ellenorzese es letrehozasa...
set "subDirs=DownloadedRobots InstalledRobots SandboxRobots Kuka"
for %%d in (%subDirs%) do (
    set "dirPath=%myRobotPath%\%%d"
    if not exist "!dirPath!" (
        echo   - %%d konyvtar letrehozasa...
        mkdir "!dirPath!" >nul 2>&1
        if errorlevel 1 (
            echo   HIBA: Nem sikerult letrehozni a %%d konyvtarat!
            pause
            exit /b 1
        )
        echo   - %%d konyvtar sikeresen letrehozva
    ) else (
        echo   - %%d konyvtar mar letezik
    )
)
echo.

REM CLA-robotok konyvtar ellenorzese es letrehozasa
set "claRobotsPath=%myRobotPath%\DownloadedRobots\CLA-robotok"
echo [4/7] %claRobotsPath% konyvtar ellenorzese...
if not exist "%claRobotsPath%" (
    echo   - CLA-robotok konyvtar letrehozasa...
    mkdir "%claRobotsPath%" >nul 2>&1
    if errorlevel 1 (
        echo   HIBA: Nem sikerult letrehozni a CLA-robotok konyvtarat!
        pause
        exit /b 1
    )
    echo   - CLA-robotok konyvtar sikeresen letrehozva
) else (
    echo   - CLA-robotok konyvtar mar letezik
    echo   - Meglevo tartalom torlese...
    rd /s /q "%claRobotsPath%" >nul 2>&1
    mkdir "%claRobotsPath%" >nul 2>&1
)
echo.

REM Git ellenorzese
echo [5/7] Git letezesnek ellenorzese...
git --version >nul 2>&1
if errorlevel 1 (
    echo   HIBA: A Git nincs telepitve vagy nem elerheto!
    echo   Kerem telepitse a Git-et: https://git-scm.com/download/win
    pause
    exit /b 1
)
echo   - Git elerheto
echo.

REM Projekt letoltese GitHub-rol
echo [6/7] CLA-robotok projekt letoltese GitHub-rol...
echo   - Repository: https://github.com/lovaszotto/CLA-robotok
echo   - Branch: CLA-ssistant
echo   - Cel konyvtar: %claRobotsPath%
echo.

cd /d "%myRobotPath%\DownloadedRobots"
git clone -b CLA-ssistant https://github.com/lovaszotto/CLA-robotok.git >nul 2>&1
if errorlevel 1 (
    echo   HIBA: Nem sikerult letolteni a projektet!
    echo   Lehetseges okok:
    echo   - Nincs internetkapcsolat
    echo   - A repository nem elerheto
    echo   - Nincs jogosultsag a repository-hoz
    pause
    exit /b 1
)
echo   - Projekt sikeresen letoltve
echo.

REM telepito.bat futtatasa
echo [7/7] telepito.bat script futtatasa...
set "telepitoPath=%claRobotsPath%\telepito.bat"
if exist "%telepitoPath%" (
    echo   - telepito.bat megtalalva: %telepitoPath%
    echo   - Script inditasa...
    echo.
    cd /d "%claRobotsPath%"
    call "%telepitoPath%"
    if errorlevel 1 (
        echo.
        echo   FIGYELMEZETES: A telepito script hibakkal fejezodott be!
    ) else (
        echo.
        echo   - Telepites sikeresen befejezve
    )
) else (
    echo   HIBA: telepito.bat nem talalhato a letoltott projektben!
    echo   Vart hely: %telepitoPath%
    pause
    exit /b 1
)
echo.

echo ========================================
echo       Setup befejezve sikeresen!
echo ========================================
echo.
echo A CLA-robotok projekt telepitve lett ide:
echo %claRobotsPath%
echo.
echo Nyomjon meg egy billentyut a kilepes...
pause >nul
exit /b 0