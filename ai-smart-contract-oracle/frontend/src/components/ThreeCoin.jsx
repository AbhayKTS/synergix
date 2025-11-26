import { Suspense, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useLoader } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

function CoinMesh({ tilt }) {
  const meshRef = useRef();
  const faceTexture = useLoader(THREE.TextureLoader, '/images/samurai-coin.jpg');
  faceTexture.colorSpace = THREE.SRGBColorSpace;
  faceTexture.anisotropy = 8;
  faceTexture.needsUpdate = true;

  const edgeMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#2a0b2f',
        metalness: 0.75,
        roughness: 0.3,
        emissive: '#1a0922',
        emissiveIntensity: 0.35
      }),
    []
  );

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const time = clock.getElapsedTime();
    meshRef.current.rotation.y = time * 0.4 + tilt.y;
    meshRef.current.rotation.x = THREE.MathUtils.lerp(meshRef.current.rotation.x, Math.PI / 2, 0.1);
    meshRef.current.rotation.z = THREE.MathUtils.lerp(meshRef.current.rotation.z, 0, 0.1);
    meshRef.current.position.y = Math.sin(time * 0.8) * 0.02;
  });

  return (
    <mesh ref={meshRef} castShadow receiveShadow>
      <cylinderGeometry args={[1.45, 1.45, 0.12, 96]} />
      <primitive attach="material-0" object={edgeMaterial} />
      <meshBasicMaterial attach="material-1" map={faceTexture} toneMapped={false} />
      <meshBasicMaterial attach="material-2" map={faceTexture} toneMapped={false} side={THREE.BackSide} />
    </mesh>
  );
}

export default function ThreeCoin() {
  const [tilt, setTilt] = useState({ y: 0 });

  const handlePointerMove = (event) => {
    const { left, width } = event.currentTarget.getBoundingClientRect();
    const horizontal = ((event.clientX - left) / width - 0.5) * 0.6;
    setTilt({ y: horizontal });
  };

  return (
    <div
      className="relative h-full w-full"
      onPointerMove={handlePointerMove}
    >
      <Canvas camera={{ position: [0, 0, 5], fov: 45 }} dpr={[1, 1.5]}>
        <color attach="background" args={[0, 0, 0, 0]} />
        <group>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.07, 0]}>
            <cylinderGeometry args={[1.6, 1.6, 0.02, 64, 1, true]} />
            <meshBasicMaterial
              side={THREE.DoubleSide}
              color="#EA2E49"
              transparent
              opacity={0.18}
            />
          </mesh>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.075, 0]}>
            <cylinderGeometry args={[1.4, 1.4, 0.01, 64]} />
            <meshBasicMaterial
              color="#7034FF"
              transparent
              opacity={0.15}
            />
          </mesh>
        </group>
        <ambientLight intensity={0.9} />
        <directionalLight position={[4, 6, 6]} intensity={1.2} color="#EA2E49" />
        <spotLight position={[-5, 3, 6]} angle={0.35} intensity={0.5} color="#7034ff" />
        <Suspense fallback={null}>
          <CoinMesh tilt={tilt} />
        </Suspense>
        <OrbitControls enableZoom={false} enablePan={false} enableRotate={false} />
      </Canvas>
    </div>
  );
}
