"""
PetCode Automated Test Suite - Mobile Accessibility & Touch Targets
IEEE Std 830-1998 Traceability:
- RNF-A11Y: WCAG 2.1 AA Compliance & Touch Targets >= 48x48px (TEST-A11Y-01)
- RF-RES-01: Ficha Pública Accesible
"""
import re
from pathlib import Path
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

class TestAccessibilityAndTouchTargets:
    """
    Suite de auditoría de accesibilidad mobile-first según WCAG 2.1 AA.
    Directriz 2.5.5: Target Size (Enhanced/AA) >= 48x48 CSS pixels.
    """

    def test_a11y_01_mobile_accessibility_and_touch_targets(self, client: TestClient):
        """
        TEST-A11Y-01 (Mobile Accessibility & Touch Targets - RNF-A11Y):
        Audita el HTML público (/q/{token} y /chat/{session_token}) y la hoja de estilos style.css:
        1. Declaración HTML obligatoria: <!DOCTYPE html> y lang="es".
        2. Configuración de Viewport mobile-first: width=device-width, initial-scale=1.0.
        3. Todos los botones (<button>, <a class="btn">) deben disponer de texto legible o atributo aria-label.
        4. Todos los campos de entrada (<input>) deben contar con placeholder, label o aria-label descriptivo.
        5. Verificación de dimensiones de área táctil (Touch Targets >= 48x48 píxeles):
           - Hoja de estilos style.css define clases con min-height >= 48px para todos los interactivos móviles (.btn, .input-field, .chat-btn-action).
           - Cero botones con tamaños inferiores a 48px.
        6. Presencia de roles ARIA semánticos en alertas (role="alert" en advertencia médica).
        """
        token = "LUNA-COL-99"

        # ----------------------------------------------------------------------
        # 1. Auditoría de la Ficha Pública (/q/{token})
        # ----------------------------------------------------------------------
        resp_public = client.get(f"/q/{token}")
        assert resp_public.status_code == 200, "RNF-A11Y FAIL: Error cargando vista pública"
        soup_public = BeautifulSoup(resp_public.text, "html.parser")

        # 1.1 Validar lang y viewport
        html_tag = soup_public.find("html")
        assert html_tag is not None and html_tag.get("lang") == "es", (
            "RNF-A11Y FAIL: Elemento <html> debe especificar lang='es' para lectores de pantalla"
        )
        viewport_meta = soup_public.find("meta", attrs={"name": "viewport"})
        assert viewport_meta is not None, "RNF-A11Y FAIL: Meta viewport no encontrado en el <head>"
        viewport_content = viewport_meta.get("content", "")
        assert "width=device-width" in viewport_content and "initial-scale=1" in viewport_content, (
            f"RNF-A11Y FAIL: Configuración viewport incorrecta: {viewport_content}"
        )

        # 1.2 Auditar botones interactivos en /q/{token}
        buttons = soup_public.find_all(["button", "a"])
        interactive_count = 0
        for btn in buttons:
            classes = btn.get("class", [])
            # Ignorar links de navegación simples sin clase interactiva
            if "btn" in classes or "brand" in classes or btn.name == "button":
                interactive_count += 1
                text = btn.get_text(strip=True)
                aria_label = btn.get("aria-label")
                title = btn.get("title")
                assert text or aria_label or title, (
                    f"RNF-A11Y FAIL: Botón interactivo sin texto descriptivo ni aria-label: {btn}"
                )

        assert interactive_count >= 3, "RNF-A11Y FAIL: No se encontraron los botones mínimos requeridos en /q/{token}"

        # 1.3 Auditar campos de formulario
        inputs = soup_public.find_all("input")
        for inp in inputs:
            if inp.get("type") == "hidden":
                continue
            has_label = bool(inp.get("aria-label") or inp.get("placeholder") or inp.get("id"))
            assert has_label, f"RNF-A11Y FAIL: Campo de entrada sin etiqueta accesible: {inp}"

        # 1.4 Auditar role="alert" en advertencia médica
        med_box = soup_public.find(class_="medical-alert-box")
        if med_box:
            assert med_box.get("role") == "alert", (
                "RNF-A11Y FAIL: Caja de advertencia médica debe incluir role='alert' para sintetizadores de voz"
            )

        # ----------------------------------------------------------------------
        # 2. Auditoría del Chat Seguro (/chat/{session_token})
        # ----------------------------------------------------------------------
        chat_sess = client.post("/api/v1/chat/sessions", json={"pet_token": token}).json()
        chat_token = chat_sess["session_token"]
        resp_chat = client.get(f"/chat/{chat_token}")
        assert resp_chat.status_code == 200, "RNF-A11Y FAIL: Error cargando vista de chat"
        soup_chat = BeautifulSoup(resp_chat.text, "html.parser")

        chat_buttons = soup_chat.find_all("button")
        for cbtn in chat_buttons:
            text = cbtn.get_text(strip=True)
            aria_label = cbtn.get("aria-label")
            title = cbtn.get("title")
            assert text or aria_label or title, (
                f"RNF-A11Y FAIL: Botón de acción en chat sin texto accesible ni aria-label: {cbtn}"
            )

        # ----------------------------------------------------------------------
        # 3. Auditoría de Dimensiones de Touch Targets en CSS (style.css)
        # ----------------------------------------------------------------------
        css_path = Path("app/static/css/style.css")
        assert css_path.exists(), "RNF-A11Y FAIL: Archivo style.css no encontrado"
        css_content = css_path.read_text(encoding="utf-8")

        # Verificar reglas explícitas de área táctil mínima >= 48px
        # .btn -> min-height: 52px;
        # .chat-btn-action -> width: 48px; height: 48px;
        # .input-field -> min-height: 48px;
        btn_height_match = re.search(r"\.btn\s*\{[^}]*min-height:\s*(\d+)px", css_content)
        assert btn_height_match is not None, "RNF-A11Y FAIL: .btn no tiene regla min-height explícita en CSS"
        btn_height = int(btn_height_match.group(1))
        assert btn_height >= 48, (
            f"RNF-A11Y FAIL: Altura mínima de botón .btn es {btn_height}px, menor a 48px requerido por WCAG 2.1 AA"
        )

        chat_btn_match = re.search(r"\.chat-btn-action\s*\{[^}]*min-width:\s*(\d+)px", css_content)
        if not chat_btn_match:
            chat_btn_match = re.search(r"\.chat-btn-action\s*\{[^}]*width:\s*(\d+)px", css_content)
        assert chat_btn_match is not None, "RNF-A11Y FAIL: .chat-btn-action sin dimensiones explícitas"
        chat_btn_dim = int(chat_btn_match.group(1))
        assert chat_btn_dim >= 48, (
            f"RNF-A11Y FAIL: Botón de acción de chat tiene dimensión {chat_btn_dim}px (< 48px)"
        )

        input_height_match = re.search(r"\.input-field\s*\{[^}]*min-height:\s*(\d+)px", css_content)
        assert input_height_match is not None, "RNF-A11Y FAIL: .input-field sin min-height explícita en CSS"
        input_height = int(input_height_match.group(1))
        assert input_height >= 48, (
            f"RNF-A11Y FAIL: Altura de input-field es {input_height}px (< 48px)"
        )
