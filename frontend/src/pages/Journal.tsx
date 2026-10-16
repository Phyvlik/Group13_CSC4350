import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { TradeRow } from "../api/types";
import { ErrorPanel, Loading, PageHead } from "../components/State";
import { useToast } from "../components/Toasts";
import { price, qtyText, signed, tone } from "../format";
import { useLoad } from "../hooks/useLoad";

export default function JournalPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data, error: loadError } = useLoad(() => api.trades(), []);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [query, setQuery] = useState("");
  const [term, setTerm] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (data) setTrades([...data].reverse());
  }, [data]);
  useEffect(() => {
    setEditing(false);
    setError("");
  }, [id]);

  if (loadError) return <ErrorPanel message={loadError} />;
  if (!data) return <Loading />;

  const rows = trades.filter((t) => !term || `${t.sym} ${t.reasoning} ${t.id}`.toLowerCase().includes(term));
  const selected = trades.find((t) => t.id === id);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    if (!draft.trim()) return setError("Reasoning cannot be empty.");
    try {
      await api.updateReasoning(selected.id, draft.trim());
      setTrades((cur) => cur.map((t) => (t.id === selected.id ? { ...t, reasoning: draft.trim() } : t)));
      setEditing(false);
      setError("");
      toast("Reasoning updated.");
    } catch (x) {
      setError(x instanceof Error ? x.message : "Could not save.");
    }
  };

  return (
    <>
      <PageHead title="Trade journal" sub="Browse, search, and edit the reasoning saved with each trade." />
      <form
        className="search"
        onSubmit={(e) => {
          e.preventDefault();
          setTerm(query.trim().toLowerCase());
        }}
      >
        <div className="field" style={{ flex: 1 }}>
          <label htmlFor="sq">Search journal</label>
          <input id="sq" type="search" placeholder="Instrument or text" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <button className="btn" type="submit" style={{ alignSelf: "end" }}>Search</button>
      </form>

      <div className="grid-2 grid-journal">
        <div className="panel divide clip">
          {rows.length ? (
            rows.map((t) => (
              <button key={t.id} className="list-item" aria-selected={t.id === id} onClick={() => navigate(`/journal/${t.id}`)}>
                <div className="li-top">
                  <span>
                    {t.sym} <span className={t.side === "buy" ? "gain" : "loss"}>{t.side === "buy" ? "Buy" : "Sell"}</span>
                  </span>
                  <span className="mono">{qtyText(t.qty)} @ {price(t.price)}</span>
                </div>
                <div className="li-sub">{t.ts} / {t.id}</div>
              </button>
            ))
          ) : (
            <div className="empty">
              <h2>{trades.length ? "No matches" : "No trades saved"}</h2>
              <p>{trades.length ? "Try a different instrument or word." : "Trades and their reasoning appear here after you practice."}</p>
              {!trades.length && <Link className="btn primary" to="/new">Start new session</Link>}
            </div>
          )}
        </div>

        <div className="panel pad">
          {selected ? (
            <>
              <h2>{selected.sym} {selected.side === "buy" ? "buy" : "sale"}</h2>
              <div className="meta">
                <span>Trade <b>{selected.id}</b></span>
                <span>Session <b>{selected.sid}</b></span>
                <span>Time <b>{selected.ts}</b></span>
                <span>Quantity <b>{qtyText(selected.qty)}</b></span>
                <span>Price <b>{price(selected.price)}</b></span>
                {selected.pnl != null && <span>Result <b className={tone(selected.pnl)}>{signed(selected.pnl)}</b></span>}
              </div>
              <form onSubmit={save} noValidate>
                <div className="field">
                  <label htmlFor="rs">Reasoning</label>
                  <textarea id="rs" style={{ minHeight: 150 }} readOnly={!editing} value={editing ? draft : selected.reasoning} onChange={(e) => setDraft(e.target.value)} />
                </div>
                <p className="err" role="alert" style={{ marginTop: 10 }}>{error}</p>
                <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
                  {editing ? (
                    <>
                      <button className="btn primary" type="submit">Save changes</button>
                      <button className="btn" type="button" onClick={() => { setEditing(false); setError(""); }}>Cancel edit</button>
                    </>
                  ) : (
                    <button className="btn" type="button" onClick={() => { setDraft(selected.reasoning); setEditing(true); }}>Edit reasoning</button>
                  )}
                </div>
              </form>
            </>
          ) : (
            <div className="empty">
              <h2>Select a trade</h2>
              <p>Choose a trade from the list to view or edit its reasoning.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
