from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List
from app.models.pet import PetStatus, Pet
from app.models.scan import ScanRecord
from app.models.chat import ChatSession

class DashboardStatusUpdate(BaseModel):
    token: str
    status: PetStatus

class DashboardRecoverRequest(BaseModel):
    token: str

class NotificationLog(BaseModel):
    id: str
    strategy: str
    recipient: str
    channel: str
    title: str
    body: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class DashboardDataResponse(BaseModel):
    pet: Pet
    recent_scans: List[ScanRecord]
    active_chat_sessions: List[ChatSession]
    recent_notifications: List[NotificationLog]
