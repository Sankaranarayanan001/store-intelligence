import aiosqlite
import os
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", "./store.db")

async def get_metrics(store_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # unique visitors today (exclude staff)
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as count
            FROM sessions
            WHERE store_id = ? AND is_staff = 0
        """, (store_id,))
        row = await cursor.fetchone()
        unique_visitors = row["count"] if row else 0

        # correlate billing zone visitors with POS transactions
        # visitor in billing zone within 5 minutes before transaction = purchased
        await db.execute("""
            UPDATE sessions SET purchased = 1
            WHERE store_id = ? AND is_staff = 0
            AND visitor_id IN (
                SELECT DISTINCT e.visitor_id
                FROM events e
                JOIN pos_transactions p
                  ON p.store_id = e.store_id
                 AND e.timestamp <= p.timestamp
                 AND e.timestamp >= datetime(p.timestamp, '-5 minutes')
                WHERE e.store_id = ?
                  AND e.zone_id = 'BILLING_AREA'
                  AND e.is_staff = 0
            )
        """, (store_id, store_id))
        await db.commit()

        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as count
            FROM sessions
            WHERE store_id = ? AND purchased = 1 AND is_staff = 0
        """, (store_id,))
        row = await cursor.fetchone()
        purchased = row["count"] if row else 0

        # conversion rate
        conversion_rate = round(
            purchased / unique_visitors, 3
        ) if unique_visitors > 0 else 0.0

        # avg dwell per zone
        cursor = await db.execute("""
            SELECT zone_id,
                   ROUND(AVG(dwell_ms) / 1000.0, 1) as avg_dwell_sec,
                   COUNT(*) as visits
            FROM events
            WHERE store_id = ?
              AND is_staff = 0
              AND zone_id IS NOT NULL
              AND event_type = 'ZONE_DWELL'
            GROUP BY zone_id
        """, (store_id,))
        rows = await cursor.fetchall()
        zone_dwell = [
            {
                "zone_id": r["zone_id"],
                "avg_dwell_sec": r["avg_dwell_sec"],
                "visits": r["visits"]
            }
            for r in rows
        ]

        # current queue depth
        cursor = await db.execute("""
            SELECT MAX(queue_depth) as depth
            FROM events
            WHERE store_id = ?
              AND event_type = 'BILLING_QUEUE_JOIN'
              AND queue_depth IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1
        """, (store_id,))
        row = await cursor.fetchone()
        queue_depth = row["depth"] if row and row["depth"] else 0

        # abandonment rate
        cursor = await db.execute("""
            SELECT COUNT(*) as count FROM events
            WHERE store_id = ?
              AND event_type = 'BILLING_QUEUE_ABANDON'
              AND is_staff = 0
        """, (store_id,))
        row = await cursor.fetchone()
        abandonments = row["count"] if row else 0

        abandonment_rate = round(
            abandonments / unique_visitors, 3
        ) if unique_visitors > 0 else 0.0

        return {
            "store_id": store_id,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "unique_visitors": unique_visitors,
            "purchased": purchased,
            "conversion_rate": conversion_rate,
            "abandonment_rate": abandonment_rate,
            "queue_depth": queue_depth,
            "zone_dwell": zone_dwell,
            "data_note": "live — not cached"
        }