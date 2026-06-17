"use client";
import { useState, useEffect, useCallback } from "react";
import {
  checkDuplicate, createCandidate, uploadFiles, fetchIntakeRecord,
  runEvaluation, fetchProgress, IntakeCandidate,
} from "@/lib/api";
import { Card, Alert, Btn, Input, Select, ProgressBar, Divider } from "./ui";
import FilePickerButton from "./FilePickerButton";

interface Props {
  onEvaluated: () => void;
}

const ROLES = [
  { value: "AI", label: "🤖 AI Engineer" },
  { value: "SWE", label: "💻 Software Engineer" },
  { value: "BA", label: "📊 Business Analyst" },
  { value: "Trainee", label: "🎓 Trainee" },
];

const DOC_META: { key: string; field: string; label: string; accept: string; hint: string }[] = [
  { key: "cv",          field: "cv_file",       label: "📄 CV",                         accept: ".pdf",             hint: "PDF only" },
  { key: "session1",    field: "session1_file",  label: "🎙️ Session 1 (Technical)",      accept: ".pdf,.txt,.docx",  hint: "PDF, TXT, or DOCX" },
  { key: "session2",    field: "session2_file",  label: "🎙️ Session 2 (HR/Behavioural)", accept: ".pdf,.txt,.docx",  hint: "PDF, TXT, or DOCX" },
  { key: "mcq",         field: "mcq_file",       label: "📊 MCQ Results",                accept: ".pdf,.txt,.docx",  hint: "AI reads the score automatically" },
  { key: "programming", field: "prog_file_1",    label: "💻 Programming Answers",        accept: ".pdf,.txt,.docx",  hint: "One doc containing both Q1 & Q2" },
];

function completeness(rec: IntakeCandidate) {
  const fields: (keyof IntakeCandidate)[] = ["cv_path", "session1_path", "session2_path", "mcq_path", "programming_path"];
  return Math.round((fields.filter((f) => rec[f]).length / fields.length) * 100);
}

export default function IntakeWizard({ onEvaluated }: Props) {
  // Step 1
  const [name, setName] = useState("");
  const [role, setRole] = useState("AI");
  const [step1Error, setStep1Error] = useState("");
  const [step1Loading, setStep1Loading] = useState(false);
  const [dupeCheck, setDupeCheck] = useState<{ show: boolean; records: IntakeCandidate[] }>({ show: false, records: [] });

  // Registered candidate
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [candidateName, setCandidateName] = useState("");
  const [liveRecord, setLiveRecord] = useState<IntakeCandidate | null>(null);
  const [replaceMode, setReplaceMode] = useState<Record<string, boolean>>({});

  // Step 2
  const [uploadFiles_, setUploadFiles] = useState<Record<string, File | null>>({});
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");

  // Step 3
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalEvents, setEvalEvents] = useState<string[]>([]);
  const [evalStatus, setEvalStatus] = useState("");
  const [evalError, setEvalError] = useState("");

  const pct = liveRecord ? completeness(liveRecord) : 0;
  const allDone = pct === 100;

  const refreshRecord = useCallback(async (id: string) => {
    try {
      const rec = await fetchIntakeRecord(id);
      setLiveRecord(rec);
    } catch {}
  }, []);

  useEffect(() => {
    if (candidateId) refreshRecord(candidateId);
  }, [candidateId, refreshRecord]);

  const doCreate = async (forceName?: string, forceRole?: string) => {
    const n = forceName ?? name.trim();
    const r = forceRole ?? role;
    setStep1Loading(true);
    setStep1Error("");
    try {
      const res = await createCandidate(n, r);
      setCandidateId(res.candidate_id);
      setCandidateName(n);
      setDupeCheck({ show: false, records: [] });
    } catch (e: unknown) {
      setStep1Error(e instanceof Error ? e.message : "Error");
    } finally {
      setStep1Loading(false);
    }
  };

  const handleStep1 = async () => {
    const n = name.trim();
    if (!n) { setStep1Error("Full name is required."); return; }
    setStep1Loading(true);
    setStep1Error("");
    try {
      const res = await checkDuplicate(n);
      if (res.has_duplicates) {
        setDupeCheck({ show: true, records: res.existing_records });
        setStep1Loading(false);
        return;
      }
      await doCreate(n, role);
    } catch (e: unknown) {
      setStep1Error(e instanceof Error ? e.message : "Error");
      setStep1Loading(false);
    }
  };

  const handleUpload = async () => {
    if (!candidateId) return;
    const filesToSend: Record<string, File> = {};
    Object.entries(uploadFiles_).forEach(([k, v]) => { if (v) filesToSend[k] = v; });
    if (!Object.keys(filesToSend).length) { setUploadMsg("No files selected."); return; }
    setUploadLoading(true);
    setUploadMsg("");
    try {
      const res = await uploadFiles(candidateId, filesToSend);
      setUploadMsg(`✅ ${res.message}`);
      setUploadFiles({});
      setReplaceMode({});
      await refreshRecord(candidateId);
    } catch (e: unknown) {
      setUploadMsg(`❌ ${e instanceof Error ? e.message : "Upload failed"}`);
    } finally {
      setUploadLoading(false);
    }
  };

  const handleEvaluate = async () => {
    if (!candidateId) return;
    setEvalLoading(true);
    setEvalEvents([]);
    setEvalStatus("running");
    setEvalError("");
    try {
      await runEvaluation(candidateId);
      const poll = setInterval(async () => {
        try {
          const prog = await fetchProgress(candidateId);
          setEvalEvents(prog.events ?? []);
          if (prog.status === "completed") {
            clearInterval(poll);
            setEvalStatus("completed");
            setEvalLoading(false);
            onEvaluated();
          } else if (prog.status === "failed") {
            clearInterval(poll);
            setEvalStatus("failed");
            setEvalError(prog.error ?? "Evaluation failed.");
            setEvalLoading(false);
          }
        } catch {}
      }, 1500);
    } catch (e: unknown) {
      setEvalError(e instanceof Error ? e.message : "Failed to start evaluation.");
      setEvalStatus("failed");
      setEvalLoading(false);
    }
  };

  const reset = () => {
    setCandidateId(null); setCandidateName(""); setLiveRecord(null);
    setName(""); setRole("AI"); setStep1Error(""); setDupeCheck({ show: false, records: [] });
    setUploadFiles({}); setUploadMsg(""); setReplaceMode({});
    setEvalLoading(false); setEvalEvents([]); setEvalStatus(""); setEvalError("");
  };

  // Derived doc status
  const docStatus: Record<string, boolean> = liveRecord ? {
    cv: !!liveRecord.cv_path, session1: !!liveRecord.session1_path,
    session2: !!liveRecord.session2_path, mcq: !!liveRecord.mcq_path, programming: !!liveRecord.programming_path,
  } : {};

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* STEP 1 */}
      <Card style={{ borderLeft: "3px solid var(--accent)" }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: "var(--accent-light)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>Step 1</div>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 14 }}>🪪 Register Candidate</div>

        {candidateId ? (
          <Alert variant="success">
            ✅ <strong>{candidateName}</strong> registered as <code style={{ fontSize: 11 }}>{candidateId}</code>
          </Alert>
        ) : dupeCheck.show ? (
          <>
            <Alert variant="warning">
              ⚠️ A candidate named <strong>{name}</strong> already exists:
              <ul style={{ margin: "8px 0 0", paddingLeft: 20, fontSize: 12 }}>
                {dupeCheck.records.map((d) => (
                  <li key={d.candidate_id}><code>{d.candidate_id}</code> — {d.role_type} — {d.status} — {d.created_at.slice(0, 10)}</li>
                ))}
              </ul>
            </Alert>
            <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
              <Btn variant="primary" onClick={() => doCreate(name, role)} disabled={step1Loading}>
                ✅ Create anyway
              </Btn>
              <Btn onClick={() => setDupeCheck({ show: false, records: [] })}>Cancel</Btn>
            </div>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Input placeholder="Full Name *" value={name} onChange={(e) => setName(e.target.value)} />
            <Select value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </Select>
            {step1Error && <Alert variant="error">{step1Error}</Alert>}
            <Btn variant="primary" onClick={handleStep1} disabled={step1Loading}>
              {step1Loading ? "Creating..." : "Create Candidate Profile →"}
            </Btn>
          </div>
        )}
      </Card>

      {/* STEP 2 */}
      <Card style={{ borderLeft: `3px solid ${candidateId ? "var(--accent)" : "var(--border)"}`, opacity: candidateId ? 1 : 0.5 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: "var(--accent-light)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>Step 2</div>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 14 }}>📁 Upload Documents</div>

        {!candidateId ? (
          <p style={{ fontSize: 13, color: "var(--muted)" }}>Complete Step 1 to unlock.</p>
        ) : (
          <>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 6 }}>Completeness: {pct}%</div>
              <ProgressBar pct={pct} />
            </div>
            {allDone && <Alert variant="success" >✅ All documents uploaded. Proceed to Step 3.</Alert>}

            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
              {DOC_META.map(({ key, field, label, accept, hint }) => {
                const done = docStatus[key] && !replaceMode[key];
                return (
                  <div key={key} style={{
                    border: `1px solid ${done ? "#065f46" : "var(--border)"}`,
                    borderRadius: 8, padding: "10px 14px",
                    background: done ? "rgba(6,95,70,0.08)" : "var(--surface2)",
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <div>
                        <span style={{ fontWeight: 600, fontSize: 13 }}>{done ? "✅" : "⬜"} {label}</span>
                        <span style={{ fontSize: 11, color: "var(--muted)", marginLeft: 8 }}>{hint}</span>
                      </div>
                      {done && (
                        <Btn size="sm" onClick={() => setReplaceMode((p) => ({ ...p, [key]: true }))}>🔄 Replace</Btn>
                      )}
                    </div>
                    {!done && (
                      <FilePickerButton
                        accept={accept}
                        selectedFile={uploadFiles_[field] ?? null}
                        onChange={(file) => setUploadFiles((p) => ({ ...p, [field]: file }))}
                      />
                    )}
                  </div>
                );
              })}
            </div>

            <div style={{ marginTop: 14, display: "flex", gap: 10, alignItems: "center" }}>
              <Btn variant="primary" onClick={handleUpload} disabled={uploadLoading}>
                {uploadLoading ? "Saving..." : "💾 Save Selected Documents"}
              </Btn>
              {uploadMsg && (
                <span style={{ fontSize: 13, color: uploadMsg.startsWith("✅") ? "var(--green)" : "var(--red)" }}>
                  {uploadMsg}
                </span>
              )}
            </div>
          </>
        )}
      </Card>

      {/* STEP 3 */}
      <Card style={{ borderLeft: `3px solid ${allDone ? "var(--accent)" : "var(--border)"}`, opacity: allDone ? 1 : 0.5 }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: "var(--accent-light)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>Step 3</div>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 14 }}>🚀 Run AI Evaluation Pipeline</div>

        {!allDone ? (
          <p style={{ fontSize: 13, color: "var(--muted)" }}>All documents must be uploaded first.</p>
        ) : evalStatus === "completed" ? (
          <Alert variant="success">🎉 Evaluation complete! View the report in the Candidate Reports tab.</Alert>
        ) : evalStatus === "failed" ? (
          <Alert variant="error">❌ {evalError}</Alert>
        ) : (
          <>
            <Alert variant="info">
              <strong>{candidateName}</strong> · <code style={{ fontSize: 11 }}>{candidateId}</code>
              <br />All documents uploaded. Pipeline ready. This takes 60–120 seconds.
            </Alert>
            <div style={{ marginTop: 14 }}>
              <Btn variant="primary" onClick={handleEvaluate} disabled={evalLoading}>
                {evalLoading ? "Running..." : "🚀 Run Full Evaluation"}
              </Btn>
            </div>
            {evalEvents.length > 0 && (
              <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 6 }}>
                {evalEvents.map((ev, i) => (
                  <div key={i} style={{ fontSize: 12, color: "var(--green)" }}>
                    ✅ {ev.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  </div>
                ))}
                {evalLoading && (
                  <div style={{ fontSize: 12, color: "var(--muted)", fontStyle: "italic" }}>Processing…</div>
                )}
              </div>
            )}
          </>
        )}
      </Card>

      {candidateId && evalStatus !== "completed" && (
        <>
          <Divider />
          <Btn onClick={reset} size="sm">🔄 Start Over (new candidate)</Btn>
        </>
      )}
    </div>
  );
}
