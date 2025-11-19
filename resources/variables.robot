*** Variables ***
#verzió információ
${VERSION}    1.0.1
${BUILD_DATE}    2025-11-19 08:39:00    

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
${USER_HOME}    %{USERPROFILE}
# a gyökér könyvtár, ahol a robotok telepítve vannak
${ROOT_FOLDER}    ${USER_HOME}/MyRobotFramework/


#developer módban csak letöltjük a robotokat, de nem telepítjük
${SANDBOX_MODE}         ${False}
${SANDBOX_ROBOTS}       ${USER_HOME}/MyRobotFramework/SandboxRobots/


# A robotok letöltési könyvtárai
${DOWNLOADED_ROBOTS}    ${USER_HOME}/MyRobotFramework/DownloadedRobots/

# Automatikus start.bat futtatás engedélyezése
${AUTO_LAUNCH_START_BAT}    ${True}


# A telepítési könyvtárai
${INSTALLED_ROBOTS}     ${USER_HOME}/MyRobotFramework/InstalledRobots/


# A kuka könyvtár helye
${TRASH_DIR}            ${USER_HOME}/MyRobotFramework/Trash/

# Python executable változó (dinamikusan meghatározva)
# Prioritási sorrend: 1. rf_env virtuális környezet, 2. rendszer python
${PYTHON_EXEC}        ${EMPTY}

# Állapot jelző státusz (dinamikusan állítjuk be)
${WORKFLOW_STATUS}         ${EMPTY}
      
