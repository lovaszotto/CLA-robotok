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
    ${GIT_URL}=    Set Variable    ${GIT_URL_BASE}${REPO}.git
    Set Global Variable    ${GIT_URL}    ${GIT_URL}
    Log To Console     Repository: ${GIT_URL}
    Log To Console     Branch: ${BRANCH}
    Log To Console     =========================\n
Letöltöttség ellenőrzése
    [Documentation]    Ellenőrzi, hogy a REPO és BRANCH ban megadott értékekhez létezik-e mappa.
    Log To Console     \n=== LETÖLTÖTTSÉG ELLENŐRZÉSE ===
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
        Log To Console     \nMindkét könyvtár létezik! ✓
        Set Global Variable    ${WORKFLOW_STATUS}    'DONE'
    ELSE
        Set Global Variable    ${WORKFLOW_STATUS}    'MAKE_DIRS'    
    END

Könyvtárak létrehozása
    [Documentation]    Létrehozza a szükséges könyvtárakat, ha még nem léteznek.    
    IF    $WORKFLOW_STATUS == 'MAKE_DIRS'

        Log To Console     ======Könyvtár létrehozás===================\n
        #létrehozzuk a repository könyvtárat, ha nem létezik
        Create Directory    ${REPO_PATH}
        Log To Console     Létrehozva a repository könyvtár: ${REPO_PATH}
        #létrehozzuk a branch könyvtárat, ha nem létezik
        Create Directory    ${BRANCH_PATH}
        Log To Console     Létrehozva a branch könyvtár: ${BRANCH_PATH}

         Set Global Variable    ${WORKFLOW_STATUS}    'TO_BE_CLONE'
        # Klónozáshoz szükséges változók újbóli beállítása (biztonsági okokból)
        ${GIT_URL}=    Set Variable    ${GIT_URL_BASE}${REPO}.git
        Set Global Variable    ${GIT_URL}    ${GIT_URL}
        Log To Console     Globálisan beállítva: GIT_URL = ${GIT_URL}

        #Set Global Variable    ${BRANCH}    ${BRANCH}
        Log To Console     Globálisan beállítva: BRANCH = ${BRANCH}
        ${TARGET_DIR}=    Set Variable    ${BRANCH_PATH}
        Log To Console     TARGET_DIR = ${TARGET_DIR}
        
   END
  
    

Branch klónozása
    [Documentation]    A REPO és BRANCH változók alapján klónozza a megfelelő könyvtárat, ha még nincs letöltve.
    Log To Console    Branch klónozása WORKFLOW_STATUS = ${WORKFLOW_STATUS}    
    IF    ${WORKFLOW_STATUS} == 'TO_BE_CLONE'
        ${TARGET_DIR}=    Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}/${BRANCH}
        Log To Console     \nGit parancs: git clone -b ${BRANCH} --single-branch ${GIT_URL} ${TARGET_DIR}
        ${result}=    Run Process    git    clone    -b    ${BRANCH}    --single-branch    ${GIT_URL}    ${TARGET_DIR}    shell=True
        Should Be Equal As Integers    ${result.rc}    0    Klónozás sikertelen: ${result.stderr}
        Set Global Variable    ${WORKFLOW_STATUS}    'CLONING'
     END

    IF    ${WORKFLOW_STATUS} == 'CLONING'
        Log To Console    Már folyamatban van egy klónozás. Várakozás a befejezésre...
        Wait Until Keyword Succeeds    5 min    10 sec    Run Keyword And Return Status    OperatingSystem.Directory Should Exist    ${TARGET_DIR}
        ${downloaded_robot_exists}=    Run Keyword And Return Status    OperatingSystem.Directory Should Exist    ${TARGET_DIR}
        IF    ${downloaded_robot_exists}
            Log To Console    A klónozás befejeződött, a könyvtár már létezik: ${TARGET_DIR} 
        END
    END
  
