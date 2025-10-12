*** Settings ***
Library           OperatingSystem
Library    Process
Library    String
#Resource    resources/keywords.robot
Resource    ./resources/variables.robot

*** Variables ***



*** Test Cases ***
Kiírás konzolra paraméterekből
    [Documentation]    A REPO és BRANCH változók értékeinek kiírása.
    Log To Console     \n=== KIVÁLASZTOTT ROBOT ===
    Set Global Variable    ${WORKFLOW_STATUS}    'STARTED'
    ${GIT_URL}=    Set Variable    ${GIT_URL_BASE}${REPO}.git
    Set Global Variable    ${GIT_URL}    ${GIT_URL}
    Log To Console     Repository: ${GIT_URL}
    Log To Console     Branch: ${BRANCH}
    Log To Console     =========================\n
Letöltöttség ellenőrzése
    [Documentation]    Ellenőrzi, hogy a REPO és BRANCH ban megadott értékekhez létezik-e mappa.
    Log To Console     \n=== LETÖLTÖTTSÉG ELLENŐRZÉSE ===  ${WORKFLOW_STATUS}
    ${REPO_PATH}=     Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}    
    ${BRANCH_PATH}=   Set Variable    ${REPO_PATH}/${BRANCH}
    Set Global Variable    ${REPO_PATH}    ${REPO_PATH}
    Set Global Variable    ${BRANCH_PATH}    ${BRANCH_PATH}

    Log To Console     Full Repository: ${REPO_PATH}
    Log To Console     Full Branch: ${BRANCH_PATH}
    #könyvtár létezésének ellenőrzése
    Set Global Variable    ${WORKFLOW_STATUS}    STARTED
    ${downloaded_repo_exists}=     Run Keyword And Return Status    OperatingSystem.Directory Should Exist     ${REPO_PATH}
    ${downloaded_robot_exists}=    Run Keyword And Return Status    OperatingSystem.Directory Should Exist    ${BRANCH_PATH}
    
    IF     ${downloaded_repo_exists} and ${downloaded_robot_exists}
        #visszatér a tesztből
        #todo verzió alapján újra letöltés
        Log To Console     Mindkét könyvtár létezik! 
        Set Global Variable    ${WORKFLOW_STATUS}    'CLONED'
    ELSE
         Log To Console     Könyvtárak nem léteznek! 
        Set Global Variable    ${WORKFLOW_STATUS}    'MAKE_DIRS'    
    END

Könyvtárak létrehozása
    [Documentation]    Létrehozza a szükséges könyvtárakat, ha még nem léteznek.  
       Log To Console     \n=== KÖNYVTÁRAK LÉTREHOZÁSA, ha 'MAKE_DIRS' === ${WORKFLOW_STATUS}
    IF    ${WORKFLOW_STATUS} == 'MAKE_DIRS'
        Log To Console     ======Könyvtár létrehozás===================
        #létrehozzuk a repository könyvtárat, ha nem létezik
        Create Directory    ${REPO_PATH}
        Log To Console     Létrehozva a repository könyvtár: ${REPO_PATH}
        #létrehozzuk a branch könyvtárat, ha nem létezik
        Create Directory    ${BRANCH_PATH}
        Log To Console     Létrehozva a branch könyvtár: ${BRANCH_PATH}
        
        # Klónozáshoz szükséges változók újbóli beállítása (biztonsági okokból)
        ${GIT_URL}=    Set Variable    ${GIT_URL_BASE}${REPO}.git
        Set Global Variable    ${GIT_URL}    ${GIT_URL}
        Log To Console     Globálisan beállítva: GIT_URL = ${GIT_URL}

        #Set Global Variable    ${BRANCH}    ${BRANCH}
        Log To Console     Globálisan beállítva: BRANCH = ${BRANCH}
        ${TARGET_DIR}=    Set Global Variable    ${BRANCH_PATH}
        Log To Console     TARGET_DIR = ${TARGET_DIR}

        Set Global Variable    ${WORKFLOW_STATUS}    'TO_BE_CLONE'
   END
    
Branch klónozása
    [Documentation]    A REPO és BRANCH változók alapján klónozza a megfelelő könyvtárat, ha még nincs letöltve.
    Log To Console    \nBranch klónozása WORKFLOW_STATUS, ha 'TO_BE_CLONE' = ${WORKFLOW_STATUS}    
    IF    ${WORKFLOW_STATUS} == 'TO_BE_CLONE'
        ${TARGET_DIR}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}
        Log To Console     \nGit parancs: git clone -b ${BRANCH} --single-branch ${GIT_URL} ${TARGET_DIR}
        
        # Git clone parancs futtatása felugró cmd ablakban
        Log To Console     Git clone futtatása új ablakban (automatikus bezárással)...
        ${result}=    Run Process    cmd    /c    start    /wait    cmd    /c    git clone -b ${BRANCH} --single-branch ${GIT_URL} ${TARGET_DIR}    shell=True    timeout=300s
        Run Keyword If    ${result.rc} != 0    Log To Console    Git clone nem sikerült (timeout vagy hiba), de folytatjuk: ${result.stderr}
        Run Keyword If    ${result.rc} == 0    Log To Console    Git clone sikeresen befejeződött
        Set Global Variable    ${WORKFLOW_STATUS}    'CLONED'
     END

Klónozás sikeresség ellenőrzése
   [Documentation]    A klónozás után ellenőrizzük, hogy létezik-e telepit.bat a most letöltött könyvtárban.
   Log To Console     \n=== KLÓNOZÁS ELLENŐRZÉSE, ha 'CLONED' ===${WORKFLOW_STATUS}
   IF    ${WORKFLOW_STATUS} == 'CLONED'
       Log To Console   DOWNLOADED_ROBOTS:${DOWNLOADED_ROBOTS}
       Log To Console    REPO:${REPO}
       Log To Console    BRANCH:${BRANCH}

        ${INSTALL_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/telepito.bat
        Log To Console     Ellenőrzés: telepit.bat létezik-e? ${INSTALL_SCRIPT}

        ${install_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${INSTALL_SCRIPT}
        IF    ${install_script_exists}
            Log To Console     A klónozás sikeres volt, a telepit.bat megtalálható: ${INSTALL_SCRIPT}
            Set Global Variable    ${WORKFLOW_STATUS}    'CLONED_OK'
        ELSE
            Log To Console     A klónozás sikertelen volt, a telepit.bat nem található:\n ${INSTALL_SCRIPT}
            Fail    A klónozás sikertelen volt, a telepit.bat nem található:\n ${INSTALL_SCRIPT}
        END
    END

Telepítés futtatása
    [Documentation]    A klónozás után futtatjuk a telepit.bat fájlt.
    Log To Console     \n=== TELEPÍTÉS FUTTATÁSA, ha 'CLONED_OK' ===${WORKFLOW_STATUS}
    IF    ${WORKFLOW_STATUS} == 'CLONED_OK'
         Log To Console   DOWNLOADED_ROBOTS:${DOWNLOADED_ROBOTS}
         Log To Console    REPO:${REPO}
         Log To Console    BRANCH:${BRANCH}
    
          ${INSTALL_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/telepito.bat
          Log To Console     Telepítés indítása: ${INSTALL_SCRIPT}
        
          # Felugró ablakban futtatás - cmd /c start paranccsal új ablakot nyit, /c bezárja a lefutás után
          Log To Console     Telepítő script futtatása új ablakban (automatikus bezárással)...
          ${install_result}=    Run Process    cmd    /c    start    /wait    cmd    /c    ${INSTALL_SCRIPT}    shell=True    cwd=${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}    timeout=120s
          IF    ${install_result.rc} != 0    
              Log To Console    Telepítés nem sikerült (timeout vagy hiba): ${install_result.stderr}
              Fail    A telepítés sikertelen volt, a telepito.bat nem található:\n ${INSTALL_SCRIPT}
          END

          IF    ${install_result.rc} == 0    
              Log To Console    Telepítés sikeresen befejeződött: ${INSTALL_SCRIPT}
              Set Global Variable    ${WORKFLOW_STATUS}    'SET_UP_OK'
          END
      END

Telepítés sikeresség ellenőrzése
   [Documentation]    A telepítés után ellenőrizzük, hogy létezik-e start.bat a most letöltött könyvtárban.
   Log To Console     \n=== TELEPÍTÉS ELLENŐRZÉSE, ha 'SET_UP_OK' ===${WORKFLOW_STATUS}
   IF    ${WORKFLOW_STATUS} == 'SET_UP_OK'

        ${INSTALL_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/start.bat
        Log To Console     Ellenőrzés: start.bat létezik-e? ${INSTALL_SCRIPT}

        ${install_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${INSTALL_SCRIPT}
        IF    ${install_script_exists}
            Log To Console     A klónozás sikeres volt, a telepit.bat megtalálható: ${INSTALL_SCRIPT}
            Set Global Variable    ${WORKFLOW_STATUS}    'READY_TO_RUN'
        ELSE
            Log To Console     A klónozás sikertelen volt, a start.bat nem található:\n ${INSTALL_SCRIPT}
            Fail    A telepítés sikertelen volt, a start.bat nem található:\n ${INSTALL_SCRIPT}
        END
    END
    
Robot futtatása
  [Documentation]    Futtatjuk a start.bat fájlt, ha létezik.
  Log To Console     \n=== ROBOT FUTTATÁSA, ha 'READY_TO_RUN' ===${WORKFLOW_STATUS}
  IF    ${WORKFLOW_STATUS} == 'READY_TO_RUN'    
      ${RUN_SCRIPT}=    Set Variable    ${INSTALLED_ROBOTS}/${REPO}/${BRANCH}/start.bat
      Log To Console     Robot futtatása: ${RUN_SCRIPT}

      # Felugró ablakban futtatás - cmd /c start paranccsal új ablakot nyit, /c bezárja a lefutás után
      Log To Console     Robot script futtatása új ablakban (automatikus bezárással)...
      ${run_result}=    Run Process    cmd    /c    start    /wait    cmd    /c    ${RUN_SCRIPT}    shell=True    cwd=${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}    timeout=300s
      IF    ${run_result.rc} != 0    
          Log To Console    Robot futtatás nem sikerült (timeout vagy hiba): ${run_result.stderr}
          Fail    A robot futtatás sikertelen volt, a start.bat nem található:\n ${RUN_SCRIPT}
      END

      IF    ${run_result.rc} == 0    
          Log To Console    Robot futtatás sikeresen befejeződött: ${RUN_SCRIPT}
          Set Global Variable    ${WORKFLOW_STATUS}    'ALL_DONE'
      END    
    END
    Log To Console     \n=== MINDEN LÉPÉS BEFEJEZŐDÖTT ===
    Log To Console     WORKFLOW_STATUS = ${WORKFLOW_STATUS}