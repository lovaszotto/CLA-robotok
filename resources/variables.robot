*** Variables ***
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

# A robotok letöltési könyvtárai
${DOWNLOADED_ROBOTS}    c:/Users/oLovasz/MyRobotFramework/TestDownloadedRobots/

# A telepítési könyvtárai
${INSTALLED_ROBOTS}     c:/Users/oLovasz/MyRobotFramework/TestInstalledRobots/

# Python executable változó (Robot Framework környezetben)
${PYTHON_EXEC}        C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe

# Állapot jelző státusz (dinamikusan állítjuk be)
${WORKFLOW_STATUS}         ${EMPTY}
      