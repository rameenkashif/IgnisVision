import { render, screen, within } from '@testing-library/react';
import type { ZoneOut } from '../api/types';
import i18n from '../i18n';
import { ZoneGrid } from './ZoneGrid';

const zone = (over: Partial<ZoneOut>): ZoneOut => ({
  id: over.code ?? 'z',
  floor_id: 'f1',
  floor_number: 1,
  code: 'F1-Z1',
  label: null,
  grid_row: 0,
  grid_col: 0,
  status: 'unclassified',
  stored_status: 'unclassified',
  stale: false,
  status_updated_at: null,
  risk_score: null,
  confidence: null,
  assessment_id: null,
  assignees: [],
  victim_count: 0,
  reasons: [],
  ...over,
});

describe('ZoneGrid', () => {
  beforeAll(() => i18n.changeLanguage('en'));

  it('never shows a stale or unanalysed zone as safe (HANDOFF §12)', () => {
    render(
      <ZoneGrid
        zones={[
          zone({ code: 'F1-Z1' }),
          // Backend marks stale zones unclassified; the stored "safe" must not leak into the UI.
          zone({
            code: 'F1-Z2',
            grid_col: 1,
            status: 'unclassified',
            stored_status: 'safe',
            stale: true,
          }),
          zone({
            code: 'F1-Z3',
            grid_col: 2,
            status: 'safe',
            stored_status: 'safe',
            status_updated_at: new Date().toISOString(),
          }),
        ]}
      />,
    );
    const cell = (code: string) => document.querySelector(`[data-zone="${code}"]`) as HTMLElement;
    expect(cell('F1-Z1')).toHaveClass('st-unclassified');
    expect(within(cell('F1-Z1')).getByText('Unclassified')).toBeInTheDocument();
    expect(cell('F1-Z2')).toHaveClass('st-unclassified');
    expect(cell('F1-Z2')).not.toHaveClass('st-safe');
    expect(within(cell('F1-Z2')).getByText('No current analysis')).toBeInTheDocument();
    expect(within(cell('F1-Z2')).queryByText('Safe')).toBeNull();
    expect(cell('F1-Z3')).toHaveClass('st-safe');
  });

  it('every status is labelled in text, not colour only', () => {
    const statuses = ['safe', 'caution', 'unsafe', 'blocked', 'unclassified'] as const;
    render(
      <ZoneGrid
        zones={statuses.map((s, i) => zone({ code: `F1-Z${i + 1}`, grid_col: i, status: s }))}
      />,
    );
    for (const label of ['Safe', 'Caution', 'Unsafe', 'Blocked', 'Unclassified']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it('shows assignees and a separate victim badge', () => {
    render(
      <ZoneGrid
        zones={[
          zone({
            victim_count: 2,
            assignees: [{ id: 'u', full_name: 'Ali Raza', username: 'ali' }],
          }),
        ]}
      />,
    );
    expect(screen.getByText('Ali Raza')).toBeInTheDocument();
    expect(screen.getByTitle('2 people detected')).toHaveTextContent('2');
  });

  it('briefing mode hides live status', () => {
    render(<ZoneGrid mode="briefing" zones={[zone({ status: 'unsafe' })]} />);
    expect(screen.queryByText('Unsafe')).toBeNull();
    expect(document.querySelector('.zone-cell')).toHaveClass('st-neutral');
  });
});
