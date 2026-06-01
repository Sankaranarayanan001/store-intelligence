import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "./store.db")

async def get_funnel(store_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Step 1 — total unique customer visitors (exclude staff)
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as count
            FROM sessions
            WHERE store_id = ? AND is_staff = 0
        """, (store_id,))
        row = await cursor.fetchone()
        total_entries = row["count"] if row else 0

        # Step 2 — visitors who entered at least one zone
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as count
            FROM events
            WHERE store_id = ?
              AND is_staff = 0
              AND event_type IN ('ZONE_ENTER', 'ZONE_DWELL')
              AND zone_id IS NOT NULL
        """, (store_id,))
        row = await cursor.fetchone()
        zone_visitors = row["count"] if row else 0

        # Step 3 — visitors who reached billing area
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as count
            FROM events
            WHERE store_id = ?
              AND is_staff = 0
              AND (
                event_type = 'BILLING_QUEUE_JOIN'
                OR zone_id IN ('BILLING_AREA', 'BILLING', 'CHECKOUT')
              )
        """, (store_id,))
        row = await cursor.fetchone()
        billing_visitors = row["count"] if row else 0

        # Step 4 — visitors who purchased
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT visitor_id) as count
            FROM sessions
            WHERE store_id = ?
              AND purchased = 1
              AND is_staff = 0
        """, (store_id,))
        row = await cursor.fetchone()
        purchased_visitors = row["count"] if row else 0

        # calculate drop-off percentages safely
        def dropoff(current, previous):
            if previous == 0:
                return 0.0
            lost = previous - current
            return round((lost / previous) * 100, 1)

        def pct(current, total):
            if total == 0:
                return 0.0
            return round((current / total) * 100, 1)

        return {
            "store_id": store_id,
            "session_unit": "unique visitor — re-entries counted once",
            "stages": [
                {
                    "stage": "entry",
                    "label": "Entered store",
                    "count": total_entries,
                    "pct_of_total": 100.0,
                    "dropoff_pct": 0.0
                },
                {
                    "stage": "zone_visit",
                    "label": "Visited a zone",
                    "count": zone_visitors,
                    "pct_of_total": pct(zone_visitors, total_entries),
                    "dropoff_pct": dropoff(zone_visitors, total_entries)
                },
                {
                    "stage": "billing",
                    "label": "Reached billing",
                    "count": billing_visitors,
                    "pct_of_total": pct(billing_visitors, total_entries),
                    "dropoff_pct": dropoff(billing_visitors, zone_visitors)
                },
                {
                    "stage": "purchase",
                    "label": "Completed purchase",
                    "count": purchased_visitors,
                    "pct_of_total": pct(purchased_visitors, total_entries),
                    "dropoff_pct": dropoff(purchased_visitors, billing_visitors)
                }
            ]
        }