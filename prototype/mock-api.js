/* MOCK API. Stands in for the backend endpoints so the pages can be viewed and reviewed on their own.
   Nothing here calculates anything. All numbers are fixed placeholders.

   Replace each function with a fetch() call when the real endpoint exists, then delete this file:
     replay, reveal, placeTrade, endSession, createSession, instruments  -> replay engine + paper trading (issues #8, #9)
     stats                                                               -> stats (issue #12)
     feedback, saveTracked                                               -> behavior feedback (issue #13)
     trades, updateReasoning                                             -> trade journal (issue #11)
     datasets, importDataset, usage                                      -> market data import (issue #7)
*/
(() => {
  const BARS = window.MOCK_BARS;
  const wait = (v) => new Promise((r) => setTimeout(() => r(JSON.parse(JSON.stringify(v))), 120));

  const sessions = [
    { id: 's1', sym: 'SPY', start: '2026-01-05', end: '2026-03-31', status: 'Completed', pl: 412.8 },
    { id: 's2', sym: 'AAPL', start: '2025-03-03', end: '2025-06-30', status: 'Completed', pl: -236.15 },
    { id: 's3', sym: 'TSLA', start: '2026-01-05', end: '2026-04-30', status: 'In progress', pl: 0 },
  ];
  const trades = [
    { id: 'T-0001', sid: 's1', sym: 'SPY', side: 'buy', qty: 10, price: 484.1, ts: '2026-01-12', reasoning: 'Breaking above the recent range on rising volume.', pnl: null },
    { id: 'T-0002', sid: 's1', sym: 'SPY', side: 'sell', qty: 10, price: 491.3, ts: '2026-01-26', reasoning: 'Taking profit into resistance.', pnl: 72 },
    { id: 'T-0003', sid: 's2', sym: 'AAPL', side: 'buy', qty: 20, price: 41.2, ts: '2025-03-10', reasoning: 'Pullback to support, starter position.', pnl: null },
    { id: 'T-0004', sid: 's2', sym: 'AAPL', side: 'sell', qty: 20, price: 38.9, ts: '2025-03-24', reasoning: 'Cutting the loss, trend has failed.', pnl: -46 },
  ];
  let cur = 40; // how many bars the mock "server" has revealed

  const replay = () => ({
    session: { id: 's3', sym: 'TSLA', start: BARS[0].d, end: BARS[BARS.length - 1].d, status: 'In progress' },
    bars: BARS.slice(0, cur),
    remaining: BARS.length - cur,
    account: { cash: 10000, position: 0, equity: 10000 },
  });

  window.api = {
    instruments: () => wait([
      { sym: 'SPY', name: 'S&P 500 ETF', from: '2019-01-01', to: '2026-10-14' },
      { sym: 'AAPL', name: 'Apple', from: '2019-01-01', to: '2026-10-14' },
      { sym: 'TSLA', name: 'Tesla', from: '2019-01-01', to: '2026-10-14' },
    ]),
    sessions: () => wait(sessions),
    createSession: () => { cur = 40; return wait({ id: 's3' }); },
    replay: () => wait(replay()),
    reveal: (id, n) => { cur = Math.min(BARS.length, cur + n); return wait(replay()); },
    placeTrade: (id, t) => wait({ trade: { id: 'T-0099' }, account: replay().account }),
    endSession: () => wait({ id: 's3' }),

    stats: (scope) => wait(scope === 'all'
      ? { pl: 176.65, winRate: 50, exposure: 18, trades: 4, summary: { sessions: 3, openPositions: 0 } }
      : { pl: 412.8, winRate: 100, exposure: 0, trades: 2, summary: { endingCash: 10412.8, openPosition: 'None', status: scope === 's3' ? 'In progress' : 'Completed' } }),

    trades: () => wait(trades),
    updateReasoning: (id, text) => { const t = trades.find((x) => x.id === id); if (t) t.reasoning = text; return wait({ id }); },

    feedback: () => wait({
      patterns: [{ title: 'Example pattern', explanation: 'The backend writes this text from verified statistics.', tradeIds: ['T-0003', 'T-0004'], evidence: 'Placeholder evidence line with a computed statistic.' }],
      metrics: [{ key: 'win', label: 'Win rate' }, { key: 'size', label: 'Average position size' }, { key: 'count', label: 'Trades per session' }, { key: 'reason', label: 'Reasoning length' }, { key: 'exposure', label: 'Peak exposure' }],
      tracked: localStorage.getItem('epoch.mock.tracked') || '',
      trend: [{ label: 'Session 1', value: '54.9%' }, { label: 'Session 2', value: '52.2%' }, { label: 'Session 3', value: '48.7%' }],
    }),
    saveTracked: (key) => { try { localStorage.setItem('epoch.mock.tracked', key); } catch (e) {} return wait({ key }); },

    datasets: () => wait([{ sym: 'SPY', range: '2019-01-01 to 2026-10-14', status: 'Imported' }, { sym: 'AAPL', range: '2019-01-01 to 2026-10-14', status: 'Imported' }]),
    importDataset: (sym, file) => wait({ sym, rows: 0 }),
    usage: () => wait({ activeSessions: 1, datasets: 2 }),
  };
})();
