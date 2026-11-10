import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.services.storage import storage
from app.services.rate_limiter import scan_rate_limiter
from app.services.purge_service import purge_service
from app.models.scan import ScanRecord
from app.models.chat import ChatMessage, ChatSenderRole

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_system_state():
    """Reinicia el estado en memoria antes de cada prueba unitaria."""
    storage.reset_for_tests()
    scan_rate_limiter.reset_for_tests()
    yield

# =========================================================================
# 1. PRUEBAS DE PRIVACIDAD ESTRICTA: CERO DOXXING (RS-SEC-01 / TEST-PRIV-01)
# =========================================================================

def test_api_pet_public_zero_doxxing():
    """
    Verifica que GET /api/v1/pets/public/{token} NUNCA retorne datos privados del dueño.
    """
    response = client.get("/api/v1/pets/public/LUNA-COL-99")
    assert response.status_code == 200
    data = response.json()

    # Campos públicos esperados
    assert data["token"] == "LUNA-COL-99"
    assert data["name"] == "Luna"
    assert data["species"] == "Perro"
    assert data["breed"] == "Golden Retriever"
    assert data["status"] == "LOST"
    assert "insulina" in data["medical_notes"].lower()
    assert data["owner_masked_name"] == "Dueño de Luna"

    # Verificación Anti-Doxxing
    assert "owner_private_phone" not in data
    assert "owner_private_address" not in data
    assert "owner_private_email" not in data
    assert "+57 300 123 4567" not in str(data)
    assert "Calle 123" not in str(data)

def test_public_view_html_zero_doxxing():
    """
    Verifica que la vista web /q/{token} no contenga teléfonos ni direcciones en el HTML o scripts.
    """
    response = client.get("/q/LUNA-COL-99")
    assert response.status_code == 200
    html_content = response.text

    # Verifica renderizado de datos públicos
    assert "Luna" in html_content
    assert "Golden Retriever" in html_content
    assert "Requiere insulina diaria" in html_content
    assert "Dueño de Luna" in html_content

    # Auditoría CERO DOXXING: Absolutamente ningún dato de contacto real en el DOM
    assert "+57 300 123 4567" not in html_content
    assert "Calle 123 #45-67" not in html_content
    assert "dueno.luna@example.com" not in html_content
    assert "Cedritos" not in html_content

def test_public_view_nonexistent_token():
    """Verifica manejo 404 para tokens no existentes."""
    response = client.get("/q/INVALIDA-999")
    assert response.status_code == 404
    assert "Placa no registrada" in response.text

# =========================================================================
# 2. PRUEBAS DE MODO EXPRESS Y ESCANEOS (RF-RES-02 CA1 / TEST-GEO-02)
# =========================================================================

def test_post_scan_express_gps():
    """
    Verifica el registro de escaneo satelital GPS en 1 clic.
    """
    payload = {
        "token": "LUNA-COL-99",
        "latitude": 4.698300,
        "longitude": -74.045000,
        "accuracy": 12.5
    }
    response = client.post("/api/v1/scans", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["mode"] == "EXPRESS_GPS"
    assert data["alert_sent"] is True
    assert "Luna" in data["message"]

    # Verificar que el escaneo quedó en el almacenamiento
    scans = storage.get_scans_for_pet("LUNA-COL-99")
    assert any(s.id == data["scan_id"] for s in scans)

    # Verificar que las notificaciones del MockNotificationManager fueron disparadas
    notifications = storage.get_notifications_for_pet("LUNA-COL-99")
    assert len(notifications) >= 3  # Push, Email, SMS

def test_post_scan_manual_address_fallback():
    """
    Verifica el escaneo mediante dirección manual (Degradación Grácil).
    """
    payload = {
        "token": "LUNA-COL-99",
        "manual_address": "Parque de la 93, cerca a la fuente"
    }
    response = client.post("/api/v1/scans", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["mode"] == "MANUAL_ADDRESS"

    # Verificar en el almacenamiento
    scans = storage.get_scans_for_pet("LUNA-COL-99")
    matching = [s for s in scans if s.id == data["scan_id"]]
    assert len(matching) == 1
    assert matching[0].manual_address == "Parque de la 93, cerca a la fuente"

# =========================================================================
# 3. PRUEBAS DE RATE LIMITING PERIMETRAL (RF-API-01 CA2 / TEST-SEC-01)
# =========================================================================

def test_rate_limiting_enforcement():
    """
    Verifica que la 4ª petición POST /api/v1/scans en menos de 10 minutos
    sea bloqueada con HTTP 429 Too Many Requests y cabecera Retry-After.
    """
    payload = {
        "token": "LUNA-COL-99",
        "latitude": 4.7000,
        "longitude": -74.0400,
        "accuracy": 10.0
    }

    # 1ª Petición -> OK (201)
    res1 = client.post("/api/v1/scans", json=payload)
    assert res1.status_code == 201

    # 2ª Petición -> OK (201)
    res2 = client.post("/api/v1/scans", json=payload)
    assert res2.status_code == 201

    # 3ª Petición -> OK (201)
    res3 = client.post("/api/v1/scans", json=payload)
    assert res3.status_code == 201

    # 4ª Petición -> HTTP 429 Too Many Requests
    res4 = client.post("/api/v1/scans", json=payload)
    assert res4.status_code == 429
    assert "Retry-After" in res4.headers
    retry_after = int(res4.headers["Retry-After"])
    assert retry_after > 0
    err_detail = res4.json()["detail"]
    assert "Rate limit exceeded" in str(err_detail)

# =========================================================================
# 4. PRUEBAS DE CHAT ANÓNIMO Y TIEMPO REAL (RF-CHAT-01 / TEST-CHAT-01)
# =========================================================================

def test_chat_session_creation_and_messaging():
    """
    Verifica creación de sesión efímera, roles enmascarados y publicación de mensajes.
    """
    # 1. Crear sesión de chat
    session_res = client.post("/api/v1/chat/sessions", json={"pet_token": "LUNA-COL-99"})
    assert session_res.status_code == 201
    session_data = session_res.json()
    session_token = session_data["session_token"]
    assert session_data["rescuer_alias"] == "Rescatista"
    assert session_data["owner_alias"] == "Dueño de Luna"

    # 2. Rescatista envía mensaje con texto
    msg_res = client.post("/api/v1/chat/messages", json={
        "session_token": session_token,
        "sender": "rescuer",
        "text": "Hola, acabo de encontrar a Luna en la esquina del parque."
    })
    assert msg_res.status_code == 201
    msg_data = msg_res.json()
    assert msg_data["sender_display_name"] == "Rescatista"
    assert msg_data["text"] == "Hola, acabo de encontrar a Luna en la esquina del parque."

    # 3. Dueño responde
    owner_msg_res = client.post("/api/v1/chat/messages", json={
        "session_token": session_token,
        "sender": "owner",
        "text": "¡Muchas gracias! Ya voy hacia allá."
    })
    assert owner_msg_res.status_code == 201
    assert owner_msg_res.json()["sender_display_name"] == "Dueño de Luna"

    # 4. Obtener mensajes históricos
    history_res = client.get(f"/api/v1/chat/{session_token}/messages")
    assert history_res.status_code == 200
    assert len(history_res.json()) == 2

# =========================================================================
# 5. PRUEBAS DE SANITIZACIÓN ANTI-XSS (RS-SEC-02 / TEST-CHAT-03)
# =========================================================================

def test_chat_xss_sanitization():
    """
    Verifica que payloads maliciosos sean neutralizados y escapados para prevenir XSS.
    """
    session = storage.get_or_create_chat_session("LUNA-COL-99")
    
    malicious_payload = "<script>alert('pwned')</script><img src=x onerror=alert(1)><b>Negrita</b>"
    msg_res = client.post("/api/v1/chat/messages", json={
        "session_token": session.session_token,
        "sender": "rescuer",
        "text": malicious_payload
    })
    assert msg_res.status_code == 201
    sanitized_text = msg_res.json()["text"]

    # No debe contener etiquetas <script> ni atributos ejecutables activos
    assert "<script>" not in sanitized_text
    assert "<img" not in sanitized_text
    assert "&lt;script&gt;" in sanitized_text
    assert "&lt;img" in sanitized_text

# =========================================================================
# 6. PRUEBAS DE PURGA CON TTL DE 7 DÍAS (RF-API-01 CA4 / TEST-PURGE-01)
# =========================================================================

def test_purge_service_ttl():
    """
    Verifica que tras 7 días se disuelvan las coordenadas GPS exactas y se purguen mensajes.
    """
    now = datetime.utcnow()
    old_date = now - timedelta(days=8) # Antigüedad > 7 días
    recent_date = now - timedelta(days=2) # Antigüedad < 7 días

    # Crear escaneo antiguo
    old_scan = ScanRecord(
        id="old-scan-1",
        token="LUNA-COL-99",
        latitude=4.698300,
        longitude=-74.045000,
        accuracy=15.0,
        ip_address="190.25.10.1",
        created_at=old_date
    )
    # Crear escaneo reciente
    recent_scan = ScanRecord(
        id="recent-scan-1",
        token="LUNA-COL-99",
        latitude=4.710000,
        longitude=-74.050000,
        accuracy=20.0,
        ip_address="190.25.10.2",
        created_at=recent_date
    )
    storage.add_scan(old_scan)
    storage.add_scan(recent_scan)

    # Crear sesión con mensaje antiguo y mensaje reciente
    session = storage.get_or_create_chat_session("LUNA-COL-99")
    old_msg = ChatMessage(
        id="old-msg-1",
        session_token=session.session_token,
        sender=ChatSenderRole.RESCUER,
        sender_display_name="Rescatista",
        text="Mensaje viejo",
        timestamp=old_date
    )
    recent_msg = ChatMessage(
        id="recent-msg-1",
        session_token=session.session_token,
        sender=ChatSenderRole.RESCUER,
        sender_display_name="Rescatista",
        text="Mensaje reciente",
        timestamp=recent_date
    )
    storage.add_message_to_session(old_msg)
    storage.add_message_to_session(recent_msg)

    # Ejecutar la tarea de purga
    result = purge_service.purge_old_data(reference_time=now)
    assert result["purged_scans_count"] >= 1
    assert result["purged_messages_count"] >= 1

    # Verificar que el escaneo antiguo perdió coordenadas exactas
    assert old_scan.latitude is None
    assert old_scan.longitude is None
    assert old_scan.exact_coords_purged is True

    # Verificar que el escaneo reciente conservó sus coordenadas
    assert recent_scan.latitude == 4.710000
    assert recent_scan.longitude == -74.050000
    assert recent_scan.exact_coords_purged is False

    # Verificar que en el chat sólo sobrevivió el mensaje reciente
    updated_session = storage.get_chat_session(session.session_token)
    msg_ids = [m.id for m in updated_session.messages]
    assert "recent-msg-1" in msg_ids
    assert "old-msg-1" not in msg_ids

# =========================================================================
# 7. PRUEBAS DEL DASHBOARD Y RECUPERACIÓN (RF-DASH-01 / TEST-DASH-01)
# =========================================================================

def test_dashboard_status_toggle_and_recovery():
    """
    Verifica conmutador de estado LOST <-> AT_HOME y botón ¡Mascota Recuperada!.
    """
    # 1. Cambiar estado a AT_HOME
    res1 = client.post("/api/v1/dashboard/status", json={"token": "LUNA-COL-99", "status": "AT_HOME"})
    assert res1.status_code == 200
    assert res1.json()["new_status"] == "AT_HOME"

    # Verificar que la ficha pública refleja el cambio de inmediato
    pub_res = client.get("/api/v1/pets/public/LUNA-COL-99")
    assert pub_res.json()["status"] == "AT_HOME"

    # 2. Cambiar de nuevo a LOST
    res2 = client.post("/api/v1/dashboard/status", json={"token": "LUNA-COL-99", "status": "LOST"})
    assert res2.status_code == 200
    assert res2.json()["new_status"] == "LOST"

    # 3. Crear sesión activa
    session = storage.get_or_create_chat_session("LUNA-COL-99")
    assert session.status.value == "ACTIVE"

    # 4. Probar acción de Recuperación
    rec_res = client.post("/api/v1/dashboard/recover", json={"token": "LUNA-COL-99"})
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["status"] == "recovered"
    assert rec_data["new_status"] == "AT_HOME"

    # Verificar que la sesión de chat fue archivada
    updated_session = storage.get_chat_session(session.session_token)
    assert updated_session.status.value == "ARCHIVED"
