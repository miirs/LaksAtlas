// LaksAtlas — Mobile hamburger menu + map drawer toggle
(function () {

  // ── Hamburger nav menu (all pages) ───────────────────────────────────────
  var btn  = document.getElementById('navHamburger');
  var menu = document.getElementById('navMobileMenu');
  if (btn && menu) {
    btn.addEventListener('click', function () {
      var isOpen = menu.classList.toggle('open');
      btn.classList.toggle('open', isOpen);
      btn.setAttribute('aria-expanded', isOpen);
    });
    menu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        menu.classList.remove('open');
        btn.classList.remove('open');
      });
    });
  }

  // ── Map page filter drawer + details sheet (map.html only) ──────────────
  var filterBtn    = document.getElementById('mapFilterBtn');
  var detailsBtn   = document.getElementById('mapDetailsBtn');
  var leftPanel    = document.getElementById('leftPanel');
  var backdrop     = document.getElementById('drawerBackdrop');
  var detailsSheet = document.getElementById('detailsSheet');
  if (!filterBtn || !leftPanel) return;

  function openDrawer() {
    closeDetails();
    leftPanel.classList.add('drawer-open');
    if (backdrop) backdrop.classList.add('open');
    filterBtn.classList.add('active');
    filterBtn.textContent = '✕ Close';
  }

  function closeDrawer() {
    leftPanel.classList.remove('drawer-open');
    if (backdrop) backdrop.classList.remove('open');
    filterBtn.classList.remove('active');
    filterBtn.textContent = '⊞ Filters';
  }

  function openDetails() {
    closeDrawer();
    if (detailsSheet) {
      detailsSheet.classList.add('open');
      if (detailsBtn) detailsBtn.classList.add('active');
    }
  }

  function closeDetails() {
    if (detailsSheet) {
      detailsSheet.classList.remove('open');
      if (detailsBtn) detailsBtn.classList.remove('active');
    }
  }

  filterBtn.addEventListener('click', function () {
    leftPanel.classList.contains('drawer-open') ? closeDrawer() : openDrawer();
  });

  if (detailsBtn) {
    detailsBtn.addEventListener('click', function () {
      detailsSheet && detailsSheet.classList.contains('open') ? closeDetails() : openDetails();
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', closeDrawer);
  }

}());
