/**
 * Фокси — живой 3D-маскот поверх всех страниц dymova-english.ru.
 *
 * Ригнутая модель v2 (Meshy biped, Meshy_AI_Meshy_Merged_Animations-2.glb,
 * 6 клипов: Big_Wave_Hello, Cheer_with_Both_Hands_Up, Happy_jump_f, Running,
 * Shake_It_Off_Dance, Walking). Маскот гуляет по нижней полосе экрана
 * В ГЛУБИНУ сцены (приближается к зрителю и удаляется), а не только
 * влево-вправо по одной плоскости.
 *
 *   Скорость скролла:
 *     скролл вниз                → Walking (шагает вправо)
 *     скролл вверх               → Walking (шагает влево)
 *     быстрый скролл (>2600 px/с)→ Running (бежит по направлению скролла)
 *     резкие рывки туда-сюда     → Happy_jump_f (от неожиданности)
 *   Место на странице:
 *     доскроллил до самого низа  → Shake_It_Off_Dance (танцует)
 *   Курсор и клики:
 *     наведение на CTA-заявку    → Big_Wave_Hello (машет)
 *     клик по CTA                → Cheer_with_Both_Hands_Up («ура, заявка!»)
 *     клик рядом с маскотом      → Happy_jump_f (подпрыгивает)
 *     курсор рядом               → голова следит (кость Head поверх клипа)
 *   Скука (idle, каждые 9–20 сек случайно):
 *     прогулка в случайную точку сцены (Walking, по диагонали — с разворотом
 *     в сторону движения), выход к зрителю (подходит ближе, машет и уходит
 *     обратно), короткое махание (Big_Wave_Hello), редкий танец
 *     (Shake_It_Off_Dance на полной скорости).
 *   Базовый idle: Shake_It_Off_Dance на timeScale 0.18 — еле заметное
 *     покачивание, чтобы не мешать читать (настоящего idle-клипа в наборе нет).
 *
 * Глубина (3D): дорожка — полоса z от depthFar (далеко, маскот выше на экране
 * и меньше) до depthNear (близко, ниже и крупнее). «Пол» под маскотом
 * пересчитывается под его глубину каждый кадр, поэтому дальний маскот стоит
 * выше на экране, ближний — ниже: читается как сцена в перспективе.
 *
 * Не мешает читать: живёт в нижней полосе экрана, клики проходят сквозь
 * canvas, правый нижний угол (чат-виджет) — запретная зона, на скрытой
 * вкладке рендер не идёт, prefers-reduced-motion и слабые устройства —
 * маскот не загружается вовсе. Three.js и GLB подгружаются ПОСЛЕ load +
 * requestIdleCallback, чтобы не бить LCP.
 *
 * Подключение (importmap обязан быть раньше любого module-скрипта на странице):
 *   <script type="importmap">{"imports":{"three":"…","three/addons/":"…"}}</script>
 *   <script>window.FOXI_CONFIG = { modelUrl: '/mascot/foxi-rigged.glb' };</script>
 *   <script type="module" src="/mascot/mascot.js"></script>
 */

const CFG = Object.assign(
  {
    modelUrl: './foxi-rigged.glb',
    dracoPath: 'https://www.gstatic.com/draco/versioned/decoders/1.5.7/',
    headBone: 'head', // подстрока имени кости головы (слежение за мышью)
    height: 1.0, // высота маскота в мировых юнитах на ближнем плане (масштаб авто)
    mobileHeight: 0.72, // высота на узких экранах
    walkMargin: 0.86, // ширина «дорожки» (доля полуширины сцены)
    reserveRightPx: 120, // запретная зона справа (чат-виджет), px
    walkSpeed: 1.7, // юнитов/сек при прогулке
    runSpeed: 3.6, // юнитов/сек при беге
    faceOffset: 0, // добавка к yaw, если лицо не в +Z (рад)
    depthNear: 1.6, // ближняя кромка дорожки (мир, z; камера на z=8)
    depthFar: -3.2, // дальняя кромка дорожки
    screenFracFar: 0.78, // где «пол» дальней кромки (доля полувысоты от низа)
    screenFracNear: 0.95, // где «пол» ближней кромки
    minDelay: 9, // минимальная пауза между «поступками», сек
    maxDelay: 20, // максимальная пауза, сек
    zIndex: 9998,
    hideUnderWidth: 0, // >0 — не показывать на экранах уже этого значения
  },
  window.FOXI_CONFIG || {}
);

// Имена клипов в GLB v2 (Meshy Merged Animations-2, 6 клипов)
const CLIP = {
  idle: 'Shake_It_Off_Dance', // на timeScale 0.18 — ненавязчивое покачивание
  walk: 'Walking',
  run: 'Running',
  jump: 'Happy_jump_f',
  wave: 'Big_Wave_Hello',
  cheer: 'Cheer_with_Both_Hands_Up',
  dance: 'Shake_It_Off_Dance', // на полной скорости — танец
};

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const weakDevice =
  (navigator.hardwareConcurrency && navigator.hardwareConcurrency < 4) ||
  (navigator.deviceMemory && navigator.deviceMemory < 4) ||
  (navigator.connection && navigator.connection.saveData);

if (
  !reducedMotion &&
  !weakDevice &&
  !(CFG.hideUnderWidth > 0 && window.innerWidth < CFG.hideUnderWidth)
) {
  // Тяжёлое (three.js ~600 КБ + GLB) — только после полной загрузки страницы
  const boot = () => {
    const ric = window.requestIdleCallback || ((cb) => setTimeout(cb, 1200));
    ric(() => init().catch((e) => console.warn('[foxi] не запустился:', e)));
  };
  if (document.readyState === 'complete') boot();
  else window.addEventListener('load', boot, { once: true });
}

async function init() {
  const THREE = await import('three');
  const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
  const { DRACOLoader } = await import('three/addons/loaders/DRACOLoader.js');

  // --- canvas поверх всего сайта, клики проходят сквозь ---
  const canvas = document.createElement('canvas');
  canvas.id = 'foxi-mascot-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  Object.assign(canvas.style, {
    position: 'fixed',
    inset: '0',
    width: '100vw',
    height: '100vh',
    pointerEvents: 'none',
    zIndex: String(CFG.zIndex),
    opacity: '0',
    transition: 'opacity 0.8s ease',
  });
  document.body.appendChild(canvas);

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  } catch (e) {
    canvas.remove();
    return; // нет WebGL — тихо уходим
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.set(0, 0, 8);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xd9c8ff, 1.05));
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.4);
  dirLight.position.set(3, 6, 6);
  scene.add(dirLight);

  // --- геометрия «дорожки» с глубиной ---
  // Все величины зависят от z: дальше → больше полувысота кадра, «пол» выше
  // на экране (меньшая доля от низа), маскот визуально меньше (перспектива).
  const tanHalf = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const view = {
    aspect: camera.aspect,
    halfHAt: (z) => tanHalf * (camera.position.z - z),
    halfWAt: (z) => tanHalf * (camera.position.z - z) * camera.aspect,
    // «пол» под маскотом на глубине z (мир, y)
    groundYAt: (z) => {
      const t = THREE.MathUtils.clamp(
        (z - CFG.depthFar) / (CFG.depthNear - CFG.depthFar),
        0,
        1
      );
      const frac = CFG.screenFracFar + (CFG.screenFracNear - CFG.screenFracFar) * t;
      return -tanHalf * (camera.position.z - z) * frac;
    },
    // границы дорожки по x на глубине z
    xLimitsAt: (z) => {
      const halfW = tanHalf * (camera.position.z - z) * camera.aspect;
      const worldPerPx = (halfW * 2) / window.innerWidth;
      const minX = -halfW * CFG.walkMargin;
      let maxX = halfW * CFG.walkMargin - CFG.reserveRightPx * worldPerPx;
      if (maxX < 0) maxX = 0;
      return { minX, maxX };
    },
  };

  // --- состояние ---
  const state = {
    ready: false,
    mode: 'idle', // idle | oneshot | scrollwalk | stroll
    oneshotClip: null, // имя клипа текущего one-shot
    rig: null, // внешняя группа: позиция (x,y,z) + yaw
    mixer: null,
    actions: {}, // имя клипа -> AnimationAction
    active: null, // текущий AnimationAction
    headBone: null,
    tailBone: null, // кость хвоста (процедурное управление)
    tailQuat: null, // сглаженная мировая ориентация хвоста
    lookWeight: 0,
    time: 0,
    behaviorTimer: null,
    strollTarget: { x: 0, z: 0 }, // куда гуляем в режиме stroll
    afterArrive: null, // колбэк по приходе в точку stroll
    cooldowns: {}, // имя -> timestamp (сек), антиспам разовых реакций
    yaw: 0, // текущий yaw (сглаживаем сами)
  };

  const mouse = new THREE.Vector2(0, 0);
  window.addEventListener('mousemove', (e) => {
    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
  }, { passive: true });

  function cooldownOk(key, sec) {
    const last = state.cooldowns[key] || -1e9;
    return state.time - last > sec;
  }
  function touch(key) {
    state.cooldowns[key] = state.time;
  }

  // --- скролл: скорость, направление, рывки, «дно» страницы ---
  const scroll = {
    lastY: window.scrollY,
    lastT: performance.now(),
    vel: 0, // px/сек, сглаженная
    dir: 1,
    activeUntil: 0, // performance.now(), до когда скролл считается идущим
    flips: [], // timestamps смен направления
  };
  window.addEventListener('scroll', () => {
    const now = performance.now();
    const y = window.scrollY;
    const dy = y - scroll.lastY;
    const dt = Math.max(now - scroll.lastT, 1);
    const v = (dy / dt) * 1000;
    scroll.vel = scroll.vel * 0.6 + v * 0.4;
    scroll.lastY = y;
    scroll.lastT = now;
    scroll.activeUntil = now + 260;
    const dir = Math.sign(dy);
    if (dir && dir !== scroll.dir) {
      scroll.flips.push(now);
      if (scroll.flips.length > 8) scroll.flips.shift();
      scroll.dir = dir;
    }
    // «Дно» страницы — танец (раз в 60 сек)
    if (
      state.ready &&
      y + window.innerHeight > document.documentElement.scrollHeight - 120 &&
      (state.mode === 'idle' || state.mode === 'scrollwalk') &&
      cooldownOk('bottomDance', 60)
    ) {
      touch('bottomDance');
      startOneshot(CLIP.dance);
    }
  }, { passive: true });

  // --- реакции на элементы сайта ---
  const CTA_SELECTOR = '[data-fxb-zayavka], .fxb-btn-main, a[href*="zayavka"]';
  document.addEventListener('mouseover', (e) => {
    if (!state.ready || state.mode !== 'idle') return;
    if (e.target.closest && e.target.closest(CTA_SELECTOR) && cooldownOk('ctaWave', 10)) {
      touch('ctaWave');
      startOneshot(CLIP.wave);
    }
  });
  document.addEventListener('pointerdown', (e) => {
    if (!state.ready) return;
    if (e.target.closest && e.target.closest(CTA_SELECTOR)) {
      if (state.mode === 'idle' && cooldownOk('ctaClick', 10)) {
        touch('ctaClick');
        startOneshot(CLIP.cheer, { timeScale: 1.3 });
      }
      return;
    }
    // клик рядом с маскотом — подпрыгивает (иногда машет)
    if (state.rig && state.mode === 'idle') {
      const p = state.rig.position;
      const halfW = view.halfWAt(p.z);
      const halfH = view.halfHAt(p.z);
      const mx = ((e.clientX / window.innerWidth) * 2 - 1) * halfW;
      const my = (-(e.clientY / window.innerHeight) * 2 + 1) * halfH;
      if (Math.hypot(mx - p.x, my - p.y) < 1.6 && cooldownOk('poke', 3)) {
        touch('poke');
        startOneshot(Math.random() < 0.75 ? CLIP.jump : CLIP.wave);
      }
    }
  });

  // --- загрузка модели ---
  const draco = new DRACOLoader().setDecoderPath(CFG.dracoPath);
  const loader = new GLTFLoader().setDRACOLoader(draco);

  const gltf = await new Promise((resolve, reject) =>
    loader.load(CFG.modelUrl, resolve, undefined, reject)
  );
  const model = gltf.scene;

  // Нормализация: если модель Z-up — ставим на «пол»
  const rawBox = new THREE.Box3().setFromObject(model);
  const rawSize = rawBox.getSize(new THREE.Vector3());
  if (rawSize.z > rawSize.y * 1.5) model.rotation.x = -Math.PI / 2;

  // Центрируем по X/Z, опора — на подошву
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  model.position.x -= center.x;
  model.position.z -= center.z;
  model.position.y -= box.min.y;

  const size = box.getSize(new THREE.Vector3());
  const wanted = window.innerWidth < 768 ? CFG.mobileHeight : CFG.height;
  const k = wanted / Math.max(size.y, 0.001);

  const body = new THREE.Group();
  body.add(model);
  body.scale.setScalar(k);

  const rig = new THREE.Group();
  rig.add(body);
  rig.add(makeBlobShadow());
  // стартует у левой кромки на средней глубине — не загораживает контент
  const startZ = (CFG.depthNear + CFG.depthFar) / 2;
  rig.position.set(view.xLimitsAt(startZ).minX * 0.8, view.groundYAt(startZ), startZ);
  scene.add(rig);
  state.rig = rig;

  // --- анимации ---
  state.mixer = new THREE.AnimationMixer(model);
  for (const clip of gltf.animations) {
    state.actions[clip.name] = state.mixer.clipAction(clip);
  }
  state.mixer.addEventListener('finished', (e) => {
    if (state.mode === 'oneshot' && e.action === state.active) endOneshot();
  });

  // кость головы — слежение за мышью; кость хвоста — процедурное управление
  // (хвост привязан к собственной кости Tail, в клипах её нет — держим его
  // сзади сами, иначе он жёстко крутится вместе с Hips и лезет вперёд)
  const headNeedle = CFG.headBone.toLowerCase();
  model.traverse((o) => {
    if (!state.headBone && o.isBone && o.name.toLowerCase().includes(headNeedle)) {
      state.headBone = o;
    }
    if (!state.tailBone && o.isBone && o.name === 'Tail') {
      state.tailBone = o;
    }
  });
  state.tailQuat = new THREE.Quaternion(); // сглаженная желаемая мировая ориентация хвоста

  console.info('[foxi] skeletal-режим v2, клипы:', gltf.animations.map((c) => c.name).join(', '));

  state.ready = true;
  playLoop(CLIP.idle, { timeScale: 0.18 }); // базовый idle — еле заметное покачивание
  canvas.style.opacity = '1';
  scheduleBehavior(3); // первый «поступок» почти сразу — маскот оживает

  // Внешний API для сайта: window.FOXI
  window.FOXI = {
    wave: () => state.mode === 'idle' && startOneshot(CLIP.wave),
    jump: () => state.mode === 'idle' && startOneshot(CLIP.jump),
    dance: () => state.mode === 'idle' && startOneshot(CLIP.dance),
    walk: () => state.mode === 'idle' && startStroll(),
    visit: () => state.mode === 'idle' && startVisit(), // подойти к зрителю и помахать
    config: CFG, // отладка/тюнинг
    _state: state, // отладка
    _scroll: scroll, // отладка
  };

  function makeBlobShadow() {
    const c = document.createElement('canvas');
    c.width = c.height = 128;
    const ctx = c.getContext('2d');
    const g = ctx.createRadialGradient(64, 64, 8, 64, 64, 62);
    g.addColorStop(0, 'rgba(20,10,40,0.35)');
    g.addColorStop(1, 'rgba(20,10,40,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
    const mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(1.4, 1.4),
      new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false })
    );
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = 0.01;
    return mesh;
  }

  // --- переключение клипов ---
  function fadeTo(action, fade, timeScale) {
    if (!action || state.active === action) {
      if (action && timeScale) action.setEffectiveTimeScale(timeScale);
      return;
    }
    const prev = state.active;
    state.active = action;
    action.reset().setEffectiveTimeScale(timeScale || 1).setEffectiveWeight(1).fadeIn(fade).play();
    if (prev) prev.fadeOut(fade);
  }

  function playLoop(name, { fade = 0.35, timeScale = 1 } = {}) {
    const a = state.actions[name];
    if (!a) return;
    a.setLoop(THREE.LoopRepeat, Infinity);
    fadeTo(a, fade, timeScale);
  }

  function startOneshot(name, { fade = 0.25, timeScale = 1 } = {}) {
    const a = state.actions[name];
    if (!a) return endIdle();
    clearTimeout(state.behaviorTimer);
    state.mode = 'oneshot';
    state.oneshotClip = name;
    a.setLoop(THREE.LoopOnce, 1);
    a.clampWhenFinished = true;
    fadeTo(a, fade, timeScale);
  }

  function endOneshot() {
    state.oneshotClip = null;
    endIdle();
  }

  function endIdle() {
    state.mode = 'idle';
    playLoop(CLIP.idle, { fade: 0.45, timeScale: 0.18 });
    scheduleBehavior();
  }

  // --- планировщик «поступков» от скуки ---
  function scheduleBehavior(delaySec) {
    clearTimeout(state.behaviorTimer);
    const delay =
      delaySec !== undefined
        ? delaySec * 1000
        : (CFG.minDelay + Math.random() * (CFG.maxDelay - CFG.minDelay)) * 1000;
    state.behaviorTimer = setTimeout(() => {
      if (document.hidden || state.mode !== 'idle') return;
      const roll = Math.random();
      if (roll < 0.4) startStroll(); // прогулка по сцене (с глубиной)
      else if (roll < 0.58) startVisit(); // подойти к зрителю, помахать, вернуться
      else if (roll < 0.82) startOneshot(CLIP.wave); // помахать
      else if (roll < 0.92) startOneshot(CLIP.cheer); // порадоваться
      else startOneshot(CLIP.dance); // редкий маленький танец
    }, delay);
  }

  // случайная точка дорожки (с глубиной)
  function randomSpot() {
    const z = CFG.depthFar + Math.random() * (CFG.depthNear - CFG.depthFar);
    const { minX, maxX } = view.xLimitsAt(z);
    return { x: minX + Math.random() * (maxX - minX), z };
  }

  // прогулка к случайной точке сцены (Walking, потом назад в idle)
  function startStroll() {
    clearTimeout(state.behaviorTimer);
    let spot = randomSpot();
    const p = state.rig.position;
    const dx = spot.x - p.x;
    const dz = spot.z - p.z;
    if (Math.hypot(dx, dz) < 1.2) {
      // слишком близко — гуляем подальше (отзеркаливаем точку)
      spot = { x: p.x - dx * 3, z: CFG.depthFar + (CFG.depthNear - spot.z) };
      const { minX, maxX } = view.xLimitsAt(spot.z);
      spot.x = THREE.MathUtils.clamp(spot.x, minX, maxX);
    }
    state.strollTarget = spot;
    state.afterArrive = null;
    state.mode = 'stroll';
    playLoop(CLIP.walk, { fade: 0.25 });
  }

  // выход к зрителю: подходит ближе, машет, уходит обратно
  function startVisit() {
    clearTimeout(state.behaviorTimer);
    const p = state.rig.position;
    const backSpot = { x: p.x, z: p.z }; // запомним, откуда пришёл
    const z = CFG.depthNear - Math.random() * 0.4;
    const { minX, maxX } = view.xLimitsAt(z);
    state.strollTarget = {
      x: THREE.MathUtils.clamp(p.x + (Math.random() - 0.5) * 1.5, minX, maxX),
      z,
    };
    state.afterArrive = () => {
      startOneshot(CLIP.wave);
      // после махания — вернуться, откуда пришёл (срабатывает после endOneshot,
      // поэтому перекрываем режим на stroll)
      const onFinished = (e) => {
        if (e.action === state.active) {
          state.mixer.removeEventListener('finished', onFinished);
          state.strollTarget = backSpot;
          state.mode = 'stroll';
          playLoop(CLIP.walk, { fade: 0.3 });
        }
      };
      state.mixer.addEventListener('finished', onFinished);
    };
    state.mode = 'stroll';
    playLoop(CLIP.walk, { fade: 0.25 });
  }

  // --- покадровая анимация ---
  const clock = new THREE.Clock();
  const lerp = THREE.MathUtils.lerp;
  const damp = (a, b, kk, dt) => lerp(a, b, 1 - Math.exp(-kk * dt));
  const _q = new THREE.Quaternion();
  const _q2 = new THREE.Quaternion();
  const _e = new THREE.Euler();

  function dampYaw(current, target, kk, dt) {
    let d = target - current;
    while (d > Math.PI) d -= Math.PI * 2;
    while (d < -Math.PI) d += Math.PI * 2;
    return current + d * (1 - Math.exp(-kk * dt));
  }

  function animate() {
    requestAnimationFrame(animate);
    const dt = Math.min(clock.getDelta(), 0.05);
    state.time += dt;
    const t = state.time;
    const { rig } = state;
    if (!rig) {
      renderer.render(scene, camera);
      return;
    }

    const now = performance.now();
    const scrolling = now < scroll.activeUntil;
    let targetYaw = CFG.faceOffset; // по умолчанию — лицом к зрителю
    let wantLook = 0;

    const speed = Math.abs(scroll.vel);

    if (state.mode === 'oneshot') {
      // во время one-shot чуть следим за мышью; рывки скроллом «пугают» — подпрыгнет
      wantLook = 0.4;
      if (scrolling && state.oneshotClip !== CLIP.jump && isJerky(now) && cooldownOk('startle', 8)) {
        touch('startle');
        startOneshot(CLIP.jump);
      }
    } else if (state.mode === 'stroll' && !(scrolling && speed > 520)) {
      // --- прогулка к точке (x, z) с разворотом в сторону движения ---
      const dx = state.strollTarget.x - rig.position.x;
      const dz = state.strollTarget.z - rig.position.z;
      const dist = Math.hypot(dx, dz);
      if (dist > 0.08) {
        targetYaw = Math.atan2(dx, dz) + CFG.faceOffset;
        const step = Math.min(CFG.walkSpeed * dt, dist);
        rig.position.x += (dx / dist) * step;
        rig.position.z += (dz / dist) * step;
      } else {
        rig.position.x = state.strollTarget.x;
        rig.position.z = state.strollTarget.z;
        const cb = state.afterArrive;
        state.afterArrive = null;
        if (cb) cb();
        else endIdle();
      }
    } else if (scrolling && (state.mode === 'scrollwalk' ? speed > 380 : speed > 520)) {
      // --- локомоция по скорости скролла (гистерезис 380/520 против мерцания) ---
      if (state.mode !== 'scrollwalk') {
        clearTimeout(state.behaviorTimer);
        state.mode = 'scrollwalk';
      }
      if (isJerky(now) && speed > 1200 && cooldownOk('startle', 8)) {
        touch('startle');
        startOneshot(CLIP.jump);
      } else if (speed > 2600) {
        // быстрый скролл — бежит по направлению скролла
        moveAlong(scroll.dir, CFG.runSpeed, dt);
        targetYaw = (scroll.dir > 0 ? Math.PI / 2 : -Math.PI / 2) + CFG.faceOffset;
        playLoop(CLIP.run, { fade: 0.2 });
      } else {
        // обычный скролл — шагает: вниз → вправо, вверх → влево
        moveAlong(scroll.dir, CFG.walkSpeed, dt);
        targetYaw = (scroll.dir > 0 ? Math.PI / 2 : -Math.PI / 2) + CFG.faceOffset;
        playLoop(CLIP.walk, { fade: 0.25 });
      }
    } else if (state.mode === 'scrollwalk') {
      // скролл затухает — останавливаемся
      endIdle();
    } else {
      // idle: курсор рядом — посматривает
      const mx = mouse.x * view.halfWAt(rig.position.z);
      if (Math.abs(mx - rig.position.x) < view.halfWAt(rig.position.z) * 0.35) {
        targetYaw =
          THREE.MathUtils.clamp((mx - rig.position.x) * 0.35, -0.45, 0.45) + CFG.faceOffset;
        wantLook = 0.6;
      }
    }

    state.yaw = dampYaw(state.yaw, targetYaw, 6, dt);
    rig.rotation.y = state.yaw;
    // «пол» пересчитывается под текущую глубину — маскот всегда стоит на нём
    rig.position.y = view.groundYAt(rig.position.z);

    state.mixer.update(dt);
    // Слежение головой — поверх анимации (mixer каждый кадр перезаписывает кость)
    state.lookWeight = damp(state.lookWeight, wantLook, 5, dt);
    if (state.headBone && state.lookWeight > 0.01) {
      const w = state.lookWeight;
      _e.set(mouse.y * 0.25 * w, mouse.x * 0.5 * w, 0, 'XYZ');
      _q.setFromEuler(_e);
      state.headBone.quaternion.multiply(_q);
    }

    // Хвост — процедурно: держим направление «назад» от рига с упругим
    // запаздыванием (танцы крутят Hips, а хвост не должен улетать вперёд).
    // Плюс виляние: чем активнее движение, тем быстрее.
    if (state.tailBone && state.tailQuat) {
      const active =
        state.mode === 'stroll' || state.mode === 'scrollwalk' || state.oneshotClip === CLIP.dance;
      const wagSpeed = active ? 7 : 2.2;
      const wagAmp = active ? 0.28 : 0.12;
      _e.set(Math.sin(t * wagSpeed * 0.5) * 0.06, state.yaw + Math.sin(t * wagSpeed) * wagAmp, 0, 'XYZ');
      _q.setFromEuler(_e);
      state.tailQuat.slerp(_q, 1 - Math.exp(-5 * dt)); // упругое запаздывание
      state.tailBone.parent.getWorldQuaternion(_q2);
      state.tailBone.quaternion.copy(_q2.invert().multiply(state.tailQuat));
    }

    renderer.render(scene, camera);
  }

  // рывки: 3+ смены направления скролла за последние 1.2 сек
  function isJerky(now) {
    scroll.flips = scroll.flips.filter((ts) => now - ts < 1200);
    return scroll.flips.length >= 3;
  }

  function moveAlong(dir, speed, dt) {
    const rig = state.rig;
    const { minX, maxX } = view.xLimitsAt(rig.position.z);
    rig.position.x = THREE.MathUtils.clamp(rig.position.x + dir * speed * dt, minX, maxX);
  }

  animate();

  // Пауза, когда вкладка скрыта — экономим батарею
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) clock.getDelta();
  });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    if (state.rig) {
      const z = THREE.MathUtils.clamp(state.rig.position.z, CFG.depthFar, CFG.depthNear);
      state.rig.position.z = z;
      const { minX, maxX } = view.xLimitsAt(z);
      state.rig.position.x = THREE.MathUtils.clamp(state.rig.position.x, minX, maxX);
      state.strollTarget.x = THREE.MathUtils.clamp(state.strollTarget.x, minX, maxX);
      state.strollTarget.z = THREE.MathUtils.clamp(state.strollTarget.z, CFG.depthFar, CFG.depthNear);
    }
  });
}
