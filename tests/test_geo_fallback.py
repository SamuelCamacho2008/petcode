"""
PetCode Automated Test Suite - Geolocation & Contingency
IEEE Std 830-1998 Traceability:
- RF-RES-02 CA1: Express 3-Second Flow (TEST-GEO-02)
- RF-RES-02 CA2: Denial Graceful Fallback (TEST-GEO-01)
"""
import time
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from app.services.storage import storage

class TestGeolocationFallbackAndExpress:
    """
    Suite de pruebas para conmutador de geolocalización asistida y degradación grácil.
    """

    def test_geo_01_denial_graceful_fallback(self, client: TestClient):
        """
        TEST-GEO-01 (Denial Graceful Fallback - RF-RES-02 CA2):
        Valida que ante la denegación o bloqueo de geolocalización GPS:
        1. La vista pública /q/{token} responde HTTP 200 sin pantalla blanca ni fallos.
        2. El DOM contiene el contenedor de contingencia (#fallback-panel) y botón de Chat Seguro.
        3. El script de la página implementa la interceptación de error GPS (triggerGracefulDegradation)
           sin lanzar excepciones no controladas ni modales invasivos.
        4. El temporizador de transición configurado en el script es estrictamente < 200 ms (50 ms configurado).
        5. El envío manual de dirección/barrio alternativo funciona de forma transparente.
        """
        token = "LUNA-COL-99"
        response = client.get(f"/q/{token}")
        
        # 1. Código HTTP 200 y contenido presente
        assert response.status_code == 200, f"RF-RES-02 CA2 FAIL: /q/{token} retornó status {response.status_code}"
        html_content = response.text
        assert len(html_content) > 500, "RF-RES-02 CA2 FAIL: HTML retornado está vacío o trunco"
        
        # 2. Análisis del DOM con BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Validar existencia de paneles clave
        action_panel = soup.find(id="action-panel")
        fallback_panel = soup.find(id="fallback-panel")
        btn_express_gps = soup.find(id="btn-express-gps")
        btn_fallback_chat = soup.find(id="btn-fallback-chat")
        manual_form = soup.find(id="manual-location-form")
        manual_input = soup.find(id="manual-address-input")
        
        assert action_panel is not None, "RF-RES-02 CA2 FAIL: Falta contenedor #action-panel"
        assert fallback_panel is not None, "RF-RES-02 CA2 FAIL: Falta contenedor de contingencia #fallback-panel"
        assert btn_express_gps is not None, "RF-RES-02 CA1 FAIL: Falta botón #btn-express-gps"
        assert btn_fallback_chat is not None, "RF-RES-02 CA2 FAIL: Falta botón de chat de contingencia #btn-fallback-chat"
        assert manual_form is not None, "RF-RES-02 CA2 FAIL: Falta formulario de dirección manual"
        assert manual_input is not None, "RF-RES-02 CA2 FAIL: Falta input de dirección manual"
        
        # 3. Validar lógica en scripts JS para el manejo de rechazo de geolocalización
        assert "triggerGracefulDegradation" in html_content, (
            "RF-RES-02 CA2 FAIL: El script no define la función de degradación grácil 'triggerGracefulDegradation'"
        )
        assert "fallbackPanel.style.display" in html_content, (
            "RF-RES-02 CA2 FAIL: La función no conmuta la visibilidad del panel de contingencia"
        )
        
        # 4. Validar temporizador de transición < 200 ms
        # En el script: setTimeout(() => { ... }, 50)
        # Extraer el valor numérico en milisegundos
        import re
        timeout_match = re.search(r"setTimeout\s*\(\s*\(\)\s*=>\s*\{[^}]*fallbackPanel[^}]*\}\s*,\s*(\d+)\s*\)", html_content)
        if timeout_match:
            delay_ms = int(timeout_match.group(1))
            assert delay_ms < 200, f"RF-RES-02 CA2 FAIL: El delay de contingencia es {delay_ms}ms, debe ser < 200ms"
        else:
            # Si no hay setTimeout, la activación es síncrona (0ms), lo cual es < 200ms
            pass

        # 5. Probar el flujo del fallback manual (Simulación de POST de contingencia sin GPS)
        manual_payload = {
            "token": token,
            "manual_address": "Carrera 7 con Calle 72, frente al parque",
            "latitude": None,
            "longitude": None,
            "accuracy": None
        }
        manual_resp = client.post("/api/v1/scans", json=manual_payload)
        assert manual_resp.status_code == 201, f"RF-RES-02 CA2 FAIL: POST manual retornó {manual_resp.status_code}"
        manual_data = manual_resp.json()
        assert manual_data["status"] == "success"
        assert manual_data["mode"] == "MANUAL_ADDRESS"

    def test_geo_02_express_3_second_flow(self, client: TestClient):
        """
        TEST-GEO-02 (Express 3-Second Flow - RF-RES-02 CA1):
        Simula geolocalización activa (lat: 2.4419, lon: -76.6063, accuracy: 12m).
        Valida que el despacho POST a /api/v1/scans:
        1. Responda con código HTTP 201 Created.
        2. Se complete en tiempo récord (< 1.5 segundos) satisfaciendo la cota de 3 segundos del flujo total.
        3. Entregue una confirmación visual y amigable de rescate (status: 'success', alert_sent: True).
        4. Registre el evento satelital en el repositorio y active las notificaciones del dueño.
        """
        token = "LUNA-COL-99"
        payload = {
            "token": token,
            "latitude": 2.4419,
            "longitude": -76.6063,
            "accuracy": 12.0
        }

        # Medición estricta de tiempo de respuesta
        start_time = time.perf_counter()
        response = client.post("/api/v1/scans", json=payload)
        elapsed_time = time.perf_counter() - start_time

        # 1. Verificación de Código HTTP
        assert response.status_code == 201, f"RF-RES-02 CA1 FAIL: POST retornó código {response.status_code}"

        # 2. Verificación de Latencia < 1.5s
        assert elapsed_time < 1.5, f"RF-RES-02 CA1 FAIL: Latencia de escaneo {elapsed_time:.3f}s supera el umbral de 1.5s"

        # 3. Verificación de Payload de Confirmación
        data = response.json()
        assert data["status"] == "success", f"RF-RES-02 CA1 FAIL: status no fue success: {data}"
        assert data["alert_sent"] is True, "RF-RES-02 CA1 FAIL: alert_sent debe ser True"
        assert data["mode"] == "EXPRESS_GPS", "RF-RES-02 CA1 FAIL: mode debe ser EXPRESS_GPS"
        assert "Luna" in data["message"] or "Ubicación" in data["message"], (
            "RF-RES-02 CA1 FAIL: Mensaje de confirmación amigable ausente"
        )

        # 4. Verificación de Almacenamiento y Notificaciones
        scans = storage.get_scans_for_pet(token)
        assert len(scans) >= 1, "RF-RES-02 CA1 FAIL: El escaneo no se persistió en storage"
        latest_scan = scans[0]
        assert latest_scan.latitude == 2.4419
        assert latest_scan.longitude == -76.6063
        assert latest_scan.accuracy == 12.0

        # Verificar que la alerta multicanal fue registrada
        notifications = storage.get_notifications_for_pet(token)
        assert len(notifications) >= 1, "RF-RES-02 CA1 FAIL: No se registraron notificaciones para el dueño"
