import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api import chat
from app.schemas.models import ChatRequest


@pytest.mark.parametrize('approved', [True, False])
def test_search_documents_only_exposed_after_approval(approved):
    documents = [{'source_id': 'doc-1', 'marca': 'Toyota', 'modelo': 'Corolla'}]

    class Workflow:
        async def run(self, message, stream):
            for item in [
                {'type': 'route_selected', 'agents': ['economy']},
                {'type': 'internal_result', 'agent': 'economy',
                 'answer': 'Toyota Corolla [doc-1]', 'documents': documents},
            ]:
                yield SimpleNamespace(type='output', data=item)

    async def collect():
        verdict = SimpleNamespace(approved=approved, category='unsafe_output',
                                  reason_code='unsupported_claim', affected_agents=['economy'])
        with patch.object(chat, 'build_workflow', return_value=Workflow()), \
             patch.object(chat, 'limiter', SimpleNamespace(check=AsyncMock(return_value=(True, 0)))), \
             patch.object(chat, 'concurrency_slots', asyncio.Semaphore(1)), \
             patch.object(chat, 'review_answers', AsyncMock(return_value=(verdict, {}))), \
             patch.object(chat, 'total_cost', return_value={}), \
             patch.object(chat, 'record_incident'):
            response = await chat.chat_stream(ChatRequest(message='Auto economico'),
                                             SimpleNamespace(client=None))
            return [json.loads(chunk.removeprefix('data: '))
                    async for chunk in response.body_iterator]

    events = asyncio.run(collect())
    final = events[-1]
    assert final['type'] == 'final'
    assert final['blocked'] is not approved
    assert all('documents' not in event and 'search_results' not in event
               for event in events[:-1])
    if approved:
        assert final['search_results'] == [{'agent': 'economy', 'documents': documents}]
    else:
        assert 'search_results' not in final
