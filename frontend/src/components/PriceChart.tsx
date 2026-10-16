import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  CrosshairMode,
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { Bar } from "../api/types";
import { useChartColors } from "../hooks/useTheme";

interface Props {
  /** Only the bars the server has revealed. The chart never receives future prices. */
  bars: Bar[];
  /** Bars of context kept on screen. */
  window?: number;
  /** Width of the hidden "future" zone, in bars. */
  future?: number;
  /** Show the hatched "future prices hidden" zone. */
  showFuture?: boolean;
  label: string;
}

const fmt = (n: number) => (n >= 100 ? n.toFixed(2) : n >= 10 ? n.toFixed(3) : n.toFixed(4));
const toData = (b: Bar): CandlestickData<Time> => ({ time: b.time as Time, open: b.open, high: b.high, low: b.low, close: b.close });

export default function PriceChart({ bars, window: win = 64, future = 12, showFuture = true, label }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const colors = useChartColors();
  const [futureLeft, setFutureLeft] = useState<number | null>(null);
  const [readout, setReadout] = useState("");

  /* create once */
  useEffect(() => {
    if (!host.current) return;
    const chart = createChart(host.current, {
      autoSize: true,
      handleScroll: false,
      handleScale: false,
      crosshair: { mode: CrosshairMode.Normal },
      leftPriceScale: { visible: true, borderVisible: false },
      rightPriceScale: { visible: false },
      timeScale: { borderVisible: false, barSpacing: 9, fixLeftEdge: false, rightOffset: future },
      layout: { background: { color: "transparent" }, fontFamily: "Geist Mono, monospace", fontSize: 11 },
    });
    const series = chart.addSeries(CandlestickSeries, { wickUpColor: "#888", wickDownColor: "#888", borderVisible: false });
    chartRef.current = chart;
    seriesRef.current = series;

    chart.subscribeCrosshairMove((p) => {
      const d = p.seriesData.get(series) as CandlestickData<Time> | undefined;
      setReadout(d ? `${String(p.time)}   O ${fmt(d.open)}  H ${fmt(d.high)}  L ${fmt(d.low)}  C ${fmt(d.close)}` : "");
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [future]);

  /* theme colors */
  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;
    chart.applyOptions({
      layout: { textColor: colors.muted },
      grid: { vertLines: { visible: false }, horzLines: { color: colors.line } },
      crosshair: {
        vertLine: { color: colors.muted, labelBackgroundColor: colors.accent },
        horzLine: { color: colors.muted, labelBackgroundColor: colors.accent },
      },
    });
    series.applyOptions({
      upColor: colors.gain,
      downColor: colors.loss,
      wickUpColor: colors.gain,
      wickDownColor: colors.loss,
    });
  }, [colors]);

  /* data and visible range */
  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series || bars.length === 0) return;
    series.setData(bars.map(toData));
    const n = bars.length;
    chart.timeScale().setVisibleLogicalRange({ from: n - win, to: n - 1 + future });

    const place = () => {
      const x = chart.timeScale().logicalToCoordinate((n - 1) as never);
      setFutureLeft(x == null ? null : x + 14);
    };
    place();
    const ro = new ResizeObserver(place);
    if (host.current) ro.observe(host.current);
    return () => ro.disconnect();
  }, [bars, win, future]);

  return (
    <div className="chart-box" role="img" aria-label={label}>
      <div className="chart" ref={host} />
      {readout && (
        <div className="mono muted" style={{ position: "absolute", top: 4, left: 64, fontSize: 11, pointerEvents: "none" }}>
          {readout}
        </div>
      )}
      {showFuture && futureLeft != null && (
        <div className="chart-future" style={{ left: futureLeft, width: "auto" }}>
          Future prices
          <br />
          hidden
        </div>
      )}
    </div>
  );
}
