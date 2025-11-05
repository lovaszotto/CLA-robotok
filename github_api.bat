@echo off 
REM ========================================= 
REM  CLA-SSISTANT - GITHUB API KEZELO 
REM ========================================= 
echo. 
echo ========================================= 
echo   GITHUB REPOSITORY LISTA LEKERES 
echo   API Owner: lovaszotto 
echo ========================================= 
echo. 
 
echo GitHub repository lista lekerese... 
rf_env\Scripts\python.exe fetch_github_repos.py lovaszotto 
echo. 
echo Repository-k es branch-ek feldolgozasa... 
rf_env\Scripts\python.exe parse_repos.py 
echo. 
echo Eredmeny HTML generalva: repository_branches_table.html 
pause 
