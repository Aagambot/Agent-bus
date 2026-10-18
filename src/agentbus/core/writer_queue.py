"""Dedicated serialization queue for SQLite writes (SEC-2, NFR-2, NFR-6)."""

import queue
import random
import sqlite3
import threading
import time
from concurrent.futures import Future
from typing import Any, Callable
from pathlib import Path

from .db import create_connection


class WriterQueue:
    """Serializes all SQLite write operations through a dedicated background thread."""

    def __init__(self, db_path: str, timeout: float = 30.0):
        self.db_path = db_path
        self.timeout = timeout
        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name=f"AgentBusWriter-{Path(db_path).stem if db_path != ':memory:' else 'mem'}",
            daemon=True,
        )
        self._worker_thread.start()

    def submit(self, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        """Submit a write function to execute on the dedicated write connection."""
        if self._stop_event.is_set():
            raise RuntimeError("WriterQueue is shut down")

        future: Future = Future()
        self._queue.put((fn, future))
        return future.result()

    def _worker_loop(self) -> None:
        """Background thread executing write tasks serially with retry on locks."""
        conn = None
        try:
            while not self._stop_event.is_set():
                try:
                    item = self._queue.get(timeout=0.05)
                except queue.Empty:
                    if conn is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass
                        conn = None
                    continue

                if item is None:
                    break

                if conn is None:
                    conn = create_connection(self.db_path, timeout=self.timeout)

                fn, future = item
                if future.set_running_or_notify_cancel():
                    try:
                        result = self._execute_with_retry(conn, fn)
                        future.set_result(result)
                    except BaseException as exc:
                        future.set_exception(exc)
                    finally:
                        self._queue.task_done()
        finally:
            if conn is not None:
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass

    def _execute_with_retry(self, conn: sqlite3.Connection, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        """Execute a write transaction using BEGIN IMMEDIATE with exponential jitter backoff."""
        max_attempts = 15
        base_delay = 0.005  # 5ms

        for attempt in range(max_attempts):
            try:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    result = fn(conn)
                    conn.execute("COMMIT")
                    return result
                except BaseException:
                    conn.execute("ROLLBACK")
                    raise
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                    if attempt == max_attempts - 1:
                        raise
                    jitter = random.uniform(0.5, 1.5)
                    delay = min(base_delay * (2 ** attempt) * jitter, 1.0)
                    time.sleep(delay)
                else:
                    raise

    def close(self) -> None:
        """Gracefully shut down the writer queue."""
        if not self._stop_event.is_set():
            self._stop_event.set()
            self._queue.put(None)
            self._worker_thread.join(timeout=5.0)
