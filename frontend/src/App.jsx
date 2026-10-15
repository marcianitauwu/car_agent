import React, { useState, useRef } from 'react';
import { CarFront, Send } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import AgentGraph from './components/AgentGraph.jsx';
import CostPanel from './components/CostPanel.jsx';
import EventLog from './components/EventLog.jsx';
import { askAgents } from './services/api.js';

// Las respuestas son datos no confiables: sin HTML, imágenes externas ni enlaces activos.
const markdownComponents = {
  a: ({ children }) => <span>{children}</span>,
  img: () => null,
};

export default function App() {
  const [message, setMessage] = useState('');
  const [submittedQuestion, setSubmittedQuestion] = useState('');
  const [graphRun, setGraphRun] = useState(0);
  const [events, setEvents] = useState([]);
  const [active, setActive] = useState([]);
  const [done, setDone] = useState([]);
  const [selected, setSelected] = useState([]);
  const [measurements, setMeasurements] = useState([]);
  const [total, setTotal] = useState(null);
  const [answer, setAnswer] = useState('');
  const visibleAnswer = answer.replace(/[ \t]*\[doc-\d+\]/gi, '');
  const [searchResults, setSearchResults] = useState([]);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const searching = useRef(new Set());

  function handleEvent(event) {
    setEvents((old) => [
      ...old,
      { ...event, time: new Date().toLocaleTimeString('es-EC') },
    ]);
    if (event.type === 'node_start')
      setActive((old) => [...new Set([...old, event.agent])]);
    if (event.type === 'policy_allowed') {
      setActive((old) => old.filter((id) => id !== 'policy'));
      setDone((old) => [...new Set([...old, 'policy'])]);
    }
    if (event.type === 'policy_blocked') {
      setBlocked(true);
      setActive([]);
      if (event.message) setAnswer(event.message);
    }
    if (event.type === 'route_selected') {
      setSelected(event.agents);
      setDone((old) => [...new Set([...old, 'orchestrator'])]);
      setActive((old) => old.filter((id) => id !== 'orchestrator'));
    }
    if (event.type === 'search_started') {
      searching.current.add(event.agent);
      setActive((old) => [...new Set([...old, 'search'])]);
    }
    if (event.type === 'search_done') {
      searching.current.delete(event.agent);
      if (searching.current.size === 0)
        setActive((old) => old.filter((id) => id !== 'search'));
      setDone((old) => [...new Set([...old, 'search'])]);
    }
    if (event.type === 'agent_done') {
      setActive((old) => old.filter((id) => id !== event.agent));
      setDone((old) => [...new Set([...old, event.agent])]);
    }
    if (event.type === 'collaboration_started') {
      setActive((old) => [...new Set([...old, event.agent])]);
      setDone((old) => old.filter((id) => id !== event.agent));
    }
    if (event.type === 'collaboration_contribution') {
      setActive((old) => old.filter((id) => id !== event.agent));
      setDone((old) => [...new Set([...old, event.agent])]);
    }
    if (event.type === 'policy_review_done') {
      setActive((old) => old.filter((id) => id !== 'policy_review'));
      setDone((old) => [...new Set([...old, 'policy_review'])]);
    }
    if (event.type === 'usage') setMeasurements((old) => [...old, event.usage]);
    if (event.type === 'final') {
      setAnswer(event.answer);
      setSearchResults(event.blocked ? [] : (event.search_results || []));
      setTotal(event.costs);
      setActive([]);
      setBlocked(Boolean(event.blocked));
      setDone((old) => [...new Set([...old, 'final'])]);
    }
    if (event.type === 'error') {
      setError(event.message);
      setActive([]);
    }
  }
  async function submit(e) {
    e.preventDefault();
    if (busy || message.trim().length < 3) return;
    searching.current.clear();
    setEvents([]);
    setActive([]);
    setDone(['user']);
    setSubmittedQuestion(message.trim());
    setGraphRun((old) => old + 1);
    setSelected([]);
    setMeasurements([]);
    setTotal(null);
    setAnswer('');
    setSearchResults([]);
    setError('');
    setBlocked(false);
    setBusy(true);
    try {
      await askAgents(message.trim(), handleEvent);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app">
      <header className="top">
        <div className="brand">
          <CarFront size={28} />
          <div>
            <h1>Car Agents</h1>
          </div>
        </div>
      </header>
      <section className="question panel">
        <h2>Consulta de vehículos</h2>
        <form onSubmit={submit}>
          <textarea
            rows="2"
            maxLength={700}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Escribe una pregunta sobre vehículos"
          />
          <button disabled={busy || message.trim().length < 3}>
            <Send size={17} />
            {busy ? 'Analizando...' : 'Preguntar'}
          </button>
        </form>

      </section>
      <div className="layout">
        <section className="panel">
          <h3>Ruta de ejecución y seguridad</h3>
          <AgentGraph
            active={active}
            done={done}
            selected={selected}
            blocked={blocked}
            question={submittedQuestion}
            runId={graphRun}
          />
          <p className="fine">
            Azul: ejecutando · Verde: completado · Rojo: bloqueado · Gris: no intervino.
            {' '}
          </p>
        </section>
        <aside>
          <CostPanel measurements={measurements} total={total} />
          <EventLog events={events} />
        </aside>
      </div>
      {(answer || error) && (
        <section className="panel answer">
          <h3>{blocked ? 'Solicitud bloqueada' : 'Resultado'}</h3>
          {error ? (
            <p className="error">{error}</p>
          ) : (
            <div className="markdown-answer">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                skipHtml
                components={markdownComponents}
              >
                {visibleAnswer}
              </ReactMarkdown>
            </div>
          )}
          {!error && !blocked && searchResults.length > 0 && (
            <div className="search-evidence">
              <h3>Documentos de Azure AI Search</h3>
              <p className="fine">
                JSON utilizado por cada agente para responder, después del filtrado de seguridad.
              </p>
              {searchResults.map(({ agent, documents }) => (
                <details key={agent}>
                  <summary>{({ comfort: 'Comodidad', consumption: 'Consumo', economy: 'Economía' })[agent] || agent} · {documents.length} documentos · Ver JSON</summary>
                  <pre><code>{JSON.stringify(documents, null, 2)}</code></pre>
                </details>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
