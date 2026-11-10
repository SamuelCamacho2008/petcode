"""
PetCode Automated Test Suite - Security & Rate Limiting Resilience
IEEE Std 830-1998 Traceability:
- RF-API-01 CA2: Perimeter Rate Limiting on Scans (TEST-SEC-01)
"""
import time
import pytest
from fastapi.testclient import TestClient

class TestSecurityResilienceAndRateLimit:
    """
    Suite de resiliencia de seguridad: Protección perimetral contra inundación de escaneos (DDoS/Spam).
    OWASP ASVS V13 - API Rate Limiting.
    """

    def test_sec_01_scan_spamming_rate_limit(self, client: TestClient):
        """
        TEST-SEC-01 (Scan Spamming Rate Limit - RF-API-01 CA2):
        Envía una ráfaga de 10 peticiones POST consecutivas a /api/v1/scans en menos de 2 segundos:
        1. Las primeras 3 peticiones deben ser aceptadas y procesadas (HTTP 201 Created).
        2. A partir de la 4.ª petición consecutiva (peticiones 4 a 10), el servidor debe responder
           invariablemente con código HTTP 429 Too Many Requests.
        3. Cada respuesta 429 debe incluir obligatoriamente la cabecera estándar 'Retry-After'.
        4. Validar que peticiones desde otra IP o para otro token mantengan su cuota independiente.
        """
        token = "LUNA-COL-99"
        client_ip = "190.145.20.10"
        headers = {"X-Forwarded-For": client_ip}

        payload = {
            "token": token,
            "latitude": 4.698300,
            "longitude": -74.045000,
            "accuracy": 15.0
        }

        responses = []
        burst_start = time.perf_counter()

        # Enviar ráfaga de 10 peticiones consecutivas
        for i in range(10):
            resp = client.post("/api/v1/scans", json=payload, headers=headers)
            responses.append((i + 1, resp.status_code, resp.headers, resp.text))

        burst_duration = time.perf_counter() - burst_start

        # Validar que la ráfaga se completó en menos de 2 segundos
        assert burst_duration < 2.0, f"RF-API-01 CA2 FAIL: La prueba de ráfaga tardó {burst_duration:.2f}s (> 2.0s)"

        # 1. Peticiones 1 a 3 -> HTTP 201 Created
        for req_idx in range(3):
            req_num, status_code, _, body = responses[req_idx]
            assert status_code == 201, (
                f"RF-API-01 CA2 FAIL: Petición #{req_num} debía ser permitida (HTTP 201), pero retornó {status_code}: {body}"
            )

        # 2. Peticiones 4 a 10 -> HTTP 429 Too Many Requests
        for req_idx in range(3, 10):
            req_num, status_code, resp_headers, body = responses[req_idx]
            assert status_code == 429, (
                f"RF-API-01 CA2 FAIL: Petición #{req_num} debía ser bloqueada con HTTP 429, pero retornó {status_code}: {body}"
            )

            # 3. Validar cabecera Retry-After
            retry_after = resp_headers.get("retry-after") or resp_headers.get("Retry-After")
            assert retry_after is not None, (
                f"RF-API-01 CA2 FAIL: Petición #{req_num} (HTTP 429) no incluyó la cabecera requerida 'Retry-After'"
            )
            assert int(retry_after) > 0, (
                f"RF-API-01 CA2 FAIL: El valor de 'Retry-After' ({retry_after}) debe ser un entero positivo en segundos"
            )

        # 4. Validar aislamiento de cuota: una IP diferente NO debe ser bloqueada
        different_ip_headers = {"X-Forwarded-For": "200.75.50.99"}
        diff_resp = client.post("/api/v1/scans", json=payload, headers=different_ip_headers)
        assert diff_resp.status_code == 201, (
            f"RF-API-01 CA2 FAIL: IP independiente '200.75.50.99' fue bloqueada indebidamente con status {diff_resp.status_code}"
        )
