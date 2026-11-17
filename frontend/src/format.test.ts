import { describe, expect, it } from "vitest";
import { money, pct, price, qtyText, signed, tone } from "./format";

describe("format helpers", () => {
  it("formats money with commas and two decimals", () => {
    expect(money(10000)).toBe("$10,000.00");
    expect(money(-236.15)).toBe("-$236.15");
  });

  it("adds a plus sign only to positive amounts", () => {
    expect(signed(412.8)).toBe("+$412.80");
    expect(signed(-46)).toBe("-$46.00");
    expect(signed(0)).toBe("$0.00");
  });

  it("shows n/a when a percentage has no value", () => {
    expect(pct(null)).toBe("n/a");
    expect(pct(Number.NaN)).toBe("n/a");
    expect(pct(54.94, 1)).toBe("54.9%");
  });

  it("uses more decimals for lower prices", () => {
    expect(price(482.654)).toBe("482.65");
    expect(price(41.2)).toBe("41.200");
    expect(price(1.1452)).toBe("1.1452");
  });

  it("trims trailing zeros from quantities", () => {
    expect(qtyText(10)).toBe("10");
    expect(qtyText(2.5)).toBe("2.5");
  });

  it("picks the gain or loss color by sign", () => {
    expect(tone(5)).toBe("gain");
    expect(tone(-5)).toBe("loss");
    expect(tone(0)).toBe("");
  });
});
