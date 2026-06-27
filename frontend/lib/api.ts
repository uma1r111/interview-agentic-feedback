// ── Core API Client ────────────────────────────────────────────────────────
declare const process: { env: { NEXT_PUBLIC_API_URL?: string } };
// Reads the public Azure URL baked in during compilation, falling back to localhost for development
const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface CandidateSummary {
  candidate_id: string;
  candidate_name: string;
  role_type: string;
  mcq_score: number;
  ai_recommendation: string;
  hiring_decision: string;
  evaluated_at: string;
}

export interface DimensionScore {
  dimension_name: string;
  score: number;
  justification: string;
  evidence?: string;
  not_assessed?: boolean;
}

export interface CandidateReport {
  candidate_name: string;
  role_applied: string;
  mcq_score: number;
  mcq_insight?: string;
  programming_passed?: boolean | null;
  programming_insight?: string;
  programming_q1_score?: number;
  programming_q2_score?: number;
  cv_experience_match?: {
    years_of_experience: number;
    role_min_experience: number;
    domain_match: string;
    overall_match_rating: string;
    required_skills_present: string[];
    required_skills_missing: string[];
  };
  communication: { score: number; justification: string; evidence?: string };
  problem_solving: { score: number; justification: string; evidence?: string };
  technical_depth: { overall_score: number; overall_justification: string; dimensions: DimensionScore[] };
  cultural_alignment: { score: number; justification: string; evidence?: string };
  interviewer_bias_flags?: { severity: string; bias_category: string; question_text: string; rationale: string }[];
  strengths: string[];
  concerns: string[];
  ai_recommendation: string;
  ai_justification: string;
  hiring_manager_decision: string;
}

export interface IntakeCandidate {
  candidate_id: string;
  candidate_name: string;
  role_type: string;
  status: string;
  created_at: string;
  cv_path?: string;
  session1_path?: string;
  session2_path?: string;
  mcq_path?: string;
  programming_path?: string;
}

// ── Endpoints ──────────────────────────────────────────────────────────────

export const fetchCandidates = () => apiFetch<CandidateSummary[]>("/candidates");
export const fetchDecisions = () => apiFetch<CandidateSummary[]>("/candidates");
export const fetchReport = (id: string) => apiFetch<CandidateReport>(`/candidates/${id}/report`);
export const fetchIntakeCandidates = () => apiFetch<IntakeCandidate[]>("/intake/candidates");
export const fetchIntakeRecord = (id: string) => apiFetch<IntakeCandidate>(`/intake/${id}`);
export const fetchProgress = (id: string) =>
  apiFetch<{ status: string; events: string[]; error?: string }>(`/intake/${id}/progress`);
export const checkHealth = () => apiFetch<{ status: string }>("/health");

export const submitDecision = (id: string, decision: string) =>
  apiFetch(`/candidates/${id}/decision`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });

export const checkDuplicate = (name: string) =>
  apiFetch<{ has_duplicates: boolean; existing_records: IntakeCandidate[] }>(
    `/intake/check-duplicate?name=${encodeURIComponent(name)}`
  );

export const createCandidate = (name: string, role: string) => {
  const fd = new FormData();
  fd.append("candidate_name", name);
  fd.append("role_type", role);
  return apiFetch<{ candidate_id: string }>("/intake/create", { method: "POST", body: fd });
};

export const uploadFiles = (id: string, files: Record<string, File>) => {
  const fd = new FormData();
  Object.entries(files).forEach(([k, v]) => fd.append(k, v));
  return apiFetch<{ status: string; message: string }>(`/intake/${id}/upload`, {
    method: "POST",
    body: fd,
  });
};

export const runEvaluation = (id: string) =>
  apiFetch(`/intake/${id}/evaluate`, { method: "POST" });

export const deleteIntake = (id: string) =>
  apiFetch(`/intake/${id}`, { method: "DELETE" });