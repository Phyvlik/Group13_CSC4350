import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ErrorPanel, Loading, PageHead } from "../components/State";
import { useToast } from "../components/Toasts";
import { useLoad } from "../hooks/useLoad";

export default function FeedbackPage() {
  const toast = useToast();
  const [version, setVersion] = useState(0);
  const { data, error } = useLoad(() => api.feedback(), [version]);
  const [pick, setPick] = useState<string | null>(null);

  if (error) return <ErrorPanel message={error} />;
  if (!data) return <Loading />;

  const chosen = pick ?? data.tracked;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!chosen) return toast("Select a habit or metric first.");
    try {
      await api.saveTracked(chosen);
      toast("Saved. Your tracked metric was updated.");
      setPick(null);
      setVersion((v) => v + 1);
    } catch (x) {
      toast(x instanceof Error ? x.message : "Could not save.");
    }
  };

  return (
    <>
      <PageHead title="Behavior feedback" sub="Review trading habits and choose a metric to track." />
      <div className="grid-2 grid-feedback">
        <section className="panel pad">
          {data.patterns.length ? (
            data.patterns.map((p) => (
              <div key={p.title} className="pattern">
                <h2>{p.title}</h2>
                <dl>
                  <dt>Explanation</dt>
                  <dd>{p.explanation}</dd>
                  <dt>Evidence</dt>
                  <dd>
                    {p.tradeIds.map((t) => (
                      <span key={t} className="chip">{t}</span>
                    ))}
                    <div style={{ marginTop: 6 }}>{p.evidence}</div>
                  </dd>
                </dl>
                <Link className="btn small" style={{ marginTop: 18 }} to={`/journal/${p.tradeIds[0]}`}>
                  Review supporting trades in Journal
                </Link>
              </div>
            ))
          ) : (
            <div className="empty">
              <h2>No feedback yet</h2>
              <p>Complete a few practice sessions and Epoch will look for repeated habits.</p>
              <Link className="btn primary" to="/new">Start new session</Link>
            </div>
          )}
        </section>

        <aside className="panel pad">
          <form onSubmit={save}>
            <div className="field">
              <label htmlFor="m">Habit or metric to track</label>
              <select id="m" value={chosen} onChange={(e) => setPick(e.target.value)}>
                <option value="">Select a habit or metric</option>
                {data.metrics.map((m) => (
                  <option key={m.key} value={m.key}>{m.label}</option>
                ))}
              </select>
            </div>
            <button className="btn primary block" type="submit" style={{ marginTop: 16 }}>Save selection</button>
          </form>
          <div style={{ marginTop: 26 }}>
            <h2>Trend across sessions</h2>
            {data.tracked && data.trend.length ? (
              <div className="trend">
                {data.trend.map((t) => (
                  <div key={t.label} className="pt">
                    <small>{t.label}</small>
                    {t.value}
                  </div>
                ))}
              </div>
            ) : (
              <p className="hint" style={{ marginTop: 8 }}>Choose a metric above to follow it session by session.</p>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}
