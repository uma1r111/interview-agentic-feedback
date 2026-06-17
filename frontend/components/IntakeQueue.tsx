"use client";
import { useEffect, useState, useCallback } from "react";
import { fetchIntakeCandidates, deleteIntake, runEvaluation, fetchProgress, IntakeCandidate } from "@/lib/api";
import { Badge, Btn, ProgressBar, Alert, Spinner } from "./ui";

function completeness(rec: IntakeCandidate) {
  const fields: (keyof IntakeCandidate)[] = ["cv_path", "session1_path", "session2_path", "mcq_path", "programming_path"];
  return Math.round((fields.filter((f) => rec[f]).length / fields.length) * 100);
}

interface Props {
  refreshKey: number;
  onResume: (id: string, name: string) => void;
}

export default function IntakeQueue({ refreshKey, onResume }: Props) {
  const [list, setList] = useState<IntakeCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [deleteMsg, setDeleteMsg] = useState<Record<string, string>>({});
  const [evalState, setEvalState] = useState<Record<string, { events: string[]; status: string; error?: string }>>({});

  const refresh = useCallback(() => {
    setLoading(true);
    fetchIntakeCandidates()
      .then(setList)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh, refreshKey]);

  const handleDelete = async (id: string) => {
    try {
      await deleteIntake(id);
      setConfirmDelete(null);
      refresh();
    } catch (e: unknown) {
      setDeleteMsg((p) => ({ ...p, [id]: e instanceof Error ? e.message : "Delete failed" }));
      setConfirmDelete(null);
    }
  };

  const handleEval = async (candidate: IntakeCandidate) => {
    setEvalState((p) => ({ ...p, [candidate.candidate_id]: { events: [], status: "running" } }));
    try {
      await runEvaluation(candidate.candidate_id);
      const poll = setInterval(async () => {
        try {
          const prog = await fetchProgress(candidate.candidate_id);
          setEvalState((p) => ({ ...p, [candidate.candidate_id]: { events: prog.events ?? [], status: prog.status, error: prog.error } }));
          if (prog.status === "completed" || prog.status === "failed") {
            clearInterval(poll);
            if (prog.status === "completed") refresh();
          }
        } catch {}
      }, 1500);
    } catch (e: unknown) {
      setEvalState((p) => ({
        ...p, [candidate.candidate_id]: { events: [], status: "failed", error: e instanceof Error ? e.message : "Failed" },
      }));
    }
  };

  const ready    = list.filter((r) => r.status === "ready");
  const awaiting = list.filter((r) => r.status === "awaiting_files");

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: "20px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Intake Queue
        </div>
        <Btn size="sm" onClick={refresh}>🔃</Btn>
      </div>

      {loading && <Spinner />}

      {!loading && list.length === 0 && (
        <p style={{ fontSize: 13, color: "var(--muted)" }}>No candidates in intake.</p>
      )}

      {ready.length > 0 && (
        <>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--green)", marginBottom: 8 }}>✅ Ready ({ready.length})</div>
          {ready.map((row) => {
            const ev = evalState[row.candidate_id];
            return (
              <div key={row.candidate_id} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 12, marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{row.candidate_name}</div>
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>{row.role_type} · <Badge label={row.status} /></div>
                    <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}><code>{row.candidate_id}</code></div>
                  </div>
                  {!ev && (
                    <Btn variant="primary" size="sm" onClick={() => handleEval(row)}>🚀</Btn>
                  )}
                </div>
                {ev && (
                  <div style={{ marginTop: 8, fontSize: 12 }}>
                    {ev.events.map((e, i) => (
                      <div key={i} style={{ color: "var(--green)" }}>✅ {e.replace(/_/g, " ")}</div>
                    ))}
                    {ev.status === "running" && <div style={{ color: "var(--muted)", fontStyle: "italic" }}>Processing…</div>}
                    {ev.status === "failed" && <Alert variant="error">❌ {ev.error}</Alert>}
                    {ev.status === "completed" && <Alert variant="success">🎉 Done!</Alert>}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}

      {awaiting.length > 0 && (
        <>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--amber)", marginBottom: 8 }}>⏳ Awaiting Files ({awaiting.length})</div>
          {awaiting.map((row) => {
            const pct = completeness(row);
            const isConfirming = confirmDelete === row.candidate_id;
            return (
              <div key={row.candidate_id} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 12, marginBottom: 12 }}>
                <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2 }}>{row.candidate_name}</div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>
                  {row.role_type} · {pct}% · {row.created_at.slice(0, 10)}
                </div>
                <ProgressBar pct={pct} />
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  {!isConfirming ? (
                    <>
                      <Btn variant="primary" size="sm" onClick={() => onResume(row.candidate_id, row.candidate_name)}>
                        📂 Resume
                      </Btn>
                      <Btn variant="danger" size="sm" onClick={() => setConfirmDelete(row.candidate_id)}>
                        🗑️
                      </Btn>
                    </>
                  ) : (
                    <>
                      <Btn variant="danger" size="sm" onClick={() => handleDelete(row.candidate_id)}>
                        Confirm Delete
                      </Btn>
                      <Btn size="sm" onClick={() => setConfirmDelete(null)}>Cancel</Btn>
                    </>
                  )}
                </div>
                {deleteMsg[row.candidate_id] && (
                  <div style={{ fontSize: 12, color: "var(--red)", marginTop: 6 }}>{deleteMsg[row.candidate_id]}</div>
                )}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
