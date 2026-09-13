"use client";

/** Двор школы: мягкий круг мощения на тёмной траве. */
export function Ground() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[26, 64]} />
        <meshStandardMaterial color="#2c2140" roughness={0.9} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow>
        <circleGeometry args={[9, 64]} />
        <meshStandardMaterial color="#3a2953" roughness={0.7} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <ringGeometry args={[8.6, 9, 64]} />
        <meshStandardMaterial color="#f5ed75" emissive="#f5ed75" emissiveIntensity={0.35} />
      </mesh>
    </group>
  );
}
