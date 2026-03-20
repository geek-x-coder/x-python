import logging
import os
from logging.handlers import TimedRotatingFileHandler


def configure_logger(name: str, log_dir: str, level: str = "INFO") -> logging.Logger:
    """Configure a logger that writes to a daily rotating file and stdout."""
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        formatter = logging.Formatter(fmt)

        file_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_dir, "cointrader.log"),
            when="midnight",
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger
