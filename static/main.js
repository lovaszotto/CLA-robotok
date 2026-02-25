// --- Globális állapot: letöltés/futtatás folyamatban ---
// Külön flag-ek: a futtatás zárolása ne tiltsa a letöltést.
var IS_RUN_BUSY = false;
var IS_INSTALL_BUSY = false;

// --- Fallback globális várakozás óra (ha az inline script nem tölt be teljesen) ---
window.__miniWaitState = window.__miniWaitState || {
    ops: {},
    activeKey: null,
    timer: null
};

function _miniWaitEnsureEls() {
    const textEl = document.getElementById('globalWaitTimerText');
    const badgeEl = document.getElementById('globalWaitTimerBadge');
    return { textEl, badgeEl };
}

function _miniWaitFormat(ms) {
    const totalSec = Math.max(0, Math.floor((Number(ms) || 0) / 1000));
    const mm = String(Math.floor(totalSec / 60)).padStart(2, '0');
    const ss = String(totalSec % 60).padStart(2, '0');
    return `${mm}:${ss}`;
}

function _miniWaitApplyStyle(kind) {
    const { badgeEl } = _miniWaitEnsureEls();
    if (!badgeEl) return;
    badgeEl.classList.remove('bg-secondary', 'bg-warning', 'bg-success', 'bg-danger', 'text-dark', 'text-white');
    if (kind === 'run') {
        badgeEl.classList.add('bg-success', 'text-white');
    } else if (kind === 'delete') {
        badgeEl.classList.add('bg-danger', 'text-white');
    } else {
        badgeEl.classList.add('bg-warning', 'text-dark');
    }
}

function _miniWaitTick() {
    const st = window.__miniWaitState || {};
    const key = st.activeKey;
    if (!key || !st.ops || !st.ops[key]) return;
    const op = st.ops[key];
    const { textEl } = _miniWaitEnsureEls();
    if (!textEl) return;
    textEl.textContent = `${op.label} ${_miniWaitFormat(Date.now() - op.startedAt)}`;
    _miniWaitApplyStyle(op.kind);
}

function miniWaitStart(opKey, label, kind) {
    try {
        const key = String(opKey || 'op');
        const st = window.__miniWaitState || (window.__miniWaitState = { ops: {}, activeKey: null, timer: null });
        st.ops[key] = {
            startedAt: Date.now(),
            label: String(label || 'Folyamatban...'),
            kind: String(kind || 'work')
        };
        st.activeKey = key;
        _miniWaitTick();
        if (!st.timer) {
            st.timer = setInterval(_miniWaitTick, 1000);
        }
    } catch (e) {}
}

function miniWaitStop(opKey) {
    try {
        const key = String(opKey || '');
        const st = window.__miniWaitState || {};
        if (st.ops && key) delete st.ops[key];

        const keys = Object.keys(st.ops || {});
        st.activeKey = keys.length ? keys[keys.length - 1] : null;

        if (!st.activeKey) {
            if (st.timer) {
                clearInterval(st.timer);
                st.timer = null;
            }
            const { textEl, badgeEl } = _miniWaitEnsureEls();
            if (textEl) textEl.textContent = 'Kész';
            if (badgeEl) {
                badgeEl.classList.remove('bg-warning', 'bg-success', 'bg-danger', 'text-dark', 'text-white');
                badgeEl.classList.add('bg-secondary');
            }
        } else {
            _miniWaitTick();
        }
    } catch (e) {}
}

async function stopWaitWhenBackendIdle(opKey) {
    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
    const key = String(opKey || '');
    const isRunOp = key.startsWith('run:');
    try {
        let seenBusy = false;
        for (let i = 0; i < 240; i++) {
            let busy = false;
            try {
                const r = await fetch('/api/busy', { cache: 'no-store' });
                const j = await r.json().catch(() => ({}));
                busy = !!(j && j.success && j.busy);
            } catch (e) {
                busy = false;
            }
            if (busy) seenBusy = true;
            if (!busy && (seenBusy || i >= 1)) break;
            await sleep(1000);
        }
    } catch (e) {
        // noop
    } finally {
        try { miniWaitStop(opKey); } catch (e) {}
        try {
            if (typeof stopGlobalWaitStopwatch === 'function') {
                stopGlobalWaitStopwatch(opKey);
            }
        } catch (e) {}
        try {
            if (isRunOp && typeof refreshRunnableRobots === 'function') {
                refreshRunnableRobots();
            }
        } catch (e) {}
    }
}

function setRunButtonsLocked(locked, opKey) {
    try {
        window.__runUiLocks = window.__runUiLocks || new Set();
        const key = String(opKey || 'run');
        if (locked) window.__runUiLocks.add(key);
        else window.__runUiLocks.delete(key);

        const runLocks = window.__runUiLocks;
        const installLocks = window.__installUiLocks || new Set();
        const hasLocks = runLocks.size > 0 || installLocks.size > 0;
        const runButtons = Array.from(document.querySelectorAll('button[onclick*="executeSingleRobot("]'));
        const downloadButtons = Array.from(document.querySelectorAll('button[onclick*="installRobot("], button[onclick*="installSelectedRobots("]'));
        runButtons.forEach((buttonEl) => {
            try {
                buttonEl.disabled = !!hasLocks;
                if (hasLocks) buttonEl.classList.add('disabled');
                else buttonEl.classList.remove('disabled');
            } catch (e) {}
        });
        downloadButtons.forEach((buttonEl) => {
            try {
                buttonEl.disabled = !!hasLocks;
                if (hasLocks) buttonEl.classList.add('disabled');
                else buttonEl.classList.remove('disabled');
            } catch (e) {}
        });
    } catch (e) {}
}

function setInstallButtonsLocked(locked, opKey) {
    try {
        window.__installUiLocks = window.__installUiLocks || new Set();
        const key = String(opKey || 'install');
        if (locked) window.__installUiLocks.add(key);
        else window.__installUiLocks.delete(key);

        const runLocks = window.__runUiLocks || new Set();
        const installLocks = window.__installUiLocks;
        const hasLocks = runLocks.size > 0 || installLocks.size > 0;
        const runButtons = Array.from(document.querySelectorAll('button[onclick*="executeSingleRobot("]'));
        const downloadButtons = Array.from(document.querySelectorAll('button[onclick*="installRobot("], button[onclick*="installSelectedRobots("]'));
        runButtons.forEach((buttonEl) => {
            try {
                buttonEl.disabled = !!hasLocks;
                if (hasLocks) buttonEl.classList.add('disabled');
                else buttonEl.classList.remove('disabled');
            } catch (e) {}
        });
        downloadButtons.forEach((buttonEl) => {
            try {
                buttonEl.disabled = !!hasLocks;
                if (hasLocks) buttonEl.classList.add('disabled');
                else buttonEl.classList.remove('disabled');
            } catch (e) {}
        });
    } catch (e) {}
}

async function sureConfirm({ title = 'Megerősítés', message = '', okText = 'OK', cancelText = 'Mégse', okVariant = 'primary' } = {}) {
    if (typeof showSureBox === 'function') {
        return await showSureBox({ title, message, okText, cancelText, okVariant, showCancel: true });
    }
    if (typeof showToast === 'function') {
        showToast(String(message || ''), 'warning');
    }
    return false;
}

async function sureInfo({ title = 'Információ', message = '', okText = 'OK' } = {}) {
    if (typeof showInfoBox === 'function') {
        await showInfoBox(message, title, okText);
        return true;
    }
    if (typeof showToast === 'function') {
        showToast(String(message || ''), 'info');
    }
    return true;
}

// --- Letöltés gombok kezelése: installRobot ---
if (typeof window.installRobot !== 'function') {
    window.installRobot = async function(repo, branch, btn) {
        if (IS_INSTALL_BUSY) return;
        const opKey = `install:${repo}:${branch}`;
        const ok = await sureConfirm({
            title: 'Robot letöltése',
            message: 'Biztosan le szeretnéd tölteni ezt a robotot?\n\nRepo: ' + repo + (branch ? ('\nRobot: ' + branch) : ''),
            okText: 'Letöltés',
            cancelText: 'Mégse',
            okVariant: 'primary'
        });
        if (!ok) return;
        IS_INSTALL_BUSY = true;
        setInstallButtonsLocked(true, opKey);
        try {
            if (btn) btn.dataset.waitKind = 'download';
            miniWaitStart(opKey, 'Letöltés folyamatban...', 'download');
            if (typeof startGlobalWaitStopwatch === 'function') {
                startGlobalWaitStopwatch(opKey, 'Letöltés folyamatban...');
            }
        } catch (e) {}
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
            return sureInfo({ title: 'Letöltés', message: msg, okText: 'OK' }).then(() => location.reload());
        })
        .catch(err => {
            return sureInfo({ title: 'Hiba', message: 'Hiba a letöltés során: ' + err, okText: 'OK' });
        })
        .finally(() => {
            IS_INSTALL_BUSY = false;
            try {
                stopWaitWhenBackendIdle(opKey);
            } catch (e) {}
            try {
                setInstallButtonsLocked(false, opKey);
            } catch (e) {}
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-download"></i>';
            }
        });
    };
}

// --- Futtatás gomb kezelése: executeSingleRobot ---
if (typeof window.executeSingleRobot !== 'function') {
    window.executeSingleRobot = async function(btn) {
        if (IS_RUN_BUSY) return;
        const repo = btn.getAttribute('data-repo');
        const branch = btn.getAttribute('data-branch');
        const opKey = `run:${repo}:${branch}`;
        const ok = await sureConfirm({
            title: 'Robot futtatása',
            message: 'Biztosan elindítod ezt a robotot?\n\nRepo: ' + repo + (branch ? ('\nRobot: ' + branch) : ''),
            okText: 'Futtatás',
            cancelText: 'Mégse',
            okVariant: 'primary'
        });
        if (!ok) return;
        IS_RUN_BUSY = true;
        setRunButtonsLocked(true, opKey);
        try {
            btn.dataset.waitKind = 'run';
            miniWaitStart(opKey, 'Fut a robot...', 'run');
            if (typeof startGlobalWaitStopwatch === 'function') {
                startGlobalWaitStopwatch(opKey, 'Fut a robot...');
            }
        } catch (e) {}
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
                return sureInfo({ title: 'Futtatás', message: '✅ Futtatás sikeres!', okText: 'OK' });
            } else {
                let msg = (data && data.error) ? data.error : 'Ismeretlen hiba a futtatás során!';
                return sureInfo({ title: 'Futtatás', message: '❌ Futtatás sikertelen!\n\n' + msg, okText: 'OK' });
            }
        })
        .catch(err => {
            return sureInfo({ title: 'Hiba', message: 'Hiba a futtatás során: ' + err, okText: 'OK' });
        })
        .finally(() => {
            IS_RUN_BUSY = false;
            Promise.resolve()
                .then(() => stopWaitWhenBackendIdle(opKey))
                .catch(() => {})
                .finally(() => {
                    try {
                        setRunButtonsLocked(false, opKey);
                        btn.disabled = false;
                        btn.innerHTML = '<i class="bi bi-play-fill"></i>';
                    } catch (e) {}
                });
        });
    };
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

// Log UI állapot
window.__logUiState = window.__logUiState || {
    autoScroll: true,
    wrap: false,
    paused: false,
    lastTextLength: 0,
    rawText: '',
    searchQuery: '',
    activeMatchIndex: 0
};

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeRegExp(s) {
    return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function setServerLogMatchCountText(text) {
    const el = document.getElementById('serverLogMatchCount');
    if (el) el.textContent = text || '';
}

function setActiveLogMatch(index) {
    const pre = document.getElementById('serverLogPre');
    if (!pre) return;

    const marks = pre.querySelectorAll('mark[data-log-match]');
    const total = marks.length;
    if (!total) {
        window.__logUiState.activeMatchIndex = 0;
        return;
    }

    const clamped = ((index % total) + total) % total;
    window.__logUiState.activeMatchIndex = clamped;
    marks.forEach(m => m.classList.remove('active'));
    const active = marks[clamped];
    if (active) {
        active.classList.add('active');
        try { active.scrollIntoView({ block: 'center' }); } catch (e) {}
    }

    setServerLogMatchCountText(`${clamped + 1}/${total}`);
}

function renderServerLog() {
    const pre = document.getElementById('serverLogPre');
    if (!pre) return;

    const raw = (window.__logUiState && window.__logUiState.rawText) ? window.__logUiState.rawText : '';
    const query = (window.__logUiState && window.__logUiState.searchQuery) ? window.__logUiState.searchQuery.trim() : '';

    if (!query) {
        pre.textContent = raw && raw.trim().length ? raw : '[Nincs log tartalom]';
        setServerLogMatchCountText('');
        updateServerLogMeta(pre.textContent || '');
        return;
    }

    const re = new RegExp(escapeRegExp(query), 'gi');
    let match;
    let lastIndex = 0;
    let count = 0;
    let html = '';

    while ((match = re.exec(raw)) !== null) {
        const start = match.index;
        const end = start + match[0].length;
        html += escapeHtml(raw.slice(lastIndex, start));
        html += `<mark data-log-match="1">${escapeHtml(raw.slice(start, end))}</mark>`;
        lastIndex = end;
        count++;
        // Védelem extrém sok találatra
        if (count > 5000) break;
    }
    html += escapeHtml(raw.slice(lastIndex));

    pre.innerHTML = html && html.length ? html : escapeHtml('[Nincs log tartalom]');
    updateServerLogMeta(pre.textContent || '');

    if (count > 0) {
        const desired = (window.__logUiState && Number.isFinite(window.__logUiState.activeMatchIndex))
            ? window.__logUiState.activeMatchIndex
            : 0;
        setActiveLogMatch(Math.min(desired, count - 1));
    } else {
        setServerLogMatchCountText('0/0');
    }
}

function updateServerLogMeta(text) {
    const metaEl = document.getElementById('serverLogMeta');
    if (!metaEl) return;

    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    const timeStr = `${hh}:${mm}:${ss}`;

    const len = (text || '').length;
    const lines = (text && text.length) ? (text.split(/\r\n|\r|\n/).length) : 0;
    metaEl.textContent = `Frissítve: ${timeStr} • Sorok: ${lines} • Karakter: ${len}`;
}

function initServerLogToolbar() {
    const pre = document.getElementById('serverLogPre');
    if (!pre) return;

    const autoScrollEl = document.getElementById('serverLogAutoScroll');
    const wrapEl = document.getElementById('serverLogWrap');
    const pauseEl = document.getElementById('serverLogPause');
    const refreshBtn = document.getElementById('serverLogRefreshBtn');
    const copyBtn = document.getElementById('serverLogCopyBtn');
    const downloadBtn = document.getElementById('serverLogDownloadBtn');

    const searchInput = document.getElementById('serverLogSearch');
    const findPrevBtn = document.getElementById('serverLogFindPrev');
    const findNextBtn = document.getElementById('serverLogFindNext');
    const findClearBtn = document.getElementById('serverLogFindClear');

    if (autoScrollEl) {
        autoScrollEl.checked = !!window.__logUiState.autoScroll;
        autoScrollEl.addEventListener('change', () => {
            window.__logUiState.autoScroll = !!autoScrollEl.checked;
            if (window.__logUiState.autoScroll) {
                try { pre.scrollTop = pre.scrollHeight; } catch (e) {}
            }
        });
    }

    if (wrapEl) {
        wrapEl.checked = !!window.__logUiState.wrap;
        if (wrapEl.checked) pre.classList.add('log-wrap');
        else pre.classList.remove('log-wrap');
        wrapEl.addEventListener('change', () => {
            window.__logUiState.wrap = !!wrapEl.checked;
            if (window.__logUiState.wrap) pre.classList.add('log-wrap');
            else pre.classList.remove('log-wrap');
        });
    }

    if (pauseEl) {
        pauseEl.checked = !!window.__logUiState.paused;
        pauseEl.addEventListener('change', () => {
            window.__logUiState.paused = !!pauseEl.checked;
        });
    }

    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => refreshServerLog(true));
    }

    if (searchInput) {
        searchInput.value = window.__logUiState.searchQuery || '';
        searchInput.addEventListener('input', () => {
            window.__logUiState.searchQuery = searchInput.value || '';
            window.__logUiState.activeMatchIndex = 0;
            renderServerLog();
        });
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (e.shiftKey) setActiveLogMatch((window.__logUiState.activeMatchIndex || 0) - 1);
                else setActiveLogMatch((window.__logUiState.activeMatchIndex || 0) + 1);
            }
            if (e.key === 'Escape') {
                window.__logUiState.searchQuery = '';
                window.__logUiState.activeMatchIndex = 0;
                searchInput.value = '';
                renderServerLog();
            }
        });
    }

    if (findPrevBtn) {
        findPrevBtn.addEventListener('click', () => setActiveLogMatch((window.__logUiState.activeMatchIndex || 0) - 1));
    }
    if (findNextBtn) {
        findNextBtn.addEventListener('click', () => setActiveLogMatch((window.__logUiState.activeMatchIndex || 0) + 1));
    }
    if (findClearBtn) {
        findClearBtn.addEventListener('click', () => {
            window.__logUiState.searchQuery = '';
            window.__logUiState.activeMatchIndex = 0;
            if (searchInput) searchInput.value = '';
            renderServerLog();
        });
    }

    if (copyBtn) {
        copyBtn.addEventListener('click', async () => {
            try {
                const text = pre.textContent || '';
                await navigator.clipboard.writeText(text);
                if (typeof showToast === 'function') showToast('Log másolva.', 'success');
            } catch (e) {
                if (typeof showToast === 'function') showToast('Másolás nem sikerült.', 'danger');
            }
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            try {
                const text = pre.textContent || '';
                const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                const now = new Date();
                const y = now.getFullYear();
                const m = String(now.getMonth() + 1).padStart(2, '0');
                const d = String(now.getDate()).padStart(2, '0');
                const hh = String(now.getHours()).padStart(2, '0');
                const mm = String(now.getMinutes()).padStart(2, '0');
                const ss = String(now.getSeconds()).padStart(2, '0');
                a.href = url;
                a.download = `server-log_${y}${m}${d}_${hh}${mm}${ss}.txt`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(() => URL.revokeObjectURL(url), 500);
            } catch (e) {
                if (typeof showToast === 'function') showToast('Letöltés nem sikerült.', 'danger');
            }
        });
    }
}

function refreshServerLog(force = false) {
    // Csak akkor frissítsen, ha a Log tab aktív
    var logTabPane = document.getElementById('log');
    if (window.__logUiState && window.__logUiState.paused && !force) {
        return;
    }
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
                    const wasNearBottom = (pre.scrollTop + pre.clientHeight) >= (pre.scrollHeight - 30);

                    window.__logUiState.rawText = (text || '');
                    renderServerLog();

                    const autoScroll = !!(window.__logUiState && window.__logUiState.autoScroll);
                    if (autoScroll || wasNearBottom) {
                        try { pre.scrollTop = pre.scrollHeight; } catch (e) {}
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
        initServerLogToolbar();
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
