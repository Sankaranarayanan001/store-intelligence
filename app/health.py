import aiosqlite
import os
from datetime import datetime, timezone, timedelta

DB_PATH = os.getenv("DB_PATH", "./store.db")

async def get_health():
    now = datetime.now(timezone.utc)
    store_status = []

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            # get all stores we have events for
            cursor = await db.execute("""
                SELECT DISTINCT store_id FROM events
            """)
            stores = [r["store_id"] for r in await cursor.fetchall()]

            # if no events yet, return healthy with no stores
            if not stores:
                return {
                    "status": "ok",
                    "checked_at": now.isoformat(),
                    "stores": [],
                    "message": "No events ingested yet"
                }

            for store_id in stores:
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
                    stale = lag_minutes > 10
                else:
                    lag_minutes = None
                    stale = False

                store_status.append({
                    "store_id": store_id,
                    "last_event_timestamp": last_event,
                    "lag_minutes": round(lag_minutes, 1) if lag_minutes else None,
                    "feed_status": "STALE_FEED" if stale else "OK"
                })

        return {
            "status": "ok",
            "checked_at": now.isoformat(),
            "stores": store_status
        }

    except Exception as e:
        # database unavailable — return 503
        return {
            "status": "degraded",
            "checked_at": now.isoformat(),
            "error": "Database unavailable",
            "stores": []
        }