import React, { useMemo, useLayoutEffect, useRef, useState } from 'react';
import { ReactFlow, Background, Controls, MarkerType, BaseEdge, Position } from '@xyflow/react';

function BypassEdge({ sourceX, sourceY, targetX, targetY, markerEnd, style }) {
  const fromRight = sourceX > targetX;
  const direction = fromRight ? -1 : 1;
  const lane = fromRight ? Math.max(sourceX, targetX + 130) : Math.min(sourceX, targetX - 130);
  const endX = targetX - direction * 82.5;
  const endY = targetY + 30;
  const path = `M ${sourceX} ${sourceY}
    C ${lane} ${sourceY + (endY - sourceY) * 0.55},
      ${lane} ${endY}, ${endX} ${endY}`;
  return <BaseEdge path={path} markerEnd={markerEnd} style={style} />;
}
const edgeTypes = { bypass: BypassEdge };

// Políticas aparece en sus dos fases. Usuario y Respuesta son etapas del flujo.
const nodesData = [
  ['user', 'Usuario', 250, 0],
  ['policy', 'Políticas · Entrada', 250, 115],
  ['orchestrator', 'Orquestador', 250, 205],
  ['comfort', 'Comodidad', 20, 305],
  ['consumption', 'Consumo', 250, 305],
  ['economy', 'Economía', 480, 305],
  ['synthesizer', 'Sintetizador', 250, 505],
  ['policy_review', 'Políticas · Salida', 250, 605],
  ['final', 'Respuesta', 250, 705],
];
const edgesData = [
  ['user', 'policy'],
  ['policy', 'orchestrator'],
  ['orchestrator', 'comfort'],
  ['orchestrator', 'consumption'],
  ['orchestrator', 'economy'],
  ['comfort', 'synthesizer'],
  ['consumption', 'synthesizer'],
  ['economy', 'synthesizer'],
  ['comfort', 'policy_review'],
  ['consumption', 'policy_review'],
  ['economy', 'policy_review'],
  ['synthesizer', 'policy_review'],
  ['policy_review', 'final'],
];
export default function AgentGraph({
  active = [],
  done = [],
  selected = [],
  blocked = false,
  question = '',
  runId = 0,
}) {
  const containerRef = useRef(null);
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 0.5 });
  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const center = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (!width || !height) return;
      // Límites conocidos de los nodos: x=20..645, y=0..765.
      // No depende de mediciones asíncronas de React Flow ni de un viewport anterior.
      const zoom = Math.max(0.1, Math.min((width - 32) / 625, (height - 32) / 765, 1));
      setViewport({ x: (width - 625 * zoom) / 2 - 20 * zoom,
                    y: (height - 765 * zoom) / 2, zoom });
    };
    center();
    const observer = new ResizeObserver(center);
    observer.observe(container);
    return () => observer.disconnect();
  }, [runId]);
  const agentActive = (id) => active.includes(id);
  const agentDone = (id) => done.includes(id);
  const pairedAgent = (id) => selected.length === 2 && selected.includes(id);
  const blockedNode = (id) => blocked && (id === 'final' || id === (selected.length ? 'policy_review' : 'policy'));
  const nodes = useMemo(
    () =>
      nodesData.map(([id, label, x, y]) => ({
        id,
        position: { x, y },
        width: 165,
        height: id === 'user' ? 85 : 60,
        // Mantiene los puntos de conexión al regenerar los nodos por cada evento.
        handles: [
          { type: 'target', position: Position.Top, x: 79.5, y: -3, width: 6, height: 6 },
          { type: 'source', position: Position.Bottom, x: 79.5,
            y: (id === 'user' ? 85 : 60) - 3, width: 6, height: 6 },
        ],
        data: { label: id === 'user' && question ? (
          <div title={question}><div>Usuario</div><div className="graph-question">{question}</div></div>
        ) : label },
        style: {
          background:
            blockedNode(id)
              ? '#fee2e2'
              : id === 'user'
                ? '#ede9fe'
                : id === 'final' && done.includes('final')
                  ? '#fef9c3'
              : agentActive(id)
                ? pairedAgent(id) ? '#fed7aa' : '#dbeafe'
                : agentDone(id)
                  ? pairedAgent(id) ? '#ffedd5' : '#dcfce7'
                  : pairedAgent(id) ? '#fff7ed' : '#f1f5f9',
          border: `2px solid ${blockedNode(id) ? '#dc2626' : id === 'user' ? '#a78bfa' : id === 'final' && done.includes('final') ? '#facc15' : pairedAgent(id) ? '#fb923c' : agentActive(id) ? '#b1c5f0' : agentDone(id) ? '#c2e4ce' : '#cbd5e1'}`,
          borderRadius: 12,
          padding: '13px 12px',
          width: 165,
          height: id === 'user' ? 85 : 60,
          fontWeight: 700,
          boxShadow: agentActive(id) ? pairedAgent(id) ? '0 0 15px #fdba74' : '0 0 15px #93c5fd' : 'none',
          color: '#12243a',
          textAlign: 'center',
          fontSize: 13,
        },
      })),
    [active, done, blocked, selected, question],
  );
  const edges = useMemo(
    () =>
      edgesData.filter(([source, target]) => !(selected.includes(source) && target === 'policy_review' && selected.length !== 1)
        && !(target === 'policy_review' && ['comfort', 'consumption', 'economy'].includes(source) && !selected.includes(source)))
      .map(([source, target]) => {
        let highlighted = false;
        highlighted =
            (source === 'user' && Boolean(question)) ||
            (source === 'policy' &&
              target === 'orchestrator' &&
              (done.includes('policy') || selected.length > 0)) ||
            (source === 'orchestrator' && selected.includes(target)) ||
            (selected.includes(source) && target === 'policy_review' &&
              (active.includes('policy_review') || done.includes('policy_review'))) ||
            (selected.includes(source) && target === 'synthesizer' &&
              (active.includes('synthesizer') || done.includes('synthesizer'))) ||
            (source === 'synthesizer' && target === 'policy_review' && done.includes('synthesizer')) ||
            (source === 'policy_review' && target === 'final' && done.includes('policy_review'));
        return {
          id: `${source}-${target}`,
          source,
          target,
          type: selected.includes(source) && target === 'policy_review' ? 'bypass' : 'default',
          animated: highlighted && active.length > 0,
          style: {
            stroke: highlighted ? (blocked ? '#dc2626' : '#86a0d8') : '#cbd5e1',
            strokeWidth: highlighted ? 2.8 : 1.5,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: highlighted ? (blocked ? '#dc2626' : '#b7c2da') : '#cbd5e1',
          },
        };
      }),
    [selected, active, done, blocked, question],
  );
  return (
    <>
    {question && <p className="graph-question-summary"><strong>Consulta:</strong> {question}</p>}
    <div className="graph" ref={containerRef}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        edgeTypes={edgeTypes}
        viewport={viewport}
        onViewportChange={setViewport}
        minZoom={0.1}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background color="#e2e8f0" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
    </>
  );
}
