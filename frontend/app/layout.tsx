import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "Imperium Dynamics · AI Interview Evaluation",
  description: "Hiring Manager Review & Candidate Intake Suite",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ minHeight: "100vh", background: "var(--bg)" }}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
