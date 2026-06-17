export type UserRole = "hr" | "hm";

export interface AuthUser {
  email: string;
  name: string;
  role: UserRole;
}

const USERS: Record<string, { password: string; user: AuthUser }> = {
  "saba.hr@imperiumdynamics.com": {
    password: "saba123",
    user: { email: "saba.hr@imperiumdynamics.com", name: "Saba", role: "hr" },
  },
  "berkha.hm@imperiumdynamics.com": {
    password: "berkha123",
    user: { email: "berkha.hm@imperiumdynamics.com", name: "Berkha", role: "hm" },
  },
};

const SESSION_KEY = "id_session";

export function login(email: string, password: string): AuthUser | null {
  const entry = USERS[email.toLowerCase().trim()];
  if (!entry || entry.password !== password) return null;
  if (typeof window !== "undefined") {
    localStorage.setItem(SESSION_KEY, JSON.stringify(entry.user));
  }
  return entry.user;
}

export function logout() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(SESSION_KEY);
  }
}

export function getSession(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}
