import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { PageHeader } from '../../components/PageHeader';
import { HELP_TOPICS } from '../../lib/help';
import { NotFound } from '../shell/guards';

/** Help skeleton (HANDOFF §11). Full per-screen content lands in Phase 8. */
export function HelpIndex() {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader page="help" />
      <div className="help-list" data-testid="help-index">
        {HELP_TOPICS.map((k) => (
          <Link key={k} className="help-card" to={`/help/${k}`}>
            <h3>{t(`help.topics.${k}.title`)}</h3>
            <p>{t(`help.topics.${k}.body`)}</p>
          </Link>
        ))}
      </div>
    </>
  );
}

export function HelpTopic() {
  const { t } = useTranslation();
  const { topic = '' } = useParams();
  if (!(HELP_TOPICS as readonly string[]).includes(topic)) return <NotFound />;
  return (
    <>
      <div className="crumbs">
        <Link to="/help">{t('help.back')}</Link>
      </div>
      <div className="page-title-row">
        <h1>{t(`help.topics.${topic}.title`)}</h1>
      </div>
      <div className="panel" data-testid={`help-${topic}`}>
        <div className="panel-body help-body">{t(`help.topics.${topic}.body`)}</div>
      </div>
    </>
  );
}
