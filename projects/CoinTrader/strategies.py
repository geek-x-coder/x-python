import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pandas as pd


class Strategy(ABC):
    """Base strategy interface."""

    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}
        self.logger = logging.getLogger(f"cointrader.strategy.{self.__class__.__name__}")

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def generate_signal(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        """Generate a signal for a given OHLCV dataframe.

        Returns a dict with at least:
          - action: "buy", "sell", or "hold"
          - confidence: float 0..1
        """

    def __repr__(self):
        return f"<{self.__class__.__name__} params={self.params}>"


class MovingAverageCrossoverStrategy(Strategy):
    def name(self) -> str:
        return "moving_average"

    def generate_signal(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        fast = int(self.params.get("fast_window", 5))
        slow = int(self.params.get("slow_window", 20))

        if len(ohlcv) < slow + 2:
            return {"action": "hold", "confidence": 0.0, "reason": "not enough data"}

        df = ohlcv.copy()
        df["ma_fast"] = df["close"].rolling(fast).mean()
        df["ma_slow"] = df["close"].rolling(slow).mean()
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if prev["ma_fast"] <= prev["ma_slow"] and last["ma_fast"] > last["ma_slow"]:
            return {"action": "buy", "confidence": 0.7, "reason": "golden cross"}
        if prev["ma_fast"] >= prev["ma_slow"] and last["ma_fast"] < last["ma_slow"]:
            return {"action": "sell", "confidence": 0.7, "reason": "death cross"}

        return {"action": "hold", "confidence": 0.2, "reason": "no crossover"}


class RSIStrategy(Strategy):
    def name(self) -> str:
        return "rsi"

    def generate_signal(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        period = int(self.params.get("rsi_period", 14))
        overbought = float(self.params.get("rsi_overbought", 70))
        oversold = float(self.params.get("rsi_oversold", 30))

        if len(ohlcv) < period + 2:
            return {"action": "hold", "confidence": 0.0, "reason": "not enough data"}

        df = ohlcv.copy()
        delta = df["close"].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ma_up = up.rolling(period).mean()
        ma_down = down.rolling(period).mean()
        rs = ma_up / ma_down
        rsi = 100 - (100 / (1 + rs))
        df["rsi"] = rsi

        last = df["rsi"].iloc[-1]
        if last > overbought:
            return {"action": "sell", "confidence": min(1.0, (last - overbought) / 20), "reason": "overbought"}
        if last < oversold:
            return {"action": "buy", "confidence": min(1.0, (oversold - last) / 20), "reason": "oversold"}

        return {"action": "hold", "confidence": 0.2, "reason": "neutral rsi"}


class BollingerBandsStrategy(Strategy):
    def name(self) -> str:
        return "bollinger"

    def generate_signal(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        window = int(self.params.get("bollinger_window", 20))
        std = float(self.params.get("bollinger_std", 2.0))

        if len(ohlcv) < window + 2:
            return {"action": "hold", "confidence": 0.0, "reason": "not enough data"}

        df = ohlcv.copy()
        df["ma"] = df["close"].rolling(window).mean()
        df["std"] = df["close"].rolling(window).std()
        df["upper"] = df["ma"] + std * df["std"]
        df["lower"] = df["ma"] - std * df["std"]

        last = df.iloc[-1]
        prev = df.iloc[-2]

        if prev["close"] > prev["upper"] and last["close"] < last["upper"]:
            return {"action": "sell", "confidence": 0.6, "reason": "reversion from upper band"}
        if prev["close"] < prev["lower"] and last["close"] > last["lower"]:
            return {"action": "buy", "confidence": 0.6, "reason": "reversion from lower band"}

        return {"action": "hold", "confidence": 0.2, "reason": "within bands"}


class MACDStrategy(Strategy):
    def name(self) -> str:
        return "macd"

    def generate_signal(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        fast = int(self.params.get("fast_ema", 12))
        slow = int(self.params.get("slow_ema", 26))
        signal_win = int(self.params.get("signal_window", 9))

        if len(ohlcv) < slow + signal_win + 2:
            return {"action": "hold", "confidence": 0.0, "reason": "not enough data"}

        df = ohlcv.copy()
        df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()
        df["macd"] = df["ema_fast"] - df["ema_slow"]
        df["signal"] = df["macd"].ewm(span=signal_win, adjust=False).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        if prev["macd"] <= prev["signal"] and last["macd"] > last["signal"]:
            return {"action": "buy", "confidence": 0.7, "reason": "MACD bullish crossover"}
        if prev["macd"] >= prev["signal"] and last["macd"] < last["signal"]:
            return {"action": "sell", "confidence": 0.7, "reason": "MACD bearish crossover"}

        return {"action": "hold", "confidence": 0.2, "reason": "MACD flat"}


class VWAPStrategy(Strategy):
    def name(self) -> str:
        return "vwap"

    def generate_signal(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        if len(ohlcv) < 2:
            return {"action": "hold", "confidence": 0.0, "reason": "not enough data"}

        df = ohlcv.copy()
        df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if prev["close"] <= prev["vwap"] and last["close"] > last["vwap"]:
            return {"action": "buy", "confidence": 0.65, "reason": "price crossed above VWAP"}
        if prev["close"] >= prev["vwap"] and last["close"] < last["vwap"]:
            return {"action": "sell", "confidence": 0.65, "reason": "price crossed below VWAP"}

        return {"action": "hold", "confidence": 0.2, "reason": "VWAP range"}


class VolumeBreakoutStrategy(Strategy):
    def name(self) -> str:
        return "volume_breakout"

    def generate_signal(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        window = int(self.params.get("volume_window", 20))
        multiplier = float(self.params.get("volume_multiplier", 2.5))

        if len(ohlcv) < window + 2:
            return {"action": "hold", "confidence": 0.0, "reason": "not enough data"}

        df = ohlcv.copy()
        df["vol_avg"] = df["volume"].rolling(window).mean()
        last = df.iloc[-1]
        prev = df.iloc[-2]

        breakout = last["volume"] > multiplier * df["vol_avg"].iloc[-2]
        rising = last["close"] > prev["close"]

        if breakout and rising:
            return {"action": "buy", "confidence": 0.6, "reason": "volume breakout"}
        if breakout and not rising:
            return {"action": "sell", "confidence": 0.6, "reason": "volume surge with drop"}

        return {"action": "hold", "confidence": 0.2, "reason": "no breakout"}


class MachineLearningStrategy(Strategy):
    def name(self) -> str:
        return "ml"

    def _calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def generate_signal(self, ohlcv: pd.DataFrame) -> Dict[str, Any]:
        """Simple ML-based prediction using historic returns.

        Falls back to a momentum rule if scikit-learn is not installed.
        """
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import train_test_split
        except ImportError:
            # Fallback: use momentum
            last = ohlcv["close"].iloc[-1]
            prev = ohlcv["close"].iloc[-2]
            if last > prev:
                return {"action": "buy", "confidence": 0.55, "reason": "momentum fallback"}
            return {"action": "hold", "confidence": 0.3, "reason": "momentum fallback"}

        lookback = int(self.params.get("lookback", 60))
        if len(ohlcv) < lookback + 10:
            return {"action": "hold", "confidence": 0.0, "reason": "not enough data"}

        df = ohlcv.copy().reset_index(drop=True)
        df["return"] = df["close"].pct_change().fillna(0)
        df["vol_chg"] = df["volume"].pct_change().fillna(0)
        
        # Add more features
        df["ma_5"] = df["close"].rolling(5).mean()
        df["ma_20"] = df["close"].rolling(20).mean()
        df["rsi"] = self._calculate_rsi(df["close"], 14)
        df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
        
        features = df[["return", "vol_chg", "ma_5", "ma_20", "rsi", "vwap"]].shift(1).dropna()
        target = (df["return"].shift(1) > 0).astype(int).iloc[1:]  # align with features

        # Ensure same length
        min_len = min(len(features), len(target))
        X = features.iloc[-min_len:]
        y = target.iloc[-min_len:]

        if len(X) < 10:
            return {"action": "hold", "confidence": 0.0, "reason": "not enough data"}

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = LogisticRegression(max_iter=200)
        model.fit(X_train, y_train)

        # Keep DataFrame columns so sklearn doesn't warn about missing feature names.
        pred = model.predict_proba(X_test[-1:])[0]
        prob_up = float(pred[1])

        history_win_rate = float(self.params.get("history_win_rate", 0.0) or 0.0)
        confidence_adj = 1.0 + (history_win_rate - 0.5) * 0.5

        if prob_up > 0.55:
            return {
                "action": "buy",
                "confidence": min(1.0, prob_up * confidence_adj),
                "reason": "ml predicted up",
            }
        if prob_up < 0.45:
            return {
                "action": "sell",
                "confidence": min(1.0, (1 - prob_up) * confidence_adj),
                "reason": "ml predicted down",
            }
        return {"action": "hold", "confidence": 0.3, "reason": "ml uncertain"}


class StrategyFactory:
    """Utility to create strategy instances by name."""

    REGISTRY = {
        "moving_average": MovingAverageCrossoverStrategy,
        "rsi": RSIStrategy,
        "bollinger": BollingerBandsStrategy,
        "macd": MACDStrategy,
        "vwap": VWAPStrategy,
        "volume_breakout": VolumeBreakoutStrategy,
        "ml": MachineLearningStrategy,
    }

    @classmethod
    def create(cls, name: str, params: Dict[str, Any] = None) -> Strategy:
        if name not in cls.REGISTRY:
            raise ValueError(f"Unknown strategy: {name}")
        return cls.REGISTRY[name](params=params)
