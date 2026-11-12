"""
Pruebas Automatizadas de Menú de Cuenta, Administración Exclusiva de Samuel,
Custodia de Recompensas con Retención del 5% de PetCode y Aislamiento Estricto de Chats.
Cumplimiento de IEEE Std 830-1998 y Política de Privacidad Anti-Doxxing.
"""
import pytest
from fastapi.testclient import TestClient

from app.models.account import ADMIN_EMAIL
from app.services.storage import storage


def test_admin_access_control_samuel_exclusive(client: TestClient):
    """
    Verifica que únicamente el correo samuelcamachoaguirre4@gmail.com
    tenga acceso al Panel Financiero del 5% y endpoints analíticos.
    Cualquier otro usuario debe recibir HTTP 403 Forbidden.
    """
    # 1. Acceso como Samuel (Superadministrador)
    client.cookies.set("petcode_user", ADMIN_EMAIL)
    res_admin_api = client.get("/api/v1/payments/admin/financials")
    assert res_admin_api.status_code == 200, f"Error: {res_admin_api.text}"
    data = res_admin_api.json()
    assert "analytics" in data
    assert data["analytics"]["platform_fee_percent"] == 5.0
    assert data["analytics"]["platform_earnings_collected"] >= 10000.0  # Pago pasado de Rocky

    res_admin_view = client.get("/admin")
    assert res_admin_view.status_code == 200
    assert "Panel Financiero y Control de Pagos" in res_admin_view.text
    assert "samuelcamachoaguirre4@gmail.com" in res_admin_view.text

    # 2. Acceso denegado para usuario regular (Dueño de Max)
    client.cookies.set("petcode_user", "dueno.max@example.com")
    res_unauth_api = client.get("/api/v1/payments/admin/financials")
    assert res_unauth_api.status_code == 403

    res_unauth_view = client.get("/admin")
    assert res_unauth_view.status_code == 403


def test_reward_escrow_calculation_and_release_split(client: TestClient):
    """
    Verifica que al fijar una recompensa:
    - PetCode calcula exactamente el 5% de comisión técnica para la plataforma.
    - El rescatista tiene asignado el 95% restante.
    - Al liberarse la recompensa tras el rescate, se liquida correctamente.
    """
    client.cookies.set("petcode_user", ADMIN_EMAIL)

    # 1. Crear custodia de $100,000 COP
    escrow_payload = {
        "pet_token": "LUNA-COL-99",
        "amount": 100000.0
    }
    res_escrow = client.post("/api/v1/payments/escrow", json=escrow_payload)
    assert res_escrow.status_code == 200, f"Error: {res_escrow.text}"
    payment_data = res_escrow.json()

    assert payment_data["total_reward"] == 100000.0
    assert payment_data["platform_fee"] == 5000.0    # 5% de 100.000
    assert payment_data["rescuer_payout"] == 95000.0 # 95% de 100.000
    assert payment_data["status"] == "ESCROW"

    session_token = payment_data["session_token"]

    # 2. Liberar recompensa al rescatista
    release_payload = {
        "session_token": session_token
    }
    res_release = client.post("/api/v1/payments/release", json=release_payload)
    assert res_release.status_code == 200, f"Error: {res_release.text}"
    released_data = res_release.json()["payment"]

    assert released_data["status"] == "RELEASED"
    assert released_data["platform_fee"] == 5000.0
    assert released_data["rescuer_payout"] == 95000.0
    assert released_data["released_at"] is not None


def test_chat_privacy_isolation_between_different_users(client: TestClient):
    """
    Garantiza que los chats y notificaciones de una mascota solo
    puedan ser vistos por el usuario que es dueño de esa mascota o el rescatista.
    Terceros ajenos NO deben recibir los chats en su bandeja ni en el dashboard.
    """
    # Luna pertenece a Samuel (ADMIN_EMAIL)
    # Max pertenece a dueno.max@example.com

    # Crear una sesión activa para Luna
    session = storage.get_or_create_chat_session("LUNA-COL-99")
    assert session is not None
    active_token = session.session_token

    # 1. Samuel consulta el dashboard de Luna: debe ver la sesión de chat de Luna
    client.cookies.set("petcode_user", ADMIN_EMAIL)
    res_samuel = client.get("/api/v1/dashboard/data?token=LUNA-COL-99")
    assert res_samuel.status_code == 200
    samuel_data = res_samuel.json()
    assert len(samuel_data["active_chat_sessions"]) >= 1
    session_tokens_samuel = [s["session_token"] for s in samuel_data["active_chat_sessions"]]
    assert active_token in session_tokens_samuel

    # 2. El Dueño de Max consulta el dashboard de Luna: NO debe ver las sesiones de chat de Luna
    client.cookies.set("petcode_user", "dueno.max@example.com")
    res_max_owner = client.get("/api/v1/dashboard/data?token=LUNA-COL-99")
    assert res_max_owner.status_code == 200
    max_owner_data = res_max_owner.json()
    
    # La lista de sesiones de chat debe estar aislada (no debe tener la de Luna)
    session_tokens_other = [s["session_token"] for s in max_owner_data["active_chat_sessions"]]
    assert active_token not in session_tokens_other


def test_account_profile_update_and_persistence(client: TestClient):
    """
    Verifica que el usuario pueda visualizar y actualizar su información
    de perfil desde la ruta de Mi Cuenta (/cuenta y /api/v1/account/update).
    """
    client.cookies.set("petcode_user", ADMIN_EMAIL)
    
    # Obtener perfil actual
    res_me = client.get("/api/v1/account/me")
    assert res_me.status_code == 200
    assert res_me.json()["email"] == ADMIN_EMAIL

    # Actualizar datos de contacto privados
    update_payload = {
        "name": "Samuel Camacho Aguirre (Admin)",
        "phone": "+57 312 999 8888",
        "address": "Calle 100 # 15-20, Bogotá D.C."
    }
    res_update = client.post("/api/v1/account/update", json=update_payload)
    assert res_update.status_code == 200
    updated_user = res_update.json()
    assert updated_user["name"] == "Samuel Camacho Aguirre (Admin)"
    assert updated_user["phone"] == "+57 312 999 8888"

    # Verificar que el HTML de /cuenta renderice la información actualizada
    res_view = client.get("/cuenta")
    assert res_view.status_code == 200
    assert "Samuel Camacho Aguirre (Admin)" in res_view.text
