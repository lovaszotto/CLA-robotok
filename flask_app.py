from flask import Flask, render_template_string, jsonify, request, send_from_directory, session
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


app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'cla-ssistant-secret')


PYTHON_EXECUTABLE = sys.executable or 'python'


# Logging beállítás: minden log menjen a server.log fájlba is, konzolra is
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('server.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_sandbox_mode() -> bool:
    """Határozza meg, hogy a felület sandbox módban fusson-e."""
    # 1) Session alapú érték, ha a felhasználó már választott üzemmódot.
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
    path = os.path.expandvars(os.path.expanduser(path))
    return os.path.normpath(path)

def get_installed_robots_dir() -> str:
    """Mindig a DownloadedRobots vagy SandboxRobots könyvtárat adja vissza, InstalledRobots megszűnt."""
    if get_sandbox_mode():
        return _normalize_dir_from_vars('SANDBOX_ROBOTS')
    return _normalize_dir_from_vars('DOWNLOADED_ROBOTS')

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
        result = subprocess.run(
            ['git', 'ls-remote', '--heads', f'https://github.com/lovaszotto/{repo_name}'],
            capture_output=True, text=True, encoding='utf-8', timeout=30
        )
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
    try:
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
            fallback_html = f"""<!DOCTYPE html>
<html lang=\"hu\">
<head>
    <meta charset=\"utf-8\">
    <title>Robot Framework fallback log</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0b1224; color: #f0f4ff; margin: 0; padding: 24px; }}
        pre {{ background: #101a33; padding: 16px; border-radius: 8px; overflow: auto; border: 1px solid #1f2b4c; }}
        h1, h2 {{ color: #7dd3fc; }}
        .meta {{ margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>Robot Framework fallback log</h1>
    <div class=\"meta\">
        <p><strong>Időbélyeg:</strong> {timestamp}</p>
        <p><strong>Megjegyzés:</strong> {html.escape(note_text)}</p>
    </div>
    <h2>STDOUT</h2>
    <pre>{html.escape(stdout_text) or '(nincs stdout kimenet)'}</pre>
    <h2>STDERR</h2>
    <pre>{html.escape(stderr_text) or '(nincs stderr kimenet)'}</pre>
</body>
</html>"""
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(fallback_html)
            logger.info(f"[RUN] Fallback log létrehozva: {log_path}")
    except Exception as e:
        logger.error(f"[RUN] Nem sikerült a fallback log mentése: {e}")

def install_robot_with_params(repo: str, branch: str):
    """Letölti és telepíti a robotot a megadott repo/branch alapján, de nem futtatja.
    Visszatér: (returncode, results_dir_rel, stdout, stderr)
    """
    import json
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_repo = (repo or 'unknown').replace('/', '_')
    safe_branch = (branch or 'unknown').replace('/', '_')
    logger.info(f"[INSTALL] install_robot_with_params indult: repo='{repo}', branch='{branch}', safe_repo='{safe_repo}', safe_branch='{safe_branch}', timestamp='{timestamp}'")
    # 1. Könyvtárak létrehozása (repo és branch szint)
    if get_sandbox_mode():
        base_dir = _normalize_dir_from_vars('SANDBOX_ROBOTS')
        if not base_dir:
            base_dir = os.path.join(os.getcwd(), 'SandboxRobots')
        logger.info(f"[INSTALL] SANDBOX_MODE aktív, base_dir: {base_dir}")
    else:
        base_dir = _normalize_dir_from_vars('DOWNLOADED_ROBOTS')
        if not base_dir:
            base_dir = os.path.join(os.getcwd(), 'DownloadedRobots')
        logger.info(f"[INSTALL] NEM sandbox mód, base_dir: {base_dir}")
    repo_dir = os.path.join(base_dir, safe_repo)
    branch_dir = os.path.join(repo_dir, safe_branch)
    logger.info(f"[INSTALL] repo_dir: {repo_dir}, branch_dir: {branch_dir}")
    os.makedirs(repo_dir, exist_ok=True)
    os.makedirs(branch_dir, exist_ok=True)

    # 2. Git repo URL kinyerése a repos_response.json-ból
    repo_url = None
    try:
        with open('repos_response.json', 'r', encoding='utf-8') as f:
            repos = json.load(f)
            for r in repos:
                if r.get('name', '').lower() == repo.lower():
                    repo_url = r.get('clone_url')
                    logger.info(f"[INSTALL] repo_url megtalálva: {repo_url}")
                    break
    except Exception as e:
        logger.error(f"[INSTALL][ERROR] Hiba a repos_response.json olvasásakor: {e}")
        return 1, '', '', f'Hiba a repos_response.json olvasásakor: {e}'
    if not repo_url:
        logger.error(f"[INSTALL][ERROR] Nem található repo URL: {repo}")
        return 1, '', '', f'Nem található repo URL: {repo}'

    # 3. Klónozás, ha nincs meg a branch könyvtárban .git
    try:
        git_dir = os.path.join(branch_dir, '.git')
        if not os.path.exists(git_dir):
            clone_cmd = [
                'git', 'clone', '--branch', branch, '--single-branch', repo_url, branch_dir
            ]
            logger.info(f"[INSTALL] Klónozás indítása: {' '.join(clone_cmd)}")
            result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=120)
            logger.info(f"[INSTALL] Klónozás befejezve: rc={result.returncode}, stdout={result.stdout[:300]}, stderr={result.stderr[:300]}")
            if result.returncode != 0:
                logger.error(f"[INSTALL][ERROR] Klónozás sikertelen: rc={result.returncode}, stdout={result.stdout[:300]}, stderr={result.stderr[:300]}")
                return 1, '', result.stdout, result.stderr
        else:
            # Force pull: fetch + reset --hard
            fetch_cmd = ['git', '-C', branch_dir, 'fetch', 'origin']
            logger.info(f"[INSTALL] Fetch indítása: {' '.join(fetch_cmd)}")
            fetch_result = subprocess.run(fetch_cmd, capture_output=True, text=True, timeout=60)
            logger.info(f"[INSTALL] Fetch befejezve: rc={fetch_result.returncode}, stdout={fetch_result.stdout[:300]}, stderr={fetch_result.stderr[:300]}")
            if fetch_result.returncode != 0:
                logger.error(f"[INSTALL][ERROR] Fetch sikertelen: rc={fetch_result.returncode}, stdout={fetch_result.stdout[:300]}, stderr={fetch_result.stderr[:300]}")
                return 1, '', fetch_result.stdout, fetch_result.stderr
            reset_cmd = ['git', '-C', branch_dir, 'reset', '--hard', f'origin/{branch}']
            logger.info(f"[INSTALL] Reset --hard indítása: {' '.join(reset_cmd)}")
            reset_result = subprocess.run(reset_cmd, capture_output=True, text=True, timeout=60)
            logger.info(f"[INSTALL] Reset --hard befejezve: rc={reset_result.returncode}, stdout={reset_result.stdout[:300]}, stderr={reset_result.stderr[:300]}")
            if reset_result.returncode != 0:
                logger.error(f"[INSTALL][ERROR] Reset --hard sikertelen: rc={reset_result.returncode}, stdout={reset_result.stdout[:300]}, stderr={reset_result.stderr[:300]}")
                return 1, '', reset_result.stdout, reset_result.stderr
    except Exception as e:
        logger.error(f"[INSTALL][ERROR] Git klónozás/pull hiba: {e}")
        return 1, '', '', f'Git klónozás/pull hiba: {e}'

    if get_sandbox_mode():
        logger.info(f"[INSTALL] SANDBOX_MODE: csak klónozás történt, nincs telepito.bat, nincs .venv ellenőrzés")
        return 0, branch_dir, 'Sandbox clone OK', ''
    # 4. telepito.bat futtatása CSAK ha nincs .venv mappa a letöltött branch könyvtárban
    installed_dir = get_installed_robots_dir()
    venv_dir = os.path.join(installed_dir, safe_repo, safe_branch, '.venv')
    logger.info(f"[INSTALL] venv_dir ellenőrzés: {venv_dir}")
    if not os.path.isdir(venv_dir):
        telepito_path = os.path.join(branch_dir, 'telepito.bat')
        logger.info(f"[INSTALL] telepito.bat path: {telepito_path}")
        if not os.path.exists(telepito_path):
            logger.error(f"[INSTALL][ERROR] telepito.bat nem található: {telepito_path}")
            return 1, '', '', f'telepito.bat nem található: {telepito_path}'
        try:
            logger.info(f"[INSTALL] telepito.bat futtatása indítás: cwd={branch_dir}")
            result = subprocess.run(['telepito.bat'], cwd=branch_dir, capture_output=True, text=True, timeout=300, shell=True)
            logger.info(f"[INSTALL] telepito.bat futtatás befejezve: rc={result.returncode}, stdout={result.stdout[:300]}, stderr={result.stderr[:300]}")
        except Exception as e:
            logger.error(f"[INSTALL][ERROR] telepito.bat futtatási hiba: {e}")
            return 1, '', '', f'telepito.bat futtatási hiba: {e}'
        # telepito.bat után újra ellenőrizzük a .venv mappát
        if not os.path.isdir(venv_dir):
            logger.error(f"[INSTALL][ERROR] .venv mappa nem található a telepítés után: {venv_dir}")
            return 1, '', '', f'.venv mappa nem található a telepítés után: {venv_dir}'
        logger.info(f"[INSTALL] .venv mappa sikeresen létrejött: {venv_dir}")
    else:
        logger.info(f"[INSTALL] .venv mappa már létezik: {venv_dir}")
    logger.info(f"[INSTALL] install_robot_with_params sikeresen lefutott: repo='{repo}', branch='{branch}', branch_dir='{branch_dir}'")
    return 0, branch_dir, 'Install OK', ''

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
            # Ha nem sikerül parse-olni, jelenítsük meg az eredeti értéket
            repo['pushed_at_formatted'] = (repo.get('pushed_at') or '')

        repo['branches'] = get_branches_for_repo(repo['name'])
    
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
    html_template = get_html_template()
    response = app.response_class(
        render_template_string(
            html_template,
            repos=repos,
            datetime=datetime,
            downloaded_keys=installed_keys,
            root_folder=root_folder or ''
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
    repos = get_repository_data()
    
    for repo in repos:
        repo['branches'] = get_branches_for_repo(repo['name'])
    
    return jsonify(repos)

@app.route('/api/execute', methods=['POST'])
def api_execute():
    """Egyetlen kiválasztott robot végrehajtásának kérése."""
    logger.info("[EXECUTE] api_execute() hívás indult")
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
        result_entry = {
            'id': len(execution_results) + 1,
            'timestamp': timestamp,
            'repo': repo,
            'branch': branch,
            'status': status,
            'returncode': rc,
            'results_dir': out_dir,
            'type': 'single',
            'stdout': _stdout,
            'stderr': _stderr
        }
        execution_results.append(result_entry)
        logger.info(f"[EXECUTE] Eredmény hozzáadva: ID={result_entry['id']} összes={len(execution_results)}")
        save_execution_results()
        logger.info("[EXECUTE] Eredmény elmentve fájlba")
        logger.info(f"[EXECUTE] Válasz visszaküldése a frontendnek: status={'ok' if rc == 0 else 'fail'}, rc={rc}, results_dir={out_dir}")
        return jsonify({
            "status": "ok" if rc == 0 else "fail",
            "repo": repo,
            "branch": branch,
            "returncode": rc,
            "results_dir": out_dir,
            "stdout": _stdout,
            "stderr": _stderr
        })
    except Exception as ex:
        import traceback
        logger.error(f"[EXECUTE][EXCEPTION] Kivétel történt: {ex}", exc_info=ex)
        return jsonify({"status": "error", "message": "internal error", "error": str(ex)}), 500
    
    # (Fentebb a try blokkban már visszatértünk.)

@app.route('/api/execute-bulk', methods=['POST'])
def api_execute_bulk():
    """Több kiválasztott robot végrehajtásának kérése egyszerre."""
    data = request.get_json(silent=True) or {}
    robots = data.get('robots') or []
    printed = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for r in robots:
        repo = (r.get('repo') or '').strip()
        branch = (r.get('branch') or '').strip()
        logger.info(f"EXECUTE SELECTED: {repo}/{branch}")
        if repo and branch:
            rc, out_dir, _stdout, _stderr = run_robot_with_params(repo, branch)
            status = "success" if rc == 0 else "failed"

            # Eredmény tárolása
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
        else:
            printed.append({
                'repo': repo,
                'branch': branch,
                'status': "error",
                'message': "Hiányzó repo vagy branch"
            })

    return jsonify(printed)

@app.route('/api/install_selected', methods=['POST'])
def api_install_selected():
    """Kijelölt robotok letöltése és telepítése, de nem futtatja őket."""
    data = request.get_json(silent=True) or {}
    robots = data.get('robots') or []
    logger.info(f"[INSTALL_SELECTED] Download gomb lenyomva, robots param: {robots}")
    if not robots:
        logger.warning("[INSTALL_SELECTED] Nincs kiválasztott robot a letöltéshez.")
        return jsonify({'success': False, 'error': 'Nincs kiválasztott robot.'}), 400
    installed = []
    errors = []
    for r in robots:
        repo = (r.get('repo') or '').strip()
        branch = (r.get('branch') or '').strip()
        if not repo or not branch:
            errors.append({'repo': repo, 'branch': branch, 'error': 'Hiányzó repo vagy branch'})
            continue
        try:
            # Log the install_robot_with_params call
            logger.info(f"[INSTALL_SELECTED] install_robot_with_params hívás: repo='{repo}', branch='{branch}'")
            # Itt csak letöltés és telepítés, futtatás nélkül
            rc, out_dir, _stdout, _stderr = install_robot_with_params(repo, branch)
            if rc == 0:
                installed.append({'repo': repo, 'branch': branch, 'results_dir': out_dir})
            else:
                errors.append({'repo': repo, 'branch': branch, 'error': f'Installáció sikertelen, rc={rc}'})
        except Exception as e:
            errors.append({'repo': repo, 'branch': branch, 'error': str(e)})
    if errors:
        return jsonify({'success': False, 'installed': installed, 'errors': errors})
    return jsonify({'success': True, 'installed': installed})
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
        if not base_dir:
            base_dir = _normalize_dir_from_vars('DOWNLOADED_ROBOTS') or os.path.join(os.getcwd(), 'DownloadedRobots')

        safe_repo = repo.replace('/', '_')
        safe_branch = branch.replace('/', '_')
        target_dir = os.path.join(base_dir, safe_repo, safe_branch)
        start_bat = os.path.join(target_dir, 'start.bat')

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
    base_inst = get_installed_robots_dir()
    keys = sorted(list(get_installed_keys()))
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
        return jsonify({'enabled': enabled, 'sandbox_mode': enabled})
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

def get_html_template():
    """Visszaadja a HTML template-et a parse_repos.py alapján"""

    # SANDBOX_MODE ellenőrzése
    is_sandbox = get_sandbox_mode()
    page_title = "Fejlesztői mód" if is_sandbox else "Segíthetünk?"
    
    # Színséma beállítása SANDBOX_MODE alapján
    if is_sandbox:
        # Fejlesztői mód: piros színvilág
        primary_color = "#dc3545"
        secondary_color = "#e74c3c" 
        tertiary_color = "#f1aeb5"
        dark_color = "#c82333"
        light_color = "#f8d7da"
        hover_color = "#b02a37"
        rgba_color = "220, 53, 69"
    else:
        # Normál mód: kék színvilág
        primary_color = "#0d6efd"
        secondary_color = "#3b82f6"
        tertiary_color = "#93c5fd"
        dark_color = "#0056b3"
        light_color = "#e7f3ff"
        hover_color = "#004085"
        rgba_color = "13, 110, 253"
    
    # CSS template létrehozása a dinamikus színekkel  
    css_template = '''<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>''' + page_title + ''' - Robot Kezelő v2.1</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
<style>
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: white; min-height: 100vh; }
.main-container { max-width: 1400px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); overflow: hidden; }
.page-header { background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 50%, {tertiary_color} 100%); color: white; padding: 30px; display: flex; align-items: center; justify-content: space-between; }
.page-header .header-content { display: flex; flex-direction: column; align-items: center; flex: 1; }
.page-header h1 { margin: 0; font-size: 2.5rem; font-weight: 700; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.timestamp { margin-top: 10px; opacity: 0.9; font-size: 0.95rem; }
.nav-tabs { border-bottom: 3px solid {primary_color}; background: #f8f9fa; }
.nav-tabs .nav-link { color: #495057; border: none; padding: 15px 25px; font-weight: 600; border-radius: 0; }
.nav-tabs .nav-link.active { background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 50%, {tertiary_color} 100%); color: white; border-bottom: 3px solid {primary_color}; }
.nav-tabs .nav-link:hover { background: linear-gradient(135deg, {tertiary_color} 0%, {light_color} 100%); color: {primary_color}; }
.tab-content { padding: 30px; }
/* Minden card halványkék háttérrel és vékony szürke kerettel */
/* Minden card halványkék háttérrel és vékony szürke kerettel */
/* Minden card halványkék háttérrel és vékony szürke kerettel, extra erősséggel */
.card, .repo-card {
    background-color: #e3f2fd !important;
    border: 1px solid #b0bec5 !important;
}
.card.bg-white, .card.bg-light, .repo-card.bg-white, .repo-card.bg-light {
    background-color: #e3f2fd !important;
}
.actions { text-align: center; margin: 25px 0; padding: 20px; background: #f8f9fa; border-radius: 10px; }
.btn-custom { background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 50%, {tertiary_color} 100%); color: white; padding: 12px 25px; border: none; border-radius: 8px; margin: 8px; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.3s ease; box-shadow: 0 3px 6px rgba(0,0,0,0.1); }
.btn-custom:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); background: linear-gradient(135deg, {hover_color} 0%, {primary_color} 50%, {tertiary_color} 100%); }
.repo-card { 
    transition: all 0.3s ease; 
}
.repo-card:hover { 
    transform: translateY(-5px); 
    box-shadow: 0 8px 25px rgba(220,53,69,0.25) !important; 
    border-color: {primary_color}; 
}
.repo-card .card-header { 
    background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 50%, {dark_color} 100%) !important; 
    color: white !important;
}
.repo-card .card-title a:hover { text-decoration: underline !important; }
.branches-container { max-height: 300px; overflow-y: auto; }
.branch-checkbox { padding: 8px 12px; margin: 2px 0; border-radius: 6px; transition: background-color 0.2s; }
.branch-checkbox:hover { background-color: #f8f9fa; }
.branch-checkbox input:checked + label { font-weight: bold; color: {primary_color}; }
/* Always show a border for checkboxes, even when not checked */
.branch-checkbox .form-check-input[type="checkbox"] {
    border: 2px solid #888;
    background-color: #fff;
    box-shadow: none;
    -webkit-appearance: checkbox;
         -moz-appearance: checkbox;
                    appearance: checkbox;
}
.branch-checkbox .form-check-input[type="checkbox"]:focus {
    border-color: #007bff;
    box-shadow: 0 0 0 0.15rem rgba(0,123,255,.25);
}
/* Always show a border for checkboxes, even when not checked */
/* Widen and emphasize switches for robot selection */
#repoSearch:focus, #branchFilter:focus { border-color: {primary_color}; box-shadow: 0 0 0 0.2rem rgba({rgba_color}, 0.25); }
.input-group-text.bg-primary { background: linear-gradient(135deg, #0d6efd 0%, #6610f2 100%) !important; }
.input-group-text.bg-success { background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 50%, {tertiary_color} 100%) !important; }
.hidden { display: none !important; }
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="main-container">
<div class="page-header">
<div class="header-content">
<h1><i class="bi bi-robot"></i> ''' + page_title + '''</h1>
</div>
</div>
<ul class="nav nav-tabs" id="mainTabs" role="tablist">
<li class="nav-item" role="presentation">
<button class="nav-link active" id="download-tab" data-bs-toggle="tab" data-bs-target="#download-pane" type="button" role="tab">
<i class="bi bi-robot"></i> Futtatható robotok
</button>
</li>
<li class="nav-item" role="presentation">
<button class="nav-link" id="available-tab" data-bs-toggle="tab" data-bs-target="#available-pane" type="button" role="tab">
<i class="bi bi-download"></i> Letölthető robotok
</button>
</li>
<li class="nav-item" role="presentation">
<button class="nav-link" id="results-tab" data-bs-toggle="tab" data-bs-target="#results-pane" type="button" role="tab">
<i class="bi bi-list-task"></i> Eredmények
</button>
</li>
<li class="nav-item" role="presentation">
<button class="nav-link" id="info-tab" data-bs-toggle="tab" data-bs-target="#info-pane" type="button" role="tab">
<i class="bi bi-info-circle"></i> Információ
</button>
</li>
<li class="nav-item" role="presentation">
<button class="nav-link" id="settings-tab" data-bs-toggle="tab" data-bs-target="#settings-pane" type="button" role="tab">
<i class="bi bi-gear"></i> Beállítások
</button>
</li>
<li class="nav-item" role="presentation">
<button class="nav-link" id="exit-tab" data-bs-toggle="tab" data-bs-target="#exit-pane" type="button" role="tab">
<i class="bi bi-box-arrow-right"></i> Kilépés
</button>
</li>
</ul>
<div class="tab-content" id="mainTabContent">
<!-- Futtatható robotok TAB -->
<div class="tab-pane fade show active" id="download-pane" role="tabpanel">
    <!-- Keresés és szűrés -->
    <div class="row mb-4 align-items-center">
        <div class="col-md-4">
            <div class="input-group">
                <span class="input-group-text bg-primary text-white"><i class="bi bi-search"></i></span>
                <input type="text" class="form-control" id="repoSearch" placeholder="Repository keresése..." onkeyup="filterRepos()">
            </div>
        </div>
        <div class="col-md-4">
            <div class="input-group">
                <span class="input-group-text bg-success text-white"><i class="bi bi-filter"></i></span>
                <input type="text" class="form-control" id="branchFilter" placeholder="Robot szűrése..." onkeyup="filterRepos()">
            </div>
        </div>
        <div class="col-md-4 d-flex align-items-center">
            <div class="text-muted small">
                <i class="bi bi-info-circle me-1"></i>
                Indítsa a robotokat a bal oldali Play gombbal
            </div>
        </div>
    </div>
    <!-- Branch név label eltávolítva -->
    <!-- Repository kártyák -->
    <div class="row" id="repoContainer">
    {% for repo in repos %}
        {% if repo.downloaded_branches|length > 0 %}
        <div class="col-lg-6 col-xl-4 mb-4 repo-item" data-repo-name="{{ repo.name }}">
            <div class="card repo-card h-100" style="background-color: #e3f2fd !important;">
                <div class="card-header text-white">
                    <h5 class="card-title mb-0">
                        <i class="bi bi-github"></i>
                        <a href="{{ repo.html_url }}" target="_blank" class="text-white text-decoration-none">
                            {{ repo.name }}
                        </a>
                    </h5>
                    {% if repo.updated_at %}
                    <small class="opacity-75">{{ repo.updated_at[:10] }}</small>
                    {% endif %}
                </div>
                <div class="card-body">
                    <p class="card-text">{{ repo.description or 'Nincs leírás' }}</p>
                    <h6 class="mt-3"><i class="bi bi-git"></i> Robotok:</h6>
                    <div class="branches-container">
                        {% for branch in repo.downloaded_branches %}
                            <div class="branch-checkbox d-flex align-items-center" style="margin-bottom: 5px;" id="branch-{{ repo.name }}-{{ branch }}">
                                <button class="btn btn-success btn-sm me-2" title="Futtatás"
                                    data-repo="{{ repo.name }}"
                                    data-branch="{{ branch }}"
                                    onclick="executeSingleRobot(this)">
                                    <i class="bi bi-play-fill"></i>
                                </button>
                                <i class="bi bi-trash text-danger me-2" 
                                   style="cursor: pointer;" 
                                   onclick='deleteRunnableBranch({{ repo.name | tojson }}, {{ branch | tojson }})'
                                   data-bs-toggle="tooltip" 
                                   data-bs-placement="top" 
                                   title="Eltávolítás a futtathatók közül"></i>
                                <span>{{ branch }}</span>
                            </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
    {% endfor %}
    </div>
    
</div>
<!-- Letölthető robotok TAB -->
<div class="tab-pane fade" id="available-pane" role="tabpanel">
    <!-- Keresés és szűrés (ugyanaz, mint a másik tabon, de külön azonosítókkal, ha kell) -->
    <div class="row mb-4 align-items-center">
        <div class="col-md-4">
            <div class="input-group">
                <span class="input-group-text bg-primary text-white"><i class="bi bi-search"></i></span>
                <input type="text" class="form-control" id="repoSearchAvailable" placeholder="Repository keresése..." onkeyup="filterReposAvailable()">
            </div>
        </div>
        <div class="col-md-4">
            <div class="input-group">
                <span class="input-group-text bg-success text-white"><i class="bi bi-filter"></i></span>
                <input type="text" class="form-control" id="branchFilterAvailable" placeholder="Robot szűrése..." onkeyup="filterReposAvailable()">
            </div>
        </div>
        <div class="col-md-4 d-flex align-items-center">
            <div class="text-muted small">
                <i class="bi bi-info-circle me-1"></i>
                Kattintson a letöltés gombra azonnali telepítéshez
            </div>
        </div>
    </div>
    <!-- Branch név label eltávolítva -->
    <!-- Repository kártyák -->
    <div class="row" id="repoContainerAvailable">
    {% for repo in repos %}
        {% if repo.available_branches|length > 0 %}
        <div class="col-lg-6 col-xl-4 mb-4 repo-item-available" data-repo-name="{{ repo.name }}">
            <div class="card repo-card h-100">
                <div class="card-header text-white">
                    <h5 class="card-title mb-0">
                        <i class="bi bi-github"></i>
                        <a href="{{ repo.html_url }}" target="_blank" class="text-white text-decoration-none">
                            {{ repo.name }}
                        </a>
                    </h5>
                    {% if repo.updated_at %}
                    <small class="opacity-75">{{ repo.updated_at[:10] }}</small>
                    {% endif %}
                </div>
                <div class="card-body">
                    <p class="card-text">{{ repo.description or 'Nincs leírás' }}</p>
                    <h6 class="mt-3"><i class="bi bi-git"></i> Robotok:</h6>
                    <div class="branches-container">
                        {% for branch in repo.available_branches %}
                            <div class="branch-checkbox d-flex align-items-center" id="branch-available-{{ repo.name }}-{{ branch }}">
                                <button class="btn btn-warning btn-sm me-2 text-dark"
                                    type="button"
                                    title="Azonnali letöltés"
                                    onclick='installRobot({{ repo.name | tojson }}, {{ branch | tojson }}, this)'>
                                    <i class="bi bi-download"></i>
                                </button>
                                <span>{{ branch }}</span>
                             </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
    {% endfor %}
    </div>
</div>
<div class="tab-pane fade" id="info-pane" role="tabpanel">
<h3><i class="bi bi-info-circle-fill text-info"></i> Rendszer Információk</h3>
<div class="row">
<div class="col-md-6">
<div class="card" style="background-color: #e3f2fd !important;">
<div class="card-header text-white" style="background: linear-gradient(135deg, {primary_color}, {dark_color});">
<h5><i class="bi bi-laptop"></i> Rendszer</h5>
</div>
<div class="card-body">
<ul class="list-unstyled">
<li><strong>Platform:</strong> Flask Web App</li>
<li><strong>Python verzió:</strong> 3.x</li>
<li><strong>Framework:</strong> Bootstrap 5</li>
<li><strong>Adatbázis:</strong> JSON fájlok</li>
</ul>
</div>
</div>
</div>

<div class="col-md-6">
<div class="card">
<div class="card-header bg-success text-white">
<h5><i class="bi bi-github"></i> GitHub Integráció</h5>
</div>
<div class="card-body">
<ul class="list-unstyled">
<li><strong>Felhasználó:</strong> lovaszotto</li>
<li><strong>Repository-k:</strong> {{ repos|length }}</li>
<li><strong>API verzió:</strong> v3 REST</li>
<li><strong>Kódolás:</strong> UTF-8</li>
</ul>
</div>
</div>
</div>
</div>
</div>
<div class="tab-pane fade" id="settings-pane" role="tabpanel">
<h3><i class="bi bi-gear-fill text-secondary"></i> Beállítások</h3>
<div class="row">
<div class="col-md-6">
<div class="card">
<div class="card-header bg-primary text-white">
<h5><i class="bi bi-display"></i> Megjelenítés</h5>
</div>
<div class="card-body">
<div class="form-check form-switch mb-3">
<input class="form-check-input" type="checkbox" role="switch" id="darkMode" checked>
<label class="form-check-label" for="darkMode">Sötét téma</label>
</div>
<div class="form-check form-switch mb-3">
<input class="form-check-input" type="checkbox" role="switch" id="compactView">
<label class="form-check-label" for="compactView">Kompakt nézet</label>
</div>
<div class="mb-3">
<label for="pageSize" class="form-label">Oldalankénti elemek száma</label>
<select class="form-select" id="pageSize">
<option value="10">10</option>
<option value="20">20</option>
<option value="50">50</option>
</select>
</div>
<button class="btn btn-primary" onclick="saveSettings()">
<i class="bi bi-check-lg"></i> Beállítások mentése
</button>
</div>
</div>
</div>

<div class="col-md-6">
<div class="card">
<div class="card-header bg-warning text-dark">
<h5><i class="bi bi-tools"></i> Futtatási beállítások</h5>
</div>
<div class="card-body">
<div class="mb-3">
<label for="executionMode" class="form-label">Futtatási mód</label>
<select class="form-select" id="executionMode">
<option value="sequential">Soros futtatás</option>
<option value="parallel">Párhuzamos futtatás</option>
</select>
</div>
<div class="mb-3">
<label for="timeout" class="form-label">Időtúllépés (másodperc)</label>
<input type="number" class="form-control" id="timeout" value="300" min="30" max="3600">
</div>
<div class="form-check form-switch mb-3">
<input class="form-check-input" type="checkbox" role="switch" id="generateReport" checked>
<label class="form-check-label" for="generateReport">Jelentés generálása</label>
</div>
<div class="form-check form-switch mb-3">
    <input class="form-check-input" type="checkbox" role="switch" id="sandboxMode" onchange="updateSandboxMode()">
    <label class="form-check-label" for="sandboxMode">Fejlesztői mód (csak letöltés, telepítés nélkül)</label>
</div>
<button class="btn btn-warning" onclick="resetSettings()">
<i class="bi bi-arrow-clockwise"></i> Alapértelmezett
</button>
</div>
</div>
</div>
</div>
</div>
<div class="tab-pane fade" id="results-pane" role="tabpanel">
<div class="card">
<div class="card-header text-white" style="background: linear-gradient(135deg, {primary_color}, {dark_color});">
<h5 class="mb-0"><i class="bi bi-list-task"></i> Futási Eredmények</h5>
</div>
<!-- Modal for showing resultsDir -->
<div class="modal fade" id="resultsModal" tabindex="-1" aria-labelledby="resultsModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="resultsModalLabel">Eredmények</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <iframe id="resultsModalIframe" style="width:100%;height:60vh;border:0;" sandbox="allow-same-origin allow-forms"></iframe>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" id="resultsModalReturn" data-bs-dismiss="modal">Visszatérés</button>
                <button type="button" class="btn btn-primary d-none" id="resultsModalOpenNew" title="Megnyitás új lapon">Megnyitás új lapon</button>
            </div>
        </div>
    </div>
</div>
<div class="card-body">
<!-- Keresés és szűrés -->
<div class="row mb-3">
<div class="col-md-4">
<div class="input-group">
<span class="input-group-text"><i class="bi bi-search"></i></span>
<input type="text" class="form-control" id="searchResults" placeholder="Keresés robot vagy branch szerint...">
</div>
</div>
<div class="col-md-3">
<select class="form-select" id="statusFilter">
<option value="">Összes státusz</option>
<option value="success">Sikeres</option>
<option value="failed">Sikertelen</option>
</select>
</div>
<div class="col-md-3">
<input type="date" class="form-control" id="dateFilter" title="Szűrés dátum szerint">
</div>
<div class="col-md-2">
<button class="btn btn-outline-danger w-100" onclick="refreshResults()">
<i class="bi bi-arrow-clockwise"></i> Frissítés
</button>
</div>
</div>
<div class="table-responsive">
<table class="table table-striped table-hover">
<thead class="table-dark">
<tr>
<th onclick="sortResults('timestamp')">
<i class="bi bi-calendar"></i> Időpont 
<span class="sort-indicator" id="sort-timestamp"></span>
</th>
<th onclick="sortResults('repo')">
<i class="bi bi-github"></i> Repository 
<span class="sort-indicator" id="sort-repo"></span>
</th>
<th onclick="sortResults('branch')">
<i class="bi bi-git"></i> Branch 
<span class="sort-indicator" id="sort-branch"></span>
</th>
<th onclick="sortResults('status')">
<i class="bi bi-check-circle"></i> Státusz 
<span class="sort-indicator" id="sort-status"></span>
</th>
<th><i class="bi bi-folder"></i> Eredmények</th>
<th><i class="bi bi-gear"></i> Műveletek</th>
</tr>
</thead>
<tbody id="resultsTableBody">
<tr>
<td colspan="6" class="text-center text-muted py-4">
<i class="bi bi-hourglass-split"></i> Eredmények betöltése...
</td>
</tr>
</tbody>
</table>
</div>
<div class="d-flex justify-content-between align-items-center mt-3">
<div>
<span class="text-muted" id="resultsInfo">Összesen: 0 eredmény</span>
</div>
<nav>
<ul class="pagination pagination-sm" id="resultsPagination">
<!-- Dinamikusan generált lapozó -->
</ul>
</nav>
</div>
</div>
</div>
</div>
<div class="tab-pane fade" id="exit-pane" role="tabpanel">
<div class="text-center mt-5">
<h3><i class="bi bi-box-arrow-right text-danger"></i> Kilépés</h3>
<p class="lead mb-4">Biztos, hogy ki szeretne lépni az alkalmazásból?</p>
<div class="d-grid gap-2 d-md-block">
<button id="exitButton" class="btn btn-danger btn-lg">
<i class="bi bi-box-arrow-right"></i> Kilépés
</button>
<button class="btn btn-secondary btn-lg" onclick="cancelExit()">
<i class="bi bi-arrow-left"></i> Mégse
</button>
</div>
</div>
</div>
</div>
</div>
<!-- jQuery és Bootstrap JavaScript -->
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
// SANDBOX_MODE lekérdezése backendről
let SANDBOX_MODE = false;
const ROOT_FOLDER = {{ (root_folder or '')|tojson }};
fetch('/api/get_sandbox_mode').then(r => r.json()).then(data => {
    SANDBOX_MODE = !!data.sandbox_mode;
    updateSandboxModeUI();
});

// Play gomb: csak megerősít, majd a közös végrehajtó ágra delegál
function executeSingleRobot(button) {
    const repo = button.getAttribute('data-repo');
    const branch = button.getAttribute('data-branch');
    const fallbackRoot = (typeof ROOT_FOLDER === 'string') ? ROOT_FOLDER : '';
    const msgLines = [
        'Valóban futtassam a robotot?',
        '',
        'Repo: ' + repo,
        'Branch: ' + branch,
        fallbackRoot ? ('Gyökér: ' + fallbackRoot) : ''
    ].filter(Boolean);
    const msg = msgLines.join("\\n");
    if (!confirm(msg)) {
        return;
    }
    try {
        showToast(`Robot futtatása indult: ${repo}/${branch}`, 'info');
        // Spinner és disable a gombon
        if (button) {
            button.disabled = true;
            button._originalInnerHTML = button.innerHTML;
            button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
        }
        executeRobot(repo, branch, button);
    } catch (e) {
        showToast('Robot indítás hiba: ' + String(e), 'danger');
        if (button) {
            button.disabled = false;
            if (button._originalInnerHTML) button.innerHTML = button._originalInnerHTML;
        }
    }
}

function updateSandboxModeUI() {
    const runBtn = document.querySelector('button[onclick="executeAllRobots()"]');
    const installBtn = document.querySelector('button[onclick="installSelectedRobots()"]');
    if (SANDBOX_MODE) {
        if (runBtn) {
            runBtn.style.display = 'none';
        }
        if (installBtn) {
            installBtn.disabled = false;
            installBtn.classList.remove('disabled');
        }
    } else {
        if (runBtn) {
            runBtn.style.display = '';
            runBtn.disabled = false;
            runBtn.classList.remove('disabled');
        }
        if (installBtn) {
            installBtn.disabled = false;
            installBtn.classList.remove('disabled');
        }
    }
}
// Kijelölt robotok telepítése (csak letöltés + install, nem futtat)
function installSelectedRobots() {
    console.log('[WORKFLOW] Kijelöltek letöltése indult');
    const robots = Array.from(document.querySelectorAll('.robot-checkbox-available:checked')).map(cb => ({
        repo: cb.getAttribute('data-repo'),
        branch: cb.getAttribute('data-branch')
    }));
    installRobots(robots);
}

// Egyedi robot azonnali letöltése a Letölthető tab-ról
function installRobot(repo, branch, buttonElement) {
    console.log('[WORKFLOW] Egyedi robot letöltése indult', repo, branch);
    installRobots([{ repo, branch }], { triggerButton: buttonElement });
}

function installRobots(robots, options = {}) {
    const { triggerButton = null } = options;
    const installBtn = document.querySelector('button[onclick="installSelectedRobots()"]');
    const runBtn = document.querySelector('button[onclick="executeAllRobots()"]');

    if (installBtn) installBtn.disabled = true;
    if (runBtn) runBtn.disabled = true;
    let triggerOriginalHtml = null;
    if (triggerButton) {
        triggerOriginalHtml = triggerButton.innerHTML;
        triggerButton.disabled = true;
        triggerButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    }

    if (!robots || robots.length === 0) {
        showToast('Nincs kijelölt robot a letöltéshez.', 'warning');
        if (installBtn) installBtn.disabled = false;
        if (runBtn) runBtn.disabled = SANDBOX_MODE ? true : false;
        if (triggerButton) {
            triggerButton.disabled = false;
            triggerButton.innerHTML = triggerOriginalHtml || '<i class="bi bi-download"></i>';
        }
        return;
    }

    console.log('[WORKFLOW] Letöltési kérés elküldése a backendnek', robots);
    fetch('/api/install_selected', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ robots })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                console.log('[WORKFLOW] Sikeres letöltés, telepített robotok:', data.installed);
                showToast('A kijelölt robotok letöltése sikeres.', 'success');
                const installed = data.installed || [];
                installed.forEach(inst => {
                    removeRobotFromExecutionList(inst.repo, inst.branch);
                    const cb = document.querySelector(`.robot-checkbox-available[data-repo="${inst.repo}"][data-branch="${inst.branch}"]`);
                    if (cb) cb.checked = false;
                });
                refreshRunnableRobots();
                if (typeof refreshAvailableRobots === 'function') {
                    refreshAvailableRobots();
                }
            } else {
                console.log('[WORKFLOW] Sikertelen letöltés vagy részleges hiba', data);
                if (data.errors && data.errors.length > 0) {
                    data.errors.forEach(err => {
                        const card = document.querySelector(
                            `.card[data-repo="${err.repo}"][data-branch="${err.branch}"]`
                        );
                        if (card) {
                            let errorDiv = card.querySelector('.install-error-msg');
                            if (!errorDiv) {
                                errorDiv = document.createElement('div');
                                errorDiv.className = 'alert alert-danger install-error-msg mt-2 mb-0';
                                card.querySelector('.card-body').appendChild(errorDiv);
                            }
                            errorDiv.innerHTML = `<i class="bi bi-exclamation-triangle"></i> Letöltési hiba: ${err.error || 'Ismeretlen hiba'}`;
                        }
                    });
                } else {
                    showToast('Hiba a letöltés során: ' + (data.error || 'Ismeretlen hiba'), 'danger');
                }
            }
        })
        .catch(err => {
            showToast('Hálózati vagy szerverhiba: ' + err, 'danger');
        })
        .finally(() => {
            if (installBtn) installBtn.disabled = false;
            if (runBtn) runBtn.disabled = SANDBOX_MODE ? true : false;
            if (triggerButton) {
                triggerButton.disabled = false;
                triggerButton.innerHTML = triggerOriginalHtml || '<i class="bi bi-download"></i>';
            }
        });
}
// Törlési funkció - mindenképpen legyen elérhető
function deleteRunnableBranch(repoName, branchName) {
    if (confirm('Valóban törölni szeretnéd a futtathatók közül?\\n\\nRepository: ' + repoName + '\\nBranch: ' + branchName)) {
        deleteBranchFromRunnable(repoName, branchName);
    }
}

// Letölthető robotok azonnali hozzáadása/eltávolítása a Futtatás tab-hoz
function handleAvailableRobotToggle(checkbox) {
    const repo = checkbox.getAttribute('data-repo');
    const branch = checkbox.getAttribute('data-branch');
    
    if (checkbox.checked) {
        // Hozzáadás a futtatási listához
        addRobotToExecutionList(repo, branch);
        console.log(`Robot hozzáadva a futtatási listához: ${repo}/${branch}`);
    } else {
        // Eltávolítás a futási listából
        removeRobotFromExecutionList(repo, branch);
        console.log(`Robot eltávolítva a futtatható listából: ${repo}/${branch}`);
    }
}

// Futtatható robotok checkbox kezelése
function handleRunnableRobotToggle(checkbox) {
    const repo = checkbox.getAttribute('data-repo');
    const branch = checkbox.getAttribute('data-branch');
    
    if (checkbox.checked) {
        // Hozzáadás a futtatási listához
        addRobotToExecutionList(repo, branch);
        console.log(`Futtatható robot hozzáadva: ${repo}/${branch}`);
    } else {
        // Eltávolítás a futtatható listából
        removeRobotFromExecutionList(repo, branch);
        console.log(`Futtatható robot eltávolítva: ${repo}/${branch}`);
    }
    
    // Továbbra is frissítsük a régi gomb állapotot is (kompatibilitás)
    // updateRunButton(); // Futtatás tab megszűnt, törölhető
}

// Robot hozzáadása a futtatási listához (Futtatás tab)
function addRobotToExecutionList(repo, branch) {
    // Ellenőrizzük, hogy már kiválasztott-e
    const existingRobots = getSelectedRobots();
    const alreadySelected = existingRobots.some(r => r.repo === repo && r.branch === branch);
    
    if (!alreadySelected) {
        const newRobot = { repo, branch };
        const allSelected = [...existingRobots, newRobot];
        showSelectedRobots(allSelected);
        
        // Gombok megjelenítése
        const executionButtons = document.getElementById('executionButtons');
        if (executionButtons) {
            executionButtons.style.display = 'block';
        }
    }
}

// Robot eltávolítása a futtatási listából
function removeRobotFromExecutionList(repo, branch) {
    const existingRobots = getSelectedRobots();
    const filteredRobots = existingRobots.filter(r => !(r.repo === repo && r.branch === branch));
    
    if (filteredRobots.length > 0) {
        showSelectedRobots(filteredRobots);
    } else {
        // Ha nincs több kiválasztott robot
        const executionButtons = document.getElementById('executionButtons');
        if (executionButtons) {
            executionButtons.style.display = 'none';
        }
        
        const container = document.getElementById('selectedRobotsContainer');
        container.innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Válasszon ki robotokat a "Letölthető robotok" tab-on a futtatáshoz.</div>';
        
        // Tab számok frissítése
        updateTabCounts();
    }
}

// Segédfüggvény: aktuálisan kiválasztott robotok lekérdezése a Futtatás tab-ról
function getSelectedRobots() {
    const container = document.getElementById('selectedRobotsContainer');
    if (!container) return [];
    
    const robotCards = container.querySelectorAll('.card[data-repo][data-branch]');
    const robots = [];
    
    robotCards.forEach(card => {
        const repo = card.getAttribute('data-repo');
        const branch = card.getAttribute('data-branch');
        if (repo && branch) {
            robots.push({ repo, branch });
        }
    });
    
    return robots;
}
// Card-ok kezelése
function filterRepos() {
    const searchTerm = document.getElementById('repoSearch').value.toLowerCase();
    const branchFilter = document.getElementById('branchFilter').value.toLowerCase();
    const repoItems = document.querySelectorAll('.repo-item');
    
    repoItems.forEach(item => {
        const repoName = item.getAttribute('data-repo-name').toLowerCase();
        const branches = item.querySelectorAll('.branch-checkbox span');
        let hasMatchingBranch = false;
        
        branches.forEach(branch => {
            const branchName = branch.textContent.toLowerCase().trim();
            if (branchName.includes(branchFilter)) {
                hasMatchingBranch = true;
            }
        });
        
        if (repoName.includes(searchTerm) && (branchFilter === '' || hasMatchingBranch)) {
            item.style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
}

function filterReposAvailable() {
    const searchTerm = document.getElementById('repoSearchAvailable').value.toLowerCase();
    const branchFilter = document.getElementById('branchFilterAvailable').value.toLowerCase();
    const repoItems = document.querySelectorAll('.repo-item-available');
    
    repoItems.forEach(item => {
        const repoName = item.getAttribute('data-repo-name').toLowerCase();
        const branches = item.querySelectorAll('.branch-checkbox span');
        let hasMatchingBranch = false;
        
        branches.forEach(branch => {
            const branchName = branch.textContent.toLowerCase().trim();
            if (branchName.includes(branchFilter)) {
                hasMatchingBranch = true;
            }
        });
        
        if (repoName.includes(searchTerm) && (branchFilter === '' || hasMatchingBranch)) {
            item.style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
}





function showSelectedRobots(robots) {
    console.log('showSelectedRobots hívva', robots.length, 'robottal');
    const container = document.getElementById('selectedRobotsContainer');
    
    // Gombok megjelenítése a fejlécben
    const executionButtons = document.getElementById('executionButtons');
    if (executionButtons) {
        executionButtons.style.display = 'block';
    }
    
    let html = '<h4><i class="bi bi-list-check"></i> Kiválasztott Robotok:</h4>';
    
    html += '<div class="row">';
        robots.forEach((robot) => {
        html += `
        <div class="col-md-6 mb-3">
            <div class="card" data-repo="${robot.repo}" data-branch="${robot.branch}">
                <div class="card-body">
                    <h6><i class="bi bi-github"></i> ${robot.repo}</h6>
                    <p class="mb-2"><i class="bi bi-git"></i> <strong>Robot:</strong> ${robot.branch}</p>
                    <div class="d-flex" style="gap: 8px;">
                        <button class="btn btn-outline-success btn-sm" onclick="executeRobot('${robot.repo}', '${robot.branch}')" title="Robot futtatása">
                                <i class="bi bi-play"></i> Indítás
                        </button>
                                               <button class="btn btn-outline-danger btn-sm" onclick="removeRobotFromList('${robot.repo}', '${robot.branch}')" title="Eltávolítás a listából">
                            <i class="bi bi-x-circle"></i> Mégse
                        </button>
                    </div>
                </div>
            </div>
        </div>`;
    });
    html += '</div>';
    
    container.innerHTML = html;
    
    // Tab számok frissítése
    updateTabCounts();
}

function executeRobot(repo, branch, button) {
    // "Fut" státusz megjelenítése azonnal
    const container = document.getElementById('selectedRobotsContainer');
    const currentTime = new Date().toLocaleString('hu-HU');
    if (container) {
        const tempMsg = document.createElement('div');
        tempMsg.className = 'alert alert-info mt-3';
        tempMsg.id = `status-${repo}-${branch}`;
        tempMsg.innerHTML = `
            <i class="bi bi-arrow-clockwise spinning"></i> Elküldve a szervernek: <strong>${repo}/${branch}</strong> 
            <small class="text-muted">(${currentTime})</small>
            <div class="mt-2">
                <span class="badge bg-primary">Státusz: Fut</span>
            </div>
        `;
        container.appendChild(tempMsg);
    }
    
    // Szerver értesítése a futtatásról
    fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo, branch })
    })
    .then(r => r.json())
    .then(data => {
        console.log('Szerver válasz (execute):', data);
        
        // Ideiglenes "Fut" üzenet eltávolítása
        const tempMsg = document.getElementById(`status-${repo}-${branch}`);
        if (tempMsg) tempMsg.remove();
        
        // Gomb visszaállítása
        if (button) {
            button.disabled = false;
            if (button._originalInnerHTML) button.innerHTML = button._originalInnerHTML;
        }

        const msg = document.createElement('div');
        const currentTime = new Date().toLocaleString('hu-HU');
        const statusIcon = getStatusIcon(data.returncode);
        const statusText = getStatusText(data.returncode);
        const statusClass = getStatusClass(data.returncode);
        
        msg.className = `alert ${statusClass} mt-3`;
        msg.innerHTML = `
            ${statusIcon} Futtatás befejezve: <strong>${repo}/${branch}</strong> 
            <small class="text-muted">(${currentTime})</small>
            <div class="mt-2">
                <span class="badge bg-secondary">Végső státusz: ${statusText}</span>
                <button class="btn btn-success btn-sm ms-2" onclick="markAsSuccessAndRemove('${repo}', '${branch}', this)" title="Sikeres befejezésként jelöl és eltávolít a listából">
                    <i class="bi bi-check-circle"></i> Sikeres
                </button>
            </div>
        `;
        const container = document.getElementById('selectedRobotsContainer');
        container.appendChild(msg);
        
        // Sikeres futás ellenőrzése különböző kritériumok alapján
        console.log(`Debug: Return code érték: ${data.returncode} (típus: ${typeof data.returncode})`);
        console.log(`Debug: Teljes szerver válasz:`, data);
        
        // Többfaktoros sikeres futás ellenőrzés
        const isSuccessful = 
            data.returncode === 0 || 
            data.status === "ok" || 
            data.status === "success" ||
            (data.results_dir && !data.results_dir.includes('error'));
            
        if (isSuccessful) {
            console.log(`Sikeres futás észlelve (többfaktoros): ${repo}/${branch} - eltávolítás a listából`);
            removeRobotFromSelection(repo, branch);
            setTimeout(() => {
                msg.innerHTML += `
                    <div class="mt-2">
                        <small class="text-success">
                            <i class="bi bi-check-circle"></i> Robot automatikusan eltávolítva a kiválasztottak közül
                        </small>
                    </div>
                `;
            }, 2000);
        } else {
            console.log(`Sikertelen futás: ${repo}/${branch} - returncode: ${data.returncode}, status: ${data.status}`);
        }
        
        // Eredmények lista frissítése a futtatás után
        console.log('Eredmények lista frissítése...');
        loadResults();
        
        // Futtatható robotok lista frissítése a futtatás után (ha telepítés történt)
        console.log('Futtatható robotok lista frissítése...');
        refreshRunnableRobots();
        
        setTimeout(() => msg.remove(), 10000);
    })
    .catch(err => {
        console.error('Hiba (execute):', err);
        alert('Hiba történt a szerver hívása közben.');
        
        // Gomb visszaállítása hiba esetén is
        if (button) {
            button.disabled = false;
            if (button._originalInnerHTML) button.innerHTML = button._originalInnerHTML;
        }

        // Hiba esetén is frissítsük az eredményeket és a futtatható listát
        loadResults();
        refreshRunnableRobots();
    });
}







function markAsSuccessAndRemove(repo, branch, buttonElement) {
    console.log(`Manuális sikeres jelölés: ${repo}/${branch}`);
    
    // Gomb módosítása jelzésként
    buttonElement.innerHTML = '<i class="bi bi-check-circle-fill"></i> Eltávolítva';
    buttonElement.className = 'btn btn-outline-success btn-sm ms-2';
    buttonElement.disabled = true;
    
    // Robot eltávolítása a kiválasztottak közül
    removeRobotFromSelection(repo, branch);
    
    // Vizuális visszajelzés hozzáadása
    setTimeout(() => {
        const alertDiv = buttonElement.closest('.alert');
        if (alertDiv) {
            alertDiv.innerHTML += `
                <div class="mt-2">
                    <small class="text-success">
                        <i class="bi bi-check-circle"></i> Robot manuálisan sikeresnek jelölve és eltávolítva a listából
                    </small>
                </div>
            `;
        }
    }, 500);
}

function removeRobotFromList(repo, branch) {
    console.log(`Manuális eltávolítás kérése: ${repo}/${branch}`);
    
    // Megerősítő dialógus
    if (confirm(`Biztos, hogy eltávolítja ezt a robotot a listából?\\n\\n${repo}/${branch}`)) {
        // Robot eltávolítása a kiválasztottak közül
        removeRobotFromSelection(repo, branch);
        
        // Vizuális visszajelzés
        const container = document.getElementById('selectedRobotsContainer');
        const currentTime = new Date().toLocaleString('hu-HU');
        const msg = document.createElement('div');
        msg.className = 'alert alert-warning mt-3';
        msg.innerHTML = `
            <i class="bi bi-info-circle"></i> Eltávolítva: <strong>${repo}/${branch}</strong> 
            <small class="text-muted">(${currentTime})</small>
            <div class="mt-2">
                <span class="badge bg-warning">Manuálisan eltávolítva</span>
            </div>
        `;
        container.appendChild(msg);
        
        // Üzenet automatikus eltávolítása 3 másodperc után
        setTimeout(() => {
            if (msg && msg.parentNode) {
                msg.remove();
            }
        }, 3000);
        
        console.log(`Robot sikeresen eltávolítva: ${repo}/${branch}`);
    } else {
        console.log(`Eltávolítás megszakítva: ${repo}/${branch}`);
    }
}

function clearSelection() {
    document.querySelectorAll('.robot-checkbox:checked').forEach(cb => cb.checked = false);
    // updateRunButton(); // Futtatás tab megszűnt, törölhető
    
    // Gombok elrejtése
    const executionButtons = document.getElementById('executionButtons');
    if (executionButtons) {
        executionButtons.style.display = 'none';
    }
    
    const container = document.getElementById('selectedRobotsContainer');
    container.innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Válasszon ki robotokat a "Futtatható robotok" tab-on a futtatáshoz.</div>';
    
    // Tab számok frissítése
    updateTabCounts();
}

function saveSettings() {
    const settings = {
        darkMode: document.getElementById('darkMode').checked,
        compactView: document.getElementById('compactView').checked,
        pageSize: document.getElementById('pageSize').value,
        executionMode: document.getElementById('executionMode').value,
        timeout: document.getElementById('timeout').value,
        generateReport: document.getElementById('generateReport').checked
        // sandboxMode-ot NEM mentjük localStorage-ba, mindig a backend a forrás
    };
    
    localStorage.setItem('robotManagerSettings', JSON.stringify(settings));
    alert('Beállítások mentve!');
}

function resetSettings() {
    document.getElementById('darkMode').checked = false;
    document.getElementById('compactView').checked = false;
    document.getElementById('pageSize').value = '10';
    document.getElementById('executionMode').value = 'sequential';
    document.getElementById('timeout').value = '300';
    document.getElementById('generateReport').checked = true;
    document.getElementById('sandboxMode').checked = false;
    
    // Sandbox mode visszaállítása a backend-en is
    updateSandboxMode();
    
    localStorage.removeItem('robotManagerSettings');
    alert('Beállítások visszaállítva!');
}

function loadSettings() {
    const savedSettings = localStorage.getItem('robotManagerSettings');
    if (savedSettings) {
        const settings = JSON.parse(savedSettings);
        document.getElementById('darkMode').checked = settings.darkMode || false;
        document.getElementById('compactView').checked = settings.compactView || false;
        document.getElementById('pageSize').value = settings.pageSize || '10';
        document.getElementById('executionMode').value = settings.executionMode || 'sequential';
        document.getElementById('timeout').value = settings.timeout || '300';
        document.getElementById('generateReport').checked = settings.generateReport !== undefined ? settings.generateReport : true;
        // sandboxMode-ot NEM töltjük a localStorage-ből, mindig a backend a forrás
    }
    
    // Sandbox mode betöltése a backend-ről (ez a mindig aktuális állapot)
    loadCurrentSandboxMode();
}

// Sandbox Mode kezelés
function updateSandboxMode() {
    const isEnabled = document.getElementById('sandboxMode').checked;
    
    fetch('/api/set_sandbox_mode', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            enabled: isEnabled
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Frissítjük a robotok listáját, mivel a forrás megváltozhatott
            updateTabCounts();
            refreshRunnableRobots();
            
            // Visszajelzés a felhasználónak
            showToast(isEnabled ? 'Sandbox mód bekapcsolva' : 'Sandbox mód kikapcsolva', 'success');
            // Teljes oldal frissítés a konzisztenst nézetért (nincs szerver újraindítás)
            setTimeout(() => { window.location.reload(); }, 800);
        } else {
            // Hiba esetén visszaállítjuk a checkbox-ot
            document.getElementById('sandboxMode').checked = !isEnabled;
            showToast('Hiba történt a beállítás mentése során', 'error');
        }
    })
    .catch(error => {
        console.error('Hiba:', error);
        // Hiba esetén visszaállítjuk a checkbox-ot
        document.getElementById('sandboxMode').checked = !isEnabled;
        showToast('Hiba történt a beállítás mentése során', 'error');
    });
}

function loadCurrentSandboxMode() {
    fetch('/api/get_sandbox_mode')
        .then(response => response.json())
        .then(data => {
            document.getElementById('sandboxMode').checked = data.enabled;
        })
        .catch(error => {
            console.error('Hiba a sandbox mode betöltése során:', error);
        });
}

// Toast értesítések megjelenítése
function showToast(message, type = 'info') {
    const toastClass = type === 'success' ? 'text-bg-success' : 
                      type === 'error' ? 'text-bg-danger' : 
                      type === 'warning' ? 'text-bg-warning' : 'text-bg-info';
                      
    const toastHtml = `
        <div class="toast ${toastClass}" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="3000">
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    // Toast container létrehozása, ha még nem létezik
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '1055';
        document.body.appendChild(toastContainer);
    }
    
    // Toast hozzáadása és megjelenítése
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toast = toastContainer.lastElementChild;
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Automatikus törlés a toast eltűnése után
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Státusz segédfüggvények
function getStatusIcon(returnCode) {
    switch(returnCode) {
        case 0: return '<i class="bi bi-check-circle-fill text-success"></i>';
        case null:
        case undefined: return '<i class="bi bi-hourglass-split text-warning"></i>';
        default: return '<i class="bi bi-x-circle-fill text-danger"></i>';
    }
}

function getStatusText(returnCode) {
    switch(returnCode) {
        case 0: return 'Sikeres';
        case null:
        case undefined: return 'Várakozás';
        default: return 'Sikertelen';
    }
}

function getStatusClass(returnCode) {
    switch(returnCode) {
        case 0: return 'alert-success';
        case null:
        case undefined: return 'alert-warning';
        default: return 'alert-danger';
    }
}

// Kilépés funkciók
function exitApplication() {
    if (!confirm('Biztos, hogy ki szeretnél lépni és leállítani a szervert?')) {
        return;
    }

    const exitBtn = document.getElementById('exitButton');
    if (exitBtn) {
        exitBtn.disabled = true;
        exitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Leállítás...';
    }

    showToast('Kilépés folyamatban, a szerver leáll.', 'info');

    fetch('/shutdown', { method: 'POST' })
        .then(() => {
            showToast('A szerver leállt, az ablak bezáródik.', 'success');
        })
        .catch((error) => {
            console.warn('Kilépés közbeni hiba:', error);
            showToast('Kilépés közben hiba történt. Ha az ablak nyitva marad, zárd be kézzel.', 'warning');
        })
        .finally(() => {
            setTimeout(function() {
                try {
                    window.open('', '_self');
                    window.close();
                } catch (e) {
                    console.warn('A böngésző nem engedte bezárni az ablakot:', e);
                }
                document.body.innerHTML = '<div class="text-center mt-5"><h1>Az alkalmazás bezárult</h1><p>Ha az ablak nyitva marad, zárd be kézzel ezt a böngészőfület.</p></div>';
            }, 350);
        });
}

function cancelExit() {
    // Visszatérés az első tabra
    const firstTab = document.querySelector('#download-tab');
    if (firstTab) {
        firstTab.click();
    }
}

// Tab-ok robotszámainak frissítése
function updateTabCounts() {
    try {
        // Futtatható robotok számának frissítése
        const runnableRobots = document.querySelectorAll('#repoContainer .branch-checkbox').length;
        const downloadTab = document.getElementById('download-tab');
        if (downloadTab) {
            downloadTab.innerHTML = '<i class="bi bi-robot"></i> Futtatható robotok (' + runnableRobots + ')';
        }

        // Letölthető robotok számának frissítése
        const availableRobots = document.querySelectorAll('#repoContainerAvailable .branch-checkbox').length;
        const availableTab = document.getElementById('available-tab');
        if (availableTab) {
            availableTab.innerHTML = '<i class="bi bi-download"></i> Letölthető robotok (' + availableRobots + ')';
        }

    } catch (error) {
        console.warn('Tab számok frissítése sikertelen:', error);
    }
}

// Oldal betöltésekor
document.addEventListener('DOMContentLoaded', function() {
    loadSettings();
    // updateRunButton(); // Futtatás tab megszűnt, törölhető
    updateTabCounts();

    // Fallback: Exit gomb eseménykezelője id alapján
    try {
        var exitBtn = document.getElementById('exitButton');
        if (exitBtn && typeof exitApplication === 'function') {
            exitBtn.addEventListener('click', function(ev){ ev.preventDefault(); exitApplication(); });
        }
    } catch(e) { /* ignore */ }
});

// Close the external results window when 'Visszatérés' is clicked in the modal
document.addEventListener('DOMContentLoaded', function() {
    const returnBtn = document.getElementById('resultsModalReturn');
    if (returnBtn) {
        returnBtn.addEventListener('click', function() {
            try {
                if (window._lastResultsWindow && !window._lastResultsWindow.closed) {
                    window._lastResultsWindow.close();
                }
            } catch (e) { /* ignore */ }
        });
    }
});

// Checkbox változásokra figyelés
document.addEventListener('change', function(e) {
    // futtatható tab megszűnt, robot-checkbox már nincs
});

// Eredmények kezelése
let currentPage = 1;
let currentSort = 'timestamp';
let currentOrder = 'desc';

function loadResults(page = 1, search = '', statusFilter = '', dateFilter = '') {
    currentPage = page;
    
    const params = new URLSearchParams({
        page: page,
        per_page: 10,
        search: search,
        status: statusFilter,
        date: dateFilter,
        sort: currentSort,
        order: currentOrder
    });
    
    fetch(`/api/results?${params}`)
    .then(response => response.json())
    .then(data => {
        displayResults(data.results);
        displayPagination(data.pagination);
        updateResultsInfo(data.pagination);
    })
    .catch(err => {
        console.error('Eredmények betöltése sikertelen:', err);
        document.getElementById('resultsTableBody').innerHTML = `
            <tr><td colspan="6" class="text-center text-danger py-4">
                <i class="bi bi-exclamation-triangle"></i> Hiba az eredmények betöltése során
            </td></tr>
        `;
    });
}

function displayResults(results) {
    const tbody = document.getElementById('resultsTableBody');
    if (results.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="6" class="text-center text-muted py-4">
                <i class="bi bi-inbox"></i> Nincs megjeleníthető eredmény
            </td></tr>
        `;
        return;
    }
    
    // Egyszerűsített megjelenítés HTML string concatenation-nal
    let htmlContent = '';
    results.forEach(result => {
        const statusBadge = result.status === 'success' 
            ? '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Sikeres</span>'
            : '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Sikertelen</span>';
            
        const typeBadge = result.type === 'bulk'
            ? '<span class="badge bg-info ms-1">Tömeges</span>'
            : '<span class="badge bg-secondary ms-1">Egyedi</span>';

        const resultsDisplay = result.results_dir 
            ? '<small class="text-muted">' + result.results_dir + '</small>' 
            : '-';

        // Use data-* attributes with encoded values to avoid inline JS quoting issues
        const encDir = encodeURIComponent(result.results_dir || '');
        const actionButton = result.results_dir
            ? '<button class="btn btn-sm btn-success" data-results-enc="' + encDir + '" onclick="openResults(decodeURIComponent(this.dataset.resultsEnc))" title="Megnyitás új ablakban"><i class="bi bi-eye"></i></button>'
            : '<button class="btn btn-sm btn-outline-secondary" data-result-id="' + (result.id || '') + '" onclick="viewDetails(this.dataset.resultId)" title="Részletek"><i class="bi bi-eye"></i></button>';
            
        htmlContent += '<tr>' +
            '<td>' + result.timestamp + typeBadge + '</td>' +
            '<td><i class="bi bi-github"></i> ' + result.repo + '</td>' +
            '<td><i class="bi bi-git"></i> ' + result.branch + '</td>' +
            '<td>' + statusBadge + '</td>' +
            '<td>' + resultsDisplay + '</td>' +
            '<td>' + actionButton + '</td>' +
            '</tr>';
    });
    
    tbody.innerHTML = htmlContent;

    // Re-initialize Bootstrap tooltips for new elements
    setTimeout(() => {
        const tList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tList.forEach(function (el) { try { new bootstrap.Tooltip(el); } catch(e) {} });
    }, 10);
}

function displayPagination(pagination) {
    const nav = document.getElementById('resultsPagination');
    if (pagination.pages <= 1) {
        nav.innerHTML = '';
        return;
    }
    
    let paginationHtml = '';
    
    // Előző oldal
    if (pagination.page > 1) {
        paginationHtml += `
            <li class="page-item">
                <a class="page-link" href="#" onclick="loadResults(${pagination.page - 1}, getCurrentSearch(), getCurrentStatusFilter(), getCurrentDateFilter())">Előző</a>
            </li>
        `;
    }
    
    // Oldalszámok
    const startPage = Math.max(1, pagination.page - 2);
    const endPage = Math.min(pagination.pages, pagination.page + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        paginationHtml += `
            <li class="page-item ${i === pagination.page ? 'active' : ''}">
                <a class="page-link" href="#" onclick="loadResults(${i}, getCurrentSearch(), getCurrentStatusFilter(), getCurrentDateFilter())">${i}</a>
            </li>
        `;
    }
    
    // Következő oldal
    if (pagination.page < pagination.pages) {
        paginationHtml += `
            <li class="page-item">
                <a class="page-link" href="#" onclick="loadResults(${pagination.page + 1}, getCurrentSearch(), getCurrentStatusFilter(), getCurrentDateFilter())">Következő</a>
            </li>
        `;
    }
    
    nav.innerHTML = paginationHtml;
}

function updateResultsInfo(pagination) {
    const info = document.getElementById('resultsInfo');
    const start = (pagination.page - 1) * pagination.per_page + 1;
    const end = Math.min(start + pagination.per_page - 1, pagination.total);
    info.textContent = `${start}-${end} / ${pagination.total} eredmény (${pagination.page}. oldal)`;
}

function getCurrentSearch() {
    return document.getElementById('searchResults').value;
}

function getCurrentStatusFilter() {
    return document.getElementById('statusFilter').value;
}

function getCurrentDateFilter() {
    return document.getElementById('dateFilter').value;
}

function refreshResults() {
    loadResults(1, getCurrentSearch(), getCurrentStatusFilter(), getCurrentDateFilter());
}

function sortResults(column) {
    if (currentSort === column) {
        currentOrder = currentOrder === 'desc' ? 'asc' : 'desc';
    } else {
        currentSort = column;
        currentOrder = 'desc';
    }
    
    // Rendezési indikátorok frissítése
    document.querySelectorAll('.sort-indicator').forEach(el => el.textContent = '');
    document.getElementById(`sort-${column}`).textContent = currentOrder === 'desc' ? '↓' : '↑';
    
    loadResults(currentPage, getCurrentSearch(), getCurrentStatusFilter(), getCurrentDateFilter());
}

function viewDetails(resultId) {
    alert(`Eredmény részletei: ID ${resultId}`);
}

function openResults(resultsDir) {
    try {
        const modalEl = document.getElementById('resultsModal');
        const iframe = document.getElementById('resultsModalIframe');
        if (!modalEl || !iframe) {
            alert(resultsDir);
            return;
        }

    // Megpróbáljuk a statikus URL-t használni, hogy a relatív assetek is működjenek
    // A backendünk a /results/<dir>/log.html útvonalon szolgálja ki a fájlt
    let dir = resultsDir || '';
        // Eltávolítjuk a vezető 'results/' vagy 'results\' elemet, ha benne van
        dir = dir.replace(/^results[\\/]+/, '');

        // Encode each path segment to avoid encoding slashes (which breaks the route)
        const segments = dir.split(/[\\/]+/).filter(Boolean);
        const encoded = segments.map(s => encodeURIComponent(s)).join('/');
        const staticUrl = `/results/${encoded}/log.html`;

    console.log('openResults: requesting staticUrl=', staticUrl, 'original resultsDir=', resultsDir);

        // Ha korábban megnyitott eredményablak létezik, zárjuk be azonnal (ne kérdezzünk)
        try {
            if (window._lastResultsWindow && !window._lastResultsWindow.closed) {
                window._lastResultsWindow.close();
            }
        } catch (e) { /* ignore */ }

        // Próbáljuk meg szinkron módon megnyitni a logot — ha sikerül, NE mutassuk a modalt (azonnal bezárjuk a kérdést)
        try {
            const immediate = window.open(staticUrl, '_blank');
            if (immediate) { window._lastResultsWindow = immediate; try { immediate.focus(); } catch(e){}; return; }
        } catch (e) { /* popup blocker or other */ }

        // Mutatjuk a modal-t azonnal és betöltünk egy rövid betöltés üzenetet,
        // most a log fájl elérési útját is megjelenítve a felhasználónak.
        const modal = new bootstrap.Modal(modalEl);
        // Link látható szövegét dekódoljuk, hogy ne jelenjenek meg %-kódok (pl. %C3)
        let visiblePath;
        try {
            visiblePath = decodeURIComponent(staticUrl);
        } catch (e) {
            visiblePath = staticUrl; // ha valamiért nem dekódolható, fallback
        }
        iframe.srcdoc = `
            <div style="padding:20px;font-family:Arial,Helvetica,sans-serif">
                Betöltés…<br>
                <small style="color:#666;">Log: <a href="${staticUrl}" target="_blank" rel="noopener">${visiblePath}</a></small>
            </div>`;
        modal.show();

        // Ellenőrizzük, hogy a fájl elérhető-e (200)
        // Közben a modal footerben található "Megnyitás új lapon" gombot beállítjuk
        const openBtn = document.getElementById('resultsModalOpenNew');
        if (openBtn) {
            openBtn.classList.add('d-none');
            openBtn.onclick = () => {
                const w = window.open(staticUrl, '_blank');
                window._lastResultsWindow = w;
                try { if (w) w.focus(); } catch(e) {}
                try { if (w) modal.hide(); } catch(e) { console.warn('Nem sikerült elrejteni a modalt:', e); }
            };
        }

        // Tároljuk el globálisan is, ha szükséges későbbi megnyitáshoz
        window._lastResultsStaticUrl = staticUrl;

        fetch(staticUrl, { method: 'GET' })
            .then(async resp => {
                if (resp.ok && resp.headers.get('content-type') && resp.headers.get('content-type').includes('text/html')) {
                    // Ha jó, állítsuk be az iframe src-ét, így a relatív hivatkozások is betöltődnek
                    iframe.src = staticUrl;
                    console.log('openResults: loaded ok, set iframe.src');

                    // Show the open-in-new-tab button
                    if (openBtn) {
                        openBtn.classList.remove('d-none');
                    }

                    // Try to open automatically in a new tab (may be blocked if not a user gesture)
                    try {
                        const newWin = window.open(staticUrl, '_blank');
                        if (newWin) {
                            window._lastResultsWindow = newWin;
                            try { newWin.focus(); } catch(e) {}
                            try { modal.hide(); } catch(e) { console.warn('Nem sikerült elrejteni a modalt:', e); }
                        }
                    } catch (e) {
                        // ignore popup blockers
                        console.warn('openResults: auto-open blocked or failed', e);
                    }
                } else {
                    // Ha nem OK, próbáljuk kiolvasni JSON hibát, vagy mutassunk hibát
                    let body = '';
                    try {
                        body = await resp.text();
                    } catch (e) {
                        console.error('openResults: failed to read response body', e);
                    }
                    try {
                        const j = JSON.parse(body || '{}');
                        iframe.srcdoc = `<div style="padding:20px;color:#a00">Hiba: ${j.error || 'Nem található'} (HTTP ${resp.status})</div>`;
                    } catch (e) {
                        iframe.srcdoc = `<div style="padding:20px;color:#a00">Nem sikerült betölteni a log.html (HTTP ${resp.status})</div>`;
                    }
                    console.warn('openResults: response not ok', resp.status, body);
                }
            })
            .catch(err => {
                console.error('Hiba a statikus log lekérésekor', err);
                iframe.srcdoc = `<div style="padding:20px;color:#a00">Hiba a log betöltésekor: ${String(err)}</div>`;
            });
    } catch (e) {
        console.error('openResults hiba:', e);
        alert(resultsDir);
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Keresés eseménykezelő
    const searchInput = document.getElementById('searchResults');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(() => {
                refreshResults();
            }, 500);
        });
    }
    
    // Szűrők eseménykezelői
    const statusFilter = document.getElementById('statusFilter');
    if (statusFilter) {
        statusFilter.addEventListener('change', refreshResults);
    }
    
    const dateFilter = document.getElementById('dateFilter');
    if (dateFilter) {
        dateFilter.addEventListener('change', refreshResults);
    }
    
    // Eredmények tab aktiválásakor betöltés
    const resultsTab = document.getElementById('results-tab');
    if (resultsTab) {
        resultsTab.addEventListener('shown.bs.tab', function() {
            loadResults();
        });
    }

    // Bootstrap tooltip inicializálás minden elemen, ahol data-bs-toggle="tooltip"
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Konzisztencia-ellenőrzés: csak azok maradjanak a "Futtatható" listában,
    // amelyek ténylegesen telepítve vannak (és van start.bat)
    try { reconcileRunnableWithInstalled(); } catch(e) {
        console.warn('reconcileRunnableWithInstalled hívás sikertelen', e);
    }
});

// Futtatható robotok lista frissítése (újra lekéri és frissíti a DOM-ot)
function refreshRunnableRobots() {
    fetch('/api/refresh')
        .then(r => r.json())
        .then(repos => {
            // Frissítsük a "Futtatható robotok" tab tartalmát
            updateRunnableRobotsTab(repos);
        })
        .catch(err => {
            console.warn('Futtatható robotok frissítése sikertelen:', err);
        });
}

// Futtatható robotok tab tartalmának frissítése
function updateRunnableRobotsTab(repos) {
    const container = document.getElementById('repoContainer');
    if (!container) return;

    // Lekérdezzük a ténylegesen telepített kulcsokat
    fetch('/api/debug/installed')
        .then(r => {
            if (!r.ok) throw new Error('installed debug endpoint not available');
            return r.json();
        })
        .then(data => {
            const installedSet = new Set(data.installed_keys || []);
            
            // Új tartalom építése - csak a telepített robotokkal
            let html = '';
            repos.forEach(repo => {
                const installedBranches = repo.branches ? repo.branches.filter(branch => 
                    installedSet.has(`${repo.name}|${branch}`)
                ) : [];
                
                if (installedBranches.length > 0) {
                    html += `
                        <div class="col-lg-6 col-xl-4 mb-4 repo-item" data-repo-name="${repo.name}">
                            <div class="card repo-card h-100">
                                <div class="card-header text-white">
                                    <h5 class="card-title mb-0">
                                        <i class="bi bi-github"></i>
                                        <a href="${repo.html_url}" target="_blank" class="text-white text-decoration-none">
                                            ${repo.name}
                                        </a>
                                    </h5>
                                    ${repo.updated_at ? `<small class="opacity-75">${repo.updated_at.slice(0,10)}</small>` : ''}
                                </div>
                                <div class="card-body">
                                    <p class="card-text">${repo.description || 'Nincs leírás'}</p>
                                    <h6 class="mt-3"><i class="bi bi-git"></i> Robotok:</h6>
                                    <div class="branches-container">
                    `;
                    
                    // Csak a telepített branch-ek
                    installedBranches.forEach(branch => {
                        html += `
                            <div class=\"branch-checkbox d-flex align-items-center\" style=\"margin-bottom: 5px;\">
                                    <!-- Checkbox removed: futtatható tab megszűnt -->
                                <div class=\"d-flex align-items-center me-2\">
                                    <i class=\"bi bi-house-fill text-primary me-2\" data-bs-toggle=\"tooltip\" data-bs-placement=\"top\" title=\"Feltöltve: ${repo.pushed_at_formatted || ''}\"></i>
                                    <i class=\"bi bi-trash text-danger\" 
                                       style=\"cursor: pointer;\" 
                                       onclick=\"deleteRunnableBranch('${repo.name}', '${branch}')\"
                                       data-bs-toggle=\"tooltip\" 
                                       data-bs-placement=\"top\" 
                                       title=\"Eltávolítás a futtathatók közül\"></i>
                                </div>
                                <label class=\"form-check-label mb-0 me-2\" for=\"branch-${repo.name}-${branch}\">${branch}</label>
                                <button class="btn btn-success btn-sm ms-2" title="Futtatás"
                                    data-repo="${repo.name}"
                                    data-branch="${branch}"
                                    onclick="executeSingleRobot(this, '${repo.name}', '${branch}', ROOT_FOLDER)">
                                    <i class="bi bi-play-fill"></i>
                                </button>
                            </div>
                        `;
                    });
                    
                    html += `
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }
            });
            
            container.innerHTML = html;
            
            // Tooltipek újrainicializálása
            const tooltipTriggerList = [].slice.call(container.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.forEach(function (tooltipTriggerEl) {
                try { new bootstrap.Tooltip(tooltipTriggerEl); } catch(e) {}
            });
            
            // Tab számok frissítése
            updateTabCounts();
        })
        .catch(err => {
            console.warn('Nem sikerült lekérni a telepített kulcsokat:', err);
        });
}

// Eltávolítja a felületről azokat a futtathatónak jelölt elemeket,
// amelyek nincsenek az Installed/SANDBOX könyvtárban start.bat-tal
function reconcileRunnableWithInstalled() {
    fetch('/api/debug/installed')
        .then(r => {
            if (!r.ok) throw new Error('installed debug endpoint not available');
            return r.json();
        })
        .then(data => {
            const set = new Set((data.installed_keys || []));
            const repoItems = document.querySelectorAll('.repo-item');
            repoItems.forEach(repoEl => {
                const repoName = repoEl.getAttribute('data-repo-name');
                const branches = repoEl.querySelectorAll('.branch-checkbox input.robot-checkbox');
                branches.forEach(inp => {
                    const r = inp.getAttribute('data-repo');
                    const b = inp.getAttribute('data-branch');
                    if (!set.has(`${r}|${b}`)) {
                        const wrapper = inp.closest('.branch-checkbox');
                        if (wrapper) wrapper.remove();
                    }
                });
                // Ha nem maradt branch, az egész kártyát is eltávolítjuk
                if (repoEl.querySelectorAll('.branch-checkbox').length === 0) {
                    repoEl.remove();
                }
            });
        })
        .catch(err => {
            // Ha nincs debug endpoint (régi szerver fut), nem csinálunk semmit
            console.info('Installed debug endpoint nem elérhető vagy hiba történt:', err.message);
        });
}

function deleteBranchFromRunnable(repoName, branchName) {
    fetch('/delete_runnable_branch', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            repo: repoName,
            branch: branchName
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Távolítsuk el a branch elemet a DOM-ból
            const branchElement = document.getElementById(`branch-${repoName}-${branchName}`).closest('.branch-checkbox');
            if (branchElement) {
                branchElement.remove();
            }
            
            // Ellenőrizzük, hogy van-e még branch a repository-ban
            const repoElement = document.querySelector(`.repo-item[data-repo-name="${repoName}"]`);
            if (repoElement) {
                const remainingBranches = repoElement.querySelectorAll('.branch-checkbox');
                if (remainingBranches.length === 0) {
                    // Ha nincs több branch, távolítsuk el az egész repository kártyát
                    repoElement.remove();
                }
            }
            
            // Frissítsük a futtatás gombot
            // updateRunButton(); // Futtatás tab megszűnt, törölhető
            
            console.log(`Branch ${repoName}/${branchName} eltávolítva a futtathatók közül`);

            // Frissítsük a Letölthető robotok tabot is
            try {
                addBranchToAvailableTab(repoName, branchName);
            } catch (e) {
                console.warn('Nem sikerült a Letölthető tabot frissíteni, oldal frissítés szükséges lehet.', e);
            }
        } else {
            alert('Hiba történt a branch eltávolításakor: ' + (data.error || 'Ismeretlen hiba'));
        }
    })
    .catch(error => {
        console.error('Hiba:', error);
        alert('Hiba történt a branch eltávolításakor.');
    });
}

// Hozzáadja a törölt futtatható branch-et a Letölthető robotok tabhoz (ha a repo kártya létezik)
function addBranchToAvailableTab(repoName, branchName) {
    const availablePane = document.getElementById('available-pane');
    if (!availablePane) return;
    const repoEl = availablePane.querySelector(`.repo-item-available[data-repo-name="${repoName}"]`);

    // Ha nincs repo kártya a Letölthető tabon, egyszerű fallback: teljes oldal frissítés
    if (!repoEl) {
        console.info('Repo kártya nem található a Letölthető tabon, teljes oldal frissítés...');
        // Soft reload csak ekkor
        window.location.reload();
        return;
    }

    const branchesContainer = repoEl.querySelector('.branches-container');
    if (!branchesContainer) return;

    const wrapperId = `branch-available-${repoName}-${branchName}`;
    if (repoEl.querySelector(`#${CSS.escape(wrapperId)}`)) {
        return;
    }

    // Új branch elem felépítése
    const wrapper = document.createElement('div');
    wrapper.className = 'branch-checkbox d-flex align-items-center';
    wrapper.id = wrapperId;

    const button = document.createElement('button');
    button.className = 'btn btn-warning btn-sm me-2 text-dark';
    button.type = 'button';
    button.title = 'Azonnali letöltés';
    button.innerHTML = '<i class="bi bi-download"></i>';
    button.addEventListener('click', function() {
        installRobot(repoName, branchName, button);
    });

    const labelSpan = document.createElement('span');
    labelSpan.textContent = branchName;

    wrapper.appendChild(button);
    wrapper.appendChild(labelSpan);
    branchesContainer.appendChild(wrapper);

    // Aktuális szűrők alkalmazása
    try { filterReposAvailable(); } catch(e) {}
    
    // Tab számok frissítése
    updateTabCounts();
}
// A branch név ikonját a HTML sablonban adjuk hozzá közvetlenül a label-ben

// Globális fallback: Letölthető robotok tab frissítése oldal reload-dal
function refreshAvailableRobots() {
    console.log('[WORKFLOW] Letölthető robotok tab frissítése (reload)');
    window.location.reload();
}

</script>
</body>
</html>
'''

    replacements = {
        '{primary_color}': primary_color,
        '{secondary_color}': secondary_color,
        '{tertiary_color}': tertiary_color,
        '{dark_color}': dark_color,
        '{light_color}': light_color,
        '{hover_color}': hover_color,
        '{rgba_color}': rgba_color,
    }
    for placeholder, value in replacements.items():
        css_template = css_template.replace(placeholder, value)

    return css_template


if __name__ == '__main__':
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    debug_env = os.environ.get('FLASK_DEBUG', '').strip().lower()
    debug_enabled = debug_env in {'1', 'true', 'on', 'yes'}
    print(f"[INFO] Flask szerver indítása host={host}, port={port}, debug={debug_enabled}")
    # Reloader kikapcsolása, mert a start.bat már felügyeli a folyamatot
    app.run(host=host, port=port, debug=debug_enabled, use_reloader=False)