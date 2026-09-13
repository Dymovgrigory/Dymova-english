"use client";

import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";

/** Subtle bloom + vignette — «не максимум постоянно» (world-art-bible §6). */
export function Postfx() {
  return (
    <EffectComposer>
      <Bloom intensity={0.45} luminanceThreshold={0.65} luminanceSmoothing={0.25} mipmapBlur />
      <Vignette eskil={false} offset={0.25} darkness={0.55} />
    </EffectComposer>
  );
}
