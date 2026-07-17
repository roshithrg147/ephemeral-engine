export function splitSseFrames(buffer, chunk) {
  const combined = buffer + chunk;
  const parts = combined.split(/\r?\n\r?\n/);
  const remainder = parts.pop() || '';
  const frames = parts.map(parseSseFrame).filter(Boolean);
  return { frames, remainder };
}

export function parseSseFrame(frame) {
  let event = 'message';
  const data = [];

  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      data.push(line.slice(5).trimStart());
    }
  }

  return data.length ? { event, data: data.join('\n') } : null;
}
