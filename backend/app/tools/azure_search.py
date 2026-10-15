"""Busqueda centralizada en Azure AI Search; no existen conectores de Web ni herramientas externas."""
import asyncio
import json
import sys
import re
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from app.core.config import setting, required
from app.services.security import contaminated_document, normalized
from app.schemas.models import SearchPlan


def color_filter(query: str) -> str | None:
    """Filtra colores explícitos simples; deja negaciones y comparaciones al agente."""
    text = normalized(query)
    if re.search(r'\b(no|sin|excepto|menos|evita|distinto|diferente)\b', text):
        return None
    colors = {
        'azul': r'azul(?:es)?', 'Blanco': r'blanc[oa]s?',
        'Negro': r'negr[oa]s?', 'Rojo': r'roj[oa]s?',
        'Gris': r'gris(?:es)?', 'Plata': r'plata',
        'Verde': r'verdes?', 'Amarillo': r'amarill[oa]s?',
    }
    matches = [color.capitalize() for color, pattern in colors.items()
               if re.search(r'\b' + pattern + r'\b', text)]
    if len(matches) != 1:
        return None
    color = matches[0]
    return '(' + ' or '.join(f"color eq '{value}'" for value in
                            (color, color.lower(), color.upper())) + ')'


def search_options(query: str, top: int) -> dict:
    """Convierte intenciones numéricas conocidas en filtros y ordenamiento del índice."""
    text = normalized(query).strip(' ¿?¡!.')
    options = {'search_text': query[:700], 'top': top}
    filters = []
    requested_color = color_filter(query)
    if requested_color:
        filters.append(requested_color)
    cheap = bool(re.search(r'\b(mas barato|menor precio|precio mas bajo)\b', text))
    efficient = bool(re.search(
        r'\b(menos gasolina|menos combustible|menor consumo|consume menos|'
        r'mas eficiente|ahorrar combustible)\b', text))
    # Reconoce importes solo cuando hay una intención explícita de presupuesto.
    budget = None
    match = re.search(r'\b(?:presupuesto(?: de)?|hasta|maximo de)\s*\$?\s*'
                      r'(\d+(?:[.,]\d{3})*(?:[.,]\d{1,2})?)', text)
    if match:
        amount = re.sub(r'[.,](?=\d{3}(?:\D|$))', '', match[1])
        budget = float(amount.replace(',', '.'))
        filters.append(f'precio_usd le {budget:g}')
        filters.append('precio_usd gt 0')
    if cheap:
        filters.append('precio_usd gt 0')
        options['order_by'] = ['precio_usd asc']
    elif efficient:
        filters.append('consumo_l_100km gt 0')
        options['order_by'] = ['consumo_l_100km asc']
    if re.search(r'\bgasolina\b', text):
        filters.append("combustible eq 'Gasolina'")
    if re.search(r'\bdisponibles?\b', text):
        filters.append('disponible eq true')
    # Solo consultas generales conocidas usan todo el catálogo. Otros calificadores
    # conservan la búsqueda textual para no perder marca, ciudad o condición.
    general = re.fullmatch(
        r'(?:cual es el |que |quiero un |busco un )?'
        r'(?:vehiculo|carro|auto) (?:es )?(?:que consume menos gasolina|que consume menos combustible|'
        r'mas eficiente para ahorrar combustible|mas barato(?: disponible)?|'
        r'de menor consumo|con menor consumo)', text)
    budget_general = re.fullmatch(
        r'(?:tengo un )?presupuesto(?: de)?\s*\$?\s*[\d.,]+\s*[,;:]?\s*'
        r'(?:¿?que vehiculos puedo considerar)?', text)
    if general or budget_general:
        options['search_text'] = '*'
    if filters:
        options['filter'] = ' and '.join(dict.fromkeys(filters))
    return options


# Campos recuperables mínimos. Ajustar únicamente si el esquema de idx-carros
# utiliza nombres distintos; la validación de campos está en SearchPlan.
IDENTITY_FIELDS = ('marca', 'modelo', 'anio')
DESCRIPTIVE_FIELDS = (
    'tipo_carroceria', 'precio_usd', 'combustible', 'transmision',
    'consumo_l_100km', 'numero_asientos', 'caracteristicas',
)


def planned_options(plan: SearchPlan, top: int) -> dict:
    options = {'search_text': plan.search_text, 'top': top}
    groups = []
    for group in plan.filter_groups:
        alternatives = []
        for constraint in group:
            value = constraint.value
            if isinstance(value, bool):
                literal = str(value).lower()
            elif isinstance(value, str):
                literal = "'" + value.replace("'", "''") + "'"
            else:
                literal = format(value, '.15g')
            alternatives.append(f'{constraint.field} {constraint.operator} {literal}')
        groups.append('(' + ' or '.join(alternatives) + ')')
    if groups:
        options['filter'] = ' and '.join(groups)
    if plan.order_by:
        options['order_by'] = [f'{order.field} {order.direction}' for order in plan.order_by]
    # Nunca dejar la proyección implícita: Azure devolvería TODOS los
    # campos retrievable, incluso si después los descartamos en Python.
    requested = plan.select_fields or (
        list(DESCRIPTIVE_FIELDS) if plan.search_text != '*' else ['precio_usd']
    )
    options['select'] = list(dict.fromkeys([
        *IDENTITY_FIELDS, *requested,
        *(constraint.field for group in plan.filter_groups for constraint in group),
        *(order.field for order in plan.order_by),
    ]))
    return options


def is_catalog_listing(query: str) -> bool:
    """Distingue exploración del inventario de recomendaciones o superlativos.

    Solo identifica solicitudes explícitas de enumeración; por defecto 3.
    """
    text = normalized(query)
    if re.search(r'\b(recomiend|mejor|mas barato|mas caro|menor precio|mayor precio|'
                 r'menos gasolina|menor consumo|mas comodo|cual es|compara)\b', text):
        return False
    return bool(re.search(
        r'\b(lista(?:do|me)?|listar|enumera|muestra(?:me)?|dime cuales|'
        r'que (?:vehiculos|carros|autos|modelos)|cuales (?:vehiculos|carros|autos|modelos)|'
        r'que (?:vehiculos|carros|autos) hay|orden(a|ame)|ordena)\b', text
    ))


async def search_vehicles(query: str, top: int | None = None, *, plan: SearchPlan | None = None) -> list[dict]:
    required('AZURE_SEARCH_ENDPOINT', 'AZURE_SEARCH_API_KEY', 'AZURE_SEARCH_INDEX')
    try:
        configured = int(setting('AZURE_SEARCH_TOP', '3'))
    except ValueError as exc:
        raise ValueError('AZURE_SEARCH_TOP debe ser entero') from exc
    # Listados: primera pagina de 10. Recomendaciones y extremos: 3.
    # No alterar el limite de forma global para no sobrecargar las recomendaciones.
    listing = is_catalog_listing(query)
    if listing:
        page_size = max(1, min(10, int(setting('AZURE_SEARCH_LIST_TOP', '10'))))
        n = min(10, max(1, int(top))) if top is not None else page_size
    else:
        n = max(1, min(3, int(top if top is not None else configured)))
    semantic = setting('AZURE_SEARCH_SEMANTIC_CONFIGURATION')

    def _search() -> list[dict]:
        client = SearchClient(
            endpoint=setting('AZURE_SEARCH_ENDPOINT'),
            index_name=setting('AZURE_SEARCH_INDEX'),
            credential=AzureKeyCredential(setting('AZURE_SEARCH_API_KEY')),
        )
        try:
            options = planned_options(plan, n) if plan is not None else search_options(query, n)
            # La intención del plan debe respetarse. Azure Semantic Ranker
            # requiere texto de búsqueda y no admite order_by explícito.
            wants_semantic = plan is None or plan.search_mode == 'semantic'
            semantic_compatible = options['search_text'] != '*' and not options.get('order_by')
            if semantic and wants_semantic and semantic_compatible:
                options.update(query_type='semantic', semantic_configuration_name=semantic)
            else:
                options['query_type'] = 'simple'
            if 'select' not in options:
                options['select'] = list(dict.fromkeys([*IDENTITY_FIELDS, *DESCRIPTIVE_FIELDS,
                    'color', 'ciudad', 'condicion', 'disponible']))
            results = client.search(**options)
            docs = []
            for raw in results:
                # No se confian campos arbitrarios del indice: autorizacion por nombre.
                doc = {}
                
                for key, value in dict(raw).items():

                    field = key.casefold()

                    # Excluir metadatos internos de Azure Search
                    if key.startswith('@'):
                        continue

                    # Excluir vectores y embeddings
                    if (
                        field.endswith('_vector')
                        or 'embedding' in field
                    ):
                        continue

                    # Excluir campos que nunca deben llegar al LLM
                    sensitive_fields = {
                        'api_key',
                        'password',
                        'secret',
                        'access_token',
                        'credential',
                    }

                    if field in sensitive_fields:
                        continue

                    if value is None:
                        continue

                    if isinstance(value, (list, dict)):
                        value = json.dumps(
                            value,
                            ensure_ascii=False,
                            default=str
                        )

                    doc[key] = str(value)[:350]

                if not doc or contaminated_document(doc):
                    continue
                # Es un ID de referencia del resultado de ESTA consulta, no un enlace externo.
                docs.append({'source_id': f'doc-{len(docs) + 1}', **doc})
            return docs
        finally:
            client.close()

    return await asyncio.to_thread(_search)


if __name__ == '__main__':
    async def main():
        result = await search_vehicles(' '.join(sys.argv[1:]) or 'SUV')
        print(json.dumps(result, indent=2, ensure_ascii=False))
    asyncio.run(main())
