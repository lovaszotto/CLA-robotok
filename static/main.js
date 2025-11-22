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
