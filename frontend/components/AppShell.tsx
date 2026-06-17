"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { getSession, logout, AuthUser } from "@/lib/auth";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    setUser(getSession());
  }, [pathname]); // re-read on every navigation

  const isLoginPage = pathname === "/login";

  const handleLogout = () => {
    logout();
    setUser(null);
    router.replace("/login");
  };

  // On login page — render children only (no shell)
  if (isLoginPage) {
    return <>{children}</>;
  }

  const tabs = [
    { label: "📊 Reports", href: "/", roles: ["hr", "hm"] as const },
    { label: "➕ Add Candidate", href: "/intake", roles: ["hr"] as const },
    { label: "🏛️ Decisions", href: "/decisions", roles: ["hr", "hm"] as const },
  ];

  const visibleTabs = user
    ? tabs.filter((t) => (t.roles as readonly string[]).includes(user.role))
    : [];

  const roleLabel: Record<string, string> = {
    hr: "HR Officer",
    hm: "Hiring Manager",
  };

  return (
    <>
      <header style={{
        borderBottom: "1px solid rgba(139,92,246,0.2)",
        background: "rgba(10,10,18,0.95)",
        backdropFilter: "blur(12px)",
        padding: "0 32px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: 56,
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}>
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 6,
              background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 13, fontWeight: 900, color: "#fff",
            }}>
              ◆
            </div>
            <span style={{ fontWeight: 800, fontSize: 14, color: "#fff", letterSpacing: "0.04em", textTransform: "uppercase" }}>
              Imperium Dynamics
            </span>
          </div>

          {/* Nav tabs */}
          {user && (
            <nav style={{ display: "flex", gap: 2 }}>
              {visibleTabs.map((t) => {
                const active = t.href === "/" ? pathname === "/" : pathname.startsWith(t.href);
                return (
                  <Link key={t.href} href={t.href} style={{
                    padding: "5px 14px",
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 500,
                    textDecoration: "none",
                    color: active ? "#c4b5fd" : "rgba(255,255,255,0.45)",
                    background: active ? "rgba(124,58,237,0.15)" : "transparent",
                    border: `1px solid ${active ? "rgba(139,92,246,0.3)" : "transparent"}`,
                    transition: "all 0.15s",
                  }}>
                    {t.label}
                  </Link>
                );
              })}
            </nav>
          )}
        </div>

        {/* User info + logout */}
        {user && (
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>{user.name}</div>
              <div style={{ fontSize: 11, color: "rgba(139,92,246,0.8)", fontWeight: 500 }}>
                {roleLabel[user.role]}
              </div>
            </div>
            <div style={{
              width: 32, height: 32, borderRadius: "50%",
              background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 13, fontWeight: 700, color: "#fff",
            }}>
              {user.name[0].toUpperCase()}
            </div>
            <button
              onClick={handleLogout}
              style={{
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 6, color: "rgba(255,255,255,0.5)",
                fontSize: 12, padding: "5px 12px", cursor: "pointer",
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => {
                (e.target as HTMLButtonElement).style.color = "#fff";
                (e.target as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.25)";
              }}
              onMouseLeave={(e) => {
                (e.target as HTMLButtonElement).style.color = "rgba(255,255,255,0.5)";
                (e.target as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.1)";
              }}
            >
              Sign out
            </button>
          </div>
        )}
      </header>

      <main style={{ padding: "28px 32px", maxWidth: 1400, margin: "0 auto" }}>
        {children}
      </main>
    </>
  );
}
