/* Фокси 3D — процедурно анимированный маскот (модель без скелета).
   Загружается лениво из foxi-wow.js после load+idle. Молча отключается
   при отсутствии WebGL или ошибке загрузки — страница не страдает. */

const MODEL_URL = '/wow/foxi.glb';
const PHRASES = [
  'Привет! Я Фокси!',
  'Пойдём учить английский?',
  'English — это легко!',
  'Нажми на меня ещё раз!',
  'Запишись на бесплатный урок!',
];

function el(tag, cls, parent) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (parent) parent.appendChild(n);
  return n;
}

export async function initFoxi3D() {
  const [THREE, { GLTFLoader }, { MeshoptDecoder }] = await Promise.all([
    import('three'),
    import('three/addons/loaders/GLTFLoader.js'),
    import('https://cdn.jsdelivr.net/npm/meshoptimizer@0.18.1/meshopt_decoder.module.js'),
  ]);

  // --- DOM ---
  const root = el('div', 'foxi3d', document.body);
  root.setAttribute('aria-hidden', 'true');
  const shadow = el('div', 'foxi3d__shadow', root);
  const canvas = el('canvas', 'foxi3d__canvas', root);
  const bubble = el('div', 'foxi3d__bubble', root);
  bubble.setAttribute('role', 'button');
  bubble.setAttribute('aria-hidden', 'true');

  // --- Renderer / scene ---
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'low-power' });
  } catch (e) {
    root.remove();
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
  camera.position.set(0, 1.15, 4.2);
  camera.lookAt(0, 0.95, 0);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7ab0, 1.15));
  const dir = new THREE.DirectionalLight(0xfff6d8, 1.6);
  dir.position.set(2.5, 4, 3);
  scene.add(dir);
  const fill = new THREE.DirectionalLight(0xb9a8ff, 0.5);
  fill.position.set(-3, 1.5, -2);
  scene.add(fill);

  const pivot = new THREE.Group(); // позиция/прыжок
  const body = new THREE.Group();  // повороты/наклоны/дыхание
  pivot.add(body);
  scene.add(pivot);

  // --- Модель ---
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const gltf = await loader.loadAsync(MODEL_URL);
  const model = gltf.scene;

  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const scale = 1.9 / Math.max(size.x, size.y, size.z);
  model.scale.setScalar(scale);
  model.position.set(-center.x * scale, -box.min.y * scale, -center.z * scale);
  model.traverse((o) => { if (o.isMesh) o.frustumCulled = false; });
  body.add(model);

  // --- Размер ---
  function resize() {
    const r = root.getBoundingClientRect();
    renderer.setSize(r.width, r.height, false);
    camera.aspect = r.width / r.height;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener('resize', resize, { passive: true });

  // --- Состояние ---
  const st = {
    mx: 0, my: 0,            // курсор -1..1
    walkX: 0, walkV: 0,      // смещение при «ходьбе»
    phase: 0,                // фаза шага
    lastScroll: window.scrollY,
    jumpT: -1,               // -1 = не прыгает
    spin: 0,
    leanX: 0, leanZ: 0,      // наклон к CTA
    squash: 0,               // приземление
    bubbleT: 0,
  };

  window.addEventListener('pointermove', (e) => {
    st.mx = (e.clientX / window.innerWidth) * 2 - 1;
    st.my = (e.clientY / window.innerHeight) * 2 - 1;
  }, { passive: true });

  // Ходьба по скроллу
  window.addEventListener('scroll', () => {
    const y = window.scrollY;
    const d = y - st.lastScroll;
    st.lastScroll = y;
    st.walkV = Math.max(-60, Math.min(60, st.walkV + d * 0.25));
  }, { passive: true });

  // «Показывает рукой» — наклон к CTA при наведении
  document.addEventListener('pointerover', (e) => {
    const cta = e.target.closest && e.target.closest('[data-fxb-zayavka], .fxb-btn-main');
    if (!cta) return;
    const cr = cta.getBoundingClientRect();
    const rr = root.getBoundingClientRect();
    const dx = (cr.left + cr.width / 2) - (rr.left + rr.width / 2);
    const dy = (cr.top + cr.height / 2) - (rr.top + rr.height / 2);
    st.leanX = Math.max(-1, Math.min(1, dx / 500));
    st.leanZ = Math.max(-0.5, Math.min(0.5, -dy / 700));
  }, { passive: true });
  document.addEventListener('pointerout', (e) => {
    if (e.target.closest && e.target.closest('[data-fxb-zayavka], .fxb-btn-main')) {
      st.leanX = 0; st.leanZ = 0;
    }
  }, { passive: true });

  // Клик по Фокси — прыжок + пузырь
  const ray = new THREE.Raycaster();
  const ptr = new THREE.Vector2();
  let bubbleTimer = 0;
  canvas.addEventListener('pointerdown', (e) => {
    const r = canvas.getBoundingClientRect();
    ptr.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    ptr.y = -((e.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(ptr, camera);
    if (ray.intersectObject(model, true).length === 0) return;
    if (st.jumpT < 0) { st.jumpT = 0; st.spin = 0; }
    bubble.textContent = PHRASES[Math.floor(Math.random() * PHRASES.length)];
    bubble.classList.add('is-on');
    bubble.setAttribute('aria-hidden', 'false');
    clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(() => {
      bubble.classList.remove('is-on');
      bubble.setAttribute('aria-hidden', 'true');
    }, 3800);
  });
  // Клик по пузырю → форма заявки
  bubble.addEventListener('click', () => {
    const cta = document.querySelector('[data-fxb-zayavka]');
    if (cta) cta.click();
  });

  // --- Цикл ---
  const clock = new THREE.Clock();
  let raf = 0;
  const JUMP_DUR = 0.85;

  function tick() {
    raf = requestAnimationFrame(tick);
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;

    // Ходьба: затухание скорости, движение по X, восьмёрка корпусом
    st.walkV *= Math.pow(0.02, dt);
    const walking = Math.abs(st.walkV) > 0.5;
    if (walking) {
      st.phase += Math.abs(st.walkV) * dt * 0.55;
      st.walkX += st.walkV * dt;
      st.walkX = Math.max(-70, Math.min(70, st.walkX));
    } else {
      st.walkX *= Math.pow(0.1, dt); // возврат в угол
    }
    const hop = walking ? Math.abs(Math.sin(st.phase)) * 0.07 : 0;
    const roll = walking ? Math.sin(st.phase) * 0.13 : 0;

    // Прыжок по клику
    let jumpY = 0;
    if (st.jumpT >= 0) {
      st.jumpT += dt;
      const p = st.jumpT / JUMP_DUR;
      if (p >= 1) {
        st.jumpT = -1;
        st.squash = 1;
      } else {
        jumpY = Math.sin(p * Math.PI) * 0.55;
        st.spin = p * Math.PI * 2;
      }
    }
    st.squash = Math.max(0, st.squash - dt * 4);

    // Дыхание + парение
    const breathe = 1 + Math.sin(t * 2.1) * 0.018;
    const floatY = Math.sin(t * 1.4) * 0.045;

    // Взгляд за курсором (lerp)
    const targetYaw = st.mx * 0.55 + st.leanX * 0.9;
    const targetPitch = -st.my * 0.18 + Math.abs(st.leanX) * 0.15 + st.leanZ;
    body.rotation.y += (targetYaw + st.spin - body.rotation.y) * Math.min(1, dt * 6);
    body.rotation.x += (targetPitch - body.rotation.x) * Math.min(1, dt * 6);
    body.rotation.z += (roll - st.leanX * 0.28 - body.rotation.z) * Math.min(1, dt * 8);

    // Squash & stretch
    const sq = st.squash;
    body.scale.set(
      breathe * (1 + sq * 0.18),
      breathe * (1 - sq * 0.22),
      breathe * (1 + sq * 0.18)
    );

    pivot.position.set(st.walkX / 100, floatY + hop + jumpY, 0);
    if (shadow) {
      const s = Math.max(0.4, 1 - (jumpY + hop) * 0.9);
      shadow.style.transform = `translateX(-50%) scale(${s})`;
      shadow.style.opacity = String(0.35 * s);
    }

    renderer.render(scene, camera);
  }
  tick();

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(raf);
    else { clock.getDelta(); tick(); }
  });

  root.classList.add('is-ready');
}
