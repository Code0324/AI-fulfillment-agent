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
      className="relative min-h-screen bg-luxury-cream pt-24 pb-16 overflow-hidden"
    >
      {/* Background blurs */}
      <motion.div
        animate={{ scale: [1, 1.05, 1], opacity: [0.02, 0.03, 0.02] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="absolute top-20 left-0 w-[500px] h-[500px] bg-luxury-gold rounded-full blur-[100px] pointer-events-none"
      />
      <motion.div
        animate={{ scale: [1, 1.08, 1], opacity: [0.02, 0.04, 0.02] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        className="absolute bottom-0 right-0 w-[600px] h-[600px] bg-luxury-charcoal rounded-full blur-[120px] pointer-events-none"
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
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-luxury-gold/10 border border-luxury-gold/20 text-xs font-semibold text-luxury-charcoal">
                <span className="w-1.5 h-1.5 rounded-full bg-luxury-gold animate-pulse" />
                Automated Order Fulfillment
              </div>
            </motion.div>

            {/* Heading */}
            <motion.h1
              variants={item}
              className="text-4xl sm:text-5xl lg:text-[3.4rem] font-serif font-bold leading-[1.08] tracking-tight text-luxury-charcoal"
            >
              Streamline Your{" "}
              <span className="relative inline-block">
                <span className="relative z-10 text-luxury-gold">
                  Order Fulfillment
                </span>
                <motion.span
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ delay: 0.8, duration: 0.6, ease: "easeOut" }}
                  className="absolute bottom-1 left-0 right-0 h-3 bg-luxury-gold/10 rounded-sm -z-0 origin-left"
                />
              </span>
            </motion.h1>

            {/* Subtext */}
            <motion.p
              variants={item}
              className="mt-6 text-lg text-gray-600 leading-relaxed max-w-xl"
            >
              Automate order intake from TikTok Shop or Google Sheets, verify inventory on Amazon, handle checkout automation, and get human approval—all in one platform.
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
                href="/dashboard"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.1, duration: 0.5, ease: "easeOut" }}
                whileHover={{ scale: 1.03, y: -2 }}
                whileTap={{ scale: 0.97 }}
                className="inline-flex items-center gap-2 px-7 py-3.5 text-sm font-semibold text-white bg-luxury-charcoal hover:bg-luxury-charcoal-light rounded-lg transition-colors duration-200 shadow-lg shadow-luxury-charcoal/20 hover:shadow-xl hover:shadow-luxury-charcoal/30"
              >
                Go to Dashboard
                <motion.span
                  animate={{ x: [0, 4, 0] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                >
                  →
                </motion.span>
              </motion.a>

              <motion.a
                href="#how-it-works"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.2, duration: 0.5, ease: "easeOut" }}
                whileHover={{ scale: 1.03, y: -2 }}
                whileTap={{ scale: 0.97 }}
                className="inline-flex items-center gap-2 px-6 py-3.5 text-sm font-semibold text-luxury-charcoal border-2 border-luxury-charcoal/20 hover:border-luxury-charcoal/40 hover:bg-luxury-charcoal/5 rounded-lg transition-colors duration-200"
              >
                Learn More
              </motion.a>
            </motion.div>

            {/* Footer note */}
            <motion.p variants={item} className="mt-6 text-sm text-gray-500">
              Modern e-commerce fulfillment made simple
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
