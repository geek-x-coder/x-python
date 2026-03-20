import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

from sentiment import SentimentAnalyzer
from news_learning import NewsLearner


@dataclass
class NewsItem:
    title: str
    description: str
    url: str
    published_at: str
    source: str
    score: float


class NewsAnalyzer:
    """Fetch news and assign a sentiment / severity score."""

    def __init__(self, logger: logging.Logger, config: Dict[str, any], log_dir: str = "logs"):
        self.logger = logger
        self.config = config
        self.last_score = 0.0
        self.last_fetch = 0.0
        self.cache: List[NewsItem] = []
        self._sentiment = SentimentAnalyzer(logger.getChild("sentiment"), config.get("sentiment", {}))
        self._learner = NewsLearner(logger.getChild("learner"), log_dir, config.get("news_learning", {}))

    def _score_text(self, text: str) -> float:
        base = self._sentiment.score(text)
        learned = self._learner.score_text(text)
        # blending base sentiment and learned weights
        return max(-1.0, min(1.0, base * 0.6 + learned * 0.4))

    def learn(self, headlines: List[str], price_change_pct: float) -> None:
        """Update learned weights based on recent headlines and price movement."""
        try:
            self._learner.update(headlines, price_change_pct)
        except Exception as e:
            self.logger.warning("News learner update failed: %s", e)

    def fetch(self) -> List[NewsItem]:
        if not self.config.get("enabled", False):
            return []

        source = self.config.get("source", "newsapi")
        if source == "newsapi":
            return self._fetch_newsapi()
        return []

    def _fetch_newsapi(self) -> List[NewsItem]:
        key = self.config.get("api_key")
        if not key:
            self.logger.warning("NewsAPI key not configured.")
            return []

        keywords = self.config.get("keywords", [])
        q = " OR ".join(keywords) if keywords else "crypto"
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": q,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": key,
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            self.logger.warning("Failed to fetch news: %s", e)
            return []

        data = resp.json()
        articles = data.get("articles", [])

        items: List[NewsItem] = []
        score = 0.0
        for a in articles:
            title = a.get("title") or ""
            desc = a.get("description") or ""
            s = self._score_text(title) + self._score_text(desc)
            score += s
            items.append(
                NewsItem(
                    title=title,
                    description=desc,
                    url=a.get("url", ""),
                    published_at=a.get("publishedAt", ""),
                    source=a.get("source", {}).get("name", ""),
                    score=s,
                )
            )

        if items:
            self.last_score = max(-1.0, min(1.0, score / len(items)))
            self.cache = items
            self.last_fetch = time.time()
        return items

    def latest_score(self) -> float:
        return self.last_score
