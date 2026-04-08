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

  // ── Map page filter drawer (map.html only) ───────────────────────────────
  var filterBtn = document.getElementById('mapFilterBtn');
  var leftPanel = document.getElementById('leftPanel');
  var backdrop  = document.getElementById('drawerBackdrop');
  if (!filterBtn || !leftPanel) return;

  function openDrawer() {
    leftPanel.classList.add('drawer-open');
    if (backdrop) backdrop.classList.add('open');
    filterBtn.textContent = '✕ Close';
  }

  function closeDrawer() {
    leftPanel.classList.remove('drawer-open');
    if (backdrop) backdrop.classList.remove('open');
    filterBtn.textContent = '⊞ Filters';
  }

  filterBtn.addEventListener('click', function () {
    leftPanel.classList.contains('drawer-open') ? closeDrawer() : openDrawer();
  });

  if (backdrop) {
    backdrop.addEventListener('click', closeDrawer);
  }


}());
