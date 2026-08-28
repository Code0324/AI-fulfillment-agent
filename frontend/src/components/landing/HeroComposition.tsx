"use client";

import { motion } from "framer-motion";
import Image from "next/image";

/* =========================================================================
 * HeroComposition — Animated PNG Composition
 *
 * Only the main board asset actually exists in public/images/ — the badge,
 * gift box, network node, and decorative sphere layers referenced their own
 * PNGs that were never added, so they rendered as broken images. Trimmed
 * down to the one real asset.
 * ========================================================================= */

// ─── Animation config per layer ──────────────────────────────────────────
interface LayerConfig {
  src: string;
  alt: string;
  /** CSS positioning (percentage-based relative to composition container) */
  top: string;
  left: string;
  width: string;
  height: string;
  /** z-index stacking */
  z: number;
  /** Entrance delay (seconds) — controls stagger sequence */
  delay: number;
  /** Continuous float amplitude (px) */
  floatY: number;
  /** Continuous rotation range (degrees) */
  rotateRange: number;
  /** Scale breathe range [min, max] */
  scaleRange: [number, number];
  /** Float cycle duration (seconds) */
  floatDuration: number;
  /** Extra: shimmer or glow color */
  shimmer?: string;
}

const LAYERS: LayerConfig[] = [
  // ── Main board — the only real asset, centered ──
  {
    src: "/images/01_main_board_transparent.png",
    alt: "AI Fulfillment Agent Board",
    top: "8%",
    left: "12%",
    width: "76%",
    height: "84%",
    z: 10,
    delay: 0,
    floatY: 6,
    rotateRange: 1.5,
    scaleRange: [1, 1.015],
    floatDuration: 6,
    shimmer: "linear-gradient(120deg, transparent 30%, rgba(255,255,255,0.06) 50%, transparent 70%)",
  },
];

/* ─────────────────────────────────────────────────────────────────────────
 * Animated Layer — renders one PNG with its own animation
 * ───────────────────────────────────────────────────────────────────────── */
function AnimatedLayer({ config }: { config: LayerConfig }) {
  const {
    src, alt, top, left, width, height, z,
    delay, floatY, rotateRange, scaleRange, floatDuration, shimmer,
  } = config;

  return (
    <motion.div
      className="absolute pointer-events-none"
      style={{ top, left, width, height, zIndex: z }}
      initial={{ opacity: 0, scale: 0.85, y: 30 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{
        delay,
        duration: 0.8,
        ease: [0.25, 0.46, 0.45, 0.94], // cinematic easeOut
      }}
    >
      {/* Continuous animation wrapper */}
      <motion.div
        className="relative w-full h-full"
        animate={{
          y: [0, -floatY, 0],
          rotate: [0, rotateRange, 0, -rotateRange, 0],
          scale: scaleRange
            ? [scaleRange[0], scaleRange[1], scaleRange[0]]
            : [1, 1, 1],
        }}
        transition={{
          y: {
            duration: floatDuration,
            repeat: Infinity,
            ease: "easeInOut",
          },
          rotate: {
            duration: floatDuration * 1.2,
            repeat: Infinity,
            ease: "easeInOut",
          },
          scale: {
            duration: floatDuration * 0.8,
            repeat: Infinity,
            ease: "easeInOut",
          },
        }}
      >
        {/* The actual PNG asset — untouched */}
        <Image
          src={src}
          alt={alt}
          fill
          className="object-contain"
          sizes="(max-width: 1024px) 0px, 520px"
          priority={delay < 0.5}
        />

        {/* Metallic light sweep overlay */}
        {shimmer && (
          <motion.div
            className="absolute inset-0 pointer-events-none overflow-hidden"
            animate={{
              background: [
                shimmer,
                shimmer.replace("30%", "60%").replace("50%", "80%").replace("70%", "90%"),
                shimmer,
              ],
            }}
            transition={{
              duration: 5,
              repeat: Infinity,
              ease: "easeInOut",
              delay: delay + 1,
            }}
          />
        )}
      </motion.div>
    </motion.div>
  );
}

/* =========================================================================
 * Main Composition Component
 * ========================================================================= */
export default function HeroComposition() {
  return (
    <div className="relative w-full max-w-[620px] aspect-[5/4] mx-auto">
      {/* Subtle depth shadows behind the composition */}
      <div className="absolute inset-[10%] bg-brand-orange/[0.03] rounded-full blur-[60px] pointer-events-none" />
      <div className="absolute inset-[15%] bg-brand-blue/[0.02] rounded-full blur-[50px] pointer-events-none" />

      {/* Render each PNG layer independently */}
      {LAYERS.map((layer) => (
        <AnimatedLayer key={layer.src} config={layer} />
      ))}
    </div>
  );
}
