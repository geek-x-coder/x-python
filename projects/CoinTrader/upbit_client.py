import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import pyupbit
except ImportError:  # pragma: no cover
    pyupbit = None


class UpbitClient:
    def __init__(self, access_key: str, secret_key: str, dry_run: bool = True):
        self._logger = logging.getLogger("cointrader.upbit")
        self._dry_run = dry_run
        self._client = None

        if access_key and secret_key:
            if pyupbit is None:
                self._logger.warning(
                    "pyupbit not installed; running in dry-run mode even though keys are provided."
                )
                self._dry_run = True
            else:
                self._client = pyupbit.Upbit(access_key, secret_key)
                self._logger.info("Upbit client initialized (dry_run=%s).", dry_run)
        else:
            self._logger.warning("No Upbit API keys provided; running in dry-run mode only.")
            self._dry_run = True

    def get_current_price(self, ticker: str) -> Optional[float]:
        if self._client is None:
            return None
        return pyupbit.get_current_price(ticker)

    def get_ohlcv(self, ticker: str, interval: str = "minute", count: int = 200) -> Any:
        # interval: minute1, minute3, minute5, minute15, minute30, minute60, minute240, day, week, month
        if self._client is None:
            self._logger.debug("pyupbit not available: cannot fetch OHLCV for %s", ticker)
            return None
        return pyupbit.get_ohlcv(ticker, interval=interval, count=count)

    def get_balances(self) -> List[Dict[str, Any]]:
        if self._dry_run or self._client is None:
            # Return mock balance for dry-run
            return [{"currency": "KRW", "balance": "1000000", "avg_buy_price": None}]
        return self._client.get_balances()

    def get_krw_balance(self) -> float:
        """Return available KRW balance."""
        bal = 0.0
        for b in self.get_balances():
            if b.get("currency") == "KRW":
                try:
                    bal = float(b.get("balance", 0) or 0)
                except Exception:
                    bal = 0.0
                break
        return bal

    def get_position(self, currency: str) -> float:
        """Return amount held for a currency (e.g., BTC, ETH)."""
        for b in self.get_balances():
            if b.get("currency") == currency:
                try:
                    return float(b.get("balance", 0) or 0)
                except Exception:
                    return 0.0
        return 0.0

    def get_positions(self) -> List[Dict[str, Any]]:
        """Return non-zero holdings except KRW."""
        results = []
        for b in self.get_balances():
            try:
                amount = float(b.get("balance", 0) or 0)
            except Exception:
                continue
            if amount > 0 and b.get("currency") != "KRW":
                results.append(b)
        return results

    def buy_market(self, ticker: str, krw: float) -> Dict[str, Any]:
        if self._dry_run:
            self._logger.info("Dry run: BUY %s KRW of %s", krw, ticker)
            return {"uuid": None, "side": "buy", "price": krw, "ticker": ticker}

        self._logger.info("Sending market buy order: %s KRW of %s", krw, ticker)
        return self._client.buy_market_order(ticker, krw)

    def sell_market(self, ticker: str, volume: float) -> Dict[str, Any]:
        if self._dry_run:
            self._logger.info("Dry run: SELL %s of %s", volume, ticker)
            return {"uuid": None, "side": "sell", "volume": volume, "ticker": ticker}

        self._logger.info("Sending market sell order: %s of %s", volume, ticker)
        return self._client.sell_market_order(ticker, volume)

    def get_ticker_info(self, ticker: str) -> Dict[str, Any]:
        if self._client is None:
            return {}
        # This is a wrapper around public API; return basic ticker info.
        return pyupbit.get_tickers(fiat="KRW")

    def refresh(self) -> None:
        """Force any internal refresh logic; no-op for pyupbit."""
        return
