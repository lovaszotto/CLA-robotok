*** Settings ***
Library           OperatingSystem
Library    Process
#Resource    resources/keywords.robot
Resource    ./resources/variables.robot

*** Variables ***
${REPO}           CLA-robotok-test
${BRANCH}         CLA-Developer-test

*** Test Cases ***
Kiírás konzolra paraméterekből
    [Documentation]    A REPO és BRANCH változók értékeinek kiírása.
    Log To Console     \n=== KIVÁLASZTOTT ROBOT ===
    Log To Console     Repository: ${REPO}
    Log To Console     Branch: ${BRANCH}
    Log To Console     =========================\n
Letöltöttség ellenőrzése
    [Documentation]    Ellenőrzi, hogy a REPO és BRANCH ban megadott értékekhez létezik-e mappa.
    Log To Console     \n=== LETÖLTÖTTSÉG ELLENŐRZÉSE ===
    ${repo_path}=     Set Variable    ${DOWNLOADED_ROBOTS}/${REPO}    
    ${branch_path}=   Set Variable    ${repo_path}/${BRANCH}

    Log To Console     Full Repository: ${repo_path}
    Log To Console     Full Branch: ${branch_path}
    #könyvtár létezésének ellenőrzése

    ${downloaded_repo_exists}=     Run Keyword And Return Status    OperatingSystem.Directory Should Exist     ${repo_path}
    ${downloaded_robot_exists}=    Run Keyword And Return Status    OperatingSystem.Directory Should Exist    ${branch_path}
    
    IF     ${downloaded_repo_exists} and ${downloaded_robot_exists}
        #visszatér a tesztből
        #todo verzió alapján újra letöltés
        Log To Console     \nMindkét könyvtár létezik! ✓
        Pass Execution    Mindkét könyvtár létezik! Nem szükséges új letöltés.
    END
    
    Log To Console     ======Könyvtár létrehozás===================\n
    #létrehozzuk a repository könyvtárat, ha nem létezik
    IF    not ${downloaded_repo_exists}
        Create Directory    ${repo_path}
        Log To Console     Létrehozva a repository könyvtár: ${repo_path}
    END            
    #létrehozzuk a branch könyvtárat, ha nem létezik
    IF    not ${downloaded_robot_exists}
        Create Directory    ${branch_path}
        Log To Console     Létrehozva a branch könyvtár: ${branch_path}
    END            

    Log To Console     ===========Git clone indul!==============\n
    #git clone parancs végrehajtása a megadott repository és branch letöltéséhez
    ${git_clone_result}=    Run Process    git    clone    --branch    ${BRANCH}    ${repo_path}
    Log To Console     Git clone eredmény: ${git_clone_result.stdout}
    Log To Console     Git clone hiba (ha van): ${git_clone_result.stderr}
    