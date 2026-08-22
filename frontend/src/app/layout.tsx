import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Amazon AI Fulfillment Assistant",
  description: "AI-powered order fulfillment workspace for Amazon sellers",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
