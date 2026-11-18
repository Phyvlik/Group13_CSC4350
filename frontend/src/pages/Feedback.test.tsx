import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { FeedbackSnapshot, HabitHistory, Habits } from "../api/feedbackTypes";
import FeedbackPage from "./Feedback";
const metric = { metric_id: "m1", code: "LOSS_CHASING", name: "Larger positions after losses", unit: "events", calculation_version: "loss-chasing-v2", calculation_rule: "Two qualifying positions after losses, at least three earlier post-buy holdings samples and a 1.5x threshold." };
const catalog: Habits = { metrics: [metric], tracked: [] };
const active: Habits = { ...catalog, tracked: [{ metric_id: "m1", active: true, selected_at: "2026-11-17T12:00:00Z" }] };
const blank = (id = "s1"): FeedbackSnapshot => ({ session_id: id, analysis_version: "loss-chasing-v2", status: "not_computed", computed_at: null, metric: null, feedback: [] });
const ready: FeedbackSnapshot = { ...blank(), status: "ready", computed_at: "2026-11-17T12:00:00Z", metric: { session_metric_id: "sm1", metric_id: "m1", revision: 2, value: "2.000000", verified_at: "2026-11-17T12:00:00Z" }, feedback: [{ feedback_id: "f1", pattern_code: "LOSS_CHASING", explanation: "Two post-buy positions were at least 1.5 times the prior holdings mean after losses.", analysis_version: "loss-chasing-v2", generated_at: "2026-11-17T12:00:00Z", trade_ids: ["trade1", "trade2"], evidence: [{ session_metric_id: "sm1", metric_code: "LOSS_CHASING", value: "2.000000", verified_at: "2026-11-17T12:00:00Z", evidence_reason: "Trade trade2 left total holdings of 20 shares against a prior holdings mean of 10 after losing trade trade1.", trade_ids: ["trade1", "trade2"], journal_entries: [{ trade_id: "trade2", reasoning: "Waited for the next setup." }] }] }] };
const history: HabitHistory = { metric_id: "m1", code: "LOSS_CHASING", unit: "events", calculation_version: "loss-chasing-v2", limit: 20, offset: 0, has_more: false, points: [] };
const point = { session_id: "usd-session", started_at: "2026-11-16T10:00:00Z", quote_currency: "USD", value: "12.123456", revision: 1, computed_at: "2026-11-17T12:00:00Z", verified_at: "2026-11-17T12:00:00Z" };
function show() { render(<MemoryRouter><FeedbackPage /></MemoryRouter>); }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
beforeEach(() => {
  vi.spyOn(api, "feedbackSessions").mockResolvedValue([{ id: "s1", label: "First session" }, { id: "s2", label: "Second session" }]);
  vi.spyOn(api, "habits").mockResolvedValue(catalog);
  vi.spyOn(api, "feedback").mockImplementation(async (id) => blank(id));
  vi.spyOn(api, "recomputeFeedback").mockResolvedValue(ready);
  vi.spyOn(api, "saveTracked").mockResolvedValue(active);
  vi.spyOn(api, "habitHistory").mockResolvedValue(history);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
describe("feedback workflow", () => {
  it("does not create feedback or a clean result just by opening the page", async () => {
    show(); expect(await screen.findByText("Session not analyzed yet")).toBeTruthy();
    expect(api.recomputeFeedback).not.toHaveBeenCalled();
    expect(screen.queryByText("No recurring pattern found")).toBeNull();
  });
  it("analyzes selected session and displays exact evidence and trade links", async () => {
    show(); await screen.findByText("Session not analyzed yet");
    await userEvent.selectOptions(screen.getByLabelText("Practice session"), "s2");
    await waitFor(() => expect(api.feedback).toHaveBeenCalledWith("s2"));
    await userEvent.click(screen.getByRole("button", { name: "Analyze session" }));
    expect(api.recomputeFeedback).toHaveBeenCalledWith("s2");
    expect(await screen.findByText(ready.feedback[0].explanation)).toBeTruthy();
    expect(screen.getByRole("link", { name: "View trade trade2" }).getAttribute("href")).toBe("/journal/trade2");
    expect(screen.getByText("Waited for the next setup.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Larger positions after losses" })).toBeTruthy();
    expect(screen.getByText(/Verified snapshot: 2 qualifying events/)).toBeTruthy();
  });
  it("explains a nonmatch without claiming that a habit is absent", async () => {
    vi.mocked(api.feedback).mockResolvedValue({ ...ready, feedback: [] }); show();
    expect(await screen.findByText("No recurring pattern found")).toBeTruthy();
    expect(screen.getByText(/does not prove that a habit is absent/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /View trade/ })).toBeNull();
  });
  it("shows failed verification as an error and lets users analyze again", async () => {
    vi.mocked(api.feedback).mockRejectedValue(new Error("Latest metric is unverified.")); show();
    expect(await screen.findByText("Latest metric is unverified.")).toBeTruthy();
    expect(screen.queryByText("No recurring pattern found")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Analyze session" }));
    expect(await screen.findByText(ready.feedback[0].explanation)).toBeTruthy();
  });
  it("prevents duplicate analysis requests and reports a failed refresh", async () => {
    const pending = deferred<FeedbackSnapshot>(); vi.mocked(api.recomputeFeedback).mockReturnValue(pending.promise);
    show(); await screen.findByText("Session not analyzed yet");
    await userEvent.dblClick(screen.getByRole("button", { name: "Analyze session" }));
    expect(api.recomputeFeedback).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve(ready));
    vi.mocked(api.recomputeFeedback).mockRejectedValueOnce(new Error("Could not verify snapshot."));
    await userEvent.click(screen.getByRole("button", { name: "Analyze session" }));
    expect(await screen.findByText("Could not verify snapshot.")).toBeTruthy();
  });
  it("ignores old session analysis responses after changing sessions", async () => {
    const pending = deferred<FeedbackSnapshot>(); vi.mocked(api.recomputeFeedback).mockReturnValue(pending.promise);
    show(); await screen.findByText("Session not analyzed yet");
    await userEvent.click(screen.getByRole("button", { name: "Analyze session" }));
    await userEvent.selectOptions(screen.getByLabelText("Practice session"), "s2");
    await waitFor(() => expect(api.feedback).toHaveBeenCalledWith("s2"));
    await act(async () => pending.resolve(ready));
    expect(await screen.findByText("Session not analyzed yet")).toBeTruthy();
    expect(screen.queryByText(ready.feedback[0].explanation)).toBeNull();
  });
  it("persists a selection and loads the saved selection after reopening", async () => {
    show(); await screen.findByLabelText("Habit or metric to track");
    await userEvent.selectOptions(screen.getByLabelText("Habit or metric to track"), "m1");
    await userEvent.click(screen.getByRole("button", { name: "Save selection" }));
    expect(api.saveTracked).toHaveBeenCalledWith("m1", true);
    expect(await screen.findByText("Saved. Your metric is now tracked.")).toBeTruthy();
    await waitFor(() => expect(api.habitHistory).toHaveBeenCalledWith("m1", 0));
    cleanup(); vi.mocked(api.habits).mockResolvedValue(active); show();
    expect(await screen.findByRole("button", { name: "Stop tracking" })).toBeTruthy();
    expect((screen.getByLabelText("Habit or metric to track") as HTMLSelectElement).value).toBe("m1");
  });
  it("does not claim success when saving fails", async () => {
    vi.mocked(api.saveTracked).mockRejectedValue(new Error("Could not reach the server.")); show();
    await screen.findByLabelText("Habit or metric to track");
    await userEvent.selectOptions(screen.getByLabelText("Habit or metric to track"), "m1");
    await userEvent.click(screen.getByRole("button", { name: "Save selection" }));
    expect(await screen.findByText("Could not reach the server.")).toBeTruthy();
    expect(api.habitHistory).not.toHaveBeenCalled();
  });
  it("stops tracking without deleting observations", async () => {
    vi.mocked(api.habits).mockResolvedValue(active);
    vi.mocked(api.saveTracked).mockResolvedValue({ ...catalog, tracked: [{ ...active.tracked[0], active: false }] });
    show(); await userEvent.click(await screen.findByRole("button", { name: "Stop tracking" }));
    expect(api.saveTracked).toHaveBeenCalledWith("m1", false);
    expect(await screen.findByText("Tracking stopped. Saved observations are kept.")).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Metric history" })).toBeNull();
  });
  it("paginates exact currency values and can return from an empty page", async () => {
    vi.mocked(api.habits).mockResolvedValue(active);
    vi.mocked(api.habitHistory).mockResolvedValueOnce({ ...history, unit: "quote currency", has_more: true, points: [point, { ...point, session_id: "eur-session", value: "8.000000", quote_currency: "EUR" }] });
    show(); expect(await screen.findByText("12.123456 USD")).toBeTruthy();
    expect(screen.getByText("8 EUR")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Older sessions" }));
    expect(await screen.findByText(/No verified history on this page/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Newer sessions" }));
    await waitFor(() => expect(api.habitHistory).toHaveBeenLastCalledWith("m1", 0));
  });
  it("supports accounts without sessions", async () => {
    vi.mocked(api.feedbackSessions).mockResolvedValue([]); show();
    expect(await screen.findByText("No practice sessions yet")).toBeTruthy();
    expect(screen.getByLabelText("Habit or metric to track")).toBeTruthy();
    expect(api.feedback).not.toHaveBeenCalled();
  });
  it("allows retry after an initial load failure", async () => {
    vi.mocked(api.habits).mockRejectedValueOnce(new Error("Session expired.")); show();
    expect(await screen.findByText("Session expired.")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Session not analyzed yet")).toBeTruthy();
  });
  it("can explicitly load older sessions beyond the initial limit", async () => {
    vi.mocked(api.feedbackSessions).mockResolvedValue(Array.from({ length: 100 }, (_, i) => ({ id: `s${i}`, label: `Session ${i}` })));
    show(); await userEvent.click(await screen.findByRole("button", { name: "Load older sessions" }));
    await waitFor(() => expect(api.feedbackSessions).toHaveBeenLastCalledWith(true));
  });
  it("keeps a pending habit save mounted while loading older sessions", async () => {
    vi.mocked(api.feedbackSessions).mockResolvedValue(Array.from({ length: 100 }, (_, i) => ({ id: `s${i}`, label: `Session ${i}` })));
    const pending = deferred<Habits>();
    vi.mocked(api.saveTracked).mockReturnValue(pending.promise);
    show(); await screen.findByLabelText("Habit or metric to track");
    await userEvent.selectOptions(screen.getByLabelText("Habit or metric to track"), "m1");
    await userEvent.click(screen.getByRole("button", { name: "Save selection" }));
    await userEvent.click(screen.getByRole("button", { name: "Load older sessions" }));
    await waitFor(() => expect(api.feedbackSessions).toHaveBeenLastCalledWith(true));
    await act(async () => pending.resolve(active));
    expect(await screen.findByRole("button", { name: "Stop tracking" })).toBeTruthy();
    expect((screen.getByLabelText("Habit or metric to track") as HTMLSelectElement).value).toBe("m1");
    expect(api.habits).toHaveBeenCalledTimes(1);
  });
  it("keeps tracking available when older sessions fail and allows retry", async () => {
    const sessions = Array.from({ length: 100 }, (_, i) => ({ id: `s${i}`, label: `Session ${i}` }));
    vi.mocked(api.feedbackSessions).mockResolvedValueOnce(sessions).mockRejectedValueOnce(new Error("Could not load older sessions.")).mockResolvedValue(sessions);
    vi.mocked(api.habits).mockResolvedValue(active);
    show(); await userEvent.click(await screen.findByRole("button", { name: "Load older sessions" }));
    expect(await screen.findByText("Could not load older sessions.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Stop tracking" })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Load older sessions" }));
    await waitFor(() => expect(screen.queryByText("Could not load older sessions.")).toBeNull());
    expect(api.habits).toHaveBeenCalledTimes(1);
  });

});
