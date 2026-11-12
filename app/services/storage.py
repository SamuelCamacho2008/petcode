import threading
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.models.pet import Pet, PetStatus, PetPublic, PetCreate
from app.models.scan import ScanRecord
from app.models.chat import ChatSession, ChatMessage, ChatSessionStatus
from app.models.dashboard import NotificationLog
from app.models.account import User, UserRole, ADMIN_EMAIL
from app.models.payment import RewardPayment, PaymentStatus

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
        self.users: Dict[str, User] = {}
        self.pets: Dict[str, Pet] = {}
        self.scans: List[ScanRecord] = []
        self.chat_sessions: Dict[str, ChatSession] = {}
        self.notifications: List[NotificationLog] = []
        self.payments: Dict[str, RewardPayment] = {}
        self._seed_data()
        self._initialized = True

    def _seed_data(self):
        # 0. Semilla Usuarios (Admin y Propietario)
        admin_user = User.create(
            email=ADMIN_EMAIL,
            name="Samuel Camacho (Admin)",
            phone="+57 300 123 4567",
            address="Bogotá, Colombia"
        )
        self.users[admin_user.email] = admin_user

        carlos_user = User.create(
            email="dueno.max@example.com",
            name="Carlos Gómez",
            phone="+57 311 987 6543",
            address="Carrera 7 #88-12, Poblado, Medellín"
        )
        self.users[carlos_user.email] = carlos_user

        # 1. Semilla Luna (Estado: LOST, Mascota de Samuel con Recompensa)
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
            owner_private_email=ADMIN_EMAIL,
            reward_amount=150000.0,
            reward_active=True,
            created_at=datetime.utcnow() - timedelta(days=2),
            updated_at=datetime.utcnow() - timedelta(hours=1)
        )
        self.pets[luna.token] = luna

        # 2. Semilla Max (Estado: AT_HOME, Mascota de Carlos)
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
            reward_amount=0.0,
            reward_active=False,
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

        # Historial de pago previo liberado para mostrar estadísticas de ganancias al Admin Samuel
        past_payment_id = "pay-hist-002"
        past_payment = RewardPayment(
            id=past_payment_id,
            pet_token="PAST-DOG-01",
            pet_name="Rocky",
            session_token="sess-past-02",
            owner_email="otro.dueno@example.com",
            owner_masked_name="Dueño de Rocky",
            rescuer_alias="Rescatista Camilo",
            total_reward=200000.0,
            platform_fee=10000.0,
            rescuer_payout=190000.0,
            status=PaymentStatus.RELEASED,
            created_at=datetime.utcnow() - timedelta(days=3),
            released_at=datetime.utcnow() - timedelta(days=2)
        )
        self.payments[past_payment_id] = past_payment

    # --- Métodos de Usuarios y Autenticación ---
    def get_or_create_user(self, email: str, name: str = "", phone: str = "", address: str = "") -> User:
        with self.lock:
            clean_email = email.strip().lower()
            if clean_email not in self.users:
                user = User.create(
                    email=clean_email,
                    name=name or clean_email.split("@")[0].capitalize(),
                    phone=phone,
                    address=address
                )
                self.users[clean_email] = user
            return self.users[clean_email]

    def get_user(self, email: str) -> Optional[User]:
        with self.lock:
            clean_email = email.strip().lower()
            return self.users.get(clean_email)

    def update_user(self, email: str, name: Optional[str] = None, phone: Optional[str] = None, address: Optional[str] = None) -> Optional[User]:
        with self.lock:
            clean_email = email.strip().lower()
            user = self.users.get(clean_email)
            if user:
                if name is not None:
                    user.name = name.strip()
                if phone is not None:
                    user.phone = phone.strip()
                if address is not None:
                    user.address = address.strip()
                return user
            return None

    # --- Métodos de Mascotas Filtrados por Usuario ---
    def get_pet(self, token: str) -> Optional[Pet]:
        with self.lock:
            return self.pets.get(token)

    def get_pets_for_user(self, email: str) -> List[Pet]:
        with self.lock:
            clean_email = email.strip().lower()
            return [
                p for p in self.pets.values()
                if p.owner_private_email.strip().lower() == clean_email
            ]

    def get_pet_public(self, token: str) -> Optional[PetPublic]:
        with self.lock:
            pet = self.pets.get(token)
            if pet:
                return pet.to_public()
            return None

    def update_pet_status(self, token: str, status: PetStatus, reward_amount: Optional[float] = None) -> Optional[Pet]:
        with self.lock:
            pet = self.pets.get(token)
            if pet:
                pet.status = status
                if status == PetStatus.LOST:
                    if reward_amount is not None:
                        pet.reward_amount = max(0.0, float(reward_amount))
                        pet.reward_active = pet.reward_amount > 0
                else:
                    pet.reward_active = False
                pet.updated_at = datetime.utcnow()
                return pet
            return None

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
            owner_email = data.owner_email.strip().lower() if data.owner_email else f"{data.owner_name.lower().replace(' ', '')}@example.com"

            # Asegurar existencia del usuario
            if owner_email not in self.users:
                self.users[owner_email] = User.create(
                    email=owner_email,
                    name=data.owner_name,
                    phone=data.owner_phone or "+57 300 000 0000",
                    address=data.owner_address or "Confidencial"
                )

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
                owner_private_email=owner_email,
                reward_amount=data.reward_amount or 0.0,
                reward_active=(data.status == PetStatus.LOST and (data.reward_amount or 0.0) > 0),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.pets[token] = new_pet
            return new_pet

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

    # --- Métodos de Sesiones de Chat (Con Aislamiento Estricto de Privacidad) ---
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
            reward_amt = pet.reward_amount if pet.reward_active else 0.0
            reward_st = "ESCROW" if pet.reward_active and reward_amt > 0 else "NONE"
            payment_id = None

            # Si hay recompensa activa, crear registro de pago en custodia automáticamente
            if reward_st == "ESCROW":
                payment_id = f"pay-{uuid.uuid4().hex[:8]}"
                fee = round(reward_amt * 0.05, 2)
                payout = round(reward_amt * 0.95, 2)
                payment = RewardPayment(
                    id=payment_id,
                    pet_token=pet.token,
                    pet_name=pet.name,
                    session_token=session_token,
                    owner_email=pet.owner_private_email,
                    owner_masked_name=pet.owner_masked_name,
                    rescuer_alias="Rescatista",
                    total_reward=reward_amt,
                    platform_fee=fee,
                    rescuer_payout=payout,
                    status=PaymentStatus.ESCROW
                )
                self.payments[payment_id] = payment

            session = ChatSession(
                id=str(uuid.uuid4()),
                session_token=session_token,
                pet_token=pet.token,
                pet_name=pet.name,
                status=ChatSessionStatus.ACTIVE,
                rescuer_alias="Rescatista",
                owner_alias=pet.owner_masked_name,
                reward_amount=reward_amt,
                reward_status=reward_st,
                payment_id=payment_id,
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

    def get_chat_sessions_for_user(self, email: str) -> List[ChatSession]:
        """
        Garantiza que sólo se retornen chats pertenecientes a mascotas del usuario logueado.
        Ninguna otra persona puede ver estas conversaciones ni sus avisos de chat.
        """
        with self.lock:
            clean_email = email.strip().lower()
            user_pet_tokens = {
                p.token for p in self.pets.values()
                if p.owner_private_email.strip().lower() == clean_email
            }
            return [
                s for s in self.chat_sessions.values()
                if s.pet_token in user_pet_tokens and s.status == ChatSessionStatus.ACTIVE
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

    # --- Métodos de Pagos y Recompensas (5% PetCode, 95% Rescatista) ---
    def record_payment(self, payment: RewardPayment):
        with self.lock:
            self.payments[payment.id] = payment

    def get_payment(self, payment_id: str) -> Optional[RewardPayment]:
        with self.lock:
            return self.payments.get(payment_id)

    def get_payment_for_session(self, session_token: str) -> Optional[RewardPayment]:
        with self.lock:
            for p in self.payments.values():
                if p.session_token == session_token:
                    return p
            return None

    def release_reward(self, session_token: str) -> Optional[RewardPayment]:
        """
        Libera la recompensa en custodia para el rescatista.
        Descuenta el 5% de ganancia para PetCode y el 95% para el rescatista.
        """
        with self.lock:
            payment = None
            for p in self.payments.values():
                if p.session_token == session_token and p.status == PaymentStatus.ESCROW:
                    payment = p
                    break
            
            if not payment:
                return None
            
            payment.status = PaymentStatus.RELEASED
            payment.released_at = datetime.utcnow()

            # Actualizar estado de la sesión de chat
            session = self.chat_sessions.get(session_token)
            if session:
                session.reward_status = "RELEASED"
                session.updated_at = datetime.utcnow()

            return payment

    def get_all_payments(self) -> List[RewardPayment]:
        with self.lock:
            payments_list = list(self.payments.values())
            payments_list.sort(key=lambda p: p.created_at, reverse=True)
            return payments_list

    # --- Notificaciones ---
    def add_notification_log(self, log: NotificationLog):
        with self.lock:
            self.notifications.append(log)

    def get_notifications_for_pet(self, pet_token: str, limit: int = 20) -> List[NotificationLog]:
        with self.lock:
            matched = [
                n for n in self.notifications
                if pet_token in n.body or pet_token in n.title
            ]
            matched.sort(key=lambda n: n.timestamp, reverse=True)
            return matched[:limit]

    def reset_for_tests(self):
        with self.lock:
            self.users.clear()
            self.pets.clear()
            self.scans.clear()
            self.chat_sessions.clear()
            self.notifications.clear()
            self.payments.clear()
            self._seed_data()

storage = PetCodeStorage()
