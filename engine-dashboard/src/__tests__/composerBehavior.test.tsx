import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Composer } from '../components/workspace/Composer';
import { RuntimeProvider } from '../runtime/RuntimeContext';

// We just test basic rendering to verify it doesn't crash, 
// a full integration test with the context is better.
describe('Composer', () => {
  it('renders correctly', () => {
    render(
      <RuntimeProvider>
        <Composer />
      </RuntimeProvider>
    );
    expect(screen.getByTestId('composer-input')).toBeDefined();
  });
});
