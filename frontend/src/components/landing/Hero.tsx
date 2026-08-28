"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Play } from "lucide-react";
import HeroComposition from "@/components/landing/HeroComposition";

/* =========================================================================
 * Hero Section — Amazon AI Fulfillment Agent
 *
 * Left side: text content with staggered entrance animations
 * Right side: HeroComposition — 8 PNG assets animated independently
 * ========================================================================= */

const trustBadges = [
  { icon: CheckCircle2, text: "Save 90% Time" },
  { icon: CheckCircle2, text: "Zero Human Error" },
  { icon: CheckCircle2, text: "Policy-Safe" },
  { icon: CheckCircle2, text: "Fully Automated" },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" as const } },
};

export default function Hero() {
  return (
    <section
      id="home"
      className="relative min-h-screen bg-gradient-to-br from-white via-blue-50/40 to-orange-50/30 pt-24 pb-16 overflow-hidden"
    >
      {/* Background blurs */}
      <motion.div
        animate={{ scale: [1, 1.05, 1], opacity: [0.03, 0.05, 0.03] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="absolute top-20 left-0 w-[500px] h-[500px] bg-brand-blue rounded-full blur-[100px] pointer-events-none"
      />
      <motion.div
        animate={{ scale: [1, 1.08, 1], opacity: [0.04, 0.06, 0.04] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        className="absolute bottom-0 right-0 w-[600px] h-[600px] bg-brand-orange rounded-full blur-[120px] pointer-events-none"
      />

      <div className="section-container">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-8 items-center">
          {/* ═══════════════ LEFT: Text ═══════════════ */}
          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="relative z-10"
          >
            {/* Version badge */}
            <motion.div variants={item} className="mb-6">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-100 text-xs font-semibold text-brand-blue">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-blue animate-pulse" />
                v2.0 — Now with AI Agent Support
              </div>
            </motion.div>

            {/* Heading */}
            <motion.h1
              variants={item}
              className="text-4xl sm:text-5xl lg:text-[3.4rem] font-extrabold leading-[1.08] tracking-tight text-gray-900"
            >
              Your 24/7{" "}
              <span className="relative inline-block">
                <span className="relative z-10 bg-gradient-to-r from-brand-blue to-blue-500 bg-clip-text text-transparent">
                  AI Employee
                </span>
                <motion.span
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ delay: 0.8, duration: 0.6, ease: "easeOut" }}
                  className="absolute bottom-1 left-0 right-0 h-3 bg-brand-blue/10 rounded-sm -z-0 origin-left"
                />
              </span>{" "}
              for{" "}
              <motion.span
                initial={{ opacity: 0, color: "#F97316" }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6, duration: 0.4 }}
              >
                Amazon
              </motion.span>{" "}
              Order Fulfillment
            </motion.h1>

            {/* Subtext */}
            <motion.p
              variants={item}
              className="mt-6 text-lg text-gray-500 leading-relaxed max-w-xl"
            >
              Automate product sourcing, address handling, supplier checkout and
              order fulfillment — safely, smartly and at scale.
            </motion.p>

            {/* Trust badges */}
            <motion.div variants={item} className="flex flex-wrap gap-2.5 mt-8">
              {trustBadges.map(({ icon: Icon, text }, i) => (
                <motion.div
                  key={text}
                  initial={{ opacity: 0, y: 10, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ delay: 0.7 + i * 0.1, duration: 0.4, ease: "easeOut" }}
                  whileHover={{ scale: 1.05, y: -2 }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-green-50 border border-green-200/60 text-sm font-medium text-green-700 cursor-default"
                >
                  <Icon className="w-3.5 h-3.5 text-green-500" />
                  {text}
                </motion.div>
              ))}
            </motion.div>

            {/* CTAs */}
            <motion.div variants={item} className="flex flex-wrap items-center gap-4 mt-8">
              <motion.a
                href="/demo"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.1, duration: 0.5, ease: "easeOut" }}
                whileHover={{ scale: 1.03, y: -2 }}
                whileTap={{ scale: 0.97 }}
                className="inline-flex items-center gap-2 px-7 py-3.5 text-sm font-semibold text-white bg-brand-blue hover:bg-brand-blue-dark rounded-xl transition-colors duration-200 shadow-lg shadow-brand-blue/20 hover:shadow-xl hover:shadow-brand-blue/30"
              >
                Start Free Demo
                <motion.span
                  animate={{ x: [0, 4, 0] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                >
                  →
                </motion.span>
              </motion.a>

              <motion.button
                onClick={() => {
                  document.getElementById("video-modal-trigger")?.click();
                }}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.2, duration: 0.5, ease: "easeOut" }}
                whileHover={{ scale: 1.03, y: -2 }}
                whileTap={{ scale: 0.97 }}
                className="inline-flex items-center gap-2 px-6 py-3.5 text-sm font-semibold text-brand-blue border-2 border-brand-blue/20 hover:border-brand-blue/40 hover:bg-blue-50/50 rounded-xl transition-colors duration-200"
              >
                <span className="flex items-center justify-center w-7 h-7 rounded-full bg-brand-blue/10">
                  <Play className="w-3.5 h-3.5 fill-brand-blue text-brand-blue" />
                </span>
                Watch How It Works
              </motion.button>
            </motion.div>

            {/* Footer note */}
            <motion.p variants={item} className="mt-6 text-sm text-gray-400">
              Built for Amazon Sellers, Agencies &amp; Ecommerce Brands
            </motion.p>
          </motion.div>

          {/* ═══════════════ RIGHT: 8-Layer Animated Composition ═══════════════ */}
          <motion.div
            initial={{ opacity: 0, x: 60, y: 30, rotate: 2 }}
            animate={{ opacity: 1, x: 0, y: 0, rotate: 0 }}
            transition={{ duration: 1, ease: "easeOut", delay: 0.3 }}
            className="relative hidden lg:flex items-center justify-center py-8"
          >
            <HeroComposition />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
