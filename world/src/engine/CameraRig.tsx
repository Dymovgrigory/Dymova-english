"use client";

import { useFrame, useThree } from "@react-three/fiber";
import { PerspectiveCamera, Vector3 } from "three";

export type CameraShot = "courtyard" | "school" | "foxi" | "reward";

type Shot = { position: Vector3; target: Vector3; fov: number };

/**
 * Точки съёмки. Дистанция общего плана (courtyard/school) сознательно больше
 * рекомендованных арт-библией 6–8 u: здание школы высотой 12–14 u физически не
 * помещается в кадр с более близкой точки — крыша и Фокси обрезаются. Более
 * тесные значения ломали композицию (проверено вживую), поэтому возвращены
 * прежние координаты, которые её не ломают.
 */
const SHOTS: Record<CameraShot, Shot> = {
  courtyard: { position: new Vector3(0, 3.4, 12), target: new Vector3(0, 2.2, -4), fov: 38 },
  school: { position: new Vector3(-2.4, 3.2, 4.5), target: new Vector3(0, 4.2, -8), fov: 38 },
  foxi: { position: new Vector3(1.6, 2.6, 3.2), target: new Vector3(2.4, 1.1, -0.4), fov: 38 },
  reward: { position: new Vector3(2.2, 1.4, 2.6), target: new Vector3(2.4, 1.5, -0.4), fov: 30 },
};

const target = new Vector3();

export function CameraRig({ shot }: { shot: CameraShot }) {
  const camera = useThree((state) => state.camera);

  useFrame((_, delta) => {
    const next = SHOTS[shot];
    const damping = 1 - Math.pow(0.001, delta);
    camera.position.lerp(next.position, damping);
    target.lerp(next.target, damping);
    camera.lookAt(target);

    if (camera instanceof PerspectiveCamera) {
      camera.fov += (next.fov - camera.fov) * damping;
      camera.updateProjectionMatrix();
    }
  });

  return null;
}
