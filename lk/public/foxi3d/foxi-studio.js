// Студия Фокси — игровой движок «Создай своего Фокси» для ЛК (2026-11-05).
//
// Это НАСТОЯЩИЙ маскот: модель /assets/foxi-rigged-v2.glb (тот же Фокси, что в Мире), со скелетом
// и клипами анимаций. Движок:
//  • анимации — микшер three.js с плавными переходами (Idle по кругу + жесты по кнопке и сами по себе),
//    хвост качается процедурно (в клипах его нет), моргание взглядом-камерой;
//  • перекраска без новых текстур — шейдер на лету: по цвету текстуры и месту на теле (поза привязки)
//    различает шерсть, глаза, футболку, логотип, шорты, рюкзак и кеды и красит их, сохраняя тени и ворс;
//  • узоры на футболке (полоски, горошек, клетка, звёзды) — тоже в шейдере, в координатах тела;
//  • вещи (шапки, очки, шарф, бабочка, медаль, плащ, причёски) — 3D-объекты, прикреплённые к костям
//    головы и груди: двигаются вместе с Фокси в любой анимации.
// Подключение: const { createFoxiStudio } = await import("/foxi3d/foxi-studio.js").
import * as THREE from "/vendor/three/three.module.min.js";
import { GLTFLoader } from "/vendor/three/GLTFLoader.js";
import { DRACOLoader } from "/vendor/three/DRACOLoader.js";
import { OrbitControls } from "/vendor/three/OrbitControls.js";

const MODEL = "/assets/foxi-rigged-v2.glb";
const DRACO = "/vendor/three/draco/";

export const DEFAULT_LOOK = {
  fur: "#c4652a", eyes: "#568698", top: "#d6b85e", pattern: "none", patternColor: "#6a3fc4",
  logo: true, bottom: "#421b5f", bag: "#421b5f", shoes: "#421b5f",
  hat: "none", hatColor: "#e2533c", hair: "none", glasses: "none", neck: "none", neckColor: "#e2533c", back: "none",
};

export const ANIMS = {
  idle: "Idle", wave: "Big_Wave_Hello", cheer: "Cheer_with_Both_Hands_Up", jump: "Happy_jump_f",
  dance: "Shake_It_Off_Dance", walk: "Walk_Inplace", run: "Running", call: "Call_Gesture",
};

const PATTERNS = { none: 0, stripes: 1, dots: 2, checks: 3, stars: 4, zigzag: 5 };

// ---------- шейдер перекраски ----------
const RECOLOR_VERT_DECL = "varying vec3 vBindPos;\n";
const RECOLOR_FRAG_DECL = `
varying vec3 vBindPos;
uniform vec3 uFur; uniform vec3 uEyes; uniform vec3 uTop; uniform vec3 uPatternColor; uniform vec3 uLogo;
uniform vec3 uBottom; uniform vec3 uBag; uniform vec3 uShoes; uniform float uPattern; uniform float uLogoOn;
vec3 toSRGB(vec3 c) { return pow(max(c, 0.0), vec3(1.0 / 2.2)); }
vec3 toLin(vec3 c) { return pow(max(c, 0.0), vec3(2.2)); }
vec3 rgb2hsv(vec3 c) {
  vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
  vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
  vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
  float d = q.x - min(q.w, q.y);
  float e = 1.0e-10;
  return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}
vec3 hsv2rgb(vec3 c) {
  vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
  vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
  return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}
// Перекраска с сохранением ворса и светотени: оттенок берём у нового цвета, а насыщенность и яркость
// пикселя меняем во столько раз, во сколько новый цвет отличается от «среднего» цвета этой части текстуры.
// Если выбран исходный цвет — пиксель остаётся как был.
vec3 paint(vec3 srcHsv, vec3 target, vec3 ref) {
  vec3 t = rgb2hsv(toSRGB(target));   // цвета приходят из three.js в линейном пространстве
  // оттенок сдвигаем на разницу «новый − средний исходный»: переливы ворса сохраняются
  float dh = t.x - ref.x;
  float hue = fract(srcHsv.x + (t.y < 0.06 ? 0.0 : dh));
  float sat = clamp(srcHsv.y * t.y / max(ref.y, 0.01), 0.0, 1.0);
  float val = clamp(srcHsv.z * t.z / max(ref.z, 0.01), 0.0, 1.0);
  return hsv2rgb(vec3(hue, sat, val));
}
const vec3 REF_FUR = vec3(0.0611, 0.80, 0.72);
const vec3 REF_TOP = vec3(0.125, 0.535, 0.784);
const vec3 REF_PURPLE = vec3(0.761, 0.72, 0.37);
const vec3 REF_EYE = vec3(0.544, 0.43, 0.60);
float starMask(vec2 p) {
  vec2 c = fract(p) - 0.5; float a = atan(c.y, c.x); float r = length(c);
  float star = 0.18 + 0.09 * cos(5.0 * a); return 1.0 - smoothstep(star - 0.02, star + 0.02, r);
}
float patternMask(vec3 p) {
  if (uPattern < 0.5) return 0.0;
  if (uPattern < 1.5) return step(0.5, fract(p.y * 26.0));
  if (uPattern < 2.5) { vec2 c = fract(vec2(p.x + p.z, p.y) * 22.0) - 0.5; return 1.0 - smoothstep(0.2, 0.25, length(c)); }
  if (uPattern < 3.5) return mod(floor((p.x + p.z) * 18.0) + floor(p.y * 18.0), 2.0);
  if (uPattern < 4.5) return starMask(vec2(p.x + p.z, p.y) * 14.0);
  return step(0.5, fract(p.y * 22.0 + abs(fract((p.x + p.z) * 11.0) - 0.5) * 1.6));
}
`;
const RECOLOR_FRAG_BODY = `
{
  vec3 s = toSRGB(diffuseColor.rgb);
  vec3 h = rgb2hsv(s); float hue = h.x * 360.0; float sat = h.y; float val = h.z;
  vec3 hp = h;
  vec3 p = vBindPos;
  vec3 outc = s;
  bool torso = p.y > 0.44 && p.y < 0.82 && abs(p.x) < 0.34;
  bool purple = hue > 250.0 && hue < 305.0 && sat > 0.28 && val > 0.12;
  if (p.y < 0.13) {
    // кеды: фиолетовые части — в цвет кед, белое остаётся
    if (purple) outc = paint(hp, uShoes, REF_PURPLE);
  } else if (purple && p.y < 0.47 && p.y > 0.2) {
    outc = paint(hp, uBottom, REF_PURPLE);                                     // шорты
  } else if (purple && torso) {
    if (p.z > 0.15 && abs(p.x) < 0.075 && p.y < 0.74) {
      outc = uLogoOn > 0.5 ? toSRGB(uLogo) * (0.8 + 0.2 * val / 0.4) : paint(vec3(hp.x, REF_TOP.y, REF_TOP.z), uTop, REF_TOP);  // логотип «Фоксинбург»
    } else {
      outc = paint(hp, uBag, REF_PURPLE);                                      // рюкзак и лямки
    }
  } else if (torso && hue > 36.0 && hue < 68.0 && sat > 0.22 && val > 0.45) {
    vec3 base = paint(hp, uTop, REF_TOP);                               // футболка
    float m = patternMask(p);
    outc = mix(base, paint(hp, uPatternColor, REF_TOP), m);
  } else if ((hue < 42.0 || hue > 345.0) && sat > 0.42 && val > 0.12) {
    outc = paint(hp, uFur, REF_FUR);                                        // рыжая шерсть
  } else if (p.y > 0.86 && p.y < 0.96 && p.z > 0.2 && hue > 165.0 && hue < 235.0 && sat > 0.2) {
    outc = paint(hp, uEyes, REF_EYE);                                       // радужка
  }
  diffuseColor.rgb = toLin(outc);
}
`;

function makeMaterial(src, uniforms) {
  const mat = new THREE.MeshStandardMaterial({ map: src.map, roughness: 0.78, metalness: 0, side: THREE.DoubleSide });
  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = RECOLOR_VERT_DECL + shader.vertexShader.replace(
      "#include <begin_vertex>", "#include <begin_vertex>\n vBindPos = position;");
    shader.fragmentShader = RECOLOR_FRAG_DECL + shader.fragmentShader.replace(
      "#include <map_fragment>", "#include <map_fragment>\n" + RECOLOR_FRAG_BODY).replace(
      "#include <emissivemap_fragment>", "#include <emissivemap_fragment>\n totalEmissiveRadiance += diffuseColor.rgb * 0.42;");
  };
  return mat;
}

// ---------- вещи на костях (координаты — тело в позе привязки, метры модели; лицо смотрит в +Z) ----------
const std = (color, rough = 0.6, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: 0, ...extra });
const gold = () => std("#f2c230", 0.3, { metalness: 0.55, emissive: "#6b4b00", emissiveIntensity: 0.25 });
function mesh(geo, mat, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, sx = 1, sy = sx, sz = sx) {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(x, y, z); m.rotation.set(rx, ry, rz); m.scale.set(sx, sy, sz);
  m.castShadow = true;
  return m;
}
const HEAD_TOP = new THREE.Vector3(0, 1.1, 0.1);   // макушка между ушами

function buildHat(kind, color) {
  const g = new THREE.Group(); g.name = "hat";
  const c = std(color, 0.7);
  const { x, y, z } = HEAD_TOP;
  if (kind === "cap") {
    g.add(mesh(new THREE.SphereGeometry(0.155, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), c, x, y - 0.04, z, 0, 0, 0, 1, 0.85, 1.08));
    g.add(mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.012, 32, 1, false, -Math.PI / 2, Math.PI), c, x, y - 0.045, z + 0.1, 0.1, 0, 0, 1.05, 1, 1.45));
    g.add(mesh(new THREE.SphereGeometry(0.018, 12, 8), std("#ffffff"), x, y + 0.07, z));
  }
  if (kind === "beanie") {
    g.add(mesh(new THREE.SphereGeometry(0.15, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), c, x, y - 0.05, z - 0.01, 0, 0, 0, 1, 0.95, 1));
    g.add(mesh(new THREE.TorusGeometry(0.145, 0.026, 12, 40), std("#f4f1ea", 0.95), x, y - 0.05, z - 0.01, Math.PI / 2));
    g.add(mesh(new THREE.IcosahedronGeometry(0.045, 2), std("#f4f1ea", 0.95), x, y + 0.105, z - 0.01));
  }
  if (kind === "wizard") {
    g.add(mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.012, 48), c, x, y - 0.055, z));
    const cone = mesh(new THREE.ConeGeometry(0.11, 0.32, 40, 6), c, x, y + 0.1, z - 0.03, -0.25);
    g.add(cone);
    for (const [sx, sy, sz] of [[0.05, 0.05, 0.1], [-0.04, 0.13, 0.06], [0.02, 0.21, 0.03]]) {
      g.add(mesh(new THREE.OctahedronGeometry(0.018), std("#ffd36e", 0.3, { emissive: "#ffb300", emissiveIntensity: 0.8 }), x + sx, y + sy, z + sz));
    }
  }
  if (kind === "crown") {
    const gm = gold();
    g.add(mesh(new THREE.CylinderGeometry(0.1, 0.105, 0.05, 10, 1, true), gm, x, y, z));
    for (let i = 0; i < 5; i++) {
      const a = (i / 5) * Math.PI * 2;
      g.add(mesh(new THREE.ConeGeometry(0.026, 0.06, 8), gm, x + Math.sin(a) * 0.1, y + 0.05, z + Math.cos(a) * 0.1));
      g.add(mesh(new THREE.SphereGeometry(0.014, 10, 8), std(i % 2 ? "#e2533c" : "#3a7bd5", 0.2), x + Math.sin(a) * 0.104, y, z + Math.cos(a) * 0.104));
    }
  }
  if (kind === "tophat") {
    g.add(mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.012, 48), c, x, y - 0.02, z));
    g.add(mesh(new THREE.CylinderGeometry(0.09, 0.095, 0.17, 40), c, x, y + 0.07, z));
    g.add(mesh(new THREE.CylinderGeometry(0.097, 0.097, 0.03, 40), std("#e2533c"), x, y + 0.0, z));
  }
  if (kind === "party") {
    g.add(mesh(new THREE.ConeGeometry(0.08, 0.22, 32), c, x, y + 0.08, z, 0, 0, 0.15));
    g.add(mesh(new THREE.SphereGeometry(0.025, 12, 8), std("#ffd36e"), x - 0.016, y + 0.2, z));
  }
  if (kind === "headphones") {
    g.add(mesh(new THREE.TorusGeometry(0.25, 0.016, 10, 48, Math.PI), c, 0, 0.95, 0.06, 0, 0, 0, 1, 0.82, 1));
    for (const s of [-1, 1]) g.add(mesh(new THREE.CylinderGeometry(0.065, 0.065, 0.05, 28), c, s * 0.235, 0.94, 0.06, 0, 0, Math.PI / 2));
  }
  if (kind === "flower") {
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2;
      g.add(mesh(new THREE.SphereGeometry(0.03, 14, 10), std(color, 0.6), 0.15 + Math.cos(a) * 0.035, 1.09 + Math.sin(a) * 0.035, 0.18, 0, 0, 0, 1, 1, 0.45));
    }
    g.add(mesh(new THREE.SphereGeometry(0.022, 12, 8), std("#ffd36e", 0.4), 0.15, 1.09, 0.19));
  }
  if (kind === "halo") {
    g.add(mesh(new THREE.TorusGeometry(0.12, 0.012, 10, 48), std("#ffe28a", 0.3, { emissive: "#ffcf40", emissiveIntensity: 1.2 }), x, y + 0.12, z, Math.PI / 2));
  }
  return g;
}

function buildHair(kind, fur) {
  const g = new THREE.Group(); g.name = "hair";
  const m = std(fur, 0.85);
  const { x, y, z } = HEAD_TOP;
  const spike = (dx, dy, dz, rx, rz, s = 1) => g.add(mesh(new THREE.ConeGeometry(0.03 * s, 0.11 * s, 12), m, x + dx, y + dy, z + dz, rx, 0, rz));
  if (kind === "tuft") { spike(0, 0.03, 0.06, 0.6, 0, 1.2); spike(-0.03, 0.02, 0.07, 0.7, 0.5); spike(0.03, 0.02, 0.07, 0.7, -0.5); }
  if (kind === "mohawk") for (let i = 0; i < 6; i++) spike(0, 0.03 - Math.abs(i - 2) * 0.004, 0.11 - i * 0.045, 0.2 - i * 0.12, 0, 1.25);
  if (kind === "spiky") for (let i = -2; i <= 2; i++) spike(i * 0.035, 0.02 - Math.abs(i) * 0.008, 0.05, 0.4, -i * 0.35, 1.1);
  if (kind === "curly") for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    g.add(mesh(new THREE.IcosahedronGeometry(0.032, 2), m, x + Math.cos(a) * 0.055, y + 0.005 + Math.sin(a * 3) * 0.006, z + Math.sin(a) * 0.055));
  }
  return g;
}

function buildGlasses(kind) {
  const g = new THREE.Group(); g.name = "glasses";
  if (kind === "none") return g;
  const frame = std(kind === "star" ? "#ef6aa8" : kind === "gold" ? "#d9a520" : "#1d1a22", 0.3);
  const y = 0.918, z = 0.262;
  for (const s of [-1, 1]) {
    const cx = s * 0.074;
    if (kind === "star") {
      const shape = new THREE.Shape();
      for (let i = 0; i < 10; i++) {
        const r = i % 2 ? 0.026 : 0.06; const a = (i / 10) * Math.PI * 2 + Math.PI / 2;
        if (i === 0) shape.moveTo(Math.cos(a) * r, Math.sin(a) * r); else shape.lineTo(Math.cos(a) * r, Math.sin(a) * r);
      }
      g.add(mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.008, bevelEnabled: false }), frame, cx, y, z, 0, s * 0.25));
    } else {
      g.add(mesh(new THREE.TorusGeometry(0.048, 0.007, 10, 36), frame, cx, y, z, 0, s * 0.28));
      if (kind === "sun") g.add(mesh(new THREE.CircleGeometry(0.046, 32), std("#141824", 0.1, { transparent: true, opacity: 0.85 }), cx, y, z + 0.002, 0, s * 0.28));
    }
    g.add(mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.13, 6), frame, s * 0.13, y + 0.005, z - 0.07, Math.PI / 2, 0, 0));
  }
  g.add(mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.05, 8), frame, 0, y + 0.01, z + 0.01, 0, 0, Math.PI / 2));
  return g;
}

function buildNeck(kind, color) {
  const g = new THREE.Group(); g.name = "neck";
  const c = std(color, 0.85);
  if (kind === "scarf") {
    g.add(mesh(new THREE.TorusGeometry(0.092, 0.026, 14, 40), c, 0, 0.75, 0.135, Math.PI / 2 + 0.1, 0, 0, 1.12, 1, 1));
    g.add(mesh(new THREE.BoxGeometry(0.05, 0.14, 0.02), c, 0.05, 0.68, 0.235, 0.18, 0, 0.12));
    g.add(mesh(new THREE.BoxGeometry(0.05, 0.11, 0.02), c, 0.0, 0.69, 0.24, 0.15, 0, -0.1));
  }
  if (kind === "bowtie") {
    for (const s of [-1, 1]) g.add(mesh(new THREE.ConeGeometry(0.035, 0.06, 4), c, s * 0.03, 0.755, 0.24, 0, 0, s * Math.PI / 2));
    g.add(mesh(new THREE.SphereGeometry(0.016, 10, 8), c, 0, 0.755, 0.245));
  }
  if (kind === "medal") {
    g.add(mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.008, 32), gold(), 0, 0.6, 0.235, Math.PI / 2 - 0.15));
    for (const s of [-1, 1]) g.add(mesh(new THREE.BoxGeometry(0.022, 0.15, 0.006), c, s * 0.03, 0.68, 0.225, -0.15, 0, s * 0.3));
  }
  if (kind === "tie") {
    g.add(mesh(new THREE.BoxGeometry(0.04, 0.03, 0.02), c, 0, 0.755, 0.24));
    g.add(mesh(new THREE.ConeGeometry(0.035, 0.16, 4), c, 0, 0.66, 0.235, Math.PI, Math.PI / 4, 0, 1, 1, 0.35));
  }
  return g;
}

function buildBack(kind, color) {
  const g = new THREE.Group(); g.name = "back";
  if (kind === "cape") {
    const geo = new THREE.CylinderGeometry(0.17, 0.34, 0.6, 48, 8, true, Math.PI * 0.5, Math.PI);
    g.add(mesh(geo, std(color, 0.6, { side: THREE.DoubleSide }), 0, 0.46, 0.08));
  }
  if (kind === "wings") {
    const shape = new THREE.Shape();
    shape.moveTo(0, 0); shape.bezierCurveTo(0.12, 0.2, 0.32, 0.18, 0.3, 0.02); shape.bezierCurveTo(0.24, -0.06, 0.1, -0.08, 0, 0);
    const wm = std("#ffffff", 0.4, { transparent: true, opacity: 0.85, emissive: "#c9e8ff", emissiveIntensity: 0.4, side: THREE.DoubleSide });
    for (const s of [-1, 1]) g.add(mesh(new THREE.ShapeGeometry(shape, 24), wm, s * 0.05, 0.62, -0.14, 0, s > 0 ? -0.5 : Math.PI + 0.5, 0));
  }
  return g;
}

// ---------- студия ----------
export async function createFoxiStudio(canvas, look = DEFAULT_LOOK, opts = {}) {
  const still = opts.still || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 30);
  const controls = new OrbitControls(camera, canvas);
  controls.enablePan = false; controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.minDistance = 0.9; controls.maxDistance = 4.2;
  controls.minPolarAngle = 0.45; controls.maxPolarAngle = 1.62;

  scene.add(new THREE.HemisphereLight("#fff4e6", "#7b6aa8", 1.25));
  const key = new THREE.DirectionalLight("#fff3e0", 2.4);
  key.position.set(1.6, 3, 2.4); key.castShadow = true; key.shadow.mapSize.set(1024, 1024);
  key.shadow.camera.left = -1; key.shadow.camera.right = 1; key.shadow.camera.top = 1.6; key.shadow.camera.bottom = -0.4;
  key.shadow.bias = -0.0005; key.shadow.normalBias = 0.02;
  scene.add(key);
  const fill = new THREE.DirectionalLight("#cfe0ff", 0.7); fill.position.set(-2, 1.5, 2); scene.add(fill);
  const rim = new THREE.DirectionalLight("#d8c4ff", 1.6); rim.position.set(-1.5, 2.2, -2.5); scene.add(rim);

  // подиум, как в редакторе персонажа
  const podium = new THREE.Group();
  podium.add(mesh(new THREE.CylinderGeometry(0.62, 0.66, 0.06, 64), std(opts.podium ?? "#ffffff", 0.5), 0, -0.03, 0));
  const ring = mesh(new THREE.TorusGeometry(0.64, 0.012, 8, 96), std("#ffd36e", 0.3, { emissive: "#ffb300", emissiveIntensity: 0.6 }), 0, 0.0, 0, Math.PI / 2);
  podium.add(ring);
  podium.children[0].receiveShadow = true;
  scene.add(podium);

  const gltf = await new GLTFLoader().setDRACOLoader(new DRACOLoader().setDecoderPath(DRACO)).loadAsync(opts.model ?? MODEL);
  const model = gltf.scene;
  let skinned = null;
  model.traverse((o) => { if (o.isSkinnedMesh) skinned = o; });
  if (!skinned) throw new Error("foxi: нет скина в модели");
  skinned.castShadow = true; skinned.frustumCulled = false;

  const uniforms = {
    uFur: { value: new THREE.Color() }, uEyes: { value: new THREE.Color() }, uTop: { value: new THREE.Color() },
    uPatternColor: { value: new THREE.Color() }, uLogo: { value: new THREE.Color() }, uBottom: { value: new THREE.Color() },
    uBag: { value: new THREE.Color() }, uShoes: { value: new THREE.Color() }, uPattern: { value: 0 }, uLogoOn: { value: 1 },
  };
  skinned.material = makeMaterial(skinned.material, uniforms);
  model.position.z = -0.1; // центр корпуса — над центром подиума
  scene.add(model);

  // крепления к костям: группа, которая в позе привязки совпадает с системой координат тела
  model.updateMatrixWorld(true);
  const attach = (boneName) => {
    const bone = model.getObjectByName(boneName);
    const holder = new THREE.Group();
    bone.add(holder);
    const inv = new THREE.Matrix4().copy(bone.matrixWorld).invert().multiply(model.matrixWorld);
    inv.decompose(holder.position, holder.quaternion, holder.scale);
    return holder;
  };
  const onHead = attach("Head");
  const onChest = attach("Spine");
  const onNeck = attach("neck");

  const mixer = new THREE.AnimationMixer(model);
  const actions = {};
  for (const clip of gltf.animations) {
    // хвост в клипах не анимирован — убираем его дорожки, им управляет движок
    clip.tracks = clip.tracks.filter((t) => !t.name.startsWith("Tail."));
    actions[clip.name] = mixer.clipAction(clip);
  }
  const tail = model.getObjectByName("Tail");
  const tailRest = tail ? tail.quaternion.clone() : null;
  let current = actions[ANIMS.idle];
  current?.play();
  let busyUntil = 0; let nextFidget = 6;

  const play = (name, { loop = false, fade = 0.35 } = {}) => {
    const clipName = ANIMS[name] ?? name;
    const next = actions[clipName];
    if (!next || next === current && loop) return;
    next.reset();
    next.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, loop ? Infinity : 1);
    next.clampWhenFinished = !loop;
    next.enabled = true; next.setEffectiveWeight(1);
    next.play();
    current?.crossFadeTo(next, fade, false);
    current = next;
    const len = next.getClip().duration;
    busyUntil = loop ? 0 : clock.elapsedTime + Math.min(len, clipName === ANIMS.dance ? 8 : clipName === ANIMS.jump ? 5 : len) - fade;
  };
  const toIdle = () => play("idle", { loop: true, fade: 0.5 });

  let state = { ...DEFAULT_LOOK };
  const props = { hat: null, hair: null, glasses: null, neck: null, back: null };
  const replace = (slot, parent, obj) => {
    if (props[slot]) { parent.remove(props[slot]); props[slot].traverse((o) => { o.geometry?.dispose(); o.material?.dispose?.(); }); }
    props[slot] = obj; parent.add(obj);
  };
  const set = (next = {}) => {
    const prev = state;
    state = { ...DEFAULT_LOOK, ...next };
    uniforms.uFur.value.set(state.fur); uniforms.uEyes.value.set(state.eyes);
    uniforms.uTop.value.set(state.top); uniforms.uPatternColor.value.set(state.patternColor);
    uniforms.uBottom.value.set(state.bottom); uniforms.uBag.value.set(state.bag); uniforms.uShoes.value.set(state.shoes);
    uniforms.uPattern.value = PATTERNS[state.pattern] ?? 0; uniforms.uLogoOn.value = state.logo ? 1 : 0;
    const top = new THREE.Color(state.top); const hsl = {}; top.getHSL(hsl);
    uniforms.uLogo.value.set(hsl.l > 0.55 ? "#3b2266" : "#fff6e0");   // логотип всегда читается на футболке
    if (prev.hat !== state.hat || prev.hatColor !== state.hatColor || !props.hat) replace("hat", onHead, buildHat(state.hat, state.hatColor));
    const hairVisible = ["none", "headphones", "flower", "halo"].includes(state.hat);
    replace("hair", onHead, hairVisible ? buildHair(state.hair, state.fur) : new THREE.Group());
    if (prev.glasses !== state.glasses || !props.glasses) replace("glasses", onHead, buildGlasses(state.glasses));
    if (prev.neck !== state.neck || prev.neckColor !== state.neckColor || !props.neck) replace("neck", state.neck === "scarf" ? onNeck : onChest, buildNeck(state.neck, state.neckColor));
    if (prev.back !== state.back || prev.neckColor !== state.neckColor || !props.back) replace("back", onChest, buildBack(state.back, state.neckColor));
  };
  set(look);

  // камера: весь рост / крупно мордочка
  const views = {
    body: { pos: new THREE.Vector3(0.55, 0.85, 2.65), target: new THREE.Vector3(0, 0.6, 0) },
    face: { pos: new THREE.Vector3(0.25, 1.02, 1.55), target: new THREE.Vector3(0, 0.9, -0.02) },
  };
  let fly = null;
  const focus = (name = "body", instant = false) => {
    const v = views[name] ?? views.body;
    if (instant) { camera.position.copy(v.pos); controls.target.copy(v.target); controls.update(); return; }
    fly = { from: camera.position.clone(), fromT: controls.target.clone(), to: v.pos, toT: v.target, t: 0 };
  };
  focus("body", true);

  const resize = () => {
    const w = canvas.clientWidth || 300, h = canvas.clientHeight || 300;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  };
  resize();
  const ro = new ResizeObserver(resize); ro.observe(canvas);

  const clock = new THREE.Clock();
  const tmpQ = new THREE.Quaternion(); const axis = new THREE.Vector3(0, 0, 1);
  let raf = 0; let spin = 0;
  const tick = () => {
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;
    if (!still) mixer.update(dt);
    if (busyUntil && t > busyUntil) { busyUntil = 0; toIdle(); }
    if (!still && !busyUntil && t > nextFidget) {           // сам по себе иногда машет или радуется
      play(Math.random() < 0.6 ? "wave" : "cheer");
      nextFidget = t + 9 + Math.random() * 8;
    }
    if (tail && tailRest && !still) {
      tmpQ.setFromAxisAngle(axis, Math.sin(t * 2.4) * 0.28 + Math.sin(t * 0.7) * 0.08);
      tail.quaternion.copy(tailRest).multiply(tmpQ);
    }
    ring.material.emissiveIntensity = 0.45 + Math.sin(t * 2) * 0.2;
    if (spin) model.rotation.y += spin * dt;
    if (fly) {
      fly.t = Math.min(1, fly.t + dt * 1.6);
      const e = 1 - Math.pow(1 - fly.t, 3);
      camera.position.lerpVectors(fly.from, fly.to, e); controls.target.lerpVectors(fly.fromT, fly.toT, e);
      if (fly.t >= 1) fly = null;
    }
    controls.update();
    renderer.render(scene, camera);
    raf = requestAnimationFrame(tick);
  };
  tick();

  return {
    set,
    play: (name) => { nextFidget = clock.elapsedTime + 12; play(name, { loop: name === "idle" || name === "walk" || name === "run" }); if (name === "walk" || name === "run") busyUntil = clock.elapsedTime + 4; },
    focus,
    turntable: (on) => { spin = on ? 0.6 : 0; },
    snapshot: () => { renderer.render(scene, camera); return canvas.toDataURL("image/png"); },
    anims: Object.keys(ANIMS).filter((k) => actions[ANIMS[k]]),
    dispose: () => {
      cancelAnimationFrame(raf); ro.disconnect(); controls.dispose(); mixer.stopAllAction();
      scene.traverse((o) => { o.geometry?.dispose(); if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => { m.map?.dispose(); m.dispose(); }); });
      renderer.dispose();
    },
  };
}
