"""
Fixture configuration for PetCode Test Suite.
IEEE Std 830-1998 & OWASP ASVS Compliance Suite.
"""
import pytest
import asyncio
import typing
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
import httpx
from httpx import ASGITransport

from app.main import app
from app.services.storage import storage
from app.services.rate_limiter import scan_rate_limiter

@pytest.fixture(autouse=True)
def reset_system_state():
    """
    Restaura el estado del almacenamiento en memoria y los contadores
    de Rate Limiting antes de cada prueba para garantizar aislamiento total.
    """
    storage.reset_for_tests()
    scan_rate_limiter.reset_for_tests()
    yield
    storage.reset_for_tests()
    scan_rate_limiter.reset_for_tests()

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """
    Cliente sincrónico de Starlette/FastAPI para pruebas de endpoints y vistas.
    """
    with TestClient(app) as test_client:
        yield test_client

class StreamingASGITransport(ASGITransport):
    """
    Transporte ASGI adaptado para soportar Streaming continuo en tiempo real (SSE).
    """
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        assert isinstance(request.stream, httpx.AsyncByteStream)
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": request.method,
            "headers": [(k.lower(), v) for (k, v) in request.headers.raw],
            "scheme": request.url.scheme,
            "path": request.url.path,
            "raw_path": request.url.raw_path.split(b"?")[0],
            "query_string": request.url.query,
            "server": (request.url.host, request.url.port),
            "client": self.client,
            "root_path": self.root_path,
        }

        request_body_chunks = request.stream.__aiter__()
        request_complete = False

        status_code = None
        response_headers = None
        started_event = asyncio.Event()
        disconnect_event = asyncio.Event()
        body_queue = asyncio.Queue()

        async def receive() -> dict[str, typing.Any]:
            nonlocal request_complete
            if request_complete:
                await disconnect_event.wait()
                return {"type": "http.disconnect"}
            try:
                body = await request_body_chunks.__anext__()
            except StopAsyncIteration:
                request_complete = True
                return {"type": "http.request", "body": b"", "more_body": False}
            return {"type": "http.request", "body": body, "more_body": True}

        async def send(message: typing.MutableMapping[str, typing.Any]) -> None:
            nonlocal status_code, response_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = message.get("headers", [])
                started_event.set()
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if body:
                    await body_queue.put(body)
                if not more_body:
                    await body_queue.put(None)

        app_task = asyncio.create_task(self.app(scope, receive, send))
        await started_event.wait()

        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self):
                while True:
                    chunk = await body_queue.get()
                    if chunk is None:
                        break
                    yield chunk

            async def aclose(self):
                disconnect_event.set()
                app_task.cancel()
                try:
                    await app_task
                except asyncio.CancelledError:
                    pass

        class ResettableResponse(httpx.Response):
            @property
            def is_stream_consumed(self) -> bool:
                return False

            @is_stream_consumed.setter
            def is_stream_consumed(self, value: bool) -> None:
                pass

        return ResettableResponse(status_code, headers=response_headers, stream=Stream())

@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Cliente asíncrono httpx para pruebas de concurrencia, streams SSE y latencia.
    """
    transport = StreamingASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
