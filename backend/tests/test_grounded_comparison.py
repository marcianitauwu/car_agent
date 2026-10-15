from app.services.grounded_comparison import grounded_comparison


def result():
    return {'agent': 'consumption', 'answer': 'A consume menos [doc-1].', 'documents': [
        {'source_id': 'doc-1', 'marca': 'Marca', 'modelo': 'A',
         'combustible': 'Gasolina', 'consumo_l_100km': '7', 'precio_usd': '6500'},
        {'source_id': 'doc-2', 'marca': 'Marca', 'modelo': 'B',
         'combustible': 'Gasolina', 'consumo_l_100km': '5.2', 'precio_usd': '9000'},
        {'source_id': 'doc-3', 'marca': 'Marca', 'modelo': 'C',
         'combustible': 'Eléctrico', 'consumo_l_100km': '0', 'precio_usd': '6000'},
    ]}


def test_recovery_computes_real_minimum_without_mixing_price_winner():
    original = result()
    repaired = grounded_comparison(original, 'auto barato y que consuma poca gasolina')
    assert 'Marca B: 5.2 L/100 km (menor consumo documentado' in repaired['answer']
    assert 'Marca A: 7 L/100 km (menor' not in repaired['answer']
    assert 'Marca C' not in repaired['answer']
    assert original['answer'] == 'A consume menos [doc-1].'
    assert repaired['documents'] == original['documents']


def test_price_minimum_and_ties_use_numeric_values():
    original = result()
    original['agent'] = 'economy'
    original['documents'][1]['precio_usd'] = '6500.0'
    repaired = grounded_comparison(original, 'auto barato y poca gasolina')
    assert repaired['answer'].count('(menor precio documentado') == 2


def test_missing_gasoline_evidence_does_not_produce_recovery():
    original = result()
    for doc in original['documents']:
        doc.pop('combustible')
    assert grounded_comparison(original, 'auto barato y poca gasolina') is None


def test_other_queries_do_not_use_specialized_recovery():
    assert grounded_comparison(result(), 'auto comodo con cinco asientos') is None


def test_api_rechecks_repaired_answer_once_before_publishing():
    import asyncio
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch
    from app.api import chat

    class Workflow:
        async def run(self, message, stream):
            for item in [
                {'type': 'route_selected', 'agents': ['consumption']},
                {'type': 'internal_result', **result()},
            ]:
                yield SimpleNamespace(type='output', data=item)

    async def collect(approved):
        rejected = SimpleNamespace(approved=False, category='unsafe_output',
                                   reason_code='contradictory_evidence', affected_agents=['consumption'])
        accepted = SimpleNamespace(approved=True, category='allowed')
        review = AsyncMock(side_effect=[(rejected, {}), (accepted if approved else rejected, {})])
        with patch.object(chat, 'build_workflow', return_value=Workflow()), \
             patch.object(chat, 'limiter', SimpleNamespace(check=AsyncMock(return_value=(True, 0)))), \
             patch.object(chat, 'concurrency_slots', asyncio.Semaphore(1)), \
             patch.object(chat, 'review_answers', review), \
             patch.object(chat, 'record_incident'), \
             patch.object(chat, 'total_cost', return_value={}):
            response = await chat.chat_stream(
                SimpleNamespace(message='auto barato y que consuma poca gasolina'),
                SimpleNamespace(client=None))
            events = [json.loads(chunk.removeprefix('data: '))
                      async for chunk in response.body_iterator]
        assert review.await_count == 2
        assert 'Marca B: 5.2' in review.call_args.args[1][0]['answer']
        assert sum(e['type'] == 'answer_repair' for e in events) == 1
        assert not any(e['type'] == 'internal_result' for e in events)
        assert events[-1]['blocked'] is not approved
        if approved:
            assert 'Marca B: 5.2' in events[-1]['answer']
        else:
            assert 'Marca B' not in events[-1]['answer']

    asyncio.run(collect(True))
    asyncio.run(collect(False))
