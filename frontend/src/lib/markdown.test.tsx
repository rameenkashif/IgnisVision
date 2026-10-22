import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Markdown } from './markdown';

const md = `# Title

Intro with **bold**, \`code\` and a [link](/help/live).

## Steps

1. First
2. Second
   - nested
- bullet <img src=x onerror=alert(1)>`;

test('renders the supported subset as elements, never raw HTML', () => {
  const { container } = render(
    <MemoryRouter>
      <Markdown source={md} skipTitle />
    </MemoryRouter>,
  );
  expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
  expect(screen.getByRole('heading', { level: 2, name: 'Steps' })).toBeInTheDocument();
  expect(container.querySelector('strong')).toHaveTextContent('bold');
  expect(container.querySelector('code')).toHaveTextContent('code');
  expect(screen.getByRole('link', { name: 'link' })).toHaveAttribute('href', '/help/live');
  expect(container.querySelectorAll('ol > li')).toHaveLength(2);
  expect(container.querySelector('ol li ul li')).toHaveTextContent('nested');
  expect(container.querySelector('img')).toBeNull();
  expect(screen.getByText(/bullet <img/)).toBeInTheDocument();
});
