import { parseSseFrame, splitSseFrames } from './sse';

test('retains incomplete SSE frame across chunks', () => {
  const first = splitSseFrames('', 'event: response_content\ndata: "hel');
  expect(first.frames).toEqual([]);

  const second = splitSseFrames(first.remainder, 'lo"\n\nevent: done\ndata: [DONE]\n\n');
  expect(second.frames).toEqual([
    { event: 'response_content', data: '"hello"' },
    { event: 'done', data: '[DONE]' }
  ]);
  expect(second.remainder).toBe('');
});

test('joins multiline SSE data', () => {
  expect(parseSseFrame('event: message\ndata: first\ndata: second')).toEqual({
    event: 'message',
    data: 'first\nsecond'
  });
});
