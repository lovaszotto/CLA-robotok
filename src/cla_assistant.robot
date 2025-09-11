*** Settings ***
Documentation     CLA-Assistant Robot Framework tesztrobot
Library           OperatingSystem
Library           Collections

*** Variables ***
${CLA_FILE}       config.json

*** Test Cases ***
CLA Ellenőrzés
    [Documentation]    Ellenőrzi, hogy a CLA konfigurációs fájl létezik-e
    File Should Exist    ${CLA_FILE}
    Log    CLA konfigurációs fájl megtalálva: ${CLA_FILE}

CLA Verzió Ellenőrzés
    [Documentation]    Ellenőrzi, hogy a CLA verzió helyes-e
    ${config}=    Get File    ${CLA_FILE}
    Should Contain    ${config}    "version": "1.0.0"
    Log    CLA verzió helyes: 1.0.0
