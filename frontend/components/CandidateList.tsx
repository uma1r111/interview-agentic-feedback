"use client";
import { useEffect, useState } from "react";
import { fetchCandidates, CandidateSummary } from "@/lib/api";
import { Badge, Input, Btn, Spinner } from "./ui";

const recDot: Record<string, string> = {
  "Strong Yes": "🟢", Yes: "🔵", Maybe: "🟡", No: "🔴",
};
const decDot: Record<string, string> = { Hired: "🟢", Rejected: "🔴", Hold: "🟡" };

interface Props {
  selected: string;
  onSelect: (id: string) => void;
}

export default function CandidateList({ selected, onSelect }: Props) {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [manualId, setManualId] = useState("");

  useEffect(() => {
    fetchCandidates()
      .then(setCandidates)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
        Candidate Registry
      </div>

      {loading && <Spinner />}

      {!loading && candidates.length === 0 && (
        <p style={{ fontSize: 13, color: "var(--muted)" }}>No evaluated candidates yet.</p>
      )}

      {candidates.map((c) => {
        const active = c.candidate_id === selected;
        return (
          <button
            key={c.candidate_id}
            onClick={() => onSelect(c.candidate_id)}
            style={{
              background: active ? "rgba(124,106,247,0.14)" : "var(--surface2)",
              border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
              borderRadius: 8, padding: "10px 12px", cursor: "pointer",
              textAlign: "left", width: "100%",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text)", marginBottom: 3 }}>
              {decDot[c.hiring_decision] ?? "⚪"} {c.candidate_name}
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>
              {c.role_type} · MCQ {c.mcq_score}/5 · {recDot[c.ai_recommendation] ?? "⚪"} {c.ai_recommendation}
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
              {c.evaluated_at?.slice(0, 10)}
            </div>
          </button>
        );
      })}

      <div style={{ marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
          Manual Lookup
        </div>
        <Input
          placeholder="Candidate ID"
          value={manualId}
          onChange={(e) => setManualId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && manualId.trim() && onSelect(manualId.trim())}
          style={{ marginBottom: 8 }}
        />
        <Btn
          variant="ghost"
          size="sm"
          style={{ width: "100%" }}
          onClick={() => manualId.trim() && onSelect(manualId.trim())}
        >
          Load by ID
        </Btn>
      </div>
    </div>
  );
}
