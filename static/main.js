// --- Globális állapot: letöltés/futtatás folyamatban ---
var IS_BUSY = false;

// --- Letöltés gombok kezelése: installRobot ---
function installRobot(repo, branch, btn) {
    if (IS_BUSY) return;
    if (!confirm('Biztosan le szeretnéd tölteni ezt a robotot?\nNév: ' + repo + (branch ? ('\nBranch: ' + branch) : ''))) return;
    IS_BUSY = true;
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    }
    fetch('/api/install_selected', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ robots: [{ repo: repo, branch: branch }] })
    })
    .then(response => {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            return response.json();
        } else {
            return response.text().then(text => {
                throw new Error('A szerver nem JSON választ adott vissza.\nRészletek: ' + text);
            });
        }
    })
    .then(data => {
        let msg = data && data.message ? data.message : 'Letöltés sikeresen befejeződött!';
        alert(msg);
        location.reload();
    })
    .catch(err => {
        alert('Hiba a letöltés során: ' + err);
    })
    .finally(() => {
        IS_BUSY = false;
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-download"></i>';
        }
    });
}

// --- Futtatás gomb kezelése: executeSingleRobot ---
function executeSingleRobot(btn) {
    if (IS_BUSY) return;
    const repo = btn.getAttribute('data-repo');
    const branch = btn.getAttribute('data-branch');
    if (!confirm('Biztosan elindítod ezt a robotot?\nNév: ' + repo + (branch ? ('\nBranch: ' + branch) : ''))) return;
    IS_BUSY = true;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo: repo, branch: branch })
    })
    .then(response => response.json())
    .then(data => {
        if (data && data.success) {
            alert('Futtatás sikeres!');
        } else {
            let msg = (data && data.error) ? data.error : 'Ismeretlen hiba a futtatás során!';
            alert('Hiba: ' + msg);
        }
    })
    .catch(err => {
        alert('Hiba a futtatás során: ' + err);
    })
    .finally(() => {
        IS_BUSY = false;
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-play-fill"></i>';
    });
}
console.log('[LOGTAB] main.js betöltve');
// Menü és oldalváltás logika, logolással

document.addEventListener('DOMContentLoaded', function() {
    console.log('[JS] DOMContentLoaded ESEMÉNY ELINDULT!');
    // Menü linkek eseménykezelői - debug loggal
    ['download','available','results','info','settings','exit'].forEach(function(pageId) {
        var link = document.getElementById('menu-' + pageId);
        if (link) {
            console.log('[JS] Menü esemény regisztrálva:', 'menu-' + pageId);
            link.addEventListener('click', function(e) {
                console.log('[JS] Menü kattintás ELŐTT:', pageId);
                e.preventDefault();
                console.log('[JS] Menü kattintás KÖZBEN, showPage előtt:', pageId);
                showPage(pageId);
                console.log('[JS] Menü kattintás UTÁN, showPage után:', pageId);
                window.location.hash = pageId;
            });
        } else {
            console.warn('[JS] Menü link nem található:', 'menu-' + pageId);
        }
    });

    // Log tab aktiválásakor frissítsen
    var logTab = document.getElementById('log-tab');
    if (logTab) {
        logTab.addEventListener('shown.bs.tab', function() {
            refreshServerLog();
        });
    }
});

// showPage függvény (ha nincs máshol definiálva)
if (typeof showPage !== 'function') {
    function showPage(pageId) {
        console.log('[JS] showPage hívva:', pageId);
        var sections = document.querySelectorAll('.page-section');
        sections.forEach(function(section) {
            section.style.display = 'none';
        });
        var page = document.getElementById('page-' + pageId);
        if (page) {
            page.style.display = 'block';
        } else {
            console.warn('[JS] Nincs ilyen oldal:', pageId);
        }
    }
}

// --- LOG TAB: server.log beolvasása 2 másodpercenként ---

function refreshServerLog() {
    // Csak akkor frissítsen, ha a Log tab aktív
    var logTabPane = document.getElementById('log');
    if (logTabPane && logTabPane.classList.contains('active')) {
        fetch('/server-log')
            .then(r => {
                console.log('[LOGTAB] fetch /server-log status:', r.status);
                return r.text();
            })
            .then(text => {
                const pre = document.getElementById('serverLogPre');
                console.log('[LOGTAB] pre elem:', pre);
                if (pre) {
                    if (text && text.trim().length > 0) {
                        pre.textContent = text;
                    } else {
                        pre.textContent = '[Nincs log tartalom]';
                    }
                } else {
                    console.warn('[LOGTAB] Nincs pre elem!');
                }
            })
            .catch(err => {
                const pre = document.getElementById('serverLogPre');
                if (pre) pre.textContent = '[Hiba a log beolvasásakor: ' + err + "]";
                console.error('[LOGTAB] fetch error:', err);
            });
    } else {
        console.log('[LOGTAB] Log tab nem aktív, nem frissítünk.');
    }
}
setInterval(refreshServerLog, 2000);
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('serverLogPre')) {
        refreshServerLog();
    }
    // Log tab aktiválásakor is frissítsen
    var logTab = document.getElementById('log-tab');
    if (logTab) {
        logTab.addEventListener('shown.bs.tab', function() {
            refreshServerLog();
        });
    }
});
