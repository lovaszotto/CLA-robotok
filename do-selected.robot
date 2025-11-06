*** Settings ***
Library           OperatingSystem
Library    Process
Library    String
#Resource    resources/keywords.robot
Resource    ./resources/variables.robot

*** Variables ***



*** Test Cases ***
Kiírás konzolra paraméterekből
    [Documentation]    A kapott REPO és BRANCH változók értékeinek kiírása.
    Log To Console     \n=== KIVÁLASZTOTT ROBOT ===
    Set Global Variable    ${WORKFLOW_STATUS}    'STARTED'
    ${GIT_URL}=    Set Variable    ${GIT_URL_BASE}${REPO}.git
    Set Global Variable    ${GIT_URL}    ${GIT_URL}
    Log To Console     Repository: ${GIT_URL}
    Log To Console     Branch: ${BRANCH}
    #trash könyvtár létrehozása, ha nem létezik
    Create Directory    ${TRASH_DIR}
    Log To Console     =========================\n

Telepítettség és letöltöttség ellenőrzése
    [Documentation]    Ellenőrzi, hogy a robot már telepítve van-e (start.bat létezik), vagy csak letöltve
    Log To Console     \n=== TELEPÍTETTSÉG ÉS LETÖLTÖTTSÉG ELLENŐRZÉSE ===  ${WORKFLOW_STATUS}
    
    # Telepített robot ellenőrzése (start.bat létezik-e)
    ${START_SCRIPT}=    Set Variable    ${INSTALLED_ROBOTS}/${REPO}/${BRANCH}/start.bat
    ${start_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${START_SCRIPT}
    
    IF    ${start_script_exists}
        Log To Console     Robot már telepítve van: ${START_SCRIPT}
        Set Global Variable    ${WORKFLOW_STATUS}    'READY_TO_RUN'
    ELSE
        Log To Console     Robot nincs telepítve, ellenőrizzük a letöltöttséget...
        
        # Letöltött robot ellenőrzése
        IF        ${SANDBOX_MODE} == True
             ${REPO_PATH}=     Set Variable    ${SANDBOX_ROBOTS}/${REPO}
        ELSE
             ${REPO_PATH}=     Set Variable    ${DOWNLOADED_ROBOTS}/${REPO} 
        END
          
        ${BRANCH_PATH}=   Set Variable    ${REPO_PATH}/${BRANCH}
        Set Global Variable    ${REPO_PATH}    ${REPO_PATH}
        Set Global Variable    ${BRANCH_PATH}    ${BRANCH_PATH}

        Log To Console     Full Repository: ${REPO_PATH}
        Log To Console     Full Branch: ${BRANCH_PATH}
        #könyvtár létezésének ellenőrzése
        ${downloaded_repo_exists}=     Run Keyword And Return Status    OperatingSystem.Directory Should Exist     ${REPO_PATH}
        ${downloaded_robot_exists}=    Run Keyword And Return Status    OperatingSystem.Directory Should Exist    ${BRANCH_PATH}
        
        IF     ${downloaded_repo_exists} and ${downloaded_robot_exists}
            #visszatér a tesztből
            #todo verzió alapján újra letöltés
            Log To Console     Mindkét könyvtár létezik! 
          
            #töröljük a sandbox tartalmát és újratelepítjük
            IF    ${SANDBOX_MODE} == True
                Log To Console     Sandbox módban vagyunk, töröljük a könyvtárt:${REPO_PATH}
                Move Directory    ${BRANCH_PATH}         ${TRASH_DIR}        
                Set Global Variable    ${WORKFLOW_STATUS}    'MAKE_DIRS'
            ELSE
              Set Global Variable    ${WORKFLOW_STATUS}    'SET_UP_OK'
            END
        ELSE
             Log To Console     Könyvtárak nem léteznek! 
            Set Global Variable    ${WORKFLOW_STATUS}    'MAKE_DIRS'    
        END
    END

Könyvtárak létrehozása
    [Documentation]    Létrehozza a szükséges könyvtárakat, ha még nem léteznek.  
       #Log To Console     \n=== KÖNYVTÁRAK LÉTREHOZÁSA, ha 'MAKE_DIRS' === ${WORKFLOW_STATUS}
    IF    ${WORKFLOW_STATUS} == 'MAKE_DIRS'
        Log To Console     ======Könyvtár létrehozás====${WORKFLOW_STATUS}
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
    #Log To Console    \nBranch klónozása WORKFLOW_STATUS, ha 'TO_BE_CLONE' = ${WORKFLOW_STATUS}    
    IF    ${WORKFLOW_STATUS} == 'TO_BE_CLONE'
         Log To Console     ======KLONOZÁS GIT-BŐL=====${WORKFLOW_STATUS}
         IF    ${SANDBOX_MODE} == True
             ${TARGET_DIR}=    Set Variable    ${SANDBOX_ROBOTS}/${REPO}/${BRANCH}
        ELSE
             ${TARGET_DIR}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}
         END
         
        #${TARGET_DIR}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}
        Log To Console     \nGit parancs: git clone -b ${BRANCH} --single-branch ${GIT_URL} ${TARGET_DIR}
        
        # Git clone parancs futtatása felugró cmd ablakban
        Log To Console     Git clone futtatása új ablakban (automatikus bezárással)...
        ${result}=    Run Process    cmd    /c    start    /wait    cmd    /c    git clone -b ${BRANCH} --single-branch ${GIT_URL} ${TARGET_DIR}    shell=True    timeout=300s
        Run Keyword If    ${result.rc} != 0    Log To Console    Git clone nem sikerült (timeout vagy hiba), de folytatjuk: ${result.stderr}
        Run Keyword If    ${result.rc} == 0    Log To Console    Git clone sikeresen befejeződött
           IF    ${SANDBOX_MODE} == True
                Set Global Variable    ${WORKFLOW_STATUS}    'ALL_DONE'
           ELSE
                Set Global Variable    ${WORKFLOW_STATUS}    'CLONED'
            END
     END

Klónozás sikeresség ellenőrzése
   [Documentation]    A klónozás után ellenőrizzük, hogy létezik-e telepito.bat a most letöltött könyvtárban.
   #Log To Console     \n=== KLÓNOZÁS ELLENŐRZÉSE, ha 'CLONED' ===${WORKFLOW_STATUS}
   IF    ${WORKFLOW_STATUS} == 'CLONED'
       Log To Console     ======KLONOZÁS ELLENŐRZÉSE=====${WORKFLOW_STATUS}
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
    #Log To Console     \n=== TELEPÍTÉS FUTTATÁSA, ha 'CLONED_OK' ===${WORKFLOW_STATUS}
    IF    ${WORKFLOW_STATUS} == 'CLONED_OK'
           Log To Console     \n=== TELEPÍTÉS FUTTATÁSA===${WORKFLOW_STATUS}
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
   #Log To Console     \n=== TELEPÍTÉS ELLENŐRZÉSE, ha 'SET_UP_OK' ===${WORKFLOW_STATUS}
   IF    ${WORKFLOW_STATUS} == 'SET_UP_OK'
        Log To Console     \n=== TELEPÍTÉS ELLENŐRZÉSE == ${WORKFLOW_STATUS}
        ${START_SCRIPT}=    Set Variable    ${INSTALLED_ROBOTS}/${REPO}/${BRANCH}/start.bat
        Log To Console     Ellenőrzés: start.bat létezik-e az INSTALLED_ROBOTS könyvtárban? ${START_SCRIPT}

        ${start_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${START_SCRIPT}
        IF    ${start_script_exists}
            Log To Console     A telepítés sikeres volt, a start.bat megtalálható az INSTALLED_ROBOTS-ban: ${START_SCRIPT}
            Set Global Variable    ${WORKFLOW_STATUS}    'READY_TO_RUN'
        ELSE
            Log To Console     A telepítés sikertelen volt, a start.bat nem található az INSTALLED_ROBOTS könyvtárban:\n ${START_SCRIPT}
            Fail    A telepítés sikertelen volt, a start.bat nem található az INSTALLED_ROBOTS könyvtárban:\n ${START_SCRIPT}
        END
    END
    
Robot futtatása
  [Documentation]    Futtatjuk a start.bat fájlt, ha létezik.
  #Log To Console     \n=== ROBOT FUTTATÁSA, ha 'READY_TO_RUN' ===${WORKFLOW_STATUS}
  IF    ${WORKFLOW_STATUS} == 'READY_TO_RUN'    
      Log To Console     \n=== ROBOT FUTTATÁSA== ${WORKFLOW_STATUS} ==
      ${RUN_SCRIPT}=    Set Variable    ${INSTALLED_ROBOTS}/${REPO}/${BRANCH}/start.bat
      Log To Console     Robot futtatása az INSTALLED_ROBOTS könyvtárból: ${RUN_SCRIPT}

      # Külön szerver indítása - popup ablakban futtatás
      Log To Console     ${REPO}/${BRANCH} alkalmazás indítása külön popup ablakban...
      Log To Console     Robot script indítása: ${RUN_SCRIPT}
      
      # Popup ablakban futtatás - /k paraméter nyitva tartja az ablakot, /wait nélkül hogy ne várjon
      ${run_result}=    Run Process    cmd    /c    start    cmd    /k    ${RUN_SCRIPT}    shell=True    cwd=${INSTALLED_ROBOTS}/${REPO}/${BRANCH}    timeout=10s
      
      IF    ${run_result.rc} == 0
          Log To Console     ${REPO}/${BRANCH} alkalmazás sikeresen elindult popup ablakban
      ELSE
          Log To Console     ${REPO}/${BRANCH} alkalmazás indítása sikertelen: ${run_result.stderr}
      END
      
      Set Global Variable    ${WORKFLOW_STATUS}    'ALL_DONE'
      Log To Console    Robot indítása befejezve, a szerver a háttérben fut tovább    
    END
    Log To Console     \n=== MINDEN LÉPÉS BEFEJEZŐDÖTT ===
    Log To Console     WORKFLOW_STATUS = ${WORKFLOW_STATUS}