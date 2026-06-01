from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: int = 1

class StoreEvent(BaseModel):
    event_id: str
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: str
    timestamp: datetime
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float
    metadata: EventMetadata