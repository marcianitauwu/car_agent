import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.collaboration import collaborate, shared_evidence


def results():
    return [
        {'agent': 'comfort', 'answer': 'Auto A cómodo [doc-1].',
         'documents': [{'source_id': 'doc-1', 'model': 'Auto A'}]},
        {'agent': 'economy', 'answer': 'Auto B económico [doc-1].',
         'documents': [{'source_id': 'doc-1', 'model': 'Auto B'}]},
    ]


def test_independent_citations_are_remapped_without_changing_originals():
    original = results()
    docs, answers = shared_evidence(original)
    assert docs == [{'source_id': 'doc-1', 'model': 'Auto A'},
                    {'source_id': 'doc-2', 'model': 'Auto B'}]
    assert answers[1]['answer'] == 'Auto B económico [doc-2].'
    assert original == results()


def run_collaboration(original, texts):
    calls = []

    class Agent:
        def __init__(self, key):
            self.key = key

        async def run(self, prompt):
            calls.append((self.key, prompt))
            return SimpleNamespace(text=next(texts), usage_details={
                'input_token_count': 10, 'output_token_count': 5})

    async def collect():
        return [event async for event in collaborate('Cómodo y económico', original)]

    with patch('app.services.collaboration.create_agent',
               side_effect=lambda key: (Agent(key), 'test-model')):
        events = asyncio.run(collect())
    return calls, events


def test_both_specialists_read_peer_and_synthesis_receives_both_contributions():
    calls, events = run_collaboration(results(), iter([
        'Comodidad de A [doc-1].', 'Precio de B [doc-2].',
        'A y B tienen criterios diferentes [doc-1] [doc-2].',
    ]))
    assert [key for key, _ in calls] == ['comfort', 'economy', 'synthesizer']
    for _, prompt in calls[:2]:
        assert 'Auto A cómodo [doc-1]' in prompt
        assert 'Auto B económico [doc-2]' in prompt
    payload = json.loads(calls[2][1])
    assert [item['agent'] for item in payload['contributions']] == ['comfort', 'economy']
    internal = next(event for event in events if event['type'] == 'internal_result')
    assert internal['agent'] == 'synthesizer' and not internal['invalid']
    assert len([event for event in events if event['type'] == 'usage']) == 3


def test_unbacked_contribution_stops_synthesis():
    calls, events = run_collaboration(results(), iter(['Inventado [doc-99].']))
    assert len(calls) == 1
    internal = next(event for event in events if event['type'] == 'internal_result')
    assert internal['invalid'] == 'unsafe_output'
    assert internal['answer'] == '' and internal['documents'] == []


def test_single_specialist_does_not_add_calls():
    calls, events = run_collaboration(results()[:1], iter([]))
    assert calls == [] and events == []


def test_api_reviews_joint_before_exposing_individual_and_joint_answers():
    events, reviewed = api_events(joint_invalid=False)
    final = next(event for event in events if event['type'] == 'final')
    assert [item['agent'] for item in reviewed] == ['comfort', 'economy', 'synthesizer']
    assert 'Auto A cómodo' in final['answer'] and 'Auto B económico' in final['answer']
    assert '### Respuesta conjunta' in final['answer']
    assert not final['blocked']
    assert all(event['type'] != 'internal_result' for event in events)


def test_api_blocks_invalid_joint_without_exposing_individual_answers():
    events, reviewed = api_events(joint_invalid=True)
    final = next(event for event in events if event['type'] == 'final')
    assert final['blocked'] and reviewed == []
    assert 'Auto A' not in final['answer'] and 'Auto B' not in final['answer']


def test_api_exposes_fixed_review_reason_without_revealing_drafts():
    events, _ = api_events(joint_invalid=False, reject_review=True)
    rejection = next(event for event in events if event['type'] == 'policy_blocked')
    assert rejection['reason_code'] == 'unsupported_claim'
    assert rejection['affected_agents'] == ['synthesizer']
    assert 'Sintetizador' in rejection['detail']
    final = next(event for event in events if event['type'] == 'final')
    assert final['blocked'] and 'Auto A' not in final['answer']


def api_events(joint_invalid, reject_review=False):
    from app.api import chat

    class Workflow:
        async def run(self, message, stream):
            yield SimpleNamespace(type='output', data={
                'type': 'route_selected', 'agents': ['comfort', 'economy']})
            for result in results():
                yield SimpleNamespace(type='output', data={'type': 'internal_result', **result})
            yield SimpleNamespace(type='output', data={'type': 'internal_result', 'agent': 'synthesizer',
               'answer': '' if joint_invalid else 'Conclusión [doc-1] [doc-2].',
               'documents': [] if joint_invalid else shared_evidence(results())[0],
               'invalid': 'unsafe_output' if joint_invalid else None})

    reviewed = []

    async def review(question, original):
        reviewed.extend(original)
        if reject_review:
            return SimpleNamespace(approved=False, category='unsafe_output',
                                   reason_code='unsupported_claim', affected_agents=['synthesizer']), {}
        return SimpleNamespace(approved=True, category='allowed'), {}

    async def collect():
        response = await chat.chat_stream(SimpleNamespace(message='Cómodo y económico'),
                                          SimpleNamespace(client=SimpleNamespace(host='test')))
        return [json.loads(chunk.removeprefix('data: ').strip())
                async for chunk in response.body_iterator]

    with (patch.object(chat, 'build_workflow', return_value=Workflow()),
          patch.object(chat, 'review_answers', review),
          patch.object(chat, 'record_incident'),
          patch.object(chat, 'limiter', SimpleNamespace(check=AsyncMock(return_value=(True, 0)))),
          patch.object(chat, 'concurrency_slots',
                       SimpleNamespace(acquire=AsyncMock(), release=MagicMock()))):
        events = asyncio.run(collect())
    return events, reviewed
