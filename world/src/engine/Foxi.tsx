"use client";

import { useEffect, useRef } from "react";
import { useAnimations, useGLTF } from "@react-three/drei";
import type { Group } from "three";

export type FoxiClip = "idle" | "wave" | "cheer" | "jump";

/** Имена клипов внутри foxi-rigged.glb — других в файле нет. */
const CLIP_NAMES: Record<FoxiClip, string> = {
  idle: "Walking",
  wave: "Big_Wave_Hello",
  cheer: "Cheer_with_Both_Hands_Up",
  jump: "Happy_jump_f",
};

type Props = { clip: FoxiClip; position?: [number, number, number] };

export function Foxi({ clip, position = [2.4, 0, -0.4] }: Props) {
  const group = useRef<Group>(null);
  const { scene, animations } = useGLTF("/assets/foxi-rigged.glb");
  const { actions } = useAnimations(animations, group);

  useEffect(() => {
    const name = CLIP_NAMES[clip];
    const action = actions[name];
    if (!action) return;
    action.reset().fadeIn(0.35).play();
    return () => {
      action.fadeOut(0.35);
    };
  }, [actions, clip]);

  return (
    <group ref={group} position={position} rotation={[0, -0.4, 0]}>
      <primitive object={scene} scale={0.9} castShadow />
    </group>
  );
}

useGLTF.preload("/assets/foxi-rigged.glb");
