"""Controles verificables; el prompt del agente no sustituye estas restricciones."""
import re
import unicodedata
from app.schemas.models import PolicyCategory

# Las negativas son textos fijos; no se repite al usuario su entrada riesgosa.
DENIALS = {
    'off_topic': 'Solo puedo atender consultas sobre caracteristicas, consumo, comodidad y precios de vehiculos.',
    'code_request': 'Este asistente se dedica a recomendar vehiculos y no genera codigo de programacion.',
    'prompt_injection': 'No puedo seguir instrucciones para modificar las reglas de este sistema.',
    'secrets': 'No puedo compartir claves, credenciales ni configuraciones privadas.',
    'privacy': 'No puedo divulgar informacion personal o documentos privados de otras personas.',
    'external_source': 'Las respuestas se basan exclusivamente en el indice autorizado de Azure AI Search.',
    'unsafe_output': 'No puedo mostrar esa respuesta porque no paso la validacion de seguridad o evidencia.',
    'unknown': 'No pude verificar que la solicitud cumple las politicas. Intenta reformularla.',
}


def normalized(value: str) -> str:
    plain = unicodedata.normalize('NFKD', value)
    plain = ''.join(c for c in plain if not unicodedata.combining(c) and c not in '\u200b\u200c\u200d\ufeff')
    return plain.casefold()


# Controles explícitos no exhaustivos. Los casos ambiguos los revisa el LLM.
INPUT_RULES: list[tuple[str, str]] = [
    ('off_topic', r'\b(?:receta de|como cocinar|prepara un pastel|hazme un poema|cuenta un chiste|pronostico del tiempo)\b'),
    ('prompt_injection', r'\b(?:ignora|olvida|desobedece|override|ignore|forget|bypass)\b.{0,85}\b(?:instrucciones|reglas|politicas|system|prompt|instructions|rules)\b'),
    ('prompt_injection', r'\b(?:system prompt|developer message|mensaje del sistema|modo desarrollador|jailbreak|you are now|actua como sistema|simula ser administrador)\b'),
    ('secrets', r'\b(?:api[ _-]?key|api[ _-]?token|clave(?:s)? de (?:azure|api|acceso)|contrase(?:n|ñ)a(?:s)?|secret(?:o|os)|\.env|credenciales|access token)\b'),
    ('privacy', r'\b(?:datos personales|informacion privada|documentos privados|historial privado|datos de otro usuario|datos personales de)\b'),
    ('external_source', r'\b(?:busca|consulta|investiga|revisa|usa|search|browse)\b.{0,55}\b(?:google|bing|internet|web|wikipedia|youtube|reddit)\b'),
    ('code_request', r'\b(?:escribe|genera|dame|crea|muestra|haz|programa|write|give me)\b.{0,55}\b(?:codigo (?:python|javascript|sql|fuente|de programacion)|script|programa (?:en|para)|codigo html|funcion (?:python|javascript)|source code)\b'),
    ('code_request', r'\b(?:escribe|genera|dame|crea|muestra|haz)\b.{0,45}\b(?:python|javascript|powershell|bash|c\+\+|sql|html)\b'),
]
SENSITIVE_VALUE_RULES = [
    r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',
    r'(?<!\d)(?:\+?593[-. ]?)?0?9\d{8}(?!\d)',
    r'\b[A-Za-z0-9_-]{40,}\b',  # potencial token / llave en un campo
]
OUTPUT_BLOCK_RULES = [
    r'```',
    r'<\s*script\b',
    r'\b(?:console\.log|print)\s*\(',
    r'(?m)^\s*(?:import\s+[a-z_]|from\s+[a-z_].*import|def\s+\w+\s*\(|class\s+\w+\s*\(|(?:pip|npm)\s+install\b|(?:curl|wget)\s+https?://)',
    r'(?m)^\s*(?:\$\s+|PS\s+[A-Z]:\\)',
    r'\b(?:api[ _-]?key|clave(?:s)? (?:api|azure|de acceso)|\.env|access token|contrase(?:n|ñ)a|secret key|credenciales)\b',
    *SENSITIVE_VALUE_RULES,
    r'https?://\S+\.(?:search\.windows\.net|services\.ai\.azure\.com|openai\.azure\.com)\b',
]
CITATION_RE = re.compile(r'\[(doc-\d+)\]')


def input_violation(question: str) -> str | None:
    text = normalized(question)
    for category, expression in INPUT_RULES:
        if re.search(expression, text, flags=re.IGNORECASE | re.DOTALL):
            return category
    return None


def contaminated_document(document: dict) -> bool:
    """Descarta documentos que intenten hacerse pasar por instrucciones o incluyan secretos."""
    text = normalized(' '.join(str(v) for v in document.values()))
    return (any(re.search(expr, text, re.I | re.S) for category, expr in INPUT_RULES
                if category in ('prompt_injection', 'secrets', 'privacy'))
            or any(re.search(expr, ' '.join(str(v) for v in document.values()), re.I)
                   for expr in SENSITIVE_VALUE_RULES))


def output_violation(answer: str, valid_citations: set[str]) -> str | None:
    """No revela texto del modelo si está sin evidencia/cita o contiene material bloqueado."""
    if not answer or len(answer) > 6500:
        return 'unsafe_output'
    if any(re.search(expr, answer, re.I) for expr in OUTPUT_BLOCK_RULES):
        return 'unsafe_output'
    citations = set(CITATION_RE.findall(answer))
    if not citations or not citations.issubset(valid_citations):
        return 'unsafe_output'
    return None


def refusal(category: str) -> str:
    return DENIALS.get(category, DENIALS['unknown'])
