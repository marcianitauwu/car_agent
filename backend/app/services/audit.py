"""Auditoria minima: sin prompts, claves, respuestas, documentos ni direcciones IP."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from app.core.config import BACKEND_ROOT

log = logging.getLogger(__name__)
VALID_EVENTS = {'blocked', 'blocked_output', 'rate_limited', 'policy_failure', 'workflow_failure'}


def record_incident(request_id: str, category: str, stage: str,
                    reason_code: str | None = None, affected_agents: list[str] | None = None) -> None:
    if stage not in VALID_EVENTS:
        return
    path = BACKEND_ROOT / 'logs' / 'policy_incidents.jsonl'
    entry = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
             'request_id': request_id, 'event': stage, 'category': category[:40]}
    if reason_code:
        from app.services.security import REVIEW_REASONS
        if reason_code in REVIEW_REASONS:
            entry['reason_code'] = reason_code
    if affected_agents:
        entry['affected_agents'] = [key for key in affected_agents
                                   if key in {'comfort', 'consumption', 'economy', 'synthesizer'}]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except OSError:
        log.warning('No se pudo escribir registro de seguridad (sin datos sensibles)')
