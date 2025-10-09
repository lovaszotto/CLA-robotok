import json
import subprocess
import webbrowser
import html as html_module
from datetime import datetime

def get_branches(repo_full_name):
    try:
        # UTF-8 kódolás biztosítása Windows-on is
        result = subprocess.run(['git', 'ls-remote', '--heads', f'https://github.com/{repo_full_name}.git'], 
                              capture_output=True, text=True, encoding='utf-8', timeout=30)
        if result.returncode == 0:
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        branch_name = parts[1].replace('refs/heads/', '')
                        branches.append(branch_name)
            return branches
        else:
            return []
    except Exception as e:
        # Debug információ a hibákhoz
        print(f"Hiba a branch-ek lekérésében {repo_full_name}: {e}")
        return []

with open('repos_response.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

html = f'''<!DOCTYPE html>
<html><head><title>GitHub Robotok Kezelő</title>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<!-- Bootstrap CSS -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
<style>
body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
.main-container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); overflow: hidden; }}
.page-header {{ background: linear-gradient(135deg, #198754 0%, #20c997 100%); color: white; padding: 30px; text-align: center; }}
.page-header h1 {{ margin: 0; font-size: 2.5rem; font-weight: 700; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }}
.timestamp {{ margin-top: 10px; opacity: 0.9; font-size: 0.95rem; }}
.nav-tabs {{ border-bottom: 3px solid #198754; background: #f8f9fa; }}
.nav-tabs .nav-link {{ color: #495057; border: none; padding: 15px 25px; font-weight: 600; border-radius: 0; }}
.nav-tabs .nav-link.active {{ background: #198754; color: white; border-bottom: 3px solid #198754; }}
.nav-tabs .nav-link:hover {{ background: #e9ecef; color: #198754; }}
.tab-content {{ padding: 30px; }}
.branch-checkbox {{ margin: 5px 0; display: flex; align-items: center; }}
.branch-checkbox input {{ margin-right: 10px; transform: scale(1.2); }}
.branch-checkbox label {{ cursor: pointer; user-select: none; font-size: 13px; color: #495057; }}
.branch-checkbox label:hover {{ color: #198754; }}
.actions {{ text-align: center; margin: 25px 0; padding: 20px; background: #f8f9fa; border-radius: 10px; }}
.btn-custom {{ background: linear-gradient(135deg, #198754 0%, #20c997 100%); color: white; padding: 12px 25px; border: none; border-radius: 8px; margin: 8px; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.3s ease; box-shadow: 0 3px 6px rgba(0,0,0,0.1); }}
.btn-custom:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); background: linear-gradient(135deg, #157347 0%, #1a936f 100%); }}
.repo-card {{ transition: all 0.3s ease; border: 2px solid transparent; }}
.repo-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0,0,0,0.15) !important; border-color: #198754; }}
.repo-card .card-header {{ background: linear-gradient(135deg, #198754 0%, #20c997 100%) !important; }}
.repo-card .card-title a:hover {{ text-decoration: underline !important; }}
.branches-container {{ max-height: 300px; overflow-y: auto; }}
.branch-checkbox {{ padding: 8px 12px; margin: 2px 0; border-radius: 6px; transition: background-color 0.2s; }}
.branch-checkbox:hover {{ background-color: #f8f9fa; }}
.branch-checkbox input:checked + label {{ font-weight: bold; color: #198754; }}
#repoSearch, #branchFilter {{ border: 2px solid #e9ecef; }}
#repoSearch:focus, #branchFilter:focus {{ border-color: #198754; box-shadow: 0 0 0 0.2rem rgba(25, 135, 84, 0.25); }}
.input-group-text.bg-primary {{ background: linear-gradient(135deg, #0d6efd 0%, #6610f2 100%) !important; }}
.input-group-text.bg-success {{ background: linear-gradient(135deg, #198754 0%, #20c997 100%) !important; }}
.hidden {{ display: none !important; }}
</style>
</head><body>
<div class="main-container">
<div class="page-header">
<h1><i class="bi bi-robot"></i> GitHub Robotok Kezelő</h1>
<div class="timestamp">Generálva: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
</div>

<!-- Tab Navigation -->
<ul class="nav nav-tabs" id="mainTabs" role="tablist">
<li class="nav-item" role="presentation">
<button class="nav-link active" id="download-tab" data-bs-toggle="tab" data-bs-target="#download-pane" type="button" role="tab">
<i class="bi bi-download"></i> Letölthető robotok
</button>
</li>
<li class="nav-item" role="presentation">
<button class="nav-link" id="executable-tab" data-bs-toggle="tab" data-bs-target="#executable-pane" type="button" role="tab">
<i class="bi bi-play-circle"></i> Futtatható robotok
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
</ul>

<!-- Tab Content -->
<div class="tab-content" id="mainTabContent">
<!-- Letölthető robotok tab -->
<div class="tab-pane fade show active" id="download-pane" role="tabpanel">

<!-- Keresés és szűrés -->
<div class="row mb-4">
    <div class="col-md-6">
        <div class="input-group">
            <span class="input-group-text bg-primary text-white"><i class="bi bi-search"></i></span>
            <input type="text" class="form-control" id="repoSearch" placeholder="Repository keresése..." onkeyup="filterRepos()">
        </div>
    </div>
    <div class="col-md-6">
        <div class="input-group">
            <span class="input-group-text bg-success text-white"><i class="bi bi-funnel"></i></span>
            <select class="form-select" id="branchFilter" onchange="filterRepos()">
                <option value="">Összes branch</option>
                <option value="main">Csak main</option>
                <option value="master">Csak master</option>
                <option value="develop">Csak develop</option>
                <option value="CLA">CLA tartalmú</option>
                <option value="CPS">CPS tartalmú</option>
                <option value="IKK">IKK tartalmú</option>
            </select>
        </div>
    </div>
</div>

<div class="actions">
<button class="btn-custom" onclick="selectAll()"><i class="bi bi-check-all"></i> Összes kiválasztása</button>
<button class="btn-custom" onclick="deselectAll()"><i class="bi bi-x-circle"></i> Összes törlése</button>
<button class="btn-custom" onclick="showSelected()"><i class="bi bi-list-check"></i> Kiválasztottak megjelenítése</button>
<button class="btn-custom" onclick="addToExecutableList()"><i class="bi bi-play-circle"></i> Futtatáshoz hozzáad</button>
<button class="btn-custom" onclick="exportSelected()"><i class="bi bi-download"></i> Export JSON</button>
</div>

<div class="row" id="repoCards">'''

for i, repo in enumerate(data, 1):
    branches = get_branches(repo['full_name'])
    branch_html = ''
    for branch in branches:
        branch_id = f"branch_{i}_{branch}".replace('-', '_').replace(' ', '_').replace('/', '_')
        branch_html += f'<div class="branch-checkbox"><input type="checkbox" id="{branch_id}" value="{branch}" data-repo="{repo["name"]}"><label for="{branch_id}">{branch}</label></div>'
    if not branch_html:
        branch_html = '<div class="text-muted fst-italic"><i class="bi bi-exclamation-triangle"></i> Nincs elérhető branch</div>'
    
    branch_count = len(branches) if branches else 0
    branch_count_badge = f'<span class="badge bg-primary rounded-pill">{branch_count}</span>' if branch_count > 0 else '<span class="badge bg-secondary rounded-pill">0</span>'
    
    # Description előkészítése
    description = repo.get("description")
    if description:
        description_html = html_module.escape(str(description))
    else:
        description_html = "Nincs leírás"
    
    html += f'''
    <div class="col-lg-6 col-xl-4 mb-4">
        <div class="card h-100 shadow-sm repo-card" data-repo="{repo["name"]}">
            <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                <h5 class="card-title mb-0 d-flex align-items-center">
                    <i class="bi bi-folder-fill me-2"></i>
                    <a href="https://github.com/{repo["full_name"]}" target="_blank" class="text-white text-decoration-none">
                        {repo["name"]}
                    </a>
                </h5>
                {branch_count_badge}
            </div>
            <div class="card-body">
                <!-- Repository leírás -->
                <div class="mb-2">
                    <small class="text-muted fst-italic">
                        <i class="bi bi-info-circle"></i> {description_html}
                    </small>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="text-muted mb-0">
                        <i class="bi bi-robot"></i> Robotok:
                    </h6>
                    <div>
                        <button class="btn btn-sm btn-outline-success me-1" onclick="selectAllInRepo('{repo["name"]}')" title="Összes robot kiválasztása">
                            <i class="bi bi-check-all"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deselectAllInRepo('{repo["name"]}')" title="Összes robot törlése">
                            <i class="bi bi-x-circle"></i>
                        </button>
                    </div>
                </div>
                <div class="branches-container">
                    {branch_html}
                </div>
            </div>
            <div class="card-footer bg-light">
                <small class="text-muted">
                    <i class="bi bi-github"></i> 
                    <a href="https://github.com/{repo["full_name"]}" target="_blank" class="text-decoration-none">
                        {repo["full_name"]}
                    </a>
                </small>
            </div>
        </div>
    </div>'''

html += f'''</div>

</div>

<!-- Futtatható robotok tab -->
<div class="tab-pane fade" id="executable-pane" role="tabpanel">
<div class="row mb-4">
<div class="col-md-8">
<h3><i class="bi bi-play-circle-fill text-success"></i> Futtatható Robotok</h3>
<p class="text-muted">Itt futtathatja a kiválasztott Robot Framework teszteket közvetlenül a böngészőből.</p>
</div>
<div class="col-md-4">
<button class="btn btn-success btn-lg w-100" onclick="runSelectedRobots()">
<i class="bi bi-play-fill"></i> Kiválasztottak futtatása
</button>
</div>
</div>

<div class="card mb-4">
<div class="card-header bg-primary text-white">
<h5><i class="bi bi-gear-wide-connected"></i> Futtatási Beállítások</h5>
</div>
<div class="card-body">
<div class="row">
<div class="col-md-4">
<label for="pythonPath" class="form-label">Python útvonal:</label>
<input type="text" class="form-control" id="pythonPath" value="python" placeholder="python vagy teljes útvonal">
</div>
<div class="col-md-4">
<label for="outputDir" class="form-label">Kimenet mappa:</label>
<input type="text" class="form-control" id="outputDir" value="./results" placeholder="./results">
</div>
<div class="col-md-4">
<label for="logLevel" class="form-label">Log szint:</label>
<select class="form-select" id="logLevel">
<option value="INFO" selected>INFO</option>
<option value="DEBUG">DEBUG</option>
<option value="WARN">WARN</option>
<option value="ERROR">ERROR</option>
</select>
</div>
</div>
<div class="row mt-3">
<div class="col-md-6">
<div class="form-check">
<input class="form-check-input" type="checkbox" id="includeKeywords" checked>
<label class="form-check-label" for="includeKeywords">Kulcsszavak logolása</label>
</div>
</div>
<div class="col-md-6">
<div class="form-check">
<input class="form-check-input" type="checkbox" id="dryRun">
<label class="form-check-label" for="dryRun">Dry run (csak validáció)</label>
</div>
</div>
</div>
</div>
</div>

<div class="card">
<div class="card-header bg-secondary text-white">
<h5><i class="bi bi-list-task"></i> Futtatandó Robotok Listája</h5>
</div>
<div class="card-body">
<div id="executableRobotsList" class="mb-3">
<div class="alert alert-info">
<i class="bi bi-info-circle"></i> Válasszon ki robotokat a "Letölthető robotok" tab-on a futtatáshoz.
</div>
</div>
<div class="row">
<div class="col-md-6">
<button class="btn btn-outline-primary" onclick="addCustomRobot()">
<i class="bi bi-plus-circle"></i> Egyéni robot hozzáadása
</button>
</div>
<div class="col-md-6 text-end">
<button class="btn btn-outline-danger" onclick="clearExecutableList()">
<i class="bi bi-trash"></i> Lista törlése
</button>
</div>
</div>
</div>
</div>

<div class="card mt-4">
<div class="card-header bg-success text-white">
<h5><i class="bi bi-terminal"></i> Futtatási Eredmények</h5>
</div>
<div class="card-body">
<div id="executionResults">
<div class="alert alert-secondary">
<i class="bi bi-clock"></i> Nincs futtatási eredmény. Indítson el egy tesztet a fenti gombbal.
</div>
</div>
</div>
</div>

</div>

<!-- Információ tab -->
<div class="tab-pane fade" id="info-pane" role="tabpanel">
<div class="row">
<div class="col-md-8">
<h3><i class="bi bi-info-circle-fill text-primary"></i> Alkalmazás Információk</h3>
<div class="card">
<div class="card-body">
<h5>GitHub Robotok Kezelő v1.0</h5>
<p class="card-text">Ez az alkalmazás lehetővé teszi a GitHub repository-k és branch-ek egyszerű kezelését és letöltését.</p>
<ul class="list-unstyled">
<li><i class="bi bi-check-circle-fill text-success"></i> Repository-k listázása</li>
<li><i class="bi bi-check-circle-fill text-success"></i> Branch-ek kezelése</li>
<li><i class="bi bi-check-circle-fill text-success"></i> Keresés és szűrés</li>
<li><i class="bi bi-check-circle-fill text-success"></i> JSON export</li>
<li><i class="bi bi-check-circle-fill text-success"></i> Lapozható táblázat</li>
</ul>
</div>
</div>
</div>
<div class="col-md-4">
<h4><i class="bi bi-graph-up text-info"></i> Statisztikák</h4>
<div class="card bg-light">
<div class="card-body">
<div class="row text-center">
<div class="col-12 mb-3">
<h3 class="text-primary">{len(data)}</h3>
<small class="text-muted">Repository</small>
</div>
<div class="col-12 mb-3">
<h3 class="text-success">{sum(len(get_branches(repo['full_name'])) for repo in data)}</h3>
<small class="text-muted">Összesen branch</small>
</div>
<div class="col-12">
<h3 class="text-warning">{datetime.now().strftime('%H:%M')}</h3>
<small class="text-muted">Utolsó frissítés</small>
</div>
</div>
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
<label for="pageSize" class="form-label">Sorok száma oldalanként</label>
<select class="form-select" id="pageSize">
<option value="5">5</option>
<option value="10" selected>10</option>
<option value="25">25</option>
<option value="50">50</option>
</select>
</div>
</div>
</div>
</div>
<div class="col-md-6">
<div class="card">
<div class="card-header bg-success text-white">
<h5><i class="bi bi-download"></i> Export Beállítások</h5>
</div>
<div class="card-body">
<div class="form-check mb-3">
<input class="form-check-input" type="radio" name="exportFormat" id="jsonFormat" checked>
<label class="form-check-label" for="jsonFormat">JSON formátum</label>
</div>
<div class="form-check mb-3">
<input class="form-check-input" type="radio" name="exportFormat" id="csvFormat">
<label class="form-check-label" for="csvFormat">CSV formátum</label>
</div>
<div class="form-check mb-3">
<input class="form-check-input" type="checkbox" id="includeTimestamp" checked>
<label class="form-check-label" for="includeTimestamp">Időbélyeg hozzáadása</label>
</div>
<button class="btn btn-outline-success" onclick="saveSettings()">
<i class="bi bi-save"></i> Beállítások mentése
</button>
</div>
</div>
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
function filterRepos() {{
    const searchTerm = document.getElementById('repoSearch').value.toLowerCase();
    const branchFilter = document.getElementById('branchFilter').value.toLowerCase();
    const cards = document.querySelectorAll('.repo-card');
    
    cards.forEach(card => {{
        const repoName = card.dataset.repo.toLowerCase();
        const branches = Array.from(card.querySelectorAll('.branch-checkbox label')).map(label => label.textContent.toLowerCase());
        
        let matchesSearch = repoName.includes(searchTerm);
        let matchesBranch = !branchFilter || branches.some(branch => branch.includes(branchFilter));
        
        if (matchesSearch && matchesBranch) {{
            card.parentElement.classList.remove('hidden');
        }} else {{
            card.parentElement.classList.add('hidden');
        }}
    }});
}}

function selectAllInRepo(repoName) {{
    const card = document.querySelector(`[data-repo="${{repoName}}"]`);
    const checkboxes = card.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = true);
}}

function deselectAllInRepo(repoName) {{
    const card = document.querySelector(`[data-repo="${{repoName}}"]`);
    const checkboxes = card.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
}}

function selectAll() {{
    document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
}}

function deselectAll() {{
    document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
}}

function showSelected() {{
    const selected = [];
    document.querySelectorAll('input[type="checkbox"]:checked').forEach(checkbox => {{
        selected.push({{
            repository: checkbox.dataset.repo,
            branch: checkbox.value
        }});
    }});
    
    console.log('Kiválasztott branch-ek:', selected);
    
    if (selected.length === 0) {{
        alert('Nincs kiválasztott branch!');
    }} else {{
        let message = `Kiválasztott branch-ek (összesen: ${{selected.length}} db):\\n\\n`;
        const groupedByRepo = {{}};
        
        selected.forEach(item => {{
            if (!groupedByRepo[item.repository]) {{
                groupedByRepo[item.repository] = [];
            }}
            groupedByRepo[item.repository].push(item.branch);
        }});
        
        for (const [repo, branches] of Object.entries(groupedByRepo)) {{
            message += `📁 ${{repo}}: ${{branches.join(', ')}}\\n`;
        }}
        
        alert(message);
    }}
}}

function exportSelected() {{
    const selected = [];
    document.querySelectorAll('input[type="checkbox"]:checked').forEach(checkbox => {{
        selected.push({{
            repository: checkbox.dataset.repo,
            branch: checkbox.value
        }});
    }});
    
    if (selected.length === 0) {{
        alert('Nincs kiválasztott branch az exportáláshoz!');
        return;
    }}
    
    const jsonData = JSON.stringify(selected, null, 2);
    const blob = new Blob([jsonData], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'kivalasztott_branchek.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    alert(`${{selected.length}} branch exportálva JSON fájlba!`);
}}

function saveSettings() {{
    const settings = {{
        darkMode: document.getElementById('darkMode').checked,
        compactView: document.getElementById('compactView').checked,
        pageSize: document.getElementById('pageSize').value,
        exportFormat: document.querySelector('input[name="exportFormat"]:checked').id,
        includeTimestamp: document.getElementById('includeTimestamp').checked
    }};
    
    localStorage.setItem('robotManagerSettings', JSON.stringify(settings));
    alert('Beállítások elmentve!');
}}

// Futtatható robotok funkciók
let executableRobots = [];

function addToExecutableList() {{
    const selected = [];
    document.querySelectorAll('input[type="checkbox"]:checked').forEach(checkbox => {{
        const repoName = checkbox.dataset.repo;
        const branchName = checkbox.value;
        if (!executableRobots.some(robot => robot.repository === repoName && robot.branch === branchName)) {{
            executableRobots.push({{
                repository: repoName,
                branch: branchName,
                status: 'Várakozik'
            }});
        }}
    }});
    updateExecutableRobotsList();
    
    // Váltás a futtatható robotok tab-ra
    const executableTab = new bootstrap.Tab(document.getElementById('executable-tab'));
    executableTab.show();
}}

function updateExecutableRobotsList() {{
    const container = document.getElementById('executableRobotsList');
    
    if (executableRobots.length === 0) {{
        container.innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Válasszon ki robotokat a "Letölthető robotok" tab-on a futtatáshoz.</div>';
        return;
    }}
    
    let html = '<div class="table-responsive"><table class="table table-sm table-striped"><thead><tr><th>Repository</th><th>Branch</th><th>Státusz</th><th>Műveletek</th></tr></thead><tbody>';
    
    executableRobots.forEach((robot, index) => {{
        const statusClass = robot.status === 'Várakozik' ? 'warning' : robot.status === 'Futtatás alatt' ? 'primary' : robot.status === 'Befejezve' ? 'success' : 'danger';
        html += `<tr>
            <td><strong>${{robot.repository}}</strong></td>
            <td><span class="badge bg-secondary">${{robot.branch}}</span></td>
            <td><span class="badge bg-${{statusClass}}">${{robot.status}}</span></td>
            <td><button class="btn btn-sm btn-outline-danger" onclick="removeFromExecutableList(${{index}})"><i class="bi bi-trash"></i></button></td>
        </tr>`;
    }});
    
    html += '</tbody></table></div>';
    container.innerHTML = html;
}}

function removeFromExecutableList(index) {{
    executableRobots.splice(index, 1);
    updateExecutableRobotsList();
}}

function clearExecutableList() {{
    if (confirm('Biztosan törli az összes robotot a listából?')) {{
        executableRobots = [];
        updateExecutableRobotsList();
    }}
}}

function addCustomRobot() {{
    const repoName = prompt('Repository neve:');
    const branchName = prompt('Branch neve:');
    
    if (repoName && branchName) {{
        if (!executableRobots.some(robot => robot.repository === repoName && robot.branch === branchName)) {{
            executableRobots.push({{
                repository: repoName,
                branch: branchName,
                status: 'Várakozik'
            }});
            updateExecutableRobotsList();
        }} else {{
            alert('Ez a robot már szerepel a listában!');
        }}
    }}
}}

function runSelectedRobots() {{
    if (executableRobots.length === 0) {{
        alert('Nincs robot kiválasztva a futtatáshoz!');
        return;
    }}
    
    const resultsContainer = document.getElementById('executionResults');
    resultsContainer.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Robotok futtatása megkezdődött...</div>';
    
    // Szimuláljuk a robot futtatást (a valóságban itt hívnánk a Robot Framework API-t)
    let completedCount = 0;
    
    executableRobots.forEach((robot, index) => {{
        robot.status = 'Futtatás alatt';
        updateExecutableRobotsList();
        
        // Szimulált futtatás késleltetéssel
        setTimeout(() => {{
            const success = Math.random() > 0.3; // 70% siker arány
            robot.status = success ? 'Befejezve' : 'Hiba';
            completedCount++;
            
            updateExecutableRobotsList();
            
            // Eredmény hozzáadása
            const resultHtml = `
                <div class="alert alert-${{success ? 'success' : 'danger'}} alert-dismissible fade show" role="alert">
                    <strong>${{robot.repository}}/${{robot.branch}}</strong>: 
                    ${{success ? 'Sikeresen befejezve' : 'Hiba történt a futtatás során'}}
                    <small class="d-block mt-1">Idő: ${{new Date().toLocaleTimeString()}}</small>
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
            
            if (completedCount === 1) {{
                resultsContainer.innerHTML = resultHtml;
            }} else {{
                resultsContainer.innerHTML += resultHtml;
            }}
            
            if (completedCount === executableRobots.length) {{
                const summaryHtml = `
                    <div class="alert alert-primary">
                        <h6><i class="bi bi-check-circle"></i> Futtatás befejezve!</h6>
                        <p class="mb-0">Összesen ${{executableRobots.length}} robot futtatva. 
                        Sikeres: ${{executableRobots.filter(r => r.status === 'Befejezve').length}}, 
                        Hibás: ${{executableRobots.filter(r => r.status === 'Hiba').length}}</p>
                    </div>
                `;
                resultsContainer.innerHTML += summaryHtml;
            }}
        }}, (index + 1) * 2000); // 2 másodperc késleltetés robotonként
    }});
}}

function loadSettings() {{
    const savedSettings = localStorage.getItem('robotManagerSettings');
    if (savedSettings) {{
        const settings = JSON.parse(savedSettings);
        document.getElementById('darkMode').checked = settings.darkMode || false;
        document.getElementById('compactView').checked = settings.compactView || false;
        document.getElementById('pageSize').value = settings.pageSize || '10';
        
        if (settings.exportFormat) {{
            document.getElementById(settings.exportFormat).checked = true;
        }}
        document.getElementById('includeTimestamp').checked = settings.includeTimestamp !== false;
    }}
}}

// Beállítások betöltése az oldal betöltésekor
$(document).ready(function() {{
    loadSettings();
}});
</script>
</body></html>'''

with open('repository_branches_table.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('HTML táblázat generálva checkbox-okkal!')
webbrowser.open('repository_branches_table.html')
