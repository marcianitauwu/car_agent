import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.agents.policy_agent import review_answers


def review(payload):
    agent = SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(text=json.dumps(payload))))
    with patch('app.agents.policy_agent.create_agent', return_value=(agent, 'test-model')):
        return asyncio.run(review_answers('5 asientos y poca gasolina', [
            {'agent': 'consumption', 'answer': 'Auto [doc-1]', 'documents': [{'source_id': 'doc-1'}]},
        ]))[0]


def test_rejection_preserves_concrete_reason_and_affected_agent():
    verdict = review({'approved': False, 'category': 'unsafe_output',
                      'reason_code': 'contradictory_evidence', 'affected_agents': ['consumption']})
    assert not verdict.approved
    assert verdict.reason_code == 'contradictory_evidence'
    assert verdict.affected_agents == ['consumption']


def test_approval_cannot_include_blocking_reason():
    verdict = review({'approved': True, 'category': 'allowed',
                      'reason_code': 'unsupported_claim', 'affected_agents': ['consumption']})
    assert not verdict.approved and verdict.reason_code == 'invalid_review'


def test_reviewer_cannot_blame_agent_absent_from_results():
    verdict = review({'approved': False, 'category': 'unsafe_output',
                      'reason_code': 'unsupported_claim', 'affected_agents': ['economy']})
    assert not verdict.approved and verdict.reason_code == 'invalid_review'


def test_free_text_cannot_be_exposed_as_reason():
    verdict = review({'approved': False, 'category': 'unsafe_output',
                      'reason_code': 'arbitrary text', 'affected_agents': ['consumption']})
    assert verdict.reason_code == 'invalid_review'
