import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import i18n from '../../i18n';
import { useAuth } from '../../stores/auth';
import { SignIn } from './SignIn';

describe('SignIn', () => {
  beforeEach(() => useAuth.getState().signedOut(null));
  afterEach(() => vi.restoreAllMocks());

  it('shows the translated error from the API envelope', async () => {
    await i18n.changeLanguage('en');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: 'invalid_credentials', message_key: 'x', params: {} } }),
        { status: 401 },
      ),
    );
    render(
      <MemoryRouter>
        <SignIn />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText('Username'), 'commander1');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-pass1');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Username or password is incorrect.',
    );
  });

  it('renders in Urdu', async () => {
    await i18n.changeLanguage('ur');
    render(
      <MemoryRouter>
        <SignIn />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: 'سائن اِن' })).toBeInTheDocument();
    await i18n.changeLanguage('en');
  });

  it('explains an idle sign-out', async () => {
    await i18n.changeLanguage('en');
    useAuth.getState().signedOut('idle_timeout');
    render(
      <MemoryRouter>
        <SignIn />
      </MemoryRouter>,
    );
    expect(screen.getByRole('status')).toHaveTextContent('30 minutes of inactivity');
  });
});
