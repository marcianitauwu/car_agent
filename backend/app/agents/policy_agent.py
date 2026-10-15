"""Agente de políticas: clasificación semántica y revisión de salida."""
import json
import asyncio
from app.agents.factory import create_agent
from app.schemas.models import PolicyDecision, PolicyReview
from app.services.costs import measure_usage


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        text = text.strip('`').removeprefix('json').strip()
    return json.loads(text)


async def evaluate_question(question: str) -> tuple[PolicyDecision, dict]:
    agent, model = create_agent('policy')
    prompt = json.dumps({'phase': 'input', 'question': question}, ensure_ascii=False)
    response = await asyncio.wait_for(agent.run(prompt), timeout=35)
    usage = measure_usage(response, 'policy', model)
    try:
        decision = PolicyDecision.model_validate(_parse_json(response.text))
    except Exception:
        # Al fallar el contrato JSON, negar pero conservar usage para el dashboard.
        decision = PolicyDecision(allowed=False, category='unknown')
    return decision, usage


async def review_answers(question: str, results: list[dict]) -> tuple[PolicyReview, dict]:
    agent, model = create_agent('policy')
    # Las respuestas NO se emiten al navegador antes de estas validaciones.
    # Se limita el contexto de revisión, manteniendo los documentos autorizados.
    payload = {'phase': 'output', 'question': question, 'results': results}
    response = await asyncio.wait_for(agent.run(json.dumps(payload, ensure_ascii=False, default=str)), timeout=40)
    usage = measure_usage(response, 'policy_review', model)
    try:
        review = PolicyReview.model_validate(_parse_json(response.text))
        if (review.approved and review.category != 'allowed') or (not review.approved and review.category == 'allowed'):
            raise ValueError('Revisión inconsistente')
        if (review.approved and (review.reason_code not in ('none', 'unspecified') or review.affected_agents)):
            raise ValueError('Aprobación con incidencias')
        if not review.approved and review.reason_code == 'none':
            raise ValueError('Bloqueo sin motivo')
        if not set(review.affected_agents).issubset({item['agent'] for item in results}):
            raise ValueError('Agente ajeno a la revisión')
    except Exception:
        review = PolicyReview(approved=False, category='unknown', reason_code='invalid_review')
    return review, usage
