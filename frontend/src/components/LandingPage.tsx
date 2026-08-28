"use client";

import { useState } from "react";
import Navbar from "@/components/landing/Navbar";
import Hero from "@/components/landing/Hero";
import TrustedBy from "@/components/landing/TrustedBy";
import Features from "@/components/landing/Features";
import HowItWorks from "@/components/landing/HowItWorks";
import BottomCTA from "@/components/landing/BottomCTA";
import Footer from "@/components/landing/Footer";
import VideoModal from "@/components/landing/VideoModal";

export default function LandingPage() {
  const [videoOpen, setVideoOpen] = useState(false);

  return (
    <div className="min-h-screen bg-white">
      {/* Hidden trigger for video modal (clicked from Hero) */}
      <button
        id="video-modal-trigger"
        className="hidden"
        onClick={() => setVideoOpen(true)}
        aria-hidden
      />

      <Navbar />
      <main>
        <Hero />
        <TrustedBy />
        <Features />
        <HowItWorks />
        <BottomCTA />
      </main>
      <Footer />
      <VideoModal isOpen={videoOpen} onClose={() => setVideoOpen(false)} />
    </div>
  );
}
