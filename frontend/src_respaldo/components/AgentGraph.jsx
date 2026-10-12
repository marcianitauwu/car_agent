import React, {useMemo} from 'react';
import { ReactFlow, Background, Controls, MarkerType } from '@xyflow/react';

const nodesData = [
 ['user','Usuario',235,10], ['orchestrator','Orquestador',235,100],
 ['comfort','Comodidad',25,220], ['consumption','Consumo',235,220], ['economy','Economía',445,220],
 ['search','Azure AI Search',235,345], ['final','Respuesta',235,465]
];
const edgesData = [
 ['user','orchestrator'],['orchestrator','comfort'],['orchestrator','consumption'],
 ['orchestrator','economy'],['comfort','search'],['consumption','search'],['economy','search'],
 ['search','final']
];
export default function AgentGraph({active, done, selected}) {
 const nodes = useMemo(()=>nodesData.map(([id,label,x,y])=>({
   id,position:{x,y},data:{label},
   style:{background:active.includes(id)?'#d7c4f3':done.includes(id)?'#d7f0e0':'#ffffff',
   border:`2px solid ${active.includes(id)?'#ec8bdf':done.includes(id)?'#9de6b8':'#e7e9db'}`,
   borderRadius:12, padding:'13px 20px',width:155,fontWeight:700,boxShadow:active.includes(id)?'0 0 15px #93c5fd':'none',
   color:'#12243a',textAlign:'center'}
 })),[active,done]);
 const edges = useMemo(()=>edgesData.map(([source,target])=>{
   const selectedPath = source==='user' || target==='final' || source==='search' ||
     (source==='orchestrator'&&selected.includes(target)) || (target==='search'&&selected.includes(source));
   const highlight = selected.length>0 && selectedPath;
   return {id:`${source}-${target}`,source,target,animated:highlight && active.length>0,
    style:{stroke:highlight?'#2563eb':'#cbd5e1',strokeWidth:highlight?2.8:1.5},
    markerEnd:{type:MarkerType.ArrowClosed,color:highlight?'#a454da':'#cbd5e1'}};
 }),[selected,active]);
 return <div className="graph"><ReactFlow nodes={nodes} edges={edges} fitView fitViewOptions={{padding:.15}}
   nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}><Background c
   olor="#e2e8f0"/><Controls showInteractive={false}/></ReactFlow></div>;
}
