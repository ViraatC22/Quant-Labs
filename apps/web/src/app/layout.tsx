import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Trading Intelligence OS",
  description: "Local-first trading memory, research, and paper lab."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
