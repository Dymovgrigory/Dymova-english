/**
 * @jest-environment jsdom
 */
const { initBurger, initDropdowns, hideTildaNativeBlocks } = require('../../prototype/js/header');

describe('Header unified block', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="fxb-hero">
        <button id="fxbBurger"><span></span><span></span><span></span></button>
        <nav id="fxbNav" class="fxb-nav">
          <div class="fxb-dd">
            <button class="fxb-dd-btn">Courses</button>
            <div class="fxb-dd-panel"><a href="/a">A</a></div>
          </div>
          <div class="fxb-dd">
            <button class="fxb-dd-btn">Directions</button>
            <div class="fxb-dd-panel"><a href="/b">B</a></div>
          </div>
        </nav>
      </div>
    `;
  });

  describe('initBurger', () => {
    test('toggles fxb-open class on nav when burger clicked', () => {
      const burger = document.getElementById('fxbBurger');
      const nav = document.getElementById('fxbNav');
      initBurger(burger, nav);

      burger.click();
      expect(nav.classList.contains('fxb-open')).toBe(true);

      burger.click();
      expect(nav.classList.contains('fxb-open')).toBe(false);
    });

    test('transforms burger spans into X when open', () => {
      const burger = document.getElementById('fxbBurger');
      const nav = document.getElementById('fxbNav');
      initBurger(burger, nav);

      burger.click();
      const spans = burger.querySelectorAll('span');
      expect(spans[0].style.transform).toBe('rotate(45deg) translate(5px,5px)');
      expect(spans[1].style.opacity).toBe('0');
      expect(spans[2].style.transform).toBe('rotate(-45deg) translate(6px,-6px)');
    });

    test('resets burger spans when closed', () => {
      const burger = document.getElementById('fxbBurger');
      const nav = document.getElementById('fxbNav');
      initBurger(burger, nav);

      burger.click();
      burger.click();
      const spans = burger.querySelectorAll('span');
      expect(spans[0].style.transform).toBe('');
      expect(spans[1].style.opacity).toBe('');
      expect(spans[2].style.transform).toBe('');
    });

    test('does nothing if elements are null', () => {
      expect(() => initBurger(null, null)).not.toThrow();
    });
  });

  describe('initDropdowns', () => {
    test('opens dropdown on button click', () => {
      const root = document.getElementById('fxb-hero');
      initDropdowns(root);

      const btn = root.querySelectorAll('.fxb-dd-btn')[0];
      btn.click();

      const dd = btn.closest('.fxb-dd');
      expect(dd.classList.contains('fxb-open')).toBe(true);
    });

    test('closes other dropdowns when one is opened', () => {
      const root = document.getElementById('fxb-hero');
      initDropdowns(root);

      const buttons = root.querySelectorAll('.fxb-dd-btn');
      buttons[0].click();
      buttons[1].click();

      const dds = root.querySelectorAll('.fxb-dd');
      expect(dds[0].classList.contains('fxb-open')).toBe(false);
      expect(dds[1].classList.contains('fxb-open')).toBe(true);
    });

    test('closes dropdown when clicking the same button again', () => {
      const root = document.getElementById('fxb-hero');
      initDropdowns(root);

      const btn = root.querySelectorAll('.fxb-dd-btn')[0];
      btn.click();
      btn.click();

      const dd = btn.closest('.fxb-dd');
      expect(dd.classList.contains('fxb-open')).toBe(false);
    });

    test('closes all dropdowns on document click', () => {
      const root = document.getElementById('fxb-hero');
      initDropdowns(root);

      const btn = root.querySelectorAll('.fxb-dd-btn')[0];
      btn.click();
      expect(btn.closest('.fxb-dd').classList.contains('fxb-open')).toBe(true);

      document.body.click();
      const dds = root.querySelectorAll('.fxb-dd');
      dds.forEach(dd => {
        expect(dd.classList.contains('fxb-open')).toBe(false);
      });
    });

    test('does nothing if root is null', () => {
      expect(() => initDropdowns(null)).not.toThrow();
    });
  });

  describe('hideTildaNativeBlocks', () => {
    test('hides .r.t-rec without fxb- children', () => {
      document.body.innerHTML = `
        <div class="r t-rec" id="rec1"><div>Native block</div></div>
        <div class="r t-rec" id="rec2"><div id="fxb-hero">Custom block</div></div>
      `;
      hideTildaNativeBlocks();

      expect(document.getElementById('rec1').style.display).toBe('none');
      expect(document.getElementById('rec2').style.display).not.toBe('none');
    });

    test('handles empty page gracefully', () => {
      document.body.innerHTML = '';
      expect(() => hideTildaNativeBlocks()).not.toThrow();
    });
  });
});
