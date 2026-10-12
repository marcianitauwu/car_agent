"""Un agente LLM que SOLO decide el enrutamiento."""
import json
import asyncio
from app.agents.factory import create_agent
from app.schemas.models import RoutingDecision
from app.services.costs import measure_usage


async def choose_agents(question: str) -> tuple[RoutingDecision, dict]:
    agent, model = create_agent('orchestrator')
    response = await asyncio.wait_for(agent.run(question), timeout=40)
    text = (getattr(response, 'text', '') or str(response)).strip()
    if text.startswith('```'):
        text = text.strip('`').removeprefix('json').strip()
    try:
        decision = RoutingDecision.model_validate({**json.loads(text), 'question': question})
    except Exception as exc:
        raise ValueError(f'El orquestador no devolvio la decision JSON esperada: {text[:300]}') from exc
    usage = measure_usage(response, 'orchestrator', model)
    return decision, usage
