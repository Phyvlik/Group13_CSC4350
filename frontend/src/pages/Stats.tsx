import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ErrorPanel, Loading, PageHead } from "../components/State";
import { money, pct, signed, tone } from "../format";
import { useLoad } from "../hooks/useLoad";

export default function StatsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const sessions = useLoad(() => api.sessions(), []);
  const scope = id && sessions.data?.some((s) => s.id === id) ? id : "all";
  const stats = useLoad(() => (sessions.data?.length ? api.stats(scope) : Promise.resolve(null)), [sessions.data, scope]);

  if (sessions.error || stats.error) return <ErrorPanel message={sessions.error ?? stats.error ?? ""} />;
  if (!sessions.data || (sessions.data.length > 0 && !stats.data)) return <Loading />;

  const d = stats.data;
  const sm = d?.summary;

  return (
    <>
      <PageHead title="Statistics" sub="Review a completed session or your overall practice performance.">
        <div className="field" style={{ minWidth: 260 }}>
          <label htmlFor="v">View</label>
          <select id="v" value={scope} onChange={(e) => navigate(e.target.value === "all" ? "/stats" : `/stats/${e.target.value}`)}>
            <option value="all">All sessions</option>
            {sessions.data.map((s) => (
              <option key={s.id} value={s.id}>
                {s.sym}, {s.start} to {s.end}
              </option>
            ))}
          </select>
        </div>
      </PageHead>

      {d && sm ? (
        <>
          <div className="stats">
            <div className="stat">
              <div className="label">Profit / loss</div>
              <div className={`v ${tone(d.pl)}`}>{signed(d.pl)}</div>
            </div>
            <div className="stat">
              <div className="label">Win rate</div>
              <div className="v">{pct(d.winRate)}</div>
            </div>
            <div className="stat">
              <div className="label">Risk exposure</div>
              <div className="v">{pct(d.exposure)}</div>
            </div>
            <div className="stat">
              <div className="label">Trades</div>
              <div className="v">{d.trades}</div>
            </div>
          </div>
          <div className="summary">
            <span className="muted">Session summary</span>
            {scope !== "all" ? (
              <>
                <span>Ending cash <b>{money(sm.endingCash ?? 0)}</b></span>
                <span>Open position <b>{sm.openPosition}</b></span>
                <span>Status <b>{sm.status}</b></span>
              </>
            ) : (
              <>
                <span>Sessions <b>{sm.sessions}</b></span>
                <span>Open positions <b>{sm.openPositions}</b></span>
              </>
            )}
          </div>
          <div className="actions">
            <Link className="btn primary" to="/journal">Review journal</Link>
            <Link className="btn" to="/feedback">View feedback</Link>
            <Link className="btn ghost" to="/dashboard">Return to dashboard</Link>
          </div>
        </>
      ) : (
        <div className="panel empty">
          <h2>Nothing to review yet</h2>
          <p>Statistics appear after your first practice session.</p>
          <Link className="btn primary" to="/new">Start new session</Link>
        </div>
      )}
    </>
  );
}
