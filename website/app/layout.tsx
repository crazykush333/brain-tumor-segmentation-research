import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Footer, Nav } from "@/components/Nav";
import { status } from "@/lib/data";

export const metadata: Metadata = {
  title: {
    default: status.project.short_title,
    template: `%s | ${status.project.short_title}`,
  },
  description: `${status.project.type}. ${status.headline}`,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="mx-auto max-w-5xl px-4 py-10">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
