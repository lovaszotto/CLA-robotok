from flask import Flask, render_template_string, jsonify, request
import json
import subprocess
import os
from datetime import datetime

app = Flask(__name__)

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
    cmd = ['robot', '-d', results_dir, '-v', f'Repo:{repo}', '-v', f'Branch:{branch}', suite_path]

    # A REPO/BRANCH változókat a meglévő teszt "REPO" és "BRANCH" nevű változóihoz igazítjuk
    # Ha a teszt a nagybetűs neveket várja, akkor azt adjuk át
    cmd = ['robot', '-d', results_dir, '-v', f'REPO:{repo}', '-v', f'BRANCH:{branch}', suite_path]

    try:
        print(f"[ROBOT] Futtatás indul: {repo}/{branch} → {results_dir}")
        # Használjunk cp1252 vagy latin-1 kódolást Windows környezetben a UTF-8 hibák elkerülésére
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='cp1252', errors='ignore')
        print(f"[ROBOT] Kész: {repo}/{branch} (exit={result.returncode})")
        # Opcionális: rövid kimenet kiírása a konzolra
        if result.stdout:
            print("[ROBOT][STDOUT]", result.stdout.strip())
        if result.stderr:
            print("[ROBOT][STDERR]", result.stderr.strip())
        return result.returncode, results_dir, result.stdout, result.stderr
    except FileNotFoundError:
        # Ha a 'robot' parancs nem található, próbáljuk meg a python -m robot-ot a rendszer Pythonjával
        py_exe = 'C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe'
        alt_cmd = [py_exe, '-m', 'robot', '-d', results_dir, '-v', f'REPO:{repo}', '-v', f'BRANCH:{branch}', suite_path]
        print(f"[ROBOT] 'robot' nem található, alternatív futtatás: {' '.join(alt_cmd)}")
        result = subprocess.run(alt_cmd, capture_output=True, text=True, encoding='cp1252', errors='ignore')
        print(f"[ROBOT] Kész (alternatív): {repo}/{branch} (exit={result.returncode})")
        if result.stdout:
            print("[ROBOT][STDOUT]", result.stdout.strip())
        if result.stderr:
            print("[ROBOT][STDERR]", result.stderr.strip())
        return result.returncode, results_dir, result.stdout, result.stderr
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
            'C:/Users/oLovasz/AppData/Local/Programs/Python/Python313/python.exe', 
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
    
    return render_template_string(html_template, 
                                repos=repos, 
                                datetime=datetime)

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
    rc, out_dir, _stdout, _stderr = run_robot_with_params(repo, branch)
    status = "ok" if rc == 0 else "fail"
    return jsonify({
        "status": status,
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
    for r in robots:
        repo = (r.get('repo') or '').strip()
        branch = (r.get('branch') or '').strip()
        print(f"EXECUTE SELECTED: {repo}/{branch}")
        if repo and branch:
            rc, out_dir, _stdout, _stderr = run_robot_with_params(repo, branch)
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

def get_html_template():
    """Visszaadja a HTML template-et a parse_repos.py alapján"""
    
    return '''<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Segíthetünk? - Robot Kezelő</title>
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
.repo-card { transition: all 0.3s ease; border: 2px solid transparent; }
.repo-card:hover { transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0,0,0,0.15) !important; border-color: #dc3545; }
.repo-card .card-header { background: linear-gradient(135deg, #dc3545 0%, #e74c3c 50%, #f1aeb5 100%) !important; }
.repo-card .card-title a:hover { text-decoration: underline !important; }
.branches-container { max-height: 300px; overflow-y: auto; }
.branch-checkbox { padding: 8px 12px; margin: 2px 0; border-radius: 6px; transition: background-color 0.2s; }
.branch-checkbox:hover { background-color: #f8f9fa; }
.branch-checkbox input:checked + label { font-weight: bold; color: #dc3545; }
#repoSearch:focus, #branchFilter:focus { border-color: #dc3545; box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25); }
.input-group-text.bg-primary { background: linear-gradient(135deg, #0d6efd 0%, #6610f2 100%) !important; }
.input-group-text.bg-success { background: linear-gradient(135deg, #dc3545 0%, #e74c3c 50%, #f1aeb5 100%) !important; }
.hidden { display: none !important; }
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
<div class="row mb-4">
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
        <button class="btn btn-custom" id="runSelectedBtn" onclick="runSelectedRobots()" disabled>
            <i class="bi bi-play-fill"></i> Futáshoz hozzáad
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
<h3><i class="bi bi-play-circle-fill text-success"></i> Kiválasztott Robotok Futtatása</h3>
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
<div class="card-header bg-info text-white">
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
    const container = document.getElementById('selectedRobotsContainer');
    
    // "Kiválasztott Robotok:" szekció a tetejére
    let html = `
    <div class="text-center mb-4">
        <button class="btn btn-success btn-lg" onclick="executeAllRobots()">
            <i class="bi bi-play-fill"></i> Összes futtatása
        </button>
        <button class="btn btn-outline-secondary btn-lg ms-2" onclick="clearSelection()">
            <i class="bi bi-trash"></i> Lista törlése
        </button>
    </div>`;
    
    html += '<h4><i class="bi bi-list-check"></i> Kiválasztott Robotok:</h4>';
    
    html += '<div class="row">';
    robots.forEach((robot, index) => {
        html += `
        <div class="col-md-6 mb-3">
            <div class="card">
                <div class="card-body">
                    <h6><i class="bi bi-github"></i> ${robot.repo}</h6>
                    <p class="mb-2"><i class="bi bi-git"></i> <strong>Robot:</strong> ${robot.branch}</p>
                    <button class="btn btn-outline-success btn-sm" onclick="executeRobot('${robot.repo}', '${robot.branch}')">
                        <i class="bi bi-play"></i> Futtatás
                    </button>
                </div>
            </div>
        </div>`;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

function executeRobot(repo, branch) {
    // Szerver értesítése a futtatásról
    fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo, branch })
    })
    .then(r => r.json())
    .then(data => {
        console.log('Szerver válasz (execute):', data);
        const msg = document.createElement('div');
        msg.className = 'alert alert-success mt-3';
        const currentTime = new Date().toLocaleString('hu-HU');
        msg.innerHTML = `<i class="bi bi-check-circle"></i> Elküldve a szervernek: <strong>${repo}/${branch}</strong> <small class="text-muted">(${currentTime})</small>`;
        const container = document.getElementById('selectedRobotsContainer');
        container.appendChild(msg);
        setTimeout(() => msg.remove(), 4000);
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
    // Szervernek elküldjük a teljes listát
    fetch('/api/execute-bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ robots })
    })
    .then(r => r.json())
    .then(data => {
        console.log('Szerver válasz (bulk):', data);
        const container = document.getElementById('selectedRobotsContainer');
        const currentTime = new Date().toLocaleString('hu-HU');
        let html = `<div class="alert alert-success"><i class="bi bi-check-circle"></i> Elküldve a szervernek: <small class="text-muted">(${currentTime})</small></div>`;
        html += '<ul class="list-group mb-3">';
        (data.robots || robots).forEach(r => {
            html += `<li class="list-group-item"><i class="bi bi-github"></i> <strong>${r.repo}</strong> / <i class="bi bi-git"></i> ${r.branch}</li>`;
        });
        html += '</ul>';
        container.insertAdjacentHTML('beforeend', html);
    })
    .catch(err => {
        console.error('Hiba (bulk execute):', err);
        alert('Hiba történt a szerver hívása közben.');
    });
}

function clearSelection() {
    document.querySelectorAll('.robot-checkbox:checked').forEach(cb => cb.checked = false);
    updateRunButton();
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
</script>
</body></html>'''

if __name__ == '__main__':
    print("Flask szerver indítása...")
    print("A weboldal elérhető lesz: http://localhost:5000")
    # Reloader kikapcsolása, hogy a shutdown megbízható legyen
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)