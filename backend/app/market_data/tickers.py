"""Seed price / drift / volatility / sector table for the market simulator."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TickerProfile:
    seed_price: float
    mu: float       # annual drift
    sigma: float    # annual volatility
    sector: str


TICKER_PROFILES: dict[str, TickerProfile] = {
    "AAPL":  TickerProfile(190.0, mu=0.08, sigma=0.28, sector="tech"),
    "GOOGL": TickerProfile(175.0, mu=0.07, sigma=0.30, sector="tech"),
    "MSFT":  TickerProfile(420.0, mu=0.09, sigma=0.25, sector="tech"),
    "AMZN":  TickerProfile(185.0, mu=0.10, sigma=0.32, sector="tech"),
    "TSLA":  TickerProfile(250.0, mu=0.05, sigma=0.55, sector="auto"),
    "NVDA":  TickerProfile(120.0, mu=0.15, sigma=0.50, sector="tech"),
    "META":  TickerProfile(500.0, mu=0.09, sigma=0.35, sector="tech"),
    "JPM":   TickerProfile(200.0, mu=0.06, sigma=0.20, sector="finance"),
    "V":     TickerProfile(275.0, mu=0.07, sigma=0.18, sector="finance"),
    "NFLX":  TickerProfile(650.0, mu=0.08, sigma=0.33, sector="media"),
}

DEFAULT_PROFILE = TickerProfile(seed_price=100.0, mu=0.06, sigma=0.30, sector="other")


def profile_for(ticker: str) -> TickerProfile:
    return TICKER_PROFILES.get(ticker.upper(), DEFAULT_PROFILE)
