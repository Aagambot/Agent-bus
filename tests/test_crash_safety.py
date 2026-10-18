"""Crash safety test for agentbus (NFR-6).

Requirements from spec.md §5 and CLAUDE.md:
- Spawns a subprocess that writes to the DB in a loop
- Sends SIGKILL (or TerminateProcess on Windows) mid-write
- Re-opens the DB
- Asserts: DB passes `PRAGMA integrity_check`
- Asserts: no partial/corrupt records
"""

import os
import sys
import time
import sqlite3
import tempfile
import subprocess
from pathlib import Path
import pytest

# Target import under test (written failing-first before Phase 1 implementation)
from agentbus.core import Bus


WORKER_SCRIPT = """
import sys
import time
import uuid
from agentbus.core import Bus

db_path = sys.argv[1]
bus = Bus(db_path=db_path)

# Continuous tight write loop
seq = 0
while True:
    seq += 1
    doc_id = f"crash_test_doc_{seq}_{uuid.uuid4().hex}"
    bus.index(
        content=f"Crash test payload {seq} with substantial text to ensure active I/O " * 20,
        agent="crash_writer",
        ns=("team", "crash_test"),
        uri=f"test://{doc_id}",
    )
    time.sleep(0.001)
"""


def test_crash_safety_kill_mid_write():
    """Verify DB integrity after SIGKILL / TerminateProcess during active writes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "agentbus_crash.db"

        # Initialize the database instance first
        bus = Bus(db_path=str(db_path))
        bus.index(
            content="Initial baseline record prior to crash testing.",
            agent="setup",
            ns=("team", "crash_test"),
            uri="test://baseline",
        )

        # Launch background writer process
        env = os.environ.copy()
        python_path = str(Path(__file__).resolve().parent.parent / "src")
        env["PYTHONPATH"] = python_path + (os.pathsep + env.get("PYTHONPATH", ""))

        proc = subprocess.Popen(
            [sys.executable, "-c", WORKER_SCRIPT, str(db_path)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Allow worker process to perform active writes
        time.sleep(1.0)

        # Forcefully terminate mid-write (SIGKILL on POSIX, TerminateProcess on Windows)
        proc.kill()
        proc.wait(timeout=5)

        # Re-open the DB directly with SQLite to verify integrity
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        integrity_result = cursor.execute("PRAGMA integrity_check").fetchall()
        conn.close()

        # Assert PRAGMA integrity_check returns 'ok'
        assert integrity_result == [("ok",)], f"Integrity check failed: {integrity_result}"

        # Re-open through Bus and verify database is readable and undamaged
        reopened_bus = Bus(db_path=str(db_path))
        baseline_search = reopened_bus.search(
            query="baseline",
            namespace=("team", "crash_test"),
            k=5,
        )
        assert len(baseline_search) > 0, "Baseline record missing after crash recovery"
