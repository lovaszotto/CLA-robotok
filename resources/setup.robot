*** Settings ***
Documentation     Python környezet inicializálás és dinamikus változók beállítása
Library           ../libraries/PythonUtils.py
Resource          variables.robot

*** Keywords ***
Initialize Python Environment
    [Documentation]    Dinamikusan beállítja a Python executable és egyéb környezeti változókat
    
    # Python executable dinamikus meghatározása
    ${python_path}=    Get Python Executable
    Set Global Variable    ${PYTHON_EXEC}    ${python_path}
    
    # Python verzió lekérése és logolása
    ${python_version}=    Get Python Version    ${python_path}
    Log    Python executable: ${python_path}
    Log    Python verzió: ${python_version}
    
    # Virtuális környezet ellenőrzése
    ${venv_path}=    Get Virtual Env Path
    IF    "${venv_path}" != ""
        Log    Virtuális környezet észlelve: ${venv_path}
        Set Global Variable    ${VENV_PATH}    ${venv_path}
    ELSE
        Log    Nincs virtuális környezet
        Set Global Variable    ${VENV_PATH}    ${EMPTY}
    END
    
    # Munkakönyvtár logolása
    ${work_dir}=    Get Working Directory
    Log    Aktuális munkakönyvtár: ${work_dir}
    
    # Python executable elérhetőség ellenőrzése
    ${is_available}=    Check Python Executable Exists    ${python_path}
    IF    not ${is_available}
        Fail    Python executable nem elérhető: ${python_path}
    END
    
    Log    Python környezet sikeresen inicializálva

Set Dynamic Repository Variables
    [Documentation]    Beállítja a dinamikus repository változókat a Flask paraméterek alapján
    [Arguments]    ${repo_name}=${REPO}    ${branch_name}=${BRANCH}
    
    # Repository és branch változók frissítése
    Set Global Variable    ${REPO}           ${repo_name}
    Set Global Variable    ${BRANCH}         ${branch_name}
    
    # URL összeállítása
    ${full_url}=    Set Variable    ${GIT_URL_BASE}${repo_name}.git
    Set Global Variable    ${GIT_URL}        ${full_url}
    
    # Repository útvonal összeállítása
    ${repo_path}=    Set Variable    ${DOWNLOADED_ROBOTS}${/}${repo_name}
    Set Global Variable    ${REPO_PATH}      ${repo_path}
    
    # Branch útvonal összeállítása
    ${branch_path}=    Set Variable    ${repo_path}${/}${branch_name}
    Set Global Variable    ${BRANCH_PATH}    ${branch_path}
    
    # Target könyvtár beállítása
    IF    ${SANDBOX_MODE}
        ${target}=    Set Variable    ${SANDBOX_ROBOTS}${/}${repo_name}${/}${branch_name}
    ELSE
        ${target}=    Set Variable    ${INSTALLED_ROBOTS}${/}${repo_name}${/}${branch_name}
    END
    Set Global Variable    ${TARGET_DIR}     ${target}
    
    Log    Repository változók beállítva:
    Log    - REPO: ${REPO}
    Log    - BRANCH: ${BRANCH}
    Log    - GIT_URL: ${GIT_URL}
    Log    - TARGET_DIR: ${TARGET_DIR}

Log Environment Status
    [Documentation]    Kiírja a jelenlegi környezeti változók állapotát
    
    Log    === KÖRNYEZETI VÁLTOZÓK ÁLLAPOTA ===
    Log    Python executable: ${PYTHON_EXEC}
    #Log    Virtuális környezet: ${VENV_PATH}
    Log    Repository: ${REPO}
    Log    Branch: ${BRANCH}
    Log    Git URL: ${GIT_URL}
    Log    Cél könyvtár: ${TARGET_DIR}
    Log    Sandbox mód: ${SANDBOX_MODE}
    Log    Workflow státusz: ${WORKFLOW_STATUS}