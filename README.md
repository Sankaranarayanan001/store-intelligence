# Store Intelligence System

AI-powered retail analytics from raw CCTV footage.
Converts video into live store metrics via a production-ready API.

---

## Setup in 5 commands

```bash
git clone <your-repo-url>
cd store-intelligence
pip install -r requirements.txt
docker compose up --build
curl http://localhost:8000/health
```

---

## Run the detection pipeline

Place your video files in the `data/` folder:

Run detection against all clips:

```bash
python pipeline/detect.py \
  --data-dir ./data \
  --output ./events.jsonl
```

This processes all cameras and writes structured events to
events.jsonl. Processing time is approximately 20-30 minutes
for 5 cameras on CPU.

---

## Feed events into the API

Start the API:

```bash
docker compose up
```

Ingest events (Linux/Mac):

```bash
curl -X POST http://localhost:8000/events/ingest \
  -H "Content-Type: application/json" \
  -d "{\"events\": $(cat events.jsonl | jq -s '.')}"
```

Ingest events (Windows PowerShell):

```powershell
$lines = Get-Content .\events.jsonl
$events = $lines | ForEach-Object { $_ | ConvertFrom-Json }
$payload = @{ events = $events } | ConvertTo-Json -Depth 10
Invoke-WebRequest -Uri http://localhost:8000/events/ingest `
  -Method POST -Body $payload `
  -ContentType "application/json" -UseBasicParsing
```

---

## API Endpoints

| Endpoint                   | Description                           |
| -------------------------- | ------------------------------------- |
| GET /health                | Service status + stale feed detection |
| POST /events/ingest        | Ingest up to 500 events (idempotent)  |
| GET /stores/{id}/metrics   | Live visitor counts, conversion rate  |
| GET /stores/{id}/funnel    | Entry → Zone → Billing → Purchase     |
| GET /stores/{id}/anomalies | Queue spikes, dead zones, stale feed  |

Example store ID: `STORE_BLR_002`

---

## Run tests

```bash
pytest tests/ -v
```

Expected: 28 tests passing.

---

## Live dashboard

```bash
python pipeline/dashboard.py
```

Opens at http://localhost:8501

---

## Architecture

## Camera layout

| Camera | Role                           |
| ------ | ------------------------------ |
| CAM 1  | Main floor zone tracking       |
| CAM 2  | Main floor zone tracking       |
| CAM 3  | Entry/exit detection (outside) |
| CAM 4  | Main floor zone tracking       |
| CAM 5  | Billing area + queue tracking  |

---

## Tech stack

| Component | Technology         | Reason                                 |
| --------- | ------------------ | -------------------------------------- |
| Detection | YOLOv8n            | Fast CPU inference, built-in ByteTrack |
| Tracking  | ByteTrack          | Stable track_id across frames          |
| API       | FastAPI            | Async, auto-validation via Pydantic    |
| Database  | SQLite + aiosqlite | Single host, zero config               |
| Container | Docker             | One command startup                    |
| Tests     | pytest + httpx     | Async test client for FastAPI          |

---

## AI tools used

Claude and GitHub Copilot were used throughout. See
docs/DESIGN.md (AI-Assisted Decisions) and docs/CHOICES.md
for specific decisions where AI input shaped the architecture.
