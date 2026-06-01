# PROMPT: "Write pytest tests for the /metrics endpoint covering unique visitors,
# conversion rate, zero purchase stores, and staff exclusion using FastAPI AsyncClient"
# CHANGES MADE: Added staff exclusion assertion, fixed async client setup,
# added zero visitor edge case, corrected expected conversion rate calculation

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import init_db, DB_PATH
import aiosqlite
import os
import uuid

# ── helpers ────────────────────────────────────────────────────────────────

def make_event(
    visitor_id=None,
    event_type="ENTRY",
    store_id="STORE_BLR_002",
    is_staff=False,
    zone_id=None,
    dwell_ms=0,
    queue_depth=None,
    confidence=0.91
):
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   store_id,
        "camera_id":  "CAM_ENTRY_03",
        "visitor_id": visitor_id or ("VIS_" + uuid.uuid4().hex[:6].upper()),
        "event_type": event_type,
        "timestamp":  "2026-06-01T14:00:00Z",
        "zone_id":    zone_id,
        "dwell_ms":   dwell_ms,
        "is_staff":   is_staff,
        "confidence": confidence,
        "metadata": {
            "queue_depth": queue_depth,
            "sku_zone":    zone_id,
            "session_seq": 1
        }
    }

async def post_events(client, events):
    resp = await client.post(
        "/events/ingest",
        json={"events": events}
    )
    return resp

# ── fixtures ───────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Fresh database for every test."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    await init_db()
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c

# ── tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_empty_store(client):
    """Empty store returns zeros — must not crash or return null."""
    resp = await client.get("/stores/STORE_BLR_002/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unique_visitors"]  == 0
    assert data["conversion_rate"]  == 0.0
    assert data["abandonment_rate"] == 0.0
    assert data["queue_depth"]      == 0
    assert data["zone_dwell"]       == []

@pytest.mark.asyncio
async def test_metrics_counts_unique_visitors(client):
    """Three different visitors = unique_visitors of 3."""
    events = [make_event() for _ in range(3)]
    await post_events(client, events)
    resp = await client.get("/stores/STORE_BLR_002/metrics")
    assert resp.status_code == 200
    assert resp.json()["unique_visitors"] == 3

@pytest.mark.asyncio
async def test_metrics_excludes_staff(client):
    """Staff events must not count toward unique_visitors."""
    customer = make_event(is_staff=False)
    staff1   = make_event(is_staff=True)
    staff2   = make_event(is_staff=True)
    await post_events(client, [customer, staff1, staff2])
    resp = await client.get("/stores/STORE_BLR_002/metrics")
    assert resp.json()["unique_visitors"] == 1

@pytest.mark.asyncio
async def test_metrics_zero_purchases(client):
    """Store with visitors but no purchases = conversion_rate 0."""
    events = [make_event() for _ in range(5)]
    await post_events(client, events)
    resp = await client.get("/stores/STORE_BLR_002/metrics")
    data = resp.json()
    assert data["unique_visitors"]  == 5
    assert data["conversion_rate"]  == 0.0

@pytest.mark.asyncio
async def test_metrics_zone_dwell(client):
    """Zone dwell events appear in zone_dwell list."""
    events = [
        make_event(
            event_type="ZONE_DWELL",
            zone_id="MAIN_FLOOR",
            dwell_ms=35000
        )
    ]
    await post_events(client, events)
    resp = await client.get("/stores/STORE_BLR_002/metrics")
    data = resp.json()
    assert len(data["zone_dwell"]) > 0
    assert data["zone_dwell"][0]["zone_id"] == "MAIN_FLOOR"

@pytest.mark.asyncio
async def test_metrics_queue_depth(client):
    """Queue depth reflects billing queue join events."""
    events = [
        make_event(
            event_type="BILLING_QUEUE_JOIN",
            zone_id="BILLING_AREA",
            queue_depth=3
        )
    ]
    await post_events(client, events)
    resp = await client.get("/stores/STORE_BLR_002/metrics")
    assert resp.json()["queue_depth"] == 3

@pytest.mark.asyncio
async def test_ingest_idempotent(client):
    """Posting same events twice must not double count."""
    events = [make_event() for _ in range(5)]
    await post_events(client, events)
    await post_events(client, events)  # second time — same events
    resp = await client.get("/stores/STORE_BLR_002/metrics")
    assert resp.json()["unique_visitors"] == 5  # not 10