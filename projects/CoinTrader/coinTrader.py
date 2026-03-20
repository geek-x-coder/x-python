import argparse
import csv
import logging
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from backtester import Backtester
from config import load_config
from logger_setup import configure_logger
from market_regime import MarketRegimeDetector
from news import NewsAnalyzer
from dashboard import create_dashboard_app
from portfolio import PortfolioManager
from risk import RiskManager
from slack_notifier import SlackNotifier
from strategies import StrategyFactory
from trade_history import TradeHistoryAnalyzer
from upbit_client import UpbitClient


class TradingEngine:
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        self.config = config
        self.logger = logger

        trade_config = config.get("trade", {})
        upbit_cfg = config.get("upbit", {})

        log_dir = config.get("logging", {}).get("dir", "logs")
        os.makedirs(log_dir, exist_ok=True)

        self.upbit = UpbitClient(
            access_key=upbit_cfg.get("access_key"),
            secret_key=upbit_cfg.get("secret_key"),
            dry_run=trade_config.get("dry_run", True),
        )

        self.news = NewsAnalyzer(logger.getChild("news"), config.get("news", {}), log_dir=log_dir)
        self.slack = SlackNotifier(logger.getChild("slack"), config.get("slack", {}))
        self.regime = MarketRegimeDetector(
            logger.getChild("regime"),
            news_analyzer=self.news,
            short_window=config.get("market", {}).get("regime_windows", {}).get("short", 20),
            long_window=config.get("market", {}).get("regime_windows", {}).get("long", 60),
            volatility_window=config.get("market", {}).get("volatility_window", 20),
            volatility_threshold=config.get("market", {}).get("volatility_threshold", 0.03),
        )

        self.backtester = Backtester(
            self.upbit,
            logger.getChild("backtest"),
            history_days=config.get("backtest", {}).get("history_days", 180),
        )

        self.watchlist = trade_config.get("symbols", [])
        self.focus = trade_config.get("focus_symbols", [])
        self.strategy_name = trade_config.get("strategy", "moving_average")
        self.strategy_params = trade_config.get("strategy_params", {})
        self.order_amount_krw = float(trade_config.get("order_amount_krw", 10000))
        self.risk = RiskManager(config.get("risk", {}))

        self.backtest_interval = int(config.get("backtest", {}).get("run_interval_minutes", 60))
        self.news_interval = int(config.get("news", {}).get("poll_interval_minutes", 15))
        self.loop_interval = int(trade_config.get("poll_interval_seconds", 60))

        dash_cfg = config.get("dashboard", {})
        self.dashboard_enabled = bool(dash_cfg.get("enabled", False))
        self.dashboard_host = dash_cfg.get("host", "0.0.0.0")
        self.dashboard_port = int(dash_cfg.get("port", 8000))

        self.trade_log_path = os.path.join(log_dir, "trade_history.csv")
        self._ensure_trade_log_header()

        self.history = TradeHistoryAnalyzer(logger.getChild("history"), self.trade_log_path)

        portfolio_cfg = config.get("portfolio", {})
        self.portfolio = PortfolioManager(
            self.upbit,
            logger.getChild("portfolio"),
            initial_balance_krw=float(portfolio_cfg.get("initial_capital", 1_000_000)),
            max_positions=int(portfolio_cfg.get("max_positions", 5)),
        )

        self.best_strategy_per_symbol: Dict[str, str] = {}

        self._stop_event = threading.Event()

        # tracking state for dashboard and adaptive sizing
        self.state: Dict[str, any] = {
            "strategy": self.strategy_name,
            "regime": "neutral",
            "news_score": 0.0,
            "last_signals": {},
            "positions": [],
            "performance": {},
            "account_krw": 0.0,
            "entry_prices": {},  # Track buy prices for P&L calculation
            "total_pnl": 0.0,    # Total profit/loss
            "last_backtest": {},
            "alerts": [],
            "news_headlines": [],
            "news_last_price": {},
        }

    def _ensure_trade_log_header(self) -> None:
        if not os.path.exists(self.trade_log_path):
            with open(self.trade_log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "symbol",
                    "action",
                    "confidence",
                    "reason",
                    "strategy",
                    "regime",
                    "pnl",
                ])

    def _log_trade(self, symbol: str, action: str, confidence: float, reason: str, strategy: str, regime: str, pnl: float = None) -> None:
        try:
            with open(self.trade_log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        datetime.utcnow().isoformat(),
                        symbol,
                        action,
                        confidence,
                        reason,
                        strategy,
                        regime,
                        pnl if pnl is not None else "",
                    ]
                )
        except Exception:
            self.logger.exception("Failed to write trade log")

    def _push_alert(self, symbol: str, action: str, confidence: float, reason: str, strategy: str, regime: str) -> None:
        alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "strategy": strategy,
            "regime": regime,
        }
        self.state.setdefault("alerts", []).insert(0, alert)
        # Keep alert list reasonably sized
        if len(self.state["alerts"]) > 200:
            self.state["alerts"] = self.state["alerts"][:200]

        # send Slack notification if configured
        try:
            text = f"[{symbol}] {action.upper()} ({reason}) strategy={strategy} regime={regime} conf={confidence:.2f}"
            self.slack.post(text)
        except Exception:
            pass

    def _choose_symbols(self) -> List[str]:
        if self.focus:
            return self.focus
        return self.watchlist

    def _select_strategy_for_regime(self, regime: str) -> str:
        mapping = self.config.get("trade", {}).get("regime_strategy_map", {})
        if mapping:
            return mapping.get(regime, self.strategy_name)
        # default mapping
        if regime == "bull":
            return "moving_average"
        if regime == "bear":
            return "rsi"
        return "bollinger"

    def _execute_signal(self, symbol: str, signal: Dict[str, Any], strategy: str, regime: str, last_price: float) -> None:
        action = signal.get("action")
        confidence = signal.get("confidence", 0)
        reason = signal.get("reason")

        self.logger.info("Signal for %s: %s (conf=%.2f) reason=%s", symbol, action, confidence, reason)

        if action == "hold":
            self._log_trade(symbol, action, confidence, reason, strategy, regime)
            self._push_alert(symbol, action, confidence, reason, strategy, regime)
            return

        if action == "buy":
            krw = float(signal.get("computed_order", self.order_amount_krw))
            self.upbit.buy_market(symbol, krw)
            self.state["entry_prices"][symbol] = last_price
            self._log_trade(symbol, action, confidence, reason, strategy, regime)
            self._push_alert(symbol, action, confidence, reason, strategy, regime)
            return

        if action == "sell":
            # find current holding volume for the ticker
            balances = self.upbit.get_balances()
            target_currency = symbol.split("-")[-1]
            volume = 0.0
            for b in balances:
                if b.get("currency") == target_currency:
                    try:
                        volume = float(b.get("balance", 0))
                    except Exception:
                        volume = 0.0
                    break
            if volume > 0:
                entry_price = self.state["entry_prices"].get(symbol, 0)
                pnl = None
                if entry_price > 0:
                    pnl = (last_price - entry_price) / entry_price * 100
                    self.state["total_pnl"] += pnl
                    del self.state["entry_prices"][symbol]
                self.upbit.sell_market(symbol, volume)
                self._log_trade(symbol, action, confidence, reason, strategy, regime, pnl)
                self._push_alert(symbol, action, confidence, reason, strategy, regime)
            else:
                self.logger.info("No holdings to sell for %s", symbol)
                self._log_trade(symbol, action, confidence, "no holdings", strategy, regime)
                self._push_alert(symbol, action, confidence, "no holdings", strategy, regime)
            return

    def _run_market_loop(self) -> None:
        if not self.config.get("trade", {}).get("enabled", True):
            self.logger.info("Market loop disabled in config")
            return

        self.logger.info("Starting market monitoring loop")

        while not self._stop_event.is_set():
            symbols = self._choose_symbols()

            account_krw = self.upbit.get_krw_balance()
            self.state["account_krw"] = account_krw

            # allocate capital per symbol
            weights = self.portfolio.allocate(symbols)

            for symbol in symbols:
                try:
                    allocation = weights.get(symbol, 0.0)
                    symbol_capital = account_krw * allocation
                    ohlcv = self.upbit.get_ohlcv(symbol, interval="minute", count=200)
                    if ohlcv is None or len(ohlcv) < 50:
                        self.logger.debug("Skipped %s: insufficient ohlcv", symbol)
                        continue

                    regime_info = self.regime.detect(ohlcv)
                    # Per-symbol best strategy (if available), else regime-based
                    strategy_name = self.best_strategy_per_symbol.get(symbol)
                    if not strategy_name:
                        strategy_name = self._select_strategy_for_regime(regime_info["regime"])

                    # Manage risk sizing / stop points
                    win_rate = self.history.win_rate(symbol) or self.state.get("last_backtest", {}).get("win_rate")
                    last_price = float(ohlcv["close"].iloc[-1])
                    computed_order = self.risk.compute_order_amount(symbol_capital, last_price, win_rate)

                    params = dict(self.strategy_params)
                    params["history_win_rate"] = win_rate
                    strat = StrategyFactory.create(strategy_name, params)
                    signal = strat.generate_signal(ohlcv)

                    # Learn from recent news + price change
                    prev_price = self.state.get("news_last_price", {}).get(symbol)
                    headlines = self.state.get("news_headlines", [])
                    if prev_price is not None and headlines:
                        try:
                            change = (last_price - float(prev_price)) / float(prev_price)
                            self.news.learn(headlines, change)
                        except Exception:
                            pass
                    # update latest snapshot for this symbol
                    if symbol:
                        self.state["news_last_price"][symbol] = last_price

                    # if we already have position, check stop loss / take profit using avg buy price
                    balances = self.upbit.get_balances()
                    # update state positions for dashboard
                    positions = [
                        b for b in balances if b.get("currency") and b.get("currency") != "KRW" and float(b.get("balance", 0) or 0) > 0
                    ]
                    self.state["positions"] = positions

                    # compute performance metrics
                    perf = {"positions": [], "total_value": 0.0, "total_cost": 0.0, "unrealized_pnl": 0.0}
                    for p in positions:
                        try:
                            cur_amt = float(p.get("balance", 0) or 0)
                        except Exception:
                            cur_amt = 0.0
                        cur_currency = p.get("currency")
                        avg_price = 0.0
                        try:
                            avg_price = float(p.get("avg_buy_price", 0) or 0)
                        except Exception:
                            avg_price = 0.0
                        cur_price = self.upbit.get_current_price(f"KRW-{cur_currency}")
                        cur_price = float(cur_price or 0)
                        value = cur_price * cur_amt
                        cost = avg_price * cur_amt
                        pnl = None
                        if avg_price > 0:
                            pnl = (cur_price - avg_price) / avg_price

                        perf["positions"].append(
                            {
                                "symbol": f"KRW-{cur_currency}",
                                "amount": cur_amt,
                                "avg_buy_price": avg_price,
                                "current_price": cur_price,
                                "value_krw": value,
                                "cost_krw": cost,
                                "unrealized_return": pnl,
                            }
                        )
                        perf["total_value"] += value
                        perf["total_cost"] += cost
                        if pnl is not None:
                            perf["unrealized_pnl"] += (value - cost)
                    perf["total_pnl"] = self.state.get("total_pnl", 0.0)
                    self.state["performance"] = perf

                    target_currency = symbol.split("-")[-1]
                    avg_buy_price = None
                    for b in balances:
                        if b.get("currency") == target_currency:
                            try:
                                avg_buy_price = float(b.get("avg_buy_price") or 0)
                            except Exception:
                                avg_buy_price = None
                            break

                    if avg_buy_price and avg_buy_price > 0:
                        exit_reason = self.risk.should_exit(avg_buy_price, last_price)
                        if exit_reason == "stop_loss":
                            signal = {"action": "sell", "confidence": 0.9, "reason": "stop_loss"}
                        elif exit_reason == "take_profit":
                            signal = {"action": "sell", "confidence": 0.9, "reason": "take_profit"}

                    self.state["regime"] = regime_info.get("regime")
                    self.state["news_score"] = self.news.latest_score()
                    self.state["strategy"] = strategy_name
                    self.state["last_signals"][symbol] = signal

                    self.logger.info(
                        "%s regime=%s score=%.2f selected_strategy=%s order_amt=%.0f",
                        symbol,
                        regime_info["regime"],
                        regime_info["score"],
                        strategy_name,
                        computed_order,
                    )

                    # pass computed order into execute logic
                    signal["computed_order"] = computed_order
                    self._execute_signal(symbol, signal, strategy_name, regime_info.get("regime", ""), last_price)
                except Exception as e:
                    self.logger.exception("Error processing %s: %s", symbol, e)

            time.sleep(self.loop_interval)

    def _run_backtest_loop(self) -> None:
        if not self.config.get("backtest", {}).get("enabled", False):
            self.logger.info("Backtesting disabled in config")
            return

        self.logger.info("Starting backtester loop (%s min interval)", self.backtest_interval)
        while not self._stop_event.wait(self.backtest_interval * 60):
            strategies = self.config.get("backtest", {}).get("strategies", [self.strategy_name])
            best_result = None
            for symbol in self._choose_symbols():
                best_for_symbol = None
                for strategy in strategies:
                    try:
                        result = self.backtester.run(symbol, strategy, self.strategy_params)
                        self.logger.info(
                            "Backtest %s @ %s: return=%.2f%% win_rate=%.2f%% trades=%s",
                            symbol,
                            strategy,
                            result.get("return_pct", 0.0),
                            result.get("win_rate", 0.0) * 100,
                            result.get("trade_count", 0),
                        )

                        if best_for_symbol is None or result.get("return_pct", 0.0) > best_for_symbol.get("return_pct", 0.0):
                            best_for_symbol = result
                        if best_result is None or result.get("return_pct", 0.0) > best_result.get("return_pct", 0.0):
                            best_result = result
                    except Exception as e:
                        self.logger.exception("Backtest error %s %s: %s", symbol, strategy, e)

                if best_for_symbol is not None:
                    self.best_strategy_per_symbol[symbol] = best_for_symbol.get("strategy")

            if best_result is not None:
                self.state["last_backtest"] = best_result
                updated_strategy = best_result.get("strategy")
                if updated_strategy and updated_strategy != self.strategy_name:
                    self.logger.info(
                        "Updating active strategy from %s to %s based on backtest results",
                        self.strategy_name,
                        updated_strategy,
                    )
                    self.strategy_name = updated_strategy
                    self.state["strategy"] = updated_strategy

    def _run_news_loop(self) -> None:
        if not self.config.get("news", {}).get("enabled", False):
            self.logger.info("News fetching disabled in config")
            return

        interval = self.news_interval
        self.logger.info("Starting news polling loop (%s min interval)", interval)

        while not self._stop_event.wait(interval * 60):
            try:
                items = self.news.fetch()
                headlines = [i.title for i in items]
                self.state["news_headlines"] = headlines

                # record price snapshot for later learning (use first watched symbol price)
                symbol = self._choose_symbols()[0] if self._choose_symbols() else None
                if symbol:
                    price = self.upbit.get_current_price(symbol)
                    if price is not None:
                        self.state["news_last_price"][symbol] = float(price)

                self.logger.debug(
                    "Fetched %s news items, current score=%.2f",
                    len(items),
                    self.news.latest_score(),
                )
            except Exception as e:
                self.logger.exception("News fetch error: %s", e)

    def _start_dashboard(self) -> None:
        if not self.dashboard_enabled:
            return
        try:
            import uvicorn
        except ImportError:
            self.logger.warning("uvicorn not installed; dashboard disabled")
            return

        try:
            app = create_dashboard_app(self)
        except Exception as e:
            self.logger.warning("Dashboard not available: %s", e)
            return
        self.logger.info("Starting dashboard on %s:%s", self.dashboard_host, self.dashboard_port)

        def _run_app():
            uvicorn.run(app, host=self.dashboard_host, port=self.dashboard_port, log_level="info")

        t = threading.Thread(target=_run_app, name="dashboard", daemon=True)
        t.start()

    def run(self) -> None:
        self.logger.info("Trading engine starting %s", datetime.utcnow().isoformat())
        threads: List[threading.Thread] = []

        # Start dashboard if enabled
        self._start_dashboard()

        # Start background tasks
        t_market = threading.Thread(target=self._run_market_loop, name="market-loop", daemon=True)
        threads.append(t_market)
        t_market.start()

        t_news = threading.Thread(target=self._run_news_loop, name="news-loop", daemon=True)
        threads.append(t_news)
        t_news.start()

        t_backtest = threading.Thread(target=self._run_backtest_loop, name="backtest-loop", daemon=True)
        threads.append(t_backtest)
        t_backtest.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down (KeyboardInterrupt)")
            self._stop_event.set()
            for t in threads:
                t.join(timeout=2)
            self.logger.info("Stopped")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Upbit automatic trading engine")
    parser.add_argument("--config", default=None, help="Path to appConfig.json")
    parser.add_argument("--dry-run", action="store_true", help="Run without executing real orders")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    log_dir = config.get("logging", {}).get("dir", "logs")
    log_level = config.get("logging", {}).get("level", "INFO")

    logger = configure_logger("cointrader", log_dir, log_level)

    if args.dry_run:
        logger.info("Overriding config to dry-run mode")
        config.setdefault("trade", {})["dry_run"] = True

    engine = TradingEngine(config, logger)
    engine.run()


if __name__ == "__main__":
    main()
