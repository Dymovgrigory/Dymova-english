"use client";

import { useFrame, useThree } from "@react-three/fiber";
import { PerspectiveCamera, Vector3 } from "three";

export type CameraShot = "courtyard" | "school" | "foxi" | "reward";

type Shot = { position: Vector3; target: Vector3; fov: number };

/** Точки съёмки: дистанция 6–8 u (courtyard/school), ~1.8 u и fov 30° для reward. */
const SHOTS: Record<CameraShot, Shot> = {
  courtyard: { position: new Vector3(0, 3.3, 5), target: new Vector3(0, 2.4, -2), fov: 38 },
  school: { position: new Vector3(-1.8, 3, 2), target: new Vector3(0.2, 4, -5), fov: 38 },
  foxi: { position: new Vector3(1.7, 1, 3.4), target: new Vector3(2.4, 1.3, -0.4), fov: 38 },
  reward: { position: new Vector3(2.52, 1.44, 1.4), target: new Vector3(2.4, 1.5, -0.4), fov: 30 },
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
