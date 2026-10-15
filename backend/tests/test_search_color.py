import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.tools.azure_search import color_filter, search_vehicles


@pytest.mark.parametrize('question', ['Quiero un carro azul', 'Solo carros azules'])
def test_search_requires_blue_in_color_field(question):
    client = MagicMock()
    client.search.return_value = [{'id': '1', 'color': 'Azul'}]
    with (patch('app.tools.azure_search.required'),
          patch('app.tools.azure_search.setting', side_effect=lambda name, default='': default),
          patch('app.tools.azure_search.AzureKeyCredential'),
          patch('app.tools.azure_search.SearchClient', return_value=client)):
        docs = asyncio.run(search_vehicles(question))
    options = client.search.call_args.kwargs
    assert options['search_text'] == question
    assert options['filter'] == "(color eq 'Azul' or color eq 'azul' or color eq 'AZUL')"
    assert 'order_by' not in options
    assert docs[0]['color'] == 'Azul'
    client.close.assert_called_once()


@pytest.mark.parametrize('question', [
    'Quiero un carro económico', 'No quiero azul',
    'Cualquier color excepto azul', 'Azul o rojo',
])
def test_does_not_impose_one_color_on_other_requests(question):
    assert color_filter(question) is None
