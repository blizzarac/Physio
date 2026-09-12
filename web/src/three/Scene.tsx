import { useEffect, useMemo } from "react";
import { useThree } from "@react-three/fiber";
import { ContactShadows } from "@react-three/drei";
import { EffectComposer, N8AO, SMAA } from "@react-three/postprocessing";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

// Image-based lighting from three's procedural RoomEnvironment: gives PBR materials
// reflections and soft ambient light without fetching an HDR at runtime (offline requirement).
function Environment({ intensity = 0.55 }: { intensity?: number }) {
  const { gl, scene } = useThree();
  const texture = useMemo(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const tex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    return tex;
  }, [gl]);
  useEffect(() => {
    scene.environment = texture;
    scene.environmentIntensity = intensity;
    return () => {
      scene.environment = null;
    };
  }, [scene, texture, intensity]);
  return null;
}

export interface SceneBounds {
  center: THREE.Vector3;
  radius: number;
  minY: number;
}

interface Props {
  bounds: SceneBounds;
  effects: boolean;
}

// Three-point studio lighting scaled to the model's bounds, plus a shadow-casting key light,
// contact shadow on the floor, ambient occlusion and anti-aliasing.
export function SceneSetup({ bounds, effects }: Props) {
  const r = Math.max(bounds.radius, 0.3);
  const c = bounds.center;
  return (
    <>
      <Environment />
      <directionalLight
        position={[c.x + r * 1.6, c.y + r * 2.2, c.z + r * 1.8]}
        intensity={2.6}
        color="#fff4e6"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0004}
        shadow-normalBias={0.02}
        shadow-camera-near={0.01}
        shadow-camera-far={r * 8}
        shadow-camera-left={-r * 1.5}
        shadow-camera-right={r * 1.5}
        shadow-camera-top={r * 1.5}
        shadow-camera-bottom={-r * 1.5}
        target-position={[c.x, c.y, c.z]}
      />
      <directionalLight position={[c.x - r * 2, c.y + r * 0.6, c.z + r * 1.2]} intensity={0.9} color="#dfe8ff" />
      <directionalLight position={[c.x + r * 0.5, c.y + r * 0.8, c.z - r * 2.5]} intensity={1.4} color="#ffe9d6" />
      <ContactShadows
        position={[c.x, bounds.minY - 0.005, c.z]}
        scale={r * 4}
        blur={2.2}
        opacity={0.55}
        far={r * 2}
        resolution={1024}
        frames={1}
      />
      {effects && (
        <EffectComposer multisampling={0} enableNormalPass={false}>
          <N8AO aoRadius={r * 0.12} intensity={2.4} distanceFalloff={r * 0.5} quality="medium" halfRes />
          <SMAA />
        </EffectComposer>
      )}
    </>
  );
}
