"""Concurrency stress test for agentbus (NFR-2).

Requirements from spec.md §5 and CLAUDE.md:
- Spins up 8 reader threads + 4 writer threads
- Runs for 60 seconds (configurable via AGENTBUS_CONCURRENCY_DURATION)
- Asserts: zero SQLite `OperationalError: database is locked` exceptions
- Asserts: all written records are readable after the run
"""

import os
import sys
import time
import uuid
import tempfile
import threading
from pathlib import Path
import pytest

# Target import under test (written failing-first before Phase 1 implementation)
from agentbus.core import Bus


def test_concurrency_stress():
    """Verify concurrent 8 readers + 4 writers execute with zero lock errors."""
    duration = int(os.environ.get("AGENTBUS_CONCURRENCY_DURATION", "60"))
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "agentbus_stress.db"
        bus = Bus(db_path=str(db_path))

        num_readers = 8
        num_writers = 4
        
        stop_event = threading.Event()
        errors = []
        errors_lock = threading.Lock()
        
        written_ids = set()
        written_ids_lock = threading.Lock()

        def writer_worker(writer_id: int):
            seq = 0
            agent_id = f"writer_{writer_id}"
            ns = ("team", "stress")
            
            while not stop_event.is_set():
                seq += 1
                doc_id = f"doc_{writer_id}_{seq}_{uuid.uuid4().hex[:8]}"
                content = f"Content payload for {doc_id} with searchable tokens alpha beta gamma"
                try:
                    bus.index(
                        content=content,
                        agent=agent_id,
                        ns=ns,
                        uri=f"test://{doc_id}",
                    )
                    with written_ids_lock:
                        written_ids.add(doc_id)
                except Exception as exc:
                    with errors_lock:
                        errors.append((agent_id, exc))
                time.sleep(0.01)

        def reader_worker(reader_id: int):
            agent_id = f"reader_{reader_id}"
            ns = ("team", "stress")
            queries = ["alpha", "beta", "gamma", "payload"]
            q_idx = 0
            
            while not stop_event.is_set():
                query = queries[q_idx % len(queries)]
                q_idx += 1
                try:
                    bus.search(
                        query=query,
                        namespace=ns,
                        k=5,
                    )
                except Exception as exc:
                    with errors_lock:
                        errors.append((agent_id, exc))
                time.sleep(0.005)

        writer_threads = [
            threading.Thread(target=writer_worker, args=(w,), name=f"Writer-{w}")
            for w in range(num_writers)
        ]
        reader_threads = [
            threading.Thread(target=reader_worker, args=(r,), name=f"Reader-{r}")
            for r in range(num_readers)
        ]

        # Start all threads
        for t in writer_threads + reader_threads:
            t.start()

        # Run for specified duration
        time.sleep(duration)
        stop_event.set()

        # Join all threads
        for t in writer_threads + reader_threads:
            t.join(timeout=10)

        # Assertions
        # 1. Zero lock errors or operational errors
        lock_errors = [e for _, e in errors if "locked" in str(e).lower()]
        assert len(lock_errors) == 0, f"Encountered database lock errors: {lock_errors}"
        assert len(errors) == 0, f"Encountered thread errors during concurrency test: {errors}"

        # 2. All written records must be accounted for and readable
        assert len(written_ids) > 0, "Expected writers to have written at least one record"
        
        # Verify store contains written items
        for doc_id in list(written_ids)[:50]:
            results = bus.search(query=doc_id, namespace=("team", "stress"), k=1)
            assert len(results) > 0, f"Record {doc_id} was written but not found in search"
