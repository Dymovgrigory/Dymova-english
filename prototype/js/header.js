/**
 * Header unified block logic: burger menu toggle + dropdown navigation.
 * Extracted from tilda_header_unified.html for testability.
 */

function initBurger(burgerEl, navEl) {
  if (!burgerEl || !navEl) return;
  burgerEl.addEventListener('click', function () {
    navEl.classList.toggle('fxb-open');
    var spans = burgerEl.querySelectorAll('span');
    if (navEl.classList.contains('fxb-open')) {
      spans[0].style.transform = 'rotate(45deg) translate(5px,5px)';
      spans[1].style.opacity = '0';
      spans[2].style.transform = 'rotate(-45deg) translate(6px,-6px)';
    } else {
      spans[0].style.transform = '';
      spans[1].style.opacity = '';
      spans[2].style.transform = '';
    }
  });
}

function initDropdowns(rootEl) {
  if (!rootEl) return;
  rootEl.querySelectorAll('.fxb-dd-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var dd = btn.closest('.fxb-dd');
      var wasOpen = dd.classList.contains('fxb-open');
      rootEl.querySelectorAll('.fxb-dd').forEach(function (d) {
        d.classList.remove('fxb-open');
      });
      if (!wasOpen) dd.classList.add('fxb-open');
    });
  });
  document.addEventListener('click', function () {
    rootEl.querySelectorAll('.fxb-dd').forEach(function (d) {
      d.classList.remove('fxb-open');
    });
  });
}

function hideTildaNativeBlocks() {
  var allRecs = document.querySelectorAll('.r.t-rec');
  allRecs.forEach(function (rec) {
    if (!rec.querySelector('[id^="fxb-"]')) rec.style.display = 'none';
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initBurger, initDropdowns, hideTildaNativeBlocks };
}
