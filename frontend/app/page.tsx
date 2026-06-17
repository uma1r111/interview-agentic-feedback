"use client";
import { useState, useEffect } from "react";
import AuthGuard from "@/components/AuthGuard";
import CandidateList from "@/components/CandidateList";
import ReportView from "@/components/ReportView";
import { checkHealth } from "@/lib/api";

export default function ReportsPage() {
  return (
    <AuthGuard>
      {(user) => <ReportsContent userRole={user.role} />}
    </AuthGuard>
  );
}

function ReportsContent({ userRole }: { userRole: "hr" | "hm" }) {
  const [selected, setSelected] = useState("");
  const [health, setHealth] = useState<"ok" | "error" | "loading">("loading");

  useEffect(() => {
    checkHealth()
      .then(() => setHealth("ok"))
      .catch(() => setHealth("error"));
  }, []);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 24, alignItems: "start" }}>
      {/* Sidebar */}
      <div style={{
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: 10, padding: "20px 16px", position: "sticky", top: 80,
      }}>
        {health === "error" && (
          <div style={{ fontSize: 11, color: "var(--red)", marginBottom: 12, padding: "6px 10px", background: "#450a0a", borderRadius: 6 }}>
            🔴 FastAPI not reachable
          </div>
        )}
        {health === "ok" && (
          <div style={{ fontSize: 11, color: "var(--green)", marginBottom: 12, padding: "6px 10px", background: "#022c22", borderRadius: 6 }}>
            🟢 Backend connected
          </div>
        )}
        <CandidateList selected={selected} onSelect={setSelected} />
      </div>

      {/* Main */}
      <div>
        {selected ? (
          <ReportView key={selected} candidateId={selected} userRole={userRole} />
        ) : (
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            minHeight: 400, color: "var(--muted)", fontSize: 14, gap: 12,
          }}>
            <span style={{ fontSize: 40 }}>💼</span>
            <p style={{ margin: 0, fontWeight: 500 }}>Select a candidate to view their evaluation report</p>
            <p style={{ margin: 0, fontSize: 12 }}>Use the registry on the left or enter an ID manually</p>
          </div>
        )}
      </div>
    </div>
  );
}
