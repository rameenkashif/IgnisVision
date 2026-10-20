import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  afterEach(() => vi.restoreAllMocks());

  it('shows API status from /api/v1/health', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', version: '0.1.0', ml_backend: 'mock' })),
    );
    render(<App />);
    expect(await screen.findByText(/API ok · v0.1.0 · ML mock/)).toBeInTheDocument();
  });

  it('shows an error chip when the API is unreachable', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('down'));
    render(<App />);
    expect(await screen.findByText('API unreachable')).toBeInTheDocument();
  });
});
