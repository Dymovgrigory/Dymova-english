"use client";

import { Canvas } from "@react-three/fiber";
import { Suspense, type ReactNode } from "react";
import { DPR, POSTFX, SHADOWS, qualityProfile } from "./quality";
import { Postfx } from "./Postfx";

/** Единственная точка входа в three: всё остальное приложение — про игру. */
export function Stage({ children }: { children: ReactNode }) {
  const profile = qualityProfile();
  return (
    <Canvas
      shadows={SHADOWS[profile]}
      dpr={DPR[profile]}
      camera={{ fov: 38, position: [0, 3.2, 12], near: 0.1, far: 120 }}
      gl={{ antialias: profile !== "low" }}
    >
      <Suspense fallback={null}>
        {children}
        {POSTFX[profile] ? <Postfx /> : null}
      </Suspense>
    </Canvas>
  );
}
