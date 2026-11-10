from fastapi import APIRouter, HTTPException, Query, status
from app.models.dashboard import (
    DashboardDataResponse,
    DashboardStatusUpdate,
    DashboardRecoverRequest
)
from app.models.pet import PetStatus
from app.services.storage import storage

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard API (Owner)"])

@router.get("/data", response_model=DashboardDataResponse)
async def get_dashboard_data(token: str = Query(default="LUNA-COL-99")):
    """
    Retorna la información completa consolidada para el propietario (RF-DASH-01):
    Mascota, historial de escaneos geográficos, chats activos y notificaciones generadas.
    """
    normalized_token = token.strip().upper()
    pet = storage.get_pet(normalized_token)
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mascota con token '{normalized_token}' no encontrada."
        )

    scans = storage.get_scans_for_pet(normalized_token)
    active_chats = storage.get_active_sessions_for_pet(normalized_token)
    notifications = storage.get_notifications_for_pet(normalized_token)

    return DashboardDataResponse(
        pet=pet,
        recent_scans=scans,
        active_chat_sessions=active_chats,
        recent_notifications=notifications
    )

@router.post("/status")
async def update_pet_status(payload: DashboardStatusUpdate):
    """
    Conmuta el estado de la mascota entre 'LOST' y 'AT_HOME' (RF-DASH-01 CA1).
    Sincronizado en tiempo real con la ficha pública.
    """
    normalized_token = payload.token.strip().upper()
    updated_pet = storage.update_pet_status(normalized_token, payload.status)
    if not updated_pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mascota con token '{normalized_token}' no encontrada."
        )

    return {
        "status": "success",
        "token": updated_pet.token,
        "new_status": updated_pet.status.value,
        "message": f"Estado de {updated_pet.name} actualizado a {updated_pet.status.value}"
    }

@router.post("/recover")
async def mark_pet_recovered(payload: DashboardRecoverRequest):
    """
    Marca la mascota como recuperada ('AT_HOME') y archiva las sesiones de chat activas (RF-DASH-01 CA4).
    """
    normalized_token = payload.token.strip().upper()
    pet = storage.update_pet_status(normalized_token, PetStatus.AT_HOME)
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mascota con token '{normalized_token}' no encontrada."
        )

    archived_count = storage.archive_sessions_for_pet(normalized_token)

    return {
        "status": "recovered",
        "token": pet.token,
        "pet_name": pet.name,
        "new_status": PetStatus.AT_HOME.value,
        "archived_chats_count": archived_count,
        "message": f"¡Enhorabuena! {pet.name} ha sido marcada como recuperada y en casa."
    }
