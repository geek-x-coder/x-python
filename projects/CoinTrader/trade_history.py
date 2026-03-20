import csv
import logging
import os
from typing import Dict, List, Optional


class TradeHistoryAnalyzer:
    """Analyze past trades from trade_history.csv."""

    def __init__(self, logger: logging.Logger, path: str):
        self.logger = logger
        self.path = path

    def _load_records(self) -> List[Dict[str, str]]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            self.logger.warning("Failed to read trade history: %s", e)
            return []

    def win_rate(self, symbol: Optional[str] = None) -> float:
        """Estimate win rate based on recent sell signals (heuristic)."""
        records = self._load_records()
        if symbol:
            records = [r for r in records if r.get("symbol") == symbol]

        sells = [r for r in records if r.get("action") == "sell"]
        if not sells:
            return 0.0

        wins = 0
        for s in sells:
            reason = (s.get("reason") or "").lower()
            if "take_profit" in reason or "profit" in reason or "golden" in reason:
                wins += 1
        return wins / len(sells) if sells else 0.0

    def latest_signals(self, limit: int = 50) -> List[Dict[str, str]]:
        records = self._load_records()
        return records[-limit:]
