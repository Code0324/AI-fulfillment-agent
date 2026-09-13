"use client";

import { motion } from "framer-motion";
import { Trophy } from "lucide-react";

export default function BottomCTA() {
  return (
    <section id="cta" className="py-16 lg:py-20">
      <div className="section-container">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="relative rounded-xl bg-luxury-charcoal p-10 lg:p-16 overflow-hidden"
        >
          {/* Background subtle gradient */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-luxury-gold/5 rounded-full -translate-y-1/2 translate-x-1/2 pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-luxury-gold/5 rounded-full translate-y-1/2 -translate-x-1/2 pointer-events-none" />

          <div className="relative z-10 flex flex-col lg:flex-row items-center justify-between gap-8">
            {/* Left */}
            <div className="text-center lg:text-left">
              <h2 className="text-3xl sm:text-4xl font-serif font-bold text-white tracking-tight leading-tight">
                Ready to Get Started?
              </h2>
              <p className="mt-4 text-lg text-gray-300 max-w-xl">
                Access the Fulfillment Platform dashboard and start automating your orders.
              </p>
              <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 mt-8">
                <a
                  href="/dashboard"
                  className="inline-flex items-center gap-2 px-7 py-3.5 text-sm font-semibold text-luxury-charcoal bg-luxury-gold hover:bg-luxury-gold-dark rounded-lg transition-all duration-200 shadow-lg hover:shadow-xl hover:-translate-y-0.5"
                >
                  Go to Dashboard
                  <span>→</span>
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
              <div className="flex flex-col items-center p-6 rounded-xl bg-luxury-gold/10 border border-luxury-gold/20">
                <div className="w-14 h-14 rounded-lg bg-luxury-gold/20 flex items-center justify-center mb-3">
                  <Trophy className="w-7 h-7 text-luxury-gold" />
                </div>
                <p className="text-sm font-semibold text-white text-center leading-snug max-w-[180px]">
                  Streamline Your Fulfillment Workflow
                </p>
              </div>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
