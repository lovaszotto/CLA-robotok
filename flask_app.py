import requests

# --- Maintenance endpoint: Remove execution_results entries with missing results_dir ---
# (A Flask app példányosítás UTÁN kell lennie!)

# ...existing code...
# --- Szükséges importok ---
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
import pathlib
import base64
import zipfile
import io
from datetime import datetime
import logging

import html
import time
import threading
from datetime import datetime
import logging





# --- LOG OUTPUT DIR beállítása ---
PYTHON_EXECUTABLE = sys.executable  # Mindig a jelenlegi Python interpreter
def _get_backend_log_path():
    # Mindig a futtató könyvtár/server.log fájlt használjuk
    return os.path.join(os.getcwd(), 'server.log')

# Töröljük a server.log tartalmát a futás elején (új helyen)
try:
    backend_log_path = _get_backend_log_path()
    with open(backend_log_path, 'w', encoding='utf-8') as f:
        f.write('')
except Exception:
    pass

app = Flask(__name__)
# Csak WARNING szinttől logoljon a werkzeug (HTTP kérések ne menjenek a server.log-ba)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'cla-ssistant-secret')

# --- Running Robot process registry (for cancel/kill) ---
# Key format: run:<repo>:<branch>
RUNNING_ROBOT_PROCS_LOCK = threading.RLock()
RUNNING_ROBOT_PROCS: dict[str, subprocess.Popen] = {}

# Tracks user-requested cancellations by opKey so /api/execute can persist status='cancelled'
CANCELLED_RUN_OPS_LOCK = threading.RLock()
CANCELLED_RUN_OPS: dict[str, float] = {}


def _mark_run_cancelled(op_key: str):
    """Marks a running opKey as cancelled (best-effort) with a short TTL."""
    try:
        now = time.time()
        with CANCELLED_RUN_OPS_LOCK:
            CANCELLED_RUN_OPS[str(op_key)] = now
            # prune old markers (avoid unbounded growth)
            cutoff = now - 15 * 60
            for k, ts in list(CANCELLED_RUN_OPS.items()):
                if ts < cutoff:
                    try:
                        del CANCELLED_RUN_OPS[k]
                    except Exception:
                        pass
    except Exception:
        pass


def _clear_run_cancelled(op_key: str):
    try:
        with CANCELLED_RUN_OPS_LOCK:
            CANCELLED_RUN_OPS.pop(str(op_key), None)
    except Exception:
        pass


def _consume_run_cancelled(op_key: str) -> bool:
    """Returns True if the opKey was marked cancelled and consumes the marker."""
    try:
        with CANCELLED_RUN_OPS_LOCK:
            return CANCELLED_RUN_OPS.pop(str(op_key), None) is not None
    except Exception:
        return False


def _make_run_op_key(repo: str, branch: str) -> str:
    return f"run:{(repo or '').strip()}:{(branch or '').strip()}"


def _get_running_robot_proc(op_key: str) -> subprocess.Popen | None:
    try:
        with RUNNING_ROBOT_PROCS_LOCK:
            proc = RUNNING_ROBOT_PROCS.get(str(op_key))
        if proc is None:
            return None
        if proc.poll() is not None:
            # Clean up stale entries
            try:
                with RUNNING_ROBOT_PROCS_LOCK:
                    if RUNNING_ROBOT_PROCS.get(str(op_key)) is proc:
                        del RUNNING_ROBOT_PROCS[str(op_key)]
            except Exception:
                pass
            return None
        return proc
    except Exception:
        return None


def _kill_process_tree(proc: subprocess.Popen) -> tuple[bool, str]:
    """Best-effort kill of a subprocess (and its children on Windows)."""
    try:
        if proc is None:
            return False, 'No process'
        if proc.poll() is not None:
            return True, 'Already finished'

        pid = int(proc.pid)
        if os.name == 'nt':
            # Kill the whole tree (/T) forcefully (/F)
            try:
                r = subprocess.run(
                    ['taskkill', '/PID', str(pid), '/T', '/F'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                )
                if r.returncode == 0:
                    return True, 'taskkill ok'
                # If the process already exited, taskkill may return non-zero.
                if proc.poll() is not None:
                    return True, 'Process already finished'
                return False, (r.stdout or r.stderr or f'taskkill failed rc={r.returncode}').strip()
            except Exception as e:
                # Fallback: terminate single process
                try:
                    proc.terminate()
                    return True, f'terminate fallback ok ({e})'
                except Exception as e2:
                    return False, f'kill failed: {e2}'
        else:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            return True, 'terminated'
    except Exception as e:
        return False, str(e)

# --- /server-log végpont: log tartalom szövegként ---
@app.route('/server-log')
def server_log():
    """Visszaadja a server.log tartalmát szövegként (plain/text), mindig a futtató könyvtárból."""
    log_path = os.path.join(os.getcwd(), 'server.log')
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-cache'}
    except Exception as e:
        return f'Hiba a log olvasásakor: {e}', 500, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/api/clear-logs', methods=['POST'])
def api_clear_logs():
    """Törli az összes napló bejegyzést (server.log + futási eredmények)."""
    cleared = {
        'server_log': False,
        'results': False,
    }
    errors: list[str] = []

    # 1) server.log ürítése
    try:
        log_path = _get_backend_log_path()
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('')
        cleared['server_log'] = True
    except Exception as e:
        errors.append(f'server.log: {e}')

    # 2) execution_results ürítése (ugyanaz, mint /api/clear-results)
    try:
        global execution_results
        execution_results = []
        save_execution_results()
        cleared['results'] = True
    except Exception as e:
        errors.append(f'execution_results: {e}')

    status_code = 200 if not errors else 500
    return jsonify({'success': not errors, 'cleared': cleared, 'errors': errors}), status_code


@app.route('/api/clear-results-files', methods=['POST'])
def api_clear_results_files():
    """Törli a ./results mappa alatti összes futási/letöltési log könyvtárat.

    Csak a WORKSPACE-ben lévő "results" mappa azonnali alkönyvtárait törli (nem töröl fájlokat a gyökérben).
    """
    base_dir = os.path.abspath(os.path.join(os.getcwd(), 'results'))
    deleted: list[str] = []
    errors: list[str] = []

    if not os.path.isdir(base_dir):
        return jsonify({'success': True, 'deleted': [], 'errors': [], 'message': 'results mappa nem létezik'}), 200

    try:
        for name in os.listdir(base_dir):
            target = os.path.join(base_dir, name)
            if not os.path.isdir(target):
                continue
            # Biztonsági ellenőrzés: csak a base alatt törlünk
            try:
                if os.path.commonpath([base_dir, target]) != os.path.commonpath([base_dir]):
                    continue
            except Exception:
                if not os.path.abspath(target).startswith(os.path.abspath(base_dir)):
                    continue

            try:
                shutil.rmtree(target, onerror=_on_rm_error)
                deleted.append(name)
            except Exception as e:
                errors.append(f"{name}: {e}")
    except Exception as e:
        errors.append(str(e))

    # Opció: tartsuk szinkronban a tárolt eredménylistát is
    try:
        global execution_results
        execution_results = []
        save_execution_results()
    except Exception as e:
        errors.append(f"execution_results: {e}")

    status_code = 200 if not errors else 500
    return jsonify({'success': not errors, 'deleted': deleted, 'errors': errors}), status_code


PYTHON_EXECUTABLE = sys.executable or 'python'



# --- Logging beállítás: minden log menjen a server.log fájlba is, konzolra is ---
log_formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')
backend_log_path = _get_backend_log_path()
file_handler = logging.FileHandler(backend_log_path, encoding='utf-8')
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

    # Idempotens törlés: ha nincs meg a könyvtár, tekintsük sikeresnek.
    if not os.path.exists(target):
        return True, f'Könyvtár nem létezik: {target}'

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
    is_sandbox = get_sandbox_mode()
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
                    if is_sandbox:
                        # Sandbox módban csak klónozás történik (nincs telepito.bat, nincs .venv).
                        # Ilyenkor minden repo/branch mappa „telepítettként” jelenjen meg a Telepített tabon.
                        keys.add(f"{repo_name}|{branch_name}")
                    else:
                        # Normál módban csak akkor tekintjük futtathatónak, ha van .venv mappa (ready to run)
                        venv_folder = os.path.join(branch_path, '.venv')
                        if os.path.isdir(venv_folder):
                            keys.add(f"{repo_name}|{branch_name}")
    except Exception as e:
        logger.info(f"[INFO] Nem sikerült a futtatható kulcsokat felderíteni: {e}")
    return keys
def get_branches_for_repo(repo_name):
    """Lekéri egy repository branch-eit a git ls-remote segítségével."""
    try:
        # Sandbox módban is repo-specifikus branch listát szeretnénk.
        # Ezért nem adunk vissza hardcoded mock listát (az minden repóra ugyanaz lenne),
        # hanem best-effort megpróbáljuk a valós lekérdezést.
        if get_sandbox_mode():
            logger.info(f"[BRANCH-QUERY] Sandbox mód aktív, valós branch lekérdezés (best-effort): repo={repo_name}")
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
            # Sandbox módban ne jelenítsünk meg nem repohoz tartozó brancheket.
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


def _get_github_token() -> str | None:
    token = (os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or '').strip()
    if token:
        return token
    try:
        token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'github_token.txt')
        if os.path.exists(token_path):
            with open(token_path, 'r', encoding='utf-8', errors='replace') as f:
                token_file = (f.read() or '').strip()
            if token_file:
                os.environ.setdefault('GITHUB_TOKEN', token_file)
                return token_file
    except Exception as e:
        logger.info(f"[GITHUB-TOKEN] Token fájl olvasási hiba: {e}")
    return None


def _github_headers() -> dict:
    headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'CLA-ssistant'}
    token = _get_github_token()
    if token:
        headers['Authorization'] = f'token {token}'
    return headers


DEFAULT_GIT_URL_BASE = 'https://github.com/lovaszotto/'
DEFAULT_GITHUB_REPO_NAME = 'CLA-robotok'


def _variables_robot_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'variables.robot')


def _read_variables_robot_lines() -> list[str]:
    p = _variables_robot_path()
    with open(p, 'r', encoding='utf-8', errors='replace') as f:
        return f.readlines()


def _write_variables_robot_lines(lines: list[str]) -> None:
    p = _variables_robot_path()
    with open(p, 'w', encoding='utf-8', errors='replace') as f:
        f.writelines(lines)


def _get_robot_variable_value(var_name: str) -> str | None:
    """Kiolvassa a resources/variables.robot ${VAR} értékét (nyersen, sor vége nélkül)."""
    try:
        p = _variables_robot_path()
        if not os.path.exists(p):
            return None
        pattern = re.compile(r'^\$\{' + re.escape(var_name) + r'\}\s+(.+?)\s*$')
        for line in _read_variables_robot_lines():
            m = pattern.match(line.strip('\n'))
            if m:
                return (m.group(1) or '').strip()
    except Exception as e:
        logger.info(f"[VARIABLES] Olvasási hiba {var_name}: {e}")
    return None


def _set_robot_variable_value(var_name: str, value: str, *, insert_after_var: str | None = None) -> bool:
    """Beállítja a resources/variables.robot ${VAR} sorát. Ha nem létezik, beszúrja."""
    p = _variables_robot_path()
    if not os.path.exists(p):
        raise FileNotFoundError('Variables.robot fájl nem található')

    lines = _read_variables_robot_lines()
    modified = False
    insert_at = None

    for i, line in enumerate(lines):
        if line.strip().startswith(f'${{{var_name}}}'):
            # Igazodjunk a meglévő SANDBOX_MODE formátumhoz (fix spacing)
            lines[i] = re.sub(
                r'^\$\{' + re.escape(var_name) + r'\}\s+.*$',
                f'${{{var_name}}}         {value}',
                line.rstrip('\n')
            ) + '\n'
            modified = True
            break
        if insert_after_var and line.strip().startswith(f'${{{insert_after_var}}}'):
            insert_at = i + 1

    if not modified:
        if insert_at is None:
            # Legyen az elején, a Variables szekcióban
            insert_at = 0
            for i, line in enumerate(lines):
                if line.strip().lower().startswith('*** variables'):
                    insert_at = i + 1
                    break
        lines.insert(insert_at, f'${{{var_name}}}         {value}\n')
        modified = True

    if modified:
        _write_variables_robot_lines(lines)
    return modified


def _normalize_git_url_base(raw: str) -> str:
    s = (raw or '').strip()
    if not s:
        return DEFAULT_GIT_URL_BASE
    # Normalizáljuk: ha nincs a végén '/', tegyük hozzá (RF-ben ${GIT_URL_BASE}${REPO}.git)
    if not s.endswith('/'):
        s = s + '/'
    return s


def _derive_github_owner_from_base(git_url_base: str) -> str | None:
    s = (git_url_base or '').strip()
    if not s:
        return None

    # HTTPS: https://github.com/<owner>/
    m = re.search(r'github\.com/([^/]+)/?$', s)
    if m:
        return (m.group(1) or '').strip() or None

    # SSH: git@github.com:<owner>/
    m = re.search(r'github\.com:([^/]+)/?$', s)
    if m:
        return (m.group(1) or '').strip() or None

    return None


def _get_github_settings() -> dict:
    git_url_base = _normalize_git_url_base(_get_robot_variable_value('GIT_URL_BASE') or DEFAULT_GIT_URL_BASE)
    repo_name = (_get_robot_variable_value('GITHUB_REPO_NAME') or DEFAULT_GITHUB_REPO_NAME).strip()
    owner = _derive_github_owner_from_base(git_url_base) or 'lovaszotto'
    issues_url = f'https://github.com/{owner}/{repo_name}/issues'
    api_repo = f'{owner}/{repo_name}'
    return {
        'git_url_base': git_url_base,
        'repo_name': repo_name,
        'owner': owner,
        'issues_url': issues_url,
        'api_repo': api_repo,
    }


@app.route('/api/get_github_settings', methods=['GET'])
def api_get_github_settings():
    try:
        return jsonify({'success': True, 'settings': _get_github_settings()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/get_installed_version', methods=['GET'])
def api_get_installed_version():
    """Visszaadja a helyben telepített verziót a megadott branch-hez.

    A verziót a Robot Framework verzióellenőrzés ugyanitt tárolja:
    installed_versions/<branch>.txt
    """
    try:
        branch_raw = (request.args.get('branch') or '').strip()
        if not branch_raw:
            return jsonify({'success': False, 'error': 'Hiányzó robot paraméter'}), 400

        return jsonify({'success': True, 'branch': branch_raw, 'version': _read_installed_version(branch_raw)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _safe_installed_version_key(raw: str) -> str:
    # Basic path traversal védelem: csak biztonságos fájlnév komponenseket engedünk.
    return re.sub(r'[^A-Za-z0-9._-]+', '_', (raw or '').strip())


def _installed_versions_base_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'installed_versions')


def _installed_version_file_path(branch_raw: str) -> str:
    safe_branch = _safe_installed_version_key(branch_raw)
    return os.path.join(_installed_versions_base_dir(), f'{safe_branch}.txt')


def _read_installed_version(branch_raw: str) -> str:
    file_path = _installed_version_file_path(branch_raw)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return (f.read() or '').strip() or 'NONE'
        except Exception:
            return 'NONE'
    return 'NONE'


def _write_installed_version(branch_raw: str, version: str) -> None:
    base_dir = _installed_versions_base_dir()
    os.makedirs(base_dir, exist_ok=True)
    file_path = _installed_version_file_path(branch_raw)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write((version or '').strip() or 'NONE')


def _try_get_latest_release_tag_for_branch(repo_name: str, branch: str) -> str:
    """A telepítés pillanatában lekéri a branch legfrissebb GitHub release tag-jét.

    Ha nem elérhető (nincs token / nincs release / hiba), 'NONE'-t ad.
    """
    try:
        repos = get_repository_data() or []
        repo_obj = next(
            (r for r in repos if (r.get('name') or '').strip().lower() == (repo_name or '').strip().lower()),
            None,
        )
        if not repo_obj:
            return 'NONE'

        meta_map = get_latest_release_by_branch(repo_obj, [branch]) or {}
        meta = meta_map.get(branch) or {}
        return (meta.get('tag') or '').strip() or 'NONE'
    except Exception as e:
        logger.warning(f"[INSTALL] Nem sikerült release tag-et lekérni: repo='{repo_name}', branch='{branch}', err={e}")
        return 'NONE'


@app.route('/api/set_github_settings', methods=['POST'])
def api_set_github_settings():
    """Mentjük a GitHub beállításokat és szinkronizáljuk a resources/variables.robot fájlba.

    Támogatja a részleges frissítést is:
    - ha egy mező nincs megadva (vagy üres), megtartjuk a korábbi értéket.
    """
    try:
        data = request.get_json(silent=True) or {}

        current = _get_github_settings()

        if 'git_url_base' in data and (data.get('git_url_base') or '').strip():
            git_url_base = _normalize_git_url_base(data.get('git_url_base') or '')
        else:
            git_url_base = _normalize_git_url_base(current.get('git_url_base') or DEFAULT_GIT_URL_BASE)

        if 'repo_name' in data and (data.get('repo_name') or '').strip():
            repo_name = (data.get('repo_name') or '').strip()
        else:
            repo_name = (current.get('repo_name') or DEFAULT_GITHUB_REPO_NAME).strip() or DEFAULT_GITHUB_REPO_NAME

        # Szinkron: variables.robot
        _set_robot_variable_value('GIT_URL_BASE', git_url_base)
        _set_robot_variable_value('GITHUB_REPO_NAME', repo_name, insert_after_var='GIT_URL_BASE')

        return jsonify({'success': True, 'settings': _get_github_settings()})
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/test_git_repo', methods=['POST'])
def api_test_git_repo():
    """Ellenőrzi, hogy a megadott GIT_URL_BASE + repo_name összeállításból valóban elérhető-e a git.

    Megvalósítás: `git ls-remote --heads <url>`
    """
    try:
        data = request.get_json(silent=True) or {}
        target = (data.get('target') or '').strip()  # 'git_url_base' vagy 'repo_name'
        raw_base = (data.get('git_url_base') or '').strip()
        raw_repo = (data.get('repo_name') or '').strip()

        # Ha csak az egyik mezőt tesztelik, a másikat vegyük a mentett beállításból (fallback).
        saved = _get_github_settings()
        base = _normalize_git_url_base(raw_base or saved.get('git_url_base') or DEFAULT_GIT_URL_BASE)
        repo_name = (raw_repo or saved.get('repo_name') or DEFAULT_GITHUB_REPO_NAME).strip()

        if target == 'git_url_base' and not raw_base:
            return jsonify({'ok': False, 'error': 'Hiányzó GIT_URL_BASE'}), 400
        if target == 'repo_name' and not raw_repo:
            return jsonify({'ok': False, 'error': 'Hiányzó repo_name'}), 400

        if not base:
            return jsonify({'ok': False, 'error': 'Hiányzó GIT_URL_BASE'}), 400
        if not repo_name:
            return jsonify({'ok': False, 'error': 'Hiányzó repo_name'}), 400

        # Minimális validáció (parancsinjekt ellen védelem: subprocess listás, de whitespace-t tiltunk)
        if any(ch.isspace() for ch in base) or any(ch.isspace() for ch in repo_name):
            return jsonify({'ok': False, 'error': 'A mezők nem tartalmazhatnak szóközt'}), 400

        # URL összeállítása
        url = f"{base}{repo_name}.git"

        # Git parancs futtatása
        try:
            result = subprocess.run(
                ['git', 'ls-remote', '--heads', url],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=20
            )
        except FileNotFoundError:
            return jsonify({'ok': False, 'url': url, 'error': 'A git parancs nem található (nincs telepítve vagy nincs PATH-ban).'}), 200
        except subprocess.TimeoutExpired:
            return jsonify({'ok': False, 'url': url, 'error': 'Időtúllépés (timeout) a git elérés teszt során.'}), 200

        ok = (result.returncode == 0)
        stderr = (result.stderr or '').strip()
        stdout = (result.stdout or '').strip()
        if ok:
            return jsonify({'ok': True, 'url': url, 'returncode': result.returncode})

        # Tipikus okok: 128 (repo nincs, nincs jog, network)
        details = stderr or stdout or f'returncode={result.returncode}'
        return jsonify({
            'ok': False,
            'url': url,
            'returncode': result.returncode,
            'error': details
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/list_github_repos', methods=['GET'])
def api_list_github_repos():
    """Visszaadja a megadott GitHub felhasználó (owner) repository-jait.

    Token esetén megpróbáljuk a /user/repos végpontot is (privát repo-k miatt),
    de csak akkor lesznek elérhetők, ha a token jogosult és a user megegyezik.
    """
    try:
        owner = (request.args.get('owner') or '').strip()
        if not owner:
            return jsonify({'success': False, 'error': 'Hiányzó owner paraméter'}), 400

        # Minimális sanity
        if any(ch.isspace() for ch in owner):
            return jsonify({'success': False, 'error': 'Érvénytelen owner (szóköz nem megengedett)'}), 400

        token = _get_github_token()
        headers = _github_headers()
        repos: list[dict] = []
        warning = ''
        include_branch_counts = str(request.args.get('include_branch_counts') or '').strip().lower() in ('1', 'true', 'yes', 'y')

        def _simplify(repo: dict) -> dict:
            return {
                'name': repo.get('name'),
                'full_name': repo.get('full_name'),
                'private': bool(repo.get('private')),
                'default_branch': repo.get('default_branch'),
                'html_url': repo.get('html_url'),
                'clone_url': repo.get('clone_url'),
                'ssh_url': repo.get('ssh_url'),
                'updated_at': repo.get('updated_at'),
            }

        def _get_branches_count(repo_name: str) -> int | None:
            """Gyors branch-szám becslés GitHub Link header alapján.

            Trükk: per_page=1 mellett a 'last' oldal száma megegyezik a branch-ok számával.
            """
            if not repo_name:
                return None
            url = f'https://api.github.com/repos/{owner}/{repo_name}/branches?per_page=1&page=1'
            try:
                resp = requests.get(url, headers=headers, timeout=15)
            except Exception:
                return None
            if resp.status_code != 200:
                return None
            link = resp.headers.get('Link') or ''
            if 'rel="last"' in link:
                for part in link.split(','):
                    if 'rel="last"' not in part:
                        continue
                    m = re.search(r'[?&]page=(\d+)', part)
                    if m:
                        try:
                            return int(m.group(1))
                        except Exception:
                            return None
            # Ha nincs paging, akkor 0 vagy 1 elem jön vissza
            try:
                data = resp.json() or []
                return int(len(data))
            except Exception:
                return None

        if token:
            # Privát repo-khoz: /user/repos (ha a token user-je azonos, és van jogosultság)
            user_repos_url = 'https://api.github.com/user/repos?per_page=100&affiliation=owner&sort=updated'
            rr = requests.get(user_repos_url, headers=headers, timeout=15)
            if rr.status_code == 200:
                all_repos = rr.json() or []
                repos = [_simplify(r) for r in all_repos if (r.get('owner') or {}).get('login') == owner]
                if not repos:
                    # Token megvan, de lehet más user; fallback a public listára
                    warning = 'A token nem ehhez a felhasználóhoz tartozik, csak public repo-k látszanak.'
                else:
                    repos.sort(key=lambda x: (x.get('updated_at') or ''), reverse=True)
                    return jsonify({'success': True, 'owner': owner, 'repos': repos, 'warning': warning})
            else:
                warning = f'Nem sikerült a privát repo-k lekérése (status={rr.status_code}), csak public repo-k látszanak.'

        # Public repo lista: /users/{owner}/repos
        public_url = f'https://api.github.com/users/{owner}/repos?per_page=100&sort=updated'
        pr = requests.get(public_url, headers=headers, timeout=15)
        if pr.status_code != 200:
            detail = ''
            try:
                j = pr.json() or {}
                detail = j.get('message') or str(j)
            except Exception:
                detail = (pr.text or '').strip()
            return jsonify({'success': False, 'error': f'GitHub API hiba (status={pr.status_code})', 'details': detail}), 502

        repos_raw = pr.json() or []
        repos = [_simplify(r) for r in repos_raw]
        repos.sort(key=lambda x: (x.get('updated_at') or ''), reverse=True)

        if include_branch_counts and repos:
            # Ne csináljunk 100+ extra HTTP hívást véletlenül.
            max_repos = 40
            if len(repos) > max_repos:
                warning = (warning + ' ' if warning else '') + f'Robot szám csak az első {max_repos} repóra lett lekérdezve.'
            for i, repo in enumerate(repos[:max_repos]):
                name = (repo.get('name') or '').strip()
                repo['branches_count'] = _get_branches_count(name)
            for repo in repos[max_repos:]:
                repo['branches_count'] = None

        return jsonify({'success': True, 'owner': owner, 'repos': repos, 'warning': warning})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/get_repo_branches_tags', methods=['GET'])
def api_get_repo_branches_tags():
    """Repo branch-ek + tag-ek + release meta (cím, dátum, info/body)."""
    try:
        owner = (request.args.get('owner') or '').strip()
        repo = (request.args.get('repo') or '').strip()
        branch = (request.args.get('branch') or '').strip()
        if not owner or not repo:
            return jsonify({'success': False, 'error': 'Hiányzó owner vagy repo paraméter'}), 400
        if any(ch.isspace() for ch in owner) or any(ch.isspace() for ch in repo):
            return jsonify({'success': False, 'error': 'Érvénytelen paraméter (szóköz nem megengedett)'}), 400
        if branch and any(ch.isspace() for ch in branch):
            return jsonify({'success': False, 'error': 'Érvénytelen robot paraméter (szóköz nem megengedett)'}), 400

        headers = _github_headers()

        # Branch-ek
        branches_url = f'https://api.github.com/repos/{owner}/{repo}/branches?per_page=100'
        br = requests.get(branches_url, headers=headers, timeout=15)
        if br.status_code != 200:
            detail = ''
            try:
                j = br.json() or {}
                detail = j.get('message') or str(j)
            except Exception:
                detail = (br.text or '').strip()
            return jsonify({'success': False, 'error': f'Robot lekérés sikertelen (status={br.status_code})', 'details': detail}), 502
        branches_raw = br.json() or []
        branches = [b.get('name') for b in branches_raw if b.get('name')]

        tags: list[dict] = []
        tags_note = ''

        # Releases (branch szerinti szűréshez is ezt használjuk)
        releases_url = f'https://api.github.com/repos/{owner}/{repo}/releases?per_page=100'
        rr = requests.get(releases_url, headers=headers, timeout=15)
        rels = rr.json() if rr.status_code == 200 else []

        if branch:
            # Branch szerint: csak az adott branch-hez célzott release-eket mutatjuk.
            # Itt a release "tag_name" a tag, a meta a release mezőkből jön.
            if rr.status_code != 200:
                # Token nélkül gyakran rate limit; ne bukjunk, csak jelezzünk
                tags_note = 'Megjegyzés: release lista nem elérhető (nincs token / rate limit).'
            else:
                for r in (rels or []):
                    if (r.get('target_commitish') or '').strip() != branch:
                        continue
                    tag = (r.get('tag_name') or '').strip()
                    if not tag:
                        continue
                    tags.append({
                        'tag': tag,
                        'title': (r.get('name') or '').strip(),
                        'date': (r.get('published_at') or '').strip() or (r.get('created_at') or '').strip(),
                        'info': (r.get('body') or '').strip(),
                        'html_url': (r.get('html_url') or '').strip(),
                    })
                if not tags:
                    tags_note = 'Nincs release/tag információ ehhez a robothoz.'
        else:
            # Összes tag: Git tag lista + release meta (ha van)
            tags_url = f'https://api.github.com/repos/{owner}/{repo}/tags?per_page=100'
            tr = requests.get(tags_url, headers=headers, timeout=15)
            if tr.status_code != 200:
                detail = ''
                try:
                    j = tr.json() or {}
                    detail = j.get('message') or str(j)
                except Exception:
                    detail = (tr.text or '').strip()
                return jsonify({'success': False, 'error': f'Tag lekérés sikertelen (status={tr.status_code})', 'details': detail}), 502
            tags_raw = tr.json() or []
            tag_names = [t.get('name') for t in tags_raw if t.get('name')]

            releases_map: dict[str, dict] = {}
            if rr.status_code == 200:
                for r in (rels or []):
                    tag = (r.get('tag_name') or '').strip()
                    if not tag:
                        continue
                    releases_map[tag] = {
                        'title': (r.get('name') or '').strip(),
                        'date': (r.get('published_at') or '').strip() or (r.get('created_at') or '').strip(),
                        'info': (r.get('body') or '').strip(),
                        'html_url': (r.get('html_url') or '').strip(),
                    }
            else:
                releases_map = {}

            for t in tag_names:
                meta = releases_map.get(t) or {}
                tags.append({
                    'tag': t,
                    'title': meta.get('title') or '',
                    'date': meta.get('date') or '',
                    'info': meta.get('info') or '',
                    'html_url': meta.get('html_url') or '',
                })

        # Próbáljunk release dátum szerint rendezni (ha van), egyébként tag név szerint
        def _sort_key(x: dict):
            return (x.get('date') or '', x.get('tag') or '')

        tags.sort(key=_sort_key, reverse=True)

        if not branch:
            if tag_names and not releases_map:
                tags_note = 'Megjegyzés: release meta nem elérhető (nincs token / rate limit / nincs release a tagekhez).'

        return jsonify({
            'success': True,
            'owner': owner,
            'repo': repo,
            'branch': branch,
            'branches': branches,
            'tags': tags,
            'tags_note': tags_note,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _parse_owner_repo(repo_obj: dict) -> tuple[str, str]:
    full_name = (repo_obj.get('full_name') or '').strip()
    if '/' in full_name:
        owner, name = full_name.split('/', 1)
        return owner, name
    tags_url_val = repo_obj.get('tags_url') or ''
    m = re.search(r'/repos/([^/]+)/([^/]+)/tags', tags_url_val)
    if m:
        return m.group(1), m.group(2)
    return 'lovaszotto', (repo_obj.get('name') or '').strip()


def _parse_github_iso_datetime(dt_raw: str) -> datetime | None:
    try:
        s = (dt_raw or '').strip()
        if not s:
            return None
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None


def get_latest_release_by_branch(repo_obj: dict, branches: list[str]) -> dict[str, dict[str, str]]:
    """Best-effort: GitHub releases alapján branch-enként a legfrissebb release meta.

    Visszaad: { "<branch>": {"tag": "v1.2.3", "title": "Release name", "date": "2026-01-28T...Z" } }
    Token hiányában/rate limit esetén üres dict.
    """
    if not branches:
        return {}

    # Token nélkül gyorsan rate limitbe futhatunk, ezért csak tokennel kérdezünk.
    if not _get_github_token():
        return {}

    owner, api_repo_name = _parse_owner_repo(repo_obj)
    if not owner or not api_repo_name:
        return {}

    releases_url = f"https://api.github.com/repos/{owner}/{api_repo_name}/releases?per_page=100"
    try:
        rr = requests.get(releases_url, headers=_github_headers(), timeout=15)
        if rr.status_code != 200:
            logger.info(f"[RELEASE-BY-BRANCH] lekérés sikertelen: {releases_url} status={rr.status_code}")
            return {}

        # branch -> (datetime, meta)
        best: dict[str, tuple[datetime, dict[str, str]]] = {}
        branch_set = set(branches)
        for rel in (rr.json() or []):
            target = (rel.get('target_commitish') or '').strip()
            if target not in branch_set:
                continue
            tag_name = (rel.get('tag_name') or '').strip()
            title = (rel.get('name') or '').strip()
            date_raw = (rel.get('published_at') or rel.get('created_at') or '').strip()
            dt = _parse_github_iso_datetime(date_raw) or datetime.min
            meta = {
                'tag': tag_name,
                'title': title,
                'date': date_raw,
            }
            prev = best.get(target)
            if prev is None or dt > prev[0]:
                best[target] = (dt, meta)

        return {b: meta for b, (_dt, meta) in best.items()}
    except Exception as e:
        logger.info(f"[RELEASE-BY-BRANCH] Hiba a release-ek lekérésekor: {owner}/{api_repo_name}: {e}")
        return {}


@app.route('/api/get_github_token_status', methods=['GET'])
def api_get_github_token_status():
    """Token státusz visszaadása a UI-nak (a token értékét nem adjuk ki)."""
    try:
        token_from_env = (os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or '').strip()
        token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'github_token.txt')
        token_from_file = ''
        if os.path.exists(token_path):
            try:
                with open(token_path, 'r', encoding='utf-8', errors='replace') as f:
                    token_from_file = (f.read() or '').strip()
            except Exception:
                token_from_file = ''

        token = token_from_env or token_from_file
        hint = ''
        if token:
            hint = ('…' + token[-4:]) if len(token) >= 4 else '…'
        source = 'env' if token_from_env else ('file' if token_from_file else 'none')
        return jsonify({'present': bool(token), 'hint': hint, 'source': source})
    except Exception as e:
        logger.info(f"[GITHUB-TOKEN] Státusz lekérés hiba: {e}")
        return jsonify({'present': False, 'hint': '', 'source': 'error'})


@app.route('/api/set_github_token', methods=['POST'])
def api_set_github_token():
    """GitHub token mentése UI-ból.

    - Mentés: github_token.txt (NE commitold; .gitignore-ban kell legyen)
    - Futó processen belül: os.environ['GITHUB_TOKEN']
    """
    try:
        data = request.get_json(silent=True) or {}
        clear = bool(data.get('clear'))
        token = (data.get('token') or '').strip()
        token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'github_token.txt')

        if clear:
            try:
                if os.path.exists(token_path):
                    os.remove(token_path)
            except Exception as e:
                logger.info(f"[GITHUB-TOKEN] Token fájl törlés hiba: {e}")
                return jsonify({'success': False, 'error': f'Nem sikerült törölni a token fájlt: {e}'}), 500
            os.environ.pop('GITHUB_TOKEN', None)
            os.environ.pop('GH_TOKEN', None)
            return jsonify({'success': True, 'cleared': True})

        if not token:
            return jsonify({'success': False, 'error': 'Hiányzó token'}), 400

        # Ne logoljuk a token értékét.
        try:
            with open(token_path, 'w', encoding='utf-8', errors='replace') as f:
                f.write(token + '\n')
        except Exception as e:
            logger.info(f"[GITHUB-TOKEN] Token fájl írás hiba: {e}")
            return jsonify({'success': False, 'error': f'Nem sikerült menteni a token fájlt: {e}'}), 500

        os.environ['GITHUB_TOKEN'] = token
        return jsonify({'success': True, 'saved': True})
    except Exception as e:
        logger.info(f"[GITHUB-TOKEN] Token mentés hiba: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/create_github_issue', methods=['POST'])
def api_create_github_issue():
    """GitHub Issue létrehozása tokennel (API-n keresztül).

    Megjegyzés: a böngészős (web UI) bejelentkezést tokennel nem automatizáljuk;
    helyette itt hozunk létre issue-t.
    """
    token = _get_github_token()
    if not token:
        return jsonify({'success': False, 'error': 'Hiányzó GitHub token (Beállítások -> GitHub token)'}), 403

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    body = (data.get('body') or '').strip()
    labels = data.get('labels')

    if not title:
        return jsonify({'success': False, 'error': 'Hiányzó cím (title)'}), 400

    payload: dict = {'title': title}
    if body:
        payload['body'] = body

    if isinstance(labels, list):
        cleaned = [str(x).strip() for x in labels if str(x).strip()]
        if cleaned:
            payload['labels'] = cleaned

    settings = _get_github_settings()
    owner = settings.get('owner') or 'lovaszotto'
    repo_name = settings.get('repo_name') or DEFAULT_GITHUB_REPO_NAME
    url = f'https://api.github.com/repos/{owner}/{repo_name}/issues'
    try:
        resp = requests.post(url, headers=_github_headers(), json=payload, timeout=20)
        if resp.status_code in (200, 201):
            j = resp.json() or {}
            return jsonify({
                'success': True,
                'number': j.get('number'),
                'html_url': j.get('html_url'),
                'title': j.get('title'),
                'repo': f"{owner}/{repo_name}",
            })

        detail = ''
        try:
            j = resp.json() or {}
            # GitHub tipikusan {'message': '...', 'errors': [...]}
            detail = j.get('message') or str(j)
        except Exception:
            detail = (resp.text or '').strip()

        return jsonify({
            'success': False,
            'error': f'GitHub API hiba (status={resp.status_code})',
            'details': detail
        }), 502
    except Exception as e:
        logger.info(f"[GITHUB-ISSUE] Létrehozás hiba: {e}")
        return jsonify({'success': False, 'error': 'Issue létrehozás hiba', 'details': str(e)}), 500


@app.route('/api/create_github_release', methods=['POST'])
def api_create_github_release():
    """GitHub Release létrehozása (tag + cím + release notes) tokennel.

    Várt payload (JSON):
      - repo_full_name (opcionális): "owner/repo"
      - repo_url (opcionális): "https://github.com/owner/repo"
      - repo (opcionális): "repo"
      - branch (opcionális): target_commitish
      - tag_name (kötelező)
      - release_title (opcionális)
      - release_notes (opcionális)
    """
    token = _get_github_token()
    if not token:
        return jsonify({'success': False, 'error': 'Hiányzó GitHub token (Beállítások -> GitHub token)'}), 403

    data = request.get_json(silent=True) or {}
    repo_full_name = (data.get('repo_full_name') or '').strip()
    repo_url = (data.get('repo_url') or '').strip()
    repo_name = (data.get('repo') or data.get('repo_name') or '').strip()
    branch = (data.get('branch') or '').strip()
    tag_name = (data.get('tag_name') or '').strip()
    release_title = (data.get('release_title') or '').strip()
    release_notes = (data.get('release_notes') or '')

    if not tag_name:
        return jsonify({'success': False, 'error': 'Hiányzó TagName (tag_name)'}), 400

    def _parse_owner_repo_from_inputs(full_name: str, url: str, name_only: str) -> tuple[str, str]:
        full_name = (full_name or '').strip()
        if '/' in full_name:
            o, r = full_name.split('/', 1)
            return (o.strip(), r.strip())
        url = (url or '').strip()
        m = re.search(r'github\.com/([^/]+)/([^/]+)', url, flags=re.IGNORECASE)
        if m:
            return (m.group(1).strip(), m.group(2).strip().replace('.git', ''))
        # Fallback: settings owner + name-only (ha adott)
        settings = _get_github_settings()
        owner = (settings.get('owner') or 'lovaszotto').strip()
        return (owner, (name_only or '').strip())

    owner, repo = _parse_owner_repo_from_inputs(repo_full_name, repo_url, repo_name)
    if not owner or not repo:
        return jsonify({'success': False, 'error': 'Hiányzó vagy érvénytelen repo azonosító (repo_full_name/repo_url/repo).'}), 400

    payload: dict = {
        'tag_name': tag_name,
        'name': release_title or tag_name,
        'body': release_notes or '',
        'draft': False,
        'prerelease': False,
    }
    if branch:
        payload['target_commitish'] = branch

    url = f'https://api.github.com/repos/{owner}/{repo}/releases'
    try:
        resp = requests.post(url, headers=_github_headers(), json=payload, timeout=30)
        if resp.status_code in (200, 201):
            j = resp.json() or {}
            # Fejlesztői/sandbox módban: új kiadás után ezt tekintsük az utoljára letöltött (telepített) verziónak.
            try:
                if get_sandbox_mode() and branch:
                    _write_installed_version(branch, str(j.get('tag_name') or tag_name))
            except Exception as e:
                logger.info(f"[GITHUB-RELEASE] installed_version mentés hiba: {e}")
            return jsonify({
                'success': True,
                'id': j.get('id'),
                'tag_name': j.get('tag_name') or tag_name,
                'name': j.get('name') or (release_title or tag_name),
                'html_url': j.get('html_url'),
                'repo': f'{owner}/{repo}',
            })

        detail = ''
        try:
            j = resp.json() or {}
            detail = j.get('message') or str(j)
        except Exception:
            detail = (resp.text or '').strip()

        return jsonify({
            'success': False,
            'error': f'GitHub API hiba (status={resp.status_code})',
            'details': detail,
        }), 502
    except Exception as e:
        logger.info(f"[GITHUB-RELEASE] Létrehozás hiba: {e}")
        return jsonify({'success': False, 'error': 'Release létrehozás hiba', 'details': str(e)}), 500


def _safe_path_basename(path: str) -> str:
    try:
        return pathlib.Path(path).name
    except Exception:
        return os.path.basename(os.path.normpath(path or ''))


def _write_fallback_html(target_path: str, title: str, content_text: str):
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    safe_title = html.escape(title or '')
    safe_body = html.escape(content_text or '')
    html_text = (
        "<!doctype html>\n"
        "<html><head><meta charset='utf-8'>"
        f"<title>{safe_title}</title>"
        "</head><body>"
        f"<h3>{safe_title}</h3>"
        "<pre style='white-space:pre-wrap'>"
        f"{safe_body}"
        "</pre></body></html>\n"
    )
    with open(target_path, 'w', encoding='utf-8', errors='replace') as f:
        f.write(html_text)


def _ensure_run_issue_artifacts(results_dir_abs: str, stdout_text: str, stderr_text: str) -> dict:
    """Előállítja az issue-hoz kért futási fájlokat.

    - r_log.html: a Robot log.html másolata (fallback: stdout/stderr HTML)
    - r_report.html: a Robot report.html másolata (fallback: stdout/stderr HTML)
    - r_riport.html: magyar név alias a r_report.html-hez

    If Robot did not produce them, create small fallback HTML files.
    """
    results_dir_abs = results_dir_abs or ''
    log_src = os.path.join(results_dir_abs, 'log.html')
    report_src = os.path.join(results_dir_abs, 'report.html')
    r_log_path = os.path.join(results_dir_abs, 'r_log.html')
    r_report_path = os.path.join(results_dir_abs, 'r_report.html')
    r_riport_path = os.path.join(results_dir_abs, 'r_riport.html')

    try:
        if os.path.exists(log_src):
            shutil.copyfile(log_src, r_log_path)
        else:
            _write_fallback_html(
                r_log_path,
                'Robot log (fallback)',
                (stdout_text or '') + ("\n\n[stderr]\n" + (stderr_text or '') if stderr_text else ''),
            )
    except Exception as e:
        logger.info(f"[RUN][ISSUE] Nem sikerült r_log.html előállítása: {e}")

    try:
        if os.path.exists(report_src):
            shutil.copyfile(report_src, r_report_path)
        else:
            _write_fallback_html(
                r_report_path,
                'Robot report (fallback)',
                (stdout_text or '') + ("\n\n[stderr]\n" + (stderr_text or '') if stderr_text else ''),
            )
    except Exception as e:
        logger.info(f"[RUN][ISSUE] Nem sikerült r_report.html előállítása: {e}")

    # Magyar alias: sok helyen r_riport.html néven várják
    try:
        if os.path.exists(r_report_path):
            shutil.copyfile(r_report_path, r_riport_path)
    except Exception as e:
        logger.info(f"[RUN][ISSUE] Nem sikerült r_riport.html előállítása: {e}")

    return {
        'r_log_path': r_log_path,
        'r_report_path': r_report_path,
        'r_riport_path': r_riport_path,
        'has_r_log': os.path.exists(r_log_path),
        'has_r_report': os.path.exists(r_report_path),
        'has_r_riport': os.path.exists(r_riport_path),
    }


def _github_create_issue(owner: str, repo_name: str, title: str, body: str, labels: list[str] | None = None) -> dict:
    url = f'https://api.github.com/repos/{owner}/{repo_name}/issues'
    payload: dict = {'title': title}
    if body:
        payload['body'] = body
    if labels:
        cleaned = [str(x).strip() for x in labels if str(x).strip()]
        if cleaned:
            payload['labels'] = cleaned
    resp = requests.post(url, headers=_github_headers(), json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"GitHub create issue failed (status={resp.status_code}): {(resp.text or '').strip()}")
    return resp.json() or {}


def _github_close_issue(owner: str, repo_name: str, issue_number: int) -> dict:
    url = f'https://api.github.com/repos/{owner}/{repo_name}/issues/{issue_number}'
    resp = requests.patch(url, headers=_github_headers(), json={'state': 'closed'}, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"GitHub close issue failed (status={resp.status_code}): {(resp.text or '').strip()}")
    return resp.json() or {}


def _github_create_issue_comment(owner: str, repo_name: str, issue_number: int, body: str) -> dict:
    url = f'https://api.github.com/repos/{owner}/{repo_name}/issues/{issue_number}/comments'
    resp = requests.post(url, headers=_github_headers(), json={'body': body}, timeout=20)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"GitHub create comment failed (status={resp.status_code}): {(resp.text or '').strip()}")
    return resp.json() or {}


def _safe_repo_path_component(s: str) -> str:
    s = (s or '').strip()
    if not s:
        return 'run'
    # GitHub path safe-ish: keep alnum, dash, underscore, dot; replace others
    out = []
    for ch in s:
        if ch.isalnum() or ch in ('-', '_', '.'):
            out.append(ch)
        else:
            out.append('_')
    return ''.join(out).strip('_') or 'run'


def _github_get_default_branch(owner: str, repo_name: str) -> str:
    try:
        url = f'https://api.github.com/repos/{owner}/{repo_name}'
        resp = requests.get(url, headers=_github_headers(), timeout=20)
        if resp.status_code != 200:
            return 'main'
        j = resp.json() or {}
        return (j.get('default_branch') or 'main').strip() or 'main'
    except Exception:
        return 'main'


def _github_put_repo_file(owner: str, repo_name: str, branch: str, path_in_repo: str, content_bytes: bytes, message: str) -> dict:
    """Feltölt egy fájlt a repóba a Contents API-n keresztül (commitot hoz létre).

    Megjegyzés: ez nem issue-attachment, hanem verziózott fájl a repóban. Stabil fallback.
    """
    path_in_repo = (path_in_repo or '').lstrip('/')
    url = f'https://api.github.com/repos/{owner}/{repo_name}/contents/{path_in_repo}'
    payload = {
        'message': message or f'Add artifact {path_in_repo}',
        'content': base64.b64encode(content_bytes or b'').decode('ascii'),
        'branch': branch,
    }
    resp = requests.put(url, headers=_github_headers(), json=payload, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"GitHub contents upload failed (status={resp.status_code}): {(resp.text or '').strip()}")
    return resp.json() or {}


def _guess_mime_type(filename: str) -> str:
    name = (filename or '').lower()
    if name.endswith('.html'):
        return 'text/html'
    if name.endswith('.zip'):
        return 'application/zip'
    if name.endswith('.xml'):
        return 'application/xml'
    if name.endswith('.txt'):
        return 'text/plain'
    return 'application/octet-stream'


def _zip_for_upload(src_path: str, zip_path: str) -> str:
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(src_path, arcname=os.path.basename(src_path))
    return zip_path


def _zip_file_to_bytes(src_path: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(src_path, arcname=os.path.basename(src_path))
    return buf.getvalue()


def _split_bytes(content: bytes, chunk_size: int) -> list[bytes]:
    if not content:
        return [b'']
    if chunk_size <= 0:
        return [content]
    return [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]


def _prepare_attachment_payloads(file_path: str, preferred_name: str, max_bytes: int) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Return ([(upload_name, upload_bytes)], notes).

    Strategy:
    - If file <= max_bytes: upload as-is
    - Else: zip in-memory and upload the zip
    - If zip still > max_bytes: split the zip into .partNN chunks <= max_bytes
    """
    notes: list[str] = []
    file_path = file_path or ''
    preferred_name = preferred_name or os.path.basename(file_path)

    try:
        size = os.path.getsize(file_path)
    except Exception:
        size = -1

    # Small enough: upload raw
    if size >= 0 and size <= max_bytes:
        with open(file_path, 'rb') as f:
            return [(preferred_name, f.read())], notes

    # Too large (or unknown size): zip
    try:
        zip_name = preferred_name if preferred_name.lower().endswith('.zip') else (preferred_name + '.zip')
        zipped = _zip_file_to_bytes(file_path)
        if size >= 0:
            notes.append(f"Zip csatolva: {zip_name} (raw={size} byte, zip={len(zipped)} byte)")
        else:
            notes.append(f"Zip csatolva: {zip_name} (zip={len(zipped)} byte)")
    except Exception as e:
        # Fallback: try raw anyway
        notes.append(f"Zip készítés sikertelen ({e}); eredeti fájl feltöltése megkísérelve: {preferred_name}")
        with open(file_path, 'rb') as f:
            return [(preferred_name, f.read())], notes

    # Zip fits
    if len(zipped) <= max_bytes:
        return [(zip_name, zipped)], notes

    # Split zip into parts
    parts = _split_bytes(zipped, max_bytes)
    notes.append(f"Zip még mindig túl nagy, darabolva {len(parts)} részre (max {max_bytes} byte/rész)")
    payloads: list[tuple[str, bytes]] = []
    for idx, part in enumerate(parts, start=1):
        part_name = f"{zip_name}.part{idx:02d}"
        payloads.append((part_name, part))
    notes.append(
        "Összefűzés Windows alatt: `copy /b file.zip.part01+file.zip.part02+... file.zip` majd kibontás."
    )
    return payloads, notes


def _prepare_attachment_path(file_path: str, preferred_name: str, max_bytes: int = 9 * 1024 * 1024) -> tuple[str, str, str | None]:
    """Returns (path_to_upload, upload_filename, note).

    If the original file is too large, creates a .zip next to it and uploads that.
    """
    file_path = file_path or ''
    preferred_name = preferred_name or os.path.basename(file_path)
    try:
        size = os.path.getsize(file_path)
    except Exception:
        size = -1

    if size >= 0 and size > max_bytes:
        base_dir = os.path.dirname(file_path)
        zip_name = preferred_name + '.zip' if not preferred_name.lower().endswith('.zip') else preferred_name
        zip_path = os.path.join(base_dir, zip_name)
        try:
            _zip_for_upload(file_path, zip_path)
            zsize = os.path.getsize(zip_path)
            note = f"Túl nagy fájl ({size} byte), zip csatolva ({zsize} byte): {zip_name}"
            return zip_path, zip_name, note
        except Exception as e:
            # Ha nem sikerül zip-elni, próbáljuk az eredetit
            return file_path, preferred_name, f"Zip készítés sikertelen ({e}); eredeti fájl feltöltése megkísérelve."

    return file_path, preferred_name, None


def _github_upload_issue_attachment(owner: str, repo_name: str, issue_number: int, filename: str, content_bytes: bytes) -> dict:
    """Uploads an attachment to an issue (GitHub Issues attachments API).

    Returns JSON from GitHub on success.
    """
    url = f'https://uploads.github.com/repos/{owner}/{repo_name}/issues/{issue_number}/attachments'
    headers = dict(_github_headers())
    headers['Accept'] = 'application/vnd.github+json'
    headers['X-GitHub-Api-Version'] = '2022-11-28'

    # FONTOS: ez a végpont multipart/form-data feltöltést vár.
    # Ne állítsunk be kézzel Content-Type-ot; a requests beállítja a boundary-t.

    # Az uploads API néha érzékeny az auth sémára (fine-grained PAT esetén gyakran Bearer)
    try:
        token = _get_github_token()
        if token:
            headers['Authorization'] = f'Bearer {token}'
    except Exception:
        pass

    if content_bytes is None:
        content_bytes = b''

    files = {
        # GitHub endpoint sensitive; use octet-stream for maximum compatibility
        'file': (filename, content_bytes, 'application/octet-stream'),
    }
    resp = requests.post(url, headers=headers, params={'name': filename}, files=files, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"GitHub upload attachment failed (status={resp.status_code}, name={filename}, bytes={len(content_bytes)}): {(resp.text or '').strip()}"
        )
    return resp.json() or {}


def run_robot_with_params(repo: str, branch: str, timeout_seconds: int | None = None):

    """Indítja el a Robot Framework futtatást a megadott repo/branch paraméterekkel.

    Ha timeout_seconds meg van adva (>0), akkor időtúllépés esetén a futó robot
    folyamatot megszakítja (kill) és a futás "Megszakítva" státusszal kerül mentésre.

    Visszatér: (returncode, results_dir_rel, stdout, stderr)
    """
    # A log/result könyvtár nevét és a CURRENT_LOG_DIR-t a backend generálja, nem a Robot Framework.

    # --- Töröljük a server.log tartalmát minden futtatás előtt ---
    try:
        backend_log_path = _get_backend_log_path()
        with open(backend_log_path, 'w', encoding='utf-8') as f:
            f.write('')
    except Exception:
        pass

    # --- Töröljük a LOG_FILES/current_log_dir.txt fájlt is ---
    try:
        log_files_dir = _normalize_dir_from_vars('LOG_FILES')
        if '%USERPROFILE%' in log_files_dir or '~' in log_files_dir:
            home = os.path.expanduser('~')
            log_files_dir = log_files_dir.replace('%USERPROFILE%', home).replace('~', home)
        current_log_dir_path = os.path.join(log_files_dir, 'current_log_dir.txt')
        if os.path.exists(current_log_dir_path):
            os.remove(current_log_dir_path)
    except Exception:
        pass

    log_files_dir = _normalize_dir_from_vars('LOG_FILES')
    # Ha %USERPROFILE% vagy ~ szerepel, cseréljük ki a tényleges home könyvtárra
    if '%USERPROFILE%' in log_files_dir or '~' in log_files_dir:
        home = os.path.expanduser('~')
        log_files_dir = log_files_dir.replace('%USERPROFILE%', home).replace('~', home)

    safe_repo = (repo or 'unknown').replace('/', '_')
    safe_branch = (branch or 'unknown').replace('/', '_')
    current_log_dir_path = os.path.join(log_files_dir, 'current_log_dir.txt')
    current_log_dir = None
    # Ha már létezik a current_log_dir.txt, olvassuk be
    if os.path.exists(current_log_dir_path):
        try:
            with open(current_log_dir_path, 'r', encoding='utf-8') as f:
                current_log_dir = f.read().strip()
        except Exception as e:
            logger.warning(f"[RUN][WARNING] Nem sikerült beolvasni a current_log_dir.txt-t: {e}")
    # Ha nem létezik, generáljunk újat
    if not current_log_dir:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        current_log_dir = f"{safe_repo}__{safe_branch}__{timestamp}"
        try:
            with open(current_log_dir_path, 'w', encoding='utf-8') as f:
                f.write(current_log_dir + '\n')
        except Exception as e:
            logger.warning(f"[RUN][WARNING] Nem sikerült a current_log_dir.txt mentése: {e}")
    results_dir_abs = os.path.join(log_files_dir, current_log_dir)
    os.makedirs(results_dir_abs, exist_ok=True)

    suite_path = os.path.abspath('do-selected.robot')
    # Ellenőrzések futtatás előtt
    if not os.path.isfile(PYTHON_EXECUTABLE):
        msg = f"Python végrehajtható nem található: {PYTHON_EXECUTABLE}"
        logger.error(f"[RUN][ERROR] {msg}")
        return 1, '', '', msg
    # Ellenőrizzük, hogy a robot modul elérhető-e
    try:
        import importlib.util
        if importlib.util.find_spec('robot.run') is None:
            msg = "A 'robot' modul nem található a Python környezetben."
            logger.error(f"[RUN][ERROR] {msg}")
            return 1, '', '', msg
    except Exception as e:
        msg = f"A 'robot' modul ellenőrzése hibát dobott: {e}"
        logger.error(f"[RUN][ERROR] {msg}")
        return 1, '', '', msg
    if not os.path.isfile(suite_path):
        msg = f"A teszt suite fájl nem található: {suite_path}"
        logger.error(f"[RUN][ERROR] {msg}")
        return 1, '', '', msg

    # A CURRENT_LOG_DIR-t és LOG_OUTPUT_DIR-t átadjuk a Robot Framework-nek
    cmd = [
        PYTHON_EXECUTABLE, '-m', 'robot.run',
        '-d', results_dir_abs,
        '--log', os.path.join(results_dir_abs, 'log.html'),
        '--report', os.path.join(results_dir_abs, 'report.html'),
        '--output', os.path.join(results_dir_abs, 'output.xml'),
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
        #result = subprocess.run(
        #    cmd,
        #    capture_output=True,
        #    text=True,
        #    encoding='utf-8',
        #    errors='ignore',
        #    check=False,
        #    creationflags=creationflags
        #)
        op_key = _make_run_op_key(repo, branch)
        # Ne indítsunk párhuzamosan ugyanarra az opKey-re új futást
        try:
            with RUNNING_ROBOT_PROCS_LOCK:
                existing = RUNNING_ROBOT_PROCS.get(op_key)
            if existing is not None and existing.poll() is None:
                msg = f"Már fut egy folyamat ehhez: {op_key}"
                logger.warning(f"[RUN][WARNING] {msg}")
                return 1, results_dir_abs, '', msg
        except Exception:
            pass

        result = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
        )

        # Opcionális futási timeout kezelése (backend oldalon enforce-olva)
        timeout_s: int | None = None
        try:
            if timeout_seconds is not None:
                timeout_s = int(timeout_seconds)
        except Exception:
            timeout_s = None
        if timeout_s is not None and timeout_s <= 0:
            timeout_s = None

        timed_out = False
        watchdog_stop = None
        watchdog_thread = None
        if timeout_s is not None:
            try:
                import threading as _threading

                watchdog_stop = _threading.Event()

                def _watchdog():
                    nonlocal timed_out
                    try:
                        # Várunk timeout_s másodpercet, vagy amíg a futás véget ér
                        if watchdog_stop.wait(timeout_s):
                            return
                        # Ha még fut, megszakítjuk
                        if result.poll() is None:
                            timed_out = True
                            try:
                                _mark_run_cancelled(op_key)
                            except Exception:
                                pass
                            logger.warning(f"[RUN][TIMEOUT] Időtúllépés: {timeout_s}s, folyamat kilövése. opKey={op_key} pid={getattr(result, 'pid', None)}")
                            try:
                                _kill_process_tree(result)
                            except Exception as e:
                                logger.warning(f"[RUN][TIMEOUT] Kill hiba: {e}")
                    except Exception as e:
                        logger.warning(f"[RUN][TIMEOUT] Watchdog hiba: {e}")

                watchdog_thread = _threading.Thread(target=_watchdog, daemon=True)
                watchdog_thread.start()
            except Exception as e:
                logger.warning(f"[RUN][TIMEOUT] Watchdog indítása sikertelen: {e}")

        # Regisztráljuk a futó folyamatot, hogy külön kérésből megszakítható legyen.
        try:
            with RUNNING_ROBOT_PROCS_LOCK:
                RUNNING_ROBOT_PROCS[op_key] = result
        except Exception:
            pass

        output_lines = []
        try:
            for line in result.stdout:
                try:
                    safe_line = line.strip()
                    if isinstance(safe_line, bytes):
                        safe_line = safe_line.decode('utf-8', errors='replace')
                    else:
                        safe_line = str(safe_line)
                    logger.info(f": {safe_line}")
                    output_lines.append(safe_line)
                except Exception as e:
                    logger.warning(f"[RUN][LOGGING ERROR]: {e}")
        finally:
            try:
                if watchdog_stop is not None:
                    watchdog_stop.set()
            except Exception:
                pass
            try:
                result.wait()
            except Exception:
                pass

            try:
                with RUNNING_ROBOT_PROCS_LOCK:
                    if RUNNING_ROBOT_PROCS.get(op_key) is result:
                        del RUNNING_ROBOT_PROCS[op_key]
            except Exception:
                pass

        if timed_out:
            output_lines.append(f"[TIMEOUT] A futás túllépte a beállított {timeout_s}s időt, a folyamat megszakítva.")
        logger.info(f"[RUN] Return code: {result.returncode}")
        logger.info(f"[RUN] Robot output (first 500 chars): {''.join(output_lines)[:500]}")
        return result.returncode, results_dir_abs, '\n'.join(output_lines), ''
    except FileNotFoundError as e:
        logger.error(f"[RUN][ERROR] FileNotFoundError: {e}")
        logger.info(f"[RUN] Robot visszatérés: returncode=1")
        logger.info(f"[RUN] Robot stdout: '')")
        logger.info(f"[RUN] Robot stderr: FileNotFoundError: {e}")
        return 1, '', '', f'FileNotFoundError: {e}'
    except Exception as e:
        # Windows hibadoboz elkerülése: hiba naplózása, de nem dobunk tovább hibát
        logger.error(f"[RUN][ERROR] {e}")
        logger.info(f"[RUN] Robot visszatérés: returncode=1")
        logger.info(f"[RUN] Robot stdout: '')")
        logger.info(f"[RUN] Robot stderr: {str(e)}")
        return 1, '', '', str(e)


@app.route('/api/cancel_execute', methods=['POST'])
def api_cancel_execute():
    """Megszakítja (kill) a futó Robot Framework folyamatot repo/branch alapján."""
    try:
        data = request.get_json(silent=True) or {}
        repo = (data.get('repo') or request.values.get('repo') or '').strip()
        branch = (data.get('branch') or request.values.get('branch') or '').strip()
        if not repo or not branch:
            return jsonify({'success': False, 'error': 'Hiányzó repo vagy robot'}), 400

        op_key = _make_run_op_key(repo, branch)

        # User intent: if Stop was pressed for this run, persist as cancelled even if
        # the process is already gone from the registry.
        _mark_run_cancelled(op_key)

        proc = _get_running_robot_proc(op_key)
        if proc is None:
            return jsonify({'success': True, 'message': 'Megszakítás jelölve (folyamat nem található)', 'opKey': op_key}), 200

        ok, message = _kill_process_tree(proc)

        # Mark as cancelled so /api/execute can persist the proper run status
        if ok:
            _mark_run_cancelled(op_key)

        # Takarítsuk ki, ha már nem fut.
        try:
            if proc.poll() is not None:
                with RUNNING_ROBOT_PROCS_LOCK:
                    if RUNNING_ROBOT_PROCS.get(op_key) is proc:
                        del RUNNING_ROBOT_PROCS[op_key]
        except Exception:
            pass

        status = 200 if ok else 500
        return jsonify({'success': ok, 'message': message, 'opKey': op_key, 'pid': int(proc.pid)}), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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


def _has_filled_latest_version(release_meta: dict) -> bool:
    """A 'legfrissebb verzió' akkor tekinthető kitöltöttnek, ha van release tag."""
    try:
        return bool((release_meta or {}).get('tag'))
    except Exception:
        return False


@app.route('/')
def index():
    """Főoldal"""
    # Repository adatok lekérése
    repos = get_repository_data()
    root_folder = get_robot_variable('ROOT_FOLDER')
    is_sandbox = get_sandbox_mode()

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
        # DEBUG/FALLBACK: normál módban ha nincs branch, adjunk hozzá teszt brancheket, hogy a UI ne legyen üres.
        # Sandbox módban ez félrevezető lenne (nem repo-specifikus), ezért ott nem töltjük fel.
        if not repo['branches'] and not get_sandbox_mode():
            repo['branches'] = ['main', 'teszt-branch']

    # Előre kiszámoljuk a futtatható (telepített) és letölthető branch-eket repo szinten
    installed_keys = get_installed_keys()
    installed_branches_by_repo: dict[str, list[str]] = {}
    if is_sandbox:
        # Sandbox módban a telepített listát a SandboxRobots könyvtárból kell építeni,
        # mert nincs .venv és a remote branch lekérdezés best-effort (akár üres is lehet).
        for key in installed_keys:
            try:
                repo_name, branch_name = key.split('|', 1)
                installed_branches_by_repo.setdefault(repo_name, []).append(branch_name)
            except Exception:
                continue
    for repo in repos:
        # Megjegyzés: a könyvtárstruktúra <base>/<repo>/<branch>/
        if is_sandbox:
            repo['downloaded_branches'] = sorted(set(installed_branches_by_repo.get(repo['name'], []) or []))
            repo['available_branches'] = [
                branch for branch in (repo.get('branches') or [])
                if branch not in set(repo['downloaded_branches'] or [])
            ]
        else:
            repo['downloaded_branches'] = [
                branch for branch in (repo.get('branches') or [])
                if f"{repo['name']}|{branch}" in installed_keys
            ]
            repo['available_branches'] = [
                branch for branch in (repo.get('branches') or [])
                if f"{repo['name']}|{branch}" not in installed_keys
            ]

        # Branch-enként a legfrissebb release tag/cím/dátum (best-effort)
        # (kell a futtatható és a letölthető tab Info ablakához is)
        try:
            branches_for_release = list(dict.fromkeys((repo.get('downloaded_branches') or []) + (repo.get('available_branches') or [])))
            repo['available_branch_releases'] = get_latest_release_by_branch(repo, branches_for_release)
        except Exception:
            repo['available_branch_releases'] = {}

        # Letölthető tab: normál módban csak azok a branchek látszódjanak,
        # ahol ki van töltve a legfrissebb verzió (release tag).
        # Fejlesztői (sandbox) módban ne szűrjünk release információ alapján.
        if not is_sandbox:
            try:
                rel_map = repo.get('available_branch_releases') or {}
                repo['available_branches'] = [
                    b for b in (repo.get('available_branches') or [])
                    if _has_filled_latest_version(rel_map.get(b) or {})
                ]
            except Exception:
                pass
    version = get_robot_variable('VERSION')
    build_date = get_robot_variable('BUILD_DATE')
    # page_title logika ugyanaz, mint a get_html_template-ben
    page_title = "Fejlesztői mód" if is_sandbox else "Segíthetünk?"
    # Színséma lekérése
    color_scheme = get_html_template(is_sandbox, page_title)
    last_run_by_key = _build_last_run_by_key()
    response = app.response_class(
        render_template(
            "main.html",
            repos=repos,
            datetime=datetime,
            downloaded_keys=installed_keys,
            last_run_by_key=last_run_by_key,
            root_folder=root_folder or '',
            version=version,
            build_date=build_date,
            page_title=page_title,
            is_sandbox=is_sandbox,
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
    is_sandbox = get_sandbox_mode()
    installed_branches_by_repo: dict[str, list[str]] = {}
    if is_sandbox:
        for key in installed_keys:
            try:
                repo_name, branch_name = key.split('|', 1)
                installed_branches_by_repo.setdefault(repo_name, []).append(branch_name)
            except Exception:
                continue
    logger.info(f"[API/REFRESH] installed_keys: {installed_keys}")
    for repo in repos:
        repo['branches'] = get_branches_for_repo(repo['name'])  # Mindig újraolvassa a branch-eket
        logger.info(f"[API/REFRESH] repo: {repo['name']}, branches: {repo['branches']}")
        if is_sandbox:
            repo['downloaded_branches'] = sorted(set(installed_branches_by_repo.get(repo['name'], []) or []))
            repo['available_branches'] = [
                branch for branch in (repo.get('branches') or [])
                if branch not in set(repo['downloaded_branches'] or [])
            ]
        else:
            repo['downloaded_branches'] = [
                branch for branch in (repo.get('branches') or [])
                if f"{repo['name']}|{branch}" in installed_keys
            ]
            repo['available_branches'] = [
                branch for branch in (repo.get('branches') or [])
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
            return jsonify({"success": False, "error": "Hiányzó repo vagy robot"}), 400

        op_key = _make_run_op_key(repo, branch)
        # Avoid stale cancellation markers affecting a new run
        _clear_run_cancelled(op_key)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"[EXECUTE] Robot futtatás indítása: {repo}/{branch}")
        # Futtatási timeout (mp) a kliens beállításából. Ha nincs/érvénytelen, akkor nincs enforce-olt timeout.
        timeout_seconds: int | None = None
        try:
            raw_to = data.get('timeout')
            if raw_to is None:
                raw_to = request.values.get('timeout')
            if raw_to is not None and str(raw_to).strip() != '':
                timeout_seconds = int(float(str(raw_to).strip()))
        except Exception:
            timeout_seconds = None

        if timeout_seconds is not None:
            # UI: min=10, max=3600; legyen itt is védőkorlát
            if timeout_seconds < 10:
                timeout_seconds = 10
            if timeout_seconds > 3600:
                timeout_seconds = 3600

        logger.info(f"[EXECUTE] run_robot_with_params hívás előtt: repo={repo}, branch={branch}, timeout_s={timeout_seconds}")
        rc, out_dir, _stdout, _stderr = run_robot_with_params(repo, branch, timeout_seconds=timeout_seconds)
        logger.info(f"[EXECUTE] run_robot_with_params visszatért: rc={rc}, out_dir={out_dir}")

        # If the user cancelled (killed) the process, persist a dedicated status
        was_cancelled = _consume_run_cancelled(op_key)
        status = "cancelled" if was_cancelled else ("success" if rc == 0 else "failed")
        logger.info(f"[EXECUTE] Robot futtatás befejezve: rc={rc}, status={status}, dir={out_dir}")

        # --- GitHub Issue automatikus létrehozás + csatolmányok ---
        issue_info: dict | None = None
        try:
            token = _get_github_token()
            if token and out_dir:
                artifacts = _ensure_run_issue_artifacts(out_dir, _stdout, _stderr)
                title = _safe_path_basename(out_dir) or out_dir

                settings = _get_github_settings()
                owner = settings.get('owner') or 'lovaszotto'
                repo_name = settings.get('repo_name') or DEFAULT_GITHUB_REPO_NAME

                body_lines = [
                    f"Automatikusan létrehozott futási ticket: **{title}**",
                    "",
                    f"- Repo: `{repo}`",
                    f"- Robot: `{branch}`",
                    f"- Return code: `{rc}`",
                    f"- Status: `{status}`",
                    f"- Results dir: `{out_dir}`",
                ]
                issue_obj = _github_create_issue(
                    owner=owner,
                    repo_name=repo_name,
                    title=title,
                    body='\n'.join(body_lines),
                    labels=['documentation'],
                )
                issue_number = int(issue_obj.get('number'))
                issue_url = issue_obj.get('html_url')

                uploads: list[dict] = []
                upload_errors: list[str] = []
                upload_notes: list[str] = []
                # A GitHub issue-attachment méretlimitje gyakorlatban nagyon alacsony lehet,
                # ezért extra konzervatív limitet használunk, és szükség esetén darabolunk.
                max_attachment_bytes = 100 * 1024
                for key, file_path in (
                    ('r_log.html', artifacts.get('r_log_path')),
                    ('r_riport.html', artifacts.get('r_riport_path') or artifacts.get('r_report_path')),
                ):
                    if not file_path or not os.path.exists(file_path):
                        upload_errors.append(f"Missing artifact: {key}")
                        continue
                    try:
                        payloads, notes = _prepare_attachment_payloads(file_path, key, max_attachment_bytes)
                        upload_notes.extend(notes)
                        for upload_name, content in payloads:
                            if not content:
                                upload_notes.append(f"Üres csatolmány kihagyva: {upload_name}")
                                continue
                            try:
                                up = _github_upload_issue_attachment(owner, repo_name, issue_number, upload_name, content)
                                uploads.append(up)
                            except Exception as e:
                                upload_errors.append(f"{upload_name} upload failed: {e}")
                    except Exception as e:
                        upload_errors.append(f"{key} upload failed: {e}")

                # Kommentben belinkeljük az attachmenteket (ha GitHub adott URL-t)
                try:
                    if uploads:
                        link_lines = ["Futtási csatolmányok:"]
                        for up in uploads:
                            name = up.get('name') or up.get('filename') or 'attachment'
                            link = up.get('browser_download_url') or up.get('html_url') or up.get('url')
                            if link:
                                link_lines.append(f"- [{name}]({link})")
                            else:
                                link_lines.append(f"- {name}")
                        _github_create_issue_comment(owner, repo_name, issue_number, '\n'.join(link_lines))
                except Exception as e:
                    # Ne szemeteljük tele az issue-t hibával; elég a server.log.
                    logger.info(f"[EXECUTE][ISSUE] Csatolmány-link komment hiba: {e}")

                # Fallback: ha a GitHub issue-attachment API hibázik (pl. 422 Bad Size),
                # akkor tegyük be a fájlokat a repóba a Contents API-val és linkeljük.
                fallback_links: list[dict] = []
                fallback_errors: list[str] = []
                if upload_errors:
                    try:
                        default_branch = _github_get_default_branch(owner, repo_name)
                        run_folder = _safe_repo_path_component(title)
                        base_path = f"run_artifacts/{run_folder}"

                        for key, file_path in (
                            ('r_log.html', artifacts.get('r_log_path')),
                            ('r_riport.html', artifacts.get('r_riport_path') or artifacts.get('r_report_path')),
                        ):
                            if not file_path or not os.path.exists(file_path):
                                continue
                            try:
                                payloads, notes = _prepare_attachment_payloads(file_path, key, 700 * 1024)
                                upload_notes.extend([f"[Repo fallback] {n}" for n in notes])
                                for upload_name, content in payloads:
                                    if not content:
                                        continue
                                    path_in_repo = f"{base_path}/{_safe_repo_path_component(upload_name)}"
                                    respj = _github_put_repo_file(
                                        owner,
                                        repo_name,
                                        default_branch,
                                        path_in_repo,
                                        content,
                                        message=f"Add run artifact {run_folder}: {upload_name}",
                                    )
                                    html_url = None
                                    try:
                                        html_url = (respj.get('content') or {}).get('html_url')
                                    except Exception:
                                        html_url = None
                                    fallback_links.append({'name': upload_name, 'path': path_in_repo, 'html_url': html_url, 'branch': default_branch})
                            except Exception as e:
                                fallback_errors.append(f"{key} repo fallback failed: {e}")

                        if fallback_links:
                            lines = ["Repo fallback csatolmányok (issue-attachment helyett):"]
                            for item in fallback_links:
                                nm = item.get('name')
                                url = item.get('html_url')
                                if url:
                                    lines.append(f"- [{nm}]({url})")
                                else:
                                    lines.append(f"- {nm}: {item.get('path')}")
                            _github_create_issue_comment(owner, repo_name, issue_number, '\n'.join(lines))
                    except Exception as e:
                        fallback_errors.append(str(e))

                closed = False
                close_error = None
                if rc == 0 and status == 'success':
                    try:
                        _github_close_issue(owner, repo_name, issue_number)
                        closed = True
                    except Exception as e:
                        close_error = str(e)

                issue_info = {
                    'repo': f"{owner}/{repo_name}",
                    'number': issue_number,
                    'html_url': issue_url,
                    'created': True,
                    'closed': closed,
                    'attachments_uploaded': [
                        {
                            'name': (u.get('name') or u.get('filename')),
                            'url': (u.get('browser_download_url') or u.get('html_url') or u.get('url')),
                        }
                        for u in uploads
                    ],
                    'upload_ok': (len(upload_errors) == 0),
                    'repo_fallback': {
                        'used': bool(upload_errors),
                        'links': fallback_links,
                    },
                    'close_error': close_error,
                }
            else:
                issue_info = {
                    'created': False,
                    'skipped': True,
                    'reason': 'Missing GitHub token or results dir',
                }
        except Exception as e:
            logger.info(f"[EXECUTE][ISSUE] Issue automatizálás hiba: {e}")
            issue_info = {
                'created': False,
                'error': str(e),
            }

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

        api_status = 'ok' if status == 'success' else ('cancelled' if status == 'cancelled' else 'fail')
        result_obj = {
            'success': status == 'success',
            'repo': repo,
            'branch': branch,
            'returncode': rc,
            'results_dir': out_dir,
            'status': api_status,
            'run_status': status,
            'issue': issue_info,
        }
        save_execution_results()
        return jsonify(result_obj)
    except Exception as e:
        logger.error(f"[EXECUTE] Hiba a futtatás során: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'repo': repo if 'repo' in locals() else None,
            'branch': branch if 'branch' in locals() else None,
            'status': "error"
        })
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
            print("[START_ROBOT] HIBA: Hiányzó repo vagy robot paraméter")
            return jsonify({
                'success': False,
                'error': 'Hiányzó repo vagy robot'
            }), 400

        base_dir = get_installed_robots_dir()
        logger.info(f"[ROBOT ELLENŐRZÉS] Robot indítás ellenőrzés, könyvtár: {base_dir}, repo: {repo}, branch: {branch}")
        if not base_dir:
            base_dir = _normalize_dir_from_vars('DOWNLOADED_ROBOTS') or os.path.join(os.getcwd(), 'DownloadedRobots')
            logger.info(f"[ROBOT ELLENŐRZÉS] Fallback könyvtár: {base_dir}")

        safe_repo = repo.replace('/', '_')
        safe_branch = branch.replace('/', '_')
        target_dir = os.path.normpath(os.path.join(base_dir, safe_repo, safe_branch))
        start_bat = os.path.join(target_dir, 'start.bat')
        logger.info(f"[ROBOT ELLENŐRZÉS] Indítás target_dir: {target_dir}, start_bat: {start_bat}")

        if not os.path.isdir(target_dir):
            logger.error(f"[START_ROBOT] HIBA: Könyvtár nem található vagy érvénytelen: {target_dir}")
            return jsonify({
                'success': False,
                'error': f'Érvénytelen vagy nem létező könyvtár: {target_dir}'
            }), 404
        if not os.path.exists(start_bat):
            logger.error(f"[START_ROBOT] HIBA: start.bat nem található: {start_bat}")
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

# Eredmények betöltése alkalmazás indításkor
execution_results = load_execution_results()
# Indulás után automatikusan töröljük a nem létező results_dir-re mutató bejegyzéseket
def _auto_cleanup_execution_results():
    global execution_results
    before = len(execution_results)
    cleaned = [r for r in execution_results if r.get('results_dir') and os.path.isdir(r['results_dir'])]
    removed = before - len(cleaned)
    if removed > 0:
        execution_results = cleaned
        save_execution_results()
        print(f"[CLEANUP] {removed} execution_results törölve, mert a results_dir nem létezik.")
_auto_cleanup_execution_results()


def _build_last_run_by_key() -> dict[str, dict]:
    """Legutóbbi futás meta repo|branch kulcsonként.

    Visszatérési forma: {"repo|branch": {"status": "success|failed|...", "timestamp": "YYYY-MM-DD HH:MM:SS", "returncode": int|None}}
    """
    last: dict[str, dict] = {}
    try:
        for r in (execution_results or []):
            repo = (r.get('repo') or '').strip()
            branch = (r.get('branch') or '').strip()
            ts = (r.get('timestamp') or '').strip()
            if not repo or not branch or not ts:
                continue
            key = f"{repo}|{branch}"
            prev = last.get(key)
            # A timestamp formátum fix: YYYY-MM-DD HH:MM:SS -> lexikografikusan összehasonlítható
            if prev is None or str(ts) > str(prev.get('timestamp') or ''):
                last[key] = {
                    'status': (r.get('status') or '').strip(),
                    'timestamp': ts,
                    'returncode': r.get('returncode'),
                }
    except Exception:
        return last
    return last


def _build_last_run_by_branch(repo_name: str, branches: list[str]) -> dict[str, dict]:
    """Repo-n belül branch->legutóbbi futás meta."""
    m = _build_last_run_by_key()
    out: dict[str, dict] = {}
    try:
        for br in (branches or []):
            key = f"{(repo_name or '').strip()}|{(br or '').strip()}"
            if key in m:
                out[str(br)] = m[key]
    except Exception:
        return out
    return out

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
    import logging
    logger = logging.getLogger("delete_runnable_branch")
    try:
        data = request.get_json()
        logger.info(f"[DELETE] Request data: {data}")
        repo_name = data.get('repo') or data.get('repo_name')
        branch_name = data.get('branch') or data.get('branch_name')
        logger.info(f"[DELETE] repo_name: {repo_name}, branch_name: {branch_name}")
        if not repo_name or not branch_name:
            logger.warning("[DELETE] Hiányzó repo vagy branch név!")
            return jsonify({'success': False, 'error': 'Repository és robot név szükséges'})
        # Telepített (runnable) robot könyvtár törlése: normál módban DownloadedRobots, sandbox módban SandboxRobots.
        is_sandbox = get_sandbox_mode()
        base_dir = get_installed_robots_dir()
        logger.info(f"[DELETE] sandbox_mode={is_sandbox} base_dir={base_dir}")
        logger.info(f"[DELETE] _delete_robot_directory hívás: base_dir={base_dir} repo={repo_name} branch={branch_name}")
        deleted_any, info_down = _delete_robot_directory(base_dir, repo_name, branch_name)
        status_down = 'törölve' if deleted_any else 'nem található, nincs mit törölni'
        logger.info(f"[DELETE] BASE_DIR ({'SANDBOX' if is_sandbox else 'DOWNLOADED'}): {repo_name}/{branch_name}: {status_down}. {info_down}")
        response = {
            'success': deleted_any,
            'message': f'Robot {repo_name}/{branch_name} eltávolítva' if deleted_any else info_down,
            'deleted': deleted_any,
            # Backward-compat: frontend might display/inspect this field
            'deleted_downloaded': deleted_any
        }
        logger.info(f"[DELETE] Válasz: {response}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Hiba a robot törlésében: {e}")
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



# ÚJ: log.html kiszolgálása a LOG_FILES könyvtárból
@app.route('/logfiles/<path:subpath>')
def serve_logfiles(subpath):
    """Serve files from the LOG_FILES directory securely.

    If a directory is requested, try to serve its log.html. Otherwise, serve the specific file.
    """
    log_files_dir = _normalize_dir_from_vars('LOG_FILES')
    if '%USERPROFILE%' in log_files_dir or '~' in log_files_dir:
        home = os.path.expanduser('~')
        log_files_dir = log_files_dir.replace('%USERPROFILE%', home).replace('~', home)
    base = os.path.abspath(log_files_dir)
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

@app.route('/api/install_selected', methods=['POST'])
def api_install_selected():
    """Kijelölt robotok letöltése és telepítése, de nem futtatja őket."""
    try:
        # --- Töröljük a server.log tartalmát minden letöltés előtt ---
        try:
            backend_log_path = _get_backend_log_path()
            with open(backend_log_path, 'w', encoding='utf-8') as f:
                f.write('')
        except Exception:
            pass
        # --- Töröljük a LOG_FILES/current_log_dir.txt fájlt is ---
        try:
            log_files_dir = _normalize_dir_from_vars('LOG_FILES')
            if '%USERPROFILE%' in log_files_dir or '~' in log_files_dir:
                home = os.path.expanduser('~')
                log_files_dir = log_files_dir.replace('%USERPROFILE%', home).replace('~', home)
            current_log_dir_path = os.path.join(log_files_dir, 'current_log_dir.txt')
            if os.path.exists(current_log_dir_path):
                os.remove(current_log_dir_path)
        except Exception:
            pass
        data = request.get_json(silent=True) or {}
        robots = data.get('robots') or []
        logger.info(f"[INSTALL_SELECTED] Download gomb lenyomva, robots param: {robots}")
        if not robots:
            logger.warning("[INSTALL_SELECTED] Nincs kiválasztott robot a letöltéshez.")
            return jsonify({'success': False, 'error': 'Nincs kiválasztott robot.'}), 400
        installed = []
        errors = []
        from datetime import datetime
        global execution_results
        import html
        for r in robots:
            repo = (r.get('repo') or '').strip()
            branch = (r.get('branch') or '').strip()
            if not repo or not branch:
                logger.error(f"[INSTALL_SELECTED] Hiányzó repo vagy branch: {r}")
                errors.append({'repo': repo, 'branch': branch, 'error': 'Hiányzó repo vagy robot'})
                continue
            try:
                logger.info(f"[INSTALL_SELECTED] install_robot_with_params hívás: repo='{repo}', branch='{branch}'")
                rc, results_dir_rel, _stdout, _stderr = install_robot_with_params(repo, branch)
                logger.info(f"[INSTALL_SELECTED] install_robot_with_params eredmény: rc={rc}, results_dir_rel={results_dir_rel}")
                installed_version = _read_installed_version(branch) if rc == 0 else 'NONE'
                # --- r_log.html készítése ---
                try:
                    # results_dir_rel pl.: IKK-Robotok__IKK01_Duplikáció-ellenőrzés__20251127_055002
                    robotresults_dir = os.path.join(os.path.expanduser('~'), 'MyRobotFramework', 'RobotResults')
                    rlog_dir = os.path.join(robotresults_dir, results_dir_rel) if results_dir_rel else None
                    if rlog_dir:
                        os.makedirs(rlog_dir, exist_ok=True)
                        rlog_path = os.path.join(rlog_dir, 'r_log.html')
                        with open(rlog_path, 'w', encoding='utf-8') as f:
                            f.write('<html><head><meta charset="utf-8"><title>Letöltés eredménye</title></head><body>')
                            f.write(f'<h2>Letöltés eredménye: {html.escape(repo)} / {html.escape(branch)}</h2>')
                            if rc == 0:
                                f.write('<p style="color:green;">Sikeres letöltés!</p>')
                                f.write(f'<p><b>Telepített:</b> {html.escape(installed_version)}</p>')
                            else:
                                f.write('<p style="color:red;">Sikertelen letöltés!</p>')
                            f.write('<h3>Részletek:</h3>')
                            f.write('<pre>')
                            f.write(html.escape(_stdout or ''))
                            if _stderr:
                                f.write('\n--- STDERR ---\n')
                                f.write(html.escape(_stderr))
                            f.write('</pre></body></html>')
                except Exception as e:
                    logger.warning(f"[INSTALL_SELECTED] r_log.html írási hiba: {e}")
                # --- vége r_log.html ---
                if rc == 0:
                    installed.append({'repo': repo, 'branch': branch, 'results_dir': results_dir_rel, 'installed_version': installed_version})
                    # ÚJ: execution_results-ba is bekerül
                    result_entry = {
                        'id': len(execution_results) + 1,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'repo': repo,
                        'branch': branch,
                        'status': 'success',
                        'returncode': rc,
                        'results_dir': results_dir_rel,
                        'type': 'install',
                        'installed_version': installed_version,
                        'stdout': _stdout,
                        'stderr': _stderr
                    }
                    execution_results.append(result_entry)
                else:
                    logger.error(f"[INSTALL_SELECTED] Installáció sikertelen, rc={rc}, repo={repo}, branch={branch}, stdout={_stdout}, stderr={_stderr}")
                    errors.append({'repo': repo, 'branch': branch, 'error': f'Installáció sikertelen, rc={rc}', 'stdout': _stdout, 'stderr': _stderr})
            except Exception as e:
                logger.exception(f"[INSTALL_SELECTED] Kivétel installálás közben: repo={repo}, branch={branch}, error={e}")
                errors.append({'repo': repo, 'branch': branch, 'error': str(e)})
        if installed:
            save_execution_results()
        if errors:
            logger.error(f"[INSTALL_SELECTED] Hibák a letöltés során: {errors}")
            return jsonify({'success': False, 'installed': installed, 'errors': errors}), 500
        logger.info(f"[INSTALL_SELECTED] Sikeres letöltés: {installed}")
        return jsonify({'success': True, 'installed': installed})
    except Exception as e:
        logger.exception(f"[INSTALL_SELECTED] Váratlan szerverhiba: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
        logger.info(f"[ROBOT ELLENŐRZÉS] Telepítés SANDBOX könyvtárban: {base_dir}, repo: {repo}, branch: {branch}")
    else:
        base_dir = _normalize_dir_from_vars('DOWNLOADED_ROBOTS')
        if not base_dir:
            base_dir = os.path.join(os.getcwd(), 'DownloadedRobots')
        logger.info(f"[INSTALL] NEM sandbox mód, base_dir: {base_dir}")
        logger.info(f"[ROBOT ELLENŐRZÉS] Telepítés DOWNLOADED könyvtárban: {base_dir}, repo: {repo}, branch: {branch}")
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
            result = subprocess.Popen(
                clone_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="ignore"
            )
            output_lines = []
            for line in result.stdout:
                try:
                    safe_line = line.strip()
                    if isinstance(safe_line, bytes):
                        safe_line = safe_line.decode('utf-8', errors='replace')
                    else:
                        safe_line = str(safe_line)
                    logger.info(f"[INSTALL][CLONE]: {safe_line}")
                    output_lines.append(safe_line)
                except Exception as e:
                    logger.warning(f"[INSTALL][CLONE][LOGGING ERROR]: {e}")
            result.wait()
            logger.info(f"[INSTALL] Klónozás befejezve: rc={result.returncode}, output={output_lines[:10]}")
            if result.returncode != 0:
                logger.error(f"[INSTALL][ERROR] Klónozás sikertelen: rc={result.returncode}, output={output_lines[:10]}")
                return 1, '', '\n'.join(output_lines), ''
        else:
            # Force pull: fetch + reset --hard
            fetch_cmd = ['git', '-C', branch_dir, 'fetch', 'origin']
            logger.info(f"[INSTALL] Fetch indítása: {' '.join(fetch_cmd)}")
            fetch_result = subprocess.Popen(
                fetch_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="ignore"
            )
            fetch_lines = []
            for line in fetch_result.stdout:
                try:
                    safe_line = line.strip()
                    if isinstance(safe_line, bytes):
                        safe_line = safe_line.decode('utf-8', errors='replace')
                    else:
                        safe_line = str(safe_line)
                    logger.info(f"[INSTALL][FETCH]: {safe_line}")
                    fetch_lines.append(safe_line)
                except Exception as e:
                    logger.warning(f"[INSTALL][FETCH][LOGGING ERROR]: {e}")
            fetch_result.wait()
            logger.info(f"[INSTALL] Fetch befejezve: rc={fetch_result.returncode}, output={fetch_lines[:10]}")
            if fetch_result.returncode != 0:
                logger.error(f"[INSTALL][ERROR] Fetch sikertelen: rc={fetch_result.returncode}, output={fetch_lines[:10]}")
                return 1, '', '\n'.join(fetch_lines), ''
            reset_cmd = ['git', '-C', branch_dir, 'reset', '--hard', f'origin/{branch}']
            logger.info(f"[INSTALL] Reset --hard indítása: {' '.join(reset_cmd)}")
            reset_result = subprocess.Popen(
                reset_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="ignore"
            )
            reset_lines = []
            for line in reset_result.stdout:
                try:
                    safe_line = line.strip()
                    if isinstance(safe_line, bytes):
                        safe_line = safe_line.decode('utf-8', errors='replace')
                    else:
                        safe_line = str(safe_line)
                    logger.info(f"[INSTALL][RESET]: {safe_line}")
                    reset_lines.append(safe_line)
                except Exception as e:
                    logger.warning(f"[INSTALL][RESET][LOGGING ERROR]: {e}")
            reset_result.wait()
            logger.info(f"[INSTALL] Reset --hard befejezve: rc={reset_result.returncode}, output={reset_lines[:10]}")
            if reset_result.returncode != 0:
                logger.error(f"[INSTALL][ERROR] Reset --hard sikertelen: rc={reset_result.returncode}, output={reset_lines[:10]}")
                return 1, '', '\n'.join(reset_lines), ''
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
            logger.info(f"[INSTALL] telepito.bat futtatása indítás: cwd={branch_dir} (szinkron, várakozás)")
            result = subprocess.Popen(
                ['telepito.bat'],
                cwd=branch_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="ignore",
                shell=True
            )
            output_lines = []
            for line in result.stdout:
                try:
                    safe_line = line.strip()
                    if isinstance(safe_line, bytes):
                        safe_line = safe_line.decode('utf-8', errors='replace')
                    else:
                        safe_line = str(safe_line)
                    logger.info(f"[INSTALL][TELEPITO]: {safe_line}")
                    output_lines.append(safe_line)
                except Exception as e:
                    logger.warning(f"[INSTALL][TELEPITO][LOGGING ERROR]: {e}")
            result.wait()
            logger.info(f"[INSTALL] telepito.bat futtatás befejezve: rc={result.returncode}, output={output_lines[:10]}")
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

    # --- Telepített verzió rögzítése (installed_versions/<branch>.txt) ---
    try:
        installed_version = _try_get_latest_release_tag_for_branch(repo, branch)
        _write_installed_version(branch, installed_version)
        logger.info(f"[INSTALL] Telepített verzió rögzítve: branch='{branch}', version='{installed_version}'")
    except Exception as e:
        logger.warning(f"[INSTALL] Telepített verzió rögzítése sikertelen: branch='{branch}', err={e}")

    # --- Eredmény log generálása a results mappába ---
    try:
        results_dir_name = f"{safe_repo}__{safe_branch}__{timestamp}"
        results_dir_abs = os.path.abspath(os.path.join('results', results_dir_name))
        os.makedirs(results_dir_abs, exist_ok=True)
        log_path = os.path.join(results_dir_abs, 'log.html')
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"""
                <html><head><meta charset='utf-8'><title>Letöltési log</title></head><body>
                <h2>Robot letöltés sikeres</h2>
                <ul>
                    <li>Repo: {repo}</li>
                    <li>Robot: {branch}</li>
                    <li>Telepített: {installed_version}</li>
                    <li>Időpont: {timestamp}</li>
                    <li>Könyvtár: {branch_dir}</li>
                </ul>
                <p style='color:green;'>A robot sikeresen le lett töltve és telepítve.</p>
                </body></html>
            """)
        logger.info(f"[INSTALL] Letöltési log.html létrehozva: {log_path}")
    except Exception as e:
        logger.error(f"[INSTALL][ERROR] Nem sikerült letöltési logot írni: {e}")
    return 0, results_dir_name, 'Install OK', ''
# --- ÚJ ENDPOINTOK: Futtatható és letölthető robotok listája külön ---

# --- ÚJ ENDPOINTOK: Futtatható és letölthető robotok listája külön ---
@app.route('/api/runnable_repos', methods=['GET'])
def api_runnable_repos():
    """Csak a futtatható/telepített branch-ek repo-nként.

    Normál módban: csak .venv-es (telepített) branchek.
    Sandbox módban: a SandboxRobots alatti klónok (nincs .venv elvárás).
    """
    repos = get_repository_data()
    installed_keys = get_installed_keys()
    is_sandbox = get_sandbox_mode()
    installed_branches_by_repo: dict[str, list[str]] = {}
    if is_sandbox:
        for key in installed_keys:
            try:
                repo_name, branch_name = key.split('|', 1)
                installed_branches_by_repo.setdefault(repo_name, []).append(branch_name)
            except Exception:
                continue
    result = []
    for repo in repos:
        repo_copy = dict(repo)
        if is_sandbox:
            repo_copy['branches'] = sorted(set(installed_branches_by_repo.get(repo.get('name') or repo_copy.get('name') or '', []) or []))
        else:
            repo_copy['branches'] = [
                branch for branch in repo.get('branches', get_branches_for_repo(repo['name']))
                if f"{repo['name']}|{branch}" in installed_keys
            ]

        # Legutóbbi futás meta (status + timestamp) branch-enként
        try:
            repo_copy['last_run_by_branch'] = _build_last_run_by_branch(repo.get('name') or repo_copy.get('name') or '', list(repo_copy.get('branches') or []))
        except Exception:
            repo_copy['last_run_by_branch'] = {}

        # Kliens oldali megjelenítéshez: release meta a futtatható branchekhez
        try:
            repo_copy['available_branch_releases'] = get_latest_release_by_branch(repo, list(repo_copy.get('branches') or []))
        except Exception:
            repo_copy['available_branch_releases'] = {}
        # Csak akkor adjuk vissza, ha van legalább 1 futtatható branch
        if repo_copy['branches']:
            result.append(repo_copy)
    return jsonify(result)

@app.route('/api/available_repos', methods=['GET'])
def api_available_repos():
    """Csak a letölthető (még nem telepített) branch-ek repo-nként."""
    repos = get_repository_data()
    installed_keys = get_installed_keys()
    is_sandbox = get_sandbox_mode()
    result = []
    for repo in repos:
        repo_copy = dict(repo)
        repo_copy['branches'] = [
            branch for branch in repo.get('branches', get_branches_for_repo(repo['name']))
            if f"{repo['name']}|{branch}" not in installed_keys
        ]

        # Kliens oldali megjelenítéshez: release meta a letölthető branchekhez
        try:
            repo_copy['available_branch_releases'] = get_latest_release_by_branch(repo, list(repo_copy.get('branches') or []))
        except Exception:
            repo_copy['available_branch_releases'] = {}

        # Normál módban csak azok a branchek maradjanak,
        # ahol van kitöltött legfrissebb verzió (release tag).
        # Fejlesztői (sandbox) módban ne szűrjünk release információ alapján.
        if not is_sandbox:
            try:
                rel_map = repo_copy.get('available_branch_releases') or {}
                repo_copy['branches'] = [
                    b for b in (repo_copy.get('branches') or [])
                    if _has_filled_latest_version(rel_map.get(b) or {})
                ]
            except Exception:
                pass

        # Csak akkor adjuk vissza, ha van legalább 1 letölthető branch
        if repo_copy['branches']:
            result.append(repo_copy)
    return jsonify(result)


# Új oldal: repositoryk, branchek és tagek megjelenítése
@app.route('/repos_branches_tags')
def repos_branches_tags_page():
    return render_template('repos_branches_tags.html')


# --- ÚJ API végpont: repositoryk, branchek és tagek listázása ---
@app.route('/api/repos_branches_tags', methods=['GET'])
def api_repos_branches_tags():
    """Visszaadja az összes repo nevét, brancheit és tagjeit.

    A tag-eket branch-onként (tags_by_branch) is visszaadja best-effort módon:
    a GitHub API 'branches-where-head' végponttal megkeresi, mely branch(ek) HEAD-je egyezik a tag commit-jával.
    """
    def _get_github_token() -> str | None:
        token = (os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or '').strip()
        if token:
            return token
        # Fallback: token fájlból (NE commitold; .gitignore-ban van)
        try:
            token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'github_token.txt')
            if os.path.exists(token_path):
                with open(token_path, 'r', encoding='utf-8', errors='replace') as f:
                    token_file = (f.read() or '').strip()
                if token_file:
                    # Hasznos lehet más hívásoknál is a processen belül
                    os.environ.setdefault('GITHUB_TOKEN', token_file)
                    return token_file
        except Exception as e:
            logger.info(f"[GITHUB-TOKEN] Token fájl olvasási hiba: {e}")
        return None

    def _github_headers() -> dict:
        headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'CLA-ssistant'}
        token = _get_github_token()
        if token:
            # GitHub REST v3: klasszikus PAT-hoz 'token', fine-grained-hez is működik.
            headers['Authorization'] = f'token {token}'
        return headers

    def _parse_owner_repo(repo_obj: dict) -> tuple[str, str]:
        full_name = (repo_obj.get('full_name') or '').strip()
        if '/' in full_name:
            owner, name = full_name.split('/', 1)
            return owner, name
        tags_url_val = repo_obj.get('tags_url') or ''
        m = re.search(r'/repos/([^/]+)/([^/]+)/tags', tags_url_val)
        if m:
            return m.group(1), m.group(2)
        return 'lovaszotto', (repo_obj.get('name') or '').strip()

    limit_tags_raw = (request.args.get('limit_tags') or '').strip()
    try:
        limit_tags = int(limit_tags_raw) if limit_tags_raw else 25
    except Exception:
        limit_tags = 25
    limit_tags = max(0, min(limit_tags, 100))

    release_cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'releases_cache.json')

    def _load_release_cache() -> dict:
        try:
            if os.path.exists(release_cache_path):
                with open(release_cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.info(f"[RELEASE-CACHE] Cache olvasási hiba: {e}")
        return {}

    def _save_release_cache(cache_obj: dict) -> None:
        try:
            tmp_path = release_cache_path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(cache_obj, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, release_cache_path)
        except Exception as e:
            logger.info(f"[RELEASE-CACHE] Cache írási hiba: {e}")

    release_cache = _load_release_cache()
    release_cache_dirty = False

    repos = get_repository_data()
    result = []
    headers = _github_headers()

    token_present = bool(_get_github_token())

    for repo in repos:
        repo_name = repo.get('name')
        owner, api_repo_name = _parse_owner_repo(repo)

        release_meta = {
            'source': 'none',
            'status': 'none',
        }

        # Release adatok (tag -> release title/name és dátum)
        release_name_by_tag: dict[str, str] = {}
        release_date_by_tag: dict[str, str] = {}

        # 1) Először próbáljunk cache-ből tölteni (token nélküli futásnál ez a fő útvonal)
        cache_key = f"{owner}/{api_repo_name}"
        cached_entry = release_cache.get(cache_key) if isinstance(release_cache, dict) else None
        if isinstance(cached_entry, dict):
            cached_releases = cached_entry.get('releases')
            if isinstance(cached_releases, dict) and cached_releases:
                for tag_name, meta in cached_releases.items():
                    if not isinstance(meta, dict):
                        continue
                    rel_name = (meta.get('name') or '').strip()
                    rel_date = (meta.get('date') or '').strip()
                    if tag_name and rel_name:
                        release_name_by_tag[tag_name] = rel_name
                    if tag_name and rel_date:
                        release_date_by_tag[tag_name] = rel_date
                release_meta = {'source': 'cache', 'status': 'ok'}

        # 2) Ha van token, frissítsük API-ból (és írjuk a cache-be)
        if token_present:
            try:
                releases_url = f"https://api.github.com/repos/{owner}/{api_repo_name}/releases?per_page=100"
                rr = requests.get(releases_url, headers=headers, timeout=15)
                if rr.status_code == 200:
                    api_release_name_by_tag: dict[str, str] = {}
                    api_release_date_by_tag: dict[str, str] = {}
                    releases_for_cache: dict[str, dict[str, str]] = {}
                    for rel in (rr.json() or []):
                        tag_name = (rel.get('tag_name') or '').strip()
                        rel_name = (rel.get('name') or '').strip()
                        rel_date = (rel.get('published_at') or rel.get('created_at') or '').strip()
                        if not tag_name:
                            continue
                        if rel_name:
                            api_release_name_by_tag[tag_name] = rel_name
                        if rel_date:
                            api_release_date_by_tag[tag_name] = rel_date
                        releases_for_cache[tag_name] = {
                            'name': rel_name,
                            'date': rel_date,
                        }

                    # API eredmény legyen az elsődleges
                    release_name_by_tag = api_release_name_by_tag
                    release_date_by_tag = api_release_date_by_tag
                    release_meta = {'source': 'api', 'status': 'ok'}

                    if isinstance(release_cache, dict):
                        release_cache[cache_key] = {
                            'fetched_at': datetime.now().isoformat(timespec='seconds'),
                            'releases': releases_for_cache,
                        }
                        release_cache_dirty = True
                else:
                    if rr.status_code == 403:
                        release_meta = {'source': release_meta.get('source', 'none'), 'status': 'rate_limited'}
                    else:
                        release_meta = {'source': release_meta.get('source', 'none'), 'status': f"http_{rr.status_code}"}
                    logger.info(f"[RELEASE-QUERY] Release-ek lekérése sikertelen: {releases_url} status={rr.status_code}")
            except Exception as e:
                release_meta = {'source': release_meta.get('source', 'none'), 'status': 'error'}
                logger.info(f"[RELEASE-QUERY] Hiba a release-ek lekérésekor: {owner}/{api_repo_name}: {e}")
        else:
            if release_meta.get('status') != 'ok':
                release_meta = {'source': 'none', 'status': 'missing_token'}

        # Branch-ek és tag-ek git ls-remote alapján (nem GitHub API, így nem fut rate limitbe)
        branches: list[str] = []
        branch_heads: dict[str, str] = {}
        tags: list[str] = []
        tags_by_branch: dict[str, list[str]] = {}

        try:
            if get_sandbox_mode():
                branches = ['main', 'teszt-branch']
                branch_heads = {}
            else:
                git_url = f'https://github.com/lovaszotto/{repo_name}'
                # branchek SHA-val
                r_heads = subprocess.run(
                    ['git', 'ls-remote', '--heads', git_url],
                    capture_output=True, text=True, encoding='utf-8', timeout=30
                )
                if r_heads.returncode == 0:
                    for line in (r_heads.stdout or '').splitlines():
                        if not line.strip():
                            continue
                        sha, ref = line.split('\t', 1)
                        if ref.startswith('refs/heads/'):
                            b = ref.replace('refs/heads/', '')
                            branches.append(b)
                            branch_heads[b] = sha
                else:
                    logger.warning(f"[BRANCH-QUERY] git ls-remote --heads sikertelen: repo={repo_name} returncode={r_heads.returncode} stderr={r_heads.stderr}")

                # tag-ek SHA-val (annotated tag esetén ^{} sor adja a commit SHA-t)
                if limit_tags > 0:
                    r_tags = subprocess.run(
                        ['git', 'ls-remote', '--tags', git_url],
                        capture_output=True, text=True, encoding='utf-8', timeout=30
                    )
                    if r_tags.returncode == 0:
                        tag_commit_sha: dict[str, str] = {}
                        tag_fallback_sha: dict[str, str] = {}
                        for line in (r_tags.stdout or '').splitlines():
                            if not line.strip():
                                continue
                            sha, ref = line.split('\t', 1)
                            if not ref.startswith('refs/tags/'):
                                continue
                            name = ref.replace('refs/tags/', '')
                            if name.endswith('^{}'):
                                tag_name = name[:-3]
                                tag_commit_sha[tag_name] = sha
                            else:
                                tag_name = name
                                tag_fallback_sha.setdefault(tag_name, sha)

                        tags = sorted(tag_fallback_sha.keys())
                        if limit_tags:
                            tags = tags[:limit_tags]

                        # Best-effort hozzárendelés: tag commit SHA == branch head SHA
                        if branch_heads:
                            inv_heads: dict[str, list[str]] = {}
                            for b, sha in branch_heads.items():
                                inv_heads.setdefault(sha, []).append(b)

                            for t in tags:
                                sha = tag_commit_sha.get(t) or tag_fallback_sha.get(t)
                                if not sha:
                                    continue
                                for b in inv_heads.get(sha, []):
                                    tags_by_branch.setdefault(b, []).append(t)
                    else:
                        logger.warning(f"[TAG-QUERY] git ls-remote --tags sikertelen: repo={repo_name} returncode={r_tags.returncode} stderr={r_tags.stderr}")
        except Exception as e:
            logger.warning(f"[BRANCH/TAG-QUERY] Hiba git ls-remote alatt: repo={repo_name}: {e}")

        # Heurisztikus besorolás: ha a tag neve pl. "IKK04_V1.1.0", akkor a "IKK04..." branch-hez rendeljük.
        # Ez segít monorepo jellegű repositoryknál, ahol a tag a robot azonosítóját tartalmazza.
        if tags and branches:
            mapped_tags: set[str] = set()
            for bt in tags_by_branch.values():
                for t in bt:
                    mapped_tags.add(t)

            for t in tags:
                if t in mapped_tags:
                    continue
                prefix = re.split(r'[_-]', t, 1)[0]
                if not prefix:
                    continue
                matched = [b for b in branches if b.startswith(prefix)]
                if matched:
                    for b in matched:
                        tags_by_branch.setdefault(b, []).append(t)
                    mapped_tags.add(t)

        result.append({
            'name': repo_name,
            'branches': branches,
            'tags': tags,
            'tags_by_branch': tags_by_branch,
            'release_name_by_tag': release_name_by_tag,
            'release_date_by_tag': release_date_by_tag,
            'release_meta': release_meta,
        })

    if release_cache_dirty:
        _save_release_cache(release_cache)

    return jsonify(result)


if __name__ == "__main__":
    # Indítsd a Flask szervert, hogy kívülről is elérhető legyen, ne csak localhostról
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
