import random

from app.market_data.cache import PriceCache
from app.market_data.simulator import SimulatedMarketDataProvider

DT = 0.5 / (252 * 6.5 * 3600)


def test_step_is_deterministic_with_seeded_rng():
    cache = PriceCache()
    sim_a = SimulatedMarketDataProvider(cache, rng=random.Random(42))
    sim_b = SimulatedMarketDataProvider(cache, rng=random.Random(42))
    sim_a._seed("AAPL")
    sim_b._seed("AAPL")

    ticks_a = sim_a._step(DT)
    ticks_b = sim_b._step(DT)

    assert ticks_a[0].price == ticks_b[0].price


def test_step_returns_one_tick_per_tracked_ticker():
    cache = PriceCache()
    sim = SimulatedMarketDataProvider(cache, rng=random.Random(1))
    sim._seed("AAPL")
    sim._seed("MSFT")

    ticks = sim._step(DT)

    assert {tick.ticker for tick in ticks} == {"AAPL", "MSFT"}


def test_step_with_no_tracked_tickers_returns_no_ticks():
    cache = PriceCache()
    sim = SimulatedMarketDataProvider(cache, rng=random.Random(1))

    assert sim._step(DT) == []


def test_prices_never_go_negative_across_many_steps():
    cache = PriceCache()
    sim = SimulatedMarketDataProvider(cache, rng=random.Random(1))
    sim._seed("TSLA")  # highest sigma in the table -- most likely to stress the floor

    for _ in range(10_000):
        sim._step(DT)

    assert sim._prices["TSLA"] > 0


def test_tech_sector_moves_more_correlated_than_cross_sector():
    """Sanity check on the one-factor-per-sector model, not an exact-value assertion."""
    cache = PriceCache()
    sim = SimulatedMarketDataProvider(cache, rng=random.Random(7))
    for ticker in ("AAPL", "MSFT", "JPM"):  # AAPL/MSFT = tech, JPM = finance
        sim._seed(ticker)

    returns: dict[str, list[float]] = {"AAPL": [], "MSFT": [], "JPM": []}
    for _ in range(500):
        for tick in sim._step(DT):
            returns[tick.ticker].append(tick.change_percent)

    def correlation(a: list[float], b: list[float]) -> float:
        n = len(a)
        mean_a, mean_b = sum(a) / n, sum(b) / n
        cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / n
        std_a = (sum((x - mean_a) ** 2 for x in a) / n) ** 0.5
        std_b = (sum((y - mean_b) ** 2 for y in b) / n) ** 0.5
        return cov / (std_a * std_b)

    tech_corr = correlation(returns["AAPL"], returns["MSFT"])
    cross_corr = correlation(returns["AAPL"], returns["JPM"])

    assert tech_corr > cross_corr
