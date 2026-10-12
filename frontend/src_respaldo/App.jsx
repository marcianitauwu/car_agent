import React,{useState,useRef} from 'react';
import {CarFront, Send, RotateCcw} from 'lucide-react';
import AgentGraph from './components/AgentGraph.jsx';
import CostPanel from './components/CostPanel.jsx';
import EventLog from './components/EventLog.jsx';
import {askAgents} from './services/api.js';

export default function App(){
 const [message,setMessage]=useState('¿Qué vehículo consume menos gasolina y es económico?');
 const [events,setEvents]=useState([]);
 const [active,setActive]=useState([]);
 const [done,setDone]=useState([]);
 const [selected,setSelected]=useState([]);
 const [measurements,setMeasurements]=useState([]);
 const [total,setTotal]=useState(null);
 const [answer,setAnswer]=useState('');
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const searching=useRef(new Set());

 function handleEvent(event){
  setEvents(old=>[...old,{...event,time:new Date().toLocaleTimeString('es-EC')}]);
  if(event.type==='node_start'){
   setActive(old=>[...new Set([...old,event.agent])]);
  }
  if(event.type==='route_selected'){
   setSelected(event.agents);setDone(old=>[...new Set([...old,'orchestrator'])]);
   setActive(old=>old.filter(id=>id!=='orchestrator'));
  }
  if(event.type==='search_started') {
   searching.current.add(event.agent);
   setActive(old=>[...new Set([...old,'search'])]);
  }
  if(event.type==='search_done') {
   searching.current.delete(event.agent);
   if(searching.current.size===0) setActive(old=>old.filter(id=>id!=='search'));
   setDone(old=>[...new Set([...old,'search'])]);
  }
  if(event.type==='agent_done') {
   setActive(old=>old.filter(id=>id!==event.agent));
   setDone(old=>[...new Set([...old,event.agent])]);
  }
  if(event.type==='usage') setMeasurements(old=>[...old,event.usage]);
  if(event.type==='final'){
   setAnswer(event.answer);setTotal(event.costs);setActive([]);
   setDone(old=>[...new Set([...old,'final'])]);
  }
  if(event.type==='error') {setError(event.message);setActive([]);}
 }
 async function submit(e){
  e.preventDefault(); if(busy||message.trim().length<3)return;
  searching.current.clear();setEvents([]);setActive([]);setDone([]);setSelected([]);setMeasurements([]);setTotal(null);setAnswer('');setError('');setBusy(true);
  try{await askAgents(message.trim(),handleEvent);}catch(err){setError(err.message);}finally{setBusy(false);}
 }
 return <main className="app"><header className="top"><div className="brand"><CarFront size={28}/><div><h1>Car Agents</h1><p>Microsoft Agent Framework + Azure AI Search</p></div></div><span className="pill">Dashboard multiagente</span></header>
 <section className="question panel"><h2>Consulta de vehículos</h2><form onSubmit={submit}><textarea rows="2" maxLength={1000} value={message} onChange={e=>setMessage(e.target.value)} placeholder="Escribe una pregunta sobre vehículos"/><button disabled={busy||message.trim().length<3}><Send size={17}/>{busy?'Analizando...':'Preguntar'}</button></form><p className="fine">Ejemplo: “¿Qué SUV es más cómoda y tiene buen rendimiento?”</p></section>
 <div className="layout"><section className="panel"><h3>Ruta de ejecución</h3><AgentGraph active={active} done={done} selected={selected}/><p className="fine">Azul: ejecutando · Verde: completado · Gris: sin intervenir.</p></section>
 <aside><CostPanel measurements={measurements} total={total}/><EventLog events={events}/></aside></div>
 {(answer||error)&&<section className="panel answer"><h3>Resultado</h3>{error?<p className="error">{error}</p>:<pre>{answer}</pre>}</section>}
 </main>;
}
