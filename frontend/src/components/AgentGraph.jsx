import React, { useMemo } from 'react';
import { ReactFlow, Background, Controls, MarkerType } from '@xyflow/react';

// Dos nodos de política = dos FASES de un mismo agente, NO dos agentes adicionales.
const nodesData = [
  ['user', 'Usuario', 250, 0],
  ['policy', 'Políticas · Entrada', 250, 88],
  ['orchestrator', 'Orquestador', 250, 185],
  ['comfort', 'Comodidad', 20, 295],
  ['consumption', 'Consumo', 250, 295],
  ['economy', 'Economía', 480, 295],
  ['search', 'Azure AI Search', 250, 405],
  ['policy_review', 'Políticas · Salida', 250, 510],
  ['final', 'Respuesta validada', 250, 610],
];
const edgesData = [
  ['user', 'policy'],
  ['policy', 'orchestrator'],
  ['policy', 'final'],
  ['orchestrator', 'comfort'],
  ['orchestrator', 'consumption'],
  ['orchestrator', 'economy'],
  ['comfort', 'search'],
  ['consumption', 'search'],
  ['economy', 'search'],
  ['search', 'policy_review'],
  ['policy_review', 'final'],
];
export default function AgentGraph({
  active = [],
  done = [],
  selected = [],
  blocked = false,
}) {
  const nodes = useMemo(
    () =>
      nodesData.map(([id, label, x, y]) => ({
        id,
        position: { x, y },
        data: { label },
        style: {
          background:
            blocked &&
            (id === 'final' ||
              (selected.length ? id === 'policy_review' : id === 'policy'))
              ? '#fee2e2'
              : active.includes(id)
                ? '#dbeafe'
                : done.includes(id)
                  ? '#dcfce7'
                  : '#fff',
          border: `2px solid ${blocked && (id === 'final' || (selected.length ? id === 'policy_review' : id === 'policy')) ? '#dc2626' : active.includes(id) ? '#b1c5f0' : done.includes(id) ? '#c2e4ce' : '#cbd5e1'}`,
          borderRadius: 12,
          padding: '13px 12px',
          width: 165,
          fontWeight: 700,
          boxShadow: active.includes(id) ? '0 0 15px #93c5fd' : 'none',
          color: '#12243a',
          textAlign: 'center',
          fontSize: 13,
        },
      })),
    [active, done, blocked],
  );
  const edges = useMemo(
    () =>
      edgesData.map(([source, target]) => {
        let highlighted = false;
        if (blocked) {
          highlighted =
            (source === 'user' && target === 'policy') ||
            (source === 'policy' && target === 'final' && !selected.length) ||
            (source === 'policy_review' &&
              target === 'final' &&
              selected.length > 0);
        } else {
          highlighted =
            (source === 'user' && target === 'policy') ||
            (source === 'policy' &&
              target === 'orchestrator' &&
              (done.includes('policy') || selected.length > 0)) ||
            (source === 'orchestrator' && selected.includes(target)) ||
            (target === 'search' && selected.includes(source)) ||
            (source === 'search' &&
              target === 'policy_review' &&
              selected.length > 0) ||
            (source === 'policy_review' &&
              target === 'final' &&
              done.includes('policy_review'));
        }
        return {
          id: `${source}-${target}`,
          source,
          target,
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
    [selected, active, done, blocked],
  );
  return (
    <div className="graph">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background color="#e2e8f0" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
