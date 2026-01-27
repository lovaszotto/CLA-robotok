*** Variables ***
#verzió információ
${VERSION}    1.2.0
${BUILD_DATE}    2025-11-23 03:22:00    

# A git repository alap URL-je
${GIT_URL_BASE}           https://github.com/lovaszotto/

# A kiválasztott GIT_URL változó (dinamikusan állítjuk be)
${GIT_URL}        ${EMPTY}

# a kiválasztott cél könyvtár a klónozáshoz (dinamikusan állítjuk be)
${TARGET_DIR}    ${EMPTY}

# a kiválasztott repository a klónozáshoz (Flask-ból paraméterként kapjuk)
${REPO}           CPS-robotok
${REPO_PATH}      ${EMPTY}

# a kiválasztott branch a klónozáshoz (Flask-ból paraméterként kapjuk)
${BRANCH}    CPS-Mezo-ellenor
${BRANCH_PATH}    ${EMPTY}

# Felhasználó HOME könyvtárának dinamikus beállítása
# a gyökér könyvtár, ahol a robotok telepítve vannak
${ROOT_FOLDER}    ~/MyRobotFramework/


#developer módban csak letöltjük a robotokat, de nem telepítjük
${SANDBOX_MODE}         ${False}
${SANDBOX_ROBOTS}       %USERPROFILE%/MyRobotFramework/SandboxRobots


# A robotok letöltési könyvtárai
${DOWNLOADED_ROBOTS}    %USERPROFILE%/MyRobotFramework/DownloadedRobots

# A robotok log könyvtárai
${LOG_FILES}    %USERPROFILE%/MyRobotFramework/RobotResults
#aktuális log könyvtár (dinamikusan állítjuk be)
${CURRENT_LOG_DIR}

# Automatikus start.bat futtatás engedélyezése
${AUTO_LAUNCH_START_BAT}    ${True}


# A telepítési könyvtárai
${INSTALLED_ROBOTS}     ~/MyRobotFramework/InstalledRobots/


# A kuka könyvtár helye
${TRASH_DIR}            ~/MyRobotFramework/Trash/

# Python executable változó (dinamikusan meghatározva)
# Prioritási sorrend: 1. rf_env virtuális környezet, 2. rendszer python
${PYTHON_EXEC}        ${EMPTY}

# Állapot jelző státusz (dinamikusan állítjuk be)
${WORKFLOW_STATUS}         ${EMPTY}


