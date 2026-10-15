import asyncio
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.schemas.models import SearchPlan
from app.tools.azure_search import planned_options, search_vehicles


@pytest.mark.parametrize('operator', ['gt', 'lt', 'ge', 'le'])
def test_numeric_comparison_and_projection_reach_azure(operator):
    plan = SearchPlan(search_text='*', select_fields=['precio_usd'], filter_groups=[[
        {'field': 'precio_usd', 'operator': operator, 'value': 30000},
    ]])
    client = MagicMock()
    client.search.return_value = []
    with patch('app.tools.azure_search.required'), \
         patch('app.tools.azure_search.setting', side_effect=lambda name, default='': default), \
         patch('app.tools.azure_search.AzureKeyCredential'), \
         patch('app.tools.azure_search.SearchClient', return_value=client):
        asyncio.run(search_vehicles('carro mayor a 30000', plan=plan))
    options = client.search.call_args.kwargs
    assert options['filter'] == f'(precio_usd {operator} 30000)'
    assert options['select'] == ['marca', 'modelo', 'anio', 'precio_usd']
    assert 'order_by' not in options


def test_projection_preserves_other_criteria_and_sort_evidence():
    plan = SearchPlan(search_text='*', select_fields=['precio_usd'], filter_groups=[
        [{'field': 'precio_usd', 'operator': 'ge', 'value': 15000}],
        [{'field': 'precio_usd', 'operator': 'le', 'value': 30000}],
        [{'field': 'ciudad', 'operator': 'eq', 'value': 'Cuenca'}],
    ], order_by=[{'field': 'consumo_l_100km', 'direction': 'asc'}])
    options = planned_options(plan, 3)
    assert options['select'] == ['marca', 'modelo', 'anio', 'precio_usd', 'ciudad', 'consumo_l_100km']
    assert options['filter'] == "(precio_usd ge 15000) and (precio_usd le 30000) and (ciudad eq 'Cuenca')"


def test_descriptive_search_keeps_document_context():
    assert 'select' not in planned_options(SearchPlan(search_text='soporte lumbar'), 3)


def test_unknown_projection_fields_are_rejected():
    with pytest.raises(ValidationError):
        SearchPlan(search_text='*', select_fields=['api_key'])
