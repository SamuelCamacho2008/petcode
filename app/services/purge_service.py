from datetime import datetime, timedelta
from typing import Dict, Any
from app.config import settings
from app.services.storage import storage

class PurgeService:
    """
    Servicio de Purga Automática con TTL de 7 Días (RF-API-01 CA4).
    Garantiza que las coordenadas satelitales exactas y el historial de mensajes
    efímeros no se retengan indefinidamente, protegiendo la privacidad de rescatistas
    y dueños conforme a OWASP y GDPR/privacidad por diseño.
    """

    def __init__(self, ttl_seconds: int = settings.PURGE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds

    def purge_old_data(self, reference_time: datetime = None) -> Dict[str, Any]:
        """
        Ejecuta la purga sobre los registros en el almacenamiento:
        1. Limpia coordenadas exactas (lat/lon a None, exact_coords_purged=True)
           para escaneos con antigüedad mayor al TTL.
        2. Elimina mensajes de chat generados hace más de TTL días.
        """
        now = reference_time or datetime.utcnow()
        cutoff_date = now - timedelta(seconds=self.ttl_seconds)

        purged_scans_count = 0
        purged_messages_count = 0

        with storage.lock:
            # 1. Purga de coordenadas en escaneos
            for scan in storage.scans:
                if scan.created_at < cutoff_date and not scan.exact_coords_purged:
                    # Mantiene el registro estadístico pero disuelve las coordenadas exactas
                    scan.latitude = None
                    scan.longitude = None
                    scan.accuracy = None
                    scan.exact_coords_purged = True
                    purged_scans_count += 1

            # 2. Purga de mensajes de chat efímeros
            for session in storage.chat_sessions.values():
                remaining_messages = []
                for msg in session.messages:
                    if msg.timestamp >= cutoff_date:
                        remaining_messages.append(msg)
                    else:
                        purged_messages_count += 1
                session.messages = remaining_messages

        return {
            "status": "success",
            "cutoff_date": cutoff_date.isoformat(),
            "purged_scans_count": purged_scans_count,
            "purged_messages_count": purged_messages_count
        }

purge_service = PurgeService()
