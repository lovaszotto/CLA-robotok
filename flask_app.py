from flask import Flask, render_template_string, jsonify, request, send_from_directory
import json
import subprocess
import os
import sys
from datetime import datetime

app = Flask(__name__)

# Globális változók - dinamikus Python executable meghatározása
def get_python_executable():
    """Meghatározza a megfelelő Python executable útvonalát.
    
    Prioritási sorrend:
    1. Virtuális környezet (rf_env\\Scripts\\python.exe)
    2. Aktuális Python interpreter (sys.executable)
    3. Rendszer PATH-ban található python
    """
    # 1. Virtuális környezet ellenőrzése
    venv_python = os.path.join('rf_env', 'Scripts', 'python.exe')
    if os.path.exists(venv_python):
        return os.path.abspath(venv_python)
    
    # 2. Aktuális Python interpreter
    if sys.executable:
        return sys.executable
    
    # 3. Fallback - rendszer python
    return 'python'

PYTHON_EXECUTABLE = get_python_executable()
print(f"[INFO] Használt Python executable: {PYTHON_EXECUTABLE}")

def get_downloaded_keys():
    """Felderíti a results mappában a korábbi futások alapján, mely REPO/BRANCH párokhoz tartozik eredmény.
    A results könyvtárban a mappa neve formátum: {safe_repo}__{safe_branch}__{timestamp}
    ahol a safe_* értékekben a "/" karakterek "_"-ra vannak cserélve.
    Visszaad: set(["{safe_repo}|{safe_branch}", ...])
    """
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
        print(f"[INFO] Nem sikerült a letöltött kulcsokat felderíteni: {e}")
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
                        # Kizárjuk a main branch-et
                        if branch_name != 'main':
                            branches.append(branch_name)
            return branches
        else:
            return []
    except Exception as e:
        print(f"Hiba a branch-ek lekérésében: {e}")
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
        print(f"Kivétel a repository adatok lekérésében: {e}")
        return []


def run_robot_with_params(repo: str, branch: str):
    """Indítja el a Robot Framework futtatást a megadott repo/branch paraméterekkel.

    Visszatér: (returncode, results_dir_rel, stdout, stderr)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_repo = (repo or 'unknown').replace('/', '_')
    safe_branch = (branch or 'unknown').replace('/', '_')
    results_dir_rel = f'{safe_repo}__{safe_branch}__{timestamp}'
    results_dir_abs = os.path.join('results', results_dir_rel)
    os.makedirs(results_dir_abs, exist_ok=True)

    suite_path = 'do-selected.robot'
    cmd = [PYTHON_EXECUTABLE, '-m', 'robot', '-d', results_dir_abs, '-v', f'REPO:{repo}', '-v', f'BRANCH:{branch}', suite_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='cp1252', errors='ignore')
        return result.returncode, results_dir_rel, result.stdout, result.stderr
    except FileNotFoundError as e:
        return 1, results_dir_rel, '', f'FileNotFoundError: {e}'
    except Exception as e:
        return 1, results_dir_rel, '', str(e)

@app.route('/')
def index():
    """Főoldal"""
    # Repository adatok lekérése
    repos = get_repository_data()
    
    # Branch adatok hozzáadása minden repository-hoz
    for repo in repos:
        repo['branches'] = get_branches_for_repo(repo['name'])
    
    # Előre kiszámoljuk a letöltött és letölthető branch-eket repo szinten
    downloaded_keys = get_downloaded_keys()
    for repo in repos:
        safe_repo = repo['name'].replace('/', '_')
        repo['downloaded_branches'] = [
            branch for branch in repo['branches']
            if f"{safe_repo}|{branch.replace('/', '_')}" in downloaded_keys
        ]
        repo['available_branches'] = [
            branch for branch in repo['branches']
            if f"{safe_repo}|{branch.replace('/', '_')}" not in downloaded_keys
        ]
    html_template = get_html_template()
    response = app.response_class(
        render_template_string(html_template, repos=repos, datetime=datetime, downloaded_keys=downloaded_keys),
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
    data = request.get_json(silent=True) or {}
    repo = (data.get('repo') or '').strip()
    branch = (data.get('branch') or '').strip()
    print(f"[EXECUTE] Futtatás kérés: {repo}/{branch}")
    # Tényleges futtatás indítása Robot Framework-kel
    if not repo or not branch:
        print(f"[EXECUTE] HIBA: Hiányzó paraméterek - repo: '{repo}', branch: '{branch}'")
        return jsonify({"status": "error", "message": "Hiányzó repo vagy branch"}), 400
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[EXECUTE] Robot futtatás indítása: {repo}/{branch}")
    rc, out_dir, _stdout, _stderr = run_robot_with_params(repo, branch)
    status = "success" if rc == 0 else "failed"
    print(f"[EXECUTE] Robot futtatás befejezve: rc={rc}, status={status}, dir={out_dir}")
    
    # Eredmény tárolása
    result_entry = {
        'id': len(execution_results) + 1,
        'timestamp': timestamp,
        'repo': repo,
        'branch': branch,
        'status': status,
        'returncode': rc,
        'results_dir': out_dir,
        'type': 'single'
    }
    execution_results.append(result_entry)
    print(f"[EXECUTE] Eredmény hozzáadva: ID={result_entry['id']}, összes eredmény: {len(execution_results)}")
    save_execution_results()  # Mentés fájlba
    print(f"[EXECUTE] Eredmény elmentve fájlba")
    
    return jsonify({
        "status": "ok" if rc == 0 else "fail",
        "repo": repo,
        "branch": branch,
        "returncode": rc,
        "results_dir": out_dir
    })

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
        print(f"EXECUTE SELECTED: {repo}/{branch}")
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
                "repo": repo,
                "branch": branch,
                "returncode": rc,
                "results_dir": out_dir,
                "status": "ok" if rc == 0 else "fail"
            })
        else:
            printed.append({
                "repo": repo,
                "branch": branch,
                "status": "error",
                "message": "Hiányzó repo vagy branch"
            })
    
    # Bulk futtatás után mentés
    if printed:
        save_execution_results()
    
    return jsonify({"status": "ok", "count": len(printed), "robots": printed})

@app.route('/favicon.ico')
def favicon():
    """Favicon kezelése"""
    return '', 204

# Szerver leállítása (Werkzeug)
@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Leállítja a Flask szervert a Kilépés gomb kérésére."""
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        # Nem werkzeug szerver vagy nem elérhető – erőltetett kilépés utólag
        os._exit(0)
    func()
    return jsonify({"status": "shutting down"})

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

    return '''<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Segíthetünk? - Robot Kezelő v2.1</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
<style>
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: white; min-height: 100vh; }
.main-container { max-width: 1400px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); overflow: hidden; }
.page-header { background: linear-gradient(135deg, #dc3545 0%, #e74c3c 50%, #f1aeb5 100%); color: white; padding: 30px; display: flex; align-items: center; justify-content: space-between; }
.page-header .header-content { display: flex; flex-direction: column; align-items: center; flex: 1; }
.page-header h1 { margin: 0; font-size: 2.5rem; font-weight: 700; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.timestamp { margin-top: 10px; opacity: 0.9; font-size: 0.95rem; }
.nav-tabs { border-bottom: 3px solid #dc3545; background: #f8f9fa; }
.nav-tabs .nav-link { color: #495057; border: none; padding: 15px 25px; font-weight: 600; border-radius: 0; }
.nav-tabs .nav-link.active { background: linear-gradient(135deg, #dc3545 0%, #e74c3c 50%, #f1aeb5 100%); color: white; border-bottom: 3px solid #dc3545; }
.nav-tabs .nav-link:hover { background: linear-gradient(135deg, #f1aeb5 0%, #f8d7da 100%); color: #dc3545; }
.tab-content { padding: 30px; }
.card { box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
.actions { text-align: center; margin: 25px 0; padding: 20px; background: #f8f9fa; border-radius: 10px; }
.btn-custom { background: linear-gradient(135deg, #dc3545 0%, #e74c3c 50%, #f1aeb5 100%); color: white; padding: 12px 25px; border: none; border-radius: 8px; margin: 8px; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.3s ease; box-shadow: 0 3px 6px rgba(0,0,0,0.1); }
.btn-custom:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); background: linear-gradient(135deg, #b02a37 0%, #dc3545 50%, #f1aeb5 100%); }
.repo-card { 
    transition: all 0.3s ease; 
    border: 2px solid transparent; 
    background: linear-gradient(135deg, #ffffff 0%, #fdf2f2 100%) !important;
}
.repo-card:hover { 
    transform: translateY(-5px); 
    box-shadow: 0 8px 25px rgba(220,53,69,0.25) !important; 
    border-color: #dc3545; 
}
.repo-card .card-header { 
    background: linear-gradient(135deg, #dc3545 0%, #e74c3c 50%, #c82333 100%) !important; 
    color: white !important;
}
.repo-card .card-title a:hover { text-decoration: underline !important; }
.branches-container { max-height: 300px; overflow-y: auto; }
.branch-checkbox { padding: 8px 12px; margin: 2px 0; border-radius: 6px; transition: background-color 0.2s; }
.branch-checkbox:hover { background-color: #f8f9fa; }
.branch-checkbox input:checked + label { font-weight: bold; color: #dc3545; }
#repoSearch:focus, #branchFilter:focus { border-color: #dc3545; box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25); }
.input-group-text.bg-primary { background: linear-gradient(135deg, #0d6efd 0%, #6610f2 100%) !important; }
.input-group-text.bg-success { background: linear-gradient(135deg, #dc3545 0%, #e74c3c 50%, #f1aeb5 100%) !important; }
.hidden { display: none !important; }
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="main-container">
<div class="page-header">
<div class="header-content">
<h1><i class="bi bi-robot"></i> Segíthetünk?</h1>
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
<button class="nav-link" id="executable-tab" data-bs-toggle="tab" data-bs-target="#executable-pane" type="button" role="tab">
<i class="bi bi-play-circle"></i> Futtatás
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
            <button class="btn btn-custom w-100 d-flex align-items-center justify-content-center" id="runSelectedBtn" onclick="runSelectedRobots()" disabled style="height: 38px;">
                <i class="bi bi-play-fill me-2"></i> Futáshoz hozzáad
            </button>
        </div>
    </div>
    <!-- Branch név label eltávolítva -->
    <!-- Repository kártyák -->
    <div class="row" id="repoContainer">
    {% for repo in repos %}
        {% if repo.downloaded_branches|length > 0 %}
        <div class="col-lg-6 col-xl-4 mb-4 repo-item" data-repo-name="{{ repo.name }}">
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
                        {% for branch in repo.downloaded_branches %}
                            <div class="branch-checkbox">
                                <input type="checkbox" class="form-check-input robot-checkbox" 
                                       id="branch-{{ repo.name }}-{{ branch }}" 
                                       data-repo="{{ repo.name }}" 
                                       data-branch="{{ branch }}"
                                       onchange="updateRunButton()">
                                <label class="form-check-label ms-2" for="branch-{{ repo.name }}-{{ branch }}">
                                    <i class="bi bi-house-fill text-primary me-1" data-bs-toggle="tooltip" data-bs-placement="top" title="Letöltve / van futási eredmény"></i>
                                    <i class="bi bi-check-circle-fill text-success me-1" data-bs-toggle="tooltip" data-bs-placement="top" title="Utolsó futás dátuma:"></i> {{ branch }}
                                </label>
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
            <button class="btn btn-custom w-100 d-flex align-items-center justify-content-center" id="downloadSelectedBtn" onclick="downloadSelectedRobots()" disabled style="height: 38px;">
                <i class="bi bi-download me-2"></i> Letöltéshez hozzáad
            </button>
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
                            <div class="branch-checkbox">
                                <input type="checkbox" class="form-check-input robot-checkbox-available" 
                                       id="branch-available-{{ repo.name }}-{{ branch }}" 
                                       data-repo="{{ repo.name }}" 
                                       data-branch="{{ branch }}"
                                       onchange="updateDownloadButton()">
                                <label class="form-check-label ms-2" for="branch-available-{{ repo.name }}-{{ branch }}">
                                    <i class="bi bi-download text-secondary me-1" data-bs-toggle="tooltip" data-bs-placement="top" title="Letölthető"></i>
                                    <i class="bi bi-check-circle-fill text-success me-1" data-bs-toggle="tooltip" data-bs-placement="top" title="Branch"></i> {{ branch }}
                                </label>
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
<div class="tab-pane fade" id="executable-pane" role="tabpanel">
<div class="d-flex justify-content-between align-items-center mb-3">
<h3 class="mb-0"><i class="bi bi-play-circle-fill text-success"></i> Kiválasztott Robotok Futtatása</h3>
<div id="executionButtons" style="display: none;">
<button class="btn btn-outline-secondary btn-lg me-2" onclick="clearSelection()">
<i class="bi bi-x-circle"></i> Összes törlése
</button>
<button class="btn btn-success btn-lg" onclick="executeAllRobots()">
<i class="bi bi-play-fill"></i> Összes futtatása
</button>
</div>
</div>
<div id="selectedRobotsContainer">
<div class="alert alert-info"><i class="bi bi-info-circle"></i> Válasszon ki robotokat a "Futtatható robotok" tab-on a futtatáshoz.</div>
</div>
</div>
<div class="tab-pane fade" id="info-pane" role="tabpanel">
<h3><i class="bi bi-info-circle-fill text-info"></i> Rendszer Információk</h3>
<div class="row">
<div class="col-md-6">
<div class="card">
<div class="card-header text-white" style="background: linear-gradient(135deg, #dc3545, #c82333);">
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
<input class="form-check-input" type="checkbox" id="darkMode" checked>
<label class="form-check-label" for="darkMode">Sötét téma</label>
</div>
<div class="form-check form-switch mb-3">
<input class="form-check-input" type="checkbox" id="compactView">
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
<div class="form-check mb-3">
<input class="form-check-input" type="checkbox" id="generateReport" checked>
<label class="form-check-label" for="generateReport">Jelentés generálása</label>
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
<div class="card-header text-white" style="background: linear-gradient(135deg, #dc3545, #c82333);">
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
<button class="btn btn-danger btn-lg" onclick="exitApplication()">
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
function downloadSelectedRobots() {
    const checkboxes = document.querySelectorAll('.robot-checkbox-available:checked');
    const selectedRobots = [];
    checkboxes.forEach(checkbox => {
        selectedRobots.push({
            repo: checkbox.getAttribute('data-repo'),
            branch: checkbox.getAttribute('data-branch')
        });
    });
    if (selectedRobots.length > 0) {
        showSelectedRobots(selectedRobots);
        // Váltás a futtatás tab-ra
        document.getElementById('executable-tab').click();
    }
}
// Letölthető robotok tab: gomb engedélyezése, ha van kijelölt
function updateDownloadButton() {
    const checkboxes = document.querySelectorAll('.robot-checkbox-available:checked');
    const btn = document.getElementById('downloadSelectedBtn');
    if (btn) {
        if (checkboxes.length > 0) {
            btn.disabled = false;
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-custom');
            btn.innerHTML = `<i class="bi bi-download me-2"></i> Letöltéshez hozzáad (${checkboxes.length})`;
        } else {
            btn.disabled = true;
            btn.classList.remove('btn-custom');
            btn.classList.add('btn-secondary');
            btn.innerHTML = '<i class="bi bi-download me-2"></i> Letöltéshez hozzáad';
        }
    }
}
// Card-ok kezelése
function filterRepos() {
    const searchTerm = document.getElementById('repoSearch').value.toLowerCase();
    const branchFilter = document.getElementById('branchFilter').value.toLowerCase();
    const repoItems = document.querySelectorAll('.repo-item');
    
    repoItems.forEach(item => {
        const repoName = item.getAttribute('data-repo-name').toLowerCase();
        const branches = item.querySelectorAll('.branch-checkbox label');
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

function updateRunButton() {
    const checkboxes = document.querySelectorAll('.robot-checkbox:checked');
    const btn = document.getElementById('runSelectedBtn');
    
    if (checkboxes.length > 0) {
        btn.disabled = false;
        btn.classList.remove('btn-secondary');
        btn.classList.add('btn-custom');
        btn.innerHTML = `<i class="bi bi-play-fill"></i> Futáshoz hozzáad (${checkboxes.length})`;
    } else {
        btn.disabled = true;
        btn.classList.remove('btn-custom');
        btn.classList.add('btn-secondary');
        btn.innerHTML = '<i class="bi bi-play-circle"></i> Futáshoz hozzáad';
    }
}

function runSelectedRobots() {
    const checkboxes = document.querySelectorAll('.robot-checkbox:checked');
    const selectedRobots = [];
    
    checkboxes.forEach(checkbox => {
        selectedRobots.push({
            repo: checkbox.getAttribute('data-repo'),
            branch: checkbox.getAttribute('data-branch')
        });
    });
    
    if (selectedRobots.length > 0) {
        showSelectedRobots(selectedRobots);
        // Váltás a futtatás tab-ra
        document.getElementById('executable-tab').click();
    }
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
            <div class="card">
                <div class="card-body">
                    <h6><i class="bi bi-github"></i> ${robot.repo}</h6>
                    <p class="mb-2"><i class="bi bi-git"></i> <strong>Robot:</strong> ${robot.branch}</p>
                    <div class="d-flex" style="gap: 8px;">
                        <button class="btn btn-outline-success btn-sm" onclick="executeRobot('${robot.repo}', '${robot.branch}')" title="Robot futtatása">
                                <i class="bi bi-play"></i> Indítás
                        </button>
                        <button class="btn btn-outline-danger btn-sm" onclick="removeRobotFromList('${robot.repo}', '${robot.branch}')" title="Eltávolítás a listából">
                            <i class="bi bi-x-circle"></i> Mégsem
                        </button>
                    </div>
                </div>
            </div>
        </div>`;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

function executeRobot(repo, branch) {
    // "Fut" státusz megjelenítése azonnal
    const container = document.getElementById('selectedRobotsContainer');
    const currentTime = new Date().toLocaleString('hu-HU');
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
        
        setTimeout(() => msg.remove(), 10000);
    })
    .catch(err => {
        console.error('Hiba (execute):', err);
        alert('Hiba történt a szerver hívása közben.');
        
        // Hiba esetén is frissítsük az eredményeket
        loadResults();
    });
}

function executeAllRobots() {
    // Mindkét tabról származó kiválasztott robotokat összegyűjtjük
    const checkboxesRun = document.querySelectorAll('.robot-checkbox:checked');
    const checkboxesDownload = document.querySelectorAll('.robot-checkbox-available:checked');
    const robots = [];
    checkboxesRun.forEach(cb => {
        robots.push({ repo: cb.getAttribute('data-repo'), branch: cb.getAttribute('data-branch') });
    });
    checkboxesDownload.forEach(cb => {
        // Ne legyen duplikáció, ha valaki mindkét tabon kijelölte ugyanazt
        const repo = cb.getAttribute('data-repo');
        const branch = cb.getAttribute('data-branch');
        if (!robots.some(r => r.repo === repo && r.branch === branch)) {
            robots.push({ repo, branch });
        }
    });
    if (robots.length === 0) {
        alert('Nincs kiválasztott robot.');
        return;
    }
    // Ha csak egy robot van kiválasztva, egyedi futtatásként kezeljük
    if (robots.length === 1) {
        const robot = robots[0];
        executeRobot(robot.repo, robot.branch);
        return;
    }
    // "Fut" státusz megjelenítése minden robotnak azonnal (többes futtatás esetén)
    const container = document.getElementById('selectedRobotsContainer');
    const currentTime = new Date().toLocaleString('hu-HU');
    // Csoport fejléc
    const groupHeader = document.createElement('div');
    groupHeader.className = 'alert alert-info mt-3';
    groupHeader.innerHTML = `
        <i class="bi bi-arrow-clockwise spinning"></i> Tömeges futtatás elindult 
        <small class="text-muted">(${currentTime})</small>
        <div class="mt-2">
            <span class="badge bg-primary">Státusz: ${robots.length} robot fut</span>
        </div>
    `;
    container.appendChild(groupHeader);
    // Egyedi kártyák minden robothoz
    robots.forEach(robot => {
        const tempCard = document.createElement('div');
        tempCard.className = 'col-md-6 mb-2 mt-2';
        tempCard.id = `bulk-status-${robot.repo}-${robot.branch}`;
        tempCard.innerHTML = `
            <div class="card border-info">
                <div class="card-body py-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <i class="bi bi-github"></i> <strong>${robot.repo}</strong> / 
                            <i class="bi bi-git"></i> ${robot.branch}
                        </div>
                        <div>
                            <i class="bi bi-arrow-clockwise spinning text-primary"></i> <small>Fut</small>
                        </div>
                    </div>
                </div>
            </div>
        `;
        container.appendChild(tempCard);
    });
    // Szervernek elküldjük a teljes listát
    fetch('/api/execute-bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ robots })
    })
    .then(r => r.json())
    .then(data => {
        console.log('Szerver válasz (bulk):', data);
        // A csoport fejléc eltávolítása
        const groupHeader = container.querySelector('.alert-info');
        if (groupHeader) {
            groupHeader.remove();
        }
        // Egyedi kártyák frissítése
        if (data.robots) {
            data.robots.forEach((result, index) => {
                const robot = robots[index];
                const card = document.getElementById(`bulk-status-${robot.repo}-${robot.branch}`);
                if (card) {
                    const currentTime = new Date().toLocaleString('hu-HU');
                    const statusIcon = getStatusIcon(result.returncode);
                    const statusText = getStatusText(result.returncode);
                    const statusClass = getStatusClass(result.returncode);
                    card.className = 'col-12 mb-2';
                    card.innerHTML = `
                        <div class="alert ${statusClass} mt-3">
                            ${statusIcon} Futtatás befejezve: <strong>${robot.repo}/${robot.branch}</strong> 
                            <small class="text-muted">(${currentTime})</small>
                            <div class="mt-2">
                                <span class="badge bg-secondary">Végső státusz: ${statusText}</span>
                            </div>
                        </div>
                    `;
                    // Sikeres futás esetén törölje a robotot a kiválasztottak közül
                    console.log(`Debug bulk: Return code érték: ${result.returncode} (típus: ${typeof result.returncode}) robot: ${robot.repo}/${robot.branch}`);
                    if (result.returncode === 0) {
                        console.log(`Sikeres tömeges futás észlelve: ${robot.repo}/${robot.branch} - eltávolítás a listából`);
                        setTimeout(() => {
                            removeRobotFromSelection(robot.repo, robot.branch);
                            card.querySelector('.alert').innerHTML += `
                                <div class="mt-2">
                                    <small class="text-success">
                                        <i class="bi bi-check-circle"></i> Robot automatikusan eltávolítva a kiválasztottak közül
                                    </small>
                                </div>
                            `;
                        }, 2000);
                    } else {
                        console.log(`Sikertelen tömeges futás: ${robot.repo}/${robot.branch} - returncode: ${result.returncode}`);
                    }
                }
            });
        }
        
        // Eredmények lista frissítése a tömeges futtatás után
        console.log('Eredmények lista frissítése (bulk után)...');
        loadResults();
    })
    .catch(err => {
        console.error('Tömeges futtatás hiba:', err);
        // Hiba esetén minden kártya frissítése
        robots.forEach(robot => {
            const card = document.getElementById(`bulk-status-${robot.repo}-${robot.branch}`);
            if (card) {
                card.className = 'col-md-6 mb-2 mt-2';
                card.innerHTML = `
                    <div class="card border-danger">
                        <div class="card-body py-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <i class="bi bi-github"></i> <strong>${robot.repo}</strong> / 
                                    <i class="bi bi-git"></i> ${robot.branch}
                                </div>
                                <div class="text-danger">
                                    <i class="bi bi-x-circle"></i> <small>Sikertelen</small>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }
        });
        // Fejléc frissítése
        const groupHeader = container.querySelector('.alert-info');
        if (groupHeader) {
            groupHeader.className = 'alert alert-danger mt-3';
            groupHeader.innerHTML = `
                <i class="bi bi-x-circle"></i> Tömeges futtatás sikertelen
                <div class="mt-2">
                    <span class="badge bg-danger">Hiba történt</span>
                </div>
            `;
        }
        
        // Hiba esetén is frissítsük az eredményeket
        console.log('Eredmények lista frissítése (bulk hiba után)...');
        loadResults();
    });
}

function removeRobotFromSelection(repo, branch) {
    // Keressük meg és törölük a checkbox-ot
    console.log(`removeRobotFromSelection meghívva: ${repo}/${branch}`);
    const selector = `input[data-repo="${repo}"][data-branch="${branch}"]`;
    console.log(`Checkbox selector: ${selector}`);
    const checkbox = document.querySelector(selector);
    console.log(`Checkbox talált:`, checkbox);
    
    if (checkbox) {
        checkbox.checked = false;
        console.log(`Robot eltávolítva a kiválasztottak közül: ${repo}/${branch}`);
        
        // Frissítsük a futtatás gombot
        updateRunButton();
        
        // Ha nincs több kiválasztott robot, frissítsük a kiválasztottak listáját
        const selectedCheckboxes = document.querySelectorAll('.robot-checkbox:checked');
        if (selectedCheckboxes.length === 0) {
            // Gombok elrejtése
            const executionButtons = document.getElementById('executionButtons');
            if (executionButtons) {
                executionButtons.style.display = 'none';
            }
            
            const container = document.getElementById('selectedRobotsContainer');
            container.innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Válasszon ki robotokat a "Futtatható robotok" tab-on a futtatáshoz.</div>';
        } else {
            // Frissítsük a kiválasztottak listáját
            updateSelectedRobotsList();
        }
    } else {
        console.log(`HIBA: Checkbox nem található: ${selector}`);
    }
}

function updateSelectedRobotsList() {
    // Új lista generálása a jelenlegi kiválasztásokból
    const checkboxes = document.querySelectorAll('.robot-checkbox:checked');
    const selectedRobots = [];
    
    checkboxes.forEach(checkbox => {
        selectedRobots.push({
            repo: checkbox.getAttribute('data-repo'),
            branch: checkbox.getAttribute('data-branch')
        });
    });
    
    if (selectedRobots.length > 0) {
        showSelectedRobots(selectedRobots);
    }
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
    updateRunButton();
    
    // Gombok elrejtése
    const executionButtons = document.getElementById('executionButtons');
    if (executionButtons) {
        executionButtons.style.display = 'none';
    }
    
    const container = document.getElementById('selectedRobotsContainer');
    container.innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Válasszon ki robotokat a "Futtatható robotok" tab-on a futtatáshoz.</div>';
}

function saveSettings() {
    const settings = {
        darkMode: document.getElementById('darkMode').checked,
        compactView: document.getElementById('compactView').checked,
        pageSize: document.getElementById('pageSize').value,
        executionMode: document.getElementById('executionMode').value,
        timeout: document.getElementById('timeout').value,
        generateReport: document.getElementById('generateReport').checked
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
    }
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
    // Először próbáljuk leállítani a szervert
    fetch('/shutdown', { method: 'POST' })
        .catch(() => { /* ignore network errors during shutdown */ })
        .finally(() => {
            // Majd bezárás vagy üzenet megjelenítése
            window.close();
            setTimeout(function() {
                document.body.innerHTML = '<div class="text-center mt-5"><h1>Az alkalmazás bezárult</h1><p>Bezárhatja ezt a böngésző fület.</p></div>';
            }, 150);
        });
}

function cancelExit() {
    // Visszatérés az első tabra
    const firstTab = document.querySelector('#download-tab');
    if (firstTab) {
        firstTab.click();
    }
}

// Oldal betöltésekor
document.addEventListener('DOMContentLoaded', function() {
    loadSettings();
    updateRunButton();
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
            } catch (e) {
                console.warn('Nem sikerült bezárni a külső ablakot:', e);
            }
        });
    }
});

// Checkbox változásokra figyelés
document.addEventListener('change', function(e) {
    if (e.target.classList.contains('robot-checkbox')) {
        updateRunButton();
    }
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
    
    tbody.innerHTML = results.map(result => {
        const statusBadge = result.status === 'success' 
            ? '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Sikeres</span>'
            : '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Sikertelen</span>';
            
        const typeBadge = result.type === 'bulk'
            ? '<span class="badge bg-info ms-1">Tömeges</span>'
            : '<span class="badge bg-secondary ms-1">Egyedi</span>';
            
        return `
            <tr>
                <td>${result.timestamp}${typeBadge}</td>
                <td><i class="bi bi-github"></i> ${result.repo}</td>
                <td><i class="bi bi-git"></i> ${result.branch}</td>
                <td>${statusBadge}</td>
                <td>
                    ${result.results_dir ? `<small class="text-muted">${result.results_dir}</small>` : '-'}
                </td>
                <td>
                    ${result.results_dir ? `
                        <button class="btn btn-sm btn-success" onclick="openResults('${result.results_dir}')" title="Megnyitás új ablakban" data-bs-toggle="tooltip" data-bs-placement="top">
                            <i class="bi bi-eye"></i>
                        </button>
                    ` : `
                        <button class="btn btn-sm btn-outline-secondary" onclick="viewDetails(${result.id})" title="Részletek" data-bs-toggle="tooltip" data-bs-placement="top">
                            <i class="bi bi-eye"></i>
                        </button>
                    `}
                </td>
            </tr>
        `;
    }).join('');

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
});

// A branch név ikonját a HTML sablonban adjuk hozzá közvetlenül a label-ben
</script>
</body>
</html>'''

# Alkalmazás indítása, ha közvetlenül futtatjuk a fájlt
if __name__ == '__main__':
    # A debug állapotot kikapcsoljuk, port 5000-en indul
    app.run(host='127.0.0.1', port=5000, debug=False)