*** Settings ***

Suite Setup    Feloldott könyvtár változók
Library    OperatingSystem
Library    Process
Library    String
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
    #Log dir beolvasása
     Beállít CURRENT_LOG_DIR a fájlból
    # --- output.xml stabilitás ellenőrzése race condition elkerülésére ---
    ${LOG_OUTPUT_DIR}=    Evaluate    __import__('os').path.normpath(r'''${LOG_FILES}/${CURRENT_LOG_DIR}''')    modules=os
    ${LOG_OUTPUT_XML}=    Evaluate    __import__('os').path.normpath(r'''${LOG_OUTPUT_DIR}/output.xml''')    modules=os
    ${max_wait_sec}=    Set Variable    5
    ${check_interval}=    Set Variable    0.5
    ${stable_count_needed}=    Set Variable    3
    ${last_size}=    Set Variable    -1
    ${stable_count}=    Set Variable    0
    ${elapsed}=    Set Variable    0
    Log    [REBOT][WAIT] output.xml stabilitás ellenőrzése indul: max ${max_wait_sec} másodperc
    WHILE    ${elapsed} < ${max_wait_sec} and ${stable_count} < ${stable_count_needed}
        ${exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${LOG_OUTPUT_XML}
        IF    ${exists}
            ${size}=    Get File Size    ${LOG_OUTPUT_XML}
            IF    ${size} == ${last_size}
                ${stable_count}=    Evaluate    ${stable_count} + 1
            ELSE
                ${stable_count}=    Set Variable    1
                ${last_size}=    Set Variable    ${size}
            END
            Log    [REBOT][WAIT] output.xml méret: ${size}, stabil: ${stable_count}/${stable_count_needed}
        ELSE
            Log    [REBOT][WAIT] output.xml még nem létezik
            ${stable_count}=    Set Variable    0
            ${last_size}=    Set Variable    -1
        END
        Sleep    ${check_interval}
        ${elapsed}=    Evaluate    ${elapsed} + ${check_interval}
    END
    Log    [REBOT][WAIT] output.xml stabilitás ellenőrzés vége, stabil: ${stable_count} (max: ${stable_count_needed})

    # --- ${ROBOT_OUTPUT_XML} stabilitás ellenőrzése ---
    ${ROBOT_OUTPUT_XML}=    Evaluate    __import__('os').path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/output.xml''')    modules=os
    ${robot_max_wait_sec}=    Set Variable    5
    ${robot_check_interval}=    Set Variable    0.5
    ${robot_stable_count_needed}=    Set Variable    3
    ${robot_last_size}=    Set Variable    -1
    ${robot_stable_count}=    Set Variable    0
    ${robot_elapsed}=    Set Variable    0
    Log    [REBOT][WAIT] ROBOT output.xml stabilitás ellenőrzése indul: max ${robot_max_wait_sec} másodperc
    WHILE    ${robot_elapsed} < ${robot_max_wait_sec} and ${robot_stable_count} < ${robot_stable_count_needed}
        ${robot_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${ROBOT_OUTPUT_XML}
        IF    ${robot_exists}
            ${robot_size}=    Get File Size    ${ROBOT_OUTPUT_XML}
            IF    ${robot_size} == ${robot_last_size}
                ${robot_stable_count}=    Evaluate    ${robot_stable_count} + 1
            ELSE
                ${robot_stable_count}=    Set Variable    1
                ${robot_last_size}=    Set Variable    ${robot_size}
            END
            Log    [REBOT][WAIT] ROBOT output.xml méret: ${robot_size}, stabil: ${robot_stable_count}/${robot_stable_count_needed}
        ELSE
            Log    [REBOT][WAIT] ROBOT output.xml még nem létezik
            ${robot_stable_count}=    Set Variable    0
            ${robot_last_size}=    Set Variable    -1
        END
        Sleep    ${robot_check_interval}
        ${robot_elapsed}=    Evaluate    ${robot_elapsed} + ${robot_check_interval}
    END
    Log    [REBOT][WAIT] ROBOT output.xml stabilitás ellenőrzés vége, stabil: ${robot_stable_count} (max: ${robot_stable_count_needed})
    [Documentation]    A futtatás után összefűzi a log fájlokat rebot --rpa paranccsal, a futás elején eltárolt log könyvtárat használva.
    #
    # Log fájlok összefűzése
    # rebot  --rpa output_master.xml output_slave.xml

    # output.xml összefűzése rebot --rpa paranccsal, a futás elején eltárolt log könyvtárat használva
    # Aktuális log könyvtár csak változóban, nincs fájl olvasás
    Log    [LOGDIR][TEARDOWN] Aktuális log könyvtár: ${CURRENT_LOG_DIR}
    ${LOG_OUTPUT_DIR}=    Evaluate    __import__('os').path.normpath(r'''${LOG_FILES}/${CURRENT_LOG_DIR}''')    modules=os
    # Ellenőrzés: ha a log könyvtár név hiányzik vagy hibás, ne folytasd!
    IF    '${CURRENT_LOG_DIR}' == '' or '${CURRENT_LOG_DIR}' == 'MISSING_LOG_DIR'
        Log    [HIBÁZOTT] A log könyvtár neve hiányzik vagy hibás (CURRENT_LOG_DIR = ${CURRENT_LOG_DIR}), log merge kihagyva!
        RETURN
    END
    ${LOG_OUTPUT_XML}=    Evaluate    __import__('os').path.normpath(r'''${LOG_OUTPUT_DIR}/output.xml''')    modules=os
    ${ROBOT_OUTPUT_XML}=    Evaluate    __import__('os').path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/output.xml''')    modules=os
    ${ROBOT_OUTPUT_LOG}=    Evaluate    __import__('os').path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/log.html''')    modules=os
   ${ROBOT_OUTPUT_REPORT}=    Evaluate    __import__('os').path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/report.html''')    modules=os
   #Másolás a log és report fájlok a log könyvtárba
    Copy File    ${ROBOT_OUTPUT_LOG}    ${LOG_OUTPUT_DIR}/r_log.html
    Copy File    ${ROBOT_OUTPUT_REPORT}    ${LOG_OUTPUT_DIR}/r_report.html
    RETURN
  
    ${LOG_OUTPUT_XML_EXISTS}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${LOG_OUTPUT_XML}
    ${ROBOT_OUTPUT_XML_EXISTS}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${ROBOT_OUTPUT_XML}
    ${LOG_OUTPUT_XML_SIZE}=    Run Keyword If    ${LOG_OUTPUT_XML_EXISTS}    Get File Size    ${LOG_OUTPUT_XML}    ELSE    Set Variable    0
    ${ROBOT_OUTPUT_XML_SIZE}=    Run Keyword If    ${ROBOT_OUTPUT_XML_EXISTS}    Get File Size    ${ROBOT_OUTPUT_XML}    ELSE    Set Variable    0
    Log    [REBOT][ELLENŐRZÉS] ${LOG_OUTPUT_XML} létezik: ${LOG_OUTPUT_XML_EXISTS}, méret: ${LOG_OUTPUT_XML_SIZE}
    Log    [REBOT][ELLENŐRZÉS] ${ROBOT_OUTPUT_XML} létezik: ${ROBOT_OUTPUT_XML_EXISTS}, méret: ${ROBOT_OUTPUT_XML_SIZE}
    ${can_run_rebot}=    Evaluate    ${LOG_OUTPUT_XML_EXISTS} and ${ROBOT_OUTPUT_XML_EXISTS} and ${LOG_OUTPUT_XML_SIZE} > 0 and ${ROBOT_OUTPUT_XML_SIZE} > 0
    IF    not ${can_run_rebot}
        Log    [HIBÁZOTT] rebot kihagyva: input XML(ek) hiányoznak vagy üresek!
        RETURN
    END

    # output.xml tartalom ellenőrzése IF/END blokkokkal
    ${log_output_xml_valid}=    Set Variable    True
    IF    ${LOG_OUTPUT_XML_EXISTS}
        ${log_output_xml_size}=    Get File Size    ${LOG_OUTPUT_XML}
        Log    [REBOT][ELLENŐRZÉS] ${LOG_OUTPUT_XML} mérete: ${log_output_xml_size}
        ${log_output_xml_valid}=    Set Variable    False
        FOR    ${retry}    IN RANGE    1    6
            ${log_output_xml_content}=    Get File    ${LOG_OUTPUT_XML}
            ${log_output_xml_valid}=    Run Keyword And Return Status    Should Contain    ${log_output_xml_content}    </robot>
            IF    ${log_output_xml_valid}
                Log    [REBOT][ELLENŐRZÉS] ${LOG_OUTPUT_XML} végén megtaláltuk a </robot> taget a(z) ${retry}. próbálkozásra.
                Exit For Loop
            ELSE
                Log    [REBOT][ELLENŐRZÉS] ${LOG_OUTPUT_XML} végén NINCS </robot> tag! ${retry}/5 próbálkozás. Várakozás 1s...
                Sleep    1s
            END
        END
        IF    not ${log_output_xml_valid}
            Log    [HIBÁZOTT] ${LOG_OUTPUT_XML} hibás vagy csonka! Hiányzik a </robot> záró tag!
            #Fail    Hiányzik a </robot> záró tag a ${LOG_OUTPUT_XML} fájlból!
        END
        IF    ${log_output_xml_size} == 0
            Log    [HIBÁZOTT] ${LOG_OUTPUT_XML} üres fájl!
            #Fail    ${LOG_OUTPUT_XML} üres fájl!
        END
    END
    # Ugyanez a másik output.xml-re
    ${robot_output_xml_valid}=    Set Variable    True
    IF    ${ROBOT_OUTPUT_XML_EXISTS}
        ${robot_output_xml_size}=    Get File Size    ${ROBOT_OUTPUT_XML}
        Log    [REBOT][ELLENŐRZÉS] ${ROBOT_OUTPUT_XML} mérete: ${robot_output_xml_size}
        ${robot_output_xml_valid}=    Set Variable    False
        FOR    ${retry}    IN RANGE    1    6
            ${robot_output_xml_content}=    Get File    ${ROBOT_OUTPUT_XML}
            ${robot_output_xml_valid}=    Run Keyword And Return Status    Should Contain    ${robot_output_xml_content}    </robot>
            IF    ${robot_output_xml_valid}
                Log    [REBOT][ELLENŐRZÉS] ${ROBOT_OUTPUT_XML} végén megtaláltuk a </robot> taget a(z) ${retry}. próbálkozásra.
                Exit For Loop
            ELSE
                Log    [REBOT][ELLENŐRZÉS] ${ROBOT_OUTPUT_XML} végén NINCS </robot> tag! ${retry}/5 próbálkozás. Várakozás 1s...
                Sleep    1s
            END
        END
        IF    not ${robot_output_xml_valid}
            Log    [HIBÁZOTT] ${ROBOT_OUTPUT_XML} hibás vagy csonka! Hiányzik a </robot> záró tag!
            Fail    Hiányzik a </robot> záró tag a ${ROBOT_OUTPUT_XML} fájlból!
        END
        IF    ${robot_output_xml_size} == 0
            Log    [HIBÁZOTT] ${ROBOT_OUTPUT_XML} üres fájl!
             Fail    ${ROBOT_OUTPUT_XML} üres fájl! 
        END
    END
    Log    [REBOT] Fájlok összefűzése: ${LOG_OUTPUT_XML} + ${ROBOT_OUTPUT_XML}
    ${log_output_dir_exists}=    Run Keyword And Return Status    OperatingSystem.Directory Should Exist    ${LOG_OUTPUT_DIR}
    IF    ${log_output_dir_exists}
        ${MERGED_LOG}=    Evaluate    __import__('os').path.normpath(r'''${LOG_OUTPUT_DIR}/mergedlog.html''')    modules=os
        ${MERGED_REPORT}=    Evaluate    __import__('os').path.normpath(r'''${LOG_OUTPUT_DIR}/mergedreport.html''')    modules=os
        Log     =======================REBOT START=========================
        ${rebot_max_attempts}=    Set Variable    3
        ${rebot_retry_wait}=    Set Variable    3
        ${rebot_attempt}=    Set Variable    1
        ${merged_log_ok}=    Set Variable    False
        # rebot.bat generálása a log könyvtárba
        ${REBOT_BAT_PATH}=    Evaluate    __import__('os').path.normpath(r'''${LOG_OUTPUT_DIR}/rebot.bat''')    modules=os
        ${REBOT_CMD}=    Set Variable    rebot --rpa --log "${MERGED_LOG}" --report "${MERGED_REPORT}" "${LOG_OUTPUT_XML}" "${ROBOT_OUTPUT_XML}"
       
       #robot log átmásolása log könyvtárba

        #Create File    ${REBOT_BAT_PATH}    @echo off\ncd /d "%~dp0"\n${REBOT_CMD}\n
        #Log    [REBOT][BAT] rebot.bat generálva: ${REBOT_BAT_PATH}\nTartalom: ${REBOT_CMD}
        WHILE    ${rebot_attempt} <= ${rebot_max_attempts} and not ${merged_log_ok}
            Log    [REBOT][PRÓBA] ${rebot_attempt}. próbálkozás a log összefűzésre...
            Sleep    2s
            
            ${rebot_result}=    Run Process    rebot    --rpa    --log    ${MERGED_LOG}    --report    ${MERGED_REPORT}    ${LOG_OUTPUT_XML}    ${ROBOT_OUTPUT_XML}    shell=True    cwd=${LOG_OUTPUT_DIR}    timeout=60s
            Run Keyword If    '${rebot_result}' == 'None'    Log    [HIBÁZOTT] rebot_result None! A rebot processz nem indult el vagy hibás paramétereket kapott. Parancs: rebot --rpa --log ${MERGED_LOG} --report ${MERGED_REPORT} ${LOG_OUTPUT_XML} ${ROBOT_OUTPUT_XML} | cwd: ${LOG_OUTPUT_DIR}
            Run Keyword If    '${rebot_result}' == 'None'    Log    [HIBÁZOTT] Paraméterek: MERGED_LOG=${MERGED_LOG}, MERGED_REPORT=${MERGED_REPORT}, LOG_OUTPUT_XML=${LOG_OUTPUT_XML}, ROBOT_OUTPUT_XML=${ROBOT_OUTPUT_XML}, LOG_OUTPUT_DIR=${LOG_OUTPUT_DIR}
            Run Keyword If    '${rebot_result}' != 'None'    Log    [REBOT] rc: ${rebot_result.rc}
            Run Keyword If    '${rebot_result}' != 'None'    Log    [REBOT] stdout: ${rebot_result.stdout}
            Run Keyword If    '${rebot_result}' != 'None'    Log    [REBOT] stderr: ${rebot_result.stderr}
            ${MERGED_LOG_EXISTS}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${LOG_OUTPUT_DIR}/mergedlog.html
            IF    ${MERGED_LOG_EXISTS}
                Log    [REBOT][SIKER] mergedlog.html sikeresen létrejött a(z) ${rebot_attempt}. próbálkozásra.
                ${merged_log_ok}=    Set Variable    True
            ELSE
                Log    [HIBÁZOTT] mergedlog.html NEM jött létre! stdout: ${rebot_result.stdout} stderr: ${rebot_result.stderr}
                Log    [REBOT][PRÓBA] Várakozás ${rebot_retry_wait} másodpercet az újrapróbálkozás előtt...
                Sleep    ${rebot_retry_wait}
                ${rebot_attempt}=    Evaluate    ${rebot_attempt} + 1
            END
        END
        Run Keyword If    not ${merged_log_ok}    Log    [HIBÁZOTT] mergedlog.html nem jött létre ${rebot_max_attempts} próbálkozás után sem! Ellenőrizd a bemeneti output.xml fájlokat!
    ELSE
        Log    [HIBÁZOTT] A log könyvtár nem létezik: ${LOG_OUTPUT_DIR}, rebot futtatás kihagyva!
    END
    Log     \n=== MINDEN LÉPÉS BEFEJEZŐDÖTT ===
    Log     WORKFLOW_STATUS = ${WORKFLOW_STATUS}

Feloldott könyvtár változók

    ${USERPROFILE}=    Get Environment Variable    USERPROFILE
    ${DOWNLOADED_ROBOTS}=    Set Variable    ${USERPROFILE}/MyRobotFramework/DownloadedRobots
    Set Suite Variable    ${DOWNLOADED_ROBOTS}
    ${SANDBOX_ROBOTS}=    Set Variable    ${USERPROFILE}/MyRobotFramework/SandboxRobots
    Set Suite Variable    ${SANDBOX_ROBOTS}
    ${LOG_FILES}=    Set Variable    ${USERPROFILE}/MyRobotFramework/RobotResults
    Set Suite Variable    ${LOG_FILES}

    # Aktuális log könyvtár csak változóban, nincs fájl írás/olvasás
    Log    [LOGDIR] Aktuális log könyvtár: ${CURRENT_LOG_DIR}

*** Test Cases ***
    # Feloldott könyvtár változók (kulcsszó, nem teszteset)
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
    ${START_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/start.bat
    ${start_script_exists}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${START_SCRIPT}
    
    IF    ${start_script_exists}
        Log     Robot már telepítve van: ${START_SCRIPT}
        Set Global Variable    ${WORKFLOW_STATUS}    'READY_TO_RUN'
    ELSE
        Log     Robot nincs telepítve, ellenőrizzük a letöltöttséget...
        
        # Letöltött robot ellenőrzése
        IF        ${SANDBOX_MODE} == True
             ${REPO_PATH}=     Set Variable    ${SANDBOX_ROBOTS}/${REPO}
        ELSE
             ${REPO_PATH}=     Set Variable    ${DOWNLOADED_ROBOTS}/${REPO} 
        END
          
        ${BRANCH_PATH}=   Set Variable    ${REPO_PATH}/${BRANCH}
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
               ${TARGET_DIR}=    Set Variable    ${SANDBOX_ROBOTS}/${REPO}/${BRANCH}
           ELSE
               ${TARGET_DIR}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}
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
        ${install_result}=    Run Process    cmd    /c    start    /wait    cmd    /c    ${INSTALL_SCRIPT}    shell=True    cwd=${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}    timeout=120s
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
          ${RUN_SCRIPT}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/start.bat
          Log     [FUTTATÁS] start.bat elérési út: ${RUN_SCRIPT}
          Log     [FUTTATÁS] Futtatás könyvtára: ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}

          # Log könyvtár nevét csak a backend (flask_app.py) generálja és írja current_log_dir.txt-be
          # Itt csak olvassuk a Suite Setup-ban beállított CURRENT_LOG_DIR értéket
          ${LOG_OUTPUT_DIR}=    Set Variable    ${LOG_FILES}/${CURRENT_LOG_DIR}
          Log     [FUTTATÁS] Log könyvtár: ${LOG_OUTPUT_DIR}

          Log     [FUTTATÁS] Robot script indítása blokkoló módon: ${RUN_SCRIPT}
          ${WORKDIR}=    Evaluate    os.path.normpath(r'''${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}''')    modules=os
          ${run_result}=    Run Process    ${RUN_SCRIPT}      shell=True    cwd=${WORKDIR}    timeout=600s
          Log     [FUTTATÁS] Run Process rc: ${run_result.rc}
          Log     [FUTTATÁS] Run Process stdout: ${run_result.stdout}
          Log     [FUTTATÁS] Run Process stderr: ${run_result.stderr}
          IF    ${run_result.rc} == 0
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

#Log fájlok összefűzése
#    [Documentation]    A futtatás után összefűzi a log fájlokat rebot --rpa paranccsal, a futás elején eltárolt log könyvtárat használva.
#    #
#    # Log fájlok összefűzése
#    # rebot  --rpa output_master.xml output_slave.xml

    # output.xml összefűzése rebot --rpa paranccsal, a futás elején eltárolt log könyvtárat használva
#    ${LOG_OUTPUT_DIR}=    Set Variable    ${LOG_FILES}/${CURRENT_LOG_DIR}
#    ${LOG_OUTPUT_XML}=    Set Variable    ${LOG_OUTPUT_DIR}/output.xml
#    ${ROBOT_OUTPUT_XML}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}/output.xml
#    ${LOG_OUTPUT_XML_EXISTS}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${LOG_OUTPUT_XML}
#    ${ROBOT_OUTPUT_XML_EXISTS}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${ROBOT_OUTPUT_XML}
#    Log    [REBOT][ELLENŐRZÉS] ${LOG_OUTPUT_XML} létezik: ${LOG_OUTPUT_XML_EXISTS}
#    Log    [REBOT][ELLENŐRZÉS] ${ROBOT_OUTPUT_XML} létezik: ${ROBOT_OUTPUT_XML_EXISTS}
    # output.xml tartalom ellenőrzése IF/END blokkokkal
#    ${log_output_xml_valid}=    Set Variable    True
#    IF    ${LOG_OUTPUT_XML_EXISTS}
#        ${log_output_xml_size}=    Get File Size    ${LOG_OUTPUT_XML}
#        Log    [REBOT][ELLENŐRZÉS] ${LOG_OUTPUT_XML} mérete: ${log_output_xml_size}
#        ${log_output_xml_content}=    Get File    ${LOG_OUTPUT_XML}
#        ${log_output_xml_valid}=    Run Keyword And Return Status    Should Contain    ${log_output_xml_content}    </robot>
#        IF    not ${log_output_xml_valid}
#            Log    [HIBÁZOTT] ${LOG_OUTPUT_XML} hibás vagy csonka! Hiányzik a </robot> záró tag!
#        END
#        IF    ${log_output_xml_size} == 0
#            Log    [HIBÁZOTT] ${LOG_OUTPUT_XML} üres fájl!
#        END
#    END
#    # Ugyanez a másik output.xml-re
#    ${robot_output_xml_valid}=    Set Variable    True
#    IF    ${ROBOT_OUTPUT_XML_EXISTS}
#        ${robot_output_xml_size}=    Get File Size    ${ROBOT_OUTPUT_XML}
#        Log    [REBOT][ELLENŐRZÉS] ${ROBOT_OUTPUT_XML} mérete: ${robot_output_xml_size}
#        ${robot_output_xml_content}=    Get File    ${ROBOT_OUTPUT_XML}
#        ${robot_output_xml_valid}=    Run Keyword And Return Status    Should Contain    ${robot_output_xml_content}    </robot>
#        IF    not ${robot_output_xml_valid}
#            Log    [HIBÁZOTT] ${ROBOT_OUTPUT_XML} hibás vagy csonka! Hiányzik a </robot> záró tag!
#        END
#        IF    ${robot_output_xml_size} == 0
#            Log    [HIBÁZOTT] ${ROBOT_OUTPUT_XML} üres fájl!
#        END
#    END
#    Log    [REBOT] Fájlok összefűzése: ${LOG_OUTPUT_XML} + ${ROBOT_OUTPUT_XML}
#    ${rebot_result}=    Run Process    rebot    --rpa    --log    ${LOG_OUTPUT_DIR}/mergedlog.html    --report    ${LOG_OUTPUT_DIR}/mergedreport.html    ${LOG_OUTPUT_XML}    ${ROBOT_OUTPUT_XML}    shell=True    cwd=${LOG_OUTPUT_DIR}    timeout=60s
#    Log    [REBOT] rc: ${rebot_result.rc}
#    Log    [REBOT] stdout: ${rebot_result.stdout}
#    Log    [REBOT] stderr: ${rebot_result.stderr}
#    ${MERGED_LOG_EXISTS}=    Run Keyword And Return Status    OperatingSystem.File Should Exist    ${LOG_OUTPUT_DIR}/mergedlog.html
#    Run Keyword If    not ${MERGED_LOG_EXISTS}    Log    [HIBÁZOTT] mergedlog.html NEM jött létre! stdout: ${rebot_result.stdout} stderr: ${rebot_result.stderr}
#    Run Keyword If    not ${MERGED_LOG_EXISTS}    Log    [HIBÁZOTT] Ellenőrizd, hogy a bemeneti output.xml fájlok léteznek-e!
    Log     \n=== MINDEN LÉPÉS BEFEJEZŐDÖTT ===
    Log     WORKFLOW_STATUS = ${WORKFLOW_STATUS}