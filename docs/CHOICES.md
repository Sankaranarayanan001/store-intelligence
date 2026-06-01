# CHOICES.md — Key Engineering Decisions

## Decision 1 — Detection Model: YOLOv8n

### Options considered

| Model     | Speed       | Accuracy | Setup                   |
| --------- | ----------- | -------- | ----------------------- |
| YOLOv8n   | ~100fps CPU | Good     | pip install ultralytics |
| YOLOv8m   | ~40fps CPU  | Better   | same                    |
| RT-DETR   | ~20fps CPU  | Best     | complex                 |
| MediaPipe | ~120fps CPU | Moderate | separate SDK            |

### What AI suggested

Claude suggested RT-DETR for highest accuracy on partially occluded
persons in retail environments, noting it handles crowded scenes
better than YOLO variants.

### What I chose and why

YOLOv8n. The footage is 15fps and the pipeline processes it offline
so real-time speed is not the primary concern. However YOLOv8n is
fast enough to process all 5 cameras in under 30 minutes on CPU,
ByteTrack is built directly into Ultralytics with zero extra setup,
and the nano model is accurate enough for person detection in retail
CCTV where people occupy a significant portion of the frame.

RT-DETR would require a separate tracking integration and adds
complexity without a meaningful accuracy gain for this specific use
case. If I were deploying this to 40 live stores I would evaluate
RT-DETR with GPU inference.

---

## Decision 2 — Event Schema Design

### Options considered

**Option A:** Flat schema — all fields at top level including metadata
**Option B:** Nested schema — core fields + metadata object
**Option C:** Separate tables per event type — ENTRY events in one
table, ZONE_DWELL in another

### What AI suggested

Claude suggested Option C (separate tables) for query performance,
arguing that zone dwell queries would be faster with a dedicated
table. It also suggested adding a sessions table as a materialised
view updated on every ingest.

### What I chose and why

Option B (nested schema with metadata object) matching the required
output schema exactly. I agreed with the suggestion to maintain a
separate sessions table updated on ingest — this makes funnel queries
O(1) lookups rather than full event table scans.

I rejected Option C because it would have made the ingest endpoint
significantly more complex (routing each event to a different table)
and would have broken schema compliance with the sample_events.jsonl
format provided in the challenge.

The session_seq field in metadata allows the full visitor journey to
be reconstructed in order without a timestamp sort, which is useful
for funnel analysis at scale.

---

## Decision 3 — API Architecture: Sync vs Async

### Options considered

**Option A:** Synchronous FastAPI with standard SQLite via sqlite3
**Option B:** Async FastAPI with aiosqlite
**Option C:** Async FastAPI with SQLAlchemy async + aiosqlite

### What AI suggested

Claude suggested Option C with SQLAlchemy for the ORM layer,
arguing it would make database migrations easier and provide better
query composition for complex analytics queries.

### What I chose and why

Option B (async FastAPI + aiosqlite directly). SQLAlchemy adds a
significant abstraction layer that is unnecessary when all queries
are known upfront and relatively simple. The analytics queries in
this system are fixed — unique visitor counts, funnel aggregations,
zone dwell averages — none of which benefit from ORM query
composition.

Direct aiosqlite queries are more readable, easier to debug, and
have less overhead. Every query in this system is a single SQL
statement that can be read and understood immediately without
tracing through ORM layers.

If the schema needed frequent changes or the query complexity grew
significantly I would reconsider SQLAlchemy. For this scope, raw
async SQL is the right choice.
