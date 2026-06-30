/**
 * @jest-environment jsdom
 */
const { initFaq } = require('../../prototype/js/faq');

describe('FAQ accordion', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="fxbFaqList">
        <div class="fxb-faq-item">
          <button class="fxb-faq-q">Question 1</button>
          <div class="fxb-faq-a" style="max-height:0"><p>Answer 1</p></div>
        </div>
        <div class="fxb-faq-item">
          <button class="fxb-faq-q">Question 2</button>
          <div class="fxb-faq-a" style="max-height:0"><p>Answer 2</p></div>
        </div>
        <div class="fxb-faq-item">
          <button class="fxb-faq-q">Question 3</button>
          <div class="fxb-faq-a" style="max-height:0"><p>Answer 3</p></div>
        </div>
      </div>
    `;
  });

  test('opens a FAQ item on click', () => {
    const list = document.getElementById('fxbFaqList');
    initFaq(list);

    const btn = list.querySelectorAll('.fxb-faq-q')[0];
    btn.click();

    const item = btn.closest('.fxb-faq-item');
    expect(item.classList.contains('fxb-faq-open')).toBe(true);
  });

  test('sets maxHeight on the answer element', () => {
    const list = document.getElementById('fxbFaqList');
    initFaq(list);

    const btn = list.querySelectorAll('.fxb-faq-q')[0];
    btn.click();

    const answer = btn.closest('.fxb-faq-item').querySelector('.fxb-faq-a');
    expect(answer.style.maxHeight).not.toBe('0');
  });

  test('closes previously open item when another is clicked', () => {
    const list = document.getElementById('fxbFaqList');
    initFaq(list);

    const buttons = list.querySelectorAll('.fxb-faq-q');
    buttons[0].click();
    buttons[1].click();

    const items = list.querySelectorAll('.fxb-faq-item');
    expect(items[0].classList.contains('fxb-faq-open')).toBe(false);
    expect(items[0].querySelector('.fxb-faq-a').style.maxHeight).toBe('0');
    expect(items[1].classList.contains('fxb-faq-open')).toBe(true);
  });

  test('closes item when clicked again (toggle off)', () => {
    const list = document.getElementById('fxbFaqList');
    initFaq(list);

    const btn = list.querySelectorAll('.fxb-faq-q')[0];
    btn.click();
    btn.click();

    const item = btn.closest('.fxb-faq-item');
    expect(item.classList.contains('fxb-faq-open')).toBe(false);
    expect(item.querySelector('.fxb-faq-a').style.maxHeight).toBe('0');
  });

  test('only one item is open at a time', () => {
    const list = document.getElementById('fxbFaqList');
    initFaq(list);

    const buttons = list.querySelectorAll('.fxb-faq-q');
    buttons[0].click();
    buttons[1].click();
    buttons[2].click();

    const openItems = list.querySelectorAll('.fxb-faq-item.fxb-faq-open');
    expect(openItems.length).toBe(1);
    expect(openItems[0]).toBe(buttons[2].closest('.fxb-faq-item'));
  });

  test('does nothing if listEl is null', () => {
    expect(() => initFaq(null)).not.toThrow();
  });
});
