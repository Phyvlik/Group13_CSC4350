export interface Bar {
  time: string; // YYYY-MM-DD
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface Instrument {
  id: string; // dataset id; one instrument can have several datasets
  sym: string;
  name: string;
  from: string;
  to: string;
}

export interface SessionRow {
  id: string;
  sym: string;
  start: string;
  end: string;
  status: "In progress" | "Completed";
  pl: number;
}

export interface Account {
  cash: number;
  position: number;
  equity: number;
}

/** Only bars up to the current replay point are ever returned. */
export interface ReplayState {
  session: { id: string; sym: string; start: string; end: string; status: string };
  bars: Bar[];
  remaining: number;
  account: Account;
}

export interface TradeInput {
  side: "buy" | "sell";
  qty: number;
  reasoning: string;
}

export interface TradeRow {
  id: string;
  sid: string;
  sym: string;
  side: "buy" | "sell";
  qty: number;
  price: number;
  ts: string;
  reasoning: string;
  pnl: number | null;
}

export interface StatsData {
  pl: number;
  winRate: number | null;
  exposure: number;
  trades: number;
  summary: { endingCash?: number; openPosition?: string; status?: string; sessions?: number; openPositions?: number };
}

export interface FeedbackPattern {
  title: string;
  explanation: string;
  tradeIds: string[];
  evidence: string;
}

export interface FeedbackData {
  patterns: FeedbackPattern[];
  metrics: { key: string; label: string }[];
  tracked: string;
  trend: { label: string; value: string }[];
}

export interface Dataset {
  id: string;
  sym: string;
  range: string;
  status: string;
}

export interface Usage {
  activeSessions: number;
  datasets: number;
}

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: "Trader" | "Admin";
  status: "Active" | "Disabled";
}
