import time
import threading
from typing import Dict, List, Tuple
from fastapi import HTTPException, status
from app.config import settings

class ScanRateLimiter:
    """
    Limitador de velocidad perimetral para POST /api/v1/scans (RF-API-01 CA2).
    Permite un máximo de 3 solicitudes cada 10 minutos (600 segundos) por tupla (IP, Token).
    La 4ª solicitud genera una excepción HTTP 429 Too Many Requests con cabecera Retry-After.
    """
    def __init__(self, max_requests: int = 3, window_seconds: int = 600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.lock = threading.Lock()
        # Clave: (ip, token) -> Lista de timestamps flotantes en segundos
        self.records: Dict[Tuple[str, str], List[float]] = {}

    def check_and_record(self, ip: str, token: str) -> None:
        """
        Verifica si la combinación (ip, token) ha superado el límite.
        Si lo supera, lanza HTTPException con status 429 y header Retry-After.
        Si no, registra la petición.
        """
        now = time.time()
        key = (ip.strip(), token.strip())
        
        with self.lock:
            # Obtener timestamps previos
            timestamps = self.records.get(key, [])
            
            # Filtrar los que están dentro de la ventana de tiempo
            cutoff = now - self.window_seconds
            valid_timestamps = [ts for ts in timestamps if ts > cutoff]
            
            if len(valid_timestamps) >= self.max_requests:
                # Calcular el tiempo de espera restante hasta que expire el timestamp más viejo
                oldest_in_window = valid_timestamps[0]
                retry_after = max(1, int(oldest_in_window + self.window_seconds - now))
                
                # Actualizar lista limpia antes de rechazar
                self.records[key] = valid_timestamps
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"Máximo {self.max_requests} escaneos cada {self.window_seconds // 60} minutos permitidos para esta placa.",
                        "token": token,
                        "retry_after_seconds": retry_after
                    },
                    headers={"Retry-After": str(retry_after)}
                )
            
            # Registrar nueva petición
            valid_timestamps.append(now)
            self.records[key] = valid_timestamps

    def reset_for_tests(self):
        with self.lock:
            self.records.clear()

scan_rate_limiter = ScanRateLimiter(
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS
)
