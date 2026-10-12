"""Busqueda centralizada en Azure AI Search; no existen conectores de Web ni herramientas externas."""
import asyncio
import json
import sys
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from app.core.config import setting, required
from app.services.security import contaminated_document


async def search_vehicles(query: str, top: int | None = None) -> list[dict]:
    required('AZURE_SEARCH_ENDPOINT', 'AZURE_SEARCH_API_KEY', 'AZURE_SEARCH_INDEX',
             'AZURE_SEARCH_ALLOWED_FIELDS')
    try:
        configured = int(setting('AZURE_SEARCH_TOP', '3'))
    except ValueError as exc:
        raise ValueError('AZURE_SEARCH_TOP debe ser entero') from exc
    n = max(1, min(3, int(top or configured)))
    allowed_fields = {k.strip().casefold() for k in setting('AZURE_SEARCH_ALLOWED_FIELDS').split(',') if k.strip()}
    if not allowed_fields:
        raise ValueError('Configura AZURE_SEARCH_ALLOWED_FIELDS')
    semantic = setting('AZURE_SEARCH_SEMANTIC_CONFIGURATION')

    def _search() -> list[dict]:
        client = SearchClient(
            endpoint=setting('AZURE_SEARCH_ENDPOINT'),
            index_name=setting('AZURE_SEARCH_INDEX'),
            credential=AzureKeyCredential(setting('AZURE_SEARCH_API_KEY')),
        )
        try:
            options = {'search_text': query[:700], 'top': n}
            if semantic:
                options.update(query_type='semantic', semantic_configuration_name=semantic)
            else:
                options['query_type'] = 'simple'
            results = client.search(**options)
            docs = []
            for raw in results:
                # No se confian campos arbitrarios del indice: autorizacion por nombre.
                doc = {}
                for key, value in dict(raw).items():
                    if key.casefold() not in allowed_fields or key.startswith('@'):
                        continue
                    if value is None:
                        continue
                    if isinstance(value, (list, dict)):
                        value = json.dumps(value, ensure_ascii=False, default=str)
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
