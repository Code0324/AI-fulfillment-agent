import type { Metadata } from "next";
import Link from "next/link";
import { Check } from "lucide-react";

export const metadata: Metadata = {
  title: "Pricing – AmazonFTE",
  description: "Simple, transparent pricing for AmazonFTE AI Fulfillment Automation.",
};

const plans = [
  {
    name: "Starter",
    price: "$49",
    period: "/month",
    description: "Perfect for small Amazon sellers getting started with automation.",
    features: [
      "Up to 100 orders/month",
      "Basic inventory tracking",
      "Address validation",
      "Email support",
      "1 user seat",
    ],
    cta: "Start Free Trial",
    href: "/register",
    highlight: false,
  },
  {
    name: "Professional",
    price: "$149",
    period: "/month",
    description: "For growing sellers who need full automation and analytics.",
    features: [
      "Up to 1,000 orders/month",
      "Smart inventory management",
      "AI address processing",
      "Automated fulfillment workflow",
      "Priority support",
      "5 user seats",
      "Advanced analytics",
    ],
    cta: "Start Free Trial",
    href: "/register",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For large operations needing unlimited scale and dedicated support.",
    features: [
      "Unlimited orders",
      "Multi-marketplace support",
      "Custom integrations",
      "Dedicated account manager",
      "SLA guarantee",
      "Unlimited users",
      "API access",
    ],
    cta: "Contact Sales",
    href: "/contact",
    highlight: false,
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-100">
        <div className="section-container py-6">
          <Link href="/" className="text-sm text-gray-500 hover:text-brand-blue transition-colors">
            ← Back to Home
          </Link>
        </div>
      </div>

      <div className="section-container py-16">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">
            Simple, Transparent <span className="text-brand-blue">Pricing</span>
          </h1>
          <p className="mt-4 text-lg text-gray-600">
            Start free, upgrade when you&apos;re ready. No hidden fees.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-2xl p-8 ${
                plan.highlight
                  ? "bg-white border-2 border-brand-blue shadow-lg ring-1 ring-brand-blue/10"
                  : "bg-white border border-gray-200 shadow-card"
              }`}
            >
              {plan.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-brand-blue text-xs font-bold text-white">
                  Most Popular
                </div>
              )}
              <h3 className="text-lg font-bold text-gray-900">{plan.name}</h3>
              <div className="mt-3 flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-gray-900">{plan.price}</span>
                {plan.period && <span className="text-gray-500">{plan.period}</span>}
              </div>
              <p className="mt-3 text-sm text-gray-600">{plan.description}</p>
              <ul className="mt-6 space-y-3">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-gray-700">
                    <Check className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href={plan.href}
                className={`mt-8 block w-full text-center py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
                  plan.highlight
                    ? "bg-brand-blue text-white hover:bg-brand-blue-dark shadow-md hover:shadow-lg"
                    : "bg-gray-100 text-gray-800 hover:bg-gray-200"
                }`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
