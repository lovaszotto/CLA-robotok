from flask import Flask, render_template_string, jsonify, request
import json
import subprocess
import os
from datetime import datetime

app = Flask(__name__)

# Globális változók
PYTHON_EXECUTABLE = 'C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe'

def run_robot_with_params(repo: str, branch: str):
    """Futtat egy Robot Framework tesztet a megadott REPO/BRANCH paraméterekkel.

    Visszatér: (returncode, results_dir, stdout, stderr)
    """
    # Kimeneti könyvtár létrehozása időbélyeggel, hogy a futások elkülönüljenek
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_repo = (repo or 'unknown').replace('/', '_')
    safe_branch = (branch or 'unknown').replace('/', '_')
    results_dir = os.path.join('results', f'{safe_repo}__{safe_branch}__{timestamp}')
    os.makedirs(results_dir, exist_ok=True)

    suite_path = 'do-selected.robot'
    
    # Elsőbbséget adunk a Python modulos futtatásnak
    cmd = [PYTHON_EXECUTABLE, '-m', 'robot', '-d', results_dir, '-v', f'REPO:{repo}', '-v', f'BRANCH:{branch}', suite_path]

    try:
        print(f"[ROBOT] Futtatás indul: {repo}/{branch} → {results_dir}")
        print(f"[ROBOT] Parancs: {' '.join(cmd)}")
        # Használjunk cp1252 vagy latin-1 kódolást Windows környezetben a UTF-8 hibák elkerülésére
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='cp1252', errors='ignore')
        print(f"[ROBOT] Kész: {repo}/{branch} (exit={result.returncode})")
        # Opcionális: rövid kimenet kiírása a konzolra
        if result.stdout:
            print("[ROBOT][STDOUT]", result.stdout.strip())
        if result.stderr:
            print("[ROBOT][STDERR]", result.stderr.strip())
        return result.returncode, results_dir, result.stdout, result.stderr
    except FileNotFoundError as e:
        print(f"[ROBOT] FileNotFoundError: {e}")
        print(f"[ROBOT] Python vagy robot modul nem található")
        return 1, results_dir, '', f"Robot futtatási hiba: {e}"
    except Exception as e:
        print(f"[ROBOT] Hiba a futtatás közben: {e}")
        return 1, results_dir, '', str(e)

def get_repository_data():
    """Lekéri a repository adatokat"""
    try:
        # Először próbálja meg beolvasni a meglévő fájlt
        if os.path.exists('repos_response.json'):
            with open('repos_response.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Ha nincs fájl, futtatja a fetch_github_repos.py szkriptet
        result = subprocess.run([
            PYTHON_EXECUTABLE, 
            'fetch_github_repos.py', 'lovaszotto'
        ], capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            # Beolvassa a frissen létrehozott fájlt
            with open('repos_response.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"Hiba a repository adatok lekérésében: {result.stderr}")
            return []
    except Exception as e:
        print(f"Kivétel a repository adatok lekérésében: {e}")
        return []

def get_branches_for_repo(repo_name):
    """Lekéri egy repository branch-eit"""
    try:
        # Git parancs futtatása a branch-ek lekéréséhez
        result = subprocess.run(['git', 'ls-remote', '--heads', f'https://github.com/lovaszotto/{repo_name}'], 
                              capture_output=True, text=True, encoding='utf-8')
        
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

@app.route('/')
def index():
    """Főoldal"""
    # Repository adatok lekérése
    repos = get_repository_data()
    
    # Branch adatok hozzáadása minden repository-hoz
    for repo in repos:
        repo['branches'] = get_branches_for_repo(repo['name'])
    
    # HTML template beolvasása és renderelése
    html_template = get_html_template()
    
    response = app.response_class(
        render_template_string(html_template, repos=repos, datetime=datetime),
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
    print(f"EXECUTE REQUEST: {repo}/{branch}")
    # Tényleges futtatás indítása Robot Framework-kel
    if not repo or not branch:
        return jsonify({"status": "error", "message": "Hiányzó repo vagy branch"}), 400
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        'type': 'single'
    }
    execution_results.append(result_entry)
    
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
execution_results = []

@app.route('/api/clear-results', methods=['POST'])
def clear_results():
    """Törli az összes tárolt futási eredményt"""
    global execution_results
    execution_results = []
    return jsonify({"status": "success", "message": "Eredmények törölve"})

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
<title>Segíthetünk? - Robot Kezelő v2.1 - TÖRLÉS GOMBOKKAL - {{ datetime.now().strftime('%H:%M:%S') }}</title>
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
</head><body>

<div class="main-container">
<div class="page-header">
<div class="header-content">
<h1><i class="bi bi-robot"></i> Segíthetünk?</h1>
</div>
</div>

<!-- Tab Navigation -->
<ul class="nav nav-tabs" id="mainTabs" role="tablist">
<li class="nav-item" role="presentation">
<button class="nav-link active" id="download-tab" data-bs-toggle="tab" data-bs-target="#download-pane" type="button" role="tab">
<i class="bi bi-robot"></i> Futtatható robotok
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

<!-- Tab Content -->
<div class="tab-content" id="mainTabContent">
<!-- Futtatható robotok tab -->
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

<!-- Repository kártyák -->
<div class="row" id="repoContainer">
{% for repo in repos %}
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
                {% for branch in repo.branches %}
                <div class="branch-checkbox">
                    <input type="checkbox" class="form-check-input robot-checkbox" 
                           id="branch-{{ repo.name }}-{{ branch }}" 
                           data-repo="{{ repo.name }}" 
                           data-branch="{{ branch }}"
                           onchange="updateRunButton()">
                    <label class="form-check-label ms-2" for="branch-{{ repo.name }}-{{ branch }}">
                        {{ branch }}
                    </label>
                </div>
                {% endfor %}
                {% if not repo.branches %}
                <div class="text-muted">Nincs elérhető robot</div>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endfor %}
</div>

</div>

<!-- Futtatás tab -->
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

<!-- Információ tab -->
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

<!-- Beállítások tab -->
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

<!-- Eredmények tab -->
<div class="tab-pane fade" id="results-pane" role="tabpanel">
<div class="card">
<div class="card-header text-white" style="background: linear-gradient(135deg, #dc3545, #c82333);">
<h5 class="mb-0"><i class="bi bi-list-task"></i> Futási Eredmények</h5>
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

<!-- Eredmények táblázat -->
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

<!-- Lapozás -->
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

<!-- Kilépés tab -->
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

</div>

<!-- jQuery és Bootstrap JavaScript -->
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

<script>
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
    robots.forEach((robot, index) => {
        html += `
        <div class="col-md-6 mb-3">
            <div class="card">
                <div class="card-body">
                    <h6><i class="bi bi-github"></i> ${robot.repo}</h6>
                    <p class="mb-2"><i class="bi bi-git"></i> <strong>Robot:</strong> ${robot.branch}</p>
                    <div class="d-flex" style="gap: 8px;">
                        <button class="btn btn-outline-success btn-sm" onclick="executeRobot('${robot.repo}', '${robot.branch}')" title="Robot futtatása">
                            <i class="bi bi-play"></i> Futtatás
                        </button>
                        <button class="btn btn-outline-danger btn-sm" onclick="removeRobotFromList('${robot.repo}', '${robot.branch}')" title="Eltávolítás a listából">
                            <i class="bi bi-trash"></i> Törlés
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
        
        setTimeout(() => msg.remove(), 10000);
    })
    .catch(err => {
        console.error('Hiba (execute):', err);
        alert('Hiba történt a szerver hívása közben.');
    });
}

function executeAllRobots() {
    const checkboxes = document.querySelectorAll('.robot-checkbox:checked');
    const robots = [];
    checkboxes.forEach(cb => {
        robots.push({ repo: cb.getAttribute('data-repo'), branch: cb.getAttribute('data-branch') });
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
                    <button class="btn btn-sm btn-outline-primary" onclick="viewDetails(${result.id})" title="Részletek">
                        <i class="bi bi-eye"></i>
                    </button>
                    ${result.results_dir ? `
                        <button class="btn btn-sm btn-outline-success ms-1" onclick="openResults('${result.results_dir}')" title="Eredmények megnyitása">
                            <i class="bi bi-folder-open"></i>
                        </button>
                    ` : ''}
                </td>
            </tr>
        `;
    }).join('');
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
    alert(`Eredmények megnyitása: ${resultsDir}`);
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
});

</script>
</body></html>'''

if __name__ == '__main__':
    print("Flask szerver indítása...")
    print("A weboldal elérhető lesz: http://localhost:5000")
    # Reloader kikapcsolása, hogy a shutdown megbízható legyen
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)