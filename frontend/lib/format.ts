/** Shared number/label formatting for the terminal UI. */

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const formatCurrency = (value: number): string => currency.format(value);

export const formatPrice = (value: number | null | undefined): string =>
  value == null ? "—" : currency.format(value);

/** Signed percentage, e.g. "+1.24%" / "-0.80%". */
export const formatPercent = (value: number | null | undefined): string => {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
};

/** Signed currency, e.g. "+$12.40" / "-$5.00". */
export const formatSignedCurrency = (value: number): string => {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${currency.format(Math.abs(value))}`;
};

export const formatQuantity = (value: number): string =>
  Number.isInteger(value) ? value.toString() : value.toFixed(4).replace(/0+$/, "");

/** Tailwind text color for a signed value (green up, red down, muted flat). */
export const pnlColor = (value: number): string =>
  value > 0 ? "text-up" : value < 0 ? "text-down" : "text-text-muted";
