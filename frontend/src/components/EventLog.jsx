import React from 'react';
const translations = {
  node_start: 'Inició etapa',
  policy_allowed: 'Políticas: autorizada',
  policy_blocked: 'Políticas: bloqueada',
  policy_review_done: 'Respuesta validada',
  route_selected: 'Ruta seleccionada',
  search_started: 'Consultando Azure AI Search',
  search_done: 'Búsqueda terminada',
  agent_done: 'Agente terminó',
  collaboration_contribution: 'Especialista aportó a la respuesta conjunta',
  collaboration_started: 'Especialista lee y contrasta la respuesta del compañero',
  synthesis_skipped: 'Síntesis omitida',
  usage: 'Tokens recibidos',
  answer_repair: 'Corrigiendo comparación con evidencia',
  final: 'Respuesta final',
  error: 'Error',
};
export default function EventLog({ events }) {
  return (
    <section className="panel logpanel">
      <h3>Registro de eventos reales</h3>
      <div className="log">
        {events.length === 0 ? (
          <p className="muted">
            Envía una consulta para observar el recorrido.
          </p>
        ) : (
          events.map((e, i) => (
            <div key={i} className="logentry">
              <span className="time">{e.time}</span>
              <strong>{translations[e.type] || e.type}</strong>
              <span>
                {({synthesizer: 'Sintetizador', exchange: 'Intercambio de análisis'}[e.agent] || e.agent) ||
                  e.category ||
                  ({single_agent: 'Intervino un solo especialista',
                    insufficient_evidence: 'Faltan documentos o una respuesta válida'}[e.reason] || e.reason) ||
                  (e.agents || []).join(', ') ||
                  (e.documents !== undefined
                    ? `${e.documents} documentos`
                    : '')}
              </span>
              {e.detail && <span>{e.detail}</span>}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
