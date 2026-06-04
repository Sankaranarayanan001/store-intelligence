# DESIGN.md — Store Intelligence System

## Overview

This system processes raw CCTV footage from physical retail stores and exposes
a real-time analytics API. The pipeline converts video frames into structured
behavioural events, ingests them into a database, and serves live metrics
through a REST API.

The north star metric is offline store conversion rate:
visitors who completed a purchase divided by total unique visitors.

---

## Architecture

---

## Stage 1 — Detection Layer

**Model:** YOLOv8n (nano) via Ultralytics
**Tracker:** ByteTrack (built into Ultralytics as model.track())
**Input:** 1080p MP4 files at 15fps

### Camera roles

| Camera Type                | Purpose                                                               |
| -------------------------- | --------------------------------------------------------------------- |
| Entry/Exit Cameras         | Detect customer entry, exit, and re-entry events                      |
| Zone Monitoring Cameras    | Track customer movement, zone visits, and dwell time                  |
| Billing Area Cameras       | Monitor checkout activity, queue depth, and billing events            |
| Store Surveillance Cameras | Generate behavioral events used for analytics and funnel calculations |

The system supports multiple cameras deployed across multiple retail stores. Each camera contributes events such as ENTRY, EXIT, ZONE_ENTER, ZONE_DWELL, and BILLING_QUEUE_JOIN, which are combined to build customer journeys and retail intelligence metrics.

### Entry/exit detection

The entry/exit camera is positioned near the store entrance. A person's centroid crossing a predefined virtual line determines movement direction. Crossing into the store generates an ENTRY event, while crossing out of the store generates an EXIT event. This approach provides a lightweight and reliable mechanism for estimating store traffic without requiring complex re-identification models.

### Staff detection heuristic

A person detected across 3 or more distinct zones within a session
is classified as staff (is_staff=true). Staff events are stored but
excluded from all customer-facing metrics. This heuristic works
because customers typically visit 1-2 zones while staff move through
all zones regularly.

### Re-entry handling

The exit_registry dictionary maps visitor_id to last exit timestamp.
When a person reappears at CAM3 after a prior EXIT event, the system
emits REENTRY instead of a second ENTRY. This prevents re-entry
inflation which is a known problem in retail analytics vendors.

### Group entry

ByteTrack assigns a separate track_id to each individual even when
multiple people enter simultaneously. Each track_id maps to a unique
visitor_id so a group of 3 people entering together produces 3
separate ENTRY events.

### Edge case handling

| Edge Case         | Handling                                                   |
| ----------------- | ---------------------------------------------------------- |
| Partial occlusion | Confidence score degraded, event still emitted             |
| Empty periods     | Zero events emitted, API handles zeros without crashing    |
| Camera overlap    | Separate visitor_ids per camera, deduplication via session |
| Low confidence    | Events emitted with actual confidence, never suppressed    |

---

## Stage 2 — Event Stream

Events are emitted as newline-delimited JSON (JSONL) to events.jsonl.
Each event follows the required schema with event_id, store_id,
camera_id, visitor_id, event_type, timestamp, zone_id, dwell_ms,
is_staff, confidence, and metadata.

The schema was designed so the full conversion funnel can be
reconstructed from events alone without additional lookups.

---

## Stage 3 — Intelligence API

**Framework:** FastAPI with async request handling
**Database:** SQLite with aiosqlite for async operations
**Validation:** Pydantic v2 models for automatic request validation

### Database schema

Three tables:

**events** — every ingested event, indexed by store_id and timestamp
**sessions** — one row per visitor session with entry/exit times and
purchased flag, indexed by store_id
**pos_transactions** — POS records for purchase correlation

### Idempotency

POST /events/ingest uses INSERT OR IGNORE on event_id as the primary
key. Sending the same batch twice produces the same result. Partial
success is supported — malformed events return errors while valid
events in the same batch are accepted.

### Real-time metrics

All metrics are computed from live database queries with no caching.
The as_of timestamp in every response confirms the data is current.

### Anomaly detection

Four anomaly types are detected:

- BILLING_QUEUE_SPIKE: queue depth >= 5 in last 10 minutes
- DEAD_ZONE: no zone visits in 30 minutes
- CONVERSION_DROP: recent conversion < 50% of overall average
- STALE_FEED: no events received for 10+ minutes

---

## Stage 4 — Production Readiness

- Single command startup: docker compose up
- Structured JSON logging on every request with trace_id
- Graceful degradation: database errors return 503 with structured body
- No raw stack traces exposed in responses
- Test coverage across metrics, anomalies, and pipeline schema

---

## AI-Assisted Decisions

### 1. Staff detection approach

I asked Claude to suggest approaches for detecting staff in retail
CCTV footage without uniform recognition. It suggested three options:
colour histogram matching on bounding box crops, zone frequency
heuristic, and a VLM prompt approach. I chose the zone frequency
heuristic because it requires no additional model and works reliably
given that staff consistently move through all store zones. The VLM
approach would have been more accurate but added API latency and cost
to every frame.

### 2. Re-entry vs new session

Claude suggested using a time window (same person returning within
5 minutes = re-entry) combined with Re-ID features. I implemented
the simpler exit_registry approach which tracks the last exit per
visitor_id and flags any subsequent appearance as REENTRY. This
is sufficient for the footage duration and avoids the complexity
of feature similarity thresholds.

### 3. SQLite vs PostgreSQL

Claude initially suggested PostgreSQL for production readiness. I
overrode this because the problem is single-host, the dataset fits
comfortably in SQLite, and SQLite in WAL mode handles concurrent
reads from multiple API endpoints without issues. PostgreSQL would
have added a second Docker service and more configuration with no
meaningful benefit at this scale.
