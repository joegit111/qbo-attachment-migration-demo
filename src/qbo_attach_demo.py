# src/qbo_attach_demo.py
"""
Demo attachment uploader.

Reads mapping_verification_log.csv, filters to attachments with status == "ok",
applies idempotency based on qbo_attach_runlog.csv, and calls fake_qbo_api.attach_file
for work that has not previously succeeded.

Writes:
    qbo_attach_runlog.csv  - all attempts
    qbo_attach_errors.csv  - failed attempts
    qbo_attach_dups.csv    - skipped because already uploaded
"""

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set, Tuple
from .auth_qbo_demo import get_qbo_session

from .config import (
    MAPPING_VERIFICATION_LOG_CSV,
    QBO_ATTACH_RUNLOG_CSV,
    QBO_ATTACH_ERRORS_CSV,
    QBO_ATTACH_DUPS_CSV,
)
from .fake_qbo_api import attach_file


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_prior_successes() -> Set[Tuple[str, str]]:
    """
    Load prior successful uploads from the run log.

    Keyed by (qbo_entity_id, file_name).
    """
    successes: Set[Tuple[str, str]] = set()

    if not QBO_ATTACH_RUNLOG_CSV.exists():
        return successes

    with QBO_ATTACH_RUNLOG_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("outcome") == "success":
                key = (row.get("qbo_entity_id", ""), row.get("file_name", ""))
                successes.add(key)

    return successes


def _open_writer(path: Path, fieldnames: list) -> csv.DictWriter:
    """
    Open a CSV DictWriter in append mode, writing header if the file is new.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()

    f = path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    if not file_exists:
        writer.writeheader()
    # Hack: stash the file handle on the writer so caller can close it later
    writer._file = f  # type: ignore[attr-defined]
    return writer


def main() -> None:

    # In production this would return a real HTTP session and realm id.
    # Here it comes from auth_qbo_demo.FakeQboSession so the structure matches.
    session, realm_id = get_qbo_session()

    if not MAPPING_VERIFICATION_LOG_CSV.exists():
        raise RuntimeError(f"{MAPPING_VERIFICATION_LOG_CSV} not found; run mapping_verifier first")

    prior_successes = _load_prior_successes()

    run_fields = [
        "ts",
        "legacy_txnid_norm",
        "legacy_entity_type",
        "raw_legacy_id",
        "qbo_entity_type",
        "qbo_entity_id",
        "file_name",
        "file_path",
        "status_code",
        "error",
        "intuit_tid",
        "outcome",
    ]

    run_writer = _open_writer(QBO_ATTACH_RUNLOG_CSV, run_fields)
    err_writer = _open_writer(QBO_ATTACH_ERRORS_CSV, run_fields)
    dup_writer = _open_writer(QBO_ATTACH_DUPS_CSV, run_fields)

    total = 0
    uploaded = 0
    skipped = 0
    failed = 0

    with MAPPING_VERIFICATION_LOG_CSV.open("r", newline="", encoding="utf-8") as src_f:
        reader = csv.DictReader(src_f)
        for row in reader:
            if row.get("status") != "ok":
                continue

            total += 1

            qbo_entity_id = row.get("qbo_entity_id", "")
            qbo_entity_type = row.get("qbo_entity_type", "")
            file_name = row.get("file_name", "")
            file_path = row.get("file_path", "")

            key = (qbo_entity_id, file_name)

            base_record: Dict[str, str] = {
                "ts": _now_iso(),
                "legacy_txnid_norm": row.get("legacy_txnid_norm", ""),
                "legacy_entity_type": row.get("legacy_entity_type", ""),
                "raw_legacy_id": row.get("raw_legacy_id", ""),
                "qbo_entity_type": qbo_entity_type,
                "qbo_entity_id": qbo_entity_id,
                "file_name": file_name,
                "file_path": file_path,
            }

            if key in prior_successes:
                record = dict(base_record)
                record.update(
                    {
                        "status_code": "",
                        "error": "",
                        "intuit_tid": "",
                        "outcome": "skipped_already_uploaded",
                    }
                )
                run_writer.writerow(record)
                dup_writer.writerow(record)
                skipped += 1
                continue

            # Attempt the "upload" via fake API
            resp = attach_file(qbo_entity_type, qbo_entity_id, Path(file_path))

            if resp.status_code == 200:
                outcome = "success"
                uploaded += 1
            elif resp.status_code == 404:
                outcome = "file_missing"
                failed += 1
            else:
                outcome = "error"
                failed += 1

            record = dict(base_record)
            record.update(
                {
                    "status_code": str(resp.status_code),
                    "error": resp.error or "",
                    "intuit_tid": resp.intuit_tid or "",
                    "outcome": outcome,
                }
            )

            run_writer.writerow(record)
            if outcome != "success":
                err_writer.writerow(record)
            else:
                # So subsequent runs will see it as already uploaded
                prior_successes.add(key)

    # Close the underlying file handles to flush everything
    run_writer._file.close()  # type: ignore[attr-defined]
    err_writer._file.close()  # type: ignore[attr-defined]
    dup_writer._file.close()  # type: ignore[attr-defined]

    print(
        f"uploader finished: total candidates={total}, "
        f"uploaded={uploaded}, skipped={skipped}, failed={failed}"
    )


if __name__ == "__main__":
    main()
