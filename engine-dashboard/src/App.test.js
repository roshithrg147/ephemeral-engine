import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';

function providerResponse(url) {
  if (String(url).endsWith('/api/session/list')) {
    return Promise.resolve({
      ok: true,
      json: async () => ({ status: 'success', data: ['session_1'] }),
    });
  }
  if (String(url).includes('/api/session/history/')) {
    return Promise.resolve({
      ok: true,
      json: async () => ({ status: 'success', data: [] }),
    });
  }
  return Promise.resolve({
    ok: true,
    json: async () => ({ status: 'success', data: null }),
  });
}

beforeEach(() => {
  window.localStorage.clear();
  window.history.pushState({}, '', '/');
  global.fetch = jest.fn(providerResponse);
});

afterEach(() => {
  jest.restoreAllMocks();
});

test('renders the runtime overview and loads the active session', async () => {
  render(<App />);

  expect(screen.getByRole('heading', {
    name: 'Context you can see, control, and remove.',
  })).toBeInTheDocument();
  await waitFor(() => expect(screen.getAllByText('session_1').length).toBeGreaterThan(0));
  expect(screen.getByText('Runtime available')).toBeInTheDocument();
});

test('supports theme switching and workspace navigation', async () => {
  render(<App />);
  await waitFor(() => expect(screen.getAllByText('session_1').length).toBeGreaterThan(0));

  fireEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }));
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');

  fireEvent.click(screen.getByRole('link', { name: 'Open workspace' }));
  expect(await screen.findByRole('heading', { name: 'Conversation' })).toBeInTheDocument();
  expect(screen.getByRole('textbox', { name: 'Message SC-EVM' })).toBeInTheDocument();
});

test('uses an accessible dialog instead of a browser prompt for sessions', async () => {
  render(<App />);
  await waitFor(() => expect(screen.getAllByText('session_1').length).toBeGreaterThan(0));
  fireEvent.click(screen.getByRole('link', { name: 'Open workspace' }));
  await screen.findByRole('heading', { name: 'Conversation' });

  fireEvent.click(screen.getByRole('button', { name: 'Create session' }));
  expect(screen.getByRole('dialog', { name: 'Create a session' })).toBeInTheDocument();
  expect(screen.getByRole('textbox', { name: 'Session name' })).toBeInTheDocument();
});
