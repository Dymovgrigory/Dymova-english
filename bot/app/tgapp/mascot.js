/**
 * Трёхмерный Фокси на главном экране мини-приложения.
 *
 * Правило простое: 3D — это надстройка, а не условие работы экрана. Статичный
 * маскот (25 КБ webp) виден сразу и остаётся единственным визуалом, если
 * устройство или сеть не тянут модель. Трёхмерная версия (~1.9 МБ вместе с
 * рантаймом) грузится только после первого рендера, только по требованию
 * и только когда проверки пройдены — иначе мини-приложение открывалось бы
 * секундами на том самом среднем телефоне, ради которого всё и делается.
 *
 * Это не движок маскота с сайта (prototype/mascot/mascot.js): тот управляет
 * персонажем во весь экран и живёт от скролла страницы. Здесь маскот стоит в
 * своей сцене на главной, реагирует на касание и на смену экрана.
 */

const STILL = document.getElementById('mascot-still');
const MOUNT = document.getElementById('mascot-3d');
const STAGE = MOUNT ? MOUNT.closest('.hero__stage') : null;

const MODEL_URL = './assets/foxi.glb';
const DRACO_PATH = './vendor/draco/';

// Клипы модели (Meshy biped, 6 анимаций). Названия заданы в самом GLB.
const CLIP_IDLE = 'Shake_It_Off_Dance';
const CLIP_WAVE = 'Big_Wave_Hello';
const CLIP_CHEER = 'Cheer_with_Both_Hands_Up';
const CLIP_JUMP = 'Happy_jump_f';

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Стоит ли вообще грузить 3D.
 *
 * Проверки консервативные: лучше показать красивую картинку, чем посадить
 * телефон на 2 МБ загрузки и просадить кадры до слайд-шоу.
 */
function shouldLoad3D() {
  if (!MOUNT || reducedMotion) return false;

  // Пользователь попросил экономить трафик — это прямое указание.
  const conn = navigator.connection;
  if (conn) {
    if (conn.saveData) return false;
    if (/(^|-)2g$/.test(conn.effectiveType || '')) return false;
  }

  // deviceMemory отдают не все браузеры; отсутствие — не приговор,
  // а вот честно названные 2 ГБ означают, что WebGL здесь лишний.
  if (typeof navigator.deviceMemory === 'number' && navigator.deviceMemory < 4) return false;
  if (typeof navigator.hardwareConcurrency === 'number' && navigator.hardwareConcurrency < 4) {
    return false;
  }

  // Без WebGL2 грузить рантайм бессмысленно.
  try {
    const probe = document.createElement('canvas');
    if (!probe.getContext('webgl2')) return false;
  } catch (_) {
    return false;
  }
  return true;
}

/** Ждёт момента, когда загрузка ничего не отнимет у первого экрана. */
function whenIdle(run) {
  const start = () => {
    const ric = window.requestIdleCallback || ((cb) => setTimeout(cb, 900));
    ric(run, { timeout: 3500 });
  };
  if (document.readyState === 'complete') start();
  else window.addEventListener('load', start, { once: true });
}

async function boot() {
  const THREE = await import('three');
  // Через спецификатор из импорт-карты, а не по прямому пути: загрузчики
  // сами тянут соседей как `three/addons/...`, и без карты эти импорты
  // разрешаются мимо каталога (проверено — GLTFLoader ронял 404 на
  // BufferGeometryUtils.js).
  const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
  const { DRACOLoader } = await import('three/addons/loaders/DRACOLoader.js');

  const size = MOUNT.clientWidth || 208;

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
  // Ретина-плотность выше 2 не видна, но стоит вчетверо дороже по пикселям.
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(size, size, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  MOUNT.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 60);
  camera.position.set(0, 1.05, 4.6);
  camera.lookAt(0, 0.95, 0);

  // Свет по схеме «ключ + заполняющий + контровой»: плоская заливка делает
  // модель пластмассовой, а нам нужна дорогая фактура.
  scene.add(new THREE.HemisphereLight(0xffffff, 0x40306a, 2.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(2.4, 3.6, 2.8);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xffc53d, 1.5);
  rim.position.set(-2.6, 1.8, -2.4);
  scene.add(rim);

  const draco = new DRACOLoader().setDecoderPath(DRACO_PATH);
  const loader = new GLTFLoader().setDRACOLoader(draco);

  const gltf = await loader.loadAsync(MODEL_URL);
  const model = gltf.scene;

  // Модель приходит в произвольном масштабе — нормируем по её же габаритам,
  // иначе она либо не влезет в кадр, либо станет точкой.
  const box = new THREE.Box3().setFromObject(model);
  const height = Math.max(box.max.y - box.min.y, 0.001);
  const scale = 1.9 / height;
  model.scale.setScalar(scale);
  box.setFromObject(model);
  model.position.y -= box.min.y;
  model.position.x -= (box.max.x + box.min.x) / 2;
  scene.add(model);

  const mixer = new THREE.AnimationMixer(model);
  const clips = new Map(gltf.animations.map((clip) => [clip.name, clip]));

  function play(name, { once = false, speed = 1 } = {}) {
    const clip = clips.get(name) || gltf.animations[0];
    if (!clip) return null;
    const action = mixer.clipAction(clip);
    action.reset();
    action.timeScale = speed;
    if (once) {
      action.setLoop(THREE.LoopOnce, 1);
      action.clampWhenFinished = true;
    }
    action.fadeIn(0.25).play();
    return action;
  }

  // База — танец на очень малой скорости: получается едва заметное дыхание,
  // а не «детская» пляска.
  let idle = play(CLIP_IDLE, { speed: 0.16 });

  function react(name, speed = 1) {
    if (!clips.has(name)) return;
    if (idle) idle.fadeOut(0.2);
    const action = play(name, { once: true, speed });
    if (!action) return;
    const onFinish = (event) => {
      if (event.action !== action) return;
      mixer.removeEventListener('finished', onFinish);
      action.fadeOut(0.3);
      idle = play(CLIP_IDLE, { speed: 0.16 });
    };
    mixer.addEventListener('finished', onFinish);
  }

  // Реакции на действия пользователя — микровзаимодействия, а не декор.
  MOUNT.addEventListener('pointerdown', () => react(CLIP_JUMP, 1.1));
  document.addEventListener('foxi:success', () => react(CLIP_CHEER, 1.25));
  document.addEventListener('foxi:greet', () => react(CLIP_WAVE));

  // Голова провожает палец: цепляем только по кости из рига.
  const head = model.getObjectByName('Head');
  const look = { x: 0, y: 0, targetX: 0, targetY: 0 };
  if (head) {
    window.addEventListener('pointermove', (event) => {
      const rect = MOUNT.getBoundingClientRect();
      look.targetX = ((event.clientX - rect.left) / (rect.width || 1)) * 2 - 1;
      look.targetY = -(((event.clientY - rect.top) / (rect.height || 1)) * 2 - 1);
    }, { passive: true });
  }

  // Кадры считаем только когда главный экран открыт и вкладка активна:
  // рендерить невидимое — это чистый расход батареи.
  let visible = true;
  const home = document.querySelector('[data-screen="home"]');
  if (home && 'IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; })
      .observe(home);
  }
  document.addEventListener('visibilitychange', () => {
    visible = document.visibilityState === 'visible';
  });

  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    const delta = clock.getDelta();
    if (!visible) return;
    mixer.update(delta);
    if (head) {
      // Упругое запаздывание вместо жёсткой привязки — движение живое.
      look.x += (look.targetX - look.x) * Math.min(1, delta * 4);
      look.y += (look.targetY - look.y) * Math.min(1, delta * 4);
      head.rotation.y = look.x * 0.42;
      head.rotation.x = look.y * 0.22;
    }
    renderer.render(scene, camera);
  });

  // Показываем 3D только теперь — до этого момента виден статичный маскот.
  if (STAGE) STAGE.classList.add('is-3d');
  react(CLIP_WAVE);

  window.addEventListener('resize', () => {
    const next = MOUNT.clientWidth || size;
    renderer.setSize(next, next, false);
  }, { passive: true });
}

if (shouldLoad3D()) {
  whenIdle(() => {
    boot().catch((error) => {
      // Провал загрузки 3D не должен ничего ломать: на экране остаётся
      // статичный маскот, и пользователь не увидит разницы.
      console.warn('[foxi] 3D не загрузился, остаётся статичный маскот', error);
      if (STAGE) STAGE.classList.remove('is-3d');
    });
  });
}

export {};
