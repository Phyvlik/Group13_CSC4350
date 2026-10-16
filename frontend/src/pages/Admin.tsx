import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth, type User } from "../auth";
import { ErrorPanel, Loading, PageHead } from "../components/State";
import { useToast } from "../components/Toasts";
import { useLoad } from "../hooks/useLoad";

export default function AdminPage() {
  const { user, users, saveUser } = useAuth();
  const toast = useToast();
  const datasets = useLoad(() => api.datasets(), []);
  const usage = useLoad(() => api.usage(), []);
  const [find, setFind] = useState("");
  const [pick, setPick] = useState<string | null>(null);
  const [role, setRole] = useState<User["role"]>("Trader");
  const [status, setStatus] = useState<User["status"]>("Active");
  const [userError, setUserError] = useState("");
  const [symbol, setSymbol] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dataError, setDataError] = useState("");

  if (user?.role !== "Admin") return <Navigate to="/dashboard" replace />;
  if (datasets.error || usage.error) return <ErrorPanel message={datasets.error ?? usage.error ?? ""} />;
  if (!datasets.data || !usage.data) return <Loading />;

  const f = find.toLowerCase();
  const shown = users.filter((u) => !f || (u.email + u.name).toLowerCase().includes(f));

  const choose = (u: User) => {
    setPick(u.id);
    setRole(u.role);
    setStatus(u.status);
    setUserError("");
  };

  const submitUser = (e: FormEvent) => {
    e.preventDefault();
    if (!pick) return;
    const problem = saveUser(pick, role, status);
    setUserError(problem ?? "");
    if (!problem) toast("User saved.");
  };

  const submitData = async (e: FormEvent) => {
    e.preventDefault();
    setDataError("");
    const sym = symbol.trim().toUpperCase();
    if (!sym) return setDataError("Select or type an instrument.");
    if (!file) return setDataError("Choose a CSV file to import.");
    try {
      await api.importDataset(sym, file);
      toast(`Import request sent for ${sym}.`);
    } catch (x) {
      setDataError(x instanceof Error ? x.message : "Import failed.");
    }
  };

  return (
    <>
      <PageHead title="Admin workspace" sub="Manage historical data and user accounts." />
      <div className="stats three" style={{ marginBottom: 28 }}>
        <div className="stat"><div className="label">Users</div><div className="v">{users.length}</div></div>
        <div className="stat"><div className="label">Active sessions</div><div className="v">{usage.data.activeSessions}</div></div>
        <div className="stat"><div className="label">Stored datasets</div><div className="v">{usage.data.datasets}</div></div>
      </div>

      <div className="grid-2 grid-admin">
        <section className="panel pad">
          <h2 style={{ marginBottom: 16 }}>Historical market data</h2>
          <form onSubmit={submitData} noValidate>
            <div className="field">
              <label htmlFor="di">Instrument</label>
              <input id="di" list="dl" placeholder="Select or type a symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} />
              <datalist id="dl">{datasets.data.map((d) => <option key={d.sym} value={d.sym} />)}</datalist>
            </div>
            <div className="field">
              <label htmlFor="dfile">Dataset file</label>
              <input id="dfile" type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              <span className="hint">CSV with columns date, open, high, low, close. One row per day.</span>
            </div>
            <p className="err" role="alert" style={{ marginTop: 10 }}>{dataError}</p>
            <button className="btn primary" type="submit" style={{ marginTop: 16 }}>Import dataset</button>
          </form>
          <div className="divide" style={{ marginTop: 24 }}>
            {datasets.data.map((d) => (
              <div key={d.sym} style={{ padding: "12px 0" }}>
                <b>{d.sym}</b> <span className="muted mono">1D / {d.range}</span> <span className="tag">{d.status}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel pad">
          <h2 style={{ marginBottom: 16 }}>User accounts</h2>
          <div className="field">
            <label htmlFor="uf">Find a user</label>
            <input id="uf" placeholder="Email or display name" value={find} onChange={(e) => setFind(e.target.value)} />
          </div>
          <div className="panel divide clip" style={{ marginTop: 14 }}>
            {shown.length ? (
              shown.map((u) => (
                <button key={u.id} className="list-item" aria-selected={u.id === pick} onClick={() => choose(u)}>
                  <div className="li-top"><span>{u.name}</span><span className="muted">{u.role} / {u.status}</span></div>
                  <div className="li-sub">{u.email}</div>
                </button>
              ))
            ) : (
              <div className="empty" style={{ padding: 28 }}>No users match.</div>
            )}
          </div>
          <form onSubmit={submitUser} style={{ marginTop: 18 }} noValidate>
            <div className="row">
              <div className="field">
                <label htmlFor="ur">Role</label>
                <select id="ur" value={role} onChange={(e) => setRole(e.target.value as User["role"])}>
                  <option>Trader</option>
                  <option>Admin</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="us">Status</label>
                <select id="us" value={status} onChange={(e) => setStatus(e.target.value as User["status"])}>
                  <option>Active</option>
                  <option>Disabled</option>
                </select>
              </div>
            </div>
            <p className="err" role="alert" style={{ marginTop: 10 }}>{userError}</p>
            <button className="btn primary" type="submit" style={{ marginTop: 16 }} disabled={!pick}>Save user</button>
          </form>
        </section>
      </div>
    </>
  );
}
