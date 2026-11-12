from fastapi import APIRouter, Request, HTTPException, status
from app.models.payment import RewardPayment, RewardSetRequest, RewardReleaseRequest, PaymentStatus
from app.models.account import ADMIN_EMAIL
from app.models.chat import ChatMessage
from app.services.storage import storage
from app.services.payment_service import payment_service
from app.services.chat_service import chat_service
from app.routers.api_account import get_current_user_from_request

router = APIRouter(prefix="/api/v1/payments", tags=["Payments & Rewards API"])

@router.post("/escrow", response_model=RewardPayment)
async def setup_reward_escrow(request_data: RewardSetRequest, request: Request):
    """
    Registra una recompensa en custodia segura (Escrow).
    Calcula la comisión del 5% para PetCode y el 95% para el rescatista.
    """
    pet = storage.get_pet(request_data.pet_token.strip().upper())
    if not pet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mascota no encontrada")

    amount = max(0.0, float(request_data.amount))
    fee, payout = payment_service.calculate_split(amount)

    # Actualizar estado de recompensa en la mascota
    pet.reward_amount = amount
    pet.reward_active = amount > 0

    session = storage.get_or_create_chat_session(pet.token)
    session_token = session.session_token if session else "unassigned"

    import uuid
    payment_id = f"pay-{uuid.uuid4().hex[:8]}"
    payment = RewardPayment(
        id=payment_id,
        pet_token=pet.token,
        pet_name=pet.name,
        session_token=session_token,
        owner_email=pet.owner_private_email,
        owner_masked_name=pet.owner_masked_name,
        rescuer_alias="Rescatista",
        total_reward=amount,
        platform_fee=fee,
        rescuer_payout=payout,
        status=PaymentStatus.ESCROW
    )
    storage.record_payment(payment)

    if session:
        session.reward_amount = amount
        session.reward_status = "ESCROW"
        session.payment_id = payment_id

        # Notificar en el chat sobre la recompensa asegurada
        sys_msg = ChatMessage(
            id=f"msg-sys-{uuid.uuid4().hex[:8]}",
            session_token=session_token,
            sender="owner",
            sender_display_name="Sistema PetCode (Garantía)",
            text=f"💰 Recompensa en custodia asegurada: ${amount:,.0f} COP. (95% para el rescatista: ${payout:,.0f} COP | 5% servicio PetCode: ${fee:,.0f} COP)."
        )
        storage.add_message_to_session(sys_msg)
        await chat_service.broadcast_message(session_token, sys_msg)

    return payment

@router.post("/release")
async def release_reward_to_rescuer(release_data: RewardReleaseRequest, request: Request):
    """
    El propietario libera la recompensa al rescatista al recibir a su mascota.
    PetCode acredita el 95% al rescatista y retiene el 5% de comisión.
    """
    session = storage.get_chat_session(release_data.session_token)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada")

    payment = storage.release_reward(release_data.session_token)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay recompensa en custodia pendiente de liberación para esta sesión"
        )

    import uuid
    # Emitir mensaje de felicitación y confirmación en el chat en tiempo real
    sys_msg = ChatMessage(
        id=f"msg-sys-{uuid.uuid4().hex[:8]}",
        session_token=session.session_token,
        sender="owner",
        sender_display_name="Sistema PetCode (Pago Exitoso)",
        text=f"🎉 ¡RECOMPENSA LIBERADA! Se han transferido exitosamente ${payment.rescuer_payout:,.0f} COP al rescatista. PetCode ha registrado la comisión del 5% (${payment.platform_fee:,.0f} COP)."
    )
    storage.add_message_to_session(sys_msg)
    await chat_service.broadcast_message(session.session_token, sys_msg)

    return {
        "status": "success",
        "message": "Recompensa liberada exitosamente al rescatista",
        "payment": payment
    }

@router.get("/admin/financials")
async def get_admin_financials(request: Request):
    """
    Acceso exclusivo de Administrador (samuelcamachoaguirre4@gmail.com).
    Reporte consolidado de pagos, recompensas y comisiones del 5% recaudadas por PetCode.
    """
    user = get_current_user_from_request(request)
    if user.email.lower() != ADMIN_EMAIL.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido. Solo el administrador (samuelcamachoaguirre4@gmail.com) puede auditar las ganancias y pagos."
        )

    all_payments = storage.get_all_payments()
    analytics = payment_service.get_financial_analytics(all_payments)

    return {
        "analytics": analytics,
        "transactions": all_payments
    }
