import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";
import { setToken } from "./http";
const fetchMock = vi.fn();
beforeEach(() => { vi.stubGlobal("fetch", fetchMock); setToken("test-token"); fetchMock.mockImplementation(async () => new Response("{}", { status: 200 })); });
afterEach(() => { setToken(null); vi.unstubAllGlobals(); fetchMock.mockReset(); });
describe("feedback HTTP contract", () => {
  it("separates reads from recomputation and sends authentication", async () => {
    await api.feedback("session-1");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/sessions\/session-1\/feedback$/);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "GET", headers: { Authorization: "Bearer test-token" } });
    await api.recomputeFeedback("session-1");
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/sessions\/session-1\/feedback\/recompute$/);
    expect(fetchMock.mock.calls[1][1].method).toBe("POST");
  });
  it("saves tracking selections and requests bounded history", async () => {
    await api.saveTracked("metric-1", false);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ metric_id: "metric-1", active: false });
    await api.habitHistory("metric-1", 20);
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/habits\/metric-1\/history\?limit=20&offset=20$/);
  });
  it("propagates verification errors without placeholder evidence", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Latest metric is unverified." }), { status: 409 }));
    await expect(api.feedback("session-1")).rejects.toThrow("Latest metric is unverified.");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("bounds initial session loading but permits explicit access to older sessions", async () => {
    fetchMock.mockImplementation(async () => new Response(JSON.stringify([{ session_id: "session-1", period_start: "2026-01-01T00:00:00Z", period_end: "2026-01-02T00:00:00Z", status: "COMPLETED" }])));
    expect((await api.feedbackSessions())[0].id).toBe("session-1");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/sessions\?limit=100$/);
    await api.feedbackSessions(true);
    expect(fetchMock.mock.calls[1][0]).toMatch(/\/sessions$/);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
