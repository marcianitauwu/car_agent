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
from app.services.grounded_comparison import grounded_comparison
from app.services.rate_limit import limiter, concurrency_slots
from app.services.security import refusal, review_reason

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
            needs_joint = (len(ordered) == len(decision) and len(decision) == 2
                           and all(x['documents'] and not x.get('invalid') for x in ordered))
            if needs_joint:
                if 'synthesizer' in responses:
                    ordered.append(responses['synthesizer'])
            expected = len(decision) + int(needs_joint)
            if len(ordered) != expected or any(x.get('invalid') for x in ordered):
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
            # Una sola recuperacion; nunca convertir un rechazo en aprobacion local.
            if (not verdict.approved and getattr(verdict, 'reason_code', '') in
                    ('contradictory_evidence', 'unsupported_claim')):
                affected = set(getattr(verdict, 'affected_agents', []))
                repaired = []
                changed = False
                for item in ordered:
                    replacement = (grounded_comparison(item, body.message)
                                   if item['agent'] in affected else None)
                    repaired.append(replacement or item)
                    changed = changed or replacement is not None
                if changed:
                    yield sse({'type': 'answer_repair',
                               'detail': 'Recalculando la comparación con los datos recuperados y revisando de nuevo.'})
                    try:
                        retry_verdict, retry_usage = await review_answers(body.message, repaired)
                    except Exception:
                        # Se conserva el rechazo original si la nueva revision falla.
                        pass
                    else:
                        measurements.append(retry_usage)
                        yield sse({'type': 'usage', 'usage': retry_usage})
                        verdict = retry_verdict
                        ordered = repaired
                        responses.update({item['agent']: item for item in ordered})
            if not verdict.approved:
                reason_code = getattr(verdict, 'reason_code', 'unspecified')
                affected_agents = getattr(verdict, 'affected_agents', [])
                detail = review_reason(reason_code, affected_agents)
                message = refusal(verdict.category) + ' ' + detail
                record_incident(request_id, verdict.category, 'blocked_output', reason_code, affected_agents)
                yield sse({'type': 'policy_blocked', 'category': verdict.category,
                           'reason_code': reason_code, 'affected_agents': affected_agents,
                           'detail': detail, 'message': message})
                yield sse({'type': 'final', 'answer': message,
                           'selected_agents': decision, 'blocked': True,
                           'costs': total_cost(measurements), 'measurements': measurements})
                return
            yield sse({'type': 'policy_review_done'})
            answer = '\n\n'.join(f'### {key.upper()}\n{responses[key]["answer"]}' for key in decision)
            joint = next((item for item in ordered if item['agent'] == 'synthesizer'), None)
            if joint:
                answer += '\n\n### Respuesta conjunta\n' + joint['answer']
            yield sse({'type': 'final', 'answer': answer, 'selected_agents': decision,
                       'blocked': False, 'costs': total_cost(measurements),
                       'measurements': measurements,
                       'search_results': [
                           {'agent': key, 'documents': responses[key]['documents']}
                           for key in decision
                       ]})
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
