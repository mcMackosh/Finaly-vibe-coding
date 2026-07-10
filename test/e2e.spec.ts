import { test, expect, Page, Locator } from "@playwright/test";

/**
 * FinAlly E2E suite. Runs against the Docker container (LLM_MOCK=true) on
 * http://localhost:8000. Tests run serially and share one backend DB, so later
 * tests build on positions opened by earlier ones (see the MSFT buy/sell chain).
 */

const DEFAULT_TICKERS = [
  "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
  "NVDA", "META", "JPM", "V", "NFLX",
];

/** A watchlist row (div with role="row") that contains the exact ticker text. */
function watchlistRow(page: Page, ticker: string): Locator {
  return page
    .locator('[role="row"]')
    .filter({ has: page.getByText(ticker, { exact: true }) });
}

/** A positions-table body row containing the ticker. */
function positionRow(page: Page, ticker: string): Locator {
  return page.locator("tbody tr").filter({ hasText: ticker });
}

function parseCurrency(text: string | null): number {
  if (!text) return NaN;
  return Number(text.replace(/[$,+\s]/g, ""));
}

/** Read the header "Cash" stat as a number. */
async function readCash(page: Page): Promise<number> {
  const value = page
    .getByText("Cash", { exact: true })
    .locator("xpath=following-sibling::span[1]");
  return parseCurrency(await value.textContent());
}

/** Read a watchlist row's current price as text (may be "—" before first tick). */
async function readWatchlistPrice(page: Page, ticker: string): Promise<string> {
  return (await watchlistRow(page, ticker).locator(".price-cell").textContent()) ?? "";
}

/** Fill the trade bar and submit a buy/sell. */
async function submitTrade(
  page: Page,
  ticker: string,
  qty: number,
  side: "Buy" | "Sell",
) {
  await page.getByPlaceholder("Ticker").fill(ticker);
  await page.getByPlaceholder("Qty").fill(String(qty));
  await page.getByRole("button", { name: side, exact: true }).click();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  // Wait for the app to hydrate and the default watchlist to render.
  await expect(watchlistRow(page, "AAPL")).toBeVisible({ timeout: 15_000 });
});

test("1. fresh start: default watchlist, $10k cash, connected", async ({ page }) => {
  for (const ticker of DEFAULT_TICKERS) {
    await expect(watchlistRow(page, ticker)).toBeVisible();
  }
  // Cash balance starts at $10,000.00 (fresh DB).
  await expect(readCash(page)).resolves.toBe(10000);
  // Connection status dot reaches "connected".
  await expect(page.getByText("connected", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
});

test("2. SSE streaming: prices update over time", async ({ page }) => {
  // Wait until AAPL has a real price (not the "—" placeholder).
  await expect
    .poll(async () => await readWatchlistPrice(page, "AAPL"), { timeout: 15_000 })
    .not.toBe("—");

  const first = await readWatchlistPrice(page, "AAPL");
  // Prices tick ~every 500ms; expect a change within a few seconds.
  await expect
    .poll(async () => await readWatchlistPrice(page, "AAPL"), { timeout: 15_000 })
    .not.toBe(first);
});

test("3. add a ticker to the watchlist", async ({ page }) => {
  const newTicker = "PYPL";
  await expect(watchlistRow(page, newTicker)).toHaveCount(0);

  await page.getByPlaceholder("Add…").fill(newTicker);
  await page.getByRole("button", { name: "+", exact: true }).click();

  await expect(watchlistRow(page, newTicker)).toBeVisible();
  // Newly added ticker should begin streaming a price.
  await expect
    .poll(async () => await readWatchlistPrice(page, newTicker), { timeout: 15_000 })
    .not.toBe("—");
});

test("4. remove a ticker from the watchlist", async ({ page }) => {
  const row = watchlistRow(page, "NFLX");
  await expect(row).toBeVisible();

  await row.hover();
  await page.getByRole("button", { name: "Remove NFLX" }).click();

  await expect(watchlistRow(page, "NFLX")).toHaveCount(0);
});

test("5. buy shares: cash decreases, position appears", async ({ page }) => {
  const cashBefore = await readCash(page);
  await expect(positionRow(page, "MSFT")).toHaveCount(0);

  await submitTrade(page, "MSFT", 5, "Buy");

  await expect(positionRow(page, "MSFT")).toBeVisible();
  await expect
    .poll(async () => await readCash(page), { timeout: 10_000 })
    .toBeLessThan(cashBefore);
  // Quantity column shows 5.
  await expect(positionRow(page, "MSFT").locator("td").nth(1)).toHaveText("5");
});

test("6. partial sell: position quantity updates, cash increases", async ({ page }) => {
  await expect(positionRow(page, "MSFT")).toBeVisible();
  const cashBefore = await readCash(page);

  await submitTrade(page, "MSFT", 2, "Sell");

  await expect(positionRow(page, "MSFT").locator("td").nth(1)).toHaveText("3");
  await expect
    .poll(async () => await readCash(page), { timeout: 10_000 })
    .toBeGreaterThan(cashBefore);
});

test("7. sell entire position: row is removed", async ({ page }) => {
  await expect(positionRow(page, "MSFT")).toBeVisible();

  await submitTrade(page, "MSFT", 3, "Sell");

  await expect(positionRow(page, "MSFT")).toHaveCount(0);
});

test("8. portfolio visualizations: heatmap + P&L chart render", async ({ page }) => {
  // Open a couple of positions so both visualizations have data.
  await submitTrade(page, "NVDA", 3, "Buy");
  await expect(positionRow(page, "NVDA")).toBeVisible();
  await submitTrade(page, "TSLA", 2, "Buy");
  await expect(positionRow(page, "TSLA")).toBeVisible();

  // Heatmap: treemap rectangles rendered inside the heatmap panel's SVG.
  const heatmap = page
    .locator("section, div")
    .filter({ hasText: "Portfolio Heatmap" })
    .last();
  await expect(heatmap.locator("svg rect").first()).toBeVisible({ timeout: 10_000 });

  // P&L chart: needs >=2 snapshots; several trades have occurred, so the line
  // path should be present.
  const pnl = page
    .locator("section, div")
    .filter({ hasText: "Portfolio Value" })
    .last();
  await expect(pnl.locator("svg path.recharts-curve").first()).toBeVisible({
    timeout: 10_000,
  });
});

test("9. AI chat (mocked): message + inline trade confirmation", async ({ page }) => {
  const cashBefore = await readCash(page);

  await page.getByPlaceholder("Message FinAlly…").fill("buy 5 AAPL");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  // Mock echoes the order back and executes it.
  await expect(page.getByText(/placing a buy order for 5 AAPL/i)).toBeVisible({
    timeout: 15_000,
  });
  // Inline execution confirmation.
  await expect(page.getByText(/Bought 5 AAPL/i)).toBeVisible();
  // Portfolio reflects the executed trade.
  await expect(positionRow(page, "AAPL")).toBeVisible();
  await expect
    .poll(async () => await readCash(page), { timeout: 10_000 })
    .toBeLessThan(cashBefore);
});

test("10. connection status dot reflects live SSE state", async ({ page }) => {
  await expect(page.getByText("connected", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  // The dot next to the status label carries the "connected" (green) style.
  const dot = page
    .getByText("connected", { exact: true })
    .locator("xpath=preceding-sibling::span[1]");
  await expect(dot).toHaveClass(/bg-up/);
});
