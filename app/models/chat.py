from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class ChatSenderRole(str, Enum):
    RESCUER = "rescuer"
    OWNER = "owner"

class ChatSessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"

class ChatCoordinates(BaseModel):
    lat: float
    lon: float
    accuracy: Optional[float] = None

class ChatMessageCreate(BaseModel):
    session_token: str
    sender: ChatSenderRole
    text: str = ""
    photo_base64: Optional[str] = None
    coords: Optional[ChatCoordinates] = None

class ChatMessage(BaseModel):
    id: str
    session_token: str
    sender: ChatSenderRole
    sender_display_name: str
    text: str
    photo_base64: Optional[str] = None
    coords: Optional[ChatCoordinates] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatSessionCreate(BaseModel):
    pet_token: str

class ChatSession(BaseModel):
    id: str
    session_token: str
    pet_token: str
    pet_name: str
    status: ChatSessionStatus = ChatSessionStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    rescuer_alias: str = "Rescatista"
    owner_alias: str
    messages: list[ChatMessage] = Field(default_factory=list)
