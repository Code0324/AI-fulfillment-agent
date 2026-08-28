import type { Metadata } from "next";
import LandingPage from "@/components/LandingPage";

export const metadata: Metadata = {
  title: "AmazonFTE – AI Amazon Order Fulfillment Automation",
  description:
    "Automate your Amazon order fulfillment with AI. Smart sourcing, address handling, supplier checkout, and order tracking — safely, smartly, and at scale.",
  keywords: [
    "Amazon automation",
    "AI fulfillment",
    "Amazon seller tools",
    "order fulfillment automation",
    "Amazon FTE",
    "ecommerce automation",
  ],
  openGraph: {
    title: "AmazonFTE – AI Amazon Order Fulfillment Automation",
    description:
      "Your 24/7 AI Employee for Amazon Order Fulfillment. Automate product sourcing, address handling, supplier checkout and order fulfillment.",
    type: "website",
    siteName: "AmazonFTE",
  },
  twitter: {
    card: "summary_large_image",
    title: "AmazonFTE – AI Amazon Order Fulfillment Automation",
    description:
      "Your 24/7 AI Employee for Amazon Order Fulfillment.",
  },
};

export default function LandingPageRoute() {
  return <LandingPage />;
}
