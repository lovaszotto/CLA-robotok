*** Settings ***
Documentation    Egyedi kulcsszavak a CLA-ssistant robotokhoz

*** Keywords ***
Log Everywhere
    [Documentation]    Egyszerre írja ki az üzenetet a Robot Framework logfájlba és a konzolra.
    [Arguments]    ${message}    ${level}=INFO    ${stream}=STDOUT
    Log    ${message}    level=${level}
    Log To Console    ${message}    stream=${stream}
