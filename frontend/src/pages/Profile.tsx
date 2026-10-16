import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { PageHead } from "../components/State";
import { useToast } from "../components/Toasts";

export default function ProfilePage() {
  const { user, updateProfile } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [error, setError] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const problem = updateProfile(name, email);
    setError(problem ?? "");
    if (!problem) toast("Profile saved.");
  };

  return (
    <>
      <PageHead title="Profile" sub="View and update your profile." />
      <form className="panel pad" style={{ maxWidth: 520 }} onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="n">Display name</label>
          <input id="n" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="e">Email</label>
          <input id="e" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <p className="hint" style={{ marginTop: 16 }}>
          Role: <b style={{ color: "var(--text)" }}>{user?.role}</b>
        </p>
        <p className="err" role="alert" style={{ marginTop: 10 }}>{error}</p>
        <div style={{ display: "flex", gap: 10, marginTop: 22 }}>
          <button className="btn primary" type="submit">Save profile</button>
          <Link className="btn" to="/dashboard">Cancel</Link>
        </div>
      </form>
    </>
  );
}
