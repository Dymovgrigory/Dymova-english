"use client";

/** Тёплое солнце + холодный ambient + туман глубины (world-art-bible §6). */
export function Lighting() {
  return (
    <>
      <color attach="background" args={["#241a30"]} />
      <fog attach="fog" args={["#241a30", 18, 46]} />
      <hemisphereLight args={["#f5ed75", "#3a2953", 0.55]} />
      <directionalLight
        position={[6, 9, 4]}
        intensity={2.1}
        color="#ffe9b8"
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-18}
        shadow-camera-right={18}
        shadow-camera-top={18}
        shadow-camera-bottom={-18}
      />
      <ambientLight intensity={0.35} color="#6b4f9a" />
    </>
  );
}
