from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from typing import Optional

ADMIN_EMAIL = "samuelcamachoaguirre4@gmail.com"

class UserRole(str, Enum):
    ADMIN = "admin"
    OWNER = "owner"

class User(BaseModel):
    email: str
    name: str
    phone: str = ""
    address: str = ""
    role: UserRole = UserRole.OWNER
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def full_name(self) -> str:
        return self.name

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN or self.email.lower() == ADMIN_EMAIL.lower()

    @classmethod
    def create(cls, email: str, name: str, phone: str = "", address: str = ""):
        clean_email = email.strip().lower()
        role = UserRole.ADMIN if clean_email == ADMIN_EMAIL else UserRole.OWNER
        return cls(
            email=clean_email,
            name=name,
            phone=phone,
            address=address,
            role=role
        )

class UserUpdate(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class UserSwitch(BaseModel):
    email: str
