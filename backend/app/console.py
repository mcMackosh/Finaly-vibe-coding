"""Console demo: live-updating simulated stock prices in the terminal.

Run with: uv run python -m app.console
Stop with Ctrl+C.
"""

import asyncio

from app.market_data.cache import PriceCache
from app.market_data.models import Direction, PriceTick
from app.market_data.simulator import SimulatedMarketDataProvider

DEFAULT_TICKERS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

REFRESH_INTERVAL_SECONDS = 1.0

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"
CLEAR_SCREEN = "\033[H\033[J"

DIRECTION_ARROW = {
    Direction.UP: f"{GREEN}^{RESET}",
    Direction.DOWN: f"{RED}v{RESET}",
    Direction.FLAT: " ",
}


def render(ticks: dict[str, PriceTick]) -> str:
    lines = [
        "FinAlly - Live Market Demo (Ctrl+C to quit)",
        "",
        f"{'TICKER':<8}{'PRICE':>12}{'CHANGE':>12}{'CHANGE %':>12}",
        "-" * 44,
    ]
    for ticker in DEFAULT_TICKERS:
        tick = ticks.get(ticker)
        if tick is None:
            lines.append(f"{ticker:<8}{'...':>12}")
            continue
        color = GREEN if tick.direction == Direction.UP else RED if tick.direction == Direction.DOWN else RESET
        arrow = DIRECTION_ARROW[tick.direction]
        lines.append(
            f"{ticker:<8}{color}{tick.price:>11.2f}{RESET} {arrow}"
            f"{color}{tick.change:>+11.2f}{RESET}"
            f"{color}{tick.change_percent:>+11.2f}%{RESET}"
        )
    return "\n".join(lines)


async def main() -> None:
    cache = PriceCache()
    provider = SimulatedMarketDataProvider(cache)
    await provider.start(DEFAULT_TICKERS)

    try:
        while True:
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
            ticks = await cache.get_all()
            print(CLEAR_SCREEN + render(ticks), flush=True)
    except asyncio.CancelledError:
        pass
    finally:
        await provider.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
