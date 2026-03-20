from typing import Dict, Optional


class RiskManager:
    """Manage position sizing and risk limits."""

    def __init__(self, config: Dict[str, any]):
        self.config = config or {}
        self.risk_per_trade = float(self.config.get("risk_per_trade", 0.01))
        self.max_positions = int(self.config.get("max_positions", 5))
        self.stop_loss_pct = float(self.config.get("stop_loss_pct", 0.02))
        self.take_profit_pct = float(self.config.get("take_profit_pct", 0.04))
        self.use_kelly = bool(self.config.get("use_kelly", False))
        self.kelly_win_rate = float(self.config.get("kelly_win_rate", 0.5))
        self.kelly_ratio = float(self.config.get("kelly_ratio", 1.5))

    def compute_order_amount(self, account_krw: float, current_price: float, win_rate: Optional[float] = None) -> float:
        """Compute how much KRW to use for a new position."""
        if account_krw <= 0 or current_price <= 0:
            return 0.0

        base = account_krw * self.risk_per_trade

        if self.use_kelly and win_rate is not None:
            kelly = win_rate - (1 - win_rate) / self.kelly_ratio
            kelly = max(0.0, min(kelly, 1.0))
            return account_krw * kelly

        return base

    def should_exit(self, entry_price: float, current_price: float) -> Optional[str]:
        """Return 'stop_loss', 'take_profit', or None based on configured thresholds."""
        if entry_price <= 0 or current_price <= 0:
            return None

        change = (current_price - entry_price) / entry_price
        if change <= -self.stop_loss_pct:
            return "stop_loss"
        if change >= self.take_profit_pct:
            return "take_profit"
        return None
