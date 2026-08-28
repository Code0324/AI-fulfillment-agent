import type { Metadata } from "next";
import Link from "next/link";
import { Bot, Shield, Zap, Users } from "lucide-react";

export const metadata: Metadata = {
  title: "About – AmazonFTE",
  description: "Learn about AmazonFTE and our mission to automate Amazon order fulfillment.",
};

const values = [
  { icon: Bot, title: "AI-First", description: "We believe AI can handle the repetitive work of order fulfillment better, faster, and cheaper than manual processes." },
  { icon: Shield, title: "Trust & Safety", description: "Every action we take follows Amazon seller policies. Your account safety is our top priority." },
  { icon: Zap, title: "Speed", description: "From order detection to fulfillment, our automation runs in seconds — not hours." },
  { icon: Users, title: "Seller-Centric", description: "Built by Amazon sellers, for Amazon sellers. We understand the challenges because we've lived them." },
];

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-100">
        <div className="section-container py-6">
          <Link href="/" className="text-sm text-gray-500 hover:text-brand-blue transition-colors">
            ← Back to Home
          </Link>
        </div>
      </div>
      <div className="section-container py-16">
        <div className="max-w-3xl mx-auto text-center mb-16">
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">
            About <span className="text-brand-blue">AmazonFTE</span>
          </h1>
          <p className="mt-6 text-lg text-gray-600 leading-relaxed">
            AmazonFTE was built to solve a simple problem: Amazon order fulfillment is repetitive, 
            error-prone, and time-consuming. Our AI-powered platform automates the entire workflow — 
            from order detection to supplier checkout — so sellers can focus on growing their business.
          </p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
          {values.map(({ icon: Icon, title, description }) => (
            <div key={title} className="bg-white rounded-2xl border border-gray-100 p-6 shadow-card hover:shadow-card-hover transition-all duration-300">
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center mb-4">
                <Icon className="w-6 h-6 text-brand-blue" />
              </div>
              <h3 className="text-lg font-bold text-gray-900 mb-2">{title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
