import abc
import uuid
from datetime import datetime
from typing import List, Dict, Any
from app.models.dashboard import NotificationLog
from app.models.pet import Pet
from app.models.scan import ScanRecord
from app.services.storage import storage

class NotificationStrategy(abc.ABC):
    """Interfaz base para el Patrón Strategy de Notificaciones."""
    
    @property
    @abc.abstractmethod
    def channel_name(self) -> str:
        pass

    @abc.abstractmethod
    async def send(self, recipient: str, title: str, body: str, metadata: Dict[str, Any]) -> bool:
        """Despacha la notificación al destinatario especificado."""
        pass

class PushNotificationStrategy(NotificationStrategy):
    @property
    def channel_name(self) -> str:
        return "PUSH"

    async def send(self, recipient: str, title: str, body: str, metadata: Dict[str, Any]) -> bool:
        # En producción invocaría WebPush / FCM / APNS
        log_entry = NotificationLog(
            id=str(uuid.uuid4()),
            strategy="PushNotificationStrategy",
            channel=self.channel_name,
            recipient=recipient,
            title=title,
            body=body,
            timestamp=datetime.utcnow()
        )
        storage.add_notification_log(log_entry)
        return True

class EmailNotificationStrategy(NotificationStrategy):
    @property
    def channel_name(self) -> str:
        return "EMAIL"

    async def send(self, recipient: str, title: str, body: str, metadata: Dict[str, Any]) -> bool:
        # En producción invocaría SES / SendGrid / SMTP
        log_entry = NotificationLog(
            id=str(uuid.uuid4()),
            strategy="EmailNotificationStrategy",
            channel=self.channel_name,
            recipient=recipient,
            title=title,
            body=body,
            timestamp=datetime.utcnow()
        )
        storage.add_notification_log(log_entry)
        return True

class SmsNotificationStrategy(NotificationStrategy):
    @property
    def channel_name(self) -> str:
        return "SMS"

    async def send(self, recipient: str, title: str, body: str, metadata: Dict[str, Any]) -> bool:
        # En producción invocaría Twilio / AWS SNS / Telco Gateway
        log_entry = NotificationLog(
            id=str(uuid.uuid4()),
            strategy="SmsNotificationStrategy",
            channel=self.channel_name,
            recipient=recipient,
            title=title,
            body=body,
            timestamp=datetime.utcnow()
        )
        storage.add_notification_log(log_entry)
        return True

class MockNotificationManager:
    """
    Gestor orquestador de estrategias de notificación (Patrón Strategy).
    Desacopla el registro de escaneos de los canales de entrega.
    """
    def __init__(self):
        self.strategies: List[NotificationStrategy] = [
            PushNotificationStrategy(),
            EmailNotificationStrategy(),
            SmsNotificationStrategy()
        ]

    def register_strategy(self, strategy: NotificationStrategy):
        self.strategies.append(strategy)

    async def dispatch_scan_alert(self, pet: Pet, scan: ScanRecord) -> Dict[str, bool]:
        """
        Emite una alerta multicanal inmediata al propietario ante un nuevo escaneo de su mascota.
        """
        location_desc = ""
        if scan.latitude is not None and scan.longitude is not None:
            location_desc = f"Coordenadas GPS: {scan.latitude:.5f}, {scan.longitude:.5f} (Precisión: ±{scan.accuracy or 10:.0f}m)"
        elif scan.manual_address:
            location_desc = f"Dirección reportada: '{scan.manual_address}'"
        else:
            location_desc = "Ubicación satelital no provista por el rescatista"

        title = f"🚨 ¡Alerta de Escaneo! Placa de {pet.name} ({pet.token}) activada"
        body = (
            f"Tu mascota {pet.name} acaba de ser escaneada. {location_desc}. "
            f"Entra de inmediato a tu panel de control para ver el mapa satelital y chatear."
        )

        metadata = {
            "token": pet.token,
            "scan_id": scan.id,
            "latitude": scan.latitude,
            "longitude": scan.longitude,
            "accuracy": scan.accuracy,
            "manual_address": scan.manual_address
        }

        results = {}
        for strategy in self.strategies:
            recipient = ""
            if strategy.channel_name == "EMAIL":
                recipient = pet.owner_private_email
            elif strategy.channel_name == "SMS":
                recipient = pet.owner_private_phone
            elif strategy.channel_name == "PUSH":
                recipient = f"device-token-{pet.token}"

            success = await strategy.send(
                recipient=recipient,
                title=title,
                body=body,
                metadata=metadata
            )
            results[strategy.channel_name] = success

        return results

notification_manager = MockNotificationManager()
