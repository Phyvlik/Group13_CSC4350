/*
 * Signed-in user state backed by the auth API: POST /auth/register, POST /auth/login, GET /auth/me, PATCH /auth/me.
 * The access token is kept in localStorage and sent as a Bearer header by the api client.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, getToken, http, setToken } from "./api/http";

export interface User {
  id: string;
  name: string;
  email: string;
  role: "Trader" | "Admin";
  status: "Active" | "Disabled";
}

interface AuthResponse {
  user: User;
  access_token: string;
}

interface AuthValue {
  user: User | null;
  /** False until a stored token has been checked against GET /auth/me. */
  ready: boolean;
  signIn: (email: string, pass: string) => Promise<string | null>;
  signUp: (name: string, email: string, pass: string, pass2: string) => Promise<string | null>;
  signOut: () => void;
  updateProfile: (name: string, email: string) => Promise<string | null>;
}

const AuthContext = createContext<AuthValue | null>(null);
const EMAIL = /^\S+@\S+\.\S+$/;

const problem = (x: unknown, fallback: string) => (x instanceof Error && x.message ? x.message : fallback);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(() => !getToken());

  useEffect(() => {
    if (!getToken()) return;
    let alive = true;
    http
      .get<User>("/auth/me")
      .then((me) => alive && setUser(me))
      .catch(() => {
        // An expired or revoked token just means signing in again.
        if (alive) setToken(null);
      })
      .finally(() => alive && setReady(true));
    return () => {
      alive = false;
    };
  }, []);

  const accept = useCallback((res: AuthResponse) => {
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      ready,
      async signIn(email, pass) {
        const e = email.trim().toLowerCase();
        if (!EMAIL.test(e)) return "Enter a valid email address.";
        if (!pass) return "Enter your password.";
        try {
          accept(await http.post<AuthResponse>("/auth/login", { email: e, password: pass }));
          return null;
        } catch (x) {
          // The API answers 401 for a wrong password and for a disabled account alike.
          if (x instanceof ApiError && x.status === 401) return "Email or password is incorrect, or the account is disabled.";
          return problem(x, "Could not sign in.");
        }
      },
      async signUp(name, email, pass, pass2) {
        const e = email.trim().toLowerCase();
        if (!name.trim()) return "Enter a display name.";
        if (!EMAIL.test(e)) return "Enter a valid email address.";
        if (pass.length < 8) return "Use at least 8 characters for your password.";
        if (pass !== pass2) return "Passwords do not match.";
        try {
          accept(await http.post<AuthResponse>("/auth/register", { email: e, password: pass, display_name: name.trim() }));
          return null;
        } catch (x) {
          if (x instanceof ApiError && x.status === 409) return "An account with this email already exists.";
          return problem(x, "Could not create the account.");
        }
      },
      signOut() {
        setToken(null);
        setUser(null);
      },
      async updateProfile(name, email) {
        if (!name.trim()) return "Enter a display name.";
        // TODO: PATCH /auth/me does not accept an email change yet, so only the display name is saved.
        if (email.trim().toLowerCase() !== user?.email) return "Changing your email is not supported yet.";
        try {
          setUser(await http.patch<User>("/auth/me", { display_name: name.trim() }));
          return null;
        } catch (x) {
          return problem(x, "Could not save the profile.");
        }
      },
    }),
    [user, ready, accept],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
