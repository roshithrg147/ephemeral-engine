import { describe, it, expect } from 'vitest';
import { parseSSEChunk } from '../runtime/sseParser';

describe('SSE Parser', () => {
  it('parses valid chunks', () => {
    const raw = `data: {"id": "1", "type": "test"}\n\n`;
    const events = parseSSEChunk(raw);
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ id: '1', type: 'test' });
  });

  it('handles multiline data within a chunk', () => {
    const raw = `data: {"id": "1", \ndata: "type": "test"}\n\n`;
    const events = parseSSEChunk(raw);
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ id: '1', type: 'test' });
  });

  it('ignores malformed json', () => {
    const raw = `data: {bad_json}\n\n`;
    const events = parseSSEChunk(raw);
    expect(events).toHaveLength(0);
  });

  it('handles multiple chunks', () => {
    const raw = `data: {"id": "1"}\n\ndata: {"id": "2"}\n\n`;
    const events = parseSSEChunk(raw);
    expect(events).toHaveLength(2);
    expect(events[0].id).toBe('1');
    expect(events[1].id).toBe('2');
  });

  it('returns empty array on empty string', () => {
    expect(parseSSEChunk('')).toHaveLength(0);
    expect(parseSSEChunk('\n\n')).toHaveLength(0);
  });
});
