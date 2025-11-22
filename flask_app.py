# --- Kliensoldali logolás endpoint (app példányosítás után, route-ok között) ---
# --- Kliensoldali hibák logolása ---
# (A Flask példányosítás után kell lennie!)
from flask import Flask, render_template, render_template_string, jsonify, request, send_from_directory, session
import json
import subprocess
import os
import sys
import re
import shutil
import html
import time
import threading
from datetime import datetime
import logging



# Töröljük a server.log tartalmát a futás elején
try:
    with open('server.log', 'w', encoding='utf-8') as f:
        f.write('')
except Exception:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'cla-ssistant-secret')


PYTHON_EXECUTABLE = sys.executable or 'python'



# --- Logging beállítás: minden log menjen a server.log fájlba is, konzolra is ---
log_formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')
file_handler = logging.FileHandler('server.log', encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Dupla handler elkerülése
if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == file_handler.baseFilename for h in root_logger.handlers):
    root_logger.addHandler(file_handler)
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    root_logger.addHandler(console_handler)

# Saját logger, propagate nélkül
logger = logging.getLogger("cla-ssistant")
logger.propagate = False
logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == file_handler.baseFilename for h in logger.handlers):
    logger.addHandler(file_handler)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    logger.addHandler(console_handler)


def get_sandbox_mode() -> bool:
    """Határozza meg, hogy a felület sandbox módban fusson-e."""
    # 1) Session alapú érték, ha a felhasználó már választott üzemmódot.
    printed = []
    try:
        if 'sandbox_mode' in session:
            return bool(session['sandbox_mode'])
    except Exception:
        pass

    # 2) Fallback: resources/variables.robot beállítása.
    try:
        variables_file = os.path.join('resources', 'variables.robot')
        if os.path.exists(variables_file):
            with open(variables_file, 'r', encoding='utf-8') as f:
                content = f.read()
                for line in content.split('\n'):
                    if line.strip().startswith('${SANDBOX_MODE}'):
                        if '${True}' in line:
                            return True
                        if '${False}' in line:
                            return False
    except Exception as e:
        logger.warning(f"[WARNING] Hiba a SANDBOX_MODE beolvasásakor: {e}")

    # 3) Végső alapértelmezés
    return False

# --- Segédfüggvények az InstalledRobots elérési út és könyvtár törléséhez ---
def get_robot_variable(var_name: str) -> str:
    """Beolvassa a resources/variables.robot fájlból a megadott változó értékét (csak DownloadedRobots/SandboxRobots támogatott)."""
    try:
        variables_file = os.path.join('resources', 'variables.robot')
        if not os.path.exists(variables_file):
            return ''
        with open(variables_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Robot Framework változó sorok: ${NAME}    value
                m = re.match(r"^\s*\$\{" + re.escape(var_name) + r"\}\s+(.+?)\s*$", line)
                if m:
                    return m.group(1).strip()
    except Exception as e:
        logger.warning(f"[WARNING] Hiba a(z) {var_name} beolvasásakor: {e}")
    return ''

def _normalize_dir_from_vars(var_name: str) -> str:
    """Visszaadja a variables.robot-ból olvasott könyvtár abszolút, normált útvonalát."""
    path = get_robot_variable(var_name)
    if not path:
        return ''
    # Mindig az aktuális user home könyvtárat használjuk, függetlenül a változó tartalmától
    home = os.path.expanduser('~')
    # Ha a változóban ${USER_HOME} vagy %USERPROFILE% vagy hasonló szerepel, azt figyelmen kívül hagyjuk
    # és mindenhol a home könyvtárat illesztjük be
    # Példák: ${USER_HOME}/MyRobotFramework/DownloadedRobots/ vagy %USERPROFILE%\MyRobotFramework\DownloadedRobots\
    # Kivesszük a változóban lévő home részt, és csak a relatív utat illesztjük a tényleges home elé
    import re
    # Eltávolítjuk az elejéről a home-ra utaló részt
    rel_path = re.sub(r'^(\${USER_HOME}|%USERPROFILE%|~)[/\\]?', '', path)
    full_path = os.path.join(home, rel_path)
    full_path = os.path.expandvars(os.path.expanduser(full_path))
    return os.path.normpath(full_path)

def get_installed_robots_dir() -> str:
    """Mindig a DownloadedRobots vagy SandboxRobots könyvtárat adja vissza, InstalledRobots megszűnt."""
    if get_sandbox_mode():
        dir_path = _normalize_dir_from_vars('SANDBOX_ROBOTS')
        logger.info(f"[ROBOT ELLENŐRZÉS] SANDBOX módban ellenőrzés, könyvtár: {os.path.abspath(dir_path)}")
        return dir_path
    dir_path = _normalize_dir_from_vars('DOWNLOADED_ROBOTS')
    logger.info(f"[ROBOT ELLENŐRZÉS] könyvtár ellenőrzés: {os.path.abspath(dir_path)}")
    return dir_path

def get_downloaded_robots_dir() -> str:
    """DownloadedRobots bázis könyvtár."""
    return _normalize_dir_from_vars('DOWNLOADED_ROBOTS')

def _on_rm_error(func, path, exc_info):
    """Read-only fájlok törlése Windows alatt: jogosultság állítása és újrapróbálás."""
    try:
        import stat
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def _delete_robot_directory(base_dir: str, repo_name: str, branch_name: str):
    """Töröl egy megadott base/<repo>/<branch> könyvtárat biztonságos ellenőrzésekkel."""
    if not base_dir:
        return False, 'Bázis könyvtár nem érhető el.'

    target = os.path.normpath(os.path.join(base_dir, repo_name, branch_name))

    # Biztonsági ellenőrzés
    try:
        base_common = os.path.commonpath([base_dir])
        target_common = os.path.commonpath([base_dir, target])
        if base_common != target_common:
            return False, f'Biztonsági okból a törlés megakadályozva: célszámított út nincs a base alatt: {target}'
    except Exception:
        if not os.path.abspath(target).startswith(os.path.abspath(base_dir)):
            return False, f'Biztonsági okból a törlés megakadályozva (prefix ellenőrzés): {target}'

    if not os.path.exists(target):
        return False, f'Könyvtár nem létezik: {target}'

    try:
        shutil.rmtree(target, onerror=_on_rm_error)
        return True, f'Törölve: {target}'
    except Exception as e:
        return False, f'Törlés sikertelen: {target} - {e}'


def delete_downloaded_robot_directory(repo_name: str, branch_name: str):
    """Törli a letöltött robot könyvtárát: DownloadedRobots/<repo>/<branch>."""
    return _delete_robot_directory(get_downloaded_robots_dir(), repo_name, branch_name)

def get_downloaded_keys():
    """KORÁBBI MŰKÖDÉS (results alapján) – megtartva kompatibilitás miatt, de nem használjuk a listázáshoz."""
    keys = set()
    base_dir = 'results'
    try:
        if os.path.isdir(base_dir):
            for name in os.listdir(base_dir):
                if '__' in name:
                    parts = name.split('__')
                    if len(parts) >= 2:
                        safe_repo = parts[0]
                        safe_branch = parts[1]
                        keys.add(f"{safe_repo}|{safe_branch}")
    except Exception as e:
        logger.info(f"[INFO] Nem sikerült a results alapú kulcsokat felderíteni: {e}")
    return keys

def get_installed_keys():
    """Felderíti a DownloadedRobots vagy SandboxRobots mappában az elérhető (futtatható) REPO/BRANCH párokat.

    Struktúra: <base>/<repo>/<branch>/, ahol base = DownloadedRobots vagy SandboxRobots
    Visszaad: set(["<repo>|<branch>", ...])
    """
    keys = set()
    base_dir = get_installed_robots_dir()
    logger.info(f"[ROBOT ELLENŐRZÉS] Futtatható robotok keresése ebben a könyvtárban: {os.path.abspath(base_dir)}")
    try:
        if base_dir and os.path.isdir(base_dir):
            for repo_name in os.listdir(base_dir):
                repo_path = os.path.join(base_dir, repo_name)
                if not os.path.isdir(repo_path):
                    continue
                for branch_name in os.listdir(repo_path):
                    branch_path = os.path.join(repo_path, branch_name)
                    if not os.path.isdir(branch_path):
                        continue
                    # Csak akkor tekintjük futtathatónak, ha van .venv mappa (ready to run)
                    venv_folder = os.path.join(branch_path, '.venv')
                    if os.path.isdir(venv_folder):
                        keys.add(f"{repo_name}|{branch_name}")
    except Exception as e:
        logger.info(f"[INFO] Nem sikerült a futtatható kulcsokat felderíteni: {e}")
    return keys
def get_branches_for_repo(repo_name):
    """Lekéri egy repository branch-eit a git ls-remote segítségével."""
    try:
        # Ha sandbox módban vagyunk, mock branch lista
        if get_sandbox_mode():
            logger.info(f"[BRANCH-QUERY][MOCK] Sandbox mód aktív, mock branch lista visszaadva.")
            return ['main', 'teszt-branch', 'CLA-ssistant', 'IKK01_Duplikáció-ellenőrzés', 'IKK04-Dokumentum-WEB-Ellenőrzés', 'KB01-Közbeszerzési-Értesítő', 'Szó-kikérdező', 'CPS-Mezo-ellenor', 'ORIANA-Mezo-ellenor', 'IKK02_Formai-Ellenorzesek', 'IKK03_Web-ellenőrzés']
        url = f'https://github.com/lovaszotto/{repo_name}'
        logger.info(f"[BRANCH-QUERY] git ls-remote URL: {url}")
        result = subprocess.run(
            ['git', 'ls-remote', '--heads', url],
            capture_output=True, text=True, encoding='utf-8', timeout=30
        )
        logger.info(f"[BRANCH-QUERY] returncode={result.returncode}")
        logger.info(f"[BRANCH-QUERY] stdout: {result.stdout}")
        logger.info(f"[BRANCH-QUERY] stderr: {result.stderr}")
        if result.returncode == 0:
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        branch_name = parts[1].replace('refs/heads/', '')
                        # Kizárjuk a main és master branch-eket
                        if branch_name not in ['main', 'master']:
                            branches.append(branch_name)
            return branches
        else:
            logger.error(f"[BRANCH-QUERY] git ls-remote returncode={result.returncode}, stderr={result.stderr}")
            return []
    except Exception as e:
        logger.error(f"Hiba a branch-ek lekérésében: {e}")
        return []

def get_repository_data():
    """Lekéri a repository adatokat lokálisan tárolt JSON fájlból vagy üres listát ad vissza.

    Eredetileg ez a függvény egy külső szkriptet hívhatott, de itt tartósan egyszerűsítjük:
    ha létezik a 'repos_response.json', beolvassuk, egyébként üres listát adunk.
    """
    try:
        if os.path.exists('repos_response.json'):
            with open('repos_response.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Kivétel a repository adatok lekérésében: {e}")
        return []


def run_robot_with_params(repo: str, branch: str):
    """Indítja el a Robot Framework futtatást a megadott repo/branch paraméterekkel.

    Visszatér: (returncode, results_dir_rel, stdout, stderr)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_repo = (repo or 'unknown').replace('/', '_')
    safe_branch = (branch or 'unknown').replace('/', '_')
    results_dir_rel = f'{safe_repo}__{safe_branch}__{timestamp}'
    results_dir_abs = os.path.abspath(os.path.join('results', results_dir_rel))
    os.makedirs(results_dir_abs, exist_ok=True)

    suite_path = os.path.abspath('do-selected.robot')
    # Ellenőrzések futtatás előtt
    if not os.path.isfile(PYTHON_EXECUTABLE):
        msg = f"Python végrehajtható nem található: {PYTHON_EXECUTABLE}"
        _persist_robot_outputs(results_dir_abs, '', msg, note=msg)
        logger.error(f"[RUN][ERROR] {msg}")
        return 1, results_dir_rel, '', msg
    # Ellenőrizzük, hogy a robot modul elérhető-e
    try:
        import importlib.util
        if importlib.util.find_spec('robot.run') is None:
            msg = "A 'robot' modul nem található a Python környezetben."
            _persist_robot_outputs(results_dir_abs, '', msg, note=msg)
            logger.error(f"[RUN][ERROR] {msg}")
            return 1, results_dir_rel, '', msg
    except Exception as e:
        msg = f"A 'robot' modul ellenőrzése hibát dobott: {e}"
        _persist_robot_outputs(results_dir_abs, '', msg, note=msg)
        logger.error(f"[RUN][ERROR] {msg}")
        return 1, results_dir_rel, '', msg
    if not os.path.isfile(suite_path):
        msg = f"A teszt suite fájl nem található: {suite_path}"
        _persist_robot_outputs(results_dir_abs, '', msg, note=msg)
        logger.error(f"[RUN][ERROR] {msg}")
        return 1, results_dir_rel, '', msg

    # Egyszerűsítés: közvetlenül a robot.run modult hívjuk (__main__ hiány miatti problémák elkerülésére)
    cmd = [
        PYTHON_EXECUTABLE, '-m', 'robot.run',
        '-d', results_dir_abs,
        '--log', 'log.html',
        '--report', 'report.html',
        '-v', f'REPO:{repo}',
        '-v', f'BRANCH:{branch}',
        suite_path
    ]
    try:
        logger.info(f"[RUN] Python exec: {PYTHON_EXECUTABLE}")
        logger.info(f"[RUN] CWD: {os.getcwd()}")
        logger.info(f"[RUN] Results dir (abs): {results_dir_abs}")
        logger.info(f"[RUN] Command: {' '.join(cmd)}")
    except Exception:
        pass
    try:
        # Windows hibadoboz elkerülése: CREATE_NO_WINDOW flag
        creationflags = 0x08000000 if os.name == 'nt' else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=False,
            creationflags=creationflags
        )
        _persist_robot_outputs(
            results_dir_abs,
            result.stdout or '',
            result.stderr or '',
            note=f"Robot Framework rc={result.returncode}"
        )
        try:
            generated = []
            if os.path.isdir(results_dir_abs):
                generated = sorted(os.listdir(results_dir_abs))
            logger.info(f"[RUN] Return code: {result.returncode}")
            logger.info(f"[RUN] Generated files in results dir: {generated}")
            logger.info(f"[RUN] Robot visszatérés: returncode={result.returncode}, results_dir_rel={results_dir_rel}")
            logger.info(f"[RUN] Robot stdout: {result.stdout[:500] if result.stdout else ''}")
            logger.info(f"[RUN] Robot stderr: {result.stderr[:500] if result.stderr else ''}")
        except Exception as e:
            logger.error(f"[RUN] Post-run inspection failed: {e}")
        return result.returncode, results_dir_rel, result.stdout, result.stderr
    except FileNotFoundError as e:
        _persist_robot_outputs(results_dir_abs, '', f'FileNotFoundError: {e}', note='Robot Framework nem indult (python modul hiányzik)')
        logger.error(f"[RUN][ERROR] FileNotFoundError: {e}")
        logger.info(f"[RUN] Robot visszatérés: returncode=1, results_dir_rel={results_dir_rel}")
        logger.info(f"[RUN] Robot stdout: '')")
        logger.info(f"[RUN] Robot stderr: FileNotFoundError: {e}")
        return 1, results_dir_rel, '', f'FileNotFoundError: {e}'
    except Exception as e:
        # Windows hibadoboz elkerülése: hiba naplózása, de nem dobunk tovább hibát
        _persist_robot_outputs(results_dir_abs, '', str(e), note='Robot Framework futtatása kivétellel leállt')
        logger.error(f"[RUN][ERROR] {e}")
        logger.info(f"[RUN] Robot visszatérés: returncode=1, results_dir_rel={results_dir_rel}")
        logger.info(f"[RUN] Robot stdout: '')")
        logger.info(f"[RUN] Robot stderr: {str(e)}")
        return 1, results_dir_rel, '', str(e)


def _persist_robot_outputs(results_dir_abs: str, stdout_text: str, stderr_text: str, note: str = ''):
    """Gondoskodik a stdout/stderr mentéséről és fallback log.html előállításáról, ha a Robot nem készített naplót."""
    os.makedirs(results_dir_abs, exist_ok=True)
    stdout_path = os.path.join(results_dir_abs, 'stdout.txt')
    stderr_path = os.path.join(results_dir_abs, 'stderr.txt')
    stdout_text = stdout_text or ''
    stderr_text = stderr_text or ''

    with open(stdout_path, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(stdout_text)
    with open(stderr_path, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(stderr_text)

    log_path = os.path.join(results_dir_abs, 'log.html')
    if not os.path.exists(log_path):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        note_text = note or 'Robot Framework log nem készült, automatikusan generált fallback tartalom.'


@app.route('/')
def index():
    """Főoldal"""
    # Repository adatok lekérése
    repos = get_repository_data()
    root_folder = get_robot_variable('ROOT_FOLDER')

    # Dátum formázása (pushed_at -> YYYY-MM-DD HH:MM) és branch adatok hozzáadása minden repository-hoz
    for repo in repos:
        try:
            pushed_at = (repo.get('pushed_at') or '').strip()
            if pushed_at:
                dt = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
                repo['pushed_at_formatted'] = dt.strftime('%Y-%m-%d %H:%M')
            else:
                repo['pushed_at_formatted'] = ''
        except Exception:
            repo['pushed_at_formatted'] = (repo.get('pushed_at') or '')

        repo['branches'] = get_branches_for_repo(repo['name'])
        # DEBUG/FALLBACK: ha nincs branch, adjunk hozzá egy teszt branch-et, hogy a UI ne legyen üres
        if not repo['branches']:
            repo['branches'] = ['main', 'teszt-branch']

    # Előre kiszámoljuk a futtatható (telepített) és letölthető branch-eket repo szinten
    installed_keys = get_installed_keys()
    for repo in repos:
        safe_repo = repo['name'].replace('/', '_')
        # Megjegyzés: az InstalledRobots-ban a mappanevek a tényleges repo/branch neveket tartalmazzák
        repo['downloaded_branches'] = [
            branch for branch in repo['branches']
            if f"{repo['name']}|{branch}" in installed_keys
        ]
        repo['available_branches'] = [
            branch for branch in repo['branches']
            if f"{repo['name']}|{branch}" not in installed_keys
        ]
    version = get_robot_variable('VERSION')
    build_date = get_robot_variable('BUILD_DATE')
    # page_title logika ugyanaz, mint a get_html_template-ben
    is_sandbox = get_sandbox_mode()
    page_title = "Fejlesztői mód" if is_sandbox else "Segíthetünk?"
    # Színséma lekérése
    color_scheme = get_html_template(is_sandbox, page_title)
    response = app.response_class(
        render_template(
            "main.html",
            repos=repos,
            datetime=datetime,
            downloaded_keys=installed_keys,
            root_folder=root_folder or '',
            version=version,
            build_date=build_date,
            page_title=page_title,
            **color_scheme
        ),
        mimetype='text/html'
    )
    # Cache törlése fejlécekkel
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/refresh')
def refresh_data():
    """API endpoint az adatok frissítéséhez"""
    # Mindig friss adatokat olvasunk, semmilyen cache-t nem használunk
    repos = get_repository_data()  # Ez mindig újraolvassa a repo metaadatokat
    installed_keys = get_installed_keys()
    logger.info(f"[API/REFRESH] installed_keys: {installed_keys}")
    for repo in repos:
        repo['branches'] = get_branches_for_repo(repo['name'])  # Mindig újraolvassa a branch-eket
        logger.info(f"[API/REFRESH] repo: {repo['name']}, branches: {repo['branches']}")
        repo['downloaded_branches'] = [
            branch for branch in repo['branches']
            if f"{repo['name']}|{branch}" in installed_keys
        ]
        repo['available_branches'] = [
            branch for branch in repo['branches']
            if f"{repo['name']}|{branch}" not in installed_keys
        ]
        logger.info(f"[API/REFRESH] repo: {repo['name']}, available_branches: {repo['available_branches']}")
    return jsonify(repos)

@app.route('/api/execute', methods=['POST'])
def api_execute():
    """Egyetlen kiválasztott robot végrehajtásának kérése."""
    logger.info("[EXECUTE] api_execute() hívás indult")
    printed = []
    try:
        raw_body = request.get_data()  # nyers POST törzs
        ct = request.content_type
        logger.info(f"[EXECUTE][RAW_BODY_LEN]={len(raw_body)}")
        # Nyers törzs első 300 byte-ja debughoz
        preview = raw_body[:300]
        logger.info(f"[EXECUTE][RAW_BODY_PREVIEW]={preview}")
        logger.info(f"[EXECUTE][CONTENT_TYPE]={ct}")
        # Próbáljuk JSON-ként értelmezni több módszerrel
        data = request.get_json(silent=True)
        if data is None:
            try:
                import json as _json
                data = _json.loads(raw_body.decode('utf-8-sig'))
                logger.info("[EXECUTE] json.loads utf-8-sig sikeres")
            except Exception as e:
                logger.warning(f"[EXECUTE] json parse hiba: {e}")
                data = {}
        repo = (data.get('repo') or request.values.get('repo') or '').strip()
        branch = (data.get('branch') or request.values.get('branch') or '').strip()
        logger.info(f"[EXECUTE] Futtatás kérés repo='{repo}' branch='{branch}' len_repo={len(repo)} len_branch={len(branch)} data_keys={list(data.keys())}")
        # Tényleges futtatás indítása Robot Framework-kel
        if not repo or not branch:
            logger.warning(f"[EXECUTE] HIBA: Hiányzó paraméterek - data={data}")
            return jsonify({"status": "error", "message": "Hiányzó repo vagy branch"}), 400
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"[EXECUTE] Robot futtatás indítása: {repo}/{branch}")
        logger.info(f"[EXECUTE] run_robot_with_params hívás előtt: repo={repo}, branch={branch}")
        rc, out_dir, _stdout, _stderr = run_robot_with_params(repo, branch)
        logger.info(f"[EXECUTE] run_robot_with_params visszatért: rc={rc}, out_dir={out_dir}")
        status = "success" if rc == 0 else "failed"
        logger.info(f"[EXECUTE] Robot futtatás befejezve: rc={rc}, status={status}, dir={out_dir}")

        # Eredmény tárolása
        global execution_results
        result_entry = {
            'id': len(execution_results) + 1,
            'timestamp': timestamp,
            'repo': repo,
            'branch': branch,
            'status': status,
            'returncode': rc,
            'results_dir': out_dir,
            'type': 'bulk'
        }
        execution_results.append(result_entry)

        printed.append({
            'repo': repo,
            'branch': branch,
            'returncode': rc,
            'results_dir': out_dir,
            'status': "ok" if rc == 0 else "fail"
        })
        save_execution_results()
    except Exception as e:
        logger.error(f"[EXECUTE] Hiba a futtatás során: {e}")
        printed.append({
            'repo': repo if 'repo' in locals() else None,
            'branch': branch if 'branch' in locals() else None,
            'status': "error",
            'message': str(e)
        })
    return jsonify(printed)
@app.route('/api/start_robot', methods=['POST'])
def api_start_robot():
    """Indítja a kiválasztott robotot a start.bat futtatásával a megfelelő könyvtárban.

    Várható bemenet (JSON): { "repo": "<repo>", "branch": "<branch>" }
    Válasz: { "success": true/false, ... }
    """
    try:
        data = request.get_json(silent=True) or {}
        repo = (data.get('repo') or '').strip()
        branch = (data.get('branch') or '').strip()
        debug_mode = bool(data.get('debug', False))

        print(f"[START_ROBOT] Kérés érkezett (start.bat futtatás letiltva): repo={repo}, branch={branch}, debug_mode={debug_mode}")

        if not repo or not branch:
            print("[START_ROBOT] HIBA: Hiányzó repo vagy branch paraméter")
            return jsonify({
                'success': False,
                'error': 'Hiányzó repo vagy branch'
            }), 400

        base_dir = get_installed_robots_dir()
        logger.info(f"[ROBOT ELLENŐRZÉS] Robot indítás ellenőrzés, könyvtár: {base_dir}, repo: {repo}, branch: {branch}")
        if not base_dir:
            base_dir = _normalize_dir_from_vars('DOWNLOADED_ROBOTS') or os.path.join(os.getcwd(), 'DownloadedRobots')
            logger.info(f"[ROBOT ELLENŐRZÉS] Fallback könyvtár: {base_dir}")

        safe_repo = repo.replace('/', '_')
        safe_branch = branch.replace('/', '_')
        target_dir = os.path.join(base_dir, safe_repo, safe_branch)
        start_bat = os.path.join(target_dir, 'start.bat')
        logger.info(f"[ROBOT ELLENŐRZÉS] Indítás target_dir: {target_dir}, start_bat: {start_bat}")

        if not os.path.isdir(target_dir):
            print(f"[START_ROBOT] HIBA: Könyvtár nem található: {target_dir}")
            return jsonify({
                'success': False,
                'error': f'Könyvtár nem található: {target_dir}'
            }), 404
        if not os.path.exists(start_bat):
            print(f"[START_ROBOT] HIBA: start.bat nem található: {start_bat}")
            return jsonify({
                'success': False,
                'error': f'start.bat nem található: {start_bat}'
            }), 404

        try:
            # start.bat futtatása subprocess-szel
            result = subprocess.run([start_bat], cwd=target_dir, capture_output=True, text=True, shell=True)
            print(f"[START_ROBOT] start.bat futtatva: rc={result.returncode}")
            return jsonify({
                'success': result.returncode == 0,
                'repo': repo,
                'branch': branch,
                'dir': target_dir,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            })
        except Exception as exc:
            print(f"[START_ROBOT] HIBA futtatás közben: {exc}")
            return jsonify({
                'success': False,
                'error': 'start.bat futtatása közben hiba történt',
                'details': str(exc)
            }), 500
    except Exception as exc:
        print(f"[START_ROBOT] HIBA: {exc}")
        return jsonify({
            'success': False,
            'error': 'start.bat futtatása letiltva, további hiba történt',
            'details': str(exc)
        }), 500

@app.route('/favicon.ico')
def favicon():
    """Favicon kezelése"""
    return '', 204

# Szerver leállítása (Werkzeug)
@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Leállítja a Flask szervert a Kilépés gomb kérésére."""
    func = request.environ.get('werkzeug.server.shutdown')

    def _delayed_shutdown(target_func):
        time.sleep(0.5)
        if target_func is not None:
            try:
                target_func()
                return
            except Exception as exc:
                print(f"[SHUTDOWN] Werkzeug leállítás sikertelen: {exc}")
        print('[SHUTDOWN] Fallback os._exit(0) hívás')
        os._exit(0)

    threading.Thread(target=_delayed_shutdown, args=(func,), daemon=True).start()
    return jsonify({"status": "shutting down"})

@app.route('/api/restart', methods=['POST'])
def api_restart():
    """Újraindítási kérés kezelése start.bat indítása nélkül."""
    print('[RESTART] start.bat indítása letiltva, restart API nem futtat parancsot.')
    return jsonify({
        'success': False,
        'error': 'start.bat indítása letiltva, kérjük manuálisan indítsd újra az alkalmazást'
    }), 403

# Globális eredmények tárolás
RESULTS_FILE = 'execution_results.json'

def load_execution_results():
    """Betölti az execution_results-okat fájlból."""
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                results = json.load(f)
                print(f"[INFO] {len(results)} korábbi futási eredmény betöltve")
                return results
    except Exception as e:
        print(f"[WARNING] Hiba az eredmények betöltésénél: {e}")
    return []

def save_execution_results():
    """Elmenti az execution_results-okat fájlba."""
    try:
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(execution_results, f, ensure_ascii=False, indent=2)
        print(f"[INFO] {len(execution_results)} futási eredmény elmentve")
    except Exception as e:
        print(f"[WARNING] Hiba az eredmények mentésénél: {e}")

# Eredmények betöltése alkalmazás indításkor
execution_results = load_execution_results()

@app.route('/api/clear-results', methods=['POST'])
def clear_results():
    """Törli az összes tárolt futási eredményt"""
    global execution_results
    execution_results = []
    save_execution_results()  # Üres lista mentése
    return jsonify({"status": "success", "message": "Eredmények törölve"})

@app.route('/delete_runnable_branch', methods=['POST'])
def delete_runnable_branch():
    """Törli a megadott branch-et a futtathatók közül"""
    try:
        data = request.get_json()
        repo_name = data.get('repo')
        branch_name = data.get('branch')
        
        if not repo_name or not branch_name:
            return jsonify({'success': False, 'error': 'Repository és branch név szükséges'})
        
    
        # Letöltött robot könyvtár törlése a DownloadedRobots alól
        deleted_downloaded, info_down = delete_downloaded_robot_directory(repo_name, branch_name)
        status_down = 'törölve' if deleted_downloaded else 'nem található, nincs mit törölni'
        print(f"[DELETE] DownloadedRobots: {repo_name}/{branch_name}: {status_down}. {info_down}")
        
        return jsonify({
            'success': True,
            'message': f'Branch {repo_name}/{branch_name} eltávolítva',
            'deleted': deleted_downloaded,  # csak DownloadedRobots számít
            'deleted_downloaded': deleted_downloaded
        })
        
    except Exception as e:
        print(f"Hiba a branch törlésében: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/debug/results')
def debug_results():
    """Debug endpoint az eredmények állapotának ellenőrzésére"""
    return jsonify({
        "current_dir": os.getcwd(),
        "results_file_path": os.path.abspath(RESULTS_FILE),
        "results_file_exists": os.path.exists(RESULTS_FILE),
        "execution_results_count": len(execution_results),
        "execution_results_sample": execution_results[:3] if execution_results else [],
        "python_executable": PYTHON_EXECUTABLE
    })

@app.route('/api/debug/installed')
def debug_installed():
    """Debug endpoint: mutatja a 'futtatható' robotok forrását és kulcsait."""
    # Mindig friss könyvtár- és branch-információkat adunk vissza
    base_inst = get_installed_robots_dir()
    keys = sorted(list(get_installed_keys()))  # Ez mindig újraolvassa a könyvtárakat
    return jsonify({
        'sandbox_mode': get_sandbox_mode(),
        'installed_base_dir': base_inst,
        'installed_count': len(keys),
        'installed_keys': keys[:100]  # levágjuk, ha sok lenne
    })

@app.route('/api/results', methods=['GET'])
def get_results():
    """Visszaadja a futási eredményeket lapozással és szűrésekkel"""
    try:
        # URL paraméterek
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        search = request.args.get('search', '')
        status_filter = request.args.get('status', '')
        date_filter = request.args.get('date', '')
        sort_by = request.args.get('sort', 'timestamp')
        sort_order = request.args.get('order', 'desc')
        
        # Eredmények szűrése
        filtered_results = execution_results.copy()
        
        if search:
            filtered_results = [r for r in filtered_results 
                              if search.lower() in r['repo'].lower() or 
                                 search.lower() in r['branch'].lower()]
        
        if status_filter:
            filtered_results = [r for r in filtered_results 
                              if r['status'] == status_filter]
        
        if date_filter:
            filtered_results = [r for r in filtered_results 
                              if r['timestamp'].startswith(date_filter)]
        
        # Rendezés
        reverse = sort_order == 'desc'
        if sort_by == 'timestamp':
            filtered_results.sort(key=lambda x: x['timestamp'], reverse=reverse)
        elif sort_by == 'repo':
            filtered_results.sort(key=lambda x: x['repo'], reverse=reverse)
        elif sort_by == 'branch':
            filtered_results.sort(key=lambda x: x['branch'], reverse=reverse)
        elif sort_by == 'status':
            filtered_results.sort(key=lambda x: x['status'], reverse=reverse)
        
        # Lapozás
        total = len(filtered_results)
        start = (page - 1) * per_page
        end = start + per_page
        results_page = filtered_results[start:end]
        
        return jsonify({
            'results': results_page,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/set_sandbox_mode', methods=['POST'])
def set_sandbox_mode():
    """Beállítja a SANDBOX_MODE értékét az aktuális session-re és szinkronizálja a variables.robot fájlt.

    - Session-ben: csak a jelenlegi böngésző session-re érvényes.
    - Fájlban: a resources/variables.robot ${SANDBOX_MODE} sorát ${True}/${False} értékre állítjuk.
    """
    try:
        data = request.get_json() or {}
        enabled = bool(data.get('enabled', False))

        # Session frissítése
        session['sandbox_mode'] = enabled

        # Fájl szinkronizálása
        variables_file = os.path.join('resources', 'variables.robot')
        if not os.path.exists(variables_file):
            return jsonify({'success': False, 'error': 'Variables.robot fájl nem található'}), 404

        with open(variables_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        import re
        new_value = '${True}' if enabled else '${False}'
        modified = False
        for i, line in enumerate(lines):
            if line.strip().startswith('${SANDBOX_MODE}'):
                # Cseréljük le az értéket, az eredeti formázást megtartva, de a példában fix 9 szóköz van
                lines[i] = re.sub(r'\$\{SANDBOX_MODE\}\s+.*$', f'${{SANDBOX_MODE}}         {new_value}', line)
                modified = True
                break

        if not modified:
            return jsonify({'success': False, 'error': 'SANDBOX_MODE változó nem található a variables.robot fájlban'}), 404

        with open(variables_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        # Nem indítjuk újra a szervert itt; a kliens oldali UI teljes oldalt frissít
        return jsonify({'success': True, 'enabled': enabled})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get_sandbox_mode', methods=['GET'])
def get_sandbox_mode_api():
    """Visszaadja a jelenlegi SANDBOX_MODE értékét"""
    try:
        enabled = get_sandbox_mode()
        return jsonify({'enabled': enabled})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/fetch-log')
def fetch_log():
    """Visszaadja a results/<safe_dir>/log.html tartalmát JSON-ben.

    Biztonsági okokból csak a 'results' könyvtáron belüli fájlok olvashatók.
    Paraméter: dir - a results könyvtárhoz képesti almappa (pl. 'repo__branch__timestamp')
    Válasz: { 'html': "..." } vagy { 'error': '...' }
    """
    dir_param = (request.args.get('dir') or '').strip()
    if not dir_param:
        return jsonify({'error': 'Hiányzó dir paraméter'}), 400

    base = os.path.abspath('results')

    # Normalize dir_param to avoid creating paths like results/results... when the param
    # already contains 'results' or is an absolute path.
    if os.path.isabs(dir_param):
        requested = os.path.abspath(dir_param)
    else:
        # If dir_param starts with 'results/' or 'results\\', strip that prefix
        if dir_param.startswith('results' + os.sep) or dir_param.startswith('results' + '/'):
            dir_rel = dir_param.split(os.sep, 1)[-1] if os.sep in dir_param else dir_param.split('/', 1)[-1]
        else:
            dir_rel = dir_param

        requested = os.path.abspath(os.path.join(base, dir_rel))

    try:
        # Ellenőrizzük, hogy requested a base alkönyvtára-e
        if os.path.commonpath([base, requested]) != base:
            return jsonify({'error': 'Érvénytelen útvonal', 'dir': dir_param, 'requested': requested}), 400
    except Exception:
        return jsonify({'error': 'Érvénytelen útvonal', 'dir': dir_param, 'requested': requested}), 400

    log_file = os.path.join(requested, 'log.html')
    if not os.path.exists(log_file):
        return jsonify({'error': f"log.html nem található a megadott mappában", 'dir': dir_param, 'log_file': log_file}), 404
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            html = f.read()
        return jsonify({'html': html})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/results/<path:subpath>')
def serve_results(subpath):
    """Serve files from the results directory securely.

    If a directory is requested, try to serve its log.html. Otherwise, serve the specific file.
    """
    base = os.path.abspath('results')
    requested = os.path.abspath(os.path.join(base, subpath))

    try:
        if os.path.commonpath([base, requested]) != base:
            return jsonify({'error': 'Érvénytelen útvonal'}), 400
    except Exception:
        return jsonify({'error': 'Érvénytelen útvonal'}), 400

    # If requested is a directory, serve log.html if present
    if os.path.isdir(requested):
        log_file = os.path.join(requested, 'log.html')
        if os.path.exists(log_file):
            return send_from_directory(requested, 'log.html')
        return jsonify({'error': f'log.html nem található: {log_file}'}), 404

    # Otherwise, serve the requested file if it exists
    if os.path.exists(requested):
        dir_name = os.path.dirname(requested)
        file_name = os.path.basename(requested)
        return send_from_directory(dir_name, file_name)

    return jsonify({'error': f'Fájl nem található: {requested}'}), 404

def get_html_template(is_sandbox, page_title):
    if is_sandbox:
        # Fejlesztői mód: piros színvilág
        return {
            "primary_color": "#dc3545",
            "secondary_color": "#e74c3c",
            "tertiary_color": "#f1aeb5",
            "dark_color": "#c82333",
            "light_color": "#f8d7da",
            "hover_color": "#b02a37",
            "rgba_color": "220, 53, 69",
        }
    else:
        # Normál mód: kék színvilág
        return {
            "primary_color": "#0d6efd",
            "secondary_color": "#3b82f6",
            "tertiary_color": "#93c5fd",
            "dark_color": "#0056b3",
            "light_color": "#e7f3ff",
            "hover_color": "#004085",
            "rgba_color": "13, 110, 253",
        }

if __name__ == "__main__":
    # Indítsd a Flask szervert, hogy kívülről is elérhető legyen, ne csak localhostról
    app.run(host="0.0.0.0", port=5000, debug=False)
