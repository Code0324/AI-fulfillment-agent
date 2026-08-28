"use client";

import { motion } from "framer-motion";
import { Lottie } from "lottie-react";
import robotAnimation from "@/../public/lottie/robot.json";
import {
  ShoppingCart,
  Package,
  CheckCircle2,
  Zap,
  DollarSign,
  TrendingUp,
  Bot,
  Activity,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/* Animated chart bars                                                         */
/* -------------------------------------------------------------------------- */

const chartBars = [35, 55, 42, 70, 48, 82, 65, 90, 58, 75, 62, 85];

/* -------------------------------------------------------------------------- */
/* Recent orders for the mini-table                                            */
/* -------------------------------------------------------------------------- */

const miniOrders = [
  { asin: "B09V3KXJPB", name: "Wireless Charger", price: "$29.99", status: "fulfilled" },
  { asin: "B0D5CDJCR2", name: "USB-C Hub 7-in-1", price: "$45.99", status: "fulfilled" },
  { asin: "B0CWYQZ3HQ", name: "Laptop Stand", price: "$34.99", status: "processing" },
];

/* -------------------------------------------------------------------------- */
/* Checklist items for the floating card                                       */
/* -------------------------------------------------------------------------- */

const checklistItems = [
  { label: "Order Received", done: true },
  { label: "Inventory Reserved", done: true },
  { label: "Address Verified", done: true },
  { label: "Supplier Checkout", done: false },
  { label: "Tracking Updated", done: false },
];

/* -------------------------------------------------------------------------- */
/* Main HeroIllustration component                                             */
/* -------------------------------------------------------------------------- */

export default function HeroIllustration() {
  return (
    <div className="relative w-full max-w-[580px] mx-auto" style={{ perspective: "1200px" }}>
      {/* Radial glow behind everything */}
      <div className="absolute inset-0 -m-16 bg-gradient-radial from-brand-blue/8 via-brand-blue/3 to-transparent rounded-full blur-3xl pointer-events-none" />

      {/* ============ MAIN DASHBOARD CARD ============ */}
      <motion.div
        initial={{ opacity: 0, y: 30, rotateX: 4, rotateY: -2 }}
        animate={{ opacity: 1, y: 0, rotateX: 0, rotateY: 0 }}
        transition={{ duration: 0.9, ease: "easeOut", delay: 0.2 }}
        className="relative z-10 bg-white rounded-2xl shadow-float border border-gray-200/80 overflow-hidden"
      >
        {/* Browser chrome top bar */}
        <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 border-b border-gray-100">
          <div className="flex gap-1.5">
            <span className="w-3 h-3 rounded-full bg-red-400" />
            <span className="w-3 h-3 rounded-full bg-yellow-400" />
            <span className="w-3 h-3 rounded-full bg-green-400" />
          </div>
          <div className="flex-1 flex justify-center">
            <div className="px-4 py-1 rounded-lg bg-white border border-gray-200 text-[10px] text-gray-400 font-mono">
              app.amazonfte.com/dashboard
            </div>
          </div>
          <div className="w-14" />
        </div>

        {/* Dashboard content */}
        <div className="p-4 space-y-3">
          {/* Top stat cards row */}
          <div className="grid grid-cols-4 gap-2">
            <StatCard
              icon={ShoppingCart}
              label="Total Orders"
              value="1,284"
              change="+12%"
              up
              iconBg="bg-blue-50"
              iconColor="text-brand-blue"
            />
            <StatCard
              icon={Package}
              label="Auto Fulfilled"
              value="1,156"
              change="90%"
              up
              iconBg="bg-green-50"
              iconColor="text-green-600"
            />
            <StatCard
              icon={TrendingUp}
              label="Pending"
              value="32"
              change="2.5%"
              up={false}
              iconBg="bg-orange-50"
              iconColor="text-orange-500"
            />
            <StatCard
              icon={DollarSign}
              label="Saved"
              value="$8,540"
              change=""
              up
              iconBg="bg-purple-50"
              iconColor="text-purple-600"
            />
          </div>

          {/* Chart + Orders row */}
          <div className="grid grid-cols-5 gap-2">
            {/* Chart area */}
            <div className="col-span-3 bg-gray-50 rounded-xl border border-gray-100 p-3">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-semibold text-gray-600">
                  Order Fulfillment Activity
                </span>
                <span className="flex items-center gap-1 text-[9px] font-semibold text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                  <Activity className="w-2.5 h-2.5" />
                  Live Processing…
                </span>
              </div>
              {/* Animated bars */}
              <div className="flex items-end gap-[3px] h-16">
                {chartBars.map((h, i) => (
                  <motion.div
                    key={i}
                    initial={{ height: 0 }}
                    animate={{ height: `${h}%` }}
                    transition={{ duration: 0.6, delay: 0.5 + i * 0.05, ease: "easeOut" }}
                    className={`flex-1 rounded-t-sm ${
                      i === chartBars.length - 1 || i === chartBars.length - 3
                        ? "bg-brand-blue"
                        : "bg-brand-blue/60"
                    }`}
                  />
                ))}
              </div>
              <div className="flex justify-between mt-1">
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"].map(
                  (d, i) => (
                    <span key={i} className="text-[7px] text-gray-400">
                      {d}
                    </span>
                  )
                )}
              </div>
            </div>

            {/* Mini orders list */}
            <div className="col-span-2 bg-gray-50 rounded-xl border border-gray-100 p-3">
              <span className="text-[10px] font-semibold text-gray-600 block mb-2">
                Recent Orders
              </span>
              <div className="space-y-1.5">
                {miniOrders.map((order) => (
                  <div
                    key={order.asin}
                    className="flex items-center gap-2 p-1.5 rounded-lg bg-white border border-gray-100"
                  >
                    <div className="w-6 h-6 rounded bg-orange-50 flex items-center justify-center flex-shrink-0">
                      <ShoppingCart className="w-3 h-3 text-brand-orange" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[9px] font-medium text-gray-800 truncate">
                        {order.name}
                      </p>
                      <p className="text-[8px] text-gray-400 font-mono">{order.asin}</p>
                    </div>
                    <span className="text-[8px] font-bold text-gray-700">{order.price}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* ============ FLOATING CHECKLIST CARD ============ */}
      <motion.div
        initial={{ opacity: 0, x: -30, y: 20 }}
        animate={{ opacity: 1, x: 0, y: 0 }}
        transition={{ delay: 1.0, duration: 0.6, ease: "easeOut" }}
        className="absolute -left-4 bottom-12 z-30 hidden xl:block"
      >
        <div className="bg-white/90 backdrop-blur-xl rounded-xl shadow-lg border border-gray-200/80 p-3 w-48">
          <div className="flex items-center gap-1.5 mb-2">
            <span className="w-5 h-5 rounded-md bg-brand-blue/10 flex items-center justify-center">
              <Zap className="w-3 h-3 text-brand-blue" />
            </span>
            <span className="text-[10px] font-bold text-gray-800">Auto Processing…</span>
          </div>
          <div className="space-y-1.5">
            {checklistItems.map((item) => (
              <div key={item.label} className="flex items-center gap-1.5">
                {item.done ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                ) : (
                  <span className="w-3.5 h-3.5 rounded-full border-2 border-gray-200 flex-shrink-0" />
                )}
                <span
                  className={`text-[9px] font-medium ${
                    item.done ? "text-gray-700" : "text-gray-400"
                  }`}
                >
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* ============ FLOATING "Working 24/7" BADGE ============ */}
      <motion.div
        initial={{ opacity: 0, scale: 0.8, y: -10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ delay: 1.2, duration: 0.5 }}
        className="absolute -top-3 -right-3 z-30"
      >
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white/90 backdrop-blur-xl rounded-full shadow-lg border border-gray-200/80">
          <Bot className="w-3.5 h-3.5 text-brand-blue" />
          <span className="text-[10px] font-bold text-gray-700 whitespace-nowrap">
            Working for you ⚡ 24/7
          </span>
        </div>
      </motion.div>

      {/* ============ ROBOT CHARACTER (Lottie) ============ */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6, duration: 0.7, ease: "easeOut" }}
        className="absolute -bottom-12 right-0 z-20 hidden lg:block w-32 h-32"
      >
        <LottieRobot />
      </motion.div>

      {/* ============ FLOATING PACKAGE BOXES ============ */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 1.4, duration: 0.5 }}
        className="absolute -bottom-2 left-6 z-20 hidden lg:block"
      >
        <ConveyorBoxes />
      </motion.div>

      {/* ============ FLOATING CONNECTOR DOTS ============ */}
      <FloatingDots />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Stat Card (tiny)                                                           */
/* -------------------------------------------------------------------------- */

function StatCard({
  icon: Icon,
  label,
  value,
  change,
  up,
  iconBg,
  iconColor,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  change: string;
  up: boolean;
  iconBg: string;
  iconColor: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-100 p-2 hover:shadow-sm transition-shadow">
      <div className="flex items-center gap-1.5 mb-1">
        <div className={`w-5 h-5 rounded-md ${iconBg} flex items-center justify-center`}>
          <Icon className={`w-2.5 h-2.5 ${iconColor}`} />
        </div>
        {change && (
          <span
            className={`text-[8px] font-bold ${up ? "text-green-600" : "text-red-500"}`}
          >
            {change}
          </span>
        )}
      </div>
      <p className="text-sm font-extrabold text-gray-900 leading-tight">{value}</p>
      <p className="text-[8px] text-gray-500 font-medium">{label}</p>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Robot Character — Lottie animated                                           */
/* -------------------------------------------------------------------------- */

function LottieRobot() {
  return (
    <motion.div
      animate={{ y: [0, -6, 0] }}
      transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      className="relative w-full h-full"
    >
      <Lottie
        src={robotAnimation}
        loop
        autoplay
        className="w-full h-full"
        style={{ filter: "drop-shadow(0 8px 24px rgba(37, 99, 235, 0.15))" }}
      />
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/* Conveyor Boxes — animated                                                   */
/* -------------------------------------------------------------------------- */

function ConveyorBoxes() {
  const boxes = [
    { size: 14, opacity: 0.35 },
    { size: 16, opacity: 0.5 },
    { size: 18, opacity: 0.7 },
    { size: 20, opacity: 0.85 },
  ];

  return (
    <div className="flex items-end gap-1.5">
      {boxes.map((box, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: box.opacity, x: 0 }}
          transition={{ delay: 1.5 + i * 0.1, duration: 0.3 }}
          className="rounded-md bg-brand-orange flex items-center justify-center"
          style={{ width: box.size, height: box.size }}
        >
          <span className="text-white text-[6px] font-bold">a</span>
        </motion.div>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Floating decorative dots                                                    */
/* -------------------------------------------------------------------------- */

function FloatingDots() {
  const dots = [
    { top: "8%", left: "92%", size: 6, color: "bg-brand-orange/30", delay: 0.8 },
    { top: "25%", left: "98%", size: 4, color: "bg-brand-blue/20", delay: 1.0 },
    { top: "70%", left: "96%", size: 5, color: "bg-brand-orange/20", delay: 1.2 },
    { top: "45%", left: "100%", size: 3, color: "bg-brand-blue/30", delay: 1.4 },
    { top: "85%", left: "88%", size: 4, color: "bg-green-400/25", delay: 0.9 },
  ];

  return (
    <>
      {dots.map((dot, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: dot.delay, duration: 0.4 }}
          className={`absolute rounded-full ${dot.color} pointer-events-none`}
          style={{
            top: dot.top,
            left: dot.left,
            width: dot.size,
            height: dot.size,
          }}
        />
      ))}
    </>
  );
}
