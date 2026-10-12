"""Refina consultas breves sin agregar preferencias del usuario."""
import re
from difflib import get_close_matches

from app.services.security import normalized


def refine_question(question: str) -> str:
    words = normalized(question).strip().split()
    if not 1 <= len(words) <= 3 or any(not re.fullmatch(r'[a-z]+', word) for word in words):
        return question
    vocabulary = ('vehiculo', 'vehiculos', 'carro', 'carros', 'auto', 'autos',
                  'coche', 'coches', 'nuevo', 'nuevos', 'usado', 'usados')
    corrected = []
    for word in words:
        matches = get_close_matches(word, vocabulary, n=1, cutoff=0.8)
        if not matches:
            return question
        corrected.append(matches[0])
    vehicles = set(vocabulary[:8])
    if corrected[0] not in vehicles or any(word in vehicles for word in corrected[1:]):
        return question
    return 'Quiero conocer opciones de ' + ' '.join(corrected) + '.'
