*** Settings ***
Documentation     CLA-Developer robot: Robot letöltése a központi nyilvántartásból, módosítása és visszatöltése a nyilvántartásba
Library           OperatingSystem
Library           SeleniumLibrary
Library           Process
Suite Teardown    Log To Console    Git parancsok végrehajtva    

*** Test Cases ***
Robot letöltése a központi nyilvántartásból
    [Documentation]    Az elkészült új robot letöltése a Központi Nyilvántartásból
    # Itt add meg a letöltés lépéseit Robot Framework szintaxissal
    Log To Console    Letöltés sikeresen elindult
    # lépjen be a https://github.com/lovaszotto?tab=repositories oldalra
    # jelenítse meg chrome-ban
    Open Browser    https://github.com/lovaszotto?tab=repositories    chrome
    Maximize Browser Window
    # A böngésző nyitva marad további műveletekhez
    #Log    Böngésző megnyitva - kézi bezárásig nyitva marad
    Sleep    30s    # Várakozás 30 másodpercig, hogy megtekinthesse az oldalt
    # klónozza a repository-t
    # lépjen be a letöltött mappába
    # végezze el a szükséges módosításokat
    # töltse vissza a módosított robotot a Központi Nyilvántartásba
    # Megjegyzés: A böngésző nem lesz automatikusan bezárva
    # kérje le a repository listát Git parancsokkal a GitHub API-ból
    #Log To Console    Repository lista lekérése Git parancsokkal...
    
    # GitHub API hívás a repository lista lekéréséhez
    ${result}=    Run Process    curl    -s    https://api.github.com/users/lovaszotto/repos    shell=True
    Log To Console    GitHub API válasz státusz: ${result.rc}
    
    # Ha a curl parancs sikeres volt
    IF    ${result.rc} == 0
        Log To Console    Repository adatok sikeresen lekérve
        
        # Mentjük a választ fájlba további feldolgozáshoz
        Create File    repos_response.json    ${result.stdout}
        Log To Console    Repository adatok mentve repos_response.json fájlba
        
        # JSON feldolgozás Python script-tel - repository-k és branch-ek listázása
        Log To Console    Repository-k és branch-ek lekérése...
        ${python_result}=    Run Process    python    parse_repos.py    shell=True    timeout=120s
        Log To Console    ${python_result.stdout}
        
        IF    '${python_result.stderr}' != ''
            Log To Console    Python hiba: ${python_result.stderr}
        END
        
    ELSE
        Log To Console    Hiba a repository lista lekérésében: ${result.stderr}
        
        # Fallback: Git parancs használata egy ismert repository klónozásához
        Log To Console    Fallback: Ismert repository klónozása...
        ${git_result}=    Run Process    git    ls-remote    --heads    https://github.com/lovaszotto/CLA-ROBOTOK.git    shell=True
        Log To Console    Git ls-remote eredmény: ${git_result.stdout}
    END
    