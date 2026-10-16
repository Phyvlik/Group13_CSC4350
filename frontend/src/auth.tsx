/*
 * Placeholder accounts kept in localStorage so the pages can be navigated.
 * Replace with the real auth endpoints (#6): register, login, profile and the admin user list.
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export interface User {
  id: string;
  name: string;
  email: string;
  pass: string;
  role: "Trader" | "Admin";
  status: "Active" | "Disabled";
}

const USERS_KEY = "epoch.users";
const UID_KEY = "epoch.uid";

const SEED: User[] = [
  { id: "u1", name: "Admin", email: "admin@epoch.test", pass: "admin-demo", role: "Admin", status: "Active" },
  { id: "u2", name: "Demo Trader", email: "demo@epoch.test", pass: "demo-demo", role: "Trader", status: "Active" },
];

function readUsers(): User[] {
  try {
    const raw = JSON.parse(localStorage.getItem(USERS_KEY) ?? "null");
    if (Array.isArray(raw) && raw.length) return raw as User[];
  } catch {
    /* fall through to the seed */
  }
  return SEED;
}

function readUid(): string | null {
  try {
    return localStorage.getItem(UID_KEY);
  } catch {
    return null;
  }
}

interface AuthValue {
  user: User | null;
  users: User[];
  signIn: (email: string, pass: string) => string | null;
  signUp: (name: string, email: string, pass: string, pass2: string) => string | null;
  signOut: () => void;
  updateProfile: (name: string, email: string) => string | null;
  saveUser: (id: string, role: User["role"], status: User["status"]) => string | null;
}

const AuthContext = createContext<AuthValue | null>(null);
const EMAIL = /^\S+@\S+\.\S+$/;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [users, setUsers] = useState<User[]>(readUsers);
  const [uid, setUid] = useState<string | null>(readUid);

  const persist = useCallback((next: User[]) => {
    setUsers(next);
    try {
      localStorage.setItem(USERS_KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable */
    }
  }, []);

  const remember = useCallback((id: string | null) => {
    setUid(id);
    try {
      if (id) localStorage.setItem(UID_KEY, id);
      else localStorage.removeItem(UID_KEY);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const user = useMemo(() => users.find((u) => u.id === uid && u.status === "Active") ?? null, [users, uid]);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      users,
      signIn(email, pass) {
        const e = email.trim().toLowerCase();
        if (!EMAIL.test(e)) return "Enter a valid email address.";
        if (!pass) return "Enter your password.";
        const found = users.find((u) => u.email === e && u.pass === pass);
        if (!found) return "Email or password is incorrect.";
        if (found.status !== "Active") return "This account is disabled. Contact an admin.";
        remember(found.id);
        return null;
      },
      signUp(name, email, pass, pass2) {
        const e = email.trim().toLowerCase();
        if (!name.trim()) return "Enter a display name.";
        if (!EMAIL.test(e)) return "Enter a valid email address.";
        if (pass.length < 8) return "Use at least 8 characters for your password.";
        if (pass !== pass2) return "Passwords do not match.";
        if (users.some((u) => u.email === e)) return "An account with this email already exists.";
        const created: User = { id: "u" + Date.now(), name: name.trim(), email: e, pass, role: "Trader", status: "Active" };
        persist([...users, created]);
        remember(created.id);
        return null;
      },
      signOut: () => remember(null),
      updateProfile(name, email) {
        const e = email.trim().toLowerCase();
        if (!name.trim()) return "Enter a display name.";
        if (!EMAIL.test(e)) return "Enter a valid email address.";
        if (users.some((u) => u.email === e && u.id !== user?.id)) return "That email is already in use.";
        persist(users.map((u) => (u.id === user?.id ? { ...u, name: name.trim(), email: e } : u)));
        return null;
      },
      saveUser(id, role, status) {
        if (id === user?.id && (role !== "Admin" || status !== "Active")) return "You cannot demote or disable your own account.";
        persist(users.map((u) => (u.id === id ? { ...u, role, status } : u)));
        return null;
      },
    }),
    [user, users, persist, remember],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
