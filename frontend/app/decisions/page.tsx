"use client";
import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import { fetchDecisions, CandidateSummary } from "@/lib/api";
import { Badge, Spinner } from "@/components/ui";

const recColor: Record<string, string> = {
  "Strong Yes": "#10b981",
  Yes: "#3b82f6",
  Maybe: "#f59e0b",
  No: "#ef4444",
};

const decisionIcon: Record<string, string> = {
  Hired: "✅",
  Rejected: "❌",
  Hold: "⏸️",
};

const HM_NAME: Record<string, string> = {
  "berkha.hm@imperiumdynamics.com": "Berkha",
};

export default function DecisionsPage() {
  return (
    <AuthGuard>
      {() => <DecisionsContent />}
    </AuthGuard>
  );
}

function DecisionsContent() {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"All" | "Hired" | "Rejected" | "Hold">("All");

  const load = () => {
    setLoading(true);
    fetchDecisions()
      .then(setCandidates)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filtered = filter === "All" ? candidates : candidates.filter((c) => c.hiring_decision === filter);

  const counts = {
    All: candidates.length,
    Hired: candidates.filter((c) => c.hiring_decision === "Hired").length,
    Rejected: candidates.filter((c) => c.hiring_decision === "Rejected").length,
    Hold: candidates.filter((c) => c.hiring_decision === "Hold").length,
  };

  return (
    <div>
      {/* Page header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 800, margin: 0, color: "var(--text)" }}>
            🏛️ Hiring Decisions
          </h2>
          <p style={{ fontSize: 13, color: "var(--muted)", margin: "4px 0 0" }}>
            Final outcomes committed by the Hiring Manager — visible to all staff.
          </p>
        </div>
        <button
          onClick={load}
          style={{
            background: "var(--surface2)", border: "1px solid var(--border)",
            borderRadius: 7, color: "var(--muted)", fontSize: 12, fontWeight: 600,
            padding: "7px 14px", cursor: "pointer",
          }}
        >
          🔃 Refresh
        </button>
      </div>

      {/* Summary stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 28 }}>
        {(["All", "Hired", "Rejected", "Hold"] as const).map((key) => {
          const colors: Record<string, { accent: string; bg: string }> = {
            All:      { accent: "var(--accent-light)", bg: "rgba(124,106,247,0.08)" },
            Hired:    { accent: "#10b981", bg: "rgba(16,185,129,0.08)" },
            Rejected: { accent: "#ef4444", bg: "rgba(239,68,68,0.08)" },
            Hold:     { accent: "#f59e0b", bg: "rgba(245,158,11,0.08)" },
          };
          const { accent, bg } = colors[key];
          const active = filter === key;
          return (
            <button
              key={key}
              onClick={() => setFilter(key)}
              style={{
                background: active ? bg : "var(--surface)",
                border: `1px solid ${active ? accent : "var(--border)"}`,
                borderRadius: 10, padding: "16px 20px", cursor: "pointer",
                textAlign: "left", transition: "all 0.15s",
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, color: active ? accent : "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
                {key === "All" ? "Total Evaluated" : key}
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, color: active ? accent : "var(--text)" }}>
                {counts[key]}
              </div>
            </button>
          );
        })}
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 60 }}><Spinner /></div>
      ) : filtered.length === 0 ? (
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 10, padding: "60px 0", textAlign: "center",
          color: "var(--muted)", fontSize: 14,
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📭</div>
          No candidates in this category yet.
        </div>
      ) : (
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 10, overflow: "hidden",
        }}>
          {/* Table header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "2fr 1.2fr 0.8fr 1fr 1.2fr 1fr",
            padding: "12px 20px",
            borderBottom: "1px solid var(--border)",
            background: "var(--surface2)",
          }}>
            {["Candidate", "Role", "MCQ", "AI Recommendation", "Decision", "Evaluated"].map((h) => (
              <div key={h} style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.07em" }}>
                {h}
              </div>
            ))}
          </div>

          {/* Rows */}
          {filtered.map((c, i) => (
            <div
              key={c.candidate_id}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1.2fr 0.8fr 1fr 1.2fr 1fr",
                padding: "14px 20px",
                borderBottom: i < filtered.length - 1 ? "1px solid var(--border)" : "none",
                alignItems: "center",
                transition: "background 0.1s",
              }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.02)")}
              onMouseLeave={(e) => ((e.currentTarget as HTMLDivElement).style.background = "transparent")}
            >
              {/* Name + ID */}
              <div>
                <div style={{ fontWeight: 600, fontSize: 14, color: "var(--text)" }}>{c.candidate_name}</div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                  <code style={{ fontSize: 10 }}>{c.candidate_id}</code>
                </div>
              </div>

              {/* Role */}
              <div style={{ fontSize: 13, color: "var(--muted)" }}>{c.role_type}</div>

              {/* MCQ */}
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{c.mcq_score}/5</div>

              {/* AI Recommendation */}
              <div>
                <span style={{
                  fontSize: 12, fontWeight: 600,
                  color: recColor[c.ai_recommendation] ?? "var(--muted)",
                }}>
                  {c.ai_recommendation ?? "—"}
                </span>
              </div>

              {/* Decision */}
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 15 }}>{decisionIcon[c.hiring_decision] ?? "⚪"}</span>
                <Badge label={c.hiring_decision ?? "Hold"} />
              </div>

              {/* Evaluated date */}
              <div style={{ fontSize: 12, color: "var(--muted)" }}>
                {c.evaluated_at ? c.evaluated_at.slice(0, 10) : "—"}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer note */}
      <div style={{ marginTop: 16, fontSize: 12, color: "var(--muted)", textAlign: "right" }}>
        Decisions committed by <strong style={{ color: "var(--accent-light)" }}>Berkha</strong> · Hiring Manager
      </div>
    </div>
  );
}
