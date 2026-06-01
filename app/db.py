import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "./store.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id    TEXT PRIMARY KEY,
                store_id    TEXT NOT NULL,
                camera_id   TEXT,
                visitor_id  TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                zone_id     TEXT,
                dwell_ms    INTEGER DEFAULT 0,
                is_staff    INTEGER DEFAULT 0,
                confidence  REAL,
                queue_depth INTEGER,
                sku_zone    TEXT,
                session_seq INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                visitor_id   TEXT NOT NULL,
                store_id     TEXT NOT NULL,
                entry_time   TEXT,
                exit_time    TEXT,
                purchased    INTEGER DEFAULT 0,
                is_staff     INTEGER DEFAULT 0,
                PRIMARY KEY (visitor_id, store_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS pos_transactions (
                transaction_id  TEXT PRIMARY KEY,
                store_id        TEXT NOT NULL,
                timestamp       TEXT NOT NULL,
                basket_value    REAL
            )
        """)

        # indexes for fast queries
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_store
            ON events(store_id, timestamp)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_visitor
            ON events(visitor_id, store_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_store
            ON sessions(store_id)
        """)

        await db.commit()
        print("Database initialised")

async def get_db():
    return aiosqlite.connect(DB_PATH)