import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from backtester import Backtester
from strategies import StrategyFactory
from upbit_client import UpbitClient


@dataclass
class Position:
    symbol: str
    amount: float
    avg_price: float


class PortfolioManager:
    """Manage per-symbol strategy allocation and simulate portfolio changes."""

    def __init__(
        self,
        upbit: UpbitClient,
        logger: logging.Logger,
        initial_balance_krw: float = 1_000_000,
        max_positions: int = 5,
    ):
        self.upbit = upbit
        self.logger = logger
        self.balance = float(initial_balance_krw)
        self.positions: Dict[str, Position] = {}
        self.max_positions = max_positions

    def allocate(self, symbols: List[str], weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Allocate capital by symbol (simple equal-weight if no weights)."""
        if not symbols:
            return {}

        if weights is None:
            weight = 1.0 / len(symbols)
            return {s: weight for s in symbols}

        # normalize weights
        total = sum(weights.values())
        if total <= 0:
            return {s: 1.0 / len(symbols) for s in symbols}
        return {s: weights.get(s, 0) / total for s in symbols}

    def simulate_trades(
        self,
        symbol: str,
        strategy_name: str,
        ohlcv: pd.DataFrame,
        initial_balance: float,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        stop_loss_pct: float = 0.0,
        take_profit_pct: float = 0.0,
        regime_detector: Optional["MarketRegimeDetector"] = None,
        allow_trading_in: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, any]:
        """Simulate trading for one symbol using a given strategy and time range.

        Optionally applies stop loss / take profit and regime filtering.
        """
        # use daily data for simulation
        df = ohlcv.copy()
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]

        if df.empty:
            return {"symbol": symbol, "error": "no data"}

        strategy = StrategyFactory.create(strategy_name, {})
        cash = float(initial_balance)
        position = 0.0
        entry_price = 0.0

        trades = []
        for idx in range(len(df)):
            window = df.iloc[: idx + 1]

            # Optionally skip trading in certain regimes
            if regime_detector is not None:
                regime_info = regime_detector.detect(window)
                allow = True
                if allow_trading_in is not None:
                    allow = allow_trading_in.get(regime_info.get("regime"), True)
                if not allow:
                    # In disallowed regime, do not enter new positions
                    if position > 0:
                        # still allow exits via stoploss/takeprofit
                        pass
                    else:
                        continue

            signal = strategy.generate_signal(window)
            price = float(window["close"].iloc[-1])

            if position > 0:
                # enforce risk management exits
                change = (price - entry_price) / entry_price if entry_price > 0 else 0
                if stop_loss_pct > 0 and change <= -abs(stop_loss_pct):
                    cash = position * price
                    position = 0
                    trades.append({
                        "date": window.index[-1],
                        "action": "sell",
                        "price": price,
                        "reason": "stop_loss",
                    })
                    continue
                if take_profit_pct > 0 and change >= abs(take_profit_pct):
                    cash = position * price
                    position = 0
                    trades.append({
                        "date": window.index[-1],
                        "action": "sell",
                        "price": price,
                        "reason": "take_profit",
                    })
                    continue

            if signal["action"] == "buy" and cash > 0:
                position = cash / price
                entry_price = price
                cash = 0
                trades.append({"date": window.index[-1], "action": "buy", "price": price})
            elif signal["action"] == "sell" and position > 0:
                cash = position * price
                position = 0
                trades.append({"date": window.index[-1], "action": "sell", "price": price})

        final_value = cash + position * float(df["close"].iloc[-1])
        return {
            "symbol": symbol,
            "strategy": strategy_name,
            "final_value": final_value,
            "return_pct": (final_value / initial_balance - 1) * 100,
            "trades": trades,
        }

    def compare_strategies(
        self,
        symbol: str,
        strategies: List[str],
        ohlcv: pd.DataFrame,
        initial_balance: float,
        verbose: bool = False,
    ) -> Dict[str, any]:
        best = None
        for strat in strategies:
            if verbose:
                print(f"   Testing strategy: {strat}")
            res = self.simulate_trades(symbol, strat, ohlcv, initial_balance)
            if best is None or res.get("return_pct", 0) > best.get("return_pct", 0):
                best = res
        return best or {}
