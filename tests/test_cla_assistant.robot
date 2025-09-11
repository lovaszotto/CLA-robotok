*** Settings ***
Documentation     CLA-Assistant Robot Framework tesztesetek
Resource          ../src/cla_assistant.robot

*** Test Cases ***
CLA Fájl Létezik
    [Tags]    smoke
    File Should Exist    ${CLA_FILE}

CLA Verzió Megfelel
    [Tags]    regression
    ${config}=    Get File    ${CLA_FILE}
    Should Contain    ${config}    "version": "1.0.0"
