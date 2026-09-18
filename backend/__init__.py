"""
Backend package initialization
This file makes the backend directory a proper Python package
"""

from pathlib import Path
import logging

formatter = logging.Formatter(
    fmt="%(asctime)s-%(levelname)s - %(message)s", datefmt="%Y-%m-%d,%H:%M:%S"
)

logger = logging.getLogger("console_logger")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

f_logger = logging.getLogger("file_logger")
f_logger.setLevel(logging.DEBUG)

log_file_path = Path(__file__).parent.parent / "logs" / "debug_log.csv"
log_file_path.parent.mkdir(parents=True, exist_ok=True)

f_handler = logging.FileHandler(log_file_path, mode="w")
f_logger.addHandler(f_handler)