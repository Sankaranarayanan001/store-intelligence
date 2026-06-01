import aiosqlite
import os
from datetime import datetime, timezone, timedelta

DB_PATH = os.getenv("DB_PATH", "./store.db")

async def get_anomalies(store_id: str):
    anomalies = []
    now = datetime.now(timezone.utc)
    thirty_min_ago = (now - timedelta(minutes=30)).isoformat()
    ten_min_ago    = (now - timedelta(minutes=10)).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # --- 1. BILLING QUEUE SPIKE ---
        cursor = await db.execute("""
            SELECT MAX(queue_depth) as max_q
            FROM events
            WHERE store_id = ?
              AND event_type = 'BILLING_QUEUE_JOIN'
              AND queue_depth IS NOT NULL
              AND timestamp >= ?
        """, (store_id, ten_min_ago))
        row = await cursor.fetchone()
        max_q = row["max_q"] if row and row["max_q"] else 0

        if max_q >= 5:
            anomalies.append({
                "type": "BILLING_QUEUE_SPIKE",
                "severity": "CRITICAL" if max_q >= 8 else "WARN",
                "detail": f"Queue depth reached {max_q} in last 10 minutes",
                "suggested_action": "Open additional billing counter immediately"
            })

        # --- 2. DEAD ZONE — no visits in 30 minutes ---
        cursor = await db.execute("""
            SELECT DISTINCT zone_id FROM events
            WHERE store_id = ? AND zone_id IS NOT NULL
        """, (store_id,))
        all_zones = [r["zone_id"] for r in await cursor.fetchall()]

        for zone in all_zones:
            cursor = await db.execute("""
                SELECT COUNT(*) as count FROM events
                WHERE store_id = ?
                  AND zone_id = ?
                  AND event_type IN ('ZONE_ENTER', 'ZONE_DWELL')
                  AND timestamp >= ?
            """, (store_id, zone, thirty_min_ago))
            row = await cursor.fetchone()
            if row and row["count"] == 0:
                anomalies.append({
                    "type": "DEAD_ZONE",
                    "severity": "INFO",
                    "detail": f"Zone {zone} has had no visits in 30+ minutes",
                    "suggested_action": f"Check display or signage in {zone} zone"
                })

        # --- 3. CONVERSION DROP ---
        # current hour conversion
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as total
            FROM sessions
            WHERE store_id = ? AND is_staff = 0
              AND entry_time >= ?
        """, (store_id, one_hour_ago))
        row = await cursor.fetchone()
        recent_visitors = row["total"] if row else 0

        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as total
            FROM sessions
            WHERE store_id = ? AND is_staff = 0
              AND purchased = 1
              AND entry_time >= ?
        """, (store_id, one_hour_ago))
        row = await cursor.fetchone()
        recent_purchased = row["total"] if row else 0

        recent_conv = (
            recent_purchased / recent_visitors
        ) if recent_visitors > 0 else None

        # overall conversion
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as total
            FROM sessions WHERE store_id = ? AND is_staff = 0
        """, (store_id,))
        row = await cursor.fetchone()
        total_visitors = row["total"] if row else 0

        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as total
            FROM sessions
            WHERE store_id = ? AND is_staff = 0 AND purchased = 1
        """, (store_id,))
        row = await cursor.fetchone()
        total_purchased = row["total"] if row else 0

        overall_conv = (
            total_purchased / total_visitors
        ) if total_visitors > 0 else None

        if recent_conv is not None and overall_conv is not None:
            if recent_conv < overall_conv * 0.5:
                anomalies.append({
                    "type": "CONVERSION_DROP",
                    "severity": "WARN",
                    "detail": (
                        f"Recent conversion {round(recent_conv*100,1)}% "
                        f"vs average {round(overall_conv*100,1)}%"
                    ),
                    "suggested_action": "Check staff availability and billing queue"
                })

        # --- 4. STALE FEED warning ---
        cursor = await db.execute("""
            SELECT MAX(timestamp) as last_event
            FROM events WHERE store_id = ?
        """, (store_id,))
        row = await cursor.fetchone()
        last_event = row["last_event"] if row else None

        if last_event:
            last_dt = datetime.fromisoformat(
                last_event.replace("Z", "+00:00")
            )
            lag_minutes = (now - last_dt).total_seconds() / 60
            if lag_minutes > 10:
                anomalies.append({
                    "type": "STALE_FEED",
                    "severity": "CRITICAL",
                    "detail": f"No events received for {round(lag_minutes,1)} minutes",
                    "suggested_action": "Check camera feed and detection pipeline"
                })

    if not anomalies:
        anomalies.append({
            "type": "NONE",
            "severity": "INFO",
            "detail": "All systems normal",
            "suggested_action": "No action needed"
        })

    return {
        "store_id": store_id,
        "checked_at": now.isoformat(),
        "anomalies": anomalies
    }