from fastapi import APIRouter, Request, Response, HTTPException, status, Query
from app.models.account import User, UserUpdate, UserSwitch, ADMIN_EMAIL
from app.services.storage import storage

router = APIRouter(prefix="/api/v1/account", tags=["Account API"])

def get_current_user_from_request(request: Request) -> User:
    """
    Identifica el usuario activo a través de cookie 'petcode_user' o parámetro 'user_email'.
    Por defecto retorna al Administrador Samuel Camacho si no hay sesión previa.
    """
    email = request.query_params.get("user_email")
    if not email:
        email = request.cookies.get("petcode_user")
    if not email:
        email = ADMIN_EMAIL
    
    clean_email = email.strip().lower()
    user = storage.get_user(clean_email)
    if not user:
        user = storage.get_or_create_user(clean_email)
    return user

@router.get("/me", response_model=User)
async def get_current_user_profile(request: Request):
    """
    Retorna la información del perfil del usuario actualmente autenticado.
    """
    return get_current_user_from_request(request)

@router.post("/update", response_model=User)
async def update_user_profile(update_data: UserUpdate, request: Request):
    """
    Actualiza la información personal de la cuenta (nombre, teléfono, dirección).
    """
    current_user = get_current_user_from_request(request)
    new_name = update_data.name or update_data.full_name
    updated = storage.update_user(
        email=current_user.email,
        name=new_name,
        phone=update_data.phone,
        address=update_data.address
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return updated

@router.post("/switch")
async def switch_active_user(switch_data: UserSwitch, response: Response):
    """
    Cambia el usuario activo fijando la cookie de sesión 'petcode_user'.
    Permite verificar la separación estricta de chats y el rol de Administrador.
    """
    clean_email = switch_data.email.strip().lower()
    user = storage.get_or_create_user(clean_email)
    response.set_cookie(key="petcode_user", value=clean_email, max_age=86400 * 30, path="/")
    return {
        "status": "success",
        "message": f"Sesión cambiada a {user.email}",
        "user": user
    }

@router.get("/users")
async def list_available_accounts():
    """
    Lista las cuentas disponibles para conmutar fácilmente en el menú de pruebas.
    """
    return list(storage.users.values())
