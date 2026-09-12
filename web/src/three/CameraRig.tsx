import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";
import type { BBox } from "../api";
import { useStore, type ViewPreset } from "../store";

// Camera directions for the standard views. The pipeline converts BodyParts3D to Y-up with the
// anterior surface facing +Z, so the anterior view looks down -Z from +Z.
const PRESET_DIR: Record<ViewPreset, THREE.Vector3> = {
  anterior: new THREE.Vector3(0, 0, 1),
  posterior: new THREE.Vector3(0, 0, -1),
  left: new THREE.Vector3(1, 0, 0),
  right: new THREE.Vector3(-1, 0, 0),
  superior: new THREE.Vector3(0.001, 1, 0.001).normalize(),
};

function boxOf(b: BBox): THREE.Box3 {
  return new THREE.Box3(new THREE.Vector3(...b.min), new THREE.Vector3(...b.max));
}

/** Distance at which a sphere of `radius` fills ~85% of the shorter viewport dimension. */
function fitDistance(camera: THREE.PerspectiveCamera, radius: number): number {
  const vFov = THREE.MathUtils.degToRad(camera.fov);
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect);
  const fov = Math.min(vFov, hFov);
  return (radius / Math.sin(fov / 2)) * 1.15;
}

interface Props {
  controls: React.RefObject<OrbitControlsImpl>;
  sceneBox: BBox | null; // full-body extent for "reset"
}

interface Move {
  t0: number;
  duration: number;
  target0: THREE.Vector3;
  target1: THREE.Vector3;
  dir0: THREE.Vector3;
  rot: THREE.Quaternion; // rotation taking dir0 to dir1
  dist0: number;
  dist1: number;
}

const ease = (k: number) => (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);

// Consumes store.cameraRequest: computes a goal target + position and moves the camera there
// over a fixed time (so it finishes regardless of frame rate), swinging the view direction
// along an arc so a front-to-back turn orbits around the model instead of passing through it.
// Frame requests keep the current viewing direction so the model does not spin unexpectedly;
// preset requests rotate around the current target at the current distance.
export function CameraRig({ controls, sceneBox }: Props) {
  const request = useStore((s) => s.cameraRequest);
  const requestCamera = useStore((s) => s.requestCamera);
  const { camera } = useThree();
  const move = useRef<Move | null>(null);

  const start = (target1: THREE.Vector3, dir1: THREE.Vector3, dist1: number) => {
    const c = controls.current!;
    const dir0 = new THREE.Vector3().subVectors(camera.position, c.target);
    const dist0 = Math.max(dir0.length(), 1e-4);
    dir0.normalize();
    move.current = {
      t0: performance.now(),
      duration: 650,
      target0: c.target.clone(),
      target1,
      dir0,
      rot: new THREE.Quaternion().setFromUnitVectors(dir0, dir1.clone().normalize()),
      dist0,
      dist1,
    };
  };

  useEffect(() => {
    const c = controls.current;
    if (!request || !c) return;
    const cam = camera as THREE.PerspectiveCamera;
    const dir = new THREE.Vector3().subVectors(cam.position, c.target).normalize();
    if (request.kind === "preset") {
      start(c.target.clone(), PRESET_DIR[request.view], cam.position.distanceTo(c.target));
      return;
    }
    const b = request.kind === "reset" ? sceneBox : request.box;
    if (!b) {
      requestCamera(null);
      return;
    }
    const sphere = boxOf(b).getBoundingSphere(new THREE.Sphere());
    const radius = Math.max(sphere.radius, 0.02);
    const viewDir = request.kind === "reset" ? PRESET_DIR.anterior : request.preset ? PRESET_DIR[request.preset] : dir;
    start(sphere.center.clone(), viewDir, fitDistance(cam, radius));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, camera, controls, sceneBox, requestCamera]);

  useFrame(() => {
    const c = controls.current;
    const m = move.current;
    if (!m || !c) return;
    const k = ease(Math.min(1, (performance.now() - m.t0) / m.duration));
    const dir = m.dir0.clone().applyQuaternion(new THREE.Quaternion().slerp(m.rot, k));
    const dist = THREE.MathUtils.lerp(m.dist0, m.dist1, k);
    c.target.lerpVectors(m.target0, m.target1, k);
    camera.position.copy(c.target).addScaledVector(dir, dist);
    c.update();
    if (k >= 1) {
      move.current = null;
      requestCamera(null);
    }
  });
  return null;
}
