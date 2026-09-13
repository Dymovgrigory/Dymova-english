"use client";

import { useRef } from "react";
import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import type { Group } from "three";

type Props = {
  position?: [number, number, number];
  /** Вихрь монет в кинематографике награды. */
  swirl?: boolean;
  seed?: number;
};

export function FoxCoin({ position = [0, 1.2, 0], swirl = false, seed = 0 }: Props) {
  const group = useRef<Group>(null);
  const { scene } = useGLTF("/assets/school-foxcoin-v1.glb");

  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.elapsedTime + seed;
    group.current.rotation.y = t * 1.6;
    if (swirl) {
      group.current.position.set(
        position[0] + Math.cos(t * 1.2) * 0.8,
        position[1] + Math.sin(t * 2) * 0.35 + 0.3,
        position[2] + Math.sin(t * 1.2) * 0.8,
      );
    } else {
      group.current.position.set(position[0], position[1] + Math.sin(t) * 0.08, position[2]);
    }
  });

  return (
    <group ref={group}>
      <primitive object={scene.clone()} scale={0.5} />
      <pointLight color="#f5ed75" intensity={2.4} distance={3} />
    </group>
  );
}

useGLTF.preload("/assets/school-foxcoin-v1.glb");
