import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "APIx · India Airfare Observatory",
  description:
    "A transparent research prototype for tracking Indian domestic airfare prices.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
