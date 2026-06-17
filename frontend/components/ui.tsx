import React from "react";

// ── Card ──────────────────────────────────────────────────────────────────
export function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 10,
      padding: "20px 24px",
      ...style,
    }}>
      {children}
    </div>
  );
}

// ── Badge ──────────────────────────────────────────────────────────────────
const badgeColors: Record<string, { bg: string; color: string }> = {
  awaiting_files: { bg: "#451a03", color: "#fde68a" },
  ready:          { bg: "#022c22", color: "#6ee7b7" },
  evaluated:      { bg: "#172554", color: "#93c5fd" },
  Hired:          { bg: "#022c22", color: "#6ee7b7" },
  Rejected:       { bg: "#450a0a", color: "#fca5a5" },
  Hold:           { bg: "#422006", color: "#fed7aa" },
  "Strong Yes":   { bg: "#022c22", color: "#6ee7b7" },
  Yes:            { bg: "#172554", color: "#93c5fd" },
  Maybe:          { bg: "#422006", color: "#fed7aa" },
  No:             { bg: "#450a0a", color: "#fca5a5" },
};

export function Badge({ label }: { label: string }) {
  const c = badgeColors[label] ?? { bg: "#1e1e2c", color: "#8892a4" };
  return (
    <span style={{
      background: c.bg, color: c.color,
      padding: "2px 10px", borderRadius: 20,
      fontSize: 11, fontWeight: 600, letterSpacing: "0.04em",
      textTransform: "uppercase",
    }}>
      {label.replace("_", " ")}
    </span>
  );
}

// ── ScoreDot ───────────────────────────────────────────────────────────────
export function ScoreDot({ score }: { score: number }) {
  const color = score >= 4 ? "var(--green)" : score === 3 ? "var(--amber)" : "var(--red)";
  return <span style={{ color, fontWeight: 700 }}>{score}/5</span>;
}

// ── ProgressBar ────────────────────────────────────────────────────────────
export function ProgressBar({ pct }: { pct: number }) {
  const color = pct === 100 ? "var(--green)" : "var(--amber)";
  return (
    <div style={{ background: "var(--border)", borderRadius: 4, height: 5, overflow: "hidden" }}>
      <div style={{ background: color, width: `${pct}%`, height: 5, transition: "width 0.3s" }} />
    </div>
  );
}

// ── Metric ──────────────────────────────────────────────────────────────────
export function Metric({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div style={{
      background: "var(--surface2)", border: "1px solid var(--border)",
      borderRadius: 8, padding: "14px 18px",
    }}>
      <div style={{ fontSize: 11, color: "var(--muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text)" }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

// ── Section heading ────────────────────────────────────────────────────────
export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", margin: "24px 0 12px" }}>
      {children}
    </h3>
  );
}

// ── Alert ──────────────────────────────────────────────────────────────────
type AlertVariant = "info" | "success" | "warning" | "error";
const alertStyle: Record<AlertVariant, { bg: string; border: string; color: string }> = {
  info:    { bg: "#172554", border: "#1d4ed8", color: "#93c5fd" },
  success: { bg: "#022c22", border: "#065f46", color: "#6ee7b7" },
  warning: { bg: "#422006", border: "#92400e", color: "#fed7aa" },
  error:   { bg: "#450a0a", border: "#7f1d1d", color: "#fca5a5" },
};

export function Alert({ variant, children }: { variant: AlertVariant; children: React.ReactNode }) {
  const s = alertStyle[variant];
  return (
    <div style={{
      background: s.bg, border: `1px solid ${s.border}`, color: s.color,
      borderRadius: 8, padding: "12px 16px", fontSize: 13, lineHeight: 1.6,
    }}>
      {children}
    </div>
  );
}

// ── Button ──────────────────────────────────────────────────────────────────
interface BtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger";
  size?: "sm" | "md";
}
export function Btn({ variant = "ghost", size = "md", style, children, ...rest }: BtnProps) {
  const base: React.CSSProperties = {
    borderRadius: 7, fontWeight: 600, cursor: "pointer",
    border: "1px solid transparent", transition: "opacity 0.15s",
    fontSize: size === "sm" ? 12 : 13,
    padding: size === "sm" ? "5px 12px" : "8px 18px",
  };
  const variants: Record<string, React.CSSProperties> = {
    primary: { background: "var(--accent)", color: "#fff", border: "1px solid var(--accent)" },
    ghost:   { background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)" },
    danger:  { background: "#450a0a", color: "#fca5a5", border: "1px solid #7f1d1d" },
  };
  return (
    <button style={{ ...base, ...variants[variant], ...style }} {...rest}>
      {children}
    </button>
  );
}

// ── Input ──────────────────────────────────────────────────────────────────
export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input {...props} style={{
      background: "var(--surface2)", border: "1px solid var(--border)",
      borderRadius: 7, color: "var(--text)", padding: "8px 12px",
      fontSize: 13, outline: "none", width: "100%",
      ...props.style,
    }} />
  );
}

// ── Select ──────────────────────────────────────────────────────────────────
export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} style={{
      background: "var(--surface2)", border: "1px solid var(--border)",
      borderRadius: 7, color: "var(--text)", padding: "8px 12px",
      fontSize: 13, outline: "none", width: "100%",
      ...props.style,
    }} />
  );
}

// ── Divider ────────────────────────────────────────────────────────────────
export function Divider() {
  return <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "20px 0" }} />;
}

// ── Spinner ────────────────────────────────────────────────────────────────
export function Spinner() {
  return (
    <div style={{
      width: 20, height: 20, border: "2px solid var(--border)",
      borderTop: "2px solid var(--accent)", borderRadius: "50%",
      animation: "spin 0.7s linear infinite", display: "inline-block",
    }} />
  );
}
