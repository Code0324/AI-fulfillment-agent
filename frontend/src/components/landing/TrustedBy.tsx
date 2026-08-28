"use client";

import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";

const techLogos = [
  { name: "Amazon Seller Central", abbr: "ASC" },
  { name: "OpenAI", abbr: "OAI" },
  { name: "FastAPI", abbr: "FAPI" },
  { name: "Next.js", abbr: "NJS" },
  { name: "PostgreSQL", abbr: "PG" },
  { name: "Docker", abbr: "DKR" },
  { name: "AWS", abbr: "AWS" },
  { name: "Oracle Cloud", abbr: "OC" },
];

export default function TrustedBy() {
  return (
    <section id="integrations" className="py-12 bg-white border-y border-gray-100">
      <div className="section-container">
        <div className="flex flex-col md:flex-row items-center justify-between gap-8">
          {/* Left: Label + Logos */}
          <div className="flex flex-col sm:flex-row items-center gap-6">
            <span className="text-sm font-semibold text-gray-500 whitespace-nowrap">
              Trusted & Powered By
            </span>
            <div className="flex flex-wrap items-center justify-center gap-4">
              {techLogos.map((tech, i) => (
                <motion.div
                  key={tech.name}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05, duration: 0.3 }}
                  className="group relative"
                >
                  <div className="w-16 h-10 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center hover:border-brand-blue/30 hover:bg-blue-50/50 transition-all duration-200">
                    <span className="text-xs font-bold text-gray-400 group-hover:text-brand-blue transition-colors">
                      {tech.abbr}
                    </span>
                  </div>
                  <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[9px] text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                    {tech.name}
                  </span>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Right: Security Badge */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="flex items-center gap-3 px-5 py-3 rounded-xl bg-green-50 border border-green-200"
          >
            <ShieldCheck className="w-6 h-6 text-green-600 flex-shrink-0" />
            <div>
              <p className="text-sm font-bold text-green-800">
                Enterprise Grade Security
              </p>
              <p className="text-xs text-green-600">
                Your data is safe with us
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
