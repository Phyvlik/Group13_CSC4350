import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { ErrorPanel, Loading, PageHead } from "../components/State";
import { signed, tone } from "../format";
import { useLoad } from "../hooks/useLoad";

export default function DashboardPage() {
  const { user } = useAuth();
  const { data, error } = useLoad(() => api.sessions(), []);

  if (error) return <ErrorPanel message={error} />;
  if (!data) return <Loading />;
  const sessions = [...data].reverse();

  return (
    <>
      <PageHead title="Dashboard" sub={`Welcome back, ${user?.name}. Choose a session or start a new practice.`}>
        <Link className="btn primary" to="/new">
          Start new session
        </Link>
      </PageHead>
      <h2 style={{ marginBottom: 12 }}>Practice sessions</h2>
      <div className="panel scroll-x">
        {sessions.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Instrument</th>
                <th>Historical period</th>
                <th>Status</th>
                <th>Profit / loss</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => {
                const live = s.status === "In progress";
                return (
                  <tr key={s.id}>
                    <td>
                      <b>{s.sym}</b>
                    </td>
                    <td className="mono">
                      {s.start} to {s.end}
                    </td>
                    <td>
                      <span className={live ? "tag live" : "tag"}>{s.status}</span>
                    </td>
                    <td className={`mono ${tone(s.pl)}`}>{signed(s.pl)}</td>
                    <td className="r">
                      <Link className="btn small" to={live ? `/replay/${s.id}` : `/stats/${s.id}`}>
                        {live ? "Resume" : "Results"}
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="empty">
            <h2>No sessions yet</h2>
            <p>Pick an instrument and a past period to place your first practice trade.</p>
            <Link className="btn primary" to="/new">
              Start new session
            </Link>
          </div>
        )}
      </div>
    </>
  );
}
