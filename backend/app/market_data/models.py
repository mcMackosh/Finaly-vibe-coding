"""Price data models shared by all market data providers."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class PriceTick(BaseModel):
    """One price update for one ticker."""

    ticker: str
    price: float
    previous_price: float
    change: float
    change_percent: float
    direction: Direction
    timestamp: datetime

    @classmethod
    def build(cls, ticker: str, price: float, previous_price: float) -> "PriceTick":
        change = price - previous_price
        return cls(
            ticker=ticker,
            price=round(price, 4),
            previous_price=round(previous_price, 4),
            change=round(change, 4),
            change_percent=round((change / previous_price) * 100, 4) if previous_price else 0.0,
            direction=Direction.UP if change > 0 else Direction.DOWN if change < 0 else Direction.FLAT,
            timestamp=datetime.now(timezone.utc),
        )
