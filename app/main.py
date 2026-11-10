import os
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.services.purge_service import purge_service
from app.routers import (
    public_views,
    api_pets,
    api_scans,
    api_chat,
    api_dashboard
)

# Worker en hilo daemon para no interferir con AnyIO ni con TestClient
def background_purge_worker():
    while True:
        try:
            time.sleep(6 * 3600)
            result = purge_service.purge_old_data()
            print(f"[PURGE-WORKER] Purga ejecutada: {result}")
        except Exception as e:
            print(f"[PURGE-WORKER] Error en purga: {e}")
            time.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Iniciar hilo de purga daemon solo en ejecución normal (no en tests)
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        purge_thread = threading.Thread(target=background_purge_worker, daemon=True)
        purge_thread.start()
    yield

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Configuración CORS abierta para desarrollo y clientes móviles
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos (CSS, JS, imágenes SVG)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Registrar Routers de la Solución
app.include_router(public_views.router)
app.include_router(api_pets.router)
app.include_router(api_scans.router)
app.include_router(api_chat.router)
app.include_router(api_dashboard.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
