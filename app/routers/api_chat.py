import asyncio
import json
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from app.models.chat import (
    ChatSessionCreate,
    ChatSession,
    ChatMessageCreate,
    ChatMessage
)
from app.services.storage import storage
from app.services.chat_service import chat_service

router = APIRouter(prefix="/api/v1/chat", tags=["Chat API"])

@router.post("/sessions", response_model=ChatSession, status_code=status.HTTP_201_CREATED)
async def create_or_get_chat_session(payload: ChatSessionCreate):
    """
    Crea o recupera una sesión de chat efímera y anónima para la placa de la mascota (RF-CHAT-01).
    Garantiza Cero Doxxing: No solicita teléfono, correo ni nombre real al rescatista.
    """
    normalized_token = payload.pet_token.strip().upper()
    session = storage.get_or_create_chat_session(normalized_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placa '{normalized_token}' no encontrada en el sistema."
        )
    return session

@router.get("/sessions/{session_token}", response_model=ChatSession)
async def get_session_info(session_token: str):
    """Obtiene los detalles y el historial de una sesión de chat."""
    session = storage.get_chat_session(session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión de chat no encontrada."
        )
    return session

@router.get("/{session_token}/messages", response_model=list[ChatMessage])
async def get_session_messages(session_token: str):
    """Retorna la lista ordenada de mensajes para sincronización inicial y reconexión."""
    session = storage.get_chat_session(session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión de chat no encontrada."
        )
    return session.messages

@router.post("/messages", response_model=ChatMessage, status_code=status.HTTP_201_CREATED)
async def send_chat_message(payload: ChatMessageCreate):
    """
    Envía un mensaje en la sesión de chat con sanitización XSS estricta y transmisión en tiempo real.
    """
    return await chat_service.post_message(payload)

@router.get("/{session_token}/stream")
async def stream_chat_messages(session_token: str, request: Request):
    """
    Stream Server-Sent Events (SSE) en tiempo real para clientes web y consola (RF-CHAT-01 CA3).
    Mantiene conexión persistente con reconexión automática y difunde nuevos mensajes al instante.
    """
    session = storage.get_chat_session(session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sesión no encontrada."
        )

    queue = await chat_service.register_listener(session_token)

    async def event_generator():
        try:
            # Evento inicial de bienvenida/handshake SSE
            handshake_data = {
                "type": "handshake",
                "session_token": session_token,
                "pet_name": session.pet_name,
                "status": session.status.value,
                "existing_messages_count": len(session.messages)
            }
            yield f"event: handshake\ndata: {json.dumps(handshake_data)}\n\n"
            await asyncio.sleep(0.01)

            while True:
                try:
                    # Esperar siguiente mensaje con timeout para keep-alive ping
                    message: ChatMessage = await asyncio.wait_for(queue.get(), timeout=15.0)
                    msg_dict = message.model_dump(mode="json")
                    yield f"event: message\ndata: {json.dumps(msg_dict)}\n\n"
                    await asyncio.sleep(0.01)
                except asyncio.TimeoutError:
                    # Keep-alive ping para evitar desconexiones de proxies o navegadores
                    yield ": ping\n\n"
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        finally:
            await chat_service.unregister_listener(session_token, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
