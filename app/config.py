import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "PetCode"
    APP_TITLE: str = "PetCode — Sistema Inteligente de Identificación y Rescate de Mascotas"
    APP_VERSION: str = "1.0.0-RELEASE"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    # Rate Limiting: Máximo 3 peticiones POST /api/v1/scans cada 10 minutos (600s) por (IP + token)
    RATE_LIMIT_MAX_REQUESTS: int = 3
    RATE_LIMIT_WINDOW_SECONDS: int = 600
    
    # TTL de purga automática de coordenadas y mensajes (7 días = 604800 segundos)
    PURGE_TTL_SECONDS: int = 7 * 86400
    
    # Límite de tamaño de fotos en chat (1.5 MB en bytes)
    MAX_PHOTO_SIZE_BYTES: int = 1572864

    class Config:
        env_prefix = "PETCODE_"

settings = Settings()
