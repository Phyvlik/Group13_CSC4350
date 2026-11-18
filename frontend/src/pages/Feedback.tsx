import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { HabitMetric, Habits } from "../api/feedbackTypes";
import { Loading, PageHead } from "../components/State";
import { useLoad } from "../hooks/useLoad";

const message = (error: unknown) => error instanceof Error ? error.message : "Could not complete the request.";
const timestamp = (value: string) => new Date(value).toLocaleString();
// Trim trailing zeros without rounding.
const decimal = (value: string) => value.includes(".") ? value.replace(/0+$/, "").replace(/\.$/, "") : value;

function SessionFeedback({ id, onAnalyzed }: { id: string; onAnalyzed: () => void }) {
  const [reload, setReload] = useState(0);
  const { data, error, setData } = useLoad(() => api.feedback(id), [id, reload]);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [analyzed, setAnalyzed] = useState(false);
  const pending = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  const analyze = async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setActionError("");
    try {
      const result = await api.recomputeFeedback(id);
      if (!alive.current) return;
      setData(result);
      setAnalyzed(true);
      onAnalyzed();
    } catch (e) {
      if (alive.current) setActionError(message(e));
    } finally {
      pending.current = false;
      if (alive.current) setBusy(false);
    }
  };

  return <>
    <div className="feedback-actions">
      <button className="btn primary" disabled={busy || (!data && !error)} onClick={analyze}>
        {busy ? "Analyzing…" : "Analyze session"}
      </button>
      <p className="hint">Creates a verified snapshot from this session’s trades and saved journal context.</p>
    </div>
    {actionError && <p className="err" role="alert">{actionError}</p>}
    {error && !analyzed ? <div role="alert">
      <p>{error}</p><button className="btn small" disabled={busy} onClick={() => setReload((n) => n + 1)}>Retry feedback</button>
    </div> : !data ? <Loading /> : <div aria-live="polite" aria-busy={busy}>
      {data.status === "not_computed" ? <div className="empty">
        <h2>Session not analyzed yet</h2>
        <p>Select Analyze session to check its saved trading history.</p>
      </div> : <>
        {data.metric && <p className="hint feedback-snapshot">
          Verified snapshot: {decimal(data.metric.value)} qualifying events · revision {data.metric.revision}<br />
          Verified {timestamp(data.metric.verified_at)} · rule {data.analysis_version}
        </p>}
        <p className="hint">Snapshots describe saved history. Analyze again after new trades or journal edits.</p>
        {data.feedback.length ? data.feedback.map((item) => <article key={item.feedback_id} className="pattern feedback-pattern">
          <h2>{item.pattern_code === "LOSS_CHASING" ? "Larger positions after losses" : item.pattern_code}</h2>
          <p>{item.explanation}</p>
          {item.evidence.map((evidence) => <div key={evidence.session_metric_id} className="feedback-evidence">
            <h3>Verified evidence</h3>
            <p>{evidence.evidence_reason}</p>
            <p className="hint">{evidence.metric_code}: {decimal(evidence.value)} · verified {timestamp(evidence.verified_at)}</p>
            <ul className="feedback-trades">
              {evidence.trade_ids.map((tradeId) => <li key={tradeId}>
                <Link to={`/journal/${encodeURIComponent(tradeId)}`}>View trade {tradeId}</Link>
              </li>)}
            </ul>
            {evidence.journal_entries.map((entry) => <blockquote key={entry.trade_id}>
              <p>{entry.reasoning}</p>
              <small>Saved reasoning for trade {entry.trade_id}</small>
            </blockquote>)}
          </div>)}
        </article>) : <div className="empty">
          <h2>No recurring pattern found</h2>
          <p>This snapshot did not meet the rule’s sample-size and recurrence thresholds. It does not prove that a habit is absent.</p>
        </div>}
      </>}
    </div>}
  </>;
}

function History({ metric, version }: { metric: HabitMetric; version: number }) {
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const { data, error } = useLoad(() => api.habitHistory(metric.metric_id, offset), [metric.metric_id, offset, version, retry]);
  return <section aria-label="Metric history" className="feedback-history">
    <h2>Trend across sessions</h2>
    <p>{metric.name} · {metric.unit}</p>
    <p className="hint">Latest verified snapshot per session, newest first. Missing or undefined values are omitted, never filled with zero. Each currency is shown separately.</p>
    {error ? <div role="alert"><p>{error}</p><button className="btn small" onClick={() => setRetry((n) => n + 1)}>Retry history</button></div>
      : !data ? <Loading /> : <>
        {!data.points.length ? <p className="hint">No verified history on this page. Analyze sessions for loss-chasing counts, or recompute statistics for other metrics.</p> : <>
        <div className="feedback-table-wrap"><table className="table">
          <caption className="hint">Saved values · rule {data.calculation_version}</caption>
          <thead><tr><th scope="col">Session</th><th scope="col">Value</th><th scope="col">Verified</th></tr></thead>
          <tbody>{data.points.map((point) => <tr key={point.session_id}>
            <td><Link to={`/stats/${encodeURIComponent(point.session_id)}`}>{point.session_id.slice(0, 8)}</Link><br /><small>{timestamp(point.started_at)}</small></td>
            <td>{decimal(point.value)} {data.unit === "quote currency" ? point.quote_currency : data.unit}<br /><small>{point.quote_currency}</small></td>
            <td><small>{timestamp(point.verified_at)}<br />Revision {point.revision}</small></td>
          </tr>)}</tbody>
        </table></div></>}
        <div className="feedback-actions">
          <button className="btn small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - data.limit))}>Newer sessions</button>
          <button className="btn small" disabled={!data.has_more} onClick={() => setOffset(offset + data.limit)}>Older sessions</button>
        </div>
      </>}
  </section>;
}

function HabitTracking({ initial, version }: { initial: Habits; version: number }) {
  const [catalog, setCatalog] = useState(initial);
  const activeId = catalog.tracked.find((habit) => habit.active)?.metric_id ?? "";
  const [pick, setPick] = useState(activeId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const pending = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const chosen = catalog.metrics.find((metric) => metric.metric_id === pick);
  const active = catalog.metrics.find((metric) => metric.metric_id === activeId);

  const save = async (event?: FormEvent, enabled = true) => {
    event?.preventDefault();
    const id = enabled ? pick : activeId;
    if (!id || pending.current) return;
    pending.current = true;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.saveTracked(id, enabled);
      if (!alive.current) return;
      setCatalog(result);
      setPick(result.tracked.find((habit) => habit.active)?.metric_id ?? "");
      setNotice(enabled ? "Saved. Your metric is now tracked." : "Tracking stopped. Saved observations are kept.");
    } catch (e) {
      if (alive.current) setError(message(e));
    } finally {
      pending.current = false;
      if (alive.current) setBusy(false);
    }
  };
  return <>
    <form onSubmit={(event) => save(event)}>
      <div className="field">
        <label htmlFor="tracked-metric">Habit or metric to track</label>
        <select id="tracked-metric" value={pick} disabled={busy} onChange={(event) => { setPick(event.target.value); setNotice(""); }}>
          <option value="">Select a habit or metric</option>
          {catalog.metrics.map((metric) => <option key={metric.metric_id} value={metric.metric_id}>{metric.name} ({metric.unit})</option>)}
        </select>
      </div>
      {chosen && <details className="feedback-rule"><summary>How this metric is calculated</summary><p>{chosen.calculation_rule}</p><small>Rule {chosen.calculation_version}</small></details>}
      <div className="feedback-actions">
        <button className="btn primary" type="submit" disabled={!pick || busy}>{busy ? "Saving…" : "Save selection"}</button>
        {activeId && <button className="btn" type="button" disabled={busy} onClick={() => save(undefined, false)}>Stop tracking</button>}
      </div>
    </form>
    {error && <p className="err" role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {active ? <History key={active.metric_id} metric={active} version={version} /> : <p className="hint">Choose and save a metric to view its history across your sessions.</p>}
  </>;
}

export default function FeedbackPage() {
  const [retry, setRetry] = useState(0);
  const [olderSessions, setOlderSessions] = useState<Awaited<ReturnType<typeof api.feedbackSessions>> | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [olderError, setOlderError] = useState("");
  const olderPending = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const { data, error } = useLoad(async () => {
    const [sessions, habits] = await Promise.all([api.feedbackSessions(), api.habits()]);
    return { sessions, habits };
  }, [retry]);
  const loadOlder = async () => {
    if (olderPending.current) return;
    olderPending.current = true;
    setLoadingOlder(true); setOlderError("");
    try {
      const sessions = await api.feedbackSessions(true);
      if (alive.current) setOlderSessions(sessions);
    } catch (e) {
      if (alive.current) setOlderError(message(e));
    } finally {
      olderPending.current = false;
      if (alive.current) setLoadingOlder(false);
    }
  };
  const [selected, setSelected] = useState("");
  const [historyVersion, setHistoryVersion] = useState(0);
  const sessions = olderSessions ?? data?.sessions ?? [];
  const sessionId = selected || sessions[0]?.id || "";

  return <>
    <PageHead title="Behavior feedback" sub="Review verified trading patterns and track a metric across sessions." />
    {error ? <div className="panel empty" role="alert"><p>{error}</p><button className="btn" onClick={() => setRetry((n) => n + 1)}>Retry</button></div>
      : !data ? <Loading /> : <div className="grid-2 grid-feedback">
        <section className="panel pad" aria-label="Session feedback">
          {sessions.length ? <>
            <div className="field">
              <label htmlFor="feedback-session">Practice session</label>
              <select id="feedback-session" value={sessionId} onChange={(event) => setSelected(event.target.value)}>
                {sessions.map((session) => <option key={session.id} value={session.id}>{session.label}</option>)}
              </select>
              {!olderSessions && data.sessions.length === 100 && <button className="btn small" disabled={loadingOlder} onClick={loadOlder}>{loadingOlder ? "Loading sessions…" : "Load older sessions"}</button>}
              {olderError && <p className="err" role="alert">{olderError}</p>}
            </div>
            <SessionFeedback key={sessionId} id={sessionId} onAnalyzed={() => setHistoryVersion((n) => n + 1)} />
          </> : <div className="empty"><h2>No practice sessions yet</h2><p>Start a practice session to build your trading history.</p><Link className="btn primary" to="/new">Start new session</Link></div>}
        </section>
        <aside className="panel pad" aria-label="Habit tracking"><HabitTracking initial={data.habits} version={historyVersion} /></aside>
      </div>}
  </>;
}
