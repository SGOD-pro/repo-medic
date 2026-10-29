"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";
import { Play, Pause } from "lucide-react";

export type RepairStage = 1 | 2 | 3 | 4;

interface StageInfo {
  id: RepairStage;
  label: string;
  title: string;
  description: string;
  badge: string;
  badgeColor: string;
}

const STAGES: StageInfo[] = [
  {
    id: 1,
    label: "1. Baseline",
    title: "Baseline tests pass",
    description: "Runs existing test suite against pinned commit to verify baseline green status before upgrade.",
    badge: "BASELINE VERIFIED",
    badgeColor: "text-[#5FCB8A] bg-[#5FCB8A]/15 border-[#5FCB8A]/30",
  },
  {
    id: 2,
    label: "2. Upgrade",
    title: "Upgrade reproduces a failure",
    description: "Upgrades target package in isolated container; captures exact breaking failure and traceback.",
    badge: "UPGRADE FAILURE REPRODUCED",
    badgeColor: "text-[#E5736A] bg-[#E5736A]/15 border-[#E5736A]/30",
  },
  {
    id: 3,
    label: "3. Candidate",
    title: "A candidate patch is proposed",
    description: "Model analyzes failure and AST rules to synthesize candidate patch constrained to allowed source paths.",
    badge: "CANDIDATE PROPOSED",
    badgeColor: "text-[#E0B45A] bg-[#E0B45A]/15 border-[#E0B45A]/30",
  },
  {
    id: 4,
    label: "4. Verify",
    title: "Tests are checked; evidence is available in a successful run",
    description: "Candidate patch verified in clean sandbox against test suite; cryptographic hash and logs emitted.",
    badge: "EVIDENCE VERIFIED",
    badgeColor: "text-[#5FCB8A] bg-[#5FCB8A]/15 border-[#5FCB8A]/30",
  },
];

interface ModuleCoord {
  x: number;
  y: number;
  z: number;
  name: string;
  status: string;
}

const MODULES: ModuleCoord[] = [
  { x: -130, y: -50, z: 12, name: "Baseline", status: "PASS" },
  { x: -45, y: 35, z: 12, name: "Upgrade", status: "FAIL" },
  { x: 45, y: -35, z: 12, name: "Patch", status: "PATCH" },
  { x: 130, y: 50, z: 12, name: "Verify", status: "VERIFIED" },
];

export function RepairBenchScene() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [currentStage, setCurrentStage] = useState<RepairStage>(1);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(() => {
    if (typeof window !== "undefined" && window.matchMedia) {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }
    return false;
  });
  const [isPlaying, setIsPlaying] = useState<boolean>(() => {
    if (typeof window !== "undefined" && window.matchMedia) {
      return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }
    return true;
  });
  const [isSupported, setIsSupported] = useState<boolean>(true);
  const [isOffscreen, setIsOffscreen] = useState<boolean>(false);

  // Parallax angles
  const mouseRef = useRef<{ targetX: number; targetY: number; currentX: number; currentY: number }>({
    targetX: 0,
    targetY: 0,
    currentX: 0,
    currentY: 0,
  });

  // Animation timeline tracking
  const animRef = useRef<{
    rafId: number | null;
    stageStartTime: number;
    lastTime: number;
    pulsePos: number; // 0 to 1 along current active wire
  }>({
    rafId: null,
    stageStartTime: 0,
    lastTime: 0,
    pulsePos: 0,
  });

  // Detect prefers-reduced-motion changes
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) {
      queueMicrotask(() => {
        setPrefersReducedMotion(true);
        setIsPlaying(false);
      });
    }

    const handler = (e: MediaQueryListEvent) => {
      setPrefersReducedMotion(e.matches);
      if (e.matches) {
        setIsPlaying(false);
      }
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // IntersectionObserver to pause when offscreen
  useEffect(() => {
    if (!containerRef.current || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsOffscreen(!entry.isIntersecting);
      },
      { threshold: 0.1 }
    );

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Mouse parallax handler
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1; // -1 to 1
    const ny = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    // Cap rotation to max ~3.5 degrees (0.06 rad)
    mouseRef.current.targetX = nx * 0.06;
    mouseRef.current.targetY = ny * 0.06;
  }, []);

  const handleMouseLeave = useCallback(() => {
    mouseRef.current.targetX = 0;
    mouseRef.current.targetY = 0;
  }, []);

  // Manual stage selection
  const selectStage = useCallback((stage: RepairStage) => {
    setCurrentStage(stage);
    animRef.current.stageStartTime = performance.now();
    animRef.current.pulsePos = 0;
  }, []);

  // Cycle duration per stage in ms: ~3200ms per stage (total cycle ~13s)
  const STAGE_DURATION = 3200;

  // Main Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      setIsSupported(false);
      return;
    }

    let animationFrameId: number;

    const render = (time: number) => {
      if (!animRef.current.stageStartTime) {
        animRef.current.stageStartTime = time;
        animRef.current.lastTime = time;
      }

      // Smooth parallax damping
      const mouse = mouseRef.current;
      mouse.currentX += (mouse.targetX - mouse.currentX) * 0.08;
      mouse.currentY += (mouse.targetY - mouse.currentY) * 0.08;

      // Handle stage progression if playing and not reduced motion
      if (isPlaying && !prefersReducedMotion && !isOffscreen) {
        const elapsedInStage = time - animRef.current.stageStartTime;
        animRef.current.pulsePos = Math.min(1, elapsedInStage / STAGE_DURATION);

        if (elapsedInStage >= STAGE_DURATION) {
          animRef.current.stageStartTime = time;
          animRef.current.pulsePos = 0;
          setCurrentStage((prev) => (prev === 4 ? 1 : ((prev + 1) as RepairStage)));
        }
      }

      // Handle canvas resolution / HiDPI
      const dpr = Math.min(2, typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1);
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;

      if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
        canvas.width = width * dpr;
        canvas.height = height * dpr;
      }

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2 + 15;

      // 2.5D Isometric projection helper
      // rotY: yaw, rotX: pitch adjustment
      const rotY = mouse.currentX;
      const rotX = mouse.currentY;

      const cos30 = 0.8660254; // cos(30 deg)
      const sin30 = 0.5; // sin(30 deg)

      const toIso = (x: number, y: number, z: number) => {
        // Apply slight rotation around Z
        const cosR = Math.cos(rotY);
        const sinR = Math.sin(rotY);
        const rx = x * cosR - y * sinR;
        const ry = x * sinR + y * cosR;

        const isoX = (rx - ry) * cos30;
        const isoY = (rx + ry) * sin30 - z + rotX * rx;
        return { px: cx + isoX, py: cy + isoY };
      };

      // -----------------------------------------------------------------------
      // 1. DRAW SUBTLE ISOMETRIC BENCH PERSPECTIVE GRID
      // -----------------------------------------------------------------------
      const gridSize = 190;
      const step = 38;

      ctx.lineWidth = 1;

      // Outer bench ground plane
      const p1 = toIso(-gridSize, -gridSize, 0);
      const p2 = toIso(gridSize, -gridSize, 0);
      const p3 = toIso(gridSize, gridSize, 0);
      const p4 = toIso(-gridSize, gridSize, 0);

      // Soft gradient fill under grid
      const groundGrad = ctx.createLinearGradient(p1.px, p1.py, p3.px, p3.py);
      groundGrad.addColorStop(0, "rgba(21, 39, 31, 0.45)");
      groundGrad.addColorStop(0.5, "rgba(27, 50, 40, 0.35)");
      groundGrad.addColorStop(1, "rgba(13, 25, 21, 0.5)");

      ctx.beginPath();
      ctx.moveTo(p1.px, p1.py);
      ctx.lineTo(p2.px, p2.py);
      ctx.lineTo(p3.px, p3.py);
      ctx.lineTo(p4.px, p4.py);
      ctx.closePath();
      ctx.fillStyle = groundGrad;
      ctx.fill();

      // Bench border
      ctx.strokeStyle = "rgba(183, 201, 173, 0.14)";
      ctx.stroke();

      // Grid Lines
      ctx.strokeStyle = "rgba(183, 201, 173, 0.08)";
      for (let i = -gridSize; i <= gridSize; i += step) {
        // Line parallel to Y
        const startY = toIso(i, -gridSize, 0);
        const endY = toIso(i, gridSize, 0);
        ctx.beginPath();
        ctx.moveTo(startY.px, startY.py);
        ctx.lineTo(endY.px, endY.py);
        ctx.stroke();

        // Line parallel to X
        const startX = toIso(-gridSize, i, 0);
        const endX = toIso(gridSize, i, 0);
        ctx.beginPath();
        ctx.moveTo(startX.px, startX.py);
        ctx.lineTo(endX.px, endX.py);
        ctx.stroke();
      }

      // Coordinate dots at intersections
      ctx.fillStyle = "rgba(183, 201, 173, 0.16)";
      for (let gx = -gridSize + step; gx < gridSize; gx += step * 2) {
        for (let gy = -gridSize + step; gy < gridSize; gy += step * 2) {
          const pt = toIso(gx, gy, 0);
          ctx.beginPath();
          ctx.arc(pt.px, pt.py, 1.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // -----------------------------------------------------------------------
      // 2. CONNECTING TRACE PATHS BETWEEN MODULES
      // -----------------------------------------------------------------------
      // Module indices: 0 -> 1 -> 2 -> 3
      const wireElevation = 6;
      const modPoints = MODULES.map((m) => toIso(m.x, m.y, wireElevation));

      for (let i = 0; i < MODULES.length - 1; i++) {
        const start = modPoints[i];
        const end = modPoints[i + 1];

        const isPast = currentStage > i + 1;
        const isCurrent = currentStage === i + 1;

        // Base wire line
        ctx.beginPath();
        ctx.moveTo(start.px, start.py);
        ctx.lineTo(end.px, end.py);

        if (isPast) {
          ctx.strokeStyle = "rgba(95, 203, 138, 0.4)";
          ctx.lineWidth = 2;
        } else if (isCurrent) {
          // If stage 2 (Upgrade -> red failure), wire color turns warning red
          if (currentStage === 2) {
            ctx.strokeStyle = "rgba(229, 115, 106, 0.5)";
          } else {
            ctx.strokeStyle = "rgba(183, 201, 173, 0.45)";
          }
          ctx.lineWidth = 2;
        } else {
          ctx.strokeStyle = "rgba(183, 201, 173, 0.15)";
          ctx.lineWidth = 1.2;
        }
        ctx.stroke();

        // Traveling pulse packet along current active segment
        if (isCurrent && !prefersReducedMotion) {
          const pulseT = animRef.current.pulsePos;
          const pulseX = start.px + (end.px - start.px) * pulseT;
          const pulseY = start.py + (end.py - start.py) * pulseT;

          // Glowing pulse dot
          ctx.beginPath();
          ctx.arc(pulseX, pulseY, 3.5, 0, Math.PI * 2);
          if (currentStage === 2) {
            ctx.fillStyle = "#E5736A";
            ctx.shadowColor = "#E5736A";
            ctx.shadowBlur = 8;
          } else if (currentStage === 3) {
            ctx.fillStyle = "#B7C9AD";
            ctx.shadowColor = "#B7C9AD";
            ctx.shadowBlur = 8;
          } else {
            ctx.fillStyle = "#5FCB8A";
            ctx.shadowColor = "#5FCB8A";
            ctx.shadowBlur = 8;
          }
          ctx.fill();
          ctx.shadowBlur = 0; // reset
        }
      }

      // -----------------------------------------------------------------------
      // 3. DRAW 3D ISOMETRIC MODULES (LOW-POLY PRISMS)
      // -----------------------------------------------------------------------
      // Render order from back to front in isometric view:
      // In this setup, Baseline (-130, -50), Patch (45, -35), Upgrade (-45, 35), Verify (130, 50)
      const sortedModules = [...MODULES].map((m, idx) => ({ ...m, origIndex: idx }));
      sortedModules.sort((a, b) => a.x + a.y - (b.x + b.y));

      sortedModules.forEach((m) => {
        const modIndex = m.origIndex + 1; // 1, 2, 3, 4
        const isCurrent = currentStage === modIndex;
        const isCompleted = currentStage > modIndex;

        const hw = 30; // half-width
        const hd = 22; // half-depth
        const h = 18; // height

        // Floating lift for active stage
        const liftZ = isCurrent ? 6 : 0;
        const baseZ = m.z + liftZ;

        // Shadow under floating module
        if (isCurrent) {
          const s1 = toIso(m.x - hw * 0.9, m.y - hd * 0.9, 0);
          const s2 = toIso(m.x + hw * 0.9, m.y - hd * 0.9, 0);
          const s3 = toIso(m.x + hw * 0.9, m.y + hd * 0.9, 0);
          const s4 = toIso(m.x - hw * 0.9, m.y + hd * 0.9, 0);
          ctx.beginPath();
          ctx.moveTo(s1.px, s1.py);
          ctx.lineTo(s2.px, s2.py);
          ctx.lineTo(s3.px, s3.py);
          ctx.lineTo(s4.px, s4.py);
          ctx.closePath();
          ctx.fillStyle = "rgba(10, 20, 16, 0.4)";
          ctx.fill();
        }

        // Visible bottom vertices
        const b1 = toIso(m.x + hw, m.y - hd, baseZ - h);
        const b2 = toIso(m.x + hw, m.y + hd, baseZ - h);
        const b3 = toIso(m.x - hw, m.y + hd, baseZ - h);
        // Top 4
        const t0 = toIso(m.x - hw, m.y - hd, baseZ);
        const t1 = toIso(m.x + hw, m.y - hd, baseZ);
        const t2 = toIso(m.x + hw, m.y + hd, baseZ);
        const t3 = toIso(m.x - hw, m.y + hd, baseZ);

        // Colors per face
        let topColor = "#1B3228";
        let leftColor = "#15271F";
        let rightColor = "#112019";
        let strokeColor = "rgba(183, 201, 173, 0.22)";

        if (isCurrent) {
          if (modIndex === 2) {
            // Upgrade Failure (Red accent)
            topColor = "#2E1B1B";
            leftColor = "#241515";
            rightColor = "#1C1010";
            strokeColor = "rgba(229, 115, 106, 0.85)";
          } else if (modIndex === 3) {
            // Patch Candidate
            topColor = "#2A3626";
            leftColor = "#202B1E";
            rightColor = "#192217";
            strokeColor = "rgba(183, 201, 173, 0.7)";
          } else if (modIndex === 4) {
            // Verify (Green accent)
            topColor = "#1A3528";
            leftColor = "#142A20";
            rightColor = "#0E1F17";
            strokeColor = "rgba(95, 203, 138, 0.9)";
          } else {
            // Baseline
            topColor = "#223C2F";
            leftColor = "#192E24";
            rightColor = "#13241C";
            strokeColor = "rgba(95, 203, 138, 0.7)";
          }
        } else if (isCompleted) {
          if (modIndex === 2) {
            strokeColor = "rgba(229, 115, 106, 0.4)";
          } else {
            strokeColor = "rgba(95, 203, 138, 0.4)";
          }
        }

        // Draw Left Face (t3, t2, b2, b3)
        ctx.beginPath();
        ctx.moveTo(t3.px, t3.py);
        ctx.lineTo(t2.px, t2.py);
        ctx.lineTo(b2.px, b2.py);
        ctx.lineTo(b3.px, b3.py);
        ctx.closePath();
        ctx.fillStyle = leftColor;
        ctx.fill();
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = 1;
        ctx.stroke();

        // Draw Right Face (t1, t2, b2, b1)
        ctx.beginPath();
        ctx.moveTo(t1.px, t1.py);
        ctx.lineTo(t2.px, t2.py);
        ctx.lineTo(b2.px, b2.py);
        ctx.lineTo(b1.px, b1.py);
        ctx.closePath();
        ctx.fillStyle = rightColor;
        ctx.fill();
        ctx.strokeStyle = strokeColor;
        ctx.stroke();

        // Draw Top Face (t0, t1, t2, t3)
        ctx.beginPath();
        ctx.moveTo(t0.px, t0.py);
        ctx.lineTo(t1.px, t1.py);
        ctx.lineTo(t2.px, t2.py);
        ctx.lineTo(t3.px, t3.py);
        ctx.closePath();
        ctx.fillStyle = topColor;
        ctx.fill();
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = isCurrent ? 1.6 : 1;
        ctx.stroke();

        // Top surface center
        const topCenter = toIso(m.x, m.y, baseZ);

        // Top face status dot or symbol
        if (modIndex === 2 && (isCurrent || isCompleted)) {
          // Failure Dot on Upgrade module
          ctx.beginPath();
          ctx.arc(topCenter.px, topCenter.py - 2, 4, 0, Math.PI * 2);
          ctx.fillStyle = "#E5736A";
          ctx.shadowColor = "#E5736A";
          ctx.shadowBlur = isCurrent ? 8 : 2;
          ctx.fill();
          ctx.shadowBlur = 0;

          // Pulse ripple if current
          if (isCurrent && !prefersReducedMotion) {
            const rippleR = 6 + (Math.sin(time * 0.005) + 1) * 3;
            ctx.beginPath();
            ctx.arc(topCenter.px, topCenter.py - 2, rippleR, 0, Math.PI * 2);
            ctx.strokeStyle = "rgba(229, 115, 106, 0.4)";
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        } else if (modIndex === 4 && (isCurrent || isCompleted)) {
          // Verification Pass Icon on Module 4
          ctx.beginPath();
          ctx.arc(topCenter.px, topCenter.py - 2, 4.5, 0, Math.PI * 2);
          ctx.fillStyle = "#5FCB8A";
          ctx.shadowColor = "#5FCB8A";
          ctx.shadowBlur = isCurrent ? 8 : 3;
          ctx.fill();
          ctx.shadowBlur = 0;
        } else if (modIndex === 3 && isCurrent) {
          // Candidate Patch small sheet moving or floating
          const patchCenter = toIso(m.x, m.y, baseZ + 8 + Math.sin(time * 0.004) * 2);
          ctx.beginPath();
          ctx.arc(patchCenter.px, patchCenter.py, 3.5, 0, Math.PI * 2);
          ctx.fillStyle = "#B7C9AD";
          ctx.shadowColor = "#B7C9AD";
          ctx.shadowBlur = 6;
          ctx.fill();
          ctx.shadowBlur = 0;
        } else if (modIndex === 1 && (isCurrent || isCompleted)) {
          ctx.beginPath();
          ctx.arc(topCenter.px, topCenter.py - 2, 3.5, 0, Math.PI * 2);
          ctx.fillStyle = "#5FCB8A";
          ctx.shadowColor = "#5FCB8A";
          ctx.shadowBlur = 4;
          ctx.fill();
          ctx.shadowBlur = 0;
        }

        // Label above module
        ctx.font = "500 11px var(--font-sans, system-ui)";
        ctx.textAlign = "center";
        ctx.fillStyle = isCurrent ? "#F7F7F2" : "#A9B8AD";
        ctx.fillText(m.name, topCenter.px, topCenter.py + 15);
      });

      // -----------------------------------------------------------------------
      // 4. DRAW EVIDENCE ARTIFACT (CRYSTAL CUBE) AFTER VERIFY (STAGE 4 ONLY)
      // -----------------------------------------------------------------------
      if (currentStage === 4) {
        const verifyMod = MODULES[3];
        const crystalZ = verifyMod.z + 28 + Math.sin(time * 0.003) * 3;
        const cCenter = toIso(verifyMod.x, verifyMod.y, crystalZ);

        // Small rotating diamond badge
        const crW = 10;
        const crH = 10;
        const ct0 = toIso(verifyMod.x, verifyMod.y - crH, crystalZ);
        const ct1 = toIso(verifyMod.x + crW, verifyMod.y, crystalZ);
        const ct2 = toIso(verifyMod.x, verifyMod.y + crH, crystalZ);
        const ct3 = toIso(verifyMod.x - crW, verifyMod.y, crystalZ);

        ctx.beginPath();
        ctx.moveTo(ct0.px, ct0.py);
        ctx.lineTo(ct1.px, ct1.py);
        ctx.lineTo(ct2.px, ct2.py);
        ctx.lineTo(ct3.px, ct3.py);
        ctx.closePath();
        ctx.fillStyle = "rgba(95, 203, 138, 0.4)";
        ctx.fill();
        ctx.strokeStyle = "#5FCB8A";
        ctx.lineWidth = 1.2;
        ctx.stroke();

        ctx.font = "600 9px var(--font-mono, monospace)";
        ctx.fillStyle = "#5FCB8A";
        ctx.textAlign = "center";
        ctx.fillText("EVIDENCE", cCenter.px, cCenter.py - 10);
      }

      ctx.restore();

      if (!prefersReducedMotion) {
        animationFrameId = requestAnimationFrame(render);
      }
    };

    if (!prefersReducedMotion) {
      animationFrameId = requestAnimationFrame(render);
    } else {
      // Single frame render for reduced motion
      render(performance.now());
    }

    return () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
    };
  }, [currentStage, isPlaying, prefersReducedMotion, isOffscreen]);

  const activeStageInfo = STAGES.find((s) => s.id === currentStage) || STAGES[0];

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="relative w-full rounded-2xl border border-[rgba(183,201,173,0.18)] bg-[#15271F] p-4 sm:p-5 shadow-2xl flex flex-col justify-between overflow-hidden"
      data-testid="repair-bench-container"
    >
      {/* Top Meta Header: Scripted Illustration Badge & Current Stage Indicator */}
      <div className="flex items-center justify-between gap-3 mb-2 z-10">
        <div className="flex items-center gap-2">
          <span className="flex size-2 rounded-full bg-[#5FCB8A] animate-pulse" />
          <span className="font-mono text-[11px] font-medium text-[#A9B8AD] tracking-wider uppercase">
            Repair Bench · 2.5D Isometric Simulation
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full border border-[rgba(183,201,173,0.2)] bg-[#1B3228] text-[#A9B8AD]">
            Illustrative sequence
          </span>
        </div>
      </div>

      {/* Center Visualization Canvas or Static Fallback */}
      <div className="relative w-full aspect-[16/10] sm:aspect-[16/9] min-h-[260px] sm:min-h-[300px] flex items-center justify-center">
        {isSupported ? (
          <canvas
            ref={canvasRef}
            className="w-full h-full block cursor-grab active:cursor-grabbing"
            aria-label="Interactive 2.5D illustration of the RepoMedic repair progression through baseline, upgrade failure, candidate patch, and verification."
            role="img"
          />
        ) : (
          /* Designed Static SVG Fallback for unsupported graphics / noscript */
          <div
            className="w-full h-full flex flex-col items-center justify-center p-6 text-center"
            data-testid="static-repair-fallback"
          >
            <svg
              className="w-full max-w-[420px] h-auto"
              viewBox="0 0 400 160"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-label="Static diagram of the 4 repair stages"
            >
              {/* Isometric grid lines */}
              <path d="M40 80 L200 20 L360 80 L200 140 Z" stroke="rgba(183,201,173,0.2)" strokeWidth="1" fill="#1B3228/30" />
              <path d="M40 80 L360 80" stroke="rgba(183,201,173,0.15)" strokeWidth="1" strokeDasharray="4 4" />
              {/* Wire */}
              <path d="M70 85 L140 105 L240 65 L320 85" stroke="#5FCB8A" strokeWidth="2" strokeDasharray="3 3" />
              {/* Stage nodes */}
              <circle cx="70" cy="85" r="14" fill="#15271F" stroke="#5FCB8A" strokeWidth="2" />
              <text x="70" y="89" fill="#F7F7F2" fontSize="9" textAnchor="middle" fontFamily="sans-serif">1</text>
              <circle cx="140" cy="105" r="14" fill="#2E1B1B" stroke="#E5736A" strokeWidth="2" />
              <text x="140" y="109" fill="#E5736A" fontSize="9" textAnchor="middle" fontFamily="sans-serif">2</text>
              <circle cx="240" cy="65" r="14" fill="#202B1E" stroke="#B7C9AD" strokeWidth="2" />
              <text x="240" y="69" fill="#B7C9AD" fontSize="9" textAnchor="middle" fontFamily="sans-serif">3</text>
              <circle cx="320" cy="85" r="14" fill="#142A20" stroke="#5FCB8A" strokeWidth="2" />
              <text x="320" y="89" fill="#5FCB8A" fontSize="9" textAnchor="middle" fontFamily="sans-serif">4</text>
            </svg>
            <p className="mt-3 text-xs text-[#A9B8AD]">
              Static representation of baseline, upgrade failure, candidate patch, and verified evidence.
            </p>
          </div>
        )}
      </div>

      {/* Active Stage Accessible Narrative Box */}
      <div
        className="mt-3 rounded-xl border border-[rgba(183,201,173,0.14)] bg-[#0D1915]/90 p-3.5 backdrop-blur-sm transition-all duration-200"
        aria-live="polite"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-2">
            <span
              className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full border ${activeStageInfo.badgeColor}`}
            >
              {activeStageInfo.badge}
            </span>
            <span className="text-xs font-semibold text-[#F7F7F2]">
              {activeStageInfo.title}
            </span>
          </div>
          <span className="text-[11px] font-mono text-[#A9B8AD]">
            Step {currentStage} of 4
          </span>
        </div>
        <p className="text-xs text-[#A9B8AD] leading-relaxed">
          {activeStageInfo.description}
        </p>
      </div>

      {/* Accessible Controls Bar: Play/Pause and Step Selector Pills */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2.5 pt-2 border-t border-[rgba(183,201,173,0.12)]">
        {/* Play/Pause Button */}
        <button
          type="button"
          onClick={() => setIsPlaying((prev) => !prev)}
          className="min-h-[44px] min-w-[44px] px-3 py-2 rounded-lg border border-[rgba(183,201,173,0.24)] bg-[#1B3228] hover:bg-[#223E32] text-[#F7F7F2] text-xs font-medium flex items-center justify-center gap-1.5 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-[#B7C9AD] outline-none"
          aria-label={isPlaying ? "Pause illustrative animation" : "Play illustrative animation"}
          data-testid="btn-scene-play-pause"
        >
          {isPlaying ? (
            <>
              <Pause className="size-3.5 text-[#B7C9AD]" />
              <span className="hidden xs:inline">Pause</span>
            </>
          ) : (
            <>
              <Play className="size-3.5 text-[#5FCB8A]" />
              <span className="hidden xs:inline">Play</span>
            </>
          )}
        </button>

        {/* 4 Step Selector Buttons */}
        <div
          role="group"
          aria-label="Repair benchmark stage selector"
          className="flex flex-wrap items-center gap-1.5"
        >
          {STAGES.map((s) => {
            const isSelected = currentStage === s.id;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => selectStage(s.id)}
                aria-pressed={isSelected}
                data-testid={`btn-scene-stage-${s.id}`}
                className={`min-h-[44px] px-3 py-2 text-xs font-mono font-medium rounded-lg border transition-all cursor-pointer focus-visible:ring-2 focus-visible:ring-[#B7C9AD] outline-none flex items-center gap-1.5 ${
                  isSelected
                    ? "bg-[#1B3228] border-[#B7C9AD] text-[#F7F7F2] shadow-sm"
                    : "bg-[#0D1915] border-[rgba(183,201,173,0.16)] text-[#A9B8AD] hover:text-[#F7F7F2] hover:border-[rgba(183,201,173,0.3)]"
                }`}
              >
                {s.id === 2 ? (
                  <span className="size-1.5 rounded-full bg-[#E5736A]" />
                ) : s.id === 4 ? (
                  <span className="size-1.5 rounded-full bg-[#5FCB8A]" />
                ) : (
                  <span className="size-1.5 rounded-full bg-[#B7C9AD]" />
                )}
                <span>{s.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}