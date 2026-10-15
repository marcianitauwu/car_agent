from app.tools.azure_search import search_options


def test_minimum_gasoline_consumption_is_numeric_not_textual():
    options = search_options('¿Cuál es el vehículo que consume menos gasolina?', 3)
    assert options['search_text'] == '*'
    assert options['order_by'][0] == 'consumo_l_100km asc'
    assert 'consumo_l_100km gt 0' in options['filter']
    assert "combustible eq 'Gasolina'" in options['filter']


def test_fuel_efficiency_sorts_numeric_consumption():
    options = search_options('¿Qué carro es más eficiente para ahorrar combustible?', 3)
    assert options['search_text'] == '*'
    assert options['order_by'][0] == 'consumo_l_100km asc'


def test_cheapest_available_sorts_and_filters_catalog():
    options = search_options('¿Cuál es el vehículo más barato disponible?', 3)
    assert options['search_text'] == '*'
    assert options['order_by'][0] == 'precio_usd asc'
    assert options['order_by'] == ['precio_usd asc']
    assert 'disponible eq true' in options['filter']


def test_budget_spanish_thousands_is_fifteen_thousand():
    options = search_options('Tengo un presupuesto de $15.000, ¿qué vehículos puedo considerar?', 3)
    assert options['search_text'] == '*'
    assert 'precio_usd le 15000' in options['filter']


def test_does_not_add_price_preference_to_color_request():
    options = search_options('Quiero un carro azul', 3)
    assert 'order_by' not in options
    assert 'precio_usd' not in options['filter']


def test_preserves_additional_text_constraints():
    options = search_options('Quiero el Toyota azul más barato en Cuenca', 3)
    assert 'Toyota' in options['search_text']
    assert 'Cuenca' in options['search_text']
    assert "color eq 'Azul'" in options['filter']


def test_year_is_not_a_budget():
    options = search_options('Quiero un carro de 2025', 3)
    assert 'filter' not in options
