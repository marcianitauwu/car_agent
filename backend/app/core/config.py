"""Centraliza variables de entorno; no crea conexiones al importar."""
import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / '.env')


def setting(name: str, default: str = '') -> str:
    return os.getenv(name, default).strip()


def required(*names: str) -> None:
    missing = [name for name in names if not setting(name) or setting(name) == 'REEMPLAZAR']
    if missing:
        raise ValueError('Configura estas variables en backend/.env: ' + ', '.join(missing))


def price(name: str) -> float | None:
    raw = setting(name)
    if not raw:
        return None
    number = float(raw)
    if number < 0:
        raise ValueError(f'{name} no puede ser negativo')
    return number
