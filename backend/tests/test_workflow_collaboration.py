"""Ejecuta el workflow real, sustituyendo únicamente modelos y Search."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.orchestration import workflow
from app.schemas.models import PolicyDecision, RoutingDecision


@pytest.mark.parametrize('selected', [
    ['comfort'], ['economy'], ['consumption'],
    ['comfort', 'economy'], ['consumption', 'economy'], ['comfort', 'consumption'],
])
def test_workflow_waits_for_selected_specialists_and_emits_synthesis_events(selected):
    events, calls = run_workflow(selected)
    initial = [event['agent'] for event in events
               if event['type'] == 'internal_result' and event['agent'] != 'synthesizer']
    assert set(initial) == set(selected)
    if len(selected) == 1:
        assert calls == []
        assert any(event['type'] == 'synthesis_skipped' for event in events)
    else:
        assert calls == [selected]
        exchange_index = next(i for i, event in enumerate(events)
                              if event == {'type': 'node_start', 'agent': 'exchange'})
        assert all(i < exchange_index for i, event in enumerate(events)
                   if event['type'] == 'agent_done' and event['agent'] in selected)
        assert any(event == {'type': 'node_start', 'agent': 'synthesizer'} for event in events)
        assert any(event['type'] == 'internal_result' and event['agent'] == 'synthesizer'
                   for event in events)


@pytest.mark.parametrize('missing,invalid', [(True, False), (False, True)])
def test_missing_or_invalid_evidence_does_not_start_exchange(missing, invalid):
    events, calls = run_workflow(['comfort', 'economy'], missing=missing, invalid=invalid)
    assert calls == []
    assert any(event['type'] == 'synthesis_skipped' for event in events)
    assert not any(event.get('agent') == 'synthesizer' for event in events)


def run_workflow(selected, missing=False, invalid=False):
    calls = []

    class Agent:
        def __init__(self, key):
            self.key = key

        async def run(self, prompt):
            # Cambia el orden de terminación para probar la reunión de resultados.
            if self.key == 'comfort':
                await asyncio.sleep(0.01)
            return SimpleNamespace(text='Sin cita' if invalid else 'Vehículo adecuado [doc-1].')

    async def collaborate(question, results):
        assert question == 'Cómodo y económico'
        calls.append([result['agent'] for result in results])
        yield {'type': 'node_start', 'agent': 'exchange'}
        yield {'type': 'agent_done', 'agent': 'exchange'}
        yield {'type': 'node_start', 'agent': 'synthesizer'}
        yield {'type': 'internal_result', 'agent': 'synthesizer',
               'answer': 'Conclusión [doc-1].', 'documents': results[0]['documents']}
        yield {'type': 'agent_done', 'agent': 'synthesizer'}

    async def collect():
        flow = workflow.build_workflow()
        return [event.data async for event in flow.run('Cómodo y económico', stream=True)
                if event.type == 'output']

    with (patch.object(workflow, 'evaluate_question', AsyncMock(return_value=(
            PolicyDecision(allowed=True, category='allowed'), {}))),
          patch.object(workflow, 'choose_agents', AsyncMock(return_value=(
            RoutingDecision(question='Cómodo y económico', agents=selected, reason='Criterios'), {}))),
          patch.object(workflow, 'search_vehicles', AsyncMock(return_value=[] if missing else [
              {'source_id': 'doc-1', 'model': 'Auto'}])),
          patch.dict(workflow.BUILDERS, {key: lambda key=key: (Agent(key), 'test') for key in selected}),
          patch.object(workflow, 'collaborate', collaborate)):
        events = asyncio.run(collect())
    return events, calls
