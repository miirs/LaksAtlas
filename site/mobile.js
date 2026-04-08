// LaksAtlas — Mobile hamburger menu toggle
// Only activates on mobile, no effect on desktop
(function () {
  var btn = document.getElementById('navHamburger');
  var menu = document.getElementById('navMobileMenu');
  if (!btn || !menu) return;

  btn.addEventListener('click', function () {
    var isOpen = menu.classList.toggle('open');
    btn.classList.toggle('open', isOpen);
    btn.setAttribute('aria-expanded', isOpen);
  });

  // Close menu when a link inside it is tapped
  menu.querySelectorAll('a').forEach(function (link) {
    link.addEventListener('click', function () {
      menu.classList.remove('open');
      btn.classList.remove('open');
    });
  });
}());
