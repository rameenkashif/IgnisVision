import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { VictimOut } from '../api/thermal';
import i18n from '../i18n';
import { VictimList } from './VictimList';

const v = (over: Partial<VictimOut>): VictimOut => ({
  id: over.id ?? 'v',
  incident_id: 'i',
  zone_id: null,
  zone_code: 'F1-Z2',
  track_key: 'k',
  posture: 'lying',
  posture_confidence: 0.9,
  low_confidence: false,
  detection_confidence: 0.88,
  rpi_score: 0.86,
  rpi_band: 'critical',
  env_risk: null,
  status: 'detected',
  source: 'web_upload',
  first_seen_at: '2026-10-20T10:00:00Z',
  last_seen_at: '2026-10-20T10:00:00Z',
  best_detection_id: null,
  media_id: null,
  media_url: null,
  timestamp_ms: 0,
  bbox: null,
  ...over,
});

describe('VictimList', () => {
  beforeAll(() => i18n.changeLanguage('en'));

  it('ranks active people and labels band, posture, flags and source in text', () => {
    render(
      <VictimList
        victims={[
          v({ id: 'a' }),
          v({
            id: 'b',
            posture: 'sitting',
            rpi_band: 'medium',
            rpi_score: 0.4,
            low_confidence: true,
            source: 'mobile_sync',
          }),
          v({ id: 'c', status: 'rescued', rpi_band: 'high', rpi_score: 0.6 }),
        ]}
      />,
    );
    const items = screen.getAllByRole('listitem');
    expect(items[0]).toHaveTextContent('1');
    expect(items[0]).toHaveTextContent('Lying');
    expect(items[0]).toHaveTextContent('Critical');
    expect(items[1]).toHaveTextContent('2');
    expect(items[1]).toHaveTextContent('low confidence');
    expect(items[1]).toHaveTextContent('Mobile');
    expect(items[2]).toHaveTextContent('Rescued');
    expect(items[2]).toHaveTextContent('–');
    expect(screen.getByText(/does not mean nobody is present/)).toBeInTheDocument();
  });

  it('lets a commander mark a person rescued', async () => {
    const onStatus = vi.fn();
    render(<VictimList victims={[v({ id: 'a' })]} onStatus={onStatus} />);
    await userEvent.click(screen.getByRole('button', { name: 'Mark rescued' }));
    expect(onStatus).toHaveBeenCalledWith(expect.objectContaining({ id: 'a' }), 'rescued');
  });
});
