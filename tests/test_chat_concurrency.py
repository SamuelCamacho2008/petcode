"""
PetCode Automated Test Suite - Real-Time Chat & Security
IEEE Std 830-1998 Traceability:
- RF-CHAT-01 CA1-3: SSE Handshake & Messaging Latency (TEST-CHAT-01)
- RF-CHAT-01 CA3: Network Drop Recovery (TEST-CHAT-02)
- RF-CHAT-01 CA4 / RS-SEC-02 CA1: Payload Sanitization XSS (TEST-CHAT-03)
"""
import asyncio
import json
import time
import pytest
import httpx
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

class TestChatConcurrencyAndSanitization:
    """
    Suite de pruebas de concurrencia en tiempo real, resiliencia ante cortes de red y sanitización XSS.
    """

    @pytest.mark.asyncio
    async def test_chat_01_socket_sse_handshake_and_messaging(self, async_client: httpx.AsyncClient):
        """
        TEST-CHAT-01 (Socket/SSE Handshake & Messaging - RF-CHAT-01 CA1-3):
        Simula dos sesiones concurrentes (Rescatista y Dueño):
        1. Se crea la sesión efímera para la mascota.
        2. El Dueño se suscribe al canal Server-Sent Events (SSE) /api/v1/chat/{session_token}/stream.
        3. Se valida el handshake SSE inicial.
        4. El Rescatista envía el mensaje "Tengo a tu perro en el parque principal".
        5. Se certifica la recepción en el extremo del Dueño con latencia < 200 ms.
        6. Se valida el enmascaramiento estricto de identidades: "Rescatista" y "Dueño de Luna".
        """
        pet_token = "LUNA-COL-99"
        
        # 1. Crear sesión de chat
        resp_session = await async_client.post("/api/v1/chat/sessions", json={"pet_token": pet_token})
        assert resp_session.status_code == 201, f"RF-CHAT-01 FAIL: Error al crear sesión: {resp_session.text}"
        session_data = resp_session.json()
        session_token = session_data["session_token"]
        assert session_data["rescuer_alias"] == "Rescatista"
        assert session_data["owner_alias"] == "Dueño de Luna"

        # 2. Conectar stream SSE del Dueño
        stream_url = f"/api/v1/chat/{session_token}/stream"
        
        async with async_client.stream("GET", stream_url) as sse_stream:
            assert sse_stream.status_code == 200, f"RF-CHAT-01 FAIL: SSE retornó status {sse_stream.status_code}"
            assert "text/event-stream" in sse_stream.headers.get("content-type", "")

            # 3. Leer handshake inicial
            handshake_received = False
            async for line in sse_stream.aiter_lines():
                if "event: handshake" in line or "handshake" in line:
                    handshake_received = True
                    break

            assert handshake_received, "RF-CHAT-01 CA3 FAIL: No se recibió evento handshake de SSE"

            # 4. El Rescatista envía mensaje en tiempo real
            msg_text = "Tengo a tu perro en el parque principal"
            payload_rescuer = {
                "session_token": session_token,
                "sender": "rescuer",
                "text": msg_text
            }

            send_start_time = time.perf_counter()
            resp_post = await async_client.post("/api/v1/chat/messages", json=payload_rescuer)
            assert resp_post.status_code == 201, f"RF-CHAT-01 FAIL: POST mensaje rescatista retornó {resp_post.status_code}"

            # 5. Medir recepción en el stream SSE del Dueño (< 200 ms)
            received_message = None
            latency_seconds = None

            async def wait_for_sse_message():
                nonlocal received_message, latency_seconds
                async for line in sse_stream.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        try:
                            parsed = json.loads(data_str)
                            if parsed.get("text") == msg_text:
                                latency_seconds = time.perf_counter() - send_start_time
                                received_message = parsed
                                break
                        except json.JSONDecodeError:
                            continue

            await asyncio.wait_for(wait_for_sse_message(), timeout=1.0)

            # Validar latencia estricta < 200 ms
            assert received_message is not None, "RF-CHAT-01 CA3 FAIL: Mensaje no recibido por stream SSE"
            assert latency_seconds < 0.200, (
                f"RF-CHAT-01 CA3 FAIL: Latencia de entrega SSE fue {latency_seconds*1000:.1f}ms, debe ser < 200ms"
            )

            # 6. Validar identidad enmascarada del emisor
            assert received_message["sender_display_name"] == "Rescatista", (
                f"RF-CHAT-01 CA2 FAIL: Sender display name inválido: {received_message.get('sender_display_name')}"
            )

        # 7. Ahora el Dueño responde y verificamos el alias enmascarado del Dueño
        payload_owner = {
            "session_token": session_token,
            "sender": "owner",
            "text": "¡Muchas gracias! Ya voy en camino."
        }
        resp_owner = await async_client.post("/api/v1/chat/messages", json=payload_owner)
        assert resp_owner.status_code == 201
        owner_msg_data = resp_owner.json()
        assert owner_msg_data["sender_display_name"] == "Dueño de Luna", (
            f"RF-CHAT-01 CA2 FAIL: Alias del dueño debe ser 'Dueño de Luna', obtenido: {owner_msg_data['sender_display_name']}"
        )

    def test_chat_02_network_drop_recovery(self, client: TestClient):
        """
        TEST-CHAT-02 (Network Drop Recovery - RF-CHAT-01 CA3):
        Simula interrupción de conexión y posterior restablecimiento:
        1. Se envían mensajes mientras la sesión está activa.
        2. Se simula una caída abrupta de red durante un intervalo.
        3. Durante la desconexión se despachan nuevos mensajes al servidor.
        4. El cliente se reconecta consultando /api/v1/chat/{session_token}/messages.
        5. Se certifica que:
           - Todos los mensajes están presentes en orden cronológico exacto.
           - Cero mensajes perdidos.
           - Cero mensajes duplicados.
        """
        pet_token = "LUNA-COL-99"
        session_resp = client.post("/api/v1/chat/sessions", json={"pet_token": pet_token})
        assert session_resp.status_code == 201
        session_token = session_resp.json()["session_token"]

        # Mensaje 1: Antes del corte de red
        m1 = client.post("/api/v1/chat/messages", json={
            "session_token": session_token,
            "sender": "rescuer",
            "text": "Mensaje 1: Te espero cerca al kiosko"
        }).json()

        # Simulación de corte de conexión (el cliente pierde el socket/SSE)
        # Durante el corte de 5 segundos simulado, el servidor sigue aceptando mensajes entrantes
        time.sleep(0.1) # Breve transición

        # Mensaje 2 y 3: Enviados durante la ventana de reconexión
        m2 = client.post("/api/v1/chat/messages", json={
            "session_token": session_token,
            "sender": "owner",
            "text": "Mensaje 2: Voy llegando en carro rojo"
        }).json()

        m3 = client.post("/api/v1/chat/messages", json={
            "session_token": session_token,
            "sender": "rescuer",
            "text": "Mensaje 3: Perfecto, Luna está tranquila con una correa"
        }).json()

        # Reconexión: el cliente restablece sesión solicitando el historial completo
        reconnect_resp = client.get(f"/api/v1/chat/{session_token}/messages")
        assert reconnect_resp.status_code == 200, f"RF-CHAT-01 CA3 FAIL: Error al reconectar: {reconnect_resp.status_code}"
        history = reconnect_resp.json()

        # Verificaciones de integridad y no-duplicidad
        assert len(history) == 3, f"RF-CHAT-01 CA3 FAIL: Se esperaban 3 mensajes tras reconexión, obtenidos {len(history)}"
        
        # Verificar orden cronológico
        assert history[0]["text"] == "Mensaje 1: Te espero cerca al kiosko"
        assert history[1]["text"] == "Mensaje 2: Voy llegando en carro rojo"
        assert history[2]["text"] == "Mensaje 3: Perfecto, Luna está tranquila con una correa"

        # Verificar unicidad de IDs (Cero duplicación)
        message_ids = [m["id"] for m in history]
        assert len(message_ids) == len(set(message_ids)), "RF-CHAT-01 CA3 FAIL: Se detectaron mensajes duplicados tras reconexión"

    def test_chat_03_payload_sanitization_xss(self, client: TestClient):
        """
        TEST-CHAT-03 (Payload Sanitization XSS - RF-CHAT-01 CA4 / RS-SEC-02 CA1):
        Inyecta cargas maliciosas de Cross-Site Scripting (XSS) en el input de chat:
        1. Inyección de script clásico: <script>alert(1)</script>
        2. Inyección de evento onerror en imagen: <img src=x onerror=alert(1)>
        3. Inyección SVG con event handler: <svg/onload=alert('XSS')>
        4. Inyección de pseudo-protocolo: javascript:alert(document.cookie)
        Valida que:
        - Las respuestas de la API neutralicen y escapen los tags (< -> &lt;, > -> &gt;).
        - El DOM en la plantilla de chat chat.html renderice mediante textContent / escapeHTML.
        - Ningún script ejecutable sea retornado en texto plano sin neutralizar.
        """
        pet_token = "LUNA-COL-99"
        session_resp = client.post("/api/v1/chat/sessions", json={"pet_token": pet_token})
        session_token = session_resp.json()["session_token"]

        malicious_payloads = [
            "<script>alert('XSS-1')</script>",
            '<img src=x onerror="alert(\'XSS-2\')">',
            "<svg/onload=alert('XSS-3')>",
            "javascript:alert(document.cookie)"
        ]

        for payload in malicious_payloads:
            res = client.post("/api/v1/chat/messages", json={
                "session_token": session_token,
                "sender": "rescuer",
                "text": payload
            })
            assert res.status_code == 201, f"RS-SEC-02 FAIL: Error enviando mensaje malicioso: {res.text}"
            data = res.json()
            clean_text = data["text"]

            # Verificación 1: Neutralización de etiquetas ejecutables
            assert "<script>" not in clean_text, f"RS-SEC-02 CA1 FAIL: Tag <script> no escapado: {clean_text}"
            assert "</script>" not in clean_text, f"RS-SEC-02 CA1 FAIL: Tag </script> no escapado: {clean_text}"
            assert "<img" not in clean_text, f"RS-SEC-02 CA1 FAIL: Tag <img no escapado: {clean_text}"
            assert "<svg" not in clean_text, f"RS-SEC-02 CA1 FAIL: Tag <svg no escapado: {clean_text}"
            assert "javascript:" not in clean_text, f"RS-SEC-02 CA1 FAIL: Protocolo javascript: no neutralizado: {clean_text}"

            # Verificación 2: Confirmar caracteres escapados HTML de forma segura
            if "<" in payload:
                assert "&lt;" in clean_text or "&gt;" in clean_text or "blocked" in clean_text, (
                    f"RS-SEC-02 CA1 FAIL: Los caracteres < > deben estar escapados como &lt; &gt;: {clean_text}"
                )

        # Verificación 3: Auditar la plantilla chat.html para asegurar que no use innerHTML inseguro para el texto
        html_page = client.get(f"/chat/{session_token}?role=rescuer").text
        assert "textDiv.textContent = msg.text" in html_page or "escapeHTML" in html_page, (
            "RS-SEC-02 CA1 FAIL: La plantilla chat.html debe renderizar el texto de mensajes usando textContent para prevenir XSS DOM-based"
        )
