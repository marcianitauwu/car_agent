"""Streaming SSE: datos sensibles y borradores NUNCA se entregan sin revisión."""
import asyncio
import json
import logging
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.schemas.models import ChatRequest
from app.orchestration.workflow import build_workflow
from app.agents.policy_agent import review_answers
from app.services.audit import record_incident
from app.services.costs import total_cost
from app.services.rate_limit import limiter, concurrency_slots
from app.services.security import refusal

router = APIRouter(prefix='/api', tags=['Agentes'])
log = logging.getLogger(__name__)


def sse(event: dict) -> str:
    return 'data: ' + json.dumps(event, ensure_ascii=False) + '\n\n'


@router.post('/chat/stream')
async def chat_stream(body: ChatRequest, request: Request):
    request_id = uuid4().hex
    client_id = request.client.host if request.client else 'unknown'
    allowed, retry_after = await limiter.check(client_id)
    if not allowed:
        record_incident(request_id, 'rate_limit', 'rate_limited')
        raise HTTPException(
            status_code=429,
            detail=f'Demasiadas solicitudes. Intenta nuevamente en {retry_after} segundos.',
            headers={'Retry-After': str(retry_after)},
        )
    try:
        await asyncio.wait_for(concurrency_slots.acquire(), timeout=0.1)
    except TimeoutError:
        record_incident(request_id, 'concurrency_limit', 'rate_limited')
        raise HTTPException(status_code=429, detail='Sistema ocupado. Intenta de nuevo.') from None

    async def generate():
        responses: dict[str, dict] = {}
        measurements: list[dict] = []
        decision: list[str] = []
        denied: dict | None = None
        try:
            workflow = build_workflow()
            async for event in workflow.run(body.message, stream=True):
                if event.type != 'output' or not isinstance(event.data, dict):
                    continue
                item = event.data
                kind = item.get('type')
                if kind == 'internal_result':
                    # Solo servidor: no exponer texto no validado ni documentos de Azure.
                    responses[item['agent']] = item
                    continue
                if kind == 'policy_blocked':
                    denied = item
                    record_incident(request_id, item['category'], 'blocked')
                elif kind == 'route_selected':
                    decision = item['agents']
                elif kind == 'usage':
                    measurements.append(item['usage'])
                yield sse(item)

            if denied:
                yield sse({'type': 'final', 'answer': denied['message'],
                           'selected_agents': [], 'blocked': True,
                           'costs': total_cost(measurements), 'measurements': measurements})
                return
            if not decision:
                raise RuntimeError('No se produjo ruta valida')
            ordered = [responses[key] for key in decision if key in responses]
            if len(ordered) != len(decision) or any(x.get('invalid') for x in ordered):
                record_incident(request_id, 'unsafe_output', 'blocked_output')
                yield sse({'type': 'policy_blocked', 'category': 'unsafe_output',
                           'message': refusal('unsafe_output')})
                yield sse({'type': 'final', 'answer': refusal('unsafe_output'),
                           'selected_agents': decision, 'blocked': True,
                           'costs': total_cost(measurements), 'measurements': measurements})
                return

            # Sin evidencia, solo existe una respuesta fija del servidor (no un hecho del LLM).
            # Tampoco hace falta pagar la revisión LLM de contenido que no fue generado.
            if any(not x['documents'] for x in ordered):
                yield sse({'type': 'final',
                           'answer': 'No se encontraron datos suficientes en Azure AI Search para responder con evidencia a todos los criterios solicitados.',
                           'selected_agents': decision, 'blocked': False,
                           'costs': total_cost(measurements), 'measurements': measurements})
                return

            yield sse({'type': 'node_start', 'agent': 'policy_review'})
            try:
                verdict, usage = await review_answers(body.message, ordered)
            except Exception:
                # Si el revisor falla o devuelve JSON inválido, bloqueamos.
                record_incident(request_id, 'unknown', 'policy_failure')
                yield sse({'type': 'policy_blocked', 'category': 'unknown',
                           'message': refusal('unknown')})
                yield sse({'type': 'final', 'answer': refusal('unknown'),
                           'selected_agents': decision, 'blocked': True,
                           'costs': total_cost(measurements), 'measurements': measurements})
                return
            measurements.append(usage)
            yield sse({'type': 'usage', 'usage': usage})
            if not verdict.approved:
                record_incident(request_id, verdict.category, 'blocked_output')
                yield sse({'type': 'policy_blocked', 'category': verdict.category,
                           'message': refusal(verdict.category)})
                yield sse({'type': 'final', 'answer': refusal(verdict.category),
                           'selected_agents': decision, 'blocked': True,
                           'costs': total_cost(measurements), 'measurements': measurements})
                return
            yield sse({'type': 'policy_review_done'})
            answer = '\n\n'.join(f'### {key.upper()}\n{responses[key]["answer"]}' for key in decision)
            yield sse({'type': 'final', 'answer': answer, 'selected_agents': decision,
                       'blocked': False, 'costs': total_cost(measurements),
                       'measurements': measurements})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # No enviar errores de SDK, trazas, rutas o secretos al navegador.
            log.error('Error interno de solicitud %s: %s', request_id, type(exc).__name__)
            record_incident(request_id, 'unknown', 'workflow_failure')
            yield sse({'type': 'error', 'message':
                       'No se pudo completar la consulta. Revisa los logs del servidor.'})
        finally:
            concurrency_slots.release()

    return StreamingResponse(generate(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no',
                                      'X-Content-Type-Options': 'nosniff'})
