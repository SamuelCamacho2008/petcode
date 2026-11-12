from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.storage import storage
from app.services.payment_service import payment_service
from app.models.account import ADMIN_EMAIL
from app.routers.api_account import get_current_user_from_request

router = APIRouter(tags=["Public Views"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
@router.get("/registro", response_class=HTMLResponse)
async def view_registration_page(request: Request):
    """
    Página principal de bienvenida y registro:
    Permite al usuario indicar quién es, registrar su mascota y obtener su placa QR inteligente.
    """
    current_user = get_current_user_from_request(request)
    is_admin = (current_user.email.lower() == ADMIN_EMAIL.lower())
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "all_pets": list(storage.pets.values()),
            "current_user": current_user,
            "is_admin": is_admin
        }
    )

@router.get("/q/{token}", response_class=HTMLResponse)
async def view_public_pet_profile(token: str, request: Request):
    """
    Vista pública de emergencia para rescatistas (RF-RES-01).
    CERO DOXXING: La plantilla NUNCA recibe ni renderiza teléfono ni dirección del dueño.
    """
    normalized_token = token.strip().upper()
    pet_public = storage.get_pet_public(normalized_token)
    if not pet_public:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={"token": normalized_token},
            status_code=status.HTTP_404_NOT_FOUND
        )

    return templates.TemplateResponse(
        request=request,
        name="public_pet.html",
        context={
            "pet": pet_public,
            "token": normalized_token
        }
    )

@router.get("/chat/{session_token}", response_class=HTMLResponse)
async def view_chat_room(session_token: str, request: Request, role: str = "rescuer"):
    """
    Sala de chat web efímera y anónima en tiempo real (RF-CHAT-01).
    El rol puede ser 'rescuer' o 'owner'. Por defecto 'rescuer'.
    """
    session = storage.get_chat_session(session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión de chat no encontrada o expirada."
        )

    current_user = get_current_user_from_request(request)
    is_admin = (current_user.email.lower() == ADMIN_EMAIL.lower())
    payment = storage.get_payment_for_session(session_token)

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "session": session,
            "session_token": session_token,
            "current_role": role if role in ["rescuer", "owner"] else "rescuer",
            "current_user": current_user,
            "is_admin": is_admin,
            "payment": payment
        }
    )

@router.get("/dashboard", response_class=HTMLResponse)
async def view_owner_dashboard(request: Request, token: str = "LUNA-COL-99"):
    """
    Panel de control privado del propietario con Geovisor Leaflet (RF-DASH-01).
    Garantiza privacidad: Solo lista mascotas y chats del usuario actual.
    """
    current_user = get_current_user_from_request(request)
    is_admin = (current_user.email.lower() == ADMIN_EMAIL.lower())
    user_pets = storage.get_pets_for_user(current_user.email)
    
    # Si no tiene mascotas aún, usar todas o fallback
    if not user_pets:
        user_pets = list(storage.pets.values())

    normalized_token = token.strip().upper()
    pet = storage.get_pet(normalized_token)
    
    # Si la mascota solicitada no pertenece al usuario (y no es admin), redirigir a su primera mascota
    if not pet or (pet not in user_pets and not is_admin):
        pet = user_pets[0]
        normalized_token = pet.token

    payment = None
    for p in storage.payments.values():
        if p.pet_token == normalized_token:
            payment = p
            break

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "pet": pet,
            "token": normalized_token,
            "all_pets": user_pets,
            "current_user": current_user,
            "is_admin": is_admin,
            "payment": payment
        }
    )

@router.get("/dashboard/plaque/{token}", response_class=HTMLResponse)
async def view_collar_plaque(token: str, request: Request):
    """
    Vista de placa física imprimible con código QR de emergencia.
    """
    normalized_token = token.strip().upper()
    pet = storage.get_pet(normalized_token)
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mascota no encontrada."
        )

    base_url = str(request.base_url).rstrip("/")
    qr_url = f"{base_url}/q/{normalized_token}"

    return templates.TemplateResponse(
        request=request,
        name="plaque.html",
        context={
            "pet": pet,
            "token": normalized_token,
            "qr_url": qr_url
        }
    )

@router.get("/simulador/{token}", response_class=HTMLResponse)
async def view_chat_simulator(token: str, request: Request):
    """
    Simulador interactivo de pantalla dividida (Rescatista ↔ Dueño).
    Permite probar en una sola ventana cómo conversan dos personas en tiempo real vía SSE,
    y cómo opera la liberación de recompensa con comisión del 5% de PetCode.
    """
    normalized_token = token.strip().upper()
    pet = storage.get_pet(normalized_token)
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mascota no encontrada."
        )

    session = storage.get_or_create_chat_session(normalized_token)
    payment = storage.get_payment_for_session(session.session_token)

    current_user = get_current_user_from_request(request)
    is_admin = (current_user.email.lower() == ADMIN_EMAIL.lower())

    return templates.TemplateResponse(
        request=request,
        name="simulator.html",
        context={
            "pet": pet,
            "session": session,
            "payment": payment,
            "current_user": current_user,
            "is_admin": is_admin
        }
    )

@router.get("/cuenta", response_class=HTMLResponse)
async def view_account_page(request: Request):
    """
    Página de información y configuración de la cuenta del usuario.
    Permite ver y editar nombre, teléfono y dirección, y conmutar de usuario para pruebas.
    """
    current_user = get_current_user_from_request(request)
    is_admin = (current_user.email.lower() == ADMIN_EMAIL.lower())
    user_pets = storage.get_pets_for_user(current_user.email)
    all_users = list(storage.users.values())

    return templates.TemplateResponse(
        request=request,
        name="account.html",
        context={
            "current_user": current_user,
            "is_admin": is_admin,
            "user_pets": user_pets,
            "all_users": all_users
        }
    )

@router.get("/admin", response_class=HTMLResponse)
async def view_admin_dashboard(request: Request):
    """
    Panel de Administración Exclusivo para samuelcamachoaguirre4@gmail.com.
    Permite auditar todas las recompensas pagadas, en custodia y la comisión del 5% de PetCode.
    """
    current_user = get_current_user_from_request(request)
    is_admin = (current_user.email.lower() == ADMIN_EMAIL.lower())
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido. Esta sección es exclusiva para el administrador (samuelcamachoaguirre4@gmail.com)."
        )

    all_payments = storage.get_all_payments()
    analytics = payment_service.get_financial_analytics(all_payments)

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "current_user": current_user,
            "is_admin": is_admin,
            "analytics": analytics,
            "payments": all_payments
        }
    )
