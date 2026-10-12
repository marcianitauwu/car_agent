from collections.abc import Mapping

from app.core.config import price


def measure_usage(response: object, role: str, model: str) -> dict:
    usage = getattr(response, 'usage_details', None)

    if isinstance(usage, Mapping):
        tokens_in = usage.get('input_token_count')
        tokens_out = usage.get('output_token_count')
    else:
        tokens_in = getattr(usage, 'input_token_count', None)
        tokens_out = getattr(usage, 'output_token_count', None)

    if role in ('policy', 'policy_review'):
        pin = price('POLICY_INPUT_PRICE_PER_M')
        pout = price('POLICY_OUTPUT_PRICE_PER_M')
        if pin is None:
            pin = price('ROUTER_INPUT_PRICE_PER_M')
        if pout is None:
            pout = price('ROUTER_OUTPUT_PRICE_PER_M')
    else:
        prefix = 'ROUTER' if role == 'orchestrator' else 'SPECIALIST'
        pin, pout = price(prefix + '_INPUT_PRICE_PER_M'), price(prefix + '_OUTPUT_PRICE_PER_M')
    cost_in = tokens_in * pin / 1_000_000 if tokens_in is not None and pin is not None else None
    cost_out = tokens_out * pout / 1_000_000 if tokens_out is not None and pout is not None else None
    return {'agent': role, 'model': model,
            'input_tokens': tokens_in, 'output_tokens': tokens_out,
            'input_cost_usd': cost_in, 'output_cost_usd': cost_out,
            'total_cost_usd': round(cost_in + cost_out, 10)
            if cost_in is not None and cost_out is not None else None}


def total_cost(measurements: list[dict]) -> dict:
    def add_field(field: str):
        values = [row.get(field) for row in measurements]
        return sum(values) if values and all(v is not None for v in values) else None
    return {'input_tokens': add_field('input_tokens'),
            'output_tokens': add_field('output_tokens'),
            'input_cost_usd': add_field('input_cost_usd'),
            'output_cost_usd': add_field('output_cost_usd'),
            'total_cost_usd': add_field('total_cost_usd')}
