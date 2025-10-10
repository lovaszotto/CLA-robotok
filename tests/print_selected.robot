*** Settings ***
Documentation     Egyszerű teszt, ami a paraméterben kapott repository és branch értékeket kiírja a konzolra.
Library           OperatingSystem

*** Variables ***
${REPO}           ${EMPTY}
${BRANCH}         ${EMPTY}

*** Test Cases ***
Kiírás konzolra paraméterekből
    [Documentation]    A REPO és BRANCH változók értékeinek kiírása.
    Log To Console     \n=== KIVÁLASZTOTT ROBOT ===
    Log To Console     Repository: ${REPO}
    Log To Console     Branch: ${BRANCH}
    Log To Console     =========================\n

*** Keywords ***
# Nincs extra keyword, a teszt egyszerű kiírást végez.