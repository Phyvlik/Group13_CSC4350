import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { MOCK_BARS } from "../api/mockBars";
import { ToastProvider } from "../components/Toasts";
import ReplayPage from "./Replay";

// The chart library needs a real canvas, so the test only records which bars it was given.
const chartBars = vi.hoisted(() => ({ latest: [] as { time: string }[] }));
vi.mock("../components/PriceChart", () => ({
  default: ({ bars }: { bars: { time: string }[] }) => {
    chartBars.latest = bars;
    return <div data-testid="chart" />;
  },
}));

function renderReplay() {
  render(
    <MemoryRouter initialEntries={["/replay/s3"]}>
      <ToastProvider>
        <Routes>
          <Route path="/replay/:id" element={<ReplayPage />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
  return screen.findByTestId("chart");
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("practice replay page", () => {
  it("only gives the chart bars up to the replay point", async () => {
    const { bars, remaining } = await api.createSession({ sym: "TSLA", start: "2026-01-05", end: "2026-04-30" }).then(() => api.replay("s3"));
    await renderReplay();

    expect(chartBars.latest).toHaveLength(bars.length);
    expect(remaining).toBeGreaterThan(0);
    const lastShown = chartBars.latest[chartBars.latest.length - 1].time;
    expect(lastShown).toBe(MOCK_BARS[bars.length - 1].time);
    expect(chartBars.latest.some((b) => b.time > lastShown)).toBe(false);
  });

  it("adds one more bar when Reveal next bar is clicked", async () => {
    await api.createSession({ sym: "TSLA", start: "2026-01-05", end: "2026-04-30" });
    await renderReplay();
    const before = chartBars.latest.length;

    await userEvent.click(screen.getByRole("button", { name: "Reveal next bar" }));

    await waitFor(() => expect(chartBars.latest).toHaveLength(before + 1));
  });

  it("does not save a trade without a quantity", async () => {
    const placeTrade = vi.spyOn(api, "placeTrade");
    await renderReplay();

    await userEvent.type(screen.getByLabelText("Trade reasoning"), "Pullback to support.");
    await userEvent.click(screen.getByRole("button", { name: "Save trade and reasoning" }));

    expect(await screen.findByText("Enter a quantity greater than zero.")).toBeTruthy();
    expect(placeTrade).not.toHaveBeenCalled();
  });

  it("does not save a trade without reasoning", async () => {
    const placeTrade = vi.spyOn(api, "placeTrade");
    await renderReplay();

    await userEvent.type(screen.getByLabelText("Quantity"), "5");
    await userEvent.click(screen.getByRole("button", { name: "Save trade and reasoning" }));

    expect(await screen.findByText("Add your reasoning before saving the trade.")).toBeTruthy();
    expect(placeTrade).not.toHaveBeenCalled();
  });

  it("sends the side, quantity and reasoning when the form is complete", async () => {
    const placeTrade = vi.spyOn(api, "placeTrade");
    await renderReplay();

    await userEvent.click(screen.getByLabelText("Sell"));
    await userEvent.type(screen.getByLabelText("Quantity"), "5");
    await userEvent.type(screen.getByLabelText("Trade reasoning"), "Trimming into strength.");
    await userEvent.click(screen.getByRole("button", { name: "Save trade and reasoning" }));

    await waitFor(() =>
      expect(placeTrade).toHaveBeenCalledWith("s3", { side: "sell", qty: 5, reasoning: "Trimming into strength." }),
    );
    expect(await screen.findByText("T-0099 saved to your journal.")).toBeTruthy();
  });
});
