import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

export function PageHeader({ page, actions }: { page: string; actions?: ReactNode }) {
  const { t } = useTranslation();
  return (
    <>
      <div className="crumbs">{t(`pages.${page}.crumbs`)}</div>
      <div className="page-title-row">
        <div>
          <h1>{t(`pages.${page}.title`)}</h1>
          <p>{t(`pages.${page}.subtitle`)}</p>
        </div>
        {actions}
      </div>
    </>
  );
}
