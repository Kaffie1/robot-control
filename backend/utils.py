"""Minimal utils for agent-only mode."""

import logging
import sys
from typing import Any

# Setup basic logging
def _get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


fault_logger = _get_logger("fault")
trace_logger = _get_logger("trace")


def get_fault_logger():
    return fault_logger


def get_fault_trace_logger():
    return trace_logger


def short_error(result: dict[str, Any]) -> str:
    """Extract short error message from command result."""
    stderr = str(result.get("stderr") or "").strip()
    if stderr:
        lines = stderr.split("\n")
        return lines[0][:200] if lines else stderr[:200]
    stdout = str(result.get("stdout") or "").strip()
    return stdout[:200] if stdout else "unknown error"
