"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Group } from "three";

type Props = { highlighted: boolean; onClick: () => void };

const WINDOW_ROWS = [3.2, 5.4];
const WINDOW_COLS = [-2.4, -0.8, 0.8, 2.4];

/** Школа-замок Фоксинбурга: chibi-пропорции, башня с часами, тёплые окна. */
export function SchoolBuilding({ highlighted, onClick }: Props) {
  const group = useRef<Group>(null);

  useFrame((state) => {
    if (!group.current || !highlighted) return;
    const pulse = 1 + Math.sin(state.clock.elapsedTime * 2) * 0.012;
    group.current.scale.setScalar(pulse);
  });

  return (
    <group
      ref={group}
      position={[0, 0, -9]}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      onPointerOver={() => (document.body.style.cursor = "pointer")}
      onPointerOut={() => (document.body.style.cursor = "auto")}
    >
      {/* корпус */}
      <mesh position={[0, 3.5, 0]} castShadow receiveShadow>
        <boxGeometry args={[11, 7, 7]} />
        <meshStandardMaterial color="#3a2953" roughness={0.65} />
      </mesh>
      {/* крыша */}
      <mesh position={[0, 8, 0]} castShadow>
        <coneGeometry args={[8.4, 3.4, 4]} />
        <meshStandardMaterial color="#241a30" roughness={0.8} />
      </mesh>
      {/* башня с часами */}
      <mesh position={[4.6, 7, 0]} castShadow>
        <cylinderGeometry args={[1.5, 1.7, 12, 16]} />
        <meshStandardMaterial color="#45305f" roughness={0.6} />
      </mesh>
      <mesh position={[4.6, 13.6, 0]} castShadow>
        <coneGeometry args={[2.1, 2.8, 16]} />
        <meshStandardMaterial color="#241a30" roughness={0.8} />
      </mesh>
      <mesh position={[4.6, 10.4, 1.55]}>
        <circleGeometry args={[1, 32]} />
        <meshStandardMaterial
          color="#f5ed75"
          emissive="#f5ed75"
          emissiveIntensity={highlighted ? 1.4 : 0.7}
        />
      </mesh>
      {/* дверь 2.2 u */}
      <mesh position={[0, 1.1, 3.55]}>
        <boxGeometry args={[2.4, 2.2, 0.2]} />
        <meshStandardMaterial
          color="#c96f4a"
          emissive="#f5ed75"
          emissiveIntensity={highlighted ? 0.5 : 0.15}
        />
      </mesh>
      {/* тёплые окна */}
      {WINDOW_ROWS.map((y) =>
        WINDOW_COLS.map((x) => (
          <mesh key={`${x}-${y}`} position={[x, y, 3.55]}>
            <boxGeometry args={[1.1, 1.4, 0.15]} />
            <meshStandardMaterial
              color="#f5ed75"
              emissive="#f5ed75"
              emissiveIntensity={0.9}
            />
          </mesh>
        )),
      )}
    </group>
  );
}
