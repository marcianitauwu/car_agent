import React from 'react';
const number = n=>n===null || n===undefined?'N/D':n.toLocaleString('es-EC');
const usd = n=>n===null || n===undefined?'N/D':`$${n.toFixed(8)}`;
export default function CostPanel({measurements, total}) {
 return <section className="panel"><h3>Tokens y costos (USD)</h3>
 <table><thead><tr><th>Agente</th><th>Entrada</th><th>Salida</th><th>Costo</th></tr></thead>
 <tbody>{measurements.map((m,i)=><tr key={i}><td>{m.agent}</td><td>{number(m.input_tokens)}</td><td>{number(m.output_tokens)}</td><td>{usd(m.total_cost_usd)}</td></tr>)}</tbody></table>
 <div className="total"><span>Total: {number(total?.input_tokens)} entrada / {number(total?.output_tokens)} salida</span><strong>{usd(total?.total_cost_usd)}</strong></div>
 <p className="fine">N/D significa que faltan tokens reportados o precios configurados. No incluye la tarifa fija de Azure AI Search.</p>
 </section>;
}
