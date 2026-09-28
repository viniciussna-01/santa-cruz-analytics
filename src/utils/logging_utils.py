"""Logging padronizado no formato pedido: [INFO] mensagem."""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def get_logger(name: str = "santacruz") -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger(name)
    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        root = logging.getLogger("santacruz")
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        root.propagate = False
        _CONFIGURED = True
    return logger
