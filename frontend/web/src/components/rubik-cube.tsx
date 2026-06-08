"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export function RubikCube() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const trackedMaterials: THREE.Material[] = [];
    const neonMaterials: THREE.MeshPhysicalMaterial[] = [];
    const trackedGeometries: THREE.BufferGeometry[] = [];

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.95;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x060914, 9, 24);

    const camera = new THREE.PerspectiveCamera(34, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
    camera.position.set(6.35, 4.35, 7.95);
    camera.lookAt(0.55, 0.02, 0);

    const root = new THREE.Group();
    root.position.set(0.82, 0.02, 0);
    scene.add(root);

    const pivot = new THREE.Group();
    root.add(pivot);

    const cubeShell = new THREE.Group();
    cubeShell.rotation.z = -0.18;
    cubeShell.rotation.x = 0.12;
    pivot.add(cubeShell);

    const faceColors = [0x7c8cff, 0x8b5cf6, 0x0f172a, 0x111827, 0x22d3ee, 0xf472b6];

    const registerGeometry = <T extends THREE.BufferGeometry>(geometry: T) => {
      trackedGeometries.push(geometry);
      return geometry;
    };

    const registerMaterial = <T extends THREE.Material>(material: T) => {
      trackedMaterials.push(material);
      return material;
    };

    const makeMaterial = (color: number, isOuter: boolean) => {
      const material = isOuter
        ? new THREE.MeshPhysicalMaterial({
            color,
            roughness: 0.22,
            metalness: 0.96,
            clearcoat: 1,
            clearcoatRoughness: 0.08,
            reflectivity: 1,
            emissive: new THREE.Color(color).multiplyScalar(0.08),
          })
        : new THREE.MeshPhysicalMaterial({
            color: 0x050816,
            roughness: 0.18,
            metalness: 1,
            clearcoat: 0.6,
            clearcoatRoughness: 0.15,
          });

      registerMaterial(material);
      if (isOuter) {
        neonMaterials.push(material);
      }
      return material;
    };

    const aura = new THREE.Mesh(
      registerGeometry(new THREE.SphereGeometry(1.15, 48, 48)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0x7c3aed, transparent: true, opacity: 0.09 })),
    );
    aura.scale.set(3.9, 3.1, 2.8);
    aura.position.set(0.2, 0.1, -0.8);
    scene.add(aura);

    const auraTwo = new THREE.Mesh(
      registerGeometry(new THREE.SphereGeometry(1.15, 48, 48)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.07 })),
    );
    auraTwo.scale.set(3.2, 2.5, 2.4);
    auraTwo.position.set(-0.6, -0.2, -1.4);
    scene.add(auraTwo);

    const sparkle = new THREE.Mesh(
      registerGeometry(new THREE.SphereGeometry(0.14, 18, 18)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0xe9d5ff, transparent: true, opacity: 0.12 })),
    );
    sparkle.position.set(1.9, 1.15, 2.65);
    scene.add(sparkle);

    const sparkleTwo = new THREE.Mesh(
      registerGeometry(new THREE.SphereGeometry(0.11, 18, 18)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0xa5f3fc, transparent: true, opacity: 0.08 })),
    );
    sparkleTwo.position.set(-1.25, -0.95, 2.45);
    scene.add(sparkleTwo);

    const floorGlow = new THREE.Mesh(
      registerGeometry(new THREE.CircleGeometry(3.9, 72)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0x7c3aed, transparent: true, opacity: 0.08 })),
    );
    floorGlow.rotation.x = -Math.PI / 2;
    floorGlow.position.set(0.78, -2.45, 0.05);
    scene.add(floorGlow);

    const floorGlowTwo = new THREE.Mesh(
      registerGeometry(new THREE.CircleGeometry(4.8, 72)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.05 })),
    );
    floorGlowTwo.rotation.x = -Math.PI / 2;
    floorGlowTwo.position.set(0.78, -2.46, -0.12);
    scene.add(floorGlowTwo);

    const backgroundBeam = new THREE.Mesh(
      registerGeometry(new THREE.PlaneGeometry(8.6, 6.2)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0x1d4ed8, transparent: true, opacity: 0.045 })),
    );
    backgroundBeam.position.set(0.8, 0.45, -4.3);
    backgroundBeam.rotation.z = -0.1;
    scene.add(backgroundBeam);

    const backgroundBeamTwo = new THREE.Mesh(
      registerGeometry(new THREE.PlaneGeometry(7.4, 5.6)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0x7c3aed, transparent: true, opacity: 0.05 })),
    );
    backgroundBeamTwo.position.set(1.25, -0.2, -4);
    backgroundBeamTwo.rotation.z = 0.12;
    scene.add(backgroundBeamTwo);

    const crystalEdges = new THREE.LineSegments(
      registerGeometry(new THREE.EdgesGeometry(new THREE.OctahedronGeometry(2.95, 0))),
      registerMaterial(new THREE.LineBasicMaterial({ color: 0xc4b5fd, transparent: true, opacity: 0.18 })),
    );
    crystalEdges.position.set(0.65, 0.1, -0.35);
    crystalEdges.rotation.y = Math.PI / 6;
    crystalEdges.rotation.x = Math.PI / 7;
    scene.add(crystalEdges);

    const crystalEdgesTwo = new THREE.LineSegments(
      registerGeometry(new THREE.EdgesGeometry(new THREE.OctahedronGeometry(3.4, 0))),
      registerMaterial(new THREE.LineBasicMaterial({ color: 0x67e8f9, transparent: true, opacity: 0.12 })),
    );
    crystalEdgesTwo.position.set(0.72, 0.05, -0.7);
    crystalEdgesTwo.rotation.y = -Math.PI / 5;
    crystalEdgesTwo.rotation.x = Math.PI / 8;
    scene.add(crystalEdgesTwo);

    const flare = new THREE.Mesh(
      registerGeometry(new THREE.PlaneGeometry(0.7, 0.03)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0xede9fe, transparent: true, opacity: 0.08 })),
    );
    flare.position.set(1.65, 1.12, 2.55);
    flare.rotation.z = 0.55;
    scene.add(flare);

    const flareCross = new THREE.Mesh(
      registerGeometry(new THREE.PlaneGeometry(0.03, 0.68)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0xede9fe, transparent: true, opacity: 0.05 })),
    );
    flareCross.position.set(1.65, 1.12, 2.54);
    flareCross.rotation.z = 0.55;
    scene.add(flareCross);

    const flareTwo = new THREE.Mesh(
      registerGeometry(new THREE.PlaneGeometry(0.55, 0.024)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0xa5f3fc, transparent: true, opacity: 0.06 })),
    );
    flareTwo.position.set(-1.18, -0.92, 2.35);
    flareTwo.rotation.z = -0.62;
    scene.add(flareTwo);

    const flareCrossTwo = new THREE.Mesh(
      registerGeometry(new THREE.PlaneGeometry(0.026, 0.52)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0xa5f3fc, transparent: true, opacity: 0.04 })),
    );
    flareCrossTwo.position.set(-1.18, -0.92, 2.34);
    flareCrossTwo.rotation.z = -0.62;
    scene.add(flareCrossTwo);

    const orbitGroup = new THREE.Group();
    orbitGroup.position.set(0.72, 0.02, -0.38);
    scene.add(orbitGroup);

    const orbitPoints = Array.from({ length: 120 }, (_, index) => {
      const angle = (index / 120) * Math.PI * 2;
      return new THREE.Vector3(Math.cos(angle) * 3.65, Math.sin(angle) * 1.32, 0);
    });
    const orbit = new THREE.LineLoop(
      registerGeometry(new THREE.BufferGeometry().setFromPoints(orbitPoints)),
      registerMaterial(new THREE.LineBasicMaterial({ color: 0x7c3aed, transparent: true, opacity: 0.16 })),
    );
    orbitGroup.add(orbit);

    const orbitTwoPoints = Array.from({ length: 120 }, (_, index) => {
      const angle = (index / 120) * Math.PI * 2;
      return new THREE.Vector3(Math.cos(angle) * 4.15, Math.sin(angle) * 1.62, 0);
    });
    const orbitTwo = new THREE.LineLoop(
      registerGeometry(new THREE.BufferGeometry().setFromPoints(orbitTwoPoints)),
      registerMaterial(new THREE.LineBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.12 })),
    );
    orbitTwo.rotation.z = 0.22;
    orbitGroup.add(orbitTwo);

    const orbitDot = new THREE.Mesh(
      registerGeometry(new THREE.SphereGeometry(0.08, 12, 12)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0xddd6fe, transparent: true, opacity: 0.18 })),
    );
    orbitGroup.add(orbitDot);

    const orbitDotTwo = new THREE.Mesh(
      registerGeometry(new THREE.SphereGeometry(0.07, 12, 12)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0x67e8f9, transparent: true, opacity: 0.14 })),
    );
    orbitGroup.add(orbitDotTwo);

    const cubeGroup = new THREE.Group();
    cubeShell.add(cubeGroup);

    const gap = 0.06;
    const size = 1;

    for (let x = -1; x <= 1; x += 1) {
      for (let y = -1; y <= 1; y += 1) {
        for (let z = -1; z <= 1; z += 1) {
          const geometry = registerGeometry(new THREE.BoxGeometry(size - gap * 2, size - gap * 2, size - gap * 2));
          const outerFaces = [x === 1, x === -1, y === 1, y === -1, z === 1, z === -1];
          const materials = outerFaces.map((isOuter, index) => makeMaterial(faceColors[index], isOuter));
          const cubie = new THREE.Mesh(geometry, materials);
          cubie.position.set(x * size, y * size, z * size);
          cubeGroup.add(cubie);
        }
      }
    }

    const frame = new THREE.Mesh(
      registerGeometry(new THREE.BoxGeometry(3.45, 3.45, 3.45)),
      registerMaterial(
        new THREE.MeshPhysicalMaterial({
          color: 0x0a1020,
          transparent: true,
          opacity: 0.08,
          roughness: 0.08,
          metalness: 0.95,
          clearcoat: 1,
          clearcoatRoughness: 0.08,
          side: THREE.BackSide,
        }),
      ),
    );
    cubeShell.add(frame);

    const edges = new THREE.LineSegments(
      registerGeometry(new THREE.EdgesGeometry(new THREE.BoxGeometry(3.22, 3.22, 3.22))),
      registerMaterial(new THREE.LineBasicMaterial({ color: 0x7dd3fc, transparent: true, opacity: 0.14 })),
    );
    cubeShell.add(edges);

    const ringMaterial = registerMaterial(new THREE.MeshBasicMaterial({ color: 0x7c3aed, transparent: true, opacity: 0.16 }));
    const ring = new THREE.Mesh(registerGeometry(new THREE.TorusGeometry(3.2, 0.045, 20, 160)), ringMaterial);
    ring.rotation.x = Math.PI / 2.8;
    ring.position.set(0.1, -0.2, -0.3);
    scene.add(ring);

    const ringTwoMaterial = registerMaterial(new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.1 }));
    const ringTwo = new THREE.Mesh(registerGeometry(new THREE.TorusGeometry(3.9, 0.035, 20, 160)), ringTwoMaterial);
    ringTwo.rotation.x = Math.PI / 2.35;
    ringTwo.rotation.y = Math.PI / 7;
    ringTwo.position.set(0.2, -0.1, -0.75);
    scene.add(ringTwo);

    const shadow = new THREE.Mesh(
      registerGeometry(new THREE.CircleGeometry(2.8, 48)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0x04060d, transparent: true, opacity: 0.18 })),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.set(0.7, -2.35, 0);
    scene.add(shadow);

    const backgroundGlow = new THREE.Mesh(
      registerGeometry(new THREE.SphereGeometry(7.5, 48, 48)),
      registerMaterial(new THREE.MeshBasicMaterial({ color: 0x0b1020, transparent: true, opacity: 0.05 })),
    );
    backgroundGlow.position.set(0.4, 0.2, -4.6);
    scene.add(backgroundGlow);

    scene.add(new THREE.AmbientLight(0xffffff, 0.24));

    const key = new THREE.DirectionalLight(0xe5e7eb, 1.55);
    key.position.set(6, 9, 7);
    scene.add(key);

    const fill = new THREE.DirectionalLight(0x8b5cf6, 0.82);
    fill.position.set(-4, 1.5, -2);
    scene.add(fill);

    const rim = new THREE.DirectionalLight(0x38bdf8, 0.68);
    rim.position.set(1, -4, -5);
    scene.add(rim);

    const halo = new THREE.PointLight(0x8b5cf6, 2.9, 18, 2);
    halo.position.set(2.35, 1.8, 4.5);
    scene.add(halo);

    const cyanGlow = new THREE.PointLight(0x22d3ee, 2.1, 16, 2);
    cyanGlow.position.set(-2.4, -1.2, 3.2);
    scene.add(cyanGlow);

    const pinkGlow = new THREE.PointLight(0xf472b6, 1.4, 14, 2);
    pinkGlow.position.set(0.5, 3.8, 2.4);
    scene.add(pinkGlow);

    const resize = () => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    window.addEventListener("resize", resize);

    let frameId = 0;
    let t = 0;

    const animate = () => {
      frameId = window.requestAnimationFrame(animate);
      t += 0.006;

      const pulse = (Math.sin(t * 1.08) + 1) / 2;
      pivot.rotation.y = t * 0.64;
      pivot.rotation.x = Math.sin(t * 0.28) * 0.22 + 0.16;
      pivot.rotation.z = Math.sin(t * 0.18) * 0.05;

      ring.rotation.z += 0.0012;
      ringTwo.rotation.z -= 0.001;
      crystalEdges.rotation.y += 0.001;
      crystalEdgesTwo.rotation.y -= 0.0008;
      orbitGroup.rotation.z += 0.0011;

      const orbitAngle = t * 1.05;
      orbitDot.position.set(Math.cos(orbitAngle) * 3.65, Math.sin(orbitAngle) * 1.32, 0);
      orbitDotTwo.position.set(Math.cos(-orbitAngle * 0.9) * 4.15, Math.sin(-orbitAngle * 0.9) * 1.62, 0);

      halo.intensity = 2.18 + pulse * 0.46;
      cyanGlow.intensity = 1.62 + pulse * 0.4;
      pinkGlow.intensity = 1.02 + pulse * 0.22;
      ringMaterial.opacity = 0.11 + pulse * 0.04;
      ringTwoMaterial.opacity = 0.065 + pulse * 0.035;
      (aura.material as THREE.MeshBasicMaterial).opacity = 0.07 + pulse * 0.03;
      (auraTwo.material as THREE.MeshBasicMaterial).opacity = 0.05 + pulse * 0.022;
      (backgroundBeam.material as THREE.MeshBasicMaterial).opacity = 0.028 + pulse * 0.014;
      (backgroundBeamTwo.material as THREE.MeshBasicMaterial).opacity = 0.034 + pulse * 0.014;
      (floorGlow.material as THREE.MeshBasicMaterial).opacity = 0.05 + pulse * 0.022;
      (floorGlowTwo.material as THREE.MeshBasicMaterial).opacity = 0.032 + pulse * 0.016;
      sparkle.scale.setScalar(0.95 + pulse * 0.16);
      sparkleTwo.scale.setScalar(0.94 + pulse * 0.14);

      neonMaterials.forEach((material, index) => {
        material.emissive.copy(new THREE.Color(faceColors[index % faceColors.length])).multiplyScalar(0.07 + pulse * 0.05);
      });

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
      renderer.dispose();
      trackedGeometries.forEach((geometry) => geometry.dispose());
      trackedMaterials.forEach((material) => material.dispose());
    };
  }, []);

  return <canvas ref={canvasRef} className="block h-full w-full" />;
}
