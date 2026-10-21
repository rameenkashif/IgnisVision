import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import i18n from '../../i18n';
import { MediaStage } from './MediaStage';

const item = {
  media_kind: 'image' as const,
  media_url: '/x.png',
  regions: [
    {
      id: 'r1',
      polygon: [
        [0, 0],
        [0.5, 0],
        [0.5, 1],
        [0, 1],
      ] as [number, number][],
    },
    {
      id: 'r2',
      polygon: [
        [0.5, 0],
        [1, 0],
        [1, 1],
        [0.5, 1],
      ] as [number, number][],
    },
  ],
  people: [],
};

test('targets are labelled, selectable by click and keyboard', async () => {
  await i18n.changeLanguage('en');
  const onSelect = vi.fn();
  render(
    <MediaStage
      item={item}
      labels={{ r2: { text: 'Unsafe', tone: 'ans-unsafe' } }}
      selectedId="r2"
      onSelect={onSelect}
    />,
  );
  const r1 = screen.getByRole('button', { name: 'Region 1' });
  const r2 = screen.getByRole('button', { name: 'Region 2: Unsafe' });
  expect(r2).toHaveAttribute('aria-pressed', 'true');
  expect(r2.getAttribute('class')).toContain('selected');
  fireEvent.click(r1);
  fireEvent.keyDown(r2, { key: 'Enter' });
  expect(onSelect.mock.calls).toEqual([['r1'], ['r2']]);
});

test('read-only stage has no interactive targets', () => {
  render(<MediaStage item={item} />);
  expect(screen.queryAllByRole('button')).toHaveLength(0);
});
