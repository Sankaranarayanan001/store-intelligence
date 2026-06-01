import aiosqlite
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "./store.db")

async def ingest_events(raw_events: list):
    accepted = 0
    rejected = 0
    errors = []

    async with aiosqlite.connect(DB_PATH) as db:
        for raw in raw_events:
            try:
                # --- validate required fields ---
                required = ["event_id", "store_id", "visitor_id",
                            "event_type", "timestamp", "confidence"]
                missing = [f for f in required if f not in raw]
                if missing:
                    rejected += 1
                    errors.append({
                        "event_id": raw.get("event_id", "unknown"),
                        "error": f"missing fields: {missing}"
                    })
                    continue

                # skip staff events from customer metrics
                is_staff = int(raw.get("is_staff", False))

                meta = raw.get("metadata", {}) or {}
                queue_depth = meta.get("queue_depth")
                sku_zone    = meta.get("sku_zone")
                session_seq = meta.get("session_seq", 1)

                # --- idempotent insert (skip duplicates) ---
                await db.execute("""
                    INSERT OR IGNORE INTO events (
                        event_id, store_id, camera_id, visitor_id,
                        event_type, timestamp, zone_id, dwell_ms,
                        is_staff, confidence, queue_depth,
                        sku_zone, session_seq
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    raw["event_id"],
                    raw["store_id"],
                    raw.get("camera_id", ""),
                    raw["visitor_id"],
                    raw["event_type"],
                    raw["timestamp"],
                    raw.get("zone_id"),
                    raw.get("dwell_ms", 0),
                    is_staff,
                    raw["confidence"],
                    queue_depth,
                    sku_zone,
                    session_seq
                ))

                # --- update sessions table ---
                event_type = raw["event_type"]
                visitor_id = raw["visitor_id"]
                store_id   = raw["store_id"]
                timestamp  = raw["timestamp"]

                if event_type == "ENTRY":
                    await db.execute("""
                        INSERT OR IGNORE INTO sessions
                        (visitor_id, store_id, entry_time, is_staff)
                        VALUES (?,?,?,?)
                    """, (visitor_id, store_id, timestamp, is_staff))

                elif event_type == "EXIT":
                    await db.execute("""
                        UPDATE sessions SET exit_time = ?
                        WHERE visitor_id = ? AND store_id = ?
                    """, (timestamp, visitor_id, store_id))

                accepted += 1

            except Exception as e:
                rejected += 1
                errors.append({
                    "event_id": raw.get("event_id", "unknown"),
                    "error": str(e)
                })

        await db.commit()

    return {
        "accepted": accepted,
        "rejected": rejected,
        "errors": errors if errors else None
    }