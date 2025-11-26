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
                    pre.textContent = text || '[üres]';
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
