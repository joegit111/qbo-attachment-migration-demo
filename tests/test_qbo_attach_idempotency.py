import csv

from src.config import LOG_DIR, QBO_ATTACH_RUNLOG_CSV
from src.qbo_attach_demo import _load_prior_successes


def test_load_prior_successes_uses_success_outcome_only():
    # Ensure log dir exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create a fake run log with mixed outcomes
    with QBO_ATTACH_RUNLOG_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["qbo_entity_id", "file_name", "outcome"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "qbo_entity_id": "1001",
                "file_name": "invoice_ABC123.txt",
                "outcome": "success",
            }
        )
        writer.writerow(
            {
                "qbo_entity_id": "1001",
                "file_name": "invoice_ABC123.txt",
                "outcome": "error",
            }
        )
        writer.writerow(
            {
                "qbo_entity_id": "1002",
                "file_name": "invoice_DEF456.txt",
                "outcome": "success",
            }
        )

    successes = _load_prior_successes()

    assert ("1001", "invoice_ABC123.txt") in successes
    assert ("1002", "invoice_DEF456.txt") in successes
    assert len(successes) == 2
