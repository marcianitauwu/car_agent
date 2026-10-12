"""Crea agentes sin herramientas implícitas. Los prompts viven en archivos Markdown."""
from pathlib import Path
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from app.core.config import required, setting

PROMPTS = Path(__file__).resolve().parents[1] / 'prompts'
AGENT_KEYS = frozenset({'policy', 'orchestrator', 'comfort', 'consumption', 'economy'})


def create_agent(key: str) -> tuple[Agent, str]:
    if key not in AGENT_KEYS:
        raise ValueError('Agente no autorizado')
    required('AZURE_OPENAI_BASE_URL', 'AZURE_OPENAI_API_KEY',
             'AZURE_OPENAI_ROUTER_DEPLOYMENT', 'AZURE_OPENAI_SPECIALIST_DEPLOYMENT')
    if key == 'policy':
        model = setting('AZURE_OPENAI_POLICY_DEPLOYMENT') or setting('AZURE_OPENAI_ROUTER_DEPLOYMENT')
    elif key == 'orchestrator':
        model = setting('AZURE_OPENAI_ROUTER_DEPLOYMENT')
    else:
        model = setting('AZURE_OPENAI_SPECIALIST_DEPLOYMENT')

    # API Responses (/openai/v1/responses): se proporciona la URL BASE, no /responses.
    client = OpenAIChatClient(
        model=model,
        base_url=setting('AZURE_OPENAI_BASE_URL'),
        api_key=setting('AZURE_OPENAI_API_KEY'),
    )
    agent = Agent(
        client=client,
        name=key,
        instructions=(PROMPTS / f'{key}.md').read_text(encoding='utf-8'),
        # Sin tools: ni politicas ni especialistas pueden llamar sitios externos.
    )
    return agent, model
