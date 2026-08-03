/**
 * Фокси — живой 3D-маскот поверх всех страниц dymova-english.ru.
 *
 * Ригнутая модель (Meshy biped + Merged Animations, 17 клипов). Маскот ходит
 * по нижней кромке экрана и использует ВСЕ клипы в зависимости от контекста:
 *
 *   Скорость скролла:
 *     медленный скролл вниз      → Walking (шагает вправо)
 *     медленный скролл вверх     → Walk_Backward (отступает спиной)
 *     быстрый скролл             → Running (бежит)
 *     резкие рывки туда-сюда     → Stumble_Walk (спотыкается)
 *   Место на странице:
 *     доскроллил до самого низа  → FunnyDancing_03 / jazz_danc (танцует)
 *   Курсор и клики:
 *     наведение на CTA-заявку    → Wave_for_Help_1 (машет)
 *     клик по CTA                → Fast_Lightning (ускоренный, «ура, заявка!»)
 *     клик рядом с маскотом      → Regular_Jump (подпрыгивает)
 *     курсор рядом               → голова следит (кость head поверх клипа)
 *   Скука (idle, каждые 8–18 сек случайно):
 *     прогулка (Walking), развороты (Walk_Turn_Left/Right,
 *     Walk_Turn_Right_Female, Walk_Turn_Left_with_Weapon,
 *     Walk_Turn_Right_Idle_Style, Run_Turn_Right), длинное махание
 *     (Wave_for_Help_3), редкий танец (You_Groove на нормальной скорости).
 *   Базовый idle: You_Groove на timeScale 0.22 — еле заметное покачивание,
 *     чтобы не мешать читать.
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
    height: 1.0, // высота маскота в мировых юнитах (масштаб авто)
    mobileHeight: 0.72, // высота на узких экранах
    groundLift: 0.02, // отступ от низа экрана (доля полувысоты сцены)
    walkMargin: 0.86, // ширина «дорожки» (доля полуширины сцены)
    reserveRightPx: 120, // запретная зона справа (чат-виджет), px
    walkSpeed: 1.7, // юнитов/сек при прогулке
    runSpeed: 3.6, // юнитов/сек при беге
    faceOffset: 0, // добавка к yaw, если лицо не в +Z (рад)
    minDelay: 8, // минимальная пауза между «поступками», сек
    maxDelay: 18, // максимальная пауза, сек
    zIndex: 9998,
    hideUnderWidth: 0, // >0 — не показывать на экранах уже этого значения
  },
  window.FOXI_CONFIG || {}
);

// Имена клипов в GLB (Meshy Merged Animations)
const CLIP = {
  groove: 'You_Groove',
  walk: 'Walking',
  walkBack: 'Walk_Backward',
  run: 'Running',
  stumble: 'Stumble_Walk',
  jump: 'Regular_Jump',
  waveShort: 'Wave_for_Help_1',
  waveLong: 'Wave_for_Help_3',
  danceA: 'FunnyDancing_03',
  danceB: 'jazz_danc',
  lightning: 'Fast_Lightning',
  turns: [
    'Walk_Turn_Left',
    'Walk_Turn_Right',
    'Walk_Turn_Right_Female',
    'Walk_Turn_Left_with_Weapon',
    'Walk_Turn_Right_Idle_Style',
    'Run_Turn_Right',
  ],
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

  // --- размеры «пола» в мире на плоскости z = 0 ---
  const view = { halfH: 0, halfW: 0, groundY: 0, minX: 0, maxX: 0 };
  function updateView() {
    const dist = camera.position.z;
    view.halfH = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * dist;
    view.halfW = view.halfH * camera.aspect;
    view.groundY = -view.halfH + view.halfH * CFG.groundLift * 2;
    const worldPerPx = (view.halfW * 2) / window.innerWidth;
    view.minX = -view.halfW * CFG.walkMargin;
    // справа — запретная зона под чат-виджет
    view.maxX = view.halfW * CFG.walkMargin - CFG.reserveRightPx * worldPerPx;
    if (view.maxX < 0) view.maxX = 0;
  }
  updateView();

  // --- состояние ---
  const state = {
    ready: false,
    mode: 'idle', // idle | oneshot | scrollwalk | stroll
    oneshotClip: null, // имя клипа текущего one-shot
    rig: null, // внешняя группа: позиция + yaw
    mixer: null,
    actions: {}, // имя клипа -> AnimationAction
    active: null, // текущий AnimationAction
    headBone: null,
    lookWeight: 0,
    time: 0,
    behaviorTimer: null,
    strollTargetX: 0, // куда гуляем в режиме stroll
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
      startOneshot(Math.random() < 0.5 ? CLIP.danceA : CLIP.danceB);
    }
  }, { passive: true });

  // --- реакции на элементы сайта ---
  const CTA_SELECTOR = '[data-fxb-zayavka], .fxb-btn-main, a[href*="zayavka"]';
  document.addEventListener('mouseover', (e) => {
    if (!state.ready || state.mode !== 'idle') return;
    if (e.target.closest && e.target.closest(CTA_SELECTOR) && cooldownOk('ctaWave', 10)) {
      touch('ctaWave');
      startOneshot(CLIP.waveShort);
    }
  });
  document.addEventListener('pointerdown', (e) => {
    if (!state.ready) return;
    if (e.target.closest && e.target.closest(CTA_SELECTOR)) {
      if (state.mode === 'idle' && cooldownOk('ctaClick', 10)) {
        touch('ctaClick');
        startOneshot(CLIP.lightning, { timeScale: 3.2 });
      }
      return;
    }
    // клик рядом с маскотом — подпрыгивает (иногда машет)
    if (state.rig && state.mode === 'idle') {
      const p = state.rig.position;
      const mx = ((e.clientX / window.innerWidth) * 2 - 1) * view.halfW;
      const my = (-(e.clientY / window.innerHeight) * 2 + 1) * view.halfH;
      if (Math.hypot(mx - p.x, my - p.y) < 1.6 && cooldownOk('poke', 3)) {
        touch('poke');
        startOneshot(Math.random() < 0.75 ? CLIP.jump : CLIP.waveShort);
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
  // стартует у левой кромки — не загораживает контент по центру
  rig.position.set(view.minX * 0.8, view.groundY, 0);
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

  // кость головы — слежение за мышью
  const headNeedle = CFG.headBone.toLowerCase();
  model.traverse((o) => {
    if (!state.headBone && o.isBone && o.name.toLowerCase().includes(headNeedle)) {
      state.headBone = o;
    }
  });

  console.info('[foxi] skeletal-режим, клипы:', gltf.animations.map((c) => c.name).join(', '));

  state.ready = true;
  playLoop(CLIP.groove, { timeScale: 0.22 }); // базовый idle — еле заметное покачивание
  canvas.style.opacity = '1';
  scheduleBehavior(3); // первый «поступок» почти сразу — маскот оживает

  // Внешний API для сайта: window.FOXI
  window.FOXI = {
    wave: () => state.mode === 'idle' && startOneshot(CLIP.waveLong),
    jump: () => state.mode === 'idle' && startOneshot(CLIP.jump),
    dance: () => state.mode === 'idle' && startOneshot(CLIP.danceA),
    walk: () => state.mode === 'idle' && startStroll(),
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
    playLoop(CLIP.groove, { fade: 0.45, timeScale: 0.22 });
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
      if (roll < 0.34) startStroll(); // прогулка
      else if (roll < 0.62) startOneshot(pick(CLIP.turns)); // развернуться-оглядеться
      else if (roll < 0.8) startOneshot(CLIP.waveLong); // помахать
      else if (roll < 0.92) startOneshot(CLIP.waveShort); // коротко махнуть
      else startOneshot(CLIP.danceB); // редкий маленький танец
    }, delay);
  }

  function pick(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  // прогулка к случайной точке (Walking, потом назад в idle)
  function startStroll() {
    clearTimeout(state.behaviorTimer);
    let x = view.minX + Math.random() * (view.maxX - view.minX);
    if (Math.abs(x - state.rig.position.x) < (view.maxX - view.minX) * 0.3) {
      x = view.maxX + view.minX - x; // гуляем подальше
    }
    state.strollTargetX = x;
    state.mode = 'stroll';
    playLoop(CLIP.walk, { fade: 0.25 });
  }

  // --- покадровая анимация ---
  const clock = new THREE.Clock();
  const lerp = THREE.MathUtils.lerp;
  const damp = (a, b, kk, dt) => lerp(a, b, 1 - Math.exp(-kk * dt));
  const _q = new THREE.Quaternion();
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
      // во время one-shot чуть следим за мышью; рывки скроллом могут «сбить» — спотыкание
      wantLook = 0.4;
      if (scrolling && state.oneshotClip !== CLIP.stumble && isJerky(now) && cooldownOk('stumble', 8)) {
        touch('stumble');
        startOneshot(CLIP.stumble);
      }
    } else if (state.mode === 'stroll' && !(scrolling && speed > 520)) {
      const dx = state.strollTargetX - rig.position.x;
      if (Math.abs(dx) > 0.08) {
        targetYaw = (dx > 0 ? Math.PI / 2 : -Math.PI / 2) + CFG.faceOffset;
        const step = Math.sign(dx) * CFG.walkSpeed * dt;
        rig.position.x += Math.abs(step) > Math.abs(dx) ? dx : step;
      } else {
        rig.position.x = state.strollTargetX;
        endIdle();
      }
    } else if (scrolling && (state.mode === 'scrollwalk' ? speed > 380 : speed > 520)) {
      // --- локомоция по скорости скролла (гистерезис 380/520 против мерцания) ---
      if (state.mode !== 'scrollwalk') {
        clearTimeout(state.behaviorTimer);
        state.mode = 'scrollwalk';
      }
      if (isJerky(now) && speed > 1200 && cooldownOk('stumble', 8)) {
        touch('stumble');
        startOneshot(CLIP.stumble);
      } else if (speed > 2600) {
        // быстрый скролл — бежит
        moveAlong(scroll.dir, CFG.runSpeed, dt);
        targetYaw = scroll.dir > 0 ? Math.PI / 2 : -Math.PI / 2;
        playLoop(CLIP.run, { fade: 0.2 });
      } else if (scroll.dir > 0) {
        // скролл вниз — шагает вправо
        moveAlong(1, CFG.walkSpeed, dt);
        targetYaw = Math.PI / 2;
        playLoop(CLIP.walk, { fade: 0.25 });
      } else {
        // скролл вверх — отступает спиной влево
        moveAlong(-1, CFG.walkSpeed * 0.8, dt);
        targetYaw = Math.PI / 2; // лицом вправо, спиной назад
        playLoop(CLIP.walkBack, { fade: 0.25 });
      }
    } else if (state.mode === 'scrollwalk') {
      // скролл затухает — останавливаемся
      endIdle();
    } else {
      // idle: курсор рядом — посматривает
      const mx = mouse.x * view.halfW;
      if (Math.abs(mx - rig.position.x) < view.halfW * 0.35) {
        targetYaw =
          THREE.MathUtils.clamp((mx - rig.position.x) * 0.35, -0.45, 0.45) + CFG.faceOffset;
        wantLook = 0.6;
      }
    }

    state.yaw = dampYaw(state.yaw, targetYaw, 6, dt);
    rig.rotation.y = state.yaw;
    rig.position.y = view.groundY;

    state.mixer.update(dt);
    // Слежение головой — поверх анимации (mixer каждый кадр перезаписывает кость)
    state.lookWeight = damp(state.lookWeight, wantLook, 5, dt);
    if (state.headBone && state.lookWeight > 0.01) {
      const w = state.lookWeight;
      _e.set(mouse.y * 0.25 * w, mouse.x * 0.5 * w, 0, 'XYZ');
      _q.setFromEuler(_e);
      state.headBone.quaternion.multiply(_q);
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
    rig.position.x = THREE.MathUtils.clamp(
      rig.position.x + dir * speed * dt,
      view.minX,
      view.maxX
    );
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
    updateView();
    if (state.rig) {
      state.rig.position.x = THREE.MathUtils.clamp(state.rig.position.x, view.minX, view.maxX);
      state.strollTargetX = THREE.MathUtils.clamp(state.strollTargetX, view.minX, view.maxX);
    }
  });
}
