from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.storage import storage

router = APIRouter(tags=["Public Views"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
@router.get("/registro", response_class=HTMLResponse)
async def view_registration_page(request: Request):
    """
    Página principal de bienvenida y registro:
    Permite al usuario indicar quién es, registrar su mascota y obtener su placa QR inteligente.
    """
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "all_pets": list(storage.pets.values())
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

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "session": session,
            "session_token": session_token,
            "current_role": role if role in ["rescuer", "owner"] else "rescuer"
        }
    )

@router.get("/dashboard", response_class=HTMLResponse)
async def view_owner_dashboard(request: Request, token: str = "LUNA-COL-99"):
    """
    Panel de control privado del propietario con Geovisor Leaflet (RF-DASH-01).
    """
    normalized_token = token.strip().upper()
    pet = storage.get_pet(normalized_token)
    if not pet:
        # Fallback a la primera mascota si no existe
        pet = next(iter(storage.pets.values()))
        normalized_token = pet.token

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "pet": pet,
            "token": normalized_token,
            "all_pets": list(storage.pets.values())
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
    Permite probar en una sola ventana cómo conversan dos personas en tiempo real vía SSE.
    """
    normalized_token = token.strip().upper()
    pet = storage.get_pet(normalized_token)
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mascota no encontrada."
        )

    # Crear o recuperar sesión de chat para la simulación
    session = storage.create_chat_session(normalized_token)

    return templates.TemplateResponse(
        request=request,
        name="simulator.html",
        context={
            "pet": pet,
            "session": session
        }
    )
