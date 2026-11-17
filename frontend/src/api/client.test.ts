import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

const fetchMock = vi.fn();

const SESSION = {
  session_id: "s1",
  dataset_id: "d1",
  period_start: "2023-03-01T00:00:00Z",
  period_end: "2023-03-08T23:59:59Z",
  replay_at: "2023-03-07T19:00:00-05:00",
  initial_cash: "10000.00",
  cash_balance: "9000.00",
  position_quantity: "10",
  average_cost: "100",
  status: "ACTIVE",
};

const BAR = { open_price: "100", high_price: "101", low_price: "99", close_price: "100.5" };

function routes(path: string): unknown {
  if (path.endsWith("/sessions/s1")) return SESSION;
  if (path.endsWith("/sessions/s1/bars"))
    return [
      { ...BAR, bar_at: "2023-03-06T19:00:00-05:00" },
      { ...BAR, bar_at: "2023-03-07T19:00:00-05:00" },
    ];
  if (path.endsWith("/datasets")) return [{ dataset_id: "d1", instrument: { symbol: "DEMO", name: "Demo" } }];
  throw new Error(`unexpected ${path}`);
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockImplementation(async (url: string) => new Response(JSON.stringify(routes(url)), { status: 200 }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

describe("api client replay mapping", () => {
  it("uses the UTC calendar day even when the server sends an offset", async () => {
    const state = await api.replay("s1");

    expect(state.bars.map((b) => b.time)).toEqual(["2023-03-07", "2023-03-08"]);
    expect(state.session.sym).toBe("DEMO");
  });

  it("values the account from cash plus the position at the last visible close", async () => {
    const state = await api.replay("s1");

    expect(state.account).toEqual({ cash: 9000, position: 10, equity: 9000 + 10 * 100.5 });
    expect(state.remaining).toBeGreaterThan(0);
  });
});
