import csv

from src.config import (
    DATA_DIR,
    ATTACHMENTS_INVENTORY_CSV,
    MAPPING_EXPORT_CSV,
    MAPPING_VERIFICATION_LOG_CSV,
)
from src.mapping_verifier import main as mapping_verifier_main


def test_mapping_verifier_labels_ok_and_missing():
    # Ensure data dir exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Create a tiny synthetic mapping_export.csv
    with MAPPING_EXPORT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "legacy_txnid_norm",
                "legacy_entity_type",
                "qbo_entity_type",
                "qbo_entity_id",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "legacy_txnid_norm": "ABC123",
                "legacy_entity_type": "Bill",
                "qbo_entity_type": "Bill",
                "qbo_entity_id": "1001",
            }
        )

    # Create a tiny attachments_inventory.csv with one mapped and one unmapped row
    with ATTACHMENTS_INVENTORY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "legacy_txnid_norm",
                "legacy_entity_type",
                "raw_legacy_id",
                "file_name",
                "file_path",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "legacy_txnid_norm": "ABC123",
                "legacy_entity_type": "Bill",
                "raw_legacy_id": "80ABC123",
                "file_name": "invoice_ABC123.txt",
                "file_path": "/tmp/invoice_ABC123.txt",
            }
        )
        writer.writerow(
            {
                "legacy_txnid_norm": "MISSING1",
                "legacy_entity_type": "Bill",
                "raw_legacy_id": "80MISSING1",
                "file_name": "invoice_missing.txt",
                "file_path": "/tmp/invoice_missing.txt",
            }
        )

    # Run the verifier
    mapping_verifier_main()

    # Inspect output
    with MAPPING_VERIFICATION_LOG_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2

    mapped = next(r for r in rows if r["legacy_txnid_norm"] == "ABC123")
    missing = next(r for r in rows if r["legacy_txnid_norm"] == "MISSING1")

    assert mapped["status"] == "ok"
    assert mapped["qbo_entity_id"] == "1001"

    assert missing["status"] == "missing_mapping"
    assert missing["qbo_entity_id"] == ""
