/*
 * API client used by the pages. Each function calls the backend and maps its response to the shapes in ./types,
 * so the pages do not depend on backend field names. Nothing here calculates trading results.
 *
 * Still placeholder, because no backend endpoint exists yet (search for TODO):
 *   trade reasoning (journal entries), behavior feedback, and CSV dataset upload.
 */
import { http } from "./http";
import { MOCK_BARS } from "./mockBars";
import type {
  AdminUser,
  Bar,
  Dataset,
  FeedbackData,
  Instrument,
  ReplayState,
  SessionRow,
  StatsData,
  TradeInput,
  TradeRow,
  Usage,
} from "./types";

/* Backend response shapes (see docs/api.md). Decimals arrive as strings. */
type Num = string;

interface DatasetOut {
  dataset_id: string;
  interval: string;
  range_start: string;
  range_end: string;
  instrument: { symbol: string; name: string } | null;
}

interface SessionOut {
  session_id: string;
  dataset_id: string;
  period_start: string;
  period_end: string;
  replay_at: string;
  initial_cash: Num;
  cash_balance: Num;
  position_quantity: Num;
  average_cost: Num;
  status: "ACTIVE" | "PAUSED" | "COMPLETED" | "ABANDONED";
}

interface PriceBarOut {
  bar_at: string;
  open_price: Num;
  high_price: Num;
  low_price: Num;
  close_price: Num;
}

interface TradeOut {
  trade_id: string;
  session_id: string;
  side: "BUY" | "SELL";
  quantity: Num;
  execution_price: Num;
  realized_pnl: Num | null;
  placed_at: string;
}

interface SessionStatsOut {
  pnl: Num;
  win_rate: Num | null;
  exposure_ratio: Num | null;
}

interface SummaryOut {
  currencies: { session_count: number; pnl: Num; win_rate: Num | null; closed_trades: number; exposure_ratio: Num | null }[];
}

interface AdminDatasetOut {
  dataset_id: string;
  symbol: string;
  interval: string;
  range_start: string;
  range_end: string;
  bar_count: number;
  session_count: number;
}

const day = (iso: string) => iso.slice(0, 10);
const ratioToPct = (v: Num | null) => (v == null ? null : Number(v) * 100);
const live = (s: SessionOut) => s.status === "ACTIVE" || s.status === "PAUSED";

const toBar = (b: PriceBarOut): Bar => ({
  time: day(b.bar_at),
  open: Number(b.open_price),
  high: Number(b.high_price),
  low: Number(b.low_price),
  close: Number(b.close_price),
});

/** Realized result so far: cash plus the open position at its cost, minus the starting cash. */
const realizedPl = (s: SessionOut) =>
  Number(s.cash_balance) + Number(s.position_quantity) * Number(s.average_cost) - Number(s.initial_cash);

async function symbolsByDataset(): Promise<Map<string, string>> {
  const datasets = await http.get<DatasetOut[]>("/datasets");
  return new Map(datasets.map((d) => [d.dataset_id, d.instrument?.symbol ?? "?"]));
}

async function sessionRows(): Promise<SessionRow[]> {
  const [sessions, symbols] = await Promise.all([http.get<SessionOut[]>("/sessions"), symbolsByDataset()]);
  // The API lists newest first; pages expect oldest first.
  return sessions.reverse().map((s) => ({
    id: s.session_id,
    sym: symbols.get(s.dataset_id) ?? "?",
    start: day(s.period_start),
    end: day(s.period_end),
    status: live(s) ? "In progress" : "Completed",
    pl: realizedPl(s),
  }));
}

async function replayState(id: string): Promise<ReplayState> {
  const [session, rawBars, symbols] = await Promise.all([
    http.get<SessionOut>(`/sessions/${id}`),
    http.get<PriceBarOut[]>(`/sessions/${id}/bars`),
    symbolsByDataset(),
  ]);
  const bars = rawBars.map(toBar);
  const cash = Number(session.cash_balance);
  const position = Number(session.position_quantity);
  const lastClose = bars.length ? bars[bars.length - 1].close : 0;
  // The API never says how many future bars exist (that would leak the future), only whether the period is over.
  const finished = !live(session) || session.replay_at >= session.period_end;
  return {
    session: {
      id: session.session_id,
      sym: symbols.get(session.dataset_id) ?? "?",
      start: day(session.period_start),
      end: day(session.period_end),
      status: live(session) ? "In progress" : "Completed",
    },
    bars,
    remaining: finished ? 0 : Number.POSITIVE_INFINITY,
    account: { cash, position, equity: cash + position * lastClose },
  };
}

async function sessionStats(id: string): Promise<SessionStatsOut> {
  try {
    return await http.get<SessionStatsOut>(`/sessions/${id}/stats`);
  } catch {
    // Nothing saved yet (409): compute and save the first snapshot.
    return http.post<SessionStatsOut>(`/sessions/${id}/stats/recompute`);
  }
}

export const api = {
  instruments: async (): Promise<Instrument[]> => {
    const datasets = await http.get<DatasetOut[]>("/datasets");
    return datasets.map((d) => ({
      id: d.dataset_id,
      sym: d.instrument?.symbol ?? "?",
      name: `${d.instrument?.name ?? "Unknown"} (${d.interval})`,
      from: day(d.range_start),
      to: day(d.range_end),
    }));
  },
  sessions: sessionRows,
  createSession: async (input: { datasetId: string; start: string; end: string }) => {
    const session = await http.post<SessionOut>("/sessions", {
      dataset_id: input.datasetId,
      period_start: `${input.start}T00:00:00Z`,
      period_end: `${input.end}T23:59:59Z`,
    });
    // Make sure the chart has at least one bar to show when the period starts before the first stored bar.
    const bars = await http.get<PriceBarOut[]>(`/sessions/${session.session_id}/bars?limit=1`);
    if (!bars.length) await http.post(`/sessions/${session.session_id}/step`, { count: 1 });
    return { id: session.session_id };
  },
  replay: replayState,
  reveal: async (id: string, n: number) => {
    await http.post(`/sessions/${id}/step`, { count: n });
    return replayState(id);
  },
  placeTrade: async (id: string, trade: TradeInput) => {
    // TODO: trade.reasoning is not saved; there is no journal entry endpoint yet.
    const placed = await http.post<TradeOut>(`/sessions/${id}/trades`, {
      side: trade.side.toUpperCase(),
      quantity: String(trade.qty),
    });
    const state = await replayState(id);
    return { trade: { id: placed.trade_id.slice(0, 8) }, account: state.account };
  },
  endSession: async (id: string) => {
    await http.patch(`/sessions/${id}`, { status: "COMPLETED" });
    // Save a final statistics snapshot for the results page.
    await http.post(`/sessions/${id}/stats/recompute`);
    return { id };
  },

  stats: async (scope: string): Promise<StatsData> => {
    if (scope === "all") {
      const [summary, sessions] = await Promise.all([
        http.get<SummaryOut>("/stats/summary"),
        http.get<SessionOut[]>("/sessions"),
      ]);
      // The demo data is all USD; a multi-currency view would need its own layout.
      const c = summary.currencies[0];
      return {
        pl: c ? Number(c.pnl) : 0,
        winRate: c ? ratioToPct(c.win_rate) : null,
        exposure: c ? (ratioToPct(c.exposure_ratio) ?? 0) : 0,
        trades: c?.closed_trades ?? 0,
        summary: {
          sessions: sessions.length,
          openPositions: sessions.filter((s) => Number(s.position_quantity) > 0).length,
        },
      };
    }
    const [stats, session, trades] = await Promise.all([
      sessionStats(scope),
      http.get<SessionOut>(`/sessions/${scope}`),
      http.get<TradeOut[]>(`/sessions/${scope}/trades`),
    ]);
    const position = Number(session.position_quantity);
    return {
      pl: Number(stats.pnl),
      winRate: ratioToPct(stats.win_rate),
      exposure: ratioToPct(stats.exposure_ratio) ?? 0,
      trades: trades.length,
      summary: {
        endingCash: Number(session.cash_balance),
        openPosition: position > 0 ? `${position} shares` : "None",
        status: live(session) ? "In progress" : "Completed",
      },
    };
  },

  trades: async (): Promise<TradeRow[]> => {
    const sessions = await sessionRows();
    const perSession = await Promise.all(
      sessions.map(async (s) => {
        const trades = await http.get<TradeOut[]>(`/sessions/${s.id}/trades`);
        return trades.map<TradeRow>((t) => ({
          id: t.trade_id,
          sid: s.id,
          sym: s.sym,
          side: t.side === "BUY" ? "buy" : "sell",
          qty: Number(t.quantity),
          price: Number(t.execution_price),
          ts: day(t.placed_at),
          // TODO: load the reasoning once a journal entry endpoint exists.
          reasoning: "",
          pnl: t.realized_pnl == null ? null : Number(t.realized_pnl),
        }));
      }),
    );
    return perSession.flat();
  },
  updateReasoning: async (_id: string, _text: string): Promise<{ id: string }> => {
    // TODO: no journal entry endpoint exists yet.
    throw new Error("Saving reasoning is not available yet.");
  },

  // TODO: behavior feedback has no backend endpoint yet; this is fixed placeholder content.
  feedback: async (): Promise<FeedbackData> => ({
    patterns: [
      {
        title: "Example pattern",
        explanation: "The backend will write this text from verified statistics.",
        tradeIds: [],
        evidence: "Placeholder until the feedback endpoint exists.",
      },
    ],
    metrics: [
      { key: "win", label: "Win rate" },
      { key: "size", label: "Average position size" },
      { key: "count", label: "Trades per session" },
      { key: "reason", label: "Reasoning length" },
      { key: "exposure", label: "Peak exposure" },
    ],
    tracked: "",
    trend: [],
  }),
  saveTracked: async (_key: string): Promise<{ key: string }> => {
    // TODO: no tracked habit endpoint exists yet.
    throw new Error("Tracking a metric is not available yet.");
  },

  datasets: async (): Promise<Dataset[]> => {
    const rows = await http.get<AdminDatasetOut[]>("/admin/datasets");
    return rows.map((d) => ({
      id: d.dataset_id,
      sym: d.symbol,
      range: `${day(d.range_start)} to ${day(d.range_end)}`,
      status: `${d.bar_count} bars, ${d.session_count} sessions`,
    }));
  },
  importDataset: async (_sym: string, _file: File): Promise<{ sym: string }> => {
    // TODO: the backend imports from Twelve Data (POST /admin/market-data/import), not from CSV files.
    throw new Error("CSV upload is not supported yet. Use POST /admin/market-data/import or the seed script.");
  },
  usage: async (): Promise<Usage> => {
    const rows = await http.get<AdminDatasetOut[]>("/admin/datasets");
    // TODO: no endpoint counts only active sessions; this is every session across all datasets.
    return { activeSessions: rows.reduce((n, d) => n + d.session_count, 0), datasets: rows.length };
  },

  users: () => http.get<AdminUser[]>("/admin/users"),
  updateUser: (id: string, role: AdminUser["role"], status: AdminUser["status"]) =>
    http.patch<AdminUser>(`/admin/users/${id}`, { role, status }),
};

/** Fixed bars for the decorative chart on the sign-in page. */
export { MOCK_BARS };
