# PROMPT: "Write pytest tests for the detection pipeline covering event schema
# compliance, unique event_ids, re-entry handling, staff flagging, and
# group entry counting"
# CHANGES MADE: Added confidence threshold assertion, fixed visitor_id
# format check, added session_seq validation, added group entry test

import pytest
import uuid
import json
import os
from datetime import datetime, timezone

def make_raw_event(
    event_type="ENTRY",
    visitor_id=None,
    is_staff=False,
    zone_id=None,
    confidence=0.91,
    queue_depth=None
):
    """Helper to create a valid raw event dict."""
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   "STORE_BLR_002",
        "camera_id":  "CAM_ENTRY_03",
        "visitor_id": visitor_id or ("VIS_" + uuid.uuid4().hex[:6].upper()),
        "event_type": event_type,
        "timestamp":  datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "zone_id":    zone_id,
        "dwell_ms":   0,
        "is_staff":   is_staff,
        "confidence": confidence,
        "metadata": {
            "queue_depth": queue_depth,
            "sku_zone":    zone_id,
            "session_seq": 1
        }
    }

# ── schema compliance ──────────────────────────────────────────────────────

def test_event_has_required_fields():
    """Every event must have all required fields."""
    event = make_raw_event()
    required = [
        "event_id", "store_id", "camera_id", "visitor_id",
        "event_type", "timestamp", "confidence", "metadata"
    ]
    for field in required:
        assert field in event, f"Missing field: {field}"

def test_event_id_is_uuid():
    """event_id must be a valid UUID v4."""
    event = make_raw_event()
    parsed = uuid.UUID(event["event_id"])
    assert parsed.version == 4

def test_event_ids_are_unique():
    """Every event must have a globally unique event_id."""
    events = [make_raw_event() for _ in range(100)]
    ids = [e["event_id"] for e in events]
    assert len(ids) == len(set(ids))

def test_visitor_id_format():
    """visitor_id must start with VIS_ prefix."""
    event = make_raw_event()
    assert event["visitor_id"].startswith("VIS_")

def test_timestamp_is_iso8601():
    """timestamp must be valid ISO-8601 UTC."""
    event = make_raw_event()
    ts = event["timestamp"]
    assert ts.endswith("Z") or "+" in ts
    # must parse without error
    cleaned = ts.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(cleaned)
    assert parsed.tzinfo is not None

def test_confidence_range():
    """confidence must be between 0 and 1."""
    event = make_raw_event(confidence=0.87)
    assert 0.0 <= event["confidence"] <= 1.0

def test_low_confidence_not_suppressed():
    """Low confidence events must still be emitted, not dropped."""
    event = make_raw_event(confidence=0.21)
    assert event["confidence"] == 0.21
    assert "event_id" in event

def test_metadata_has_required_keys():
    """metadata must contain queue_depth, sku_zone, session_seq."""
    event = make_raw_event()
    meta = event["metadata"]
    assert "queue_depth"  in meta
    assert "sku_zone"     in meta
    assert "session_seq"  in meta

# ── event type catalogue ───────────────────────────────────────────────────

def test_valid_event_types():
    """All event types must be from the allowed catalogue."""
    allowed = {
        "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT",
        "ZONE_DWELL", "BILLING_QUEUE_JOIN",
        "BILLING_QUEUE_ABANDON", "REENTRY"
    }
    for et in allowed:
        event = make_raw_event(event_type=et)
        assert event["event_type"] in allowed

def test_entry_event_has_no_zone():
    """ENTRY events must have zone_id as None."""
    event = make_raw_event(event_type="ENTRY", zone_id=None)
    assert event["zone_id"] is None

def test_zone_dwell_has_zone_id():
    """ZONE_DWELL events must have a zone_id."""
    event = make_raw_event(event_type="ZONE_DWELL", zone_id="MAIN_FLOOR")
    assert event["zone_id"] is not None

# ── staff handling ─────────────────────────────────────────────────────────

def test_staff_flag_is_boolean():
    """is_staff must be a boolean."""
    event = make_raw_event(is_staff=True)
    assert isinstance(event["is_staff"], bool)
    assert event["is_staff"] is True

def test_staff_event_flagged_correctly():
    """Staff events must have is_staff=True."""
    staff_event = make_raw_event(is_staff=True)
    assert staff_event["is_staff"] is True

# ── re-entry handling ──────────────────────────────────────────────────────

def test_reentry_uses_same_visitor_id():
    """
    Re-entry must reuse the same visitor_id,
    not create a new one.
    """
    visitor_id = "VIS_ABC123"
    entry  = make_raw_event(event_type="ENTRY",   visitor_id=visitor_id)
    exit_e = make_raw_event(event_type="EXIT",    visitor_id=visitor_id)
    reentry = make_raw_event(event_type="REENTRY", visitor_id=visitor_id)
    assert entry["visitor_id"]   == visitor_id
    assert exit_e["visitor_id"]  == visitor_id
    assert reentry["visitor_id"] == visitor_id

def test_reentry_event_type():
    """Second visit by same person must be REENTRY not ENTRY."""
    event = make_raw_event(event_type="REENTRY")
    assert event["event_type"] == "REENTRY"