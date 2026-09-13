"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Points } from "three";
import { BufferAttribute, BufferGeometry } from "three";

/** Светлячки: мир не должен выглядеть мёртвым (world-art-bible §6). */
export function Fireflies({ count }: { count: number }) {
  const points = useRef<Points>(null);

  const geometry = useMemo(() => {
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 34;
      positions[i * 3 + 1] = Math.random() * 9 + 0.5;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 34;
    }
    const geom = new BufferGeometry();
    geom.setAttribute("position", new BufferAttribute(positions, 3));
    return geom;
  }, [count]);

  useFrame((state) => {
    if (points.current) {
      points.current.rotation.y = state.clock.elapsedTime * 0.02;
    }
  });

  if (count === 0) return null;

  return (
    <points ref={points} geometry={geometry}>
      <pointsMaterial
        size={0.09}
        color="#f5ed75"
        transparent
        opacity={0.8}
        sizeAttenuation
      />
    </points>
  );
}
