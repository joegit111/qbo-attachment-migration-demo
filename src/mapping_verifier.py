# src/mapping_verifier.py
"""
Verify that attachments have a corresponding mapping entry.

Joins attachments_inventory.csv to mapping_export.csv on
(legacy_txnid_norm, legacy_entity_type) and writes
mapping_verification_log.csv with a status field.
"""

import csv
from typing import Dict, Tuple
from .auth_qbo_demo import get_qbo_session

from .config import (
    ATTACHMENTS_INVENTORY_CSV,
    MAPPING_EXPORT_CSV,
    MAPPING_VERIFICATION_LOG_CSV,
    MAPPING_VERIFICATION_SKIPS_CSV,
)


def _load_mapping() -> Dict[Tuple[str, str], dict]:
    mapping: Dict[Tuple[str, str], dict] = {}

    with MAPPING_EXPORT_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["legacy_txnid_norm"], row["legacy_entity_type"])
            mapping[key] = row

    return mapping


def main() -> None:
    mapping = _load_mapping()

    MAPPING_VERIFICATION_LOG_CSV.parent.mkdir(parents=True, exist_ok=True)

    with ATTACHMENTS_INVENTORY_CSV.open("r", newline="", encoding="utf-8") as src_f, \
            MAPPING_VERIFICATION_LOG_CSV.open("w", newline="", encoding="utf-8") as log_f:

        src_reader = csv.DictReader(src_f)
        fieldnames = [
            "legacy_txnid_norm",
            "legacy_entity_type",
            "raw_legacy_id",
            "file_name",
            "file_path",
            "qbo_entity_type",
            "qbo_entity_id",
            "status",
            "reason",
        ]
        log_writer = csv.DictWriter(log_f, fieldnames=fieldnames)
        log_writer.writeheader()

        ok_count = 0
        missing_count = 0

        for row in src_reader:
            key = (row["legacy_txnid_norm"], row["legacy_entity_type"])
            mapping_row = mapping.get(key)

            out = dict(row)  # start with attachment columns
            if mapping_row is not None:
                out["qbo_entity_type"] = mapping_row.get("qbo_entity_type", "")
                out["qbo_entity_id"] = mapping_row.get("qbo_entity_id", "")
                out["status"] = "ok"
                out["reason"] = ""
                ok_count += 1
            else:
                out["qbo_entity_type"] = ""
                out["qbo_entity_id"] = ""
                out["status"] = "missing_mapping"
                out["reason"] = "no mapping for (legacy_txnid_norm, legacy_entity_type)"
                missing_count += 1

            log_writer.writerow(out)

    # Create an empty skips file with just a header, for completeness.
    with MAPPING_VERIFICATION_SKIPS_CSV.open("w", newline="", encoding="utf-8") as skip_f:
        skip_writer = csv.DictWriter(skip_f, fieldnames=["legacy_txnid_norm", "legacy_entity_type", "file_name", "reason"])
        skip_writer.writeheader()

    print(
        f"verification complete: {ok_count} with mapping, {missing_count} missing "
        f"(see {MAPPING_VERIFICATION_LOG_CSV})"
    )


if __name__ == "__main__":
    main()
