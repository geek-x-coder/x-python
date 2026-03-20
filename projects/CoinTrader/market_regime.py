import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from news import NewsAnalyzer
    NEWS_AVAILABLE = True
except ImportError:
    NewsAnalyzer = None
    NEWS_AVAILABLE = False


class MarketRegimeDetector:
    """Detect market regime (bull/bear/sideways) based on price action and news sentiment."""

    def __init__(
        self,
        logger: logging.Logger,
        news_analyzer: Optional[NewsAnalyzer] = None,
        short_window: int = 20,
        long_window: int = 60,
        volatility_window: int = 20,
        volatility_threshold: float = 0.03,
    ):
        self.logger = logger
        self.news_analyzer = news_analyzer
        self.short_window = short_window
        self.long_window = long_window
        self.volatility_window = volatility_window
        self.volatility_threshold = volatility_threshold

    def detect(self, ohlcv: pd.DataFrame) -> Dict[str, any]:
        result: Dict[str, any] = {"regime": "neutral", "score": 0.0, "reason": []}

        if len(ohlcv) < self.long_window + 2:
            result["reason"].append("not enough price history")
            return result

        series = ohlcv["close"]
        ma_short = series.rolling(self.short_window).mean()
        ma_long = series.rolling(self.long_window).mean()

        short_last = ma_short.iloc[-1]
        long_last = ma_long.iloc[-1]
        diff = (short_last - long_last) / long_last

        volatility = series.pct_change().rolling(self.volatility_window).std().iloc[-1]

        score = 0.0
        if diff > 0.015:
            score += 0.5
            result["reason"].append("short MA above long MA")
        elif diff < -0.015:
            score -= 0.5
            result["reason"].append("short MA below long MA")

        if volatility > self.volatility_threshold:
            score += 0.1
            result["reason"].append("elevated volatility")

        news_score = 0.0
        if self.news_analyzer is not None:
            news_score = self.news_analyzer.latest_score()
            score += news_score
            result["reason"].append(f"news_score={news_score:.2f}")

        if score > 0.4:
            regime = "bull"
        elif score < -0.3:
            regime = "bear"
        else:
            regime = "neutral"

        result.update({"regime": regime, "score": score, "volatility": float(volatility)})
        return result
