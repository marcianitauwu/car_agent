"""Limites por IP en un solo proceso; configurables para la demo local.

En producción usar Redis/API Management y autenticación. Un limite de peticiones
no es un limite monetario de Azure.
"""
import asyncio
import math
from collections import defaultdict, deque
from time import monotonic

from app.core.config import setting


def positive_int_setting(name: str, default: int, maximum: int) -> int:
    value = int(setting(name, str(default)))
    if not 1 <= value <= maximum:
        raise ValueError(f"{name} debe estar entre 1 y {maximum}")
    return value


class LocalRateLimiter:
    def __init__(self, per_minute: int = 30):
        if per_minute < 1:
            raise ValueError('per_minute debe ser mayor que cero')
        self.per_minute = per_minute
        self._events = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._last_cleanup = monotonic()

    async def check(self, client_id: str) -> tuple[bool, int]:
        """Devuelve (permitido, segundos para volver a intentar)."""
        now = monotonic()
        async with self._lock:
            if now - self._last_cleanup > 180:
                for key in list(self._events):
                    if not self._events[key] or self._events[key][-1] <= now - 60:
                        self._events.pop(key, None)
                self._last_cleanup = now
            recent = self._events[client_id]
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= self.per_minute:
                return False, max(1, math.ceil(recent[0] + 60 - now))
            recent.append(now)
            return True, 0

    async def allow(self, client_id: str) -> bool:
        # Mantener compatibilidad con las pruebas existentes.
        allowed, _ = await self.check(client_id)
        return allowed


limiter = LocalRateLimiter(positive_int_setting('RATE_LIMIT_PER_MINUTE', 30, 120))
concurrency_slots = asyncio.Semaphore(positive_int_setting('MAX_CONCURRENT_REQUESTS', 3, 10))
