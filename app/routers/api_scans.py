import uuid
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status
from app.models.scan import ScanCreate, ScanRecord, ScanResponse
from app.services.storage import storage
from app.services.rate_limiter import scan_rate_limiter
from app.services.notification_service import notification_manager

router = APIRouter(prefix="/api/v1/scans", tags=["Scans API"])

def get_client_ip(request: Request) -> str:
    """Extrae la IP real del cliente, considerando proxies inversos si aplica."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def submit_scan(payload: ScanCreate, request: Request):
    """
    Registra un evento de escaneo de placa inteligente y dispara notificaciones al dueño (RF-RES-02 / RF-API-01).
    Aplica Rate Limiting estricto: Máximo 3 peticiones cada 10 minutos por (IP + Token).
    La 4ª petición retorna HTTP 429 Too Many Requests con cabecera Retry-After.
    """
    client_ip = get_client_ip(request)
    normalized_token = payload.token.strip().upper()

    # 1. Verificación perimetral de Rate Limiting
    scan_rate_limiter.check_and_record(client_ip, normalized_token)

    # 2. Validación de existencia de la mascota
    pet = storage.get_pet(normalized_token)
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placa inteligente con token '{normalized_token}' no registrada."
        )

    # 3. Determinar modo de escaneo
    has_gps = payload.latitude is not None and payload.longitude is not None
    has_manual = bool(payload.manual_address and payload.manual_address.strip())

    if not has_gps and not has_manual:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe suministrar coordenadas satelitales (GPS) o una dirección/barrio manual."
        )

    mode = "EXPRESS_GPS" if has_gps else "MANUAL_ADDRESS"

    # 4. Crear y almacenar registro de escaneo
    scan_record = ScanRecord(
        id=str(uuid.uuid4()),
        token=normalized_token,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy=payload.accuracy,
        manual_address=payload.manual_address.strip() if payload.manual_address else None,
        ip_address=client_ip,
        created_at=payload.timestamp or datetime.utcnow()
    )
    storage.add_scan(scan_record)

    # 5. Despacho asíncrono desacoplado de notificaciones (Strategy Pattern)
    await notification_manager.dispatch_scan_alert(pet, scan_record)

    return ScanResponse(
        status="success",
        message=f"¡Ubicación de {pet.name} reportada exitosamente al dueño! Muchas gracias por tu ayuda.",
        scan_id=scan_record.id,
        pet_name=pet.name,
        alert_sent=True,
        mode=mode
    )
