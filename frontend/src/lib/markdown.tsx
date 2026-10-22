import { Fragment, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

/** Inline: **bold**, `code`, [text](href). Text only — raw HTML is never interpreted. */
function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const k = `${key}-${i++}`;
    if (m[1] !== undefined) out.push(<strong key={k}>{inline(m[1], k)}</strong>);
    else if (m[2] !== undefined) out.push(<code key={k}>{m[2]}</code>);
    else if (m[4].startsWith('/'))
      out.push(
        <Link key={k} to={m[4]}>
          {m[3]}
        </Link>,
      );
    else if (/^https?:\/\//.test(m[4]))
      out.push(
        <a key={k} href={m[4]} target="_blank" rel="noreferrer">
          {m[3]}
        </a>,
      );
    else out.push(m[3]);
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

type Block =
  | { kind: 'h'; level: number; text: string }
  | { kind: 'p'; text: string }
  | { kind: 'list'; ordered: boolean; items: { text: string; sub: string[] }[] };

function parseMarkdown(src: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) blocks.push({ kind: 'p', text: para.join(' ') });
    para = [];
  };
  for (const raw of src.replace(/\r/g, '').split('\n')) {
    const line = raw.trimEnd();
    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    const item = /^(\s*)(?:[-*]|(\d+)\.)\s+(.*)$/.exec(line);
    if (!line.trim()) {
      flush();
    } else if (h) {
      flush();
      blocks.push({ kind: 'h', level: h[1].length, text: h[2] });
    } else if (item) {
      flush();
      const nested = item[1].length >= 2;
      const prev = blocks[blocks.length - 1];
      if (nested && prev?.kind === 'list' && prev.items.length)
        prev.items[prev.items.length - 1].sub.push(item[3]);
      else if (prev?.kind === 'list' && prev.ordered === !!item[2])
        prev.items.push({ text: item[3], sub: [] });
      else blocks.push({ kind: 'list', ordered: !!item[2], items: [{ text: item[3], sub: [] }] });
    } else {
      para.push(line.trim());
    }
  }
  flush();
  return blocks;
}

/** Help pages (HANDOFF §11): a small, safe Markdown subset rendered to React. */
export function Markdown({ source, skipTitle = false }: { source: string; skipTitle?: boolean }) {
  const blocks = parseMarkdown(source).filter(
    (b, i) => !(skipTitle && i === 0 && b.kind === 'h' && b.level === 1),
  );
  return (
    <>
      {blocks.map((b, i) => {
        const k = `b${i}`;
        if (b.kind === 'h') {
          const H = (['h1', 'h2', 'h3'] as const)[b.level - 1];
          return <H key={k}>{inline(b.text, k)}</H>;
        }
        if (b.kind === 'p') return <p key={k}>{inline(b.text, k)}</p>;
        const L = b.ordered ? 'ol' : 'ul';
        return (
          <L key={k}>
            {b.items.map((it, j) => (
              <li key={j}>
                {inline(it.text, `${k}-${j}`)}
                {it.sub.length > 0 && (
                  <ul>
                    {it.sub.map((s, n) => (
                      <Fragment key={n}>
                        <li>{inline(s, `${k}-${j}-${n}`)}</li>
                      </Fragment>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </L>
        );
      })}
    </>
  );
}
