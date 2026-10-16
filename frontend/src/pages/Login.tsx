import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { MOCK_BARS } from "../api/client";
import { useAuth } from "../auth";
import PriceChart from "../components/PriceChart";

/** Decorative chart: replays on its own, and the pointer scrubs through it. */
function ReplayArt() {
  const reduced = useMemo(() => matchMedia("(prefers-reduced-motion: reduce)").matches, []);
  const [n, setN] = useState(reduced ? 150 : 40);
  const scrubbing = useRef(false);

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => {
      if (!scrubbing.current) setN((v) => (v >= 200 ? 40 : v + 1));
    }, 420);
    return () => clearInterval(id);
  }, [reduced]);

  return (
    <section
      className="auth-art"
      aria-hidden="true"
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        scrubbing.current = true;
        setN(40 + Math.round(((e.clientX - r.left) / r.width) * 160));
      }}
      onPointerLeave={() => {
        scrubbing.current = false;
      }}
    >
      <PriceChart bars={MOCK_BARS.slice(0, n)} window={90} future={24} label="Decorative price chart" />
      <p>Practice on past markets. Decide first, see the outcome after.</p>
    </section>
  );
}

export default function LoginPage({ mode }: { mode: "signin" | "signup" }) {
  const { user, signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const signin = mode === "signin";

  if (user) return <Navigate to={user.role === "Admin" ? "/admin" : "/dashboard"} replace />;

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "");
    const problem = signin
      ? signIn(get("email"), get("pass"))
      : signUp(get("name"), get("email"), get("pass"), get("pass2"));
    if (problem) setError(problem);
    else navigate("/");
  };

  return (
    <div className="auth">
      <section className="auth-form">
        <Link className="logo" to="/login">
          Epoch<i>.</i>
        </Link>
        <h1>{signin ? "Sign in" : "Create account"}</h1>
        <p className="sub">{signin ? "Access your Epoch account." : "Create a trader account to save your practice."}</p>
        <form onSubmit={submit} noValidate>
          {!signin && (
            <div className="field">
              <label htmlFor="n">Display name</label>
              <input id="n" name="name" autoComplete="nickname" />
            </div>
          )}
          <div className="field">
            <label htmlFor="e">Email</label>
            <input id="e" name="email" type="email" autoComplete="email" />
          </div>
          <div className="field">
            <label htmlFor="p">Password</label>
            <input id="p" name="pass" type="password" autoComplete={signin ? "current-password" : "new-password"} />
          </div>
          {!signin && (
            <div className="field">
              <label htmlFor="p2">Confirm password</label>
              <input id="p2" name="pass2" type="password" autoComplete="new-password" />
            </div>
          )}
          <p className="err" role="alert" style={{ marginTop: 12 }}>
            {error}
          </p>
          <button className="btn primary block" type="submit">
            {signin ? "Sign in" : "Create account"}
          </button>
        </form>
        <p className="auth-alt">
          {signin ? (
            <>
              New to Epoch? <Link to="/signup">Create an account</Link>
            </>
          ) : (
            <>
              Already registered? <Link to="/login">Sign in</Link>
            </>
          )}
        </p>
        {signin && (
          <p className="hint" style={{ marginTop: 28 }}>
            Placeholder logins: demo@epoch.test / demo-demo (trader), admin@epoch.test / admin-demo (admin).
          </p>
        )}
      </section>
      <ReplayArt />
    </div>
  );
}
