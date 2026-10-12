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
  usage: 'Tokens recibidos',
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
                {e.agent ||
                  e.category ||
                  e.reason ||
                  (e.agents || []).join(', ') ||
                  (e.documents !== undefined
                    ? `${e.documents} documentos`
                    : '')}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
