/**
 * Intersection Observer based card animations.
 * Used by advantages, languages, team, onboarding blocks.
 */

function initCardAnimations(rootEl, selector, options) {
  if (!rootEl) return null;
  var cards = rootEl.querySelectorAll(selector || '.fxb-card');
  var threshold = (options && options.threshold) || 0.2;
  var stagger = (options && options.stagger) || 110;

  if (!('IntersectionObserver' in window)) {
    cards.forEach(function (c) { c.classList.add('fxb-in'); });
    return null;
  }

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        cards.forEach(function (c, i) {
          setTimeout(function () { c.classList.add('fxb-in'); }, i * stagger);
        });
        io.disconnect();
      }
    });
  }, { threshold: threshold });

  if (cards.length > 0) {
    io.observe(rootEl);
  }

  return io;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initCardAnimations };
}
