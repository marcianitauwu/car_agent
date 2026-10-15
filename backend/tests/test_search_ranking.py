import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.models import SearchPlan
from app.tools.azure_search import search_vehicles


@pytest.mark.parametrize('direction,requested_top,expected_top', [
    ('asc', None, 20), ('desc', None, 20), ('asc', 1000, 50),
])
def test_price_ranking_retrieves_more_than_three_with_numeric_order(
        direction, requested_top, expected_top):
    plan = SearchPlan(search_text='*', filter_groups=[[{
        'field': 'precio_usd', 'operator': 'gt', 'value': 0,
    }]], order_by=[{'field': 'precio_usd', 'direction': direction}])
    client = MagicMock()
    # El cuarto resultado permite continuar despues de un empate de tres.
    client.search.return_value = [
        {'marca': 'Ford', 'modelo': str(i), 'precio_usd': price}
        for i, price in enumerate([6500, 6500, 6500, 7000])
    ]
    with (patch('app.tools.azure_search.required'),
          patch('app.tools.azure_search.setting', side_effect=lambda name, default='': default),
          patch('app.tools.azure_search.AzureKeyCredential'),
          patch('app.tools.azure_search.SearchClient', return_value=client)):
        docs = asyncio.run(search_vehicles('Ordena los vehiculos por precio',
                                          top=requested_top, plan=plan))
    options = client.search.call_args.kwargs
    assert options['top'] == expected_top
    assert options['search_text'] == '*'
    assert options['order_by'] == [f'precio_usd {direction}']
    assert options['filter'] == '(precio_usd gt 0)'
    assert len(docs) == 4
    assert docs[-1]['precio_usd'] == '7000'
    assert docs[-1]['source_id'] == 'doc-4'
    client.close.assert_called_once()
