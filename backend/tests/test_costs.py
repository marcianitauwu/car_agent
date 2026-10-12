from types import SimpleNamespace

import pytest

from app.services.costs import measure_usage, total_cost


@pytest.mark.parametrize('usage', [
    {'input_token_count': 100, 'output_token_count': 20},
    SimpleNamespace(input_token_count=100, output_token_count=20),
])
def test_reported_usage_and_cost(usage, monkeypatch):
    monkeypatch.setenv('ROUTER_INPUT_PRICE_PER_M', '1')
    monkeypatch.setenv('ROUTER_OUTPUT_PRICE_PER_M', '2')
    result = measure_usage(SimpleNamespace(usage_details=usage), 'orchestrator', 'test')
    assert result['input_tokens'] == 100
    assert result['output_tokens'] == 20
    assert result['input_cost_usd'] == pytest.approx(0.0001)
    assert result['output_cost_usd'] == pytest.approx(0.00004)
    assert result['total_cost_usd'] == pytest.approx(0.00014)


def test_missing_usage_stays_unknown():
    result = measure_usage(SimpleNamespace(), 'orchestrator', 'test')
    assert result['input_tokens'] is None
    assert result['output_tokens'] is None
    assert result['total_cost_usd'] is None


def test_total():
    measures = [
        {'input_tokens': 100, 'output_tokens': 50, 'input_cost_usd': .0001, 'output_cost_usd': .0002, 'total_cost_usd': .0003},
        {'input_tokens': 200, 'output_tokens': 70, 'input_cost_usd': .0002, 'output_cost_usd': .0003, 'total_cost_usd': .0005},
    ]
    assert total_cost(measures)['input_tokens'] == 300
    assert round(total_cost(measures)['total_cost_usd'], 4) == .0008


def test_unknown_price_is_unknown():
    assert total_cost([{'input_tokens': 100, 'output_tokens': 50, 'input_cost_usd': None,
                        'output_cost_usd': None, 'total_cost_usd': None}])['total_cost_usd'] is None
