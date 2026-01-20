from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO", json: bool = False) -> None:
    """Initialize logging for CLI and apps.

    Args:
        level: Logging level name (e.g., DEBUG, INFO, WARNING).
        json: If True, emit JSON logs with a simple structure.
    """
    lvl = getattr(logging, level.upper(), logging.INFO)

    if json:
        # Minimal JSON formatter to avoid adding heavy deps
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
                base = {
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                    base["exc_info"] = self.formatException(record.exc_info)
                return __import__("json").dumps(base, ensure_ascii=False)

        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logging.root.handlers[:] = [handler]
        logging.root.setLevel(lvl)
    else:
        logging.basicConfig(
            level=lvl,
            format="%(levelname)s %(name)s: %(message)s",
        )
