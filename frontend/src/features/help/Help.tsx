import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { useAskHelp, usePublicSettings } from '../../api/admin';
import { ApiError } from '../../api/errors';
import { PageHeader } from '../../components/PageHeader';
import { currentLang, errorMessage } from '../../i18n';
import { HELP_TOPICS, helpText } from '../../lib/help';
import { Markdown } from '../../lib/markdown';
import { NotFound } from '../shell/guards';

/** Help index (HANDOFF §11): every screen's page, searchable in the current language. */
export function HelpIndex() {
  const { t } = useTranslation();
  const [q, setQ] = useState('');
  const lang = currentLang();
  const topics = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return [...HELP_TOPICS];
    return HELP_TOPICS.filter((k) =>
      `${t(`help.topics.${k}.title`)} ${helpText(k, lang)}`.toLowerCase().includes(needle),
    );
  }, [q, lang, t]);
  return (
    <>
      <PageHeader page="help" />
      <div className="filters" role="search">
        <label className="grow">
          <span className="field-label">{t('help.search')}</span>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            data-testid="help-search"
          />
        </label>
      </div>
      <div className="help-list" data-testid="help-index">
        {topics.map((k) => (
          <Link key={k} className="help-card" to={`/help/${k}`} data-topic={k}>
            <h3>{t(`help.topics.${k}.title`)}</h3>
            <p>{t(`help.topics.${k}.body`)}</p>
          </Link>
        ))}
      </div>
      {topics.length === 0 && <p className="muted">{t('help.noMatch')}</p>}
    </>
  );
}

/** Optional assistant grounded in the page text (HANDOFF §10.3). */
function AskBox({ topic, context }: { topic: string; context: string }) {
  const { t } = useTranslation();
  const ask = useAskHelp();
  const [question, setQuestion] = useState('');
  return (
    <section className="panel help-ask" data-testid="help-ask">
      <div className="panel-head">
        <h2>{t('help.ask.title')}</h2>
      </div>
      <div className="panel-body">
        <form
          className="ask-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (question.trim().length >= 2)
              ask.mutate({ question: question.trim(), topic, context, lang: currentLang() });
          }}
        >
          <input
            value={question}
            maxLength={500}
            placeholder={t('help.ask.placeholder')}
            aria-label={t('help.ask.title')}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button
            type="submit"
            className="btn primary"
            disabled={ask.isPending || question.trim().length < 2}
          >
            {ask.isPending ? t('help.ask.thinking') : t('help.ask.send')}
          </button>
        </form>
        {ask.data && (
          <p className="ask-answer" style={{ whiteSpace: 'pre-wrap' }} data-testid="help-answer">
            {ask.data.answer}
          </p>
        )}
        {ask.isError && (
          <p className="error-text" role="alert">
            {errorMessage(ask.error instanceof ApiError ? ask.error.code : undefined)}
          </p>
        )}
        <p className="muted small">{t('help.ask.note')}</p>
      </div>
    </section>
  );
}

export function HelpTopic() {
  const { t } = useTranslation();
  const { topic = '' } = useParams();
  const settings = usePublicSettings();
  const lang = currentLang();
  if (!(HELP_TOPICS as readonly string[]).includes(topic)) return <NotFound />;
  const text = helpText(topic, lang);
  const others = HELP_TOPICS.filter((k) => k !== topic);
  return (
    <>
      <div className="crumbs">
        <Link to="/help">{t('help.back')}</Link>
      </div>
      <div className="page-title-row">
        <h1>{t(`help.topics.${topic}.title`)}</h1>
      </div>
      <div className="help-layout">
        <article className="panel help-article" data-testid={`help-${topic}`} lang={lang}>
          <div className="panel-body help-body">
            <Markdown source={text} skipTitle />
          </div>
        </article>
        <nav className="help-side" aria-label={t('help.index')}>
          <h2>{t('help.more')}</h2>
          <ul>
            {others.map((k) => (
              <li key={k}>
                <Link to={`/help/${k}`}>{t(`help.topics.${k}.title`)}</Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      {settings.data?.['llm.features']?.help_assistant && <AskBox topic={topic} context={text} />}
    </>
  );
}
