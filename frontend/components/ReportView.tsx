"use client";
import { useEffect, useState, useCallback } from "react";
import { fetchReport, submitDecision, CandidateReport } from "@/lib/api";
import { saveComment, getComment } from "@/lib/comments";
import {
  Card, Badge, Metric, SectionTitle, Alert, Btn, ScoreDot, Divider, Spinner,
} from "./ui";

interface Props { candidateId: string; userRole: "hr" | "hm" }

export default function ReportView({ candidateId, userRole }: Props) {
  const [report, setReport] = useState<CandidateReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Acknowledgment checkboxes
  const [ackDims, setAckDims] = useState(false);
  const [ackBias, setAckBias] = useState(false);
  const [ackResp, setAckResp] = useState(false);
  const [decision, setDecision] = useState("Hold");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitMsg, setSubmitMsg] = useState("");
  const [existingComment, setExistingComment] = useState<{ comment: string; decision: string } | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    setReport(null);
    setAckDims(false); setAckBias(false); setAckResp(false);
    setSubmitMsg("");
    setComment("");
    setExistingComment(getComment(candidateId));
    fetchReport(candidateId)
      .then(setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [candidateId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ padding: 48, display: "flex", justifyContent: "center" }}><Spinner /></div>;
  if (error) return <Alert variant="error">❌ {error}</Alert>;
  if (!report) return null;

  const r = report;
  const allAck = ackDims && ackBias && ackResp;

  const recColor: Record<string, string> = {
    "Strong Yes": "var(--green)", Yes: "var(--blue)", Maybe: "var(--amber)", No: "var(--red)",
  };

  const isRejection = decision === "Rejected";
  const commentMissing = isRejection && comment.trim().length === 0;

  const handleDecision = async () => {
    if (commentMissing) return;
    setSubmitting(true);
    setSubmitMsg("");
    try {
      await submitDecision(candidateId, decision);
      saveComment(candidateId, decision, comment.trim());
      setExistingComment({ comment: comment.trim(), decision });
      setSubmitMsg(`✅ Decision committed: ${decision}`);
    } catch (e: unknown) {
      setSubmitMsg(`❌ ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Header metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        <Metric label="Candidate" value={r.candidate_name} />
        <Metric label="Role Applied" value={r.role_applied} />
        <Metric label="MCQ Score" value={`${r.mcq_score} / 5`} />
      </div>

      {r.mcq_insight && (
        <Alert variant="info">
          <strong>MCQ Insight:</strong> {r.mcq_insight}
        </Alert>
      )}

      {/* Programming */}
      <SectionTitle>Automated Test Code Submissions</SectionTitle>
      <Card>
        {r.programming_passed !== null && r.programming_passed !== undefined ? (
          <>
            <Metric
              label="Programming Logic & Approach"
              value={r.programming_passed ? "✅ PASS" : "❌ FAIL"}
            />
            {r.programming_insight && (
              <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 12 }}>{r.programming_insight}</p>
            )}
          </>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Metric label="Programming Q1" value={`${r.programming_q1_score ?? "N/A"} / 5`} />
            <Metric label="Programming Q2" value={`${r.programming_q2_score ?? "N/A"} / 5`} />
          </div>
        )}
      </Card>

      {/* CV Match */}
      {r.cv_experience_match && (() => {
        const cv = r.cv_experience_match;
        const dot = (v: string) => ({ strong: "🟢", moderate: "🟡", weak: "🔴" }[v] ?? "⚪");
        return (
          <>
            <SectionTitle>CV Experience Match</SectionTitle>
            <Card>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 16 }}>
                <Metric label="Years of Experience" value={cv.years_of_experience} sub={`Role requires ${cv.role_min_experience}`} />
                <Metric label="Domain Match" value={`${dot(cv.domain_match)} ${cv.domain_match}`} />
                <Metric label="Overall CV Rating" value={`${dot(cv.overall_match_rating)} ${cv.overall_match_rating}`} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--green)", marginBottom: 8 }}>✅ Required Skills Present</div>
                  {cv.required_skills_present.map((s) => (
                    <div key={s} style={{ fontSize: 13, color: "var(--text)", paddingLeft: 12, marginBottom: 4 }}>• {s}</div>
                  ))}
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--red)", marginBottom: 8 }}>❌ Required Skills Missing</div>
                  {cv.required_skills_missing.length ? cv.required_skills_missing.map((s) => (
                    <div key={s} style={{ fontSize: 13, color: "var(--text)", paddingLeft: 12, marginBottom: 4 }}>• {s}</div>
                  )) : (
                    <div style={{ fontSize: 13, color: "var(--muted)", paddingLeft: 12 }}>All required skills present.</div>
                  )}
                </div>
              </div>
            </Card>
          </>
        );
      })()}

      {/* Dimensional Analysis */}
      <SectionTitle>Multi-Agent Dimensional Analysis</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        <Card>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
            🗣️ Communication — <ScoreDot score={r.communication.score} />
          </div>
          <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>{r.communication.justification}</p>
          {r.communication.evidence && (
            <p style={{ fontSize: 12, color: "var(--muted)", fontStyle: "italic", marginTop: 8 }}>"{r.communication.evidence}"</p>
          )}
        </Card>

        <Card>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
            🧩 Problem Solving — <ScoreDot score={r.problem_solving.score} />
          </div>
          <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>{r.problem_solving.justification}</p>
          {r.problem_solving.evidence && (
            <p style={{ fontSize: 12, color: "var(--muted)", fontStyle: "italic", marginTop: 8 }}>"{r.problem_solving.evidence}"</p>
          )}
        </Card>

        <Card style={{ gridColumn: "span 1" }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
            💻 Technical Depth — <ScoreDot score={r.technical_depth.overall_score} />
          </div>
          <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 12 }}>{r.technical_depth.overall_justification}</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {r.technical_depth.dimensions.map((d) => (
              <div key={d.dimension_name} style={{ borderLeft: "2px solid var(--border)", paddingLeft: 10 }}>
                {d.not_assessed ? (
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    ⚪ <strong>{d.dimension_name.replace(/_/g, " ")}</strong> — Not assessed
                  </div>
                ) : (
                  <>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>
                      {d.score >= 4 ? "🟢" : d.score === 3 ? "🟡" : "🔴"}{" "}
                      {d.dimension_name.replace(/_/g, " ")} — <ScoreDot score={d.score} />
                    </div>
                    <div style={{ fontSize: 12, color: "var(--muted)" }}>{d.justification}</div>
                  </>
                )}
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
            🤝 Cultural Alignment — <ScoreDot score={r.cultural_alignment.score} />
          </div>
          <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>{r.cultural_alignment.justification}</p>
          {r.cultural_alignment.evidence && (
            <p style={{ fontSize: 12, color: "var(--muted)", fontStyle: "italic", marginTop: 8 }}>"{r.cultural_alignment.evidence}"</p>
          )}
        </Card>
      </div>

      {/* Bias Flags */}
      <SectionTitle>Interviewer Bias Pre-Screen</SectionTitle>
      {r.interviewer_bias_flags && r.interviewer_bias_flags.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Alert variant="warning">
            ⚠️ <strong>{r.interviewer_bias_flags.length} biased question(s) detected.</strong> Review before committing a decision.
          </Alert>
          {r.interviewer_bias_flags.map((f, i) => (
            <Card key={i} style={{ borderLeft: `3px solid ${f.severity === "high" ? "var(--red)" : "var(--amber)"}` }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>
                {f.severity === "high" ? "🔴" : "🟡"} [{f.severity.toUpperCase()}] {f.bias_category.replace(/_/g, " ")}
              </div>
              <div style={{ fontSize: 13, color: "var(--text)", marginBottom: 6 }}><strong>Question:</strong> {f.question_text}</div>
              <div style={{ fontSize: 12, color: "var(--muted)" }}><strong>Rationale:</strong> {f.rationale}</div>
            </Card>
          ))}
        </div>
      ) : (
        <Alert variant="success">✅ No biased questions detected.</Alert>
      )}

      {/* Strengths & Concerns */}
      <SectionTitle>AI Core Synthesis</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--green)", marginBottom: 10 }}>📈 Strengths</div>
          {r.strengths.map((s, i) => (
            <div key={i} style={{ fontSize: 13, color: "var(--text)", paddingLeft: 12, marginBottom: 6 }}>• {s}</div>
          ))}
        </Card>
        <Card>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--red)", marginBottom: 10 }}>⚠️ Concerns</div>
          {r.concerns.map((c, i) => (
            <div key={i} style={{ fontSize: 13, color: "var(--text)", paddingLeft: 12, marginBottom: 6 }}>• {c}</div>
          ))}
        </Card>
      </div>

      {/* Decision */}
      <SectionTitle>AI Recommendation & Decision Status</SectionTitle>
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: "var(--muted)" }}>AI Recommendation:</span>
          <span style={{ fontWeight: 700, color: recColor[r.ai_recommendation] ?? "var(--text)" }}>
            {r.ai_recommendation}
          </span>
          <Badge label={r.hiring_manager_decision} />
        </div>
        <p style={{ fontSize: 13, color: "var(--muted)", fontStyle: "italic", marginBottom: 0 }}>
          {r.ai_justification}
        </p>

        {/* HR: read-only view of current decision */}
        {userRole === "hr" && (
          <>
            <Divider />
            <Alert variant="info">
              Hiring decision visible above. Only the Hiring Manager can update the candidate status.
            </Alert>
          </>
        )}

        {/* HM: full acknowledgment + decision form */}
        {userRole === "hm" && (
          <>
            <Divider />
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
              Human Review Acknowledgment
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
              {[
                [ackDims, setAckDims, "I have reviewed all dimension scores and justifications."],
                [ackBias, setAckBias, "I have reviewed the bias pre-screen results."],
                [ackResp, setAckResp, "I understand this decision is my professional responsibility."],
              ].map(([val, setter, label], i) => (
                <label key={i} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", fontSize: 13, color: "var(--text)" }}>
                  <input
                    type="checkbox"
                    checked={val as boolean}
                    onChange={(e) => (setter as (v: boolean) => void)(e.target.checked)}
                    style={{ width: 15, height: 15, accentColor: "var(--accent)" }}
                  />
                  {label as string}
                </label>
              ))}
            </div>
            {!allAck ? (
              <Alert variant="error">⛔ Complete all three acknowledgments above to unlock the decision form.</Alert>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {/* Existing committed comment */}
                {existingComment && (
                  <div style={{
                    background: "var(--surface2)", border: "1px solid var(--border)",
                    borderRadius: 8, padding: "12px 14px",
                  }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>
                      Previously committed — {existingComment.decision}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--text)", fontStyle: existingComment.comment ? "normal" : "italic" }}>
                      {existingComment.comment || "No comment provided."}
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                  <select
                    value={decision}
                    onChange={(e) => { setDecision(e.target.value); setComment(""); }}
                    style={{
                      background: "var(--surface2)", border: "1px solid var(--border)",
                      borderRadius: 7, color: "var(--text)", padding: "8px 12px", fontSize: 13,
                      flexShrink: 0,
                    }}
                  >
                    {["Hold", "Hired", "Rejected"].map((d) => <option key={d}>{d}</option>)}
                  </select>

                  <div style={{ flex: 1 }}>
                    <textarea
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      placeholder={isRejection
                        ? "Rejection reason is required — explain why this candidate was not selected…"
                        : "Optional — add a note about this decision…"
                      }
                      rows={3}
                      style={{
                        width: "100%", resize: "vertical",
                        background: "var(--surface2)",
                        border: `1px solid ${commentMissing ? "var(--red)" : "var(--border)"}`,
                        borderRadius: 7, color: "var(--text)",
                        padding: "8px 12px", fontSize: 13,
                        outline: "none", boxSizing: "border-box",
                        fontFamily: "inherit",
                      }}
                    />
                    {isRejection && (
                      <div style={{ fontSize: 11, marginTop: 4, color: commentMissing ? "var(--red)" : "var(--muted)" }}>
                        {commentMissing ? "⚠️ A rejection reason is mandatory." : "✓ Rejection reason provided."}
                      </div>
                    )}
                    {!isRejection && (
                      <div style={{ fontSize: 11, marginTop: 4, color: "var(--muted)" }}>
                        Optional for {decision}.
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <Btn variant="primary" onClick={handleDecision} disabled={submitting || commentMissing}>
                    {submitting ? "Committing..." : "Commit Decision"}
                  </Btn>
                  {submitMsg && (
                    <span style={{ fontSize: 13, color: submitMsg.startsWith("✅") ? "var(--green)" : "var(--red)" }}>
                      {submitMsg}
                    </span>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
