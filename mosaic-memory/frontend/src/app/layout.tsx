import type { Metadata } from "next";
import "./globals.css";

import { AppNav } from "@/components/app-nav";

export const metadata: Metadata = {
  title: {
    default: "Mosaic Memory",
    template: "%s · Mosaic Memory",
  },
  description: "A calm, private record of your digital activity.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AppNav />
        <main className="min-h-dvh lg:pl-[17rem]">
          <div className="mx-auto max-w-6xl px-5 py-9 sm:px-8 sm:py-12 lg:px-12">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
