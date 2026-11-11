export const money = (n: number) =>
  (n < 0 ? "-" : "") + "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const signed = (n: number) => (n > 0 ? "+" : "") + money(n);

export const pct = (n: number | null, digits = 0) => (n == null || !Number.isFinite(n) ? "n/a" : n.toFixed(digits) + "%");

export const price = (n: number) => (n >= 100 ? n.toFixed(2) : n >= 10 ? n.toFixed(3) : n.toFixed(4));

export const qtyText = (n: number) => (+n).toFixed(4).replace(/\.?0+$/, "") || "0";

export const tone = (n: number) => (n > 0 ? "gain" : n < 0 ? "loss" : "");
