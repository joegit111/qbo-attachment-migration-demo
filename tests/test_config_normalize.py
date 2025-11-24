from src.config import normalize_legacy_id


def test_normalize_strips_80_prefix_and_uppercases():
    assert normalize_legacy_id("80abc123") == "ABC123"
    assert normalize_legacy_id("80ABC123") == "ABC123"


def test_normalize_handles_non_prefixed_ids():
    assert normalize_legacy_id("abc123") == "ABC123"
    assert normalize_legacy_id("ABC123") == "ABC123"


def test_normalize_handles_none_and_whitespace():
    assert normalize_legacy_id(None) == ""
    assert normalize_legacy_id("   80xyz789  ") == "XYZ789"
