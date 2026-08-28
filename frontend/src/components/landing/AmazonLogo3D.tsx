"use client";

import { motion } from "framer-motion";

/* --------------------------------------------------------------------------
 * 3D Glassmorphism AmazonLogo3D — Hero Illustration
 * Pure white background, central black frosted-glass card, floating glass elements
 * All side icons float LEFT-TO-RIGHT and UPWARD (opposite from typical)
 * -------------------------------------------------------------------------- */

export default function AmazonLogo3D() {
  return (
    <div className="relative w-full max-w-[520px] aspect-square mx-auto flex items-center justify-center">
      {/* ============ VOLUMETRIC LIGHTING / GLOW ============ */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Top-right warm glow */}
        <div className="absolute -top-10 -right-10 w-72 h-72 bg-brand-orange/[0.06] rounded-full blur-[90px]" />
        {/* Bottom-left cool glow */}
        <div className="absolute -bottom-10 -left-10 w-64 h-64 bg-blue-400/[0.04] rounded-full blur-[80px]" />
        {/* Center radial highlight */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-white rounded-full blur-[60px] opacity-60" />
      </div>

      {/* ============ MAIN BLACK FROSTED GLASS CARD ============ */}
      <motion.div
        initial={{ opacity: 0, y: 30, rotateX: -8 }}
        animate={{ opacity: 1, y: 0, rotateX: 0 }}
        transition={{ duration: 0.9, ease: "easeOut", delay: 0.15 }}
        className="relative z-10"
        style={{ perspective: "1200px" }}
      >
        <motion.div
          animate={{ y: [0, -6, 0], rotateY: [0, 2, 0, -2, 0] }}
          transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
          style={{ transformStyle: "preserve-3d" }}
        >
          {/* Ground shadow */}
          <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 w-56 h-8 bg-gray-900/10 rounded-full blur-2xl" />

          {/* The card */}
          <div className="relative w-64 h-72 sm:w-72 sm:h-80 rounded-3xl overflow-hidden"
            style={{
              background: "linear-gradient(135deg, rgba(15,17,23,0.92) 0%, rgba(25,28,36,0.88) 50%, rgba(15,17,23,0.95) 100%)",
              backdropFilter: "blur(40px) saturate(180%)",
              WebkitBackdropFilter: "blur(40px) saturate(180%)",
              boxShadow: "0 0 0 1px rgba(255,255,255,0.08), 0 25px 60px -12px rgba(0,0,0,0.5), 0 0 80px -20px rgba(255,153,0,0.15), inset 0 1px 0 0 rgba(255,255,255,0.1)",
            }}
          >
            {/* Glass refraction highlight */}
            <div className="absolute top-0 left-0 right-0 h-1/3 bg-gradient-to-b from-white/[0.07] to-transparent pointer-events-none rounded-t-3xl" />
            {/* Subtle grid */}
            <div
              className="absolute inset-0 pointer-events-none opacity-[0.025]"
              style={{
                backgroundImage: "linear-gradient(rgba(255,255,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.3) 1px, transparent 1px)",
                backgroundSize: "24px 24px",
              }}
            />

            {/* --- Top-left: orange square "a" logo --- */}
            <motion.div
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.6, duration: 0.4, type: "spring" }}
              className="absolute top-4 left-4 w-9 h-9 rounded-xl bg-gradient-to-br from-brand-orange to-orange-600 flex items-center justify-center shadow-lg shadow-brand-orange/30"
            >
              <span className="text-white font-black text-sm leading-none">a</span>
            </motion.div>

            {/* --- Top-right: "2026" --- */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8, duration: 0.4 }}
              className="absolute top-4 right-4 text-[10px] font-mono font-bold text-white/30 tracking-widest"
            >
              2026
            </motion.div>

            {/* --- Center: Amazon logo (white) + smile arrow --- */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pt-6">
              <AmazonWhiteLogo />
            </div>

            {/* --- Bottom: AF-AGENT-2026 code --- */}
            <div className="absolute bottom-4 left-0 right-0 text-center">
              <span className="text-[9px] font-mono font-semibold text-white/20 tracking-[0.2em]">AF-AGENT-2026</span>
            </div>

            {/* --- 3D depth side --- */}
            <div
              className="absolute top-4 right-0 w-[3px] h-[calc(100%-16px)] rounded-r-3xl"
              style={{ background: "linear-gradient(to bottom, rgba(255,255,255,0.06), rgba(255,255,255,0.02))" }}
            />
          </div>
        </motion.div>
      </motion.div>

      {/* ==================================================================
          FLOATING ELEMENTS — All drift LEFT→RIGHT and UPWARD
          ================================================================== */}

      {/* --- Percentage badge: 50% (top-left area, drifting right+up) --- */}
      <GlassPercentBadge
        percent="50%"
        className="absolute top-[8%] left-[4%] z-20"
        delay={0.8}
        direction="right-up"
      />

      {/* --- Percentage badge: 30% (mid-left, drifting right+up) --- */}
      <GlassPercentBadge
        percent="30%"
        className="absolute top-[38%] left-[0%] z-20"
        delay={1.1}
        direction="right-up"
      />

      {/* --- Percentage badge: 20% (bottom-left, drifting right+up) --- */}
      <GlassPercentBadge
        percent="20%"
        className="absolute bottom-[18%] left-[8%] z-20"
        delay={1.4}
        direction="right-up"
      />

      {/* --- Glass Gift Box 1 (top-right, drifting right+up) --- */}
      <GlassGiftBox className="absolute top-[6%] right-[6%] z-20" delay={1.0} direction="right-up" size="sm" />

      {/* --- Glass Gift Box 2 (mid-right, drifting right+up) --- */}
      <GlassGiftBox className="absolute top-[42%] right-[2%] z-20" delay={1.3} direction="right-up" size="md" />

      {/* --- Glass Robot Head (bottom-right, drifting right+up) --- */}
      <GlassRobotHead className="absolute bottom-[12%] right-[10%] z-20" delay={1.2} direction="right-up" />

      {/* --- Glass Robot Head 2 (top-center-left, drifting right+up) --- */}
      <GlassRobotHead className="absolute top-[22%] left-[18%] z-20" delay={1.5} direction="right-up" size="sm" />

      {/* --- Neural Network Node (mid-right, drifting right+up) --- */}
      <NeuralNode className="absolute top-[55%] right-[16%] z-15" delay={1.0} direction="right-up" />

      {/* --- Neural Node 2 (bottom-center, drifting right+up) --- */}
      <NeuralNode className="absolute bottom-[25%] left-[28%] z-15" delay={1.6} direction="right-up" size="sm" />

      {/* --- Glass Amazon Smile Tag "AI" (bottom-left, drifting right+up) --- */}
      <GlassAmazonTag className="absolute bottom-[5%] left-[16%] z-20" delay={1.4} direction="right-up" />

      {/* --- Glass Amazon Smile Tag "AI" (top-right, drifting right+up) --- */}
      <GlassAmazonTag className="absolute top-[14%] right-[22%] z-20" delay={1.7} direction="right-up" size="sm" />

      {/* ============ SPARKLES ============ */}
      <Sparkles />

      {/* ============ FLOATING CONNECTION LINES ============ */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-0 opacity-[0.06]" viewBox="0 0 520 520">
        <motion.line
          x1="120" y1="160" x2="260" y2="220"
          stroke="url(#lineGrad1)" strokeWidth="1"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ delay: 1, duration: 1.5 }}
        />
        <motion.line
          x1="400" y1="200" x2="280" y2="280"
          stroke="url(#lineGrad2)" strokeWidth="1"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ delay: 1.2, duration: 1.5 }}
        />
        <motion.line
          x1="150" y1="380" x2="240" y2="300"
          stroke="url(#lineGrad1)" strokeWidth="1"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ delay: 1.4, duration: 1.5 }}
        />
        <motion.line
          x1="380" y1="360" x2="280" y2="310"
          stroke="url(#lineGrad2)" strokeWidth="1"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ delay: 1.6, duration: 1.5 }}
        />
        <defs>
          <linearGradient id="lineGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#F97316" stopOpacity="0" />
            <stop offset="50%" stopColor="#F97316" stopOpacity="1" />
            <stop offset="100%" stopColor="#F97316" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="lineGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3B82F6" stopOpacity="0" />
            <stop offset="50%" stopColor="#3B82F6" stopOpacity="1" />
            <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}

/* --------------------------------------------------------------------------
 * White Amazon Logo with smile arrow
 * -------------------------------------------------------------------------- */

function AmazonWhiteLogo() {
  return (
    <div className="flex flex-col items-center">
      {/* Amazon wordmark */}
      <svg viewBox="0 0 200 60" className="w-40 sm:w-48 h-auto" fill="none">
        <defs>
          <linearGradient id="whiteLogoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#e0e0e0" />
          </linearGradient>
          <filter id="logoGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
            <feFlood floodColor="#F97316" floodOpacity="0.3" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <text
          x="100" y="35"
          textAnchor="middle"
          fill="url(#whiteLogoGrad)"
          fontSize="32"
          fontWeight="800"
          fontFamily="Inter, system-ui, sans-serif"
          letterSpacing="-0.5"
          filter="url(#logoGlow)"
        >
          amazon
        </text>
        {/* Smile arrow */}
        <motion.path
          d="M55 44 Q100 56 145 44"
          stroke="#F97316"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.8, ease: "easeOut" }}
        />
        <motion.g
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 1.5, duration: 0.3 }}
        >
          <path d="M140 42 L148 44 L140 48" stroke="#F97316" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </motion.g>
      </svg>

      {/* "AI Fulfillment Agent" text */}
      <motion.h2
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6, duration: 0.5 }}
        className="mt-4 text-xl sm:text-2xl font-extrabold tracking-tight"
        style={{
          background: "linear-gradient(135deg, #ffffff 0%, #d4d4d8 50%, #ffffff 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          textShadow: "none",
          filter: "drop-shadow(0 2px 8px rgba(255,255,255,0.15))",
        }}
      >
        AI Fulfillment Agent
      </motion.h2>
    </div>
  );
}

/* --------------------------------------------------------------------------
 * Glass Percentage Badge — translucent yellow/black
 * -------------------------------------------------------------------------- */

function GlassPercentBadge({
  percent,
  className = "",
  delay = 0,
  direction = "right-up",
}: {
  percent: string;
  className?: string;
  delay?: number;
  direction?: "right-up" | "left-up";
}) {
  const xDrift = direction === "right-up" ? [0, 12, 0] : [0, -12, 0];
  return (
    <motion.div
      initial={{ opacity: 0, x: direction === "right-up" ? -15 : 15, y: 15 }}
      animate={{
        opacity: 1,
        x: 0,
        y: 0,
      }}
      transition={{ delay, duration: 0.6, ease: "easeOut" }}
      className={className}
    >
      <motion.div
        animate={{ y: [0, -5, 0], x: xDrift }}
        transition={{ duration: 4 + delay, repeat: Infinity, ease: "easeInOut" }}
        className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl flex items-center justify-center"
        style={{
          background: "linear-gradient(135deg, rgba(250,204,21,0.15) 0%, rgba(17,24,39,0.6) 100%)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          boxShadow: "0 0 0 1px rgba(250,204,21,0.15), 0 8px 25px -5px rgba(0,0,0,0.2), inset 0 1px 0 0 rgba(255,255,255,0.1)",
        }}
      >
        <span className="text-sm sm:text-base font-black text-yellow-300/90">{percent}</span>
      </motion.div>
    </motion.div>
  );
}

/* --------------------------------------------------------------------------
 * Glass Gift Box — glossy with orange ribbon
 * -------------------------------------------------------------------------- */

function GlassGiftBox({
  className = "",
  delay = 0,
  direction = "right-up",
  size = "md",
}: {
  className?: string;
  delay?: number;
  direction?: "right-up" | "left-up";
  size?: "sm" | "md";
}) {
  const sz = size === "sm" ? "w-12 h-12" : "w-14 h-14 sm:w-16 sm:h-16";
  const xDrift = direction === "right-up" ? [0, 10, 0] : [0, -10, 0];

  return (
    <motion.div
      initial={{ opacity: 0, x: direction === "right-up" ? -15 : 15, y: 15 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ delay, duration: 0.6, ease: "easeOut" }}
      className={className}
    >
      <motion.div
        animate={{ y: [0, -6, 0], rotate: [0, 3, 0, -3, 0], x: xDrift }}
        transition={{ duration: 5 + delay, repeat: Infinity, ease: "easeInOut" }}
        className={`${sz} rounded-2xl relative flex items-center justify-center`}
        style={{
          background: "linear-gradient(135deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.04) 100%)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          boxShadow: "0 0 0 1px rgba(255,255,255,0.12), 0 10px 30px -8px rgba(0,0,0,0.15), inset 0 1px 0 0 rgba(255,255,255,0.15)",
        }}
      >
        {/* Gift icon */}
        <svg viewBox="0 0 24 24" className="w-6 h-6 sm:w-7 sm:h-7" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="3" y="10" width="18" height="11" rx="2" className="text-white/50" />
          <rect x="1" y="6" width="22" height="4" rx="1" className="text-white/60" />
          <line x1="12" y1="6" x2="12" y2="21" className="text-brand-orange/70" strokeWidth="2" />
          <path d="M12 6C12 6 9 2 6.5 3.5S7 6 12 6Z" className="text-brand-orange/50" />
          <path d="M12 6C12 6 15 2 17.5 3.5S17 6 12 6Z" className="text-brand-orange/50" />
        </svg>
        {/* Ribbon shine */}
        <div className="absolute top-1 left-1 w-3 h-3 bg-white/20 rounded-full blur-sm" />
      </motion.div>
    </motion.div>
  );
}

/* --------------------------------------------------------------------------
 * Glass Robot Head — frosted glass AI robot
 * -------------------------------------------------------------------------- */

function GlassRobotHead({
  className = "",
  delay = 0,
  direction = "right-up",
  size = "md",
}: {
  className?: string;
  delay?: number;
  direction?: "right-up" | "left-up";
  size?: "sm" | "md";
}) {
  const sz = size === "sm" ? "w-12 h-12" : "w-14 h-14 sm:w-16 sm:h-16";
  const xDrift = direction === "right-up" ? [0, 8, 0] : [0, -8, 0];

  return (
    <motion.div
      initial={{ opacity: 0, x: direction === "right-up" ? -15 : 15, y: 15 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ delay, duration: 0.6, ease: "easeOut" }}
      className={className}
    >
      <motion.div
        animate={{ y: [0, -5, 0], rotate: [0, -2, 0, 2, 0], x: xDrift }}
        transition={{ duration: 4.5 + delay, repeat: Infinity, ease: "easeInOut" }}
        className={`${sz} rounded-2xl relative flex items-center justify-center`}
        style={{
          background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.03) 100%)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          boxShadow: "0 0 0 1px rgba(255,255,255,0.1), 0 10px 30px -8px rgba(0,0,0,0.15), inset 0 1px 0 0 rgba(255,255,255,0.12)",
        }}
      >
        {/* Robot face */}
        <svg viewBox="0 0 24 24" className="w-7 h-7 sm:w-8 sm:h-8" fill="none">
          {/* Head */}
          <rect x="4" y="7" width="16" height="12" rx="4" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" />
          {/* Eyes */}
          <circle cx="9" cy="13" r="1.5" fill="rgba(59,130,246,0.7)" />
          <circle cx="15" cy="13" r="1.5" fill="rgba(249,115,22,0.7)" />
          {/* Antenna */}
          <line x1="12" y1="7" x2="12" y2="4" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" />
          <circle cx="12" cy="3" r="1.5" fill="rgba(249,115,22,0.6)" />
          {/* Mouth */}
          <path d="M9 16 Q12 18 15 16" stroke="rgba(255,255,255,0.25)" strokeWidth="1" strokeLinecap="round" />
        </svg>
        {/* Eye glow */}
        <div className="absolute top-[52%] left-[33%] w-2 h-2 bg-blue-400/40 rounded-full blur-sm" />
        <div className="absolute top-[52%] right-[33%] w-2 h-2 bg-brand-orange/40 rounded-full blur-sm" />
      </motion.div>
    </motion.div>
  );
}

/* --------------------------------------------------------------------------
 * Neural Network Node — transparent glowing nodes
 * -------------------------------------------------------------------------- */

function NeuralNode({
  className = "",
  delay = 0,
  direction = "right-up",
  size = "md",
}: {
  className?: string;
  delay?: number;
  direction?: "right-up" | "left-up";
  size?: "sm" | "md";
}) {
  const sz = size === "sm" ? "w-10 h-10" : "w-12 h-12 sm:w-14 sm:h-14";
  const xDrift = direction === "right-up" ? [0, 10, 0] : [0, -10, 0];

  return (
    <motion.div
      initial={{ opacity: 0, x: direction === "right-up" ? -10 : 10, y: 10 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ delay, duration: 0.6, ease: "easeOut" }}
      className={className}
    >
      <motion.div
        animate={{ y: [0, -4, 0], x: xDrift, scale: [1, 1.05, 1] }}
        transition={{ duration: 4 + delay, repeat: Infinity, ease: "easeInOut" }}
        className={`${sz} relative flex items-center justify-center`}
      >
        <svg viewBox="0 0 40 40" className="w-full h-full" fill="none">
          {/* Outer ring */}
          <circle cx="20" cy="20" r="18" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
          {/* Inner glow circle */}
          <circle cx="20" cy="20" r="12" fill="rgba(59,130,246,0.06)" stroke="rgba(59,130,246,0.15)" strokeWidth="1" />
          {/* Center dot */}
          <circle cx="20" cy="20" r="3" fill="rgba(59,130,246,0.3)" />
          {/* Connection lines */}
          <line x1="20" y1="2" x2="20" y2="8" stroke="rgba(255,255,255,0.08)" strokeWidth="0.8" />
          <line x1="20" y1="32" x2="20" y2="38" stroke="rgba(255,255,255,0.08)" strokeWidth="0.8" />
          <line x1="2" y1="20" x2="8" y2="20" stroke="rgba(255,255,255,0.08)" strokeWidth="0.8" />
          <line x1="32" y1="20" x2="38" y2="20" stroke="rgba(255,255,255,0.08)" strokeWidth="0.8" />
          {/* Small nodes at cardinal points */}
          <circle cx="20" cy="4" r="1.5" fill="rgba(249,115,22,0.3)" />
          <circle cx="36" cy="20" r="1.5" fill="rgba(59,130,246,0.3)" />
          <circle cx="20" cy="36" r="1.5" fill="rgba(16,185,129,0.3)" />
          <circle cx="4" cy="20" r="1.5" fill="rgba(168,85,247,0.3)" />
        </svg>
      </motion.div>
    </motion.div>
  );
}

/* --------------------------------------------------------------------------
 * Glass Amazon Smile Tag "AI" — frosted tag with orange arrow
 * -------------------------------------------------------------------------- */

function GlassAmazonTag({
  className = "",
  delay = 0,
  direction = "right-up",
  size = "md",
}: {
  className?: string;
  delay?: number;
  direction?: "right-up" | "left-up";
  size?: "sm" | "md";
}) {
  const sz = size === "sm" ? "w-16 h-8" : "w-20 h-9 sm:w-24 sm:h-10";
  const xDrift = direction === "right-up" ? [0, 8, 0] : [0, -8, 0];

  return (
    <motion.div
      initial={{ opacity: 0, x: direction === "right-up" ? -15 : 15, y: 15 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ delay, duration: 0.6, ease: "easeOut" }}
      className={className}
    >
      <motion.div
        animate={{ y: [0, -4, 0], x: xDrift, rotate: [0, 2, 0, -2, 0] }}
        transition={{ duration: 5 + delay, repeat: Infinity, ease: "easeInOut" }}
        className={`${sz} rounded-full relative flex items-center justify-center gap-1`}
        style={{
          background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.03) 100%)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          boxShadow: "0 0 0 1px rgba(255,255,255,0.1), 0 6px 20px -5px rgba(0,0,0,0.12), inset 0 1px 0 0 rgba(255,255,255,0.1)",
        }}
      >
        {/* Amazon smile mini */}
        <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none">
          <path d="M2 10 Q8 14 14 10" stroke="#F97316" strokeWidth="1.5" strokeLinecap="round" fill="none" />
          <path d="M12 9 L14.5 10 L12 11.5" stroke="#F97316" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </svg>
        <span className="text-[9px] sm:text-[10px] font-bold text-white/60 tracking-wide">AI</span>
      </motion.div>
    </motion.div>
  );
}

/* --------------------------------------------------------------------------
 * Sparkles — subtle animated sparkle dots
 * -------------------------------------------------------------------------- */

function Sparkles() {
  const sparkles = [
    { top: "15%", left: "10%", delay: 1.0, dur: 3.5 },
    { top: "25%", right: "8%", delay: 1.5, dur: 4 },
    { top: "60%", left: "5%", delay: 2.0, dur: 3 },
    { top: "70%", right: "12%", delay: 1.8, dur: 3.5 },
    { top: "40%", left: "22%", delay: 2.2, dur: 4 },
    { top: "85%", right: "20%", delay: 1.3, dur: 3.2 },
    { top: "10%", right: "25%", delay: 2.5, dur: 3.8 },
    { top: "90%", left: "18%", delay: 1.7, dur: 3.5 },
    { top: "50%", right: "30%", delay: 2.1, dur: 4.2 },
    { top: "35%", left: "35%", delay: 1.9, dur: 3.3 },
  ];

  return (
    <>
      {sparkles.map((s, i) => (
        <motion.div
          key={i}
          className="absolute pointer-events-none z-30"
          style={{ top: s.top, left: "left" in s ? s.left : undefined, right: "right" in s ? (s as {right:string}).right : undefined }}
          animate={{
            opacity: [0, 1, 0],
            scale: [0, 1.2, 0],
          }}
          transition={{
            delay: s.delay,
            duration: s.dur,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
            <path d="M4 0L4.8 3.2L8 4L4.8 4.8L4 8L3.2 4.8L0 4L3.2 3.2Z" fill="rgba(255,255,255,0.5)" />
          </svg>
        </motion.div>
      ))}
    </>
  );
}
