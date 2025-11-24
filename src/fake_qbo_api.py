# src/fake_qbo_api.py
"""
Fake QuickBooks Online attachment API.

Provides a small function that mimics the shape of an HTTP call to
the QBO attachment endpoint. It performs basic file existence checks,
can randomly fail to exercise error handling, and returns a synthetic
Intuit-style transaction id on success.
"""

import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FakeQboResponse:
    status_code: int
    intuit_tid: Optional[str]
    error: Optional[str]
    duration_ms: int


def _generate_fake_tid() -> str:
    """
    Generate a synthetic Intuit-style id.

    The exact format does not matter; it just needs to look stable
    enough to log.
    """
    now_ns = time.time_ns()
    rand = random.randint(0, 999999)
    return f"1-{now_ns:x}-{rand:06d}"


def attach_file(entity_type: str, entity_id: str, file_path: Path, fail_rate: float = 0.1) -> FakeQboResponse:
    """
    "Upload" a file to a QuickBooks Online entity.

    Arguments:
        entity_type: QBO entity type, for example "Bill" or "Invoice".
        entity_id:   QBO entity identifier as a string.
        file_path:   Path to the local file to attach.
        fail_rate:   Probability between 0 and 1 of returning a synthetic failure.

    Returns:
        FakeQboResponse with:
          - status_code 200 on success, 500 on synthetic failure,
            404 if the file does not exist.
          - intuit_tid set on success, otherwise None.
          - error populated on failure, otherwise None.
          - duration_ms as a simple elapsed time measurement.
    """
    start = time.perf_counter()

    path = Path(file_path)

    if not path.is_file():
        duration_ms = int((time.perf_counter() - start) * 1000)
        return FakeQboResponse(
            status_code=404,
            intuit_tid=None,
            error=f"file not found: {path}",
            duration_ms=duration_ms,
        )

    # Decide whether this call "fails" or "succeeds"
    if random.random() < fail_rate:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return FakeQboResponse(
            status_code=500,
            intuit_tid=None,
            error=f"synthetic API failure attaching {path.name} to {entity_type} {entity_id}",
            duration_ms=duration_ms,
        )

    tid = _generate_fake_tid()
    duration_ms = int((time.perf_counter() - start) * 1000)
    return FakeQboResponse(
        status_code=200,
        intuit_tid=tid,
        error=None,
        duration_ms=duration_ms,
    )
