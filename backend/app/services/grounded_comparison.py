"""Comparaciones de respaldo calculadas, sin generar nuevas cifras con un LLM."""
import math

from app.services.security import normalized, output_violation


def numeric(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def grounded_comparison(result: dict, question: str) -> dict | None:
    key = result['agent']
    if key not in ('consumption', 'economy'):
        return None
    # Recuperacion acotada a precio + consumo de gasolina; no inferir otros criterios.
    text = normalized(question)
    if 'gasolina' not in text or not any(word in text for word in ('barato', 'precio', 'economico')):
        return None
    field = 'consumo_l_100km' if key == 'consumption' else 'precio_usd'
    candidates = []
    for doc in result['documents']:
        value = numeric(doc.get(field))
        if (value is not None and normalized(str(doc.get('combustible', ''))) == 'gasolina'
                and doc.get('marca') and doc.get('modelo')):
            candidates.append((doc, value))
    if not candidates:
        return None
    minimum = min(value for _, value in candidates)
    metric = 'consumo documentado' if key == 'consumption' else 'precio documentado'
    lines = ['Comparación limitada a los vehículos de gasolina con datos positivos '
             'en los documentos de este especialista:']
    for doc, value in candidates:
        amount = f'{value:g} L/100 km' if key == 'consumption' else f'USD {value:g}'
        tie = f' (menor {metric} entre estas opciones)' if value == minimum else ''
        lines.append(f"- {doc['marca']} {doc['modelo']}: {amount}{tie} [{doc['source_id']}].")
    lines.append('Este resultado compara un solo criterio; no demuestra que la misma opción '
                 'sea la más barata y la de menor consumo, ni confirma otros requisitos de la pregunta.')
    answer = '\n'.join(lines)
    if output_violation(answer, {doc['source_id'] for doc in result['documents']}):
        return None
    return {**result, 'answer': answer, 'invalid': None}
