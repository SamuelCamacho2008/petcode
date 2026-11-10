from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class PetStatus(str, Enum):
    LOST = "LOST"
    AT_HOME = "AT_HOME"

class PetBase(BaseModel):
    token: str
    name: str
    species: str
    breed: str
    photo_url: str
    status: PetStatus = PetStatus.LOST
    medical_notes: str = ""
    owner_masked_name: str

class PetPublic(PetBase):
    """
    Modelo de vista pública con POLÍTICA ESTRICTA CERO-DOXXING (RS-SEC-01).
    Bajo ninguna circunstancia expone el teléfono ni la dirección domiciliaria del dueño.
    """
    pass

class PetCreate(BaseModel):
    """
    Modelo para registrar un nuevo propietario y su mascota en el sistema.
    """
    owner_name: str
    owner_phone: str = ""
    owner_email: str = ""
    owner_address: str = ""
    pet_name: str
    species: str = "Perro"
    breed: str = "Mestizo / Criollo"
    medical_notes: str = ""
    photo_url: str = "/static/img/luna.svg"
    status: PetStatus = PetStatus.AT_HOME

class Pet(PetBase):
    """
    Modelo interno completo de la mascota con información de contacto privada del dueño.
    Sólo accesible internamente por servicios de backend y notificaciones privadas.
    """
    owner_private_phone: str
    owner_private_address: str
    owner_private_email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_public(self) -> PetPublic:
        return PetPublic(
            token=self.token,
            name=self.name,
            species=self.species,
            breed=self.breed,
            photo_url=self.photo_url,
            status=self.status,
            medical_notes=self.medical_notes,
            owner_masked_name=self.owner_masked_name
        )
