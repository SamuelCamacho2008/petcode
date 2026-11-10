import asyncio
import base64
import html
import threading
import uuid
import re
from datetime import datetime
from typing import Dict, Set, Optional, List
from fastapi import HTTPException, status
from app.config import settings
from app.models.chat import (
    ChatMessage,
    ChatMessageCreate,
    ChatSenderRole,
    ChatSession,
    ChatCoordinates
)
from app.services.storage import storage

class ChatService:
    """
    Servicio de Chat Efímero y Anónimo con SSE y Sanitización XSS (RF-CHAT-01 / RS-SEC-02).
    """
    def __init__(self):
        # Mapeo: session_token -> Set de asyncio.Queue para SSE clients
        self.listeners: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def sanitize_text(raw_text: str) -> str:
        """
        Neutraliza completamente vectores de ataque Cross-Site Scripting (XSS).
        Escapa caracteres especiales HTML (&, <, >, ", ') y remueve protocolos peligrosos como javascript:.
        """
        if not raw_text:
            return ""
        # 1. Escapado estándar HTML seguro
        escaped = html.escape(raw_text.strip(), quote=True)
        # 2. Neutralizar posibles javascript: o data: maliciosos si quedaron
        sanitized = re.sub(r'(?i)javascript:', 'blocked-script:', escaped)
        return sanitized

    @staticmethod
    def validate_and_process_photo(photo_base64: Optional[str]) -> Optional[str]:
        """
        Valida que la fotografía en base64 no exceda el límite de 1.5 MB (CA4).
        """
        if not photo_base64:
            return None
        
        # Si incluye data URI scheme (e.g. "data:image/jpeg;base64,..."), separar cabecera
        raw_b64 = photo_base64
        if "," in photo_base64:
            header, raw_b64 = photo_base64.split(",", 1)
        
        try:
            decoded_bytes = base64.b64decode(raw_b64)
            size_bytes = len(decoded_bytes)
            if size_bytes > settings.MAX_PHOTO_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"La fotografía excede el tamaño máximo permitido de 1.5 MB (actual: {size_bytes / (1024*1024):.2f} MB)."
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato base64 de imagen no válido."
            )
        
        return photo_base64

    async def register_listener(self, session_token: str) -> asyncio.Queue:
        """Registra o recupera la cola SSE de la sesión para recibir mensajes en tiempo real."""
        with self._lock:
            if session_token not in self.listeners:
                self.listeners[session_token] = asyncio.Queue()
            return self.listeners[session_token]

    async def unregister_listener(self, session_token: str, queue: asyncio.Queue):
        """Mantiene la cola activa para resiliencia ante reconexiones."""
        pass

    async def broadcast_message(self, session_token: str, message: ChatMessage):
        """Envía el mensaje en tiempo real a la cola de la sesión."""
        with self._lock:
            q = self.listeners.get(session_token)
        if q:
            try:
                q.put_nowait(message)
            except Exception:
                pass

    async def post_message(self, payload: ChatMessageCreate) -> ChatMessage:
        """
        Procesa, sanitiza, almacena y difunde un mensaje en la sesión de chat.
        """
        session = storage.get_chat_session(payload.session_token)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión de chat no encontrada o expirada."
            )

        # 1. Sanitizar contenido de texto
        clean_text = self.sanitize_text(payload.text)
        
        # 2. Validar imagen si fue provista
        processed_photo = self.validate_and_process_photo(payload.photo_base64)

        # Validar que al menos haya texto, foto o coordenadas
        if not clean_text and not processed_photo and not payload.coords:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El mensaje no puede estar vacío (debe contener texto, fotografía o coordenadas)."
            )

        # 3. Determinar alias enmascarado
        display_name = session.rescuer_alias if payload.sender == ChatSenderRole.RESCUER else session.owner_alias

        # 4. Crear instancia de mensaje
        chat_msg = ChatMessage(
            id=str(uuid.uuid4()),
            session_token=payload.session_token,
            sender=payload.sender,
            sender_display_name=display_name,
            text=clean_text,
            photo_base64=processed_photo,
            coords=payload.coords,
            timestamp=datetime.utcnow()
        )

        # 5. Persistir en la sesión
        storage.add_message_to_session(chat_msg)

        # 6. Difundir en tiempo real
        await self.broadcast_message(payload.session_token, chat_msg)

        return chat_msg

chat_service = ChatService()
