import logging
from typing import Dict, Optional

import requests


class SlackNotifier:
    def __init__(self, logger: logging.Logger, config: Dict[str, any]):
        self.logger = logger
        self.config = config
        self.enabled = bool(config.get("enabled", False))
        self.webhook = config.get("webhook_url")

    def post(self, text: str, blocks: Optional[list] = None) -> None:
        if not self.enabled or not self.webhook:
            return

        payload = {"text": text}
        if blocks:
            payload["blocks"] = blocks

        try:
            resp = requests.post(self.webhook, json=payload, timeout=5)
            resp.raise_for_status()
        except Exception as e:
            self.logger.warning("Failed to send Slack message: %s", e)
