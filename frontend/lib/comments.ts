const KEY = "hm_decision_comments";

function load(): Record<string, { comment: string; decision: string; committedAt: string }> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}");
  } catch {
    return {};
  }
}

export function saveComment(candidateId: string, decision: string, comment: string) {
  const store = load();
  store[candidateId] = { comment, decision, committedAt: new Date().toISOString() };
  localStorage.setItem(KEY, JSON.stringify(store));
}

export function getComment(candidateId: string): { comment: string; decision: string; committedAt: string } | null {
  return load()[candidateId] ?? null;
}

export function getAllComments(): Record<string, { comment: string; decision: string; committedAt: string }> {
  return load();
}
