"use client";

import { useFrame, useThree } from "@react-three/fiber";
import { Vector3 } from "three";

export type CameraShot = "courtyard" | "school" | "foxi" | "reward";

/** Точки съёмки: дистанция 6–8 u, высота 2.5–3.5 u; reward — 1.8 u, low-angle. */
const SHOTS: Record<CameraShot, { position: Vector3; target: Vector3 }> = {
  courtyard: { position: new Vector3(0, 3.4, 12), target: new Vector3(0, 2.2, -4) },
  school: { position: new Vector3(-2.4, 3.2, 4.5), target: new Vector3(0, 4.2, -8) },
  foxi: { position: new Vector3(1.6, 2.6, 3.2), target: new Vector3(2.4, 1.1, -0.4) },
  reward: { position: new Vector3(2.2, 1.4, 2.6), target: new Vector3(2.4, 1.5, -0.4) },
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
  });

  return null;
}
