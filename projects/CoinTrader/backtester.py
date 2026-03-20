import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from strategies import StrategyFactory
from upbit_client import UpbitClient


class Backtester:
    """Simple backtesting engine for comparing strategies on historical OHLCV data."""

    def __init__(
        self,
        upbit: UpbitClient,
        logger: logging.Logger,
        history_days: int = 180,
    ):
        self.upbit = upbit
        self.logger = logger
        self.history_days = history_days

    def run(self, symbol: str, strategy_name: str, params: Dict[str, any]) -> Dict[str, any]:
        self.logger.info("Backtesting %s on %s for %s days", strategy_name, symbol, self.history_days)
        ohlcv = self._fetch_history(symbol)
        if ohlcv is None or len(ohlcv) < 50:
            return {"symbol": symbol, "strategy": strategy_name, "error": "not enough data"}

        strat = StrategyFactory.create(strategy_name, params)
        return self._simulate(ohlcv, strat)

    def _fetch_history(self, symbol: str) -> Optional[pd.DataFrame]:
        lookback = self.history_days
        ohlcv = self.upbit.get_ohlcv(symbol, interval="day", count=lookback + 5)
        return ohlcv

    def _simulate(self, ohlcv: pd.DataFrame, strategy) -> Dict[str, any]:
        trades = []
        position = 0.0
        cash = 1.0
        base_price = float(ohlcv["close"].iloc[0])
        cash_in_krw = 1.0

        for idx in range(len(ohlcv)):
            window = ohlcv.iloc[: idx + 1]
            signal = strategy.generate_signal(window)
            price = float(window["close"].iloc[-1])
            if signal.get("action") == "buy" and position == 0:
                position = cash / price
                cash = 0
                trades.append({"date": window.index[-1], "action": "buy", "price": price})
            elif signal.get("action") == "sell" and position > 0:
                cash = position * price
                position = 0
                trades.append({"date": window.index[-1], "action": "sell", "price": price})

        final_value = cash + position * float(ohlcv["close"].iloc[-1])
        ret = final_value - 1.0
        win_trades = sum(1 for i in range(1, len(trades)) if trades[i]["action"] == "sell" and trades[i]["price"] > trades[i - 1]["price"])
        total_sells = sum(1 for t in trades if t["action"] == "sell")
        win_rate = float(win_trades) / total_sells if total_sells else 0.0

        return {
            "symbol": symbol,
            "strategy": strategy.name(),
            "trades": trades,
            "final_value": final_value,
            "return_pct": ret * 100,
            "win_rate": win_rate,
            "trade_count": len(trades),
        }
