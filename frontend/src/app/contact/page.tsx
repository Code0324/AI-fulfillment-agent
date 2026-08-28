"use client";

import { useState } from "react";
import Link from "next/link";
import { Send, Mail, MessageSquare, MapPin } from "lucide-react";

export default function ContactPage() {
  const [submitted, setSubmitted] = useState(false);

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
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">
              Get in <span className="text-brand-blue">Touch</span>
            </h1>
            <p className="mt-4 text-lg text-gray-600">
              Have a question or want to learn more? We&apos;d love to hear from you.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="space-y-6">
              <div className="flex items-start gap-3 p-4 bg-white rounded-xl border border-gray-100 shadow-card">
                <Mail className="w-5 h-5 text-brand-blue mt-0.5" />
                <div>
                  <p className="text-sm font-bold text-gray-900">Email</p>
                  <p className="text-sm text-gray-600">support@amazonfte.com</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-white rounded-xl border border-gray-100 shadow-card">
                <MessageSquare className="w-5 h-5 text-brand-blue mt-0.5" />
                <div>
                  <p className="text-sm font-bold text-gray-900">Live Chat</p>
                  <p className="text-sm text-gray-600">Available Mon-Fri, 9am-6pm EST</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-white rounded-xl border border-gray-100 shadow-card">
                <MapPin className="w-5 h-5 text-brand-blue mt-0.5" />
                <div>
                  <p className="text-sm font-bold text-gray-900">Office</p>
                  <p className="text-sm text-gray-600">San Francisco, CA</p>
                </div>
              </div>
            </div>
            <div className="md:col-span-2">
              {submitted ? (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-12 text-center">
                  <div className="w-16 h-16 rounded-full bg-green-50 flex items-center justify-center mx-auto mb-4">
                    <Send className="w-8 h-8 text-green-500" />
                  </div>
                  <h3 className="text-xl font-bold text-gray-900 mb-2">Message Sent!</h3>
                  <p className="text-gray-600">We&apos;ll get back to you within 24 hours.</p>
                </div>
              ) : (
                <form
                  onSubmit={(e) => { e.preventDefault(); setSubmitted(true); }}
                  className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 space-y-5"
                >
                  <div className="grid sm:grid-cols-2 gap-5">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">Name</label>
                      <input type="text" required className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent" placeholder="Your name" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
                      <input type="email" required className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent" placeholder="you@company.com" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Subject</label>
                    <input type="text" required className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent" placeholder="How can we help?" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Message</label>
                    <textarea rows={5} required className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent resize-none" placeholder="Tell us more..." />
                  </div>
                  <button type="submit" className="inline-flex items-center gap-2 px-6 py-3 text-sm font-semibold text-white bg-brand-blue hover:bg-brand-blue-dark rounded-xl transition-all duration-200 shadow-md hover:shadow-lg">
                    <Send className="w-4 h-4" />
                    Send Message
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
