from fastapi import APIRouter, HTTPException, status
from app.models.pet import PetPublic, PetCreate
from app.services.storage import storage

router = APIRouter(prefix="/api/v1/pets", tags=["Pets API"])

@router.get("/public/{token}", response_model=PetPublic)
async def get_pet_public_info(token: str):
    """
    Retorna la información pública no confidencial de una mascota (RS-SEC-01).
    CERO-DOXXING: NUNCA expone teléfono personal, dirección domiciliaria ni correo del propietario.
    """
    pet_public = storage.get_pet_public(token.strip().upper())
    if not pet_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placa inteligente con token '{token}' no encontrada en el sistema PetCode."
        )
    return pet_public

@router.post("/", response_model=PetPublic, status_code=status.HTTP_201_CREATED)
async def register_new_pet(pet_data: PetCreate):
    """
    Registra un nuevo propietario y su mascota en el sistema.
    Retorna el perfil público con el nuevo token generado.
    """
    new_pet = storage.create_pet(pet_data)
    return new_pet.to_public()
