# PROMPT: "Write pytest tests for the /anomalies endpoint covering queue spike,
# dead zone detection, conversion drop, and stale feed using FastAPI AsyncClient"
# CHANGES MADE: Added severity assertions, fixed timestamp for stale feed test,
# corrected queue spike threshold to match implementation (>=5)

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import init_db, DB_PATH
import os
import uuid
from datetime import datetime, timezone, timedelta

def make_event(
    visitor_id=None,
    event_type="ENTRY",
    zone_id=None,
    queue_depth=None,
    is_staff=False,
    timestamp=None,
    confidence=0.91
):
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   "STORE_BLR_002",
        "camera_id":  "CAM_ENTRY_03",
        "visitor_id": visitor_id or ("VIS_" + uuid.uuid4().hex[:6].upper()),
        "event_type": event_type,
        "timestamp":  timestamp,
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

async def post_events(client, events):
    return await client.post("/events/ingest", json={"events": events})

@pytest_asyncio.fixture(autouse=True)
async def clean_db():
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

@pytest.mark.asyncio
async def test_no_anomalies_when_normal(client):
    """Normal store with recent events returns NONE anomaly."""
    events = [make_event() for _ in range(3)]
    await post_events(client, events)
    resp = await client.get("/stores/STORE_BLR_002/anomalies")
    assert resp.status_code == 200
    types = [a["type"] for a in resp.json()["anomalies"]]
    assert "NONE" in types

@pytest.mark.asyncio
async def test_billing_queue_spike(client):
    """Queue depth >= 5 triggers BILLING_QUEUE_SPIKE."""
    events = [
        make_event(
            event_type="BILLING_QUEUE_JOIN",
            zone_id="BILLING_AREA",
            queue_depth=6
        )
        for _ in range(3)
    ]
    await post_events(client, events)
    resp = await client.get("/stores/STORE_BLR_002/anomalies")
    types = [a["type"] for a in resp.json()["anomalies"]]
    assert "BILLING_QUEUE_SPIKE" in types

@pytest.mark.asyncio
async def test_billing_queue_spike_severity(client):
    """Queue depth >= 8 triggers CRITICAL severity."""
    events = [
        make_event(
            event_type="BILLING_QUEUE_JOIN",
            zone_id="BILLING_AREA",
            queue_depth=9
        )
    ]
    await post_events(client, events)
    resp = await client.get("/stores/STORE_BLR_002/anomalies")
    anomalies = resp.json()["anomalies"]
    spike = next((a for a in anomalies if a["type"] == "BILLING_QUEUE_SPIKE"), None)
    assert spike is not None
    assert spike["severity"] == "CRITICAL"

@pytest.mark.asyncio
async def test_dead_zone_detection(client):
    """Zone with no visits in 30 min triggers DEAD_ZONE."""
    old_time = (
        datetime.now(timezone.utc) - timedelta(minutes=45)
    ).isoformat().replace("+00:00", "Z")
    events = [
        make_event(
            event_type="ZONE_ENTER",
            zone_id="MAIN_FLOOR",
            timestamp=old_time
        )
    ]
    await post_events(client, events)
    resp = await client.get("/stores/STORE_BLR_002/anomalies")
    types = [a["type"] for a in resp.json()["anomalies"]]
    assert "DEAD_ZONE" in types

@pytest.mark.asyncio
async def test_stale_feed_detection(client):
    """No events for 10+ min triggers STALE_FEED."""
    old_time = (
        datetime.now(timezone.utc) - timedelta(minutes=20)
    ).isoformat().replace("+00:00", "Z")
    events = [make_event(timestamp=old_time)]
    await post_events(client, events)
    resp = await client.get("/stores/STORE_BLR_002/anomalies")
    types = [a["type"] for a in resp.json()["anomalies"]]
    assert "STALE_FEED" in types

@pytest.mark.asyncio
async def test_anomaly_has_suggested_action(client):
    """Every anomaly must have a suggested_action string."""
    resp = await client.get("/stores/STORE_BLR_002/anomalies")
    for anomaly in resp.json()["anomalies"]:
        assert "suggested_action" in anomaly
        assert len(anomaly["suggested_action"]) > 0