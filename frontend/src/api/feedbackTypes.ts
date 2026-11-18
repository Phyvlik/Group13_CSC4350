/** Feedback responses keep decimals as strings. */
export interface HabitMetric {
  metric_id: string;
  code: string;
  name: string;
  unit: string;
  calculation_version: string;
  calculation_rule: string;
}
export interface Habits {
  metrics: HabitMetric[];
  tracked: { metric_id: string; selected_at: string; active: boolean }[];
}
export interface FeedbackSnapshot {
  session_id: string;
  analysis_version: string;
  status: "not_computed" | "ready";
  computed_at: string | null;
  metric: null | {
    session_metric_id: string; metric_id: string; revision: number;
    value: string; verified_at: string;
  };
  feedback: {
    feedback_id: string; pattern_code: string; explanation: string;
    analysis_version: string; generated_at: string; trade_ids: string[];
    evidence: {
      session_metric_id: string; metric_code: string; value: string;
      verified_at: string; evidence_reason: string; trade_ids: string[];
      journal_entries: { trade_id: string; reasoning: string }[];
    }[];
  }[];
}
export interface HabitHistory {
  metric_id: string; code: string; unit: string; calculation_version: string;
  points: {
    session_id: string; started_at: string; quote_currency: string;
    value: string; revision: number; computed_at: string; verified_at: string;
  }[];
  limit: number; offset: number; has_more: boolean;
}
