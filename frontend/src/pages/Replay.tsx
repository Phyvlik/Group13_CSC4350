import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ReplayState } from "../api/types";
import PriceChart from "../components/PriceChart";
import { ErrorPanel, Loading, PageHead } from "../components/State";
import { useToast } from "../components/Toasts";
import { money, price, qtyText, tone } from "../format";
import { useLoad } from "../hooks/useLoad";

export default function ReplayPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data: state, error: loadError, setData } = useLoad<ReplayState>(() => api.replay(id), [id]);
  const [pace, setPace] = useState(1);
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [qty, setQty] = useState("");
  const [why, setWhy] = useState("");
  const [error, setError] = useState("");

  if (loadError) return <ErrorPanel message={loadError} />;
  if (!state) return <Loading />;

  const last = state.bars[state.bars.length - 1];
  const prev = state.bars[state.bars.length - 2] ?? last;
  const change = (last.close / prev.close - 1) * 100;
  const step = Math.min(pace, state.remaining);
  const orderValue = (parseFloat(qty) || 0) * last.close;

  const reveal = async () => {
    try {
      setData(await api.reveal(id, pace));
    } catch (x) {
      toast(x instanceof Error ? x.message : "Could not reveal the next bar.");
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    const amount = parseFloat(qty);
    if (!(amount > 0)) return setError("Enter a quantity greater than zero.");
    if (!why.trim()) return setError("Add your reasoning before saving the trade.");
    try {
      const result = await api.placeTrade(id, { side, qty: amount, reasoning: why.trim() });
      setData({ ...state, account: result.account });
      setQty("");
      setWhy("");
      toast(`${result.trade.id} saved to your journal.`);
    } catch (x) {
      setError(x instanceof Error ? x.message : "Could not save the trade.");
    }
  };

  const end = async () => {
    if (state.account.position > 0 && !confirm("You still hold an open position. It will be marked at the current price. End the session?")) return;
    try {
      await api.endSession(id);
      navigate(`/stats/${id}`);
    } catch (x) {
      toast(x instanceof Error ? x.message : "Could not end the session.");
    }
  };

  return (
    <>
      <PageHead title="Practice replay" sub="Replay historical prices and save a practice trade." />
      <div className="grid-2">
        <div>
          <div className="panel chart-wrap">
            <div className="chart-top">
              <div>
                <span className="sym">{state.session.sym}</span> <span className="muted mono">| {last.time}</span>
              </div>
              <div className="mono">
                {price(last.close)} <span className={tone(change)}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</span>
              </div>
            </div>
            <PriceChart bars={state.bars} label={`Historical price chart for ${state.session.sym}. Future prices are hidden.`} />
          </div>
          <div className="pace">
            <div className="field">
              <label htmlFor="pace">Replay pace</label>
              <select id="pace" value={pace} onChange={(e) => setPace(+e.target.value)}>
                <option value={1}>1 bar at a time</option>
                <option value={5}>5 bars at a time</option>
                <option value={10}>10 bars at a time</option>
              </select>
            </div>
            <button className="btn" type="button" disabled={state.remaining === 0} onClick={reveal}>
              {state.remaining === 0 ? "Period complete" : step === 1 ? "Reveal next bar" : `Reveal next ${step} bars`}
            </button>
          </div>
        </div>

        <aside className="stack">
          <div className="panel account">
            <div>
              <div className="label">Cash</div>
              <div className="v">{money(state.account.cash)}</div>
            </div>
            <div>
              <div className="label">Position</div>
              <div className="v">{qtyText(state.account.position)}</div>
            </div>
            <div>
              <div className="label">Equity</div>
              <div className="v">{money(state.account.equity)}</div>
            </div>
          </div>

          <form className="panel pad" onSubmit={submit} noValidate>
            <div className="field">
              <span className="label">Side</span>
              <div className="seg" role="radiogroup" aria-label="Side">
                <input type="radio" name="side" id="sb" value="buy" checked={side === "buy"} onChange={() => setSide("buy")} />
                <label htmlFor="sb">Buy</label>
                <input type="radio" name="side" id="ss" value="sell" checked={side === "sell"} onChange={() => setSide("sell")} />
                <label htmlFor="ss">Sell</label>
              </div>
            </div>
            <div className="field">
              <label htmlFor="q">Quantity</label>
              <input id="q" type="number" min="0" step="any" inputMode="decimal" placeholder="Enter amount" value={qty} onChange={(e) => setQty(e.target.value)} />
              <span className="hint">Order value {money(orderValue)}</span>
            </div>
            <div className="field">
              <label htmlFor="r">Trade reasoning</label>
              <textarea id="r" placeholder="Why are you making this trade?" value={why} onChange={(e) => setWhy(e.target.value)} />
            </div>
            <p className="err" role="alert" style={{ marginTop: 12 }}>
              {error}
            </p>
            <button className="btn primary block" type="submit" style={{ marginTop: 16 }}>
              Save trade and reasoning
            </button>
          </form>

          <button className="btn block" type="button" onClick={end}>
            End session / Results
          </button>
        </aside>
      </div>
    </>
  );
}
