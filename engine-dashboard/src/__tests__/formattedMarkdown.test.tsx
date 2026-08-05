import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { FormattedMarkdown } from '../components/workspace/FormattedMarkdown';

describe('FormattedMarkdown', () => {
  it('unwraps stringified JSON blobs automatically', () => {
    const rawJson = JSON.stringify({
      text: '### Clean Heading\nHere is the response content.',
      intent: 'chat',
    });
    render(<FormattedMarkdown content={rawJson} />);
    expect(screen.getByText('Clean Heading')).toBeDefined();
    expect(screen.getByText('Here is the response content.')).toBeDefined();
  });

  it('renders code blocks with copy buttons and language badges', () => {
    const markdown = '```typescript\nconst x: number = 42;\n```';
    render(<FormattedMarkdown content={markdown} />);
    expect(screen.getByText('TYPESCRIPT')).toBeDefined();
    expect(screen.getByText('const x: number = 42;')).toBeDefined();
    expect(screen.getByText('Copy')).toBeDefined();
  });

  it('formats headings, list items, and bold text correctly', () => {
    const markdown = '# Main Title\n- **Item 1:** Value\n- Item 2';
    render(<FormattedMarkdown content={markdown} />);
    expect(screen.getByText('Main Title')).toBeDefined();
    expect(screen.getByText('Item 1:')).toBeDefined();
    expect(screen.getByText('Item 2')).toBeDefined();
  });
});
