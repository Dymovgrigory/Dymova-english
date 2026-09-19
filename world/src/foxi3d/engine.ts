/**
 * Живой 3D-Фокси для башни учебника — чистый three.js, без React Three Fiber.
 *
 * Модель: /assets/foxi-rigged-v2.glb (draco + webp512), клипы:
 * Idle, Walk_Inplace, Walking, Running, Call_Gesture, Big_Wave_Hello,
 * Cheer_with_Both_Hands_Up, Happy_jump_f, Shake_It_Off_Dance.
 * Кость Tail управляется процедурно (в клипах её нет) — паттерн из
 * prototype/mascot/mascot.js: держим хвост «назад» от рига с упругим
 * запаздыванием + виляние.
 *
 * Поведение: стоит у окна (Idle + редкое махание), периодически переходит
 * к соседнему «окну» (Walk_Inplace + смещение/поворот), при долгом простое
 * зовёт (Call_Gesture + колбэк бабла «Нажми на следующий урок!»),
 * celebrate()/dance() — реакции на пульс нового урока.
 */

export interface FoxiOptions {
  modelUrl?: string;
  dracoPath?: string;
  /** Показать/скрыть DOM-бабл «Нажми на следующий урок!». */
  onPrompt?: (visible: boolean) => void;
  onReady?: () => void;
  /** Клип недоступен/нет WebGL/ошибка GLB — вызывающий код покажет webp. */
  onError?: (err: unknown) => void;
}

export interface FoxiHandle {
  celebrate: () => void;
  dance: () => void;
  dispose: () => void;
}

type Three = typeof import("three");

const CLIP = {
  idle: "Idle",
  walk: "Walk_Inplace",
  wave: "Big_Wave_Hello",
  call: "Call_Gesture",
  cheer: "Cheer_with_Both_Hands_Up",
  jump: "Happy_jump_f",
  dance: "Shake_It_Off_Dance",
} as const;

const DANCE_FRAGMENT_SEC = 5; // короткий фрагмент танца, не все 16.3с

export async function createFoxi(container: HTMLElement, opts: FoxiOptions = {}): Promise<FoxiHandle> {
  const modelUrl = opts.modelUrl ?? "/assets/foxi-rigged-v2.glb";
  const dracoPath = opts.dracoPath ?? "/draco/";

  try {
    performance.mark?.("foxi:boot-start");
  } catch {
    /* marks опциональны */
  }

  let THREE: Three;
  let GLTFLoader: typeof import("three/examples/jsm/loaders/GLTFLoader.js").GLTFLoader;
  let DRACOLoader: typeof import("three/examples/jsm/loaders/DRACOLoader.js").DRACOLoader;
  try {
    THREE = await import("three");
    ({ GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js"));
    ({ DRACOLoader } = await import("three/examples/jsm/loaders/DRACOLoader.js"));
  } catch (err) {
    opts.onError?.(err);
    throw err;
  }

  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  Object.assign(canvas.style, {
    position: "absolute",
    inset: "0",
    width: "100%",
    height: "100%",
    pointerEvents: "none",
    opacity: "0",
    transition: "opacity 0.6s ease",
  });
  container.appendChild(canvas);

  let renderer: InstanceType<Three["WebGLRenderer"]>;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "low-power" });
  } catch (err) {
    canvas.remove();
    opts.onError?.(err);
    throw err;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const width = Math.max(container.clientWidth, 1);
  const height = Math.max(container.clientHeight, 1);
  renderer.setSize(width, height);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 50);
  camera.position.set(0, 0.9, 4.2);
  camera.lookAt(0, 0.55, 0);

  scene.add(new THREE.HemisphereLight(0xfff6e3, 0x8a7ab0, 1.1));
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
  dirLight.position.set(2.5, 5, 5);
  scene.add(dirLight);

  const draco = new DRACOLoader().setDecoderPath(dracoPath);
  const loader = new GLTFLoader().setDRACOLoader(draco);

  let gltf: Awaited<ReturnType<InstanceType<typeof GLTFLoader>["loadAsync"]>>;
  try {
    gltf = await loader.loadAsync(modelUrl);
  } catch (err) {
    renderer.dispose();
    canvas.remove();
    opts.onError?.(err);
    throw err;
  }

  const model = gltf.scene;

  // Нормализация: Z-up → ставим на «пол», центрируем, опора на подошву
  const rawBox = new THREE.Box3().setFromObject(model);
  const rawSize = rawBox.getSize(new THREE.Vector3());
  if (rawSize.z > rawSize.y * 1.5) model.rotation.x = -Math.PI / 2;
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  model.position.x -= center.x;
  model.position.z -= center.z;
  model.position.y -= box.min.y;

  const size = box.getSize(new THREE.Vector3());
  const k = 1.05 / Math.max(size.y, 0.001);

  const body = new THREE.Group();
  body.add(model);
  body.scale.setScalar(k);
  const rig = new THREE.Group();
  rig.add(body);
  rig.add(makeBlobShadow());
  rig.position.set(0, 0, 0);
  scene.add(rig);

  function makeBlobShadow() {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const ctx = c.getContext("2d");
    if (ctx) {
      const g = ctx.createRadialGradient(64, 64, 8, 64, 64, 62);
      g.addColorStop(0, "rgba(20,10,40,0.32)");
      g.addColorStop(1, "rgba(20,10,40,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 128, 128);
    }
    const mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(1.5, 1.5),
      new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false }),
    );
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = 0.01;
    return mesh;
  }

  // --- анимации ---
  type Action = InstanceType<Three["AnimationAction"]>;
  const mixer = new THREE.AnimationMixer(model);
  const actions: Record<string, Action> = {};
  for (const clip of gltf.animations) actions[clip.name] = mixer.clipAction(clip);

  let headBone: InstanceType<Three["Bone"]> | null = null;
  let tailBone: InstanceType<Three["Bone"]> | null = null;
  model.traverse((o) => {
    const bone = o as InstanceType<Three["Bone"]>;
    if (!headBone && bone.isBone && bone.name.toLowerCase().includes("head")) headBone = bone;
    if (!tailBone && bone.isBone && bone.name === "Tail") tailBone = bone;
  });
  const tailQuat = new THREE.Quaternion();

  type Mode = "idle" | "oneshot" | "stroll";
  const state = {
    mode: "idle" as Mode,
    active: null as Action | null,
    yaw: 0,
    time: 0,
    disposed: false,
    visible: true,
    pageVisible: !document.hidden,
    behaviorTimer: 0 as unknown as ReturnType<typeof setTimeout>,
    strollTargetX: 0,
    promptShown: false,
  };

  // «Окна» — якоря по горизонтали в пределах canvas
  const ANCHORS = [-0.85, 0, 0.85];
  let anchorIndex = 1;

  function fadeTo(action: Action, fade: number, timeScale = 1) {
    if (state.active === action) {
      action.setEffectiveTimeScale(timeScale);
      return;
    }
    const prev = state.active;
    state.active = action;
    action.reset().setEffectiveTimeScale(timeScale).setEffectiveWeight(1).fadeIn(fade).play();
    if (prev) prev.fadeOut(fade);
  }

  function playLoop(name: string, fade = 0.35, timeScale = 1) {
    const a = actions[name];
    if (!a) return;
    a.setLoop(THREE.LoopRepeat, Infinity);
    fadeTo(a, fade, timeScale);
  }

  function hidePrompt() {
    if (state.promptShown) {
      state.promptShown = false;
      opts.onPrompt?.(false);
    }
  }

  function startOneshot(name: string, timeScale = 1, onDone?: () => void) {
    const a = actions[name];
    if (!a) {
      endIdle();
      return;
    }
    clearTimeout(state.behaviorTimer);
    hidePrompt();
    state.mode = "oneshot";
    a.setLoop(THREE.LoopOnce, 1);
    a.clampWhenFinished = true;
    fadeTo(a, 0.25, timeScale);
    const onFinished = (e: { action: Action }) => {
      if (e.action !== a) return;
      mixer.removeEventListener("finished", onFinished as never);
      if (onDone) onDone();
      else endIdle();
    };
    mixer.addEventListener("finished", onFinished as never);
  }

  function endIdle() {
    if (state.disposed) return;
    state.mode = "idle";
    playLoop(CLIP.idle, 0.45);
    scheduleBehavior();
  }

  function scheduleBehavior(delaySec?: number) {
    clearTimeout(state.behaviorTimer);
    const delay = (delaySec ?? 9 + Math.random() * 9) * 1000;
    state.behaviorTimer = setTimeout(() => {
      if (state.disposed || document.hidden || state.mode !== "idle") return;
      const roll = Math.random();
      if (roll < 0.3) startStroll();
      else if (roll < 0.55) startOneshot(CLIP.wave);
      else startCall();
    }, delay);
  }

  // Долгий простой: жест «иди сюда» + бабл «Нажми на следующий урок!»
  function startCall() {
    startOneshot(CLIP.call, 1.15, () => {
      // бабл держим ещё немного после жеста
      state.behaviorTimer = setTimeout(() => {
        hidePrompt();
        if (!state.disposed) endIdle();
      }, 2600);
      state.mode = "idle";
      playLoop(CLIP.idle, 0.45);
    });
    // после startOneshot: он скрывает прежний бабл, новый показываем поверх
    if (!state.promptShown) {
      state.promptShown = true;
      opts.onPrompt?.(true);
    }
  }

  function startStroll() {
    clearTimeout(state.behaviorTimer);
    hidePrompt();
    const options = ANCHORS.map((_, i) => i).filter((i) => i !== anchorIndex);
    anchorIndex = options[(Math.random() * options.length) | 0];
    state.strollTargetX = ANCHORS[anchorIndex];
    state.mode = "stroll";
    playLoop(CLIP.walk, 0.25);
  }

  /** Пульс нового урока: «ура» + прыжок радости. */
  function celebrate() {
    if (state.disposed) return;
    startOneshot(CLIP.cheer, 1.1, () => startOneshot(CLIP.jump, 1.5));
  }

  /** Короткий фрагмент танца по событию пульса. */
  function dance() {
    if (state.disposed) return;
    const a = actions[CLIP.dance];
    if (!a) return endIdle();
    clearTimeout(state.behaviorTimer);
    hidePrompt();
    state.mode = "oneshot";
    a.setLoop(THREE.LoopOnce, 1);
    a.clampWhenFinished = false;
    fadeTo(a, 0.3, 1.4);
    // обрываем длинный клип через фрагмент
    state.behaviorTimer = setTimeout(() => {
      if (!state.disposed && state.active === a) endIdle();
    }, DANCE_FRAGMENT_SEC * 1000);
  }

  // --- покадровый цикл ---
  const clock = new THREE.Clock();
  const _q = new THREE.Quaternion();
  const _q2 = new THREE.Quaternion();
  const _e = new THREE.Euler();
  let firstFrameMarked = false;
  let rafId = 0;

  function dampYaw(current: number, target: number, kk: number, dt: number) {
    let d = target - current;
    while (d > Math.PI) d -= Math.PI * 2;
    while (d < -Math.PI) d += Math.PI * 2;
    return current + d * (1 - Math.exp(-kk * dt));
  }

  function frame() {
    if (state.disposed) return;
    rafId = requestAnimationFrame(frame);
    if (!state.visible || !state.pageVisible) return;

    const dt = Math.min(clock.getDelta(), 0.05);
    state.time += dt;
    const t = state.time;

    let targetYaw = 0;
    if (state.mode === "stroll") {
      const dx = state.strollTargetX - rig.position.x;
      if (Math.abs(dx) > 0.03) {
        targetYaw = Math.sign(dx) * 0.7; // лёгкий поворот в сторону перехода
        const step = Math.sign(dx) * Math.min(0.9 * dt, Math.abs(dx));
        rig.position.x += step;
      } else {
        rig.position.x = state.strollTargetX;
        endIdle();
      }
    }
    state.yaw = dampYaw(state.yaw, targetYaw, 6, dt);
    rig.rotation.y = state.yaw;

    mixer.update(dt);

    // Хвост — процедурно: назад от рига, упругое запаздывание + виляние
    if (tailBone) {
      const active = state.mode === "stroll";
      const wagSpeed = active ? 7 : 2.2;
      const wagAmp = active ? 0.28 : 0.12;
      _e.set(Math.sin(t * wagSpeed * 0.5) * 0.06, state.yaw + Math.sin(t * wagSpeed) * wagAmp, 0, "XYZ");
      _q.setFromEuler(_e);
      tailQuat.slerp(_q, 1 - Math.exp(-5 * dt));
      const parent = tailBone.parent;
      if (parent) {
        parent.getWorldQuaternion(_q2);
        tailBone.quaternion.copy(_q2.invert().multiply(tailQuat));
      }
    }

    renderer.render(scene, camera);
    if (!firstFrameMarked) {
      firstFrameMarked = true;
      try {
        performance.mark?.("foxi:first-frame");
        performance.measure?.("foxi:time-to-first-frame", "foxi:boot-start", "foxi:first-frame");
      } catch {
        /* marks опциональны */
      }
    }
  }

  // Пауза: вкладка скрыта или маскот вне вьюпорта
  const onVisibility = () => {
    state.pageVisible = !document.hidden;
    if (state.pageVisible) clock.getDelta();
  };
  document.addEventListener("visibilitychange", onVisibility);
  const io = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      state.visible = entry.isIntersecting;
      if (entry.isIntersecting) clock.getDelta();
    }
  });
  io.observe(container);

  const onResize = () => {
    const w = Math.max(container.clientWidth, 1);
    const h = Math.max(container.clientHeight, 1);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  };
  const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(onResize) : null;
  ro?.observe(container);

  playLoop(CLIP.idle);
  canvas.style.opacity = "1";
  scheduleBehavior(3.5);
  frame();
  opts.onReady?.();

  function dispose() {
    state.disposed = true;
    clearTimeout(state.behaviorTimer);
    cancelAnimationFrame(rafId);
    document.removeEventListener("visibilitychange", onVisibility);
    io.disconnect();
    ro?.disconnect();
    hidePrompt();
    mixer.stopAllAction();
    mixer.uncacheRoot(model);
    scene.traverse((o) => {
      const mesh = o as InstanceType<Three["Mesh"]>;
      if (mesh.isMesh) {
        mesh.geometry?.dispose();
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const m of mats) {
          const mat = m as InstanceType<Three["Material"]> & { map?: InstanceType<Three["Texture"]> | null };
          mat.map?.dispose();
          mat.dispose();
        }
      }
    });
    draco.dispose();
    renderer.dispose();
    canvas.remove();
  }

  return { celebrate, dance, dispose };
}
