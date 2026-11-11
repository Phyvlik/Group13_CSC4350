/*
 * Placeholder API client. Nothing here calculates anything: replay, trading, stats and feedback
 * come from the backend, and every number below is a fixed stand-in so the pages can be built and reviewed.
 *
 * Replace each function with a fetch() to the real endpoint, then delete the mock data:
 *   instruments, createSession, replay, reveal, placeTrade, endSession  -> replay engine and paper trading (#8, #9)
 *   stats                                                               -> stats (#12)
 *   feedback, saveTracked                                               -> behavior feedback (#13)
 *   trades, updateReasoning                                             -> trade journal (#11)
 *   datasets, importDataset, usage                                      -> market data import (#7)
 */
import { MOCK_BARS } from "./mockBars";
import type {
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

const wait = <T>(value: T): Promise<T> =>
  new Promise((resolve) => setTimeout(() => resolve(structuredClone(value)), 120));

const sessions: SessionRow[] = [
  { id: "s1", sym: "SPY", start: "2026-01-05", end: "2026-03-31", status: "Completed", pl: 412.8 },
  { id: "s2", sym: "AAPL", start: "2025-03-03", end: "2025-06-30", status: "Completed", pl: -236.15 },
  { id: "s3", sym: "TSLA", start: "2026-01-05", end: "2026-04-30", status: "In progress", pl: 0 },
];

const trades: TradeRow[] = [
  { id: "T-0001", sid: "s1", sym: "SPY", side: "buy", qty: 10, price: 484.1, ts: "2026-01-12", reasoning: "Breaking above the recent range on rising volume.", pnl: null },
  { id: "T-0002", sid: "s1", sym: "SPY", side: "sell", qty: 10, price: 491.3, ts: "2026-01-26", reasoning: "Taking profit into resistance.", pnl: 72 },
  { id: "T-0003", sid: "s2", sym: "AAPL", side: "buy", qty: 20, price: 41.2, ts: "2025-03-10", reasoning: "Pullback to support, starter position.", pnl: null },
  { id: "T-0004", sid: "s2", sym: "AAPL", side: "sell", qty: 20, price: 38.9, ts: "2025-03-24", reasoning: "Cutting the loss, trend has failed.", pnl: -46 },
];

let revealed = 40; // bars the placeholder "server" has shown so far
let tracked = "";

const replayState = (): ReplayState => ({
  session: { id: "s3", sym: "TSLA", start: MOCK_BARS[0].time, end: MOCK_BARS[MOCK_BARS.length - 1].time, status: "In progress" },
  bars: MOCK_BARS.slice(0, revealed),
  remaining: MOCK_BARS.length - revealed,
  account: { cash: 10000, position: 0, equity: 10000 },
});

export const api = {
  instruments: () =>
    wait<Instrument[]>([
      { sym: "SPY", name: "S&P 500 ETF", from: "2019-01-01", to: "2026-10-14" },
      { sym: "AAPL", name: "Apple", from: "2019-01-01", to: "2026-10-14" },
      { sym: "TSLA", name: "Tesla", from: "2019-01-01", to: "2026-10-14" },
    ]),
  sessions: () => wait(sessions),
  createSession: (_input: { sym: string; start: string; end: string }) => {
    revealed = 40;
    return wait({ id: "s3" });
  },
  replay: (_id: string) => wait(replayState()),
  reveal: (_id: string, n: number) => {
    revealed = Math.min(MOCK_BARS.length, revealed + n);
    return wait(replayState());
  },
  placeTrade: (_id: string, _trade: TradeInput) => wait({ trade: { id: "T-0099" }, account: replayState().account }),
  endSession: (id: string) => wait({ id }),

  stats: (scope: string) =>
    wait<StatsData>(
      scope === "all"
        ? { pl: 176.65, winRate: 50, exposure: 18, trades: 4, summary: { sessions: 3, openPositions: 0 } }
        : { pl: 412.8, winRate: 100, exposure: 0, trades: 2, summary: { endingCash: 10412.8, openPosition: "None", status: scope === "s3" ? "In progress" : "Completed" } },
    ),

  trades: () => wait(trades),
  updateReasoning: (id: string, text: string) => {
    const t = trades.find((x) => x.id === id);
    if (t) t.reasoning = text;
    return wait({ id });
  },

  feedback: () =>
    wait<FeedbackData>({
      patterns: [
        {
          title: "Example pattern",
          explanation: "The backend writes this text from verified statistics.",
          tradeIds: ["T-0003", "T-0004"],
          evidence: "Placeholder evidence line with a computed statistic.",
        },
      ],
      metrics: [
        { key: "win", label: "Win rate" },
        { key: "size", label: "Average position size" },
        { key: "count", label: "Trades per session" },
        { key: "reason", label: "Reasoning length" },
        { key: "exposure", label: "Peak exposure" },
      ],
      tracked,
      trend: [
        { label: "Session 1", value: "54.9%" },
        { label: "Session 2", value: "52.2%" },
        { label: "Session 3", value: "48.7%" },
      ],
    }),
  saveTracked: (key: string) => {
    tracked = key;
    return wait({ key });
  },

  datasets: () =>
    wait<Dataset[]>([
      { sym: "SPY", range: "2019-01-01 to 2026-10-14", status: "Imported" },
      { sym: "AAPL", range: "2019-01-01 to 2026-10-14", status: "Imported" },
    ]),
  importDataset: (sym: string, _file: File) => wait({ sym }),
  usage: () => wait<Usage>({ activeSessions: 1, datasets: 2 }),
};

export { MOCK_BARS };
