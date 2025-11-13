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
    Log To Console     [DEBUG] SANDBOX_MODE értéke: ${SANDBOX_MODE}
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
              Log To Console     Letöltött branch frissítése (git pull) szükséges
              Set Global Variable    ${WORKFLOW_STATUS}    'TO_BE_PULL'
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
         
           Log To Console     [GIT KLÓNOZÁS] Forrás: ${GIT_URL}
           Log To Console     [GIT KLÓNOZÁS] Branch: ${BRANCH}
           Log To Console     [GIT KLÓNOZÁS] Cél könyvtár: ${TARGET_DIR}
           Log To Console     [GIT KLÓNOZÁS] Parancs: git clone -b ${BRANCH} --single-branch ${GIT_URL} ${TARGET_DIR}

           # Git clone parancs futtatása (kimenet rögzítése)
           ${result}=    Run Process    git    clone    -b    ${BRANCH}    --single-branch    ${GIT_URL}    ${TARGET_DIR}    shell=True    timeout=300s
           Log To Console     [GIT KLÓNOZÁS] rc: ${result.rc}
           Log To Console     [GIT KLÓNOZÁS] stdout: ${result.stdout}
           Log To Console     [GIT KLÓNOZÁS] stderr: ${result.stderr}
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
           Log To Console     ======GIT PULL FUTTATÁSA=====${WORKFLOW_STATUS}
           Log To Console     [GIT PULL] Könyvtár: ${BRANCH_PATH}
           ${pull_result}=    Run Process    git    -C    ${BRANCH_PATH}    pull    shell=True    timeout=180s
           Log To Console     [GIT PULL] rc: ${pull_result.rc}
           Log To Console     [GIT PULL] stdout: ${pull_result.stdout}
           Log To Console     [GIT PULL] stderr: ${pull_result.stderr}
           Run Keyword If    ${pull_result.rc} != 0    Fail    Git pull sikertelen: ${pull_result.stderr}
           Set Global Variable    ${WORKFLOW_STATUS}    'CLONED'
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
        Log To Console     [TELEPÍTŐ] telepito.bat elérési út: ${INSTALL_SCRIPT}
        Log To Console     [TELEPÍTŐ] Futtatás könyvtára: ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}
        Log To Console     [TELEPÍTŐ] Telepítés indítása: ${INSTALL_SCRIPT}

        # Felugró ablakban futtatás - cmd /c start paranccsal új ablakot nyit, /c bezárja a lefutás után
        Log To Console     [TELEPÍTŐ] Telepítő script futtatása új ablakban (automatikus bezárással)...
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
  [Documentation]    Futtatjuk a start.bat fájlt, ha létezik, vagy SANDBOX módban közvetlenül a letöltött robotot.
  #Log To Console     \n=== ROBOT FUTTATÁSA, ha 'READY_TO_RUN' ===${WORKFLOW_STATUS}
  IF    ${WORKFLOW_STATUS} == 'READY_TO_RUN'    
      Log To Console     \n=== [FUTTATÁS GOMB] ROBOT FUTTATÁSA INDUL ===
      Log To Console     [FUTTATÁS] WORKFLOW_STATUS: ${WORKFLOW_STATUS}
      Log To Console     [FUTTATÁS] REPO: ${REPO}
      Log To Console     [FUTTATÁS] BRANCH: ${BRANCH}
            ${RUN_SCRIPT}=    Set Variable    ${INSTALLED_ROBOTS}/${REPO}/${BRANCH}/start.bat
        Log To Console     [FUTTATÁS] start.bat elérési út: ${RUN_SCRIPT}
        Log To Console     [FUTTATÁS] Futtatás könyvtára: ${INSTALLED_ROBOTS}/${REPO}/${BRANCH}

      # Külön szerver indítása - popup ablakban futtatás
      Log To Console     [FUTTATÁS] ${REPO}/${BRANCH} alkalmazás indítása külön popup ablakban...
      Log To Console     [FUTTATÁS] Robot script indítása: ${RUN_SCRIPT}

      # Popup ablakban futtatás: a CWD-ben lévő start.bat-ot indítjuk, hogy elkerüljük az útvonal kódolási gondokat
      ${run_result}=    Run Process    cmd    /c    start    ""    start.bat    shell=True    cwd=${INSTALLED_ROBOTS}/${REPO}/${BRANCH}    timeout=60s
      Log To Console     [FUTTATÁS] Run Process rc: ${run_result.rc}
      Log To Console     [FUTTATÁS] Run Process stdout: ${run_result.stdout}
      Log To Console     [FUTTATÁS] Run Process stderr: ${run_result.stderr}

      IF    ${run_result.rc} == 0
          Log To Console     [FUTTATÁS] ${REPO}/${BRANCH} alkalmazás sikeresen elindult popup ablakban
      ELSE
          Log To Console     [FUTTATÁS] start indítás sikertelen, PowerShell fallback próbálása...
          ${ps_command}=    Set Variable    Start-Process -FilePath 'start.bat' -WorkingDirectory '${INSTALLED_ROBOTS}/${REPO}/${BRANCH}' -WindowStyle Normal
          ${ps_result}=    Run Process    powershell.exe    -NoProfile    -ExecutionPolicy    Bypass    -Command    ${ps_command}    shell=True    timeout=60s
          Log To Console     [FUTTATÁS][PS] rc: ${ps_result.rc}
          Log To Console     [FUTTATÁS][PS] stdout: ${ps_result.stdout}
          Log To Console     [FUTTATÁS][PS] stderr: ${ps_result.stderr}
          IF    ${ps_result.rc} == 0
              Log To Console     [FUTTATÁS] PowerShell fallback sikeres, ablak elindítva
          ELSE
              Log To Console     [FUTTATÁS] ${REPO}/${BRANCH} alkalmazás indítása sikertelen: ${ps_result.stderr}
          END
      END

      Set Global Variable    ${WORKFLOW_STATUS}    'ALL_DONE'
      Log To Console    [FUTTATÁS] Robot indítása befejezve, a szerver a háttérben fut tovább    
    ELSE IF    ${SANDBOX_MODE} == True and ${WORKFLOW_STATUS} == 'ALL_DONE'
      # SANDBOX módban közvetlenül futtatás a letöltött könyvtárból
      Log To Console     \n=== SANDBOX ROBOT FUTTATÁSA ===
    ${SANDBOX_RUN_SCRIPT}=    Set Variable    ${SANDBOX_ROBOTS}/${REPO}/${BRANCH}/start.bat
      ${sandbox_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${SANDBOX_RUN_SCRIPT}
      
      IF    ${sandbox_script_exists}
          Log To Console     Robot futtatása SANDBOX módban: ${SANDBOX_RUN_SCRIPT}
          
          # Popup ablakban futtatás: a CWD-ben lévő start.bat-ot indítjuk
          ${sandbox_run_result}=    Run Process    cmd    /c    start    ""    start.bat    shell=True    cwd=${SANDBOX_ROBOTS}/${REPO}/${BRANCH}    timeout=60s
          
          IF    ${sandbox_run_result.rc} == 0
              Log To Console     ${REPO}/${BRANCH} SANDBOX alkalmazás sikeresen elindult popup ablakban
          ELSE
              Log To Console     ${REPO}/${BRANCH} SANDBOX start indítása sikertelen, PowerShell fallback...
              ${ps_sandbox_cmd}=    Set Variable    Start-Process -FilePath 'start.bat' -WorkingDirectory '${SANDBOX_ROBOTS}/${REPO}/${BRANCH}' -WindowStyle Normal
              ${ps_sandbox_result}=    Run Process    powershell.exe    -NoProfile    -ExecutionPolicy    Bypass    -Command    ${ps_sandbox_cmd}    shell=True    timeout=60s
              Log To Console     [SANDBOX][PS] rc: ${ps_sandbox_result.rc}
              Log To Console     [SANDBOX][PS] stdout: ${ps_sandbox_result.stdout}
              Log To Console     [SANDBOX][PS] stderr: ${ps_sandbox_result.stderr}
              IF    ${ps_sandbox_result.rc} == 0
                  Log To Console     ${REPO}/${BRANCH} SANDBOX alkalmazás PowerShell fallback-kel elindult
              ELSE
                  Log To Console     ${REPO}/${BRANCH} SANDBOX alkalmazás indítása sikertelen: ${ps_sandbox_result.stderr}
              END
          END
      ELSE
          Log To Console     SANDBOX start.bat nem található: ${SANDBOX_RUN_SCRIPT}
      END
    END
    Log To Console     \n=== MINDEN LÉPÉS BEFEJEZŐDÖTT ===
    Log To Console     WORKFLOW_STATUS = ${WORKFLOW_STATUS}