"""Console demo: live-updating simulated stock prices in the terminal.

Consumes the same PriceCache pub/sub queue the SSE endpoint (`/api/stream/prices`) uses,
so this is a terminal-only stand-in for a chart client.

Run with: uv run python -m app.console
Stop with Ctrl+C.
"""

import asyncio

from app.market_data.cache import PriceCache
from app.market_data.models import Direction, PriceTick
from app.market_data.simulator import SimulatedMarketDataProvider
from app.market_data.tickers import DEFAULT_WATCHLIST

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


def render(latest: dict[str, PriceTick]) -> str:
    lines = [
        "FinAlly - Live Market Demo (Ctrl+C to quit)",
        "",
        f"{'TICKER':<8}{'PRICE':>12}{'CHANGE':>12}{'CHANGE %':>12}",
        "-" * 44,
    ]
    for ticker in DEFAULT_WATCHLIST:
        tick = latest.get(ticker)
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
    await provider.start(DEFAULT_WATCHLIST)
    queue = cache.subscribe()

    latest: dict[str, PriceTick] = {}
    try:
        while True:
            try:
                while True:
                    tick = queue.get_nowait()
                    latest[tick.ticker] = tick
            except asyncio.QueueEmpty:
                pass
            print(CLEAR_SCREEN + render(latest), flush=True)
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        pass
    finally:
        cache.unsubscribe(queue)
        await provider.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
