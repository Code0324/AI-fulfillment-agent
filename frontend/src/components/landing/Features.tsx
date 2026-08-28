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
    title: "Smart Order Processing",
    description:
      "Automatically detect, validate, and process Amazon orders with AI-powered intelligence. Zero manual input required.",
    color: "blue",
  },
  {
    icon: Warehouse,
    title: "Inventory Management",
    description:
      "Real-time inventory tracking across suppliers. Auto-reserve stock and prevent overselling before it happens.",
    color: "purple",
  },
  {
    icon: MapPin,
    title: "AI Address Processing",
    description:
      "Intelligent address validation, standardization, and verification ensures every package reaches the right doorstep.",
    color: "orange",
  },
  {
    icon: Truck,
    title: "Supplier Automation",
    description:
      "Automated supplier checkout with smart routing. AI selects the best supplier for every order based on speed, cost, and reliability.",
    color: "green",
  },
  {
    icon: ShieldCheck,
    title: "Policy Safe Workflow",
    description:
      "Built-in compliance checks ensure every action follows Amazon seller policies. Stay safe while scaling.",
    color: "emerald",
  },
  {
    icon: BarChart3,
    title: "Live Tracking & Analytics",
    description:
      "Real-time dashboards, order tracking, and performance analytics to monitor your fulfillment operations 24/7.",
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
    <section id="features" className="py-20 lg:py-28 bg-gray-50/50">
      <div className="section-container">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center max-w-2xl mx-auto mb-16"
        >
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-blue-50 border border-blue-100 text-sm font-semibold text-brand-blue mb-4">
            ✨ Features
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight">
            Everything You Need to{" "}
            <span className="text-brand-blue">Automate Fulfillment</span>
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            Powerful AI-driven tools that handle your entire Amazon fulfillment
            workflow — from order to delivery.
          </p>
        </motion.div>

        {/* Grid */}
        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-50px" }}
          className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6"
        >
          {features.map((feature) => {
            const colors = colorMap[feature.color];
            return (
              <motion.div
                key={feature.title}
                variants={item}
                className="group relative p-6 rounded-2xl bg-white border border-gray-100 hover:border-gray-200 shadow-card hover:shadow-card-hover transition-all duration-300 hover:-translate-y-1"
              >
                <div
                  className={`inline-flex items-center justify-center w-12 h-12 rounded-xl ${colors.bg} ring-1 ${colors.ring} mb-4 group-hover:scale-110 transition-transform duration-200`}
                >
                  <feature.icon className={`w-6 h-6 ${colors.icon}`} />
                </div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">
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
