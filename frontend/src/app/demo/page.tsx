'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ShoppingCart, Play, CheckCircle, ArrowRight, Zap, Bot, Package, MapPin } from 'lucide-react';

export default function DemoPage() {
  const [orderUrl, setOrderUrl] = useState('');
  const [processing, setProcessing] = useState(false);
  const [completed, setCompleted] = useState(false);

  const handleProcess = (e: React.FormEvent) => {
    e.preventDefault();
    setProcessing(true);
    setTimeout(() => {
      setProcessing(false);
      setCompleted(true);
    }, 3000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center">
              <ShoppingCart className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-slate-900">AmazonFTE</span>
          </Link>
          <Link href="/" className="text-sm text-slate-600 hover:text-blue-600 font-medium">
            ← Back to Home
          </Link>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-12">
        {/* Title */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-blue-100 text-blue-700 px-4 py-2 rounded-full text-sm font-medium mb-4">
            <Play className="w-4 h-4" /> Interactive Demo
          </div>
          <h1 className="text-4xl font-bold text-slate-900 mb-4">
            Try AmazonFTE <span className="text-orange-500">Live</span>
          </h1>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Experience how our AI automates Amazon order fulfillment. Paste an order URL or use our sample data to see it in action.
          </p>
        </div>

        {/* Demo Form */}
        <div className="bg-white rounded-2xl shadow-xl p-8 border border-slate-100 mb-8">
          <h2 className="text-xl font-bold text-slate-900 mb-2">Order Fulfillment Sandbox</h2>
          <p className="text-xs text-slate-400 mb-6">
            This is a scripted, simulated walkthrough — no order is actually created. Try the{' '}
            <Link href="/dashboard/orders" className="text-blue-600 hover:text-blue-700 font-medium">
              live dashboard
            </Link>{' '}
            to process a real order against the backend.
          </p>

          {!completed ? (
            <form onSubmit={handleProcess} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Amazon Order URL or Order ID</label>
                <input
                  type="text"
                  value={orderUrl}
                  onChange={(e) => setOrderUrl(e.target.value)}
                  placeholder="e.g., https://amazon.com/dp/B08N5WRWNW or order #112-3456789-1234567"
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={processing}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition-all"
              >
                {processing ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Processing with AI...
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5" /> Run Fulfillment Simulation
                  </>
                )}
              </button>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3 bg-green-50 text-green-700 p-4 rounded-xl">
                <CheckCircle className="w-6 h-6 flex-shrink-0" />
                <div>
                  <p className="font-semibold">Simulated Run Complete</p>
                  <p className="text-sm">This is a scripted preview — no real order, reservation, or address check happened.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  { icon: Package, label: 'Inventory Reserved', desc: 'What this looks like once an order is placed' },
                  { icon: MapPin, label: 'Address Verified', desc: 'AI validation runs on real orders in the dashboard' },
                  { icon: Bot, label: 'Supplier Checkout', desc: 'Requires human approval before any real order' },
                ].map((step, i) => (
                  <div key={i} className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle className="w-5 h-5 text-green-500" />
                      <step.icon className="w-5 h-5 text-blue-600" />
                    </div>
                    <p className="font-semibold text-slate-900 text-sm">{step.label}</p>
                    <p className="text-xs text-slate-500 mt-1">{step.desc}</p>
                  </div>
                ))}
              </div>

              <button
                onClick={() => { setCompleted(false); setOrderUrl(''); }}
                className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-3 rounded-xl transition-all"
              >
                Try Another Order
              </button>
            </div>
          )}
        </div>

        {/* CTA */}
        <div className="text-center">
          <p className="text-slate-600 mb-4">Ready for production?</p>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-xl transition-all"
          >
            Go to Dashboard <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}
