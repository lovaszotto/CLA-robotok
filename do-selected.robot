*** Settings ***
Library           OperatingSystem
Library    Process
Library    String
Resource    ./resources/keywords.robot
Resource    ./resources/variables.robot

*** Variables ***

*** Keywords ***
Feloldott könyvtár változók
    ${DOWNLOADED_ROBOTS}=    Expand Environment Variables    ${DOWNLOADED_ROBOTS}
    Set Suite Variable    ${DOWNLOADED_ROBOTS}
    ${SANDBOX_ROBOTS}=       Expand Environment Variables    ${SANDBOX_ROBOTS}
    Set Suite Variable    ${SANDBOX_ROBOTS}




*** Test Cases ***
    Feloldott könyvtár változók
Kiírás konzolra paraméterekből
    # Dinamikus könyvtár változók beállítása a környezeti USERPROFILE alapján
    ${USERPROFILE}=    Get Environment Variable    USERPROFILE
    ${DOWNLOADED_ROBOTS}=    Set Variable    ${USERPROFILE}/MyRobotFramework/DownloadedRobots
    ${SANDBOX_ROBOTS}=       Set Variable    ${USERPROFILE}/MyRobotFramework/SandboxRobots
    Set Suite Variable    ${DOWNLOADED_ROBOTS}
    Set Suite Variable    ${SANDBOX_ROBOTS}
    Set Suite Variable    ${DOWNLOADED_ROBOTS}
    Set Suite Variable    ${SANDBOX_ROBOTS}
    [Documentation]    A kapott REPO és BRANCH változók értékeinek kiírása.
    Log Everywhere     \n=== KIVÁLASZTOTT ROBOT ===
    Log Everywhere     [DEBUG] SANDBOX_MODE értéke: ${SANDBOX_MODE}
    Set Global Variable    ${WORKFLOW_STATUS}    'STARTED'
    ${GIT_URL}=    Set Variable    ${GIT_URL_BASE}${REPO}.git
    Set Global Variable    ${GIT_URL}    ${GIT_URL}
    Log Everywhere     Repository: ${GIT_URL}
    Log Everywhere     Branch: ${BRANCH}
    #trash könyvtár létrehozása, ha nem létezik
    Create Directory    ${TRASH_DIR}
    Log Everywhere     =========================\n

Telepítettség és letöltöttség ellenőrzése
    [Documentation]    Ellenőrzi, hogy a robot már telepítve van-e (start.bat létezik), vagy csak letöltve
    Log Everywhere     \n=== TELEPÍTETTSÉG ÉS LETÖLTÖTTSÉG ELLENŐRZÉSE === (${WORKFLOW_STATUS})
    
    # Telepített robot ellenőrzése (start.bat létezik-e)
    ${START_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/start.bat
    ${start_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${START_SCRIPT}
    
    IF    ${start_script_exists}
        Log Everywhere     Robot már telepítve van: ${START_SCRIPT}
        Set Global Variable    ${WORKFLOW_STATUS}    'READY_TO_RUN'
    ELSE
        Log Everywhere     Robot nincs telepítve, ellenőrizzük a letöltöttséget...
        
        # Letöltött robot ellenőrzése
        IF        ${SANDBOX_MODE} == True
             ${REPO_PATH}=     Set Variable    ${SANDBOX_ROBOTS}/${REPO}
        ELSE
             ${REPO_PATH}=     Set Variable    ${DOWNLOADED_ROBOTS}/${REPO} 
        END
          
        ${BRANCH_PATH}=   Set Variable    ${REPO_PATH}/${BRANCH}
        Set Global Variable    ${REPO_PATH}    ${REPO_PATH}
        Set Global Variable    ${BRANCH_PATH}    ${BRANCH_PATH}

        Log Everywhere     Full Repository: ${REPO_PATH}
        Log Everywhere     Full Branch: ${BRANCH_PATH}
        #könyvtár létezésének ellenőrzése
        ${downloaded_repo_exists}=     Run Keyword And Return Status    OperatingSystem.Directory Should Exist     ${REPO_PATH}
        ${downloaded_robot_exists}=    Run Keyword And Return Status    OperatingSystem.Directory Should Exist    ${BRANCH_PATH}
        
        IF     ${downloaded_repo_exists} and ${downloaded_robot_exists}
            #visszatér a tesztből
            #todo verzió alapján újra letöltés
            Log Everywhere     Mindkét könyvtár létezik! 
          
            #töröljük a sandbox tartalmát és újratelepítjük
            IF    ${SANDBOX_MODE} == True
                Log Everywhere     Sandbox módban vagyunk, töröljük a könyvtárt:${REPO_PATH}
                Move Directory    ${BRANCH_PATH}         ${TRASH_DIR}        
                Set Global Variable    ${WORKFLOW_STATUS}    'MAKE_DIRS'
            ELSE
              Log Everywhere     Letöltött branch frissítése (git pull) szükséges
              Set Global Variable    ${WORKFLOW_STATUS}    'TO_BE_PULL'
            END
        ELSE
             Log Everywhere     Könyvtárak nem léteznek! 
            Set Global Variable    ${WORKFLOW_STATUS}    'MAKE_DIRS'    
        END
    END

Könyvtárak létrehozása
    [Documentation]    Létrehozza a szükséges könyvtárakat, ha még nem léteznek.  
       #Log To Console     \n=== KÖNYVTÁRAK LÉTREHOZÁSA, ha 'MAKE_DIRS' === ${WORKFLOW_STATUS}
    IF    ${WORKFLOW_STATUS} == 'MAKE_DIRS'
        Log Everywhere     ======Könyvtár létrehozás==== (${WORKFLOW_STATUS})
        #létrehozzuk a repository könyvtárat, ha nem létezik
        Create Directory    ${REPO_PATH}
        Log Everywhere     Létrehozva a repository könyvtár: ${REPO_PATH}
        #létrehozzuk a branch könyvtárat, ha nem létezik
        Create Directory    ${BRANCH_PATH}
        Log Everywhere     Létrehozva a branch könyvtár: ${BRANCH_PATH}
        
        # Klónozáshoz szükséges változók újbóli beállítása (biztonsági okokból)
        ${GIT_URL}=    Set Variable    ${GIT_URL_BASE}${REPO}.git
        Set Global Variable    ${GIT_URL}    ${GIT_URL}
        Log Everywhere     Globálisan beállítva: GIT_URL = ${GIT_URL}

        #Set Global Variable    ${BRANCH}    ${BRANCH}
        Log Everywhere     Globálisan beállítva: BRANCH = ${BRANCH}
        ${TARGET_DIR}=    Set Global Variable    ${BRANCH_PATH}
        Log Everywhere     TARGET_DIR = ${TARGET_DIR}

        Set Global Variable    ${WORKFLOW_STATUS}    'TO_BE_CLONE'
   END
    
Branch klónozása
    [Documentation]    A REPO és BRANCH változók alapján klónozza a megfelelő könyvtárat, ha még nincs letöltve.
    #Log To Console    \nBranch klónozása WORKFLOW_STATUS, ha 'TO_BE_CLONE' = ${WORKFLOW_STATUS}    
        IF    ${WORKFLOW_STATUS} == 'TO_BE_CLONE'
            Log Everywhere     ======KLONOZÁS GIT-BŐL===== (${WORKFLOW_STATUS})
            IF    ${SANDBOX_MODE} == True
               ${TARGET_DIR}=    Set Variable    ${SANDBOX_ROBOTS}/${REPO}/${BRANCH}
           ELSE
               ${TARGET_DIR}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}
            END
         
           Log Everywhere     [GIT KLÓNOZÁS] Forrás: ${GIT_URL}
           Log Everywhere     [GIT KLÓNOZÁS] Branch: ${BRANCH}
           Log Everywhere     [GIT KLÓNOZÁS] Cél könyvtár: ${TARGET_DIR}
           Log Everywhere     [GIT KLÓNOZÁS] Parancs: git clone -b ${BRANCH} --single-branch ${GIT_URL} ${TARGET_DIR}

           # Git clone parancs futtatása (kimenet rögzítése)
           ${result}=    Run Process    git    clone    -b    ${BRANCH}    --single-branch    ${GIT_URL}    ${TARGET_DIR}    shell=True    timeout=300s
           Log Everywhere     [GIT KLÓNOZÁS] rc: ${result.rc}
           Log Everywhere     [GIT KLÓNOZÁS] stdout: ${result.stdout}
           Log Everywhere     [GIT KLÓNOZÁS] stderr: ${result.stderr}
           Run Keyword If    ${result.rc} != 0    Fail    Git clone sikertelen: ${result.stderr}
           Run Keyword If    ${result.rc} == 0    Log To Console    Git clone sikeresen befejeződött
             IF    ${SANDBOX_MODE} == True
                 Set Global Variable    ${WORKFLOW_STATUS}    'ALL_DONE'
             ELSE
                 Set Global Variable    ${WORKFLOW_STATUS}    'CLONED'
              END
        END

Letöltött branch frissítése
        [Documentation]    Ha a letöltött könyvtár már létezik, futtatunk egy git pull-t frissítéshez.
        IF    ${WORKFLOW_STATUS} == 'TO_BE_PULL'
           Log Everywhere     ======GIT PULL FUTTATÁSA===== (${WORKFLOW_STATUS})
           Log Everywhere     [GIT PULL] Könyvtár: ${BRANCH_PATH}
           ${pull_result}=    Run Process    git    -C    ${BRANCH_PATH}    pull    shell=True    timeout=180s
           Log Everywhere     [GIT PULL] rc: ${pull_result.rc}
           Log Everywhere     [GIT PULL] stdout: ${pull_result.stdout}
           Log Everywhere     [GIT PULL] stderr: ${pull_result.stderr}
           Run Keyword If    ${pull_result.rc} != 0    Fail    Git pull sikertelen: ${pull_result.stderr}
           Set Global Variable    ${WORKFLOW_STATUS}    'CLONED'
        END

Klónozás sikeresség ellenőrzése
   [Documentation]    A klónozás után ellenőrizzük, hogy létezik-e telepito.bat a most letöltött könyvtárban.
   #Log To Console     \n=== KLÓNOZÁS ELLENŐRZÉSE, ha 'CLONED' ===${WORKFLOW_STATUS}
   IF    ${WORKFLOW_STATUS} == 'CLONED'
    Log Everywhere     ======KLONOZÁS ELLENŐRZÉSE===== (${WORKFLOW_STATUS})
       Log Everywhere    REPO:${REPO}
       Log Everywhere    BRANCH:${BRANCH}

        ${INSTALL_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/telepito.bat
        Log Everywhere     Ellenőrzés: telepit.bat létezik-e? ${INSTALL_SCRIPT}

        ${install_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${INSTALL_SCRIPT}
        IF    ${install_script_exists}
            Log Everywhere     A klónozás sikeres volt, a telepit.bat megtalálható: ${INSTALL_SCRIPT}
            Set Global Variable    ${WORKFLOW_STATUS}    'CLONED_OK'
        ELSE
            Log Everywhere     A klónozás sikertelen volt, a telepit.bat nem található:\n ${INSTALL_SCRIPT}
            Fail    A klónozás sikertelen volt, a telepit.bat nem található:\n ${INSTALL_SCRIPT}
        END
    END

Telepítés futtatása
    [Documentation]    A klónozás után futtatjuk a telepit.bat fájlt.
    #Log To Console     \n=== TELEPÍTÉS FUTTATÁSA, ha 'CLONED_OK' ===${WORKFLOW_STATUS}
    IF    ${WORKFLOW_STATUS} == 'CLONED_OK'
           Log Everywhere     \n=== TELEPÍTÉS FUTTATÁSA=== (${WORKFLOW_STATUS})
        Log Everywhere   DOWNLOADED_ROBOTS:${DOWNLOADED_ROBOTS}
        Log Everywhere    REPO:${REPO}
        Log Everywhere    BRANCH:${BRANCH}

        ${INSTALL_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/telepito.bat
        Log Everywhere     [TELEPÍTŐ] telepito.bat elérési út: ${INSTALL_SCRIPT}
        Log Everywhere     [TELEPÍTŐ] Futtatás könyvtára: ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}
        Log Everywhere     [TELEPÍTŐ] Telepítés indítása: ${INSTALL_SCRIPT}

        # Felugró ablakban futtatás - cmd /c start paranccsal új ablakot nyit, /c bezárja a lefutás után
        Log Everywhere     [TELEPÍTŐ] Telepítő script futtatása új ablakban (automatikus bezárással)...
        ${install_result}=    Run Process    cmd    /c    start    /wait    cmd    /c    ${INSTALL_SCRIPT}    shell=True    cwd=${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}    timeout=120s
            IF    ${install_result.rc} != 0    
                Log Everywhere    Telepítés nem sikerült (timeout vagy hiba): ${install_result.stderr}
                Fail    A telepítés sikertelen volt, a telepito.bat nem található:\n ${INSTALL_SCRIPT}
            END

            IF    ${install_result.rc} == 0    
                Log Everywhere    Telepítés sikeresen befejeződött: ${INSTALL_SCRIPT}
                Set Global Variable    ${WORKFLOW_STATUS}    'SET_UP_OK'
            END
      END

Telepítés sikeresség ellenőrzése
   [Documentation]    A telepítés után ellenőrizzük, hogy létezik-e start.bat a most letöltött könyvtárban.
   #Log To Console     \n=== TELEPÍTÉS ELLENŐRZÉSE, ha 'SET_UP_OK' ===${WORKFLOW_STATUS}
   IF    ${WORKFLOW_STATUS} == 'SET_UP_OK'
        Log Everywhere     \n=== TELEPÍTÉS ELLENŐRZÉSE == (${WORKFLOW_STATUS})
        ${START_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/start.bat
        Log Everywhere     Ellenőrzés: start.bat létezik-e az DOWNLOADED_ROBOTS könyvtárban? ${START_SCRIPT}

        ${start_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${START_SCRIPT}
        IF    ${start_script_exists}
            Log Everywhere     A telepítés sikeres volt, a start.bat megtalálható az DOWNLOADED_ROBOTS-ban: ${START_SCRIPT}
            Set Global Variable    ${WORKFLOW_STATUS}    'READY_TO_RUN'
        ELSE
            Log Everywhere     A telepítés sikertelen volt, a start.bat nem található az DOWNLOADED_ROBOTS könyvtárban:\n ${START_SCRIPT}
            Fail    A telepítés sikertelen volt, a start.bat nem található az DOWNLOADED_ROBOTS könyvtárban:\n ${START_SCRIPT}
        END
    END
    
Robot futtatása
  [Documentation]    Futtatjuk a start.bat fájlt
  #Log To Console     \n=== ROBOT FUTTATÁSA, ha 'READY_TO_RUN' ===${WORKFLOW_STATUS}
  IF    ${AUTO_LAUNCH_START_BAT} == True
      IF    ${WORKFLOW_STATUS} == 'READY_TO_RUN'    
          Log Everywhere     \n=== [FUTTATÁS GOMB] ROBOT FUTTATÁSA INDUL ===
          Log Everywhere     [FUTTATÁS] WORKFLOW_STATUS: ${WORKFLOW_STATUS}
          Log Everywhere     [FUTTATÁS] REPO: ${REPO}
          Log Everywhere     [FUTTATÁS] BRANCH: ${BRANCH}
                ${RUN_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/start.bat
            Log Everywhere     [FUTTATÁS] start.bat elérési út: ${RUN_SCRIPT}
            Log Everywhere     [FUTTATÁS] Futtatás könyvtára: ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}

          Log Everywhere     [FUTTATÁS] Robot script indítása blokkoló módon: ${RUN_SCRIPT}
          ${WORKDIR}=    Evaluate    os.path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}''')    modules=os
          ${run_result}=    Run Process    ${RUN_SCRIPT}    shell=True    cwd=${WORKDIR}    timeout=600s
          Log Everywhere     [FUTTATÁS] Run Process rc: ${run_result.rc}
          Log Everywhere     [FUTTATÁS] Run Process stdout: ${run_result.stdout}
          Log Everywhere     [FUTTATÁS] Run Process stderr: ${run_result.stderr}
          IF    ${run_result.rc} == 0
              Log Everywhere     [FUTTATÁS] ${REPO}/${BRANCH} alkalmazás sikeresen lefutott.
          ELSE
              Log Everywhere     [FUTTATÁS] ${REPO}/${BRANCH} alkalmazás futtatása sikertelen: ${run_result.stderr}
          END
          Set Global Variable    ${WORKFLOW_STATUS}    'ALL_DONE'
          Log Everywhere    [FUTTATÁS] Robot indítása befejezve, a szerver tényleg megvárta a futás végét    
        ELSE IF    ${SANDBOX_MODE} == True and ${WORKFLOW_STATUS} == 'ALL_DONE'
          # SANDBOX módban közvetlenül futtatás a letöltött könyvtárból
          Log Everywhere     \n=== SANDBOX ROBOT FUTTATÁSA ===
        ${SANDBOX_RUN_SCRIPT}=    Set Variable    ${SANDBOX_ROBOTS}/${REPO}/${BRANCH}/start.bat
          ${sandbox_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${SANDBOX_RUN_SCRIPT}
          
          IF    ${sandbox_script_exists}
              Log Everywhere     Robot futtatása SANDBOX módban: ${SANDBOX_RUN_SCRIPT}
              
              # Popup ablakban futtatás: a CWD-ben lévő start.bat-ot indítjuk
              ${sandbox_run_result}=    Run Process    cmd    /c    start    ""    start.bat    shell=True    cwd=${SANDBOX_ROBOTS}/${REPO}/${BRANCH}    timeout=60s
              
              IF    ${sandbox_run_result.rc} == 0
                  Log Everywhere     ${REPO}/${BRANCH} SANDBOX alkalmazás sikeresen elindult popup ablakban
              ELSE
                  Log Everywhere     ${REPO}/${BRANCH} SANDBOX start indítása sikertelen, PowerShell fallback...
                  ${ps_sandbox_cmd}=    Set Variable    Start-Process -FilePath 'start.bat' -WorkingDirectory '${SANDBOX_ROBOTS}/${REPO}/${BRANCH}' -WindowStyle Normal
                  ${ps_sandbox_result}=    Run Process    powershell.exe    -NoProfile    -ExecutionPolicy    Bypass    -Command    ${ps_sandbox_cmd}    shell=True    timeout=60s
                  Log Everywhere     [SANDBOX][PS] rc: ${ps_sandbox_result.rc}
                  Log Everywhere     [SANDBOX][PS] stdout: ${ps_sandbox_result.stdout}
                  Log Everywhere     [SANDBOX][PS] stderr: ${ps_sandbox_result.stderr}
                  IF    ${ps_sandbox_result.rc} == 0
                      Log Everywhere     ${REPO}/${BRANCH} SANDBOX alkalmazás PowerShell fallback-kel elindult
                  ELSE
                      Log Everywhere     ${REPO}/${BRANCH} SANDBOX alkalmazás indítása sikertelen: ${ps_sandbox_result.stderr}
                  END
              END
          ELSE
              Log Everywhere     SANDBOX start.bat nem található: ${SANDBOX_RUN_SCRIPT}
          END
      END
  ELSE
      Log Everywhere     [FUTTATÁS] start.bat automatikus indítása kihagyva (AUTO_LAUNCH_START_BAT = ${AUTO_LAUNCH_START_BAT})
      Set Global Variable    ${WORKFLOW_STATUS}    'ALL_DONE'
  END
    Log Everywhere     \n=== MINDEN LÉPÉS BEFEJEZŐDÖTT ===
    Log Everywhere     WORKFLOW_STATUS = ${WORKFLOW_STATUS}