# src/build_attachment_inventory.py
"""
Build an attachments_inventory.csv from a legacy-style filesystem tree.

Expected layout under FILES_DIR:

    FILES_DIR/
        Bill/
            80ABC123/
                invoice_ABC123.txt
            80DEF456/
                invoice_DEF456.txt
            80MISSING/
                invoice_MISSING.txt

If FILES_DIR does not exist or is empty, a small synthetic tree with this
shape is created so the demo is runnable on a fresh clone.
"""

import csv
from pathlib import Path
from typing import Iterable

from .config import FILES_DIR, ATTACHMENTS_INVENTORY_CSV, normalize_legacy_id


def _ensure_sample_tree() -> None:
    """
    Create a tiny synthetic attachment tree if FILES_DIR is empty.
    """
    if FILES_DIR.exists():
        any_files = any(p.is_file() for p in FILES_DIR.rglob("*"))
        if any_files:
            return
    else:
        FILES_DIR.mkdir(parents=True, exist_ok=True)

    sample = [
        ("Bill", "80ABC123", "invoice_ABC123.txt"),
        ("Bill", "80DEF456", "invoice_DEF456.txt"),
        ("Bill", "80MISSING", "invoice_MISSING.txt"),
    ]

    for entity_type, raw_id, filename in sample:
        dir_path = FILES_DIR / entity_type / raw_id
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / filename
        if not file_path.exists():
            file_path.write_text(
                f"Synthetic attachment for {entity_type} {raw_id}\n",
                encoding="utf-8",
            )


def _iter_attachments(root: Path) -> Iterable[dict]:
    """
    Walk FILES_DIR and yield attachment rows.

    Assumes paths of the form:
        root / <entity_type> / <raw_legacy_id> / <filename>
    """
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            rel = file_path.relative_to(root)
        except ValueError:
            # Should not happen, but skip anything weird
            continue

        parts = rel.parts
        if len(parts) < 3:
            # Not in expected <entity_type>/<raw_legacy_id>/<filename> layout
            continue

        legacy_entity_type = parts[0]
        raw_legacy_id = parts[1]
        file_name = parts[-1]

        legacy_txnid_norm = normalize_legacy_id(raw_legacy_id)

        yield {
            "legacy_txnid_norm": legacy_txnid_norm,
            "legacy_entity_type": legacy_entity_type,
            "raw_legacy_id": raw_legacy_id,
            "file_name": file_name,
            "file_path": str(file_path),
        }


def main() -> None:
    _ensure_sample_tree()

    ATTACHMENTS_INVENTORY_CSV.parent.mkdir(parents=True, exist_ok=True)

    with ATTACHMENTS_INVENTORY_CSV.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "legacy_txnid_norm",
            "legacy_entity_type",
            "raw_legacy_id",
            "file_name",
            "file_path",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        count = 0
        for row in _iter_attachments(FILES_DIR):
            writer.writerow(row)
            count += 1

    print(f"wrote {count} attachment rows to {ATTACHMENTS_INVENTORY_CSV}")


if __name__ == "__main__":
    main()
