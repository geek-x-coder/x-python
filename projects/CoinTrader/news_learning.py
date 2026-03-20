import json
import logging
import os
import re
from typing import Dict, List, Optional

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
except ImportError:  # pragma: no cover
    TfidfVectorizer = None
    LogisticRegression = None



class NewsLearner:
    """Learn headline importance using token weights + optional TF-IDF model."""

    def __init__(self, logger: logging.Logger, storage_dir: str, config: Dict = None):
        self.logger = logger
        self.config = config or {}
        self.storage_dir = storage_dir
        self.weights_path = os.path.join(storage_dir, "news_weights.json")
        self.training_path = os.path.join(storage_dir, "news_training.json")
        self.weights: Dict[str, float] = {}
        self.training: List[Dict[str, any]] = []
        self._tfidf_model = None
        self._clf = None
        self._tokenizer = self._build_tokenizer()
        self._load_weights()
        self._load_training()
        self._build_model()

    def _build_tokenizer(self):
        if self.config.get("use_korean", False):
            try:
                from konlpy.tag import Okt

                okt = Okt()

                def tokenize(text: str) -> List[str]:
                    if not text:
                        return []
                    return [t for t in okt.morphs(text) if len(t) > 1]

                return tokenize
            except Exception:
                # konlpy/JPype can be difficult to initialize in some environments.
                # Fall back to a simple tokenizer.
                pass

        def tokenize(text: str) -> List[str]:
            if not text:
                return []
            text = text.lower()
            return re.findall(r"[a-z0-9]{2,}", text)

        return tokenize

    def _load_weights(self) -> None:
        if not os.path.exists(self.weights_path):
            return
        try:
            with open(self.weights_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.weights = {k: float(v) for k, v in data.items()}
        except Exception as e:
            self.logger.warning("Failed to load news weights: %s", e)

    def _persist_weights(self) -> None:
        try:
            with open(self.weights_path, "w", encoding="utf-8") as f:
                json.dump(self.weights, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning("Failed to persist news weights: %s", e)

    def _load_training(self) -> None:
        if not os.path.exists(self.training_path):
            return
        try:
            with open(self.training_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.training = data
        except Exception as e:
            self.logger.warning("Failed to load news training: %s", e)

    def _persist_training(self) -> None:
        try:
            with open(self.training_path, "w", encoding="utf-8") as f:
                json.dump(self.training, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning("Failed to persist news training: %s", e)

    def _build_model(self) -> None:
        if self.config.get("use_tfidf", False) and TfidfVectorizer is not None and LogisticRegression is not None:
            try:
                texts = [t["headline"] for t in self.training]
                targets = [int(t["direction"] > 0) for t in self.training]
                if len(texts) > 10 and len(set(targets)) > 1:
                    self._tfidf_model = TfidfVectorizer(max_features=2000, ngram_range=(1, 2))
                    X = self._tfidf_model.fit_transform(texts)
                    self._clf = LogisticRegression(max_iter=200)
                    self._clf.fit(X, targets)
            except Exception as e:
                self.logger.warning("Failed to build TF-IDF model: %s", e)
                self._tfidf_model = None
                self._clf = None

    def score_text(self, text: str) -> float:
        """Score text using learned weights plus optional TF-IDF model."""
        tfidf_score = 0.0
        if self._tfidf_model is not None and self._clf is not None:
            try:
                X = self._tfidf_model.transform([text])
                prob = self._clf.predict_proba(X)[0]
                tfidf_score = prob[1] - prob[0]
            except Exception:
                tfidf_score = 0.0

        tokens = self._tokenizer(text)
        weight_score = sum(self.weights.get(t, 0.0) for t in tokens)
        score = 0.0
        if self.config.get("blend", 0.5) > 0:
            blend = float(self.config.get("blend", 0.5))
            score = weight_score * (1 - blend) + tfidf_score * blend
        else:
            score = weight_score
        return max(-1.0, min(1.0, score))

    def update(self, headlines: List[str], price_change_pct: float) -> None:
        """Update weights and training dataset based on price movement."""
        if not headlines:
            return

        direction = 1 if price_change_pct > 0 else -1 if price_change_pct < 0 else 0
        if direction == 0:
            return

        factor = float(self.config.get("learning_rate", 0.01))
        for headline in headlines:
            for token in set(self._tokenizer(headline)):
                self.weights[token] = self.weights.get(token, 0.0) + direction * factor
                self.weights[token] = max(-2.0, min(2.0, self.weights[token]))

        self._persist_weights()

        # store training data, and retrain TF-IDF model occasionally
        self.training.append({"headline": " ".join(headlines), "direction": direction})
        if len(self.training) > int(self.config.get("max_training", 500)):
            self.training = self.training[-int(self.config.get("max_training", 500)) :]
        self._persist_training()
        self._build_model()

    def _load_weights(self) -> None:
        if not os.path.exists(self.weights_path):
            return
        try:
            with open(self.weights_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.weights = {k: float(v) for k, v in data.items()}
        except Exception as e:
            self.logger.warning("Failed to load news weights: %s", e)

    def _persist_weights(self) -> None:
        try:
            with open(self.weights_path, "w", encoding="utf-8") as f:
                json.dump(self.weights, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning("Failed to persist news weights: %s", e)

    def _tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        text = text.lower()
        tokens = re.findall(r"[a-z0-9]{2,}", text)
        return tokens

    def score_text(self, text: str) -> float:
        """Score text using learned weights. Returns value in [-1, 1]."""
        tokens = self._tokenize(text)
        score = 0.0
        for t in tokens:
            score += self.weights.get(t, 0.0)
        # clamp
        return max(-1.0, min(1.0, score))

    def update(self, headlines: List[str], price_change_pct: float) -> None:
        """Update weights given the direction of price movement after headlines."""
        if not headlines:
            return

        # if price went up, we want words to be positive; if down, negative
        direction = 1 if price_change_pct > 0 else -1 if price_change_pct < 0 else 0
        if direction == 0:
            return

        factor = float(self.config.get("learning_rate", 0.01))
        for headline in headlines:
            for token in set(self._tokenize(headline)):
                self.weights[token] = self.weights.get(token, 0.0) + direction * factor
                # simple decay / clamp to avoid runaway
                self.weights[token] = max(-2.0, min(2.0, self.weights[token]))

        self._persist_weights()
