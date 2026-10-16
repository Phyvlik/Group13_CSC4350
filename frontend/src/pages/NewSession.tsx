import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { ErrorPanel, Loading, PageHead } from "../components/State";
import { useLoad } from "../hooks/useLoad";

export default function NewSessionPage() {
  const navigate = useNavigate();
  const { data: instruments, error: loadError } = useLoad(() => api.instruments(), []);
  const [sym, setSym] = useState("");
  const [error, setError] = useState("");

  if (loadError) return <ErrorPanel message={loadError} />;
  if (!instruments) return <Loading />;
  const chosen = instruments.find((i) => i.sym === sym);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const start = String(f.get("start") ?? "");
    const end = String(f.get("end") ?? "");
    setError("");
    if (!sym) return setError("Select an instrument.");
    if (!start || !end) return setError("Enter both a start and an end date.");
    if (start >= end) return setError("The end date must be after the start date.");
    try {
      const created = await api.createSession({ sym, start, end });
      navigate(`/replay/${created.id}`);
    } catch (x) {
      setError(x instanceof Error ? x.message : "Could not start the session.");
    }
  };

  return (
    <>
      <PageHead title="New practice session" sub="Choose one instrument and a historical period." />
      <form className="panel pad" style={{ maxWidth: 560 }} onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="i">Instrument</label>
          <select id="i" value={sym} onChange={(e) => setSym(e.target.value)}>
            <option value="">Select an instrument</option>
            {instruments.map((i) => (
              <option key={i.sym} value={i.sym}>
                {i.sym} - {i.name}
              </option>
            ))}
          </select>
        </div>
        <div className="row" style={{ marginTop: 16 }}>
          <div className="field">
            <label htmlFor="a">Start date</label>
            <input id="a" name="start" type="date" min={chosen?.from} max={chosen?.to} />
          </div>
          <div className="field">
            <label htmlFor="b">End date</label>
            <input id="b" name="end" type="date" min={chosen?.from} max={chosen?.to} />
          </div>
        </div>
        <p className="hint" style={{ marginTop: 10 }}>
          {chosen ? `Available: ${chosen.from} to ${chosen.to}.` : "Pick an instrument to see its available dates."}
        </p>
        <p className="hint" style={{ marginTop: 14 }}>
          Virtual starting cash is assigned when the session starts.
        </p>
        <p className="err" role="alert" style={{ marginTop: 12 }}>
          {error}
        </p>
        <div style={{ display: "flex", gap: 10, marginTop: 22 }}>
          <button className="btn primary" type="submit">
            Start practice
          </button>
          <Link className="btn" to="/dashboard">
            Cancel
          </Link>
        </div>
      </form>
    </>
  );
}
