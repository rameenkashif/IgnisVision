import { useTranslation } from 'react-i18next';
import { PageHeader } from './PageHeader';

/** Placeholder for modules delivered in later phases (HANDOFF §13). */
export function ComingSoon({ page }: { page: string }) {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader page={page} />
      <div className="empty-state" data-testid={`page-${page}`}>
        <div className="ic-circle" aria-hidden="true">
          ◌
        </div>
        <h2>{t('common.comingSoonTitle')}</h2>
        <p>{t('common.comingSoonBody')}</p>
      </div>
    </>
  );
}
