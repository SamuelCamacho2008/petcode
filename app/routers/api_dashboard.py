from fastapi import APIRouter, HTTPException, Query, status, Request
from app.models.dashboard import (
    DashboardDataResponse,
    DashboardStatusUpdate,
    DashboardRecoverRequest
)
from app.models.pet import PetStatus
from app.models.account import ADMIN_EMAIL
from app.services.storage import storage
from app.services.payment_service import payment_service
from app.routers.api_account import get_current_user_from_request

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard API (Owner)"])

@router.get("/data", response_model=DashboardDataResponse)
async def get_dashboard_data(request: Request, token: str = Query(default="LUNA-COL-99")):
    """
    Retorna la información completa consolidada para el propietario (RF-DASH-01):
    Mascota, historial de escaneos geográficos, chats activos y notificaciones generadas.
    Aislamiento estricto: Solo retorna los chats pertenecientes a las mascotas del usuario activo.
    """
    normalized_token = token.strip().upper()
    pet = storage.get_pet(normalized_token)
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mascota con token '{normalized_token}' no encontrada."
        )

    current_user = get_current_user_from_request(request)
    is_admin = (current_user.email.lower() == ADMIN_EMAIL.lower())
    is_owner = (pet.owner_private_email.lower() == current_user.email.lower())

    scans = storage.get_scans_for_pet(normalized_token)
    notifications = storage.get_notifications_for_pet(normalized_token)

    # AISLAMIENTO DE CHATS:
    # Solo se retornan los chats si el usuario es el dueño de esta mascota o el Administrador.
    # Los demás usuarios NO pueden ver las conversaciones de terceros.
    if is_owner or is_admin:
        active_chats = storage.get_active_sessions_for_pet(normalized_token)
    else:
        active_chats = []

    # Cálculo de ganancias de la plataforma si es el Admin
    platform_earnings = None
    if is_admin:
        all_payments = storage.get_all_payments()
        analytics = payment_service.get_financial_analytics(all_payments)
        platform_earnings = analytics["platform_earnings_5_percent"]

    return DashboardDataResponse(
        pet=pet,
        recent_scans=scans,
        active_chat_sessions=active_chats,
        recent_notifications=notifications,
        user_email=current_user.email,
        is_admin=is_admin,
        platform_earnings=platform_earnings
    )

@router.post("/status")
async def update_pet_status(payload: DashboardStatusUpdate):
    """
    Conmuta el estado de la mascota entre 'LOST' y 'AT_HOME' (RF-DASH-01 CA1).
    Permite fijar monto de recompensa cuando se activa el Modo Perdida.
    """
    normalized_token = payload.token.strip().upper()
    updated_pet = storage.update_pet_status(
        token=normalized_token,
        status=payload.status,
        reward_amount=payload.reward_amount
    )
    if not updated_pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mascota con token '{normalized_token}' no encontrada."
        )

    return {
        "status": "success",
        "token": updated_pet.token,
        "new_status": updated_pet.status.value,
        "reward_amount": updated_pet.reward_amount,
        "reward_active": updated_pet.reward_active,
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
