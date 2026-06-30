/**
 * @jest-environment jsdom
 */
const { initCardAnimations } = require('../../prototype/js/animations');

describe('Card animations (IntersectionObserver)', () => {
  let mockObserve;
  let mockDisconnect;
  let observerCallback;

  beforeEach(() => {
    mockObserve = jest.fn();
    mockDisconnect = jest.fn();

    global.IntersectionObserver = jest.fn((callback) => {
      observerCallback = callback;
      return {
        observe: mockObserve,
        disconnect: mockDisconnect,
        unobserve: jest.fn(),
      };
    });

    document.body.innerHTML = `
      <div id="fxb-adv">
        <div class="fxb-card">Card 1</div>
        <div class="fxb-card">Card 2</div>
        <div class="fxb-card">Card 3</div>
      </div>
    `;
  });

  afterEach(() => {
    delete global.IntersectionObserver;
    jest.useRealTimers();
  });

  test('creates IntersectionObserver and observes root', () => {
    const root = document.getElementById('fxb-adv');
    initCardAnimations(root);

    expect(global.IntersectionObserver).toHaveBeenCalledTimes(1);
    expect(mockObserve).toHaveBeenCalledWith(root);
  });

  test('adds fxb-in class to cards when intersecting', () => {
    jest.useFakeTimers();
    const root = document.getElementById('fxb-adv');
    initCardAnimations(root, '.fxb-card', { stagger: 100 });

    observerCallback([{ isIntersecting: true }]);
    jest.advanceTimersByTime(300);

    const cards = root.querySelectorAll('.fxb-card');
    cards.forEach(c => {
      expect(c.classList.contains('fxb-in')).toBe(true);
    });
  });

  test('disconnects observer after triggering', () => {
    jest.useFakeTimers();
    const root = document.getElementById('fxb-adv');
    initCardAnimations(root);

    observerCallback([{ isIntersecting: true }]);
    expect(mockDisconnect).toHaveBeenCalled();
  });

  test('does not add class when not intersecting', () => {
    jest.useFakeTimers();
    const root = document.getElementById('fxb-adv');
    initCardAnimations(root);

    observerCallback([{ isIntersecting: false }]);
    jest.advanceTimersByTime(1000);

    const cards = root.querySelectorAll('.fxb-card');
    cards.forEach(c => {
      expect(c.classList.contains('fxb-in')).toBe(false);
    });
  });

  test('uses default threshold 0.2 and stagger 110', () => {
    const root = document.getElementById('fxb-adv');
    initCardAnimations(root);

    expect(global.IntersectionObserver).toHaveBeenCalledWith(
      expect.any(Function),
      { threshold: 0.2 }
    );
  });

  test('respects custom threshold and stagger', () => {
    jest.useFakeTimers();
    const root = document.getElementById('fxb-adv');
    initCardAnimations(root, '.fxb-card', { threshold: 0.5, stagger: 200 });

    expect(global.IntersectionObserver).toHaveBeenCalledWith(
      expect.any(Function),
      { threshold: 0.5 }
    );

    observerCallback([{ isIntersecting: true }]);

    jest.advanceTimersByTime(199);
    const cards = root.querySelectorAll('.fxb-card');
    expect(cards[1].classList.contains('fxb-in')).toBe(false);

    jest.advanceTimersByTime(1);
    expect(cards[1].classList.contains('fxb-in')).toBe(true);
  });

  test('returns null if rootEl is null', () => {
    const result = initCardAnimations(null);
    expect(result).toBeNull();
  });

  test('falls back to adding class directly when IntersectionObserver not available', () => {
    delete global.IntersectionObserver;
    const root = document.getElementById('fxb-adv');
    initCardAnimations(root);

    const cards = root.querySelectorAll('.fxb-card');
    cards.forEach(c => {
      expect(c.classList.contains('fxb-in')).toBe(true);
    });
  });
});
