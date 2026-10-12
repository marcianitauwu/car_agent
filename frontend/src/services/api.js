const API = '';

// fetch + ReadableStream porque EventSource no permite POST con cuerpo JSON.
export async function askAgents(message, onEvent) {
  const response = await fetch(`${API}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Error HTTP ${response.status}`);
  }
  if (!response.body) throw new Error('El navegador no admite streaming');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index;
    while ((index = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, index).trim();
      buffer = buffer.slice(index + 2);
      const data = block
        .split('\n')
        .filter((x) => x.startsWith('data:'))
        .map((x) => x.slice(5).trim())
        .join('');
      if (data) onEvent(JSON.parse(data));
    }
  }
}
