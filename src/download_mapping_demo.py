# src/download_mapping_demo.py
"""
Generate a synthetic QbdtEntityIdMapping-style export.

Writes mapping_export.csv under DATA_DIR with a few rows that match
the sample legacy IDs used by build_attachment_inventory.py.
"""

import csv
from pathlib import Path
from .auth_qbo_demo import get_qbo_session

from .config import DATA_DIR, MAPPING_EXPORT_CSV, normalize_legacy_id


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Sample legacy IDs that match what build_attachment_inventory will generate
    # Raw IDs include the "80" prefix to exercise normalization.
    sample_legacy = [
        ("Bill", "80ABC123", "1001"),
        ("Bill", "80DEF456", "1002"),
        # Intentionally omit one ID that will exist in the filesystem
        # to show how missing mappings are handled.
        # ("Bill", "80MISSING", "1003"),
    ]

    rows = []
    for legacy_entity_type, raw_id, qbo_entity_id in sample_legacy:
        legacy_norm = normalize_legacy_id(raw_id)
        rows.append(
            {
                "legacy_txnid_norm": legacy_norm,
                "legacy_entity_type": legacy_entity_type,
                "qbo_entity_type": "Bill",
                "qbo_entity_id": qbo_entity_id,
            }
        )

    MAPPING_EXPORT_CSV.parent.mkdir(parents=True, exist_ok=True)

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
        writer.writerows(rows)

    print(f"wrote synthetic mapping export to {MAPPING_EXPORT_CSV}")


if __name__ == "__main__":
    main()
