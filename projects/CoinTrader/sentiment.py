import logging
from typing import Any, Dict, Optional

# Optional dependencies - moved to lazy import
TEXTBLOB_AVAILABLE = False
TRANSFORMERS_AVAILABLE = False


class SentimentAnalyzer:
    """Analyze text sentiment using pluggable backends."""

    DEFAULT_POSITIVE = {
        "bull", "rally", "surge", "record", "breakout", "gain", "optimism", "buy", "strong", "uptrend",
        "recovery", "beat", "upgrade", "growth",
    }
    DEFAULT_NEGATIVE = {
        "bear", "crash", "plummet", "drop", "sell", "weak", "downtrend", "risk", "dump", "fear", "correction",
        "downgrade", "loss",
    }

    def __init__(self, logger: logging.Logger, config: Dict[str, Any]):
        self.logger = logger
        self.config = config or {}
        self.engine = self.config.get("engine", "simple")
        self.model_name = self.config.get("transformers_model", "distilbert-base-uncased-finetuned-sst-2-english")
        self._transformer = None
        self._textblob_available = False
        self._transformers_available = False

        # Lazy import
        if self.engine == "transformers":
            try:
                from transformers import pipeline
                self._transformer = pipeline("sentiment-analysis", model=self.model_name)
                self._transformers_available = True
            except Exception as e:
                self.logger.warning("Failed to load transformers sentiment model %s: %s", self.model_name, e)
                self._transformer = None
        elif self.engine == "textblob":
            try:
                import textblob
                self._textblob_available = True
            except ImportError:
                self.logger.warning("TextBlob not available")

    def score(self, text: str) -> float:
        """Return sentiment score in [-1, 1]."""
        if not text:
            return 0.0

        text = text.strip()
        if self.engine == "transformers" and self._transformer is not None:
            try:
                result = self._transformer(text[:512])
                if result and isinstance(result, list):
                    lbl = result[0].get("label", "NEUTRAL").upper()
                    score = float(result[0].get("score", 0.0))
                    if lbl in {"NEGATIVE", "LABEL_0"}:
                        return -score
                    if lbl in {"POSITIVE", "LABEL_1"}:
                        return score
            except Exception:
                self.logger.exception("Transformers sentiment analysis failed")

        if self.engine == "textblob" and self._textblob_available:
            try:
                from textblob import TextBlob
                tb = TextBlob(text)
                # polarity in [-1,1]
                return float(tb.sentiment.polarity)
            except Exception:
                self.logger.exception("TextBlob sentiment analysis failed")

        # Simple keyword-based scoring as fallback
        return self._simple_score(text)

    def _simple_score(self, text: str) -> float:
        t = text.lower()
        score = 0.0
        for word in self.config.get("positive_words", self.DEFAULT_POSITIVE):
            if word in t:
                score += 0.15
        for word in self.config.get("negative_words", self.DEFAULT_NEGATIVE):
            if word in t:
                score -= 0.17
        return max(-1.0, min(1.0, score))
