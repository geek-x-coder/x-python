"""Run a one-shot portfolio simulation using historical OHLCV data.

This script uses the PortfolioManager simulation helper to backtest the strategies
listed in the config over the last `history_days` of data (default 180 days).

It prints a summary per symbol and the best-performing strategy for each symbol.

Usage:
    python run_simulation.py

"""

from datetime import datetime, timedelta

try:
    from market_regime import MarketRegimeDetector
    REGIME_AVAILABLE = True
except ImportError:
    MarketRegimeDetector = None
    REGIME_AVAILABLE = False

from config import load_config
from logger_setup import configure_logger
from portfolio import PortfolioManager
from risk import RiskManager
from upbit_client import UpbitClient


def main():
    logger = configure_logger("cointrader.simulation", "logs", "INFO")
    logger.info("Starting portfolio simulation")

    config = load_config()
    trade_cfg = config.get("trade", {})
    portfolio_cfg = config.get("portfolio", {})
    backtest_cfg = config.get("backtest", {})
    risk_cfg = config.get("risk", {})

    symbols = trade_cfg.get("symbols", [])
    strategies = backtest_cfg.get("strategies", [trade_cfg.get("strategy", "moving_average")])
    history_days = int(backtest_cfg.get("history_days", 180))

    logger.info(f"Simulation config: symbols={symbols}, strategies={strategies}, history_days={history_days}")

    upbit = UpbitClient(
        access_key=config.get("upbit", {}).get("access_key"),
        secret_key=config.get("upbit", {}).get("secret_key"),
        dry_run=True,
    )

    pm = PortfolioManager(
        upbit,
        logger=None,
        initial_balance_krw=float(portfolio_cfg.get("initial_capital", 1_000_000)),
        max_positions=int(portfolio_cfg.get("max_positions", 5)),
    )

    if REGIME_AVAILABLE:
        regime_detector = MarketRegimeDetector(
            logger=None,
            short_window=config.get("market", {}).get("regime_windows", {}).get("short", 20),
            long_window=config.get("market", {}).get("regime_windows", {}).get("long", 60),
            volatility_window=config.get("market", {}).get("volatility_window", 20),
            volatility_threshold=config.get("market", {}).get("volatility_threshold", 0.03),
        )
    else:
        regime_detector = None

    risk_mgr = RiskManager(risk_cfg)
    stop_loss_pct = float(risk_cfg.get("stop_loss_pct", 0.0))
    take_profit_pct = float(risk_cfg.get("take_profit_pct", 0.0))

    # only allow buys in bull/neutral regimes
    allow_trading_in = {"bull": True, "neutral": True, "bear": False}

    print("Simulation run:")
    print(f"  Symbols: {symbols}")
    print(f"  Strategies: {strategies}")
    print(f"  History window (days): {history_days}")
    print(f"  Stop loss: {stop_loss_pct:.2%}, Take profit: {take_profit_pct:.2%}")
    print()

    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=history_days)

    aggregate_results = []

    for symbol in symbols:
        print(f"-- Symbol: {symbol}")
        logger.info(f"Processing symbol: {symbol}")
        ohlcv = upbit.get_ohlcv(symbol, interval="day", count=history_days + 10)
        if ohlcv is None or ohlcv.empty:
            print("   [WARN] No OHLCV data (network/API issue?)")
            logger.warning(f"No OHLCV data for {symbol}")
            continue

        last_ts = ohlcv.index[-1]
        print(f"   Data range: {ohlcv.index[0].date()} -> {last_ts.date()}")

        best = pm.compare_strategies(symbol, strategies, ohlcv, pm.balance, verbose=True)
        if not best:
            print("   [WARN] No result from strategy comparison")
            logger.warning(f"No strategy result for {symbol}")
            continue

        # Re-simulate with risk management and regime filtering using the best candidate
        best_strategy = best.get("strategy")
        sim = pm.simulate_trades(
            symbol,
            best_strategy,
            ohlcv,
            pm.balance,
            start_date=start_dt,
            end_date=last_ts,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            regime_detector=regime_detector,
            allow_trading_in=allow_trading_in,
        )

        aggregate_results.append(sim)
        print(f"   Best strategy: {best_strategy} | sim return={sim.get('return_pct', 0):.2f}% | trades={len(sim.get('trades', []))}")
        logger.info(f"Symbol {symbol}: best strategy {best_strategy}, return {sim.get('return_pct', 0):.2f}%, trades {len(sim.get('trades', []))}")

        # Save simulation results to history
        date_str = datetime.now().strftime("%Y-%m-%d")
        history_file = f"history/simulation_{symbol}_{date_str}.json"
        import json
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(sim, f, indent=2, default=str)
        logger.info(f"Saved simulation results to {history_file}")

    if aggregate_results:
        total_return = sum(r.get("return_pct", 0) for r in aggregate_results) / len(aggregate_results)
        print()
        print(f"Average simulated return across symbols: {total_return:.2f}%")
        logger.info(f"Average return: {total_return:.2f}%")


if __name__ == "__main__":
    main()
