export function parseSSEChunk(raw: string) {
  if (!raw) return [];
  const chunks = raw.split('\n\n');
  const events: any[] = [];
  
  for (const chunk of chunks) {
    if (!chunk.trim()) continue;
    
    const lines = chunk.split('\n');
    let dataStr = '';
    
    for (const line of lines) {
      if (line.startsWith('data:')) {
        dataStr += line.substring(5).trim();
      }
    }
    
    if (dataStr) {
      try {
        const event = JSON.parse(dataStr);
        events.push(event);
      } catch (e) {
        // Skip malformed JSON
      }
    }
  }
  
  return events;
}
