import { describe, expect, it } from "vitest";
import {
  formatCurrency,
  formatPercent,
  formatPrice,
  formatQuantity,
  formatSignedCurrency,
  pnlColor,
} from "@/lib/format";

describe("format helpers", () => {
  it("formats currency and prices", () => {
    expect(formatCurrency(10000)).toBe("$10,000.00");
    expect(formatPrice(189.9)).toBe("$189.90");
    expect(formatPrice(null)).toBe("—");
  });

  it("formats signed percent with two decimals", () => {
    expect(formatPercent(1.234)).toBe("+1.23%");
    expect(formatPercent(-0.8)).toBe("-0.80%");
    expect(formatPercent(0)).toBe("0.00%");
    expect(formatPercent(null)).toBe("—");
  });

  it("formats signed currency for P&L", () => {
    expect(formatSignedCurrency(78.5)).toBe("+$78.50");
    expect(formatSignedCurrency(-12.4)).toBe("-$12.40");
    expect(formatSignedCurrency(0)).toBe("$0.00");
  });

  it("trims trailing zeros from fractional quantities", () => {
    expect(formatQuantity(10)).toBe("10");
    expect(formatQuantity(1.5)).toBe("1.5");
  });

  it("maps signed values to P&L colors", () => {
    expect(pnlColor(5)).toBe("text-up");
    expect(pnlColor(-5)).toBe("text-down");
    expect(pnlColor(0)).toBe("text-text-muted");
  });
});
