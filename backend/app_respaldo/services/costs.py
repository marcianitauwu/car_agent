"""No estimar tokens si el proveedor no reporto usage."""
from app.core.config import price


def measure_usage(response: object, role: str, model: str) -> dict:
    usage = getattr(response, 'usage_details', None)
    tokens_in = getattr(usage, 'input_token_count', None) if usage is not None else None
    tokens_out = getattr(usage, 'output_token_count', None) if usage is not None else None
    prefix = 'ROUTER' if role == 'orchestrator' else 'SPECIALIST'
    pin = price(prefix + '_INPUT_PRICE_PER_M')
    pout = price(prefix + '_OUTPUT_PRICE_PER_M')
    cost_in = tokens_in * pin / 1_000_000 if tokens_in is not None and pin is not None else None
    cost_out = tokens_out * pout / 1_000_000 if tokens_out is not None and pout is not None else None
    return {
        'agent': role, 'model': model,
        'input_tokens': tokens_in, 'output_tokens': tokens_out,
        'input_cost_usd': cost_in, 'output_cost_usd': cost_out,
        'total_cost_usd': round(cost_in + cost_out, 10) if cost_in is not None and cost_out is not None else None,
    }


def total_cost(measurements: list[dict]) -> dict:
    """N/D si falta cualquier cifra, para no fingir costo real cero."""
    def add_field(field: str):
        values = [row[field] for row in measurements]
        return sum(values) if values and all(v is not None for v in values) else None

    return {
        'input_tokens': add_field('input_tokens'),
        'output_tokens': add_field('output_tokens'),
        'input_cost_usd': add_field('input_cost_usd'),
        'output_cost_usd': add_field('output_cost_usd'),
        'total_cost_usd': add_field('total_cost_usd'),
    }
