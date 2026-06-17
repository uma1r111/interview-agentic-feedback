"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { login, getSession } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getSession()) router.replace("/");
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    await new Promise((r) => setTimeout(r, 400)); // subtle delay
    const user = login(email, password);
    if (!user) {
      setError("Invalid email or password.");
      setLoading(false);
      return;
    }
    router.replace("/");
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #0a0a12 0%, #0f0a1e 50%, #0a0a12 100%)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "'Inter', sans-serif",
      position: "relative",
      overflow: "hidden",
    }}>

      {/* Background grid */}
      <div style={{
        position: "absolute", inset: 0, opacity: 0.04,
        backgroundImage: "linear-gradient(#8b5cf6 1px, transparent 1px), linear-gradient(90deg, #8b5cf6 1px, transparent 1px)",
        backgroundSize: "60px 60px",
        pointerEvents: "none",
      }} />

      {/* Glow orbs */}
      <div style={{
        position: "absolute", width: 600, height: 600, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(124,58,237,0.15) 0%, transparent 70%)",
        top: "-200px", left: "-100px", pointerEvents: "none",
      }} />
      <div style={{
        position: "absolute", width: 400, height: 400, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(139,92,246,0.1) 0%, transparent 70%)",
        bottom: "-100px", right: "-50px", pointerEvents: "none",
      }} />

      <div style={{
        width: "100%", maxWidth: 440,
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(139,92,246,0.2)",
        borderRadius: 16,
        padding: "44px 40px",
        backdropFilter: "blur(20px)",
        position: "relative",
        zIndex: 1,
      }}>

        {/* Logo + brand */}
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 12, margin: "0 auto 16px",
            background: "linear-gradient(135deg, #7c3aed, #a855f7)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 24, boxShadow: "0 8px 32px rgba(124,58,237,0.4)",
          }}>
            ◆
          </div>
          <div style={{
            fontSize: 20, fontWeight: 800, color: "#fff",
            letterSpacing: "0.04em", textTransform: "uppercase",
          }}>
            Imperium Dynamics
          </div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", marginTop: 4 }}>
            AI Interview Evaluation Platform
          </div>
        </div>

        {/* Divider */}
        <div style={{
          height: 1,
          background: "linear-gradient(90deg, transparent, rgba(139,92,246,0.4), transparent)",
          marginBottom: 32,
        }} />

        <div style={{ fontSize: 15, fontWeight: 600, color: "#fff", marginBottom: 6 }}>
          Sign in to your account
        </div>
        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginBottom: 28 }}>
          Access is restricted to authorised personnel only.
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 6 }}>
              Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@imperiumdynamics.com"
              required
              style={{
                width: "100%", padding: "11px 14px",
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(139,92,246,0.25)",
                borderRadius: 8, color: "#fff", fontSize: 13,
                outline: "none", boxSizing: "border-box",
                transition: "border-color 0.2s",
              }}
              onFocus={(e) => (e.target.style.borderColor = "rgba(139,92,246,0.7)")}
              onBlur={(e) => (e.target.style.borderColor = "rgba(139,92,246,0.25)")}
            />
          </div>

          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.08em", display: "block", marginBottom: 6 }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={{
                width: "100%", padding: "11px 14px",
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(139,92,246,0.25)",
                borderRadius: 8, color: "#fff", fontSize: 13,
                outline: "none", boxSizing: "border-box",
                transition: "border-color 0.2s",
              }}
              onFocus={(e) => (e.target.style.borderColor = "rgba(139,92,246,0.7)")}
              onBlur={(e) => (e.target.style.borderColor = "rgba(139,92,246,0.25)")}
            />
          </div>

          {error && (
            <div style={{
              background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 7, padding: "10px 14px", fontSize: 13, color: "#fca5a5",
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: 4, padding: "12px",
              background: loading
                ? "rgba(124,58,237,0.4)"
                : "linear-gradient(135deg, #7c3aed, #a855f7)",
              border: "none", borderRadius: 8,
              color: "#fff", fontSize: 14, fontWeight: 700,
              cursor: loading ? "not-allowed" : "pointer",
              letterSpacing: "0.02em",
              boxShadow: loading ? "none" : "0 4px 20px rgba(124,58,237,0.4)",
              transition: "all 0.2s",
            }}
          >
            {loading ? "Signing in…" : "Sign In →"}
          </button>
        </form>

        {/* Footer */}
        <div style={{
          marginTop: 32, paddingTop: 24,
          borderTop: "1px solid rgba(255,255,255,0.05)",
          textAlign: "center", fontSize: 11, color: "rgba(255,255,255,0.2)",
        }}>
          © {new Date().getFullYear()} Imperium Dynamics · Confidential
        </div>
      </div>
    </div>
  );
}
