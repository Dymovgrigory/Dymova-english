/**
 * FAQ accordion logic.
 * Extracted from tilda_faq.html for testability.
 */

function initFaq(listEl) {
  if (!listEl) return;
  listEl.querySelectorAll('.fxb-faq-q').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var item = btn.closest('.fxb-faq-item');
      var answer = item.querySelector('.fxb-faq-a');
      var wasOpen = item.classList.contains('fxb-faq-open');
      listEl.querySelectorAll('.fxb-faq-item').forEach(function (i) {
        i.classList.remove('fxb-faq-open');
        i.querySelector('.fxb-faq-a').style.maxHeight = '0';
      });
      if (!wasOpen) {
        item.classList.add('fxb-faq-open');
        answer.style.maxHeight = answer.scrollHeight + 'px';
      }
    });
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initFaq };
}
