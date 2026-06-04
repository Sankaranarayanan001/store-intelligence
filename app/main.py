from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.ingestion import ingest_events
from app.metrics import get_metrics, get_heatmap
from app.funnel import get_funnel
from app.health import get_health
from app.anomalies import get_anomalies
import logging, uuid, time
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import init_db
    from app.pos_loader import load_pos_transactions
    from app.ingestion import ingest_events
    import json
    import os
    await init_db()
    await load_pos_transactions("./data/pos_transactions.csv")
    # auto ingest events on startup if database is empty
    events_file = "./events.jsonl"
    if os.path.exists(events_file):
        async with __import__('aiosqlite').connect(
            __import__('os').getenv("DB_PATH", "./store.db")
        ) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM events")
            row = await cursor.fetchone()
            count = row[0] if row else 0
        if count == 0:
            with open(events_file, encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
            if events:
                await ingest_events(events)
                print(f"Auto-ingested {len(events)} events on startup")
    yield

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="pipeline"), name="static")

@app.get("/dashboard")
async def dashboard():
    return FileResponse("pipeline/dashboard.html")

@app.middleware("http")
async def log_requests(request, call_next):
    trace_id = str(uuid.uuid4())[:8]
    start = time.time()
    response = await call_next(request)
    latency = int((time.time() - start) * 1000)
    logger.info(
        f"trace={trace_id} path={request.url.path} "
        f"status={response.status_code} latency={latency}ms"
    )
    return response

class IngestPayload(BaseModel):
    events: list[Any]

@app.post("/events/ingest")
async def ingest(payload: IngestPayload):
    return await ingest_events(payload.events)

@app.get("/stores/{store_id}/metrics")
async def metrics(store_id: str):
    return await get_metrics(store_id)

@app.get("/stores/{store_id}/funnel")
async def funnel(store_id: str):
    return await get_funnel(store_id)

@app.get("/stores/{store_id}/heatmap")
async def heatmap(store_id: str):
    return await get_heatmap(store_id)

@app.get("/stores/{store_id}/anomalies")
async def anomalies(store_id: str):
    return await get_anomalies(store_id)

@app.get("/health")
async def health():
    return await get_health()