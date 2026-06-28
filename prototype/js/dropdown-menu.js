/**
 * Standalone dropdown menu logic.
 * Extracted from tilda_dropdown_menu.html for testability.
 */

function initMenu(rootEl, burgerEl, navEl) {
  if (!rootEl || !burgerEl || !navEl) return;

  hideTildaMenus();

  burgerEl.addEventListener('click', function () {
    burgerEl.classList.toggle('fxb-active');
    navEl.classList.toggle('fxb-open');
  });

  rootEl.querySelectorAll('.fxb-has-sub').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var dd = btn.parentNode;
      var wasOpen = dd.classList.contains('fxb-open');
      rootEl.querySelectorAll('.fxb-dropdown').forEach(function (d) {
        d.classList.remove('fxb-open');
      });
      if (!wasOpen) dd.classList.add('fxb-open');
    });
  });

  document.addEventListener('click', function () {
    rootEl.querySelectorAll('.fxb-dropdown').forEach(function (d) {
      d.classList.remove('fxb-open');
    });
  });
}

function hideTildaMenus() {
  document.querySelectorAll('.t228, .t188, .t210, .t-menusub, .t-menu').forEach(function (el) {
    var rec = el.closest('.t-rec');
    if (rec) rec.style.display = 'none';
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initMenu, hideTildaMenus };
}
