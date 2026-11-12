from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class PaymentStatus(str, Enum):
    ESCROW = "ESCROW"        # En custodia segura (pagado por dueño, retenido por PetCode)
    RELEASED = "RELEASED"    # Liberado al rescatista (95% entregado, 5% ganancia PetCode)
    REFUNDED = "REFUNDED"    # Devuelto al dueño

class RewardPayment(BaseModel):
    id: str
    pet_token: str
    pet_name: str
    session_token: str
    owner_email: str
    owner_masked_name: str
    rescuer_alias: str = "Rescatista"
    total_reward: float                       # Monto total configurado por el dueño (100%)
    platform_fee: float                       # Comisión de la plataforma PetCode (5%)
    rescuer_payout: float                     # Monto neto para el rescatista (95%)
    status: PaymentStatus = PaymentStatus.ESCROW
    payment_method: str = "PSE / Garantía PetCode Escrow"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    released_at: Optional[datetime] = None

class RewardSetRequest(BaseModel):
    pet_token: str
    amount: float

class RewardReleaseRequest(BaseModel):
    session_token: str
