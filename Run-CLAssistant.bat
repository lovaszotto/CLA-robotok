@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Run-CLAssistant Indito Script
echo ========================================
echo.

REM Aktualis felhasznalo meghatározasa
set "actualUser=%USERNAME%"
echo Aktualis felhasznalo: %actualUser%
echo.

REM Telepitett CLA-ssistant konyvtar meghatározasa
set "myRobotPath=c:\users\%actualUser%\MyRobotFramework"
set "installedPath=%myRobotPath%\InstalledRobots\CLA-robotok\CLA-ssistant"

echo [1/3] Telepitett CLA-ssistant keresese...
echo Keresett hely: %installedPath%

REM Ellenorizzuk, hogy letezik-e a telepitett konyvtar
if not exist "%installedPath%" (
    echo   HIBA: CLA-ssistant nincs telepitve!
    echo   A telepitett konyvtar nem talalhato: %installedPath%
    echo.
    echo   Megoldasok:
    echo   1. Futtassa eloszor a Setup-CLAssistant.bat fajlt
    echo   2. Ellenorizze, hogy befejezodott-e a telepites
    echo   3. Ellenorizze a konyvtar strukturat
    echo.
    pause
    exit /b 1
)
echo   - CLA-ssistant telepitett konyvtar megtalálva
echo.

echo [2/3] start.bat fajl ellenorzese...
set "startBatPath=%installedPath%\start.bat"
if not exist "%startBatPath%" (
    echo   HIBA: start.bat nem talalhato!
    echo   Vart hely: %startBatPath%
    echo.
    echo   Megoldasok:
    echo   1. Futtassa ujra a Setup-CLAssistant.bat fajlt
    echo   2. Ellenorizze a telepitesi folyamat sikerességét
    echo.
    pause
    exit /b 1
)
echo   - start.bat megtalálva: %startBatPath%
echo.

echo [3/3] CLA-ssistant Flask szerver inditasa...
echo Valtás a telepitett konyvtarra: %installedPath%
echo.

REM Valtunk a telepitett konyvtarra es futtatjuk a start.bat-ot
cd /d "%installedPath%"
echo Aktualis munkakonyvtar: %CD%
echo.

echo ========================================
echo  CLA-ssistant Flask szerver inditasa...
echo ========================================
echo.

REM start.bat futtatasa
call "%startBatPath%"

REM Szerver leallitasa utan
echo.
echo ========================================
echo     CLA-ssistant leállt
echo ========================================
echo.
echo A Flask szerver leállt. Újraindításhoz futtassa újra ezt a scriptet.
echo.
pause
exit /b 0