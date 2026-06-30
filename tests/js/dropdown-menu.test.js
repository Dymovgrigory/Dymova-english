/**
 * @jest-environment jsdom
 */
const { initMenu, hideTildaMenus } = require('../../prototype/js/dropdown-menu');

describe('Dropdown menu block', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="fxb-menu">
        <div class="fxb-menu-inner">
          <button class="fxb-burger" id="fxbBurger"><span></span><span></span><span></span></button>
          <nav class="fxb-nav" id="fxbNav">
            <div class="fxb-dropdown">
              <button class="fxb-link fxb-has-sub">Courses</button>
              <div class="fxb-sub"><a href="/a">A</a></div>
            </div>
            <div class="fxb-dropdown">
              <button class="fxb-link fxb-has-sub">Directions</button>
              <div class="fxb-sub"><a href="/b">B</a></div>
            </div>
          </nav>
        </div>
      </div>
    `;
  });

  describe('initMenu', () => {
    test('burger toggles fxb-active on itself and fxb-open on nav', () => {
      const root = document.getElementById('fxb-menu');
      const burger = document.getElementById('fxbBurger');
      const nav = document.getElementById('fxbNav');
      initMenu(root, burger, nav);

      burger.click();
      expect(burger.classList.contains('fxb-active')).toBe(true);
      expect(nav.classList.contains('fxb-open')).toBe(true);

      burger.click();
      expect(burger.classList.contains('fxb-active')).toBe(false);
      expect(nav.classList.contains('fxb-open')).toBe(false);
    });

    test('dropdown opens on sub-button click', () => {
      const root = document.getElementById('fxb-menu');
      const burger = document.getElementById('fxbBurger');
      const nav = document.getElementById('fxbNav');
      initMenu(root, burger, nav);

      const btn = root.querySelectorAll('.fxb-has-sub')[0];
      btn.click();

      expect(btn.parentNode.classList.contains('fxb-open')).toBe(true);
    });

    test('only one dropdown open at a time', () => {
      const root = document.getElementById('fxb-menu');
      const burger = document.getElementById('fxbBurger');
      const nav = document.getElementById('fxbNav');
      initMenu(root, burger, nav);

      const buttons = root.querySelectorAll('.fxb-has-sub');
      buttons[0].click();
      buttons[1].click();

      const dropdowns = root.querySelectorAll('.fxb-dropdown');
      expect(dropdowns[0].classList.contains('fxb-open')).toBe(false);
      expect(dropdowns[1].classList.contains('fxb-open')).toBe(true);
    });

    test('clicking same dropdown button toggles it closed', () => {
      const root = document.getElementById('fxb-menu');
      const burger = document.getElementById('fxbBurger');
      const nav = document.getElementById('fxbNav');
      initMenu(root, burger, nav);

      const btn = root.querySelectorAll('.fxb-has-sub')[0];
      btn.click();
      btn.click();

      expect(btn.parentNode.classList.contains('fxb-open')).toBe(false);
    });

    test('document click closes all dropdowns', () => {
      const root = document.getElementById('fxb-menu');
      const burger = document.getElementById('fxbBurger');
      const nav = document.getElementById('fxbNav');
      initMenu(root, burger, nav);

      root.querySelectorAll('.fxb-has-sub')[0].click();
      document.body.click();

      root.querySelectorAll('.fxb-dropdown').forEach(dd => {
        expect(dd.classList.contains('fxb-open')).toBe(false);
      });
    });

    test('does nothing when root/burger/nav are null', () => {
      expect(() => initMenu(null, null, null)).not.toThrow();
    });
  });

  describe('hideTildaMenus', () => {
    test('hides Tilda native menu records', () => {
      document.body.innerHTML = `
        <div class="t-rec" id="rec100">
          <div class="t228">Tilda menu</div>
        </div>
        <div class="t-rec" id="rec200">
          <div class="t188">Another menu</div>
        </div>
        <div class="t-rec" id="rec300">
          <div class="content">Normal block</div>
        </div>
      `;
      hideTildaMenus();

      expect(document.getElementById('rec100').style.display).toBe('none');
      expect(document.getElementById('rec200').style.display).toBe('none');
      expect(document.getElementById('rec300').style.display).not.toBe('none');
    });
  });
});
