import threading
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.models.pet import Pet, PetStatus, PetPublic, PetCreate
from app.models.scan import ScanRecord
from app.models.chat import ChatSession, ChatMessage, ChatSessionStatus
from app.models.dashboard import NotificationLog

class PetCodeStorage:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(PetCodeStorage, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.lock = threading.Lock()
        self.pets: Dict[str, Pet] = {}
        self.scans: List[ScanRecord] = []
        self.chat_sessions: Dict[str, ChatSession] = {}
        self.notifications: List[NotificationLog] = []
        self._seed_data()
        self._initialized = True

    def _seed_data(self):
        # 1. Semilla Luna (Estado: LOST)
        luna = Pet(
            token="LUNA-COL-99",
            name="Luna",
            species="Perro",
            breed="Golden Retriever",
            photo_url="/static/img/luna.svg",
            status=PetStatus.LOST,
            medical_notes="Requiere insulina diaria - Alérgica a granos",
            owner_masked_name="Dueño de Luna",
            owner_private_phone="+57 300 123 4567",
            owner_private_address="Calle 123 #45-67, Cedritos, Bogotá",
            owner_private_email="dueno.luna@example.com",
            created_at=datetime.utcnow() - timedelta(days=2),
            updated_at=datetime.utcnow() - timedelta(hours=1)
        )
        self.pets[luna.token] = luna

        # 2. Semilla Max (Estado: AT_HOME)
        max_pet = Pet(
            token="MAX-COL-42",
            name="Max",
            species="Gato",
            breed="Siamés",
            photo_url="/static/img/max.svg",
            status=PetStatus.AT_HOME,
            medical_notes="Ninguna",
            owner_masked_name="Dueño de Max",
            owner_private_phone="+57 311 987 6543",
            owner_private_address="Carrera 7 #88-12, Poblado, Medellín",
            owner_private_email="dueno.max@example.com",
            created_at=datetime.utcnow() - timedelta(days=10),
            updated_at=datetime.utcnow() - timedelta(days=1)
        )
        self.pets[max_pet.token] = max_pet

        # Escaneo inicial para Luna para visualizar en el Geovisor Leaflet
        initial_scan = ScanRecord(
            id=str(uuid.uuid4()),
            token="LUNA-COL-99",
            latitude=4.698300,
            longitude=-74.045000,
            accuracy=35.0,
            manual_address=None,
            ip_address="190.25.10.4",
            created_at=datetime.utcnow() - timedelta(minutes=45)
        )
        self.scans.append(initial_scan)

    # --- Métodos de Mascotas ---
    def get_pet(self, token: str) -> Optional[Pet]:
        with self.lock:
            return self.pets.get(token)

    def get_pet_public(self, token: str) -> Optional[PetPublic]:
        with self.lock:
            pet = self.pets.get(token)
            if pet:
                return pet.to_public()
            return None

    def update_pet_status(self, token: str, status: PetStatus) -> Optional[Pet]:
        with self.lock:
            pet = self.pets.get(token)
            if pet:
                pet.status = status
                pet.updated_at = datetime.utcnow()
                return pet

    def create_pet(self, data: PetCreate) -> Pet:
        """
        Registra una nueva mascota y su propietario con token y placa únicos.
        """
        with self.lock:
            clean_name = "".join(c for c in data.pet_name.upper() if c.isalnum())[:4]
            if not clean_name:
                clean_name = "PET"
            rand_suffix = uuid.uuid4().hex[:4].upper()
            token = f"{clean_name}-COL-{rand_suffix}"

            masked_owner = f"Dueño de {data.pet_name}"

            new_pet = Pet(
                token=token,
                name=data.pet_name,
                species=data.species,
                breed=data.breed,
                photo_url=data.photo_url or "/static/img/luna.svg",
                status=data.status,
                medical_notes=data.medical_notes or "Ninguna",
                owner_masked_name=masked_owner,
                owner_private_phone=data.owner_phone or "+57 300 000 0000",
                owner_private_address=data.owner_address or "Confidencial",
                owner_private_email=data.owner_email or f"{data.owner_name.lower().replace(' ', '')}@example.com",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.pets[token] = new_pet
            return new_pet
            return None

    # --- Métodos de Escaneos ---
    def add_scan(self, scan: ScanRecord) -> ScanRecord:
        with self.lock:
            self.scans.append(scan)
            return scan

    def get_scans_for_pet(self, token: str, limit: int = 50) -> List[ScanRecord]:
        with self.lock:
            matched = [s for s in self.scans if s.token == token]
            matched.sort(key=lambda s: s.created_at, reverse=True)
            return matched[:limit]

    # --- Métodos de Sesiones de Chat ---
    def get_or_create_chat_session(self, pet_token: str) -> Optional[ChatSession]:
        with self.lock:
            pet = self.pets.get(pet_token)
            if not pet:
                return None
            
            # Buscar si ya existe una sesión activa para esta mascota
            for session in self.chat_sessions.values():
                if session.pet_token == pet_token and session.status == ChatSessionStatus.ACTIVE:
                    return session
            
            # Crear nueva sesión efímera
            session_token = uuid.uuid4().hex
            session = ChatSession(
                id=str(uuid.uuid4()),
                session_token=session_token,
                pet_token=pet.token,
                pet_name=pet.name,
                status=ChatSessionStatus.ACTIVE,
                rescuer_alias="Rescatista",
                owner_alias=f"Dueño de {pet.name}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                messages=[]
            )
            self.chat_sessions[session_token] = session
            return session

    def get_chat_session(self, session_token: str) -> Optional[ChatSession]:
        with self.lock:
            return self.chat_sessions.get(session_token)

    def get_active_sessions_for_pet(self, pet_token: str) -> List[ChatSession]:
        with self.lock:
            return [
                s for s in self.chat_sessions.values()
                if s.pet_token == pet_token and s.status == ChatSessionStatus.ACTIVE
            ]

    def add_message_to_session(self, message: ChatMessage) -> Optional[ChatSession]:
        with self.lock:
            session = self.chat_sessions.get(message.session_token)
            if session:
                session.messages.append(message)
                session.updated_at = datetime.utcnow()
                return session
            return None

    def archive_sessions_for_pet(self, pet_token: str) -> int:
        with self.lock:
            count = 0
            for session in self.chat_sessions.values():
                if session.pet_token == pet_token and session.status == ChatSessionStatus.ACTIVE:
                    session.status = ChatSessionStatus.ARCHIVED
                    session.updated_at = datetime.utcnow()
                    count += 1
            return count

    # --- Notificaciones ---
    def add_notification_log(self, log: NotificationLog):
        with self.lock:
            self.notifications.append(log)

    def get_notifications_for_pet(self, pet_token: str, limit: int = 20) -> List[NotificationLog]:
        with self.lock:
            # Filtra las notificaciones por pet_token si está en el cuerpo o título
            matched = [
                n for n in self.notifications
                if pet_token in n.body or pet_token in n.title
            ]
            matched.sort(key=lambda n: n.timestamp, reverse=True)
            return matched[:limit]

    def reset_for_tests(self):
        with self.lock:
            self.pets.clear()
            self.scans.clear()
            self.chat_sessions.clear()
            self.notifications.clear()
            self._seed_data()

storage = PetCodeStorage()
