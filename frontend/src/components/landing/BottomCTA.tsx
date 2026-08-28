"use client";

import { motion } from "framer-motion";
import { Trophy } from "lucide-react";

export default function BottomCTA() {
  return (
    <section id="pricing" className="py-16 lg:py-20">
      <div className="section-container">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="relative rounded-3xl bg-cta-gradient p-10 lg:p-14 overflow-hidden"
        >
          {/* Background decorations */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2 pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2 pointer-events-none" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-white/3 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10 flex flex-col lg:flex-row items-center justify-between gap-8">
            {/* Left */}
            <div className="text-center lg:text-left">
              <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
                Ready to Transform Your{" "}
                <br className="hidden sm:block" />
                Amazon Business?
              </h2>
              <p className="mt-4 text-lg text-blue-100 max-w-xl">
                Automate fulfillment. Save time. Scale faster.
              </p>
              <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 mt-8">
                <a
                  href="/demo"
                  className="inline-flex items-center gap-2 px-7 py-3.5 text-sm font-semibold text-brand-blue bg-white hover:bg-gray-50 rounded-xl transition-all duration-200 shadow-lg hover:shadow-xl hover:-translate-y-0.5"
                >
                  Start Free Demo
                  <span>→</span>
                </a>
                <a
                  href="/contact"
                  className="inline-flex items-center gap-2 px-6 py-3.5 text-sm font-semibold text-white border-2 border-white/30 hover:border-white hover:bg-white/10 rounded-xl transition-all duration-200"
                >
                  Contact Us
                </a>
              </div>
            </div>

            {/* Right: Badge */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3, duration: 0.5 }}
              className="flex-shrink-0"
            >
              <div className="flex flex-col items-center p-6 rounded-2xl bg-white/10 backdrop-blur-sm border border-white/20">
                <div className="w-14 h-14 rounded-2xl bg-white/15 flex items-center justify-center mb-3">
                  <Trophy className="w-7 h-7 text-yellow-400" />
                </div>
                <p className="text-sm font-bold text-white text-center leading-snug max-w-[180px]">
                  Become 10x More Efficient with AI Automation
                </p>
              </div>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
