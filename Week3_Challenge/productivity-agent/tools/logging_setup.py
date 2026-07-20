"""
tools/logging_setup.py
-------------------------
One shared logger configuration every tool uses, so each tool is a
genuinely independent, observable service — it logs its own
invocation and outcome, regardless of what calls it (the agent
controller, a test, or anything else). This is separate from
logging_/run_logger.py, which records the AGGREGATE outcome of a full
agent run to the database; this is per-tool-call, plain-text logging,
using Python's standard logging module and the LOG_LEVEL/LOG_DIRECTORY
settings that already existed in config.py but were never wired up.
"""

import logging
import os

from config import settings

_configured = False


def get_tool_logger(tool_module_name: str) -> logging.Logger:
    """
    Return a logger for a tool module, configuring the shared handlers
    the first time this is called (safe to call many times).
    """
    global _configured

    if not _configured:
        os.makedirs(settings.LOG_DIRECTORY, exist_ok=True)
        log_file_path = os.path.join(settings.LOG_DIRECTORY, "tools.log")

        root_logger = logging.getLogger("tools")
        root_logger.setLevel(settings.LOG_LEVEL)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        file_handler = logging.FileHandler(log_file_path)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        _configured = True

    return logging.getLogger("tools." + tool_module_name)
