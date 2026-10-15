import pytest
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError

from app.schemas.models import SearchPlan
from app.tools.azure_search import planned_options
from app.agents.orchestrator import choose_agents


def test_combined_alternatives_negation_range_and_order():
    plan = SearchPlan.model_validate({
        'search_text': '*',
        'filter_groups': [
            [{'field': 'color', 'operator': 'eq', 'value': 'Azul'},
             {'field': 'color', 'operator': 'eq', 'value': 'Rojo'}],
            [{'field': 'combustible', 'operator': 'ne', 'value': 'Diésel'}],
            [{'field': 'ciudad', 'operator': 'eq', 'value': 'Cuenca'}],
            [{'field': 'precio_usd', 'operator': 'ge', 'value': 10000}],
            [{'field': 'precio_usd', 'operator': 'le', 'value': 15000}],
        ],
        'order_by': [{'field': 'consumo_l_100km', 'direction': 'asc'}],
    })
    options = planned_options(plan, 3)
    assert options['filter'] == (
        "(color eq 'Azul' or color eq 'Rojo') and (combustible ne 'Diésel') "
        "and (ciudad eq 'Cuenca') and (precio_usd ge 10000) and (precio_usd le 15000)")
    assert options['search_text'] == '*'
    assert options['order_by'] == ['consumo_l_100km asc']


def test_filter_literal_escapes_quotes_instead_of_executing_expression():
    plan = SearchPlan(search_text='*', filter_groups=[[{
        'field': 'modelo', 'operator': 'eq', 'value': "x' or disponible eq true or modelo eq 'x",
    }]])
    assert "'x'' or disponible eq true or modelo eq ''x'" in planned_options(plan, 3)['filter']


@pytest.mark.parametrize('condition', [
    {'field': 'secret', 'operator': 'eq', 'value': 'x'},
    {'field': 'precio_usd', 'operator': 'le', 'value': 'barato'},
    {'field': 'precio_usd', 'operator': 'le', 'value': True},
    {'field': 'precio_usd', 'operator': 'le', 'value': float('nan')},
    {'field': 'color', 'operator': 'gt', 'value': 'Azul'},
    {'field': 'disponible', 'operator': 'eq', 'value': 'true'},
])
def test_invalid_search_conditions_are_rejected(condition):
    with pytest.raises(ValidationError):
        SearchPlan(search_text='*', filter_groups=[[condition]])


def test_qualitative_search_does_not_invent_numeric_ranking():
    plan = SearchPlan(search_text='asientos ajuste lumbar')
    assert planned_options(plan, 3) == {'search_text': 'asientos ajuste lumbar', 'top': 3}


@pytest.mark.parametrize('with_plan', [True, False])
def test_router_requires_validated_plan_for_each_selected_agent(with_plan):
    payload = {'agents': ['economy'], 'reason': 'Color y presupuesto'}
    if with_plan:
        payload['search_plans'] = {'economy': {
            'search_text': '*', 'filter_groups': [[{
                'field': 'precio_usd', 'operator': 'le', 'value': 15000}]], 'order_by': []}}
    agent = SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(text=json.dumps(payload))))
    with patch('app.agents.orchestrator.create_agent', return_value=(agent, 'test-model')):
        if with_plan:
            decision, _ = asyncio.run(choose_agents('No puedo gastar más de quince mil'))
            assert decision.search_plans['economy'].filter_groups[0][0].value == 15000
        else:
            with pytest.raises(ValueError):
                asyncio.run(choose_agents('No puedo gastar más de quince mil'))
