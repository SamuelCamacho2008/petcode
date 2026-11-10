"""
PetCode Automated Test Suite - Anti-Doxxing & Privacy Inspection
IEEE Std 830-1998 Traceability:
- RS-SEC-01: Cero Doxxing / PII Shield (TEST-PRIV-01)
- RF-RES-01: Ficha Pública y Advertencia Médica (CA1, CA2)
"""
import re
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from app.models.pet import Pet, PetStatus
from app.services.storage import storage

class TestPrivacyAndAntiDoxxing:
    """
    Suite de auditoría de seguridad y privacidad: Cero Fuga de Información Personal (Anti-Doxxing).
    OWASP ASVS V4 / GDPR Privacy by Design.
    """

    def test_priv_01_data_leak_inspection_zero_doxxing(self, client: TestClient):
        """
        TEST-PRIV-01 (Data Leak Inspection - Cero Doxxing - RS-SEC-01):
        Inspecciona exhaustivamente el HTML renderizado, comentarios del código fuente,
        atributos DOM, scripts inline y respuestas JSON de los recursos públicos:
        - GET /q/{token}
        - GET /api/v1/pets/public/{token}

        Certifica veredictos booleanos estrictos:
        1. ¿Aparece el teléfono personal del dueño? -> True = FAIL, False = PASS.
        2. ¿Aparece la dirección física familiar de la casa? -> True = FAIL, False = PASS.
        3. ¿Aparece el correo electrónico personal del dueño? -> True = FAIL, False = PASS.
        4. ¿Aparece el teléfono o correo del rescatista? -> True = FAIL, False = PASS.

        Certifica además que la ficha pública expone de forma legítima:
        - Nombre de la mascota, especie, raza y badge médico.
        """
        # Registrar una mascota de prueba con PII intencionalmente sensible y reconocible
        secret_phone = "+57 399 765 4321"
        secret_phone_clean = "3997654321"
        secret_address = "Calle Secreta #99-88 Conjunto Residencial Los Sauces Torre 4 Apto 302"
        secret_email = "propietario_confidencial_petcode@privatemail.org"
        rescuer_mock_email = "rescatista_anonimo@rescatistas.org"
        rescuer_mock_phone = "3129998877"

        test_token = "TEST-SHIELD-01"
        secret_pet = Pet(
            token=test_token,
            name="Thor",
            species="Perro",
            breed="Husky Siberiano",
            photo_url="/static/img/luna.svg",
            status=PetStatus.LOST,
            medical_notes="Cardiopatía congénita — requiere medicación urgente cada 12 horas",
            owner_masked_name="Dueño de Thor",
            owner_private_phone=secret_phone,
            owner_private_address=secret_address,
            owner_private_email=secret_email
        )
        storage.pets[test_token] = secret_pet

        # ----------------------------------------------------------------------
        # FASE 1: Inspección de la Vista HTML Pública (/q/{token})
        # ----------------------------------------------------------------------
        html_resp = client.get(f"/q/{test_token}")
        assert html_resp.status_code == 200, f"RS-SEC-01 FAIL: Error al cargar vista pública: {html_resp.status_code}"
        raw_html = html_resp.text
        soup = BeautifulSoup(raw_html, "html.parser")

        # Remover scripts de análisis para aislar contenido DOM y texto
        all_text = soup.get_text()
        all_comments = soup.find_all(string=lambda text: isinstance(text, type(soup.comment))) if soup.comment else []

        # Certificaciones Booleanas en HTML
        owner_phone_in_html = (
            secret_phone in raw_html or
            secret_phone_clean in raw_html or
            "300 123 4567" in raw_html
        )
        owner_address_in_html = (
            secret_address in raw_html or
            "Los Sauces" in raw_html or
            "Cedritos" in raw_html or
            "Calle 123" in raw_html
        )
        owner_email_in_html = (
            secret_email in raw_html or
            "dueno.luna@example.com" in raw_html
        )
        rescuer_contact_in_html = (
            rescuer_mock_email in raw_html or
            rescuer_mock_phone in raw_html
        )

        assert not owner_phone_in_html, (
            "RS-SEC-01 CA1 FAIL (CRÍTICO): ¡El teléfono personal del dueño fue filtrado en el HTML público de /q/{token}!"
        )
        assert not owner_address_in_html, (
            "RS-SEC-01 CA2 FAIL (CRÍTICO): ¡La dirección domiciliaria privada fue filtrada en el HTML público de /q/{token}!"
        )
        assert not owner_email_in_html, (
            "RS-SEC-01 CA1 FAIL (CRÍTICO): ¡El correo electrónico del dueño fue filtrado en el HTML público de /q/{token}!"
        )
        assert not rescuer_contact_in_html, (
            "RS-SEC-01 CA3 FAIL (CRÍTICO): ¡Datos de contacto del rescatista fueron expuestos en el HTML público!"
        )

        # ----------------------------------------------------------------------
        # FASE 2: Inspección de la API Pública JSON (/api/v1/pets/public/{token})
        # ----------------------------------------------------------------------
        api_resp = client.get(f"/api/v1/pets/public/{test_token}")
        assert api_resp.status_code == 200, f"RF-API-01 FAIL: API pública retornó {api_resp.status_code}"
        json_data = api_resp.json()
        raw_json_str = api_resp.text

        owner_phone_in_json = (
            secret_phone in raw_json_str or
            secret_phone_clean in raw_json_str or
            "owner_private_phone" in json_data
        )
        owner_address_in_json = (
            secret_address in raw_json_str or
            "owner_private_address" in json_data
        )
        owner_email_in_json = (
            secret_email in raw_json_str or
            "owner_private_email" in json_data
        )

        assert not owner_phone_in_json, (
            "RS-SEC-01 CA1 FAIL (CRÍTICO): ¡El teléfono personal del dueño está presente en el JSON de /api/v1/pets/public/{token}!"
        )
        assert not owner_address_in_json, (
            "RS-SEC-01 CA2 FAIL (CRÍTICO): ¡La dirección privada del dueño está presente en el JSON de /api/v1/pets/public/{token}!"
        )
        assert not owner_email_in_json, (
            "RS-SEC-01 CA1 FAIL (CRÍTICO): ¡El correo privado del dueño está presente en el JSON de /api/v1/pets/public/{token}!"
        )

        # ----------------------------------------------------------------------
        # FASE 3: Certificación de Datos Públicos Legítimos (RF-RES-01 CA1/CA2)
        # ----------------------------------------------------------------------
        assert json_data["name"] == "Thor", "RF-RES-01 CA1 FAIL: Nombre de mascota incorrecto"
        assert json_data["species"] == "Perro", "RF-RES-01 CA1 FAIL: Especie incorrecta"
        assert json_data["breed"] == "Husky Siberiano", "RF-RES-01 CA1 FAIL: Raza incorrecta"
        assert json_data["owner_masked_name"] == "Dueño de Thor", "RF-RES-01 CA1 FAIL: Alias enmascarado incorrecto"
        assert "Cardiopatía congénita" in json_data["medical_notes"], "RF-RES-01 CA2 FAIL: Advertencia médica ausente en JSON"

        # Validar que el badge médico y el estado aparezcan en el HTML
        assert "Thor" in raw_html, "RF-RES-01 CA1 FAIL: Nombre no renderizado en HTML"
        assert "Cardiopatía congénita" in raw_html, "RF-RES-01 CA2 FAIL: Advertencia médica no renderizada en HTML"
        assert "MODO MASCOTA PERDIDA" in raw_html, "RF-RES-01 CA1 FAIL: Estado de alerta perdido no visible en HTML"
