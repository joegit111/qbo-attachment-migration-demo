# src/config.py
"""
Central configuration for the QBO attachment demo pipeline.

Uses environment variables when present, otherwise falls back to
paths relative to the repository root.
"""

import os
from pathlib import Path

# Resolve repo root as parent of the src directory
ROOT_DIR = Path(__file__).resolve().parent.parent

# Base directories, overridable via environment variables
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT_DIR / "data"))
FILES_DIR = Path(os.environ.get("FILES_DIR", ROOT_DIR / "files"))
LOG_DIR = Path(os.environ.get("LOG_DIR", ROOT_DIR / "logs"))

# Ensure the log directory exists so writers do not explode
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Default CSV filenames, kept here so everything uses the same names
ATTACHMENTS_INVENTORY_CSV = DATA_DIR / "attachments_inventory.csv"
MAPPING_EXPORT_CSV = DATA_DIR / "mapping_export.csv"

MAPPING_VERIFICATION_LOG_CSV = LOG_DIR / "mapping_verification_log.csv"
MAPPING_VERIFICATION_SKIPS_CSV = LOG_DIR / "mapping_verification_skips.csv"

QBO_ATTACH_RUNLOG_CSV = LOG_DIR / "qbo_attach_runlog.csv"
QBO_ATTACH_ERRORS_CSV = LOG_DIR / "qbo_attach_errors.csv"
QBO_ATTACH_DUPS_CSV = LOG_DIR / "qbo_attach_dups.csv"


def normalize_legacy_id(raw_id: str) -> str:
    """
    Normalize a legacy transaction identifier into the canonical form
    used in mapping_export and attachments_inventory.

    The real project stripped a fixed prefix and uppercased the rest.
    This demo models the same behavior.

    Example:
        "80ABC123" -> "ABC123"
        "abc123"   -> "ABC123"
    """
    if raw_id is None:
        return ""
    raw = str(raw_id).strip()

    # Strip the "80" prefix if present, because mapping is stored without it
    if raw.startswith("80"):
        raw = raw[2:]

    return raw.upper()
