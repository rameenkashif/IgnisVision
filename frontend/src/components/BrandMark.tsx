export function BrandMark({ large = false }: { large?: boolean }) {
  return (
    <div className={large ? 'brand-mark-lg' : 'brand-mark'} aria-hidden="true">
      IV
    </div>
  );
}
