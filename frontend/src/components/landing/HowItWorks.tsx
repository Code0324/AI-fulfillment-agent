"use client";

import { motion } from "framer-motion";
import {
  Package,
  Search,
  CreditCard,
  Truck,
  CheckCircle2,
  TrendingUp,
  DollarSign,
  Clock,
  Heart,
  BarChart3,
} from "lucide-react";

const steps = [
  {
    num: 1,
    icon: Package,
    title: "Amazon Order Received",
    description:
      "AI automatically detects new orders from your Amazon Seller Central account in real-time.",
  },
  {
    num: 2,
    icon: Search,
    title: "Inventory & Address Check",
    description:
      "Verifies inventory availability across suppliers and validates customer shipping addresses instantly.",
  },
  {
    num: 3,
    icon: CreditCard,
    title: "Auto Supplier Checkout",
    description:
      "Automatically places orders with the optimal supplier based on price, speed, and reliability scores.",
  },
  {
    num: 4,
    icon: Truck,
    title: "Tracking & Sync",
    description:
      "Syncs tracking information back to Amazon and updates the customer — fully automated, zero manual steps.",
  },
  {
    num: 5,
    icon: CheckCircle2,
    title: "Order Fulfilled",
    description:
      "Order is marked complete. Your customer is happy, and you didn't have to touch a single button.",
  },
];

const benefits = [
  { icon: TrendingUp, text: "More time for business growth" },
  { icon: DollarSign, text: "Lower operational costs" },
  { icon: Clock, text: "Faster order fulfillment" },
  { icon: Heart, text: "Happier customers" },
];

const barData = [65, 80, 55, 90, 70, 85, 95];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="py-20 lg:py-28 bg-white">
      <div className="section-container">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center max-w-2xl mx-auto mb-16"
        >
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-orange-50 border border-orange-100 text-sm font-semibold text-brand-orange mb-4">
            🤖 Process
          </span>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 tracking-tight">
            How AmazonFTE Works?
          </h2>
          <p className="mt-4 text-lg text-gray-600">
            From Order to Fulfillment — Fully Automated
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-5 gap-10 lg:gap-8 items-start">
          {/* Steps (5 columns on lg) */}
          <div className="lg:col-span-3 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {steps.map((step, i) => (
              <motion.div
                key={step.num}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.4 }}
                className="relative p-5 rounded-2xl border border-gray-100 bg-white shadow-card hover:shadow-card-hover transition-all duration-300 hover:-translate-y-1"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-brand-blue text-white text-sm font-bold">
                    {step.num}
                  </div>
                  <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                    <step.icon className="w-4 h-4 text-brand-blue" />
                  </div>
                </div>
                <h4 className="text-sm font-bold text-gray-900 mb-1.5">
                  {step.title}
                </h4>
                <p className="text-xs text-gray-600 leading-relaxed">
                  {step.description}
                </p>
              </motion.div>
            ))}
          </div>

          {/* Right: Benefits Card */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="lg:col-span-2"
          >
            <div className="rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 p-6 shadow-card sticky top-28">
              <h3 className="text-lg font-bold text-gray-900 mb-1">
                Let AI Handle the Repetitive Work
              </h3>
              <p className="text-sm text-gray-600 mb-6">
                Focus on growing your business while AI handles fulfillment.
              </p>

              <div className="space-y-3 mb-6">
                {benefits.map(({ icon: Icon, text }) => (
                  <div
                    key={text}
                    className="flex items-center gap-3 p-3 rounded-xl bg-white/80 border border-white"
                  >
                    <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-green-50">
                      <CheckCircle2 className="w-4 h-4 text-green-600" />
                    </div>
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4 text-brand-blue" />
                      <span className="text-sm font-medium text-gray-700">
                        {text}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Mini bar chart */}
              <div className="rounded-xl bg-white/80 border border-white p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold text-gray-700">
                    Efficiency Gain
                  </span>
                  <BarChart3 className="w-4 h-4 text-brand-blue" />
                </div>
                <div className="flex items-end gap-1.5 h-20">
                  {barData.map((h, i) => (
                    <motion.div
                      key={i}
                      initial={{ height: 0 }}
                      whileInView={{ height: `${h}%` }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.5 + i * 0.05, duration: 0.5 }}
                      className="flex-1 rounded-t bg-gradient-to-t from-brand-green to-green-400"
                    />
                  ))}
                </div>
                <div className="flex justify-between mt-2">
                  <span className="text-[9px] text-gray-400">Mon</span>
                  <span className="text-[9px] text-gray-400">Sun</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
