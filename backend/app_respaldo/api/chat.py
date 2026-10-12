"""SSE sobre POST; los eventos nacen del workflow, no de un temporizador."""
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.models import ChatRequest
from app.orchestration.workflow import build_workflow
from app.services.costs import total_cost

router = APIRouter(prefix='/api', tags=['Agentes'])


def sse(event: dict) -> str:
    return 'data: ' + json.dumps(event, ensure_ascii=False) + '\n\n'


@router.post('/chat/stream')
async def chat_stream(body: ChatRequest):
    async def generate():
        responses = {}
        measurements = []
        decision = []
        try:
            workflow = build_workflow()
            async for event in workflow.run(body.message, stream=True):
                if event.type != 'output' or not isinstance(event.data, dict):
                    continue
                item = event.data
                if item.get('type') == 'route_selected':
                    decision = item['agents']
                if item.get('type') == 'agent_done':
                    responses[item['agent']] = item['answer']
                if item.get('type') == 'usage':
                    measurements.append(item['usage'])
                yield sse(item)
            if not decision:
                raise RuntimeError('El workflow finalizo sin una decision de ruta')
            answer = '\n\n'.join(f'### {name.upper()}\n{responses.get(name, "El agente no devolvio resultados")}' for name in decision)
            yield sse({'type': 'final', 'answer': answer,
                       'selected_agents': decision,
                       'costs': total_cost(measurements), 'measurements': measurements})
        except Exception as exc:
            # Solo entorno de desarrollo; no exponer detalles internos en produccion.
            yield sse({'type': 'error', 'message': str(exc)})

    return StreamingResponse(generate(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
