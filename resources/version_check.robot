*** Settings ***
Library    RequestsLibrary
Library    JSONLibrary
Library    OperatingSystem
Library    Collections
Library    String

*** Variables ***
${GITHUB_API}               https://api.github.com
${REPO_OWNER}               lovaszotto
${REPO_NAME}                KBSZ-robotok
${INSTALLED_VERSION_DIR}    installed_versions

# Ha több robotod van, mindegyikhez tartozhat egy branch
&{ROBOT_BRANCH}    robot_a=KBSZ-robotok   


# Release létrehozó parancs 
# gh release create v1.0.0 --title "v1.0.0" --notes "Első stabil verzió"


*** Keywords ***
Get Latest Release Tag For Branch
    [Arguments]    ${branch}    ${owner}=${REPO_OWNER}    ${repo}=${REPO_NAME}
    Create Session    github    ${GITHUB_API}    verify=False
    ${resp}=    GET On Session    github    /repos/${owner}/${repo}/releases
    Should Be Equal As Integers    ${resp.status_code}    200
    ${releases}=    Set Variable    ${resp.json()}

    ${latest_tag}=    Set Variable    ${None}
    FOR    ${rel}    IN    @{releases}
        ${target}=    Get From Dictionary    ${rel}    target_commitish    ${None}
        Continue For Loop If    '${target}' != '${branch}'
        ${tag}=    Get From Dictionary    ${rel}    tag_name    ${None}
        ${latest_tag}=    Set Variable    ${tag}
        Exit For Loop
    END

    Run Keyword If    '${latest_tag}' == '${None}'    Fail    No release found for branch ${branch}
    RETURN    ${latest_tag}


Get Installed Version For Branch
    [Arguments]    ${branch}
    ${file}=    Set Variable    ${INSTALLED_VERSION_DIR}/${branch}.txt
    ${exists}=    Run Keyword And Return Status    File Should Exist    ${file}
    IF    not ${exists}
        ${content}=    Set Variable    NONE
    ELSE
        ${content}=    Get File    ${file}
        ${content}=    String.Strip String    ${content}
    END
    RETURN    ${content}


Save Installed Version For Branch
    [Arguments]    ${branch}    ${version}
    Create Directory    ${INSTALLED_VERSION_DIR}
    ${file}=    Set Variable    ${INSTALLED_VERSION_DIR}/${branch}.txt
    Create File    ${file}    ${version}


Check For New Version For Branch
    [Arguments]    ${branch}
    ${latest}=       Get Latest Release Tag For Branch    ${branch}
    ${installed}=    Get Installed Version For Branch     ${branch}

    Log To Console   \n=== VERSION CHECK (${branch}) ===
    Log To Console   Latest release: ${latest}
    Log To Console   Installed version: ${installed}

    Run Keyword If    '${installed}' == 'NONE'    Log To Console    No installed version found for branch ${branch}. Treat as not installed.

    ${is_new}=    Run Keyword And Return Status    Should Be Equal    ${latest}    ${installed}
    Run Keyword If    not ${is_new}
    ...    Log To Console    *** NEW VERSION AVAILABLE on ${branch}: ${latest} (installed: ${installed}) ***
    ...  ELSE
    ...    Log To Console    Branch ${branch} already up to date.

    RETURN    ${is_new}


Check All Robots Up To Date
    # Végigmegy a ROBOT_BRANCH mappingen és megnézi mindet
    FOR    ${name}    ${branch}    IN    &{ROBOT_BRANCH}
        Log To Console    \n>>> Checking robot: ${name} (branch: ${branch})
        Check For New Version For Branch    ${branch}
    END


*** Test Cases ***
Check Versions Before Run
    # Ezt beteheted egy külön suite-ba, vagy a futtatás elejére
    Set Environment Variable    PYTHONWARNINGS    ignore::InsecureRequestWarning
    Check All Robots Up To Date
