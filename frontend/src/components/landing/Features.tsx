"use client";

import { motion } from "framer-motion";
import {
  ShoppingCart,
  Warehouse,
  MapPin,
  Truck,
  ShieldCheck,
  BarChart3,
} from "lucide-react";

const features = [
  {
    icon: ShoppingCart,
    title: "Amazon Checkout Automation",
    description:
      "Automatically search products by SKU, fill shipping details and gift options, and reach the order summary on Amazon—no manual shopping required.",
    color: "blue",
  },
  {
    icon: ShieldCheck,
    title: "Human Approval Gate",
    description:
      "Nothing purchases without your explicit approval. Review all orders in the Fulfillment dashboard before any purchase is made.",
    color: "emerald",
  },
  {
    icon: BarChart3,
    title: "Google Sheet Sync",
    description:
      "Incoming orders sync directly to your Google Sheet, and results (order confirmations, tracking, delivery dates) sync back automatically.",
    color: "sky",
  },
];

const colorMap: Record<string, { bg: string; icon: string; ring: string }> = {
  blue: { bg: "bg-blue-50", icon: "text-blue-600", ring: "ring-blue-500/10" },
  purple: { bg: "bg-purple-50", icon: "text-purple-600", ring: "ring-purple-500/10" },
  orange: { bg: "bg-orange-50", icon: "text-orange-600", ring: "ring-orange-500/10" },
  green: { bg: "bg-green-50", icon: "text-green-600", ring: "ring-green-500/10" },
  emerald: { bg: "bg-emerald-50", icon: "text-emerald-600", ring: "ring-emerald-500/10" },
  sky: { bg: "bg-sky-50", icon: "text-sky-600", ring: "ring-sky-500/10" },
};

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

export default function Features() {
  return (
    <section id="features" className="py-20 lg:py-28 bg-luxury-cream">
      <div className="section-container">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center max-w-2xl mx-auto mb-16"
        >
          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-luxury-gold/10 border border-luxury-gold/20 text-sm font-semibold text-luxury-charcoal mb-4">
            ✨ Core Features
          </span>
          <h2 className="text-3xl sm:text-4xl font-serif font-bold text-luxury-charcoal tracking-tight">
            Built for Real Fulfillment
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Three powerful capabilities that automate your entire workflow.
          </p>
        </motion.div>

        {/* Grid */}
        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-50px" }}
          className="grid sm:grid-cols-2 lg:grid-cols-3 gap-8"
        >
          {features.map((feature) => {
            const colors = colorMap[feature.color];
            return (
              <motion.div
                key={feature.title}
                variants={item}
                className="group relative p-7 rounded-lg bg-white border border-gray-100 shadow-subtle hover:shadow-card transition-all duration-300 hover:-translate-y-1"
              >
                <div
                  className={`inline-flex items-center justify-center w-14 h-14 rounded-lg ${colors.bg} ring-1 ${colors.ring} mb-5 group-hover:scale-110 transition-transform duration-200`}
                >
                  <feature.icon className={`w-6 h-6 ${colors.icon}`} />
                </div>
                <h3 className="text-lg font-semibold text-luxury-charcoal mb-3">
                  {feature.title}
                </h3>
                <p className="text-sm text-gray-600 leading-relaxed">
                  {feature.description}
                </p>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
