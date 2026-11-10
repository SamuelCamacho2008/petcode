from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class ScanCreate(BaseModel):
    token: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None
    manual_address: Optional[str] = None
    timestamp: Optional[datetime] = None

class ScanRecord(BaseModel):
    id: str
    token: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None
    manual_address: Optional[str] = None
    ip_address: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    exact_coords_purged: bool = False

class ScanResponse(BaseModel):
    status: str
    message: str
    scan_id: str
    pet_name: str
    alert_sent: bool
    mode: str
