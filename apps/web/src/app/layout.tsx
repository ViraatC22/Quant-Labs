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
  // Render the dark theme by default (this is a dark-first app). `ThemeToggle`
  // resolves the stored/system preference after mount and corrects the class if
  // needed. `suppressHydrationWarning` covers that post-mount adjustment.
  return (
    <html className="dark" lang="en" style={{ colorScheme: "dark" }} suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
