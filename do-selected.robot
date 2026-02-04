*** Settings ***

Suite Setup    Feloldott könyvtár változók
Library    OperatingSystem
Library    Process
Library    String
Library     ./libraries/RealtimeProcess.py
Resource    ./resources/keywords.robot
Resource    ./resources/variables.robot
Suite Teardown    Log fájlok összefűzése

*** Variables ***

*** Keywords ***
Beállít CURRENT_LOG_DIR a fájlból
    [Documentation]    Beolvassa a LOG_FILES/current_log_dir.txt tartalmát és beállítja a globális CURRENT_LOG_DIR változót.
    ${log_files}=    Get Variable Value    ${LOG_FILES}
    ${current_log_dir_path}=    Evaluate    __import__('os').path.join(r'''${log_files}''', 'current_log_dir.txt')    modules=os
    ${exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${current_log_dir_path}
    IF    ${exists}
        ${current_log_dir}=    Get File    ${current_log_dir_path}
        ${current_log_dir}=    Strip String    ${current_log_dir}
        Set Global Variable    ${CURRENT_LOG_DIR}    ${current_log_dir}
        Log    [INIT] CURRENT_LOG_DIR beállítva: ${CURRENT_LOG_DIR}
    ELSE
        Log    [INIT][WARN] current_log_dir.txt nem található: ${current_log_dir_path}
    END
Log fájlok összefűzése
    [Documentation]    A futtatás után összefűzi a log fájlokat rebot --rpa paranccsal, a futás elején eltárolt log könyvtárat használva.
    #Log dir beolvasása
     Beállít CURRENT_LOG_DIR a fájlból
  
   
    # Aktuális log könyvtár csak változóban, nincs fájl olvasás
    Log    [LOGDIR][TEARDOWN] Aktuális log könyvtár: ${CURRENT_LOG_DIR}
    ${LOG_OUTPUT_DIR}=    Evaluate    __import__('os').path.normpath(r'''${LOG_FILES}/${CURRENT_LOG_DIR}''')    modules=os
    # Ellenőrzés: ha a log könyvtár név hiányzik vagy hibás, ne folytasd!
    IF    '${CURRENT_LOG_DIR}' == '' or '${CURRENT_LOG_DIR}' == 'MISSING_LOG_DIR'
        Log    [HIBÁZOTT] A log könyvtár neve hiányzik vagy hibás (CURRENT_LOG_DIR = ${CURRENT_LOG_DIR}), log merge kihagyva!
        RETURN
    END
    # A 

    ${LOG_OUTPUT_XML}=    Evaluate    __import__('os').path.normpath(r'''${LOG_OUTPUT_DIR}/output.xml''')    modules=os
    ${LOG_OUTPUT_LOG}=    Evaluate    __import__('os').path.normpath(r'''${LOG_OUTPUT_DIR}/log.html''')    modules=os
    ${LOG_OUTPUT_REPORT}=    Evaluate    __import__('os').path.normpath(r'''${LOG_OUTPUT_DIR}/report.html''')    modules=os
    
    ${ROBOT_OUTPUT_XML}=    Evaluate    __import__('os').path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/output.xml''')    modules=os
    ${ROBOT_OUTPUT_LOG}=    Evaluate    __import__('os').path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/log.html''')    modules=os
   ${ROBOT_OUTPUT_REPORT}=    Evaluate    __import__('os').path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/report.html''')    modules=os
 
  Log    [REBOT][LOG_OUTPUT_LOG] ${LOG_OUTPUT_LOG} 
  Log    [REBOT][LOG_OUTPUT_REPORT] ${LOG_OUTPUT_REPORT} 
  Log    [REBOT][ROBOT_OUTPUT_LOG] ${ROBOT_OUTPUT_LOG} 
  Log    [REBOT][ROBOT_OUTPUT_REPORT] ${ROBOT_OUTPUT_REPORT} 
   
   #Másolás a log és report fájlok a log könyvtárba

    Copy File    ${ROBOT_OUTPUT_LOG}    ${LOG_OUTPUT_DIR}/r_log.html
    Copy File    ${ROBOT_OUTPUT_REPORT}    ${LOG_OUTPUT_DIR}/r_report.html
   
    # Az r_log.html fájlban cseréljük ki a log.html hivatkozásokat r_log.html-re
    ${r_log_content}=    Get File    ${LOG_OUTPUT_DIR}/r_log.html
    ${r_log_content_modified}=    Replace String    ${r_log_content}    report.html    r_report.html
    Create File    ${LOG_OUTPUT_DIR}/r_log.html    ${r_log_content_modified}
    Log    [REBOT][r_log.html] log.html hivatkozások cserélve r_log.html-re a ${LOG_OUTPUT_DIR}/r_log.html fájlban.
   
    # cseréljük log.html hivatkozásokat r_log.html-re a report.html fájlban is
    ${report_content}=    Get File    ${LOG_OUTPUT_DIR}/r_report.html
    ${report_content_modified}=    Replace String    ${report_content}    log.html    r_log.html
    Create File    ${LOG_OUTPUT_DIR}/r_report.html    ${report_content_modified}
    Log    [REBOT][r_report.html] log.html hivatkozások cserélve r_log.html-re a ${LOG_OUTPUT_DIR}/r_report.html fájlban.

    # Készítsen egy issuet és csatolja az r_log.html és r_report.html fájlokat
    Log    [REBOT] Log fájlok összefűzése befejeződött: ${LOG_OUTPUT_DIR}        
    
    Log     \n=== MINDEN LÉPÉS BEFEJEZŐDÖTT ===
    Log     WORKFLOW_STATUS = ${WORKFLOW_STATUS}

Feloldott könyvtár változók

    ${USERPROFILE}=    Get Environment Variable    USERPROFILE
    ${DOWNLOADED_ROBOTS}=    Set Variable    ${USERPROFILE}${/}MyRobotFramework${/}DownloadedRobots
    Set Suite Variable    ${DOWNLOADED_ROBOTS}
    ${SANDBOX_ROBOTS}=    Set Variable    ${USERPROFILE}${/}MyRobotFramework${/}SandboxRobots
    Set Suite Variable    ${SANDBOX_ROBOTS}
    ${LOG_FILES}=    Set Variable    ${USERPROFILE}${/}MyRobotFramework${/}RobotResults
    Set Suite Variable    ${LOG_FILES}

    # Aktuális log könyvtár csak változóban, nincs fájl írás/olvasás
    Log    [LOGDIR] Aktuális log könyvtár: ${CURRENT_LOG_DIR}

*** Test Cases ***
    # Feloldott könyvtár változók (kulcsszó, nem teszteset)
Kiírás konzolra paraméterekből
    # Dinamikus könyvtár változók beállítása a környezeti USERPROFILE alapján
    ${USERPROFILE}=    Get Environment Variable    USERPROFILE
    ${DOWNLOADED_ROBOTS}=    Set Variable    ${USERPROFILE}${/}MyRobotFramework${/}DownloadedRobots
    ${SANDBOX_ROBOTS}=       Set Variable    ${USERPROFILE}${/}MyRobotFramework${/}SandboxRobots
    Set Suite Variable    ${DOWNLOADED_ROBOTS}
    Set Suite Variable    ${SANDBOX_ROBOTS}
    Set Suite Variable    ${DOWNLOADED_ROBOTS}
    Set Suite Variable    ${SANDBOX_ROBOTS}
    [Documentation]    A kapott REPO és BRANCH változók értékeinek kiírása.
    Log     \n=== KIVÁLASZTOTT ROBOT ===
    Log     [DEBUG] SANDBOX_MODE értéke: ${SANDBOX_MODE}
    Set Global Variable    ${WORKFLOW_STATUS}    'STARTED'
    ${GIT_URL}=    Set Variable    ${GIT_URL_BASE}${REPO}.git
    Set Global Variable    ${GIT_URL}    ${GIT_URL}
    Log     Repository: ${GIT_URL}
    Log     Branch: ${BRANCH}
    #trash könyvtár létrehozása, ha nem létezik
    Create Directory    ${TRASH_DIR}
    Log     =========================\n

Telepítettség és letöltöttség ellenőrzése
    [Documentation]    Ellenőrzi, hogy a robot már telepítve van-e (start.bat létezik), vagy csak letöltve
    Log     \n=== TELEPÍTETTSÉG ÉS LETÖLTÖTTSÉG ELLENŐRZÉSE === (${WORKFLOW_STATUS})
    
    # Telepített robot ellenőrzése (start.bat létezik-e)
    ${START_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}${/}${REPO}${/}${BRANCH}${/}start.bat
    ${start_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${START_SCRIPT}
    
    IF    ${start_script_exists}
        Log     Robot már telepítve van: ${START_SCRIPT}
        Set Global Variable    ${WORKFLOW_STATUS}    'READY_TO_RUN'
    ELSE
        Log     Robot nincs telepítve, ellenőrizzük a letöltöttséget...
        
        # Letöltött robot ellenőrzése
        IF        ${SANDBOX_MODE} == True
               ${REPO_PATH}=     Set Variable    ${SANDBOX_ROBOTS}${/}${REPO}
        ELSE
               ${REPO_PATH}=     Set Variable    ${DOWNLOADED_ROBOTS}${/}${REPO} 
        END
          
           ${BRANCH_PATH}=   Set Variable    ${REPO_PATH}${/}${BRANCH}
        Set Global Variable    ${REPO_PATH}    ${REPO_PATH}
        Set Global Variable    ${BRANCH_PATH}    ${BRANCH_PATH}

        Log     Full Repository: ${REPO_PATH}
        Log     Full Branch: ${BRANCH_PATH}
        #könyvtár létezésének ellenőrzése
        ${downloaded_repo_exists}=     Run Keyword And Return Status    OperatingSystem.Directory Should Exist     ${REPO_PATH}
        ${downloaded_robot_exists}=    Run Keyword And Return Status    OperatingSystem.Directory Should Exist    ${BRANCH_PATH}
        
        IF     ${downloaded_repo_exists} and ${downloaded_robot_exists}
            #visszatér a tesztből
            #todo verzió alapján újra letöltés
            Log     Mindkét könyvtár létezik! 
          
            #töröljük a sandbox tartalmát és újratelepítjük
            IF    ${SANDBOX_MODE} == True
                Log     Sandbox módban vagyunk, töröljük a könyvtárt:${REPO_PATH}
                Move Directory    ${BRANCH_PATH}         ${TRASH_DIR}        
                Set Global Variable    ${WORKFLOW_STATUS}    'MAKE_DIRS'
            ELSE
              Log     Letöltött branch frissítése (git pull) szükséges
              Set Global Variable    ${WORKFLOW_STATUS}    'TO_BE_PULL'
            END
        ELSE
             Log     Könyvtárak nem léteznek! 
            Set Global Variable    ${WORKFLOW_STATUS}    'MAKE_DIRS'    
        END
    END

Könyvtárak létrehozása
    [Documentation]    Létrehozza a szükséges könyvtárakat, ha még nem léteznek.  
       #Log To Console     \n=== KÖNYVTÁRAK LÉTREHOZÁSA, ha 'MAKE_DIRS' === ${WORKFLOW_STATUS}
    IF    ${WORKFLOW_STATUS} == 'MAKE_DIRS'
        Log     ======Könyvtár létrehozás==== (${WORKFLOW_STATUS})
        #létrehozzuk a repository könyvtárat, ha nem létezik
        Create Directory    ${REPO_PATH}
        Log     Létrehozva a repository könyvtár: ${REPO_PATH}
        #létrehozzuk a branch könyvtárat, ha nem létezik
        Create Directory    ${BRANCH_PATH}
        Log     Létrehozva a branch könyvtár: ${BRANCH_PATH}
        
        # Klónozáshoz szükséges változók újbóli beállítása (biztonsági okokból)
        ${GIT_URL}=    Set Variable    ${GIT_URL_BASE}${REPO}.git
        Set Global Variable    ${GIT_URL}    ${GIT_URL}
        Log     Globálisan beállítva: GIT_URL = ${GIT_URL}

        #Set Global Variable    ${BRANCH}    ${BRANCH}
        Log     Globálisan beállítva: BRANCH = ${BRANCH}
        ${TARGET_DIR}=    Set Global Variable    ${BRANCH_PATH}
        Log     TARGET_DIR = ${TARGET_DIR}

        Set Global Variable    ${WORKFLOW_STATUS}    'TO_BE_CLONE'
   END
    
Branch klónozása
    [Documentation]    A REPO és BRANCH változók alapján klónozza a megfelelő könyvtárat, ha még nincs letöltve.
    #Log To Console    \nBranch klónozása WORKFLOW_STATUS, ha 'TO_BE_CLONE' = ${WORKFLOW_STATUS}    
        IF    ${WORKFLOW_STATUS} == 'TO_BE_CLONE'
            Log     ======KLONOZÁS GIT-BŐL===== (${WORKFLOW_STATUS})
            IF    ${SANDBOX_MODE} == True
                    ${TARGET_DIR}=    Set Variable    ${SANDBOX_ROBOTS}${/}${REPO}${/}${BRANCH}
           ELSE
                    ${TARGET_DIR}=    Set Variable    ${DOWNLOADED_ROBOTS}${/}${REPO}${/}${BRANCH}
            END
         
           Log     [GIT KLÓNOZÁS] Forrás: ${GIT_URL}
           Log     [GIT KLÓNOZÁS] Branch: ${BRANCH}
           Log     [GIT KLÓNOZÁS] Cél könyvtár: ${TARGET_DIR}
           Log     [GIT KLÓNOZÁS] Parancs: git clone -b ${BRANCH} --single-branch ${GIT_URL} ${TARGET_DIR}

           # Git clone parancs futtatása (kimenet rögzítése)
           ${result}=    Run Process    git    clone    -b    ${BRANCH}    --single-branch    ${GIT_URL}    ${TARGET_DIR}    shell=True    timeout=300s
           Log     [GIT KLÓNOZÁS] rc: ${result.rc}
           Log     [GIT KLÓNOZÁS] stdout: ${result.stdout}
           Log     [GIT KLÓNOZÁS] stderr: ${result.stderr}
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
           Log     ======GIT PULL FUTTATÁSA===== (${WORKFLOW_STATUS})
           Log     [GIT PULL] Könyvtár: ${BRANCH_PATH}
           ${pull_result}=    Run Process    git    -C    ${BRANCH_PATH}    pull    shell=True    timeout=180s
           Log     [GIT PULL] rc: ${pull_result.rc}
           Log     [GIT PULL] stdout: ${pull_result.stdout}
           Log     [GIT PULL] stderr: ${pull_result.stderr}
           Run Keyword If    ${pull_result.rc} != 0    Fail    Git pull sikertelen: ${pull_result.stderr}
           Set Global Variable    ${WORKFLOW_STATUS}    'CLONED'
        END

Klónozás sikeresség ellenőrzése
   [Documentation]    A klónozás után ellenőrizzük, hogy létezik-e telepito.bat a most letöltött könyvtárban.
   #Log To Console     \n=== KLÓNOZÁS ELLENŐRZÉSE, ha 'CLONED' ===${WORKFLOW_STATUS}
   IF    ${WORKFLOW_STATUS} == 'CLONED'
    Log     ======KLONOZÁS ELLENŐRZÉSE===== (${WORKFLOW_STATUS})
    Log    REPO:${REPO}
    Log    BRANCH:${BRANCH}

        ${INSTALL_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/telepito.bat
        Log     Ellenőrzés: telepit.bat létezik-e? ${INSTALL_SCRIPT}

        ${install_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${INSTALL_SCRIPT}
        IF    ${install_script_exists}
            Log     A klónozás sikeres volt, a telepit.bat megtalálható: ${INSTALL_SCRIPT}
            Set Global Variable    ${WORKFLOW_STATUS}    'CLONED_OK'
        ELSE
            Log     A klónozás sikertelen volt, a telepit.bat nem található:\n ${INSTALL_SCRIPT}
            Fail    A klónozás sikertelen volt, a telepit.bat nem található:\n ${INSTALL_SCRIPT}
        END
    END

Telepítés futtatása
    [Documentation]    A klónozás után futtatjuk a telepit.bat fájlt.
    #Log To Console     \n=== TELEPÍTÉS FUTTATÁSA, ha 'CLONED_OK' ===${WORKFLOW_STATUS}
    IF    ${WORKFLOW_STATUS} == 'CLONED_OK'
        Log     \n=== TELEPÍTÉS FUTTATÁSA=== (${WORKFLOW_STATUS})
        Log   DOWNLOADED_ROBOTS:${DOWNLOADED_ROBOTS}
        Log    REPO:${REPO}
        Log    BRANCH:${BRANCH}

        ${INSTALL_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/telepito.bat
        Log     [TELEPÍTŐ] telepito.bat elérési út: ${INSTALL_SCRIPT}
        Log     [TELEPÍTŐ] Futtatás könyvtára: ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}
        Log     [TELEPÍTŐ] Telepítés indítása: ${INSTALL_SCRIPT}

        # Felugró ablakban futtatás - cmd /c start paranccsal új ablakot nyit, /c bezárja a lefutás után
        Log     [TELEPÍTŐ] Telepítő script futtatása új ablakban (automatikus bezárással)...
        ${install_result}=    Run Process    cmd    /c    start    "Telepítés"    cmd    /k    ${INSTALL_SCRIPT}    shell=True    cwd=${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}    timeout=120s
            IF    ${install_result.rc} != 0    
                Log    Telepítés nem sikerült (timeout vagy hiba): ${install_result.stderr}
                Fail    A telepítés sikertelen volt, a telepito.bat nem található:\n ${INSTALL_SCRIPT}
            END

            IF    ${install_result.rc} == 0    
                Log    Telepítés sikeresen befejeződött: ${INSTALL_SCRIPT}
                Set Global Variable    ${WORKFLOW_STATUS}    'SET_UP_OK'
            END
      END

Telepítés sikeresség ellenőrzése
   [Documentation]    A telepítés után ellenőrizzük, hogy létezik-e start.bat a most letöltött könyvtárban.
   #Log To Console     \n=== TELEPÍTÉS ELLENŐRZÉSE, ha 'SET_UP_OK' ===${WORKFLOW_STATUS}
   IF    ${WORKFLOW_STATUS} == 'SET_UP_OK'
        Log     \n=== TELEPÍTÉS ELLENŐRZÉSE == (${WORKFLOW_STATUS})
        ${START_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/start.bat
        Log     Ellenőrzés: start.bat létezik-e az DOWNLOADED_ROBOTS könyvtárban? ${START_SCRIPT}

        ${start_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${START_SCRIPT}
        IF    ${start_script_exists}
            Log     A telepítés sikeres volt, a start.bat megtalálható az DOWNLOADED_ROBOTS-ban: ${START_SCRIPT}
            Set Global Variable    ${WORKFLOW_STATUS}    'READY_TO_RUN'
        ELSE
            Log     A telepítés sikertelen volt, a start.bat nem található az DOWNLOADED_ROBOTS könyvtárban:\n ${START_SCRIPT}
            Fail    A telepítés sikertelen volt, a start.bat nem található az DOWNLOADED_ROBOTS könyvtárban:\n ${START_SCRIPT}
        END
    END
    

Robot futtatása
  [Documentation]    Futtatjuk a start.bat fájlt, és elmentjük a log könyvtár nevét.
  #Log To Console     \n=== ROBOT FUTTATÁSA, ha 'READY_TO_RUN' ===${WORKFLOW_STATUS}
  IF    ${AUTO_LAUNCH_START_BAT} == True
      IF    ${WORKFLOW_STATUS} == 'READY_TO_RUN'    
          Log     \n=== [FUTTATÁS GOMB] ROBOT FUTTATÁSA INDUL ===
          Log     [FUTTATÁS] WORKFLOW_STATUS: ${WORKFLOW_STATUS}
          Log     [FUTTATÁS] REPO: ${REPO}
          Log     [FUTTATÁS] BRANCH: ${BRANCH}
        
        
          # Log könyvtár nevét csak a backend (flask_app.py) generálja és írja current_log_dir.txt-be
          # Itt csak olvassuk a Suite Setup-ban beállított CURRENT_LOG_DIR értéket
          ${LOG_OUTPUT_DIR}=    Set Variable    ${LOG_FILES}/${CURRENT_LOG_DIR}
          Log     [FUTTATÁS] Log könyvtár: ${LOG_OUTPUT_DIR}
          Log     [FUTTATÁS] Futtatás könyvtára: ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}

          ${WORKDIR}=    Evaluate    os.path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}''')    modules=os
          #${SERVERLOG_FILE}=    Evaluate    os.path.normpath(r'''./serverlog.log''')    modules=os
          #adja össze a SERVERLOG_FILE elérési útját a log könyvtárral
          ${SERVERLOG_FILE}=    Evaluate    os.path.normpath(r'''${WORKDIR}/server.log''')    modules=os
         Log     [FUTTATÁS] WORKDIR:${WORKDIR}   
         Log     [FUTTATÁS] SERVERLOG_FILE:${SERVERLOG_FILE}   
         

          #${RUN_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/start.bat | tee  ${SERVERLOG_FILE}serverlog.log
          ${RUN_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/start.bat 
          Log     [FUTTATÁS] Robot script indítása blokkoló módon: ${RUN_SCRIPT}
          
          #${run_result}=    Run Process    ${RUN_SCRIPT}      shell=True    cwd=${WORKDIR}    timeout=600s     stdout=${SERVERLOG_FILE}    stderr=${SERVERLOG_FILE}    
          ${run_result}=    Run Realtime To Log    ${RUN_SCRIPT}    ${SERVERLOG_FILE}    cwd=${WORKDIR}
         #${run_result}=    Run Process    ${RUN_SCRIPT}      shell=True    cwd=${WORKDIR}    timeout=600s 
          #${run_result}=    Run Process    cmd    /c    start    ""    "${RUN_SCRIPT}"    shell=True       cwd=${WORKDIR}    timeout=600s
          Log     [FUTTATÁS] Run Process rc: ${run_result}
          # stdout és stderr nem elérhető, mert csak returncode van
          IF    ${run_result} == 0
              Log     [FUTTATÁS] ${REPO}/${BRANCH} alkalmazás sikeresen lefutott.
          ELSE
              Log     [FUTTATÁS] ${REPO}/${BRANCH} alkalmazás futtatása sikertelen: ${run_result.stderr}
          END
        
          Set Global Variable    ${WORKFLOW_STATUS}    'ALL_DONE'
          Log    [FUTTATÁS] Robot indítása befejezve, a szerver tényleg megvárta a futás végét    
      ELSE IF    ${SANDBOX_MODE} == True and ${WORKFLOW_STATUS} == 'ALL_DONE'
          # SANDBOX módban közvetlenül futtatás a letöltött könyvtárból
          Log     \n=== SANDBOX ROBOT FUTTATÁSA ===
          ${SANDBOX_RUN_SCRIPT}=    Set Variable    ${SANDBOX_ROBOTS}/${REPO}/${BRANCH}/start.bat
          ${sandbox_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${SANDBOX_RUN_SCRIPT}
          IF    ${sandbox_script_exists}
              Log     Robot futtatása SANDBOX módban: ${SANDBOX_RUN_SCRIPT}
              # Popup ablakban futtatás: a CWD-ben lévő start.bat-ot indítjuk
              ${sandbox_run_result}=    Run Process    cmd    /c    start    ""    start.bat    shell=True    cwd=${SANDBOX_ROBOTS}/${REPO}/${BRANCH}    timeout=60s
              IF    ${sandbox_run_result.rc} == 0
                  Log     ${REPO}/${BRANCH} SANDBOX alkalmazás sikeresen elindult popup ablakban
              ELSE
                  Log     ${REPO}/${BRANCH} SANDBOX start indítása sikertelen, PowerShell fallback...
                  ${ps_sandbox_cmd}=    Set Variable    Start-Process -FilePath 'start.bat' -WorkingDirectory '${SANDBOX_ROBOTS}/${REPO}/${BRANCH}' -WindowStyle Normal
                  ${ps_sandbox_result}=    Run Process    powershell.exe    -NoProfile    -ExecutionPolicy    Bypass    -Command    ${ps_sandbox_cmd}    shell=True    timeout=60s
                  Log     [SANDBOX][PS] rc: ${ps_sandbox_result.rc}
                  Log     [SANDBOX][PS] stdout: ${ps_sandbox_result.stdout}
                  Log     [SANDBOX][PS] stderr: ${ps_sandbox_result.stderr}
                  IF    ${ps_sandbox_result.rc} == 0
                      Log     ${REPO}/${BRANCH} SANDBOX alkalmazás PowerShell fallback-kel elindult
                  ELSE
                      Log     ${REPO}/${BRANCH} SANDBOX alkalmazás indítása sikertelen: ${ps_sandbox_result.stderr}
                  END
              END
          ELSE
              Log     SANDBOX start.bat nem található: ${SANDBOX_RUN_SCRIPT}
          END
      END
  ELSE
    Log     [FUTTATÁS] start.bat automatikus indítása kihagyva (AUTO_LAUNCH_START_BAT = ${AUTO_LAUNCH_START_BAT})
      Set Global Variable    ${WORKFLOW_STATUS}    'ALL_DONE'
  END
    Log     \n=== MINDEN LÉPÉS BEFEJEZŐDÖTT ===
    Log     WORKFLOW_STATUS = ${WORKFLOW_STATUS}