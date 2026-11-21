"""Run work after the webhook has answered 200.

MVP: a thread pool inside each gunicorn worker. To move to a real queue (Celery, RQ, ...),
change only `run_in_background`.
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()


def run_in_background(fn: Callable[..., Any], *args: Any) -> None:
    if settings.BACKGROUND_SYNC:  # tests and scripts: run inline, in the caller's DB connection
        _call(fn, *args)
    else:
        _get_executor().submit(_run_in_thread, fn, *args)


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=settings.BACKGROUND_WORKERS, thread_name_prefix="bg"
            )
        return _executor


def _run_in_thread(fn: Callable[..., Any], *args: Any) -> None:
    # Each pool thread has its own DB connection; drop stale/finished ones around each task.
    close_old_connections()
    try:
        _call(fn, *args)
    finally:
        close_old_connections()


def _call(fn: Callable[..., Any], *args: Any) -> None:
    try:
        fn(*args)
    except Exception:
        logger.exception("background task failed fn=%s", getattr(fn, "__name__", fn))
