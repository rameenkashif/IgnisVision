import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ROLES,
  useCreateUser,
  useDeactivateUser,
  useResetPassword,
  useUpdateUser,
  useUsers,
  type Role,
  type UserCreate,
  type UserOut,
} from '../../api/admin';
import { ApiError } from '../../api/errors';
import { ConfirmDialog, Modal } from '../../components/Modal';
import { PageHeader } from '../../components/PageHeader';
import { errorMessage } from '../../i18n';
import { formatDateTime } from '../../lib/format';
import { useAuth } from '../../stores/auth';
import { AdminTabs } from './AdminTabs';

type Pending = { kind: 'deactivate' | 'reset'; user: UserOut };
const errText = (e: unknown) => errorMessage(e instanceof ApiError ? e.code : undefined);

function UserForm({
  user,
  onClose,
  onCreated,
}: {
  user: UserOut | null;
  onClose: () => void;
  onCreated: (username: string, password: string | null | undefined) => void;
}) {
  const { t } = useTranslation();
  const me = useAuth((s) => s.user!);
  const create = useCreateUser();
  const update = useUpdateUser();
  const [form, setForm] = useState<UserCreate>({
    username: user?.username ?? '',
    full_name: user?.full_name ?? '',
    role: user?.role ?? 'field_responder',
    preferred_language: user?.preferred_language ?? 'en',
  });
  const [error, setError] = useState<string | null>(null);
  const self = user?.id === me.id;
  const busy = create.isPending || update.isPending;
  const submit = () => {
    setError(null);
    if (user)
      update.mutate(
        {
          id: user.id,
          body: {
            full_name: form.full_name,
            role: form.role,
            preferred_language: form.preferred_language,
          },
        },
        { onSuccess: onClose, onError: (e) => setError(errText(e)) },
      );
    else
      create.mutate(form, {
        onSuccess: (r) => onCreated(r.user.username, r.temporary_password),
        onError: (e) => setError(errText(e)),
      });
  };
  return (
    <Modal
      title={user ? t('admin.users.edit', { name: user.full_name }) : t('admin.users.new')}
      onClose={onClose}
      footer={
        <>
          {error && (
            <span className="error-text" role="alert">
              {error}
            </span>
          )}
          <button type="button" className="btn" onClick={onClose}>
            {t('common.cancel')}
          </button>
          <button
            type="button"
            className="btn primary"
            disabled={busy || !form.username || !form.full_name}
            onClick={submit}
            data-testid="save-user"
          >
            {t('common.save')}
          </button>
        </>
      }
    >
      <div className="form-grid">
        <label>
          <span className="field-label">{t('admin.users.username')}</span>
          <input
            id="u-username"
            value={form.username}
            disabled={!!user}
            dir="ltr"
            autoComplete="off"
            onChange={(e) => setForm({ ...form, username: e.target.value.trim() })}
          />
          {!user && <span className="hint">{t('admin.users.usernameHint')}</span>}
        </label>
        <label>
          <span className="field-label">{t('admin.users.fullName')}</span>
          <input
            id="u-fullname"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
        </label>
        <label>
          <span className="field-label">{t('admin.users.role')}</span>
          <select
            id="u-role"
            value={form.role}
            disabled={self}
            onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`roles.${r}`)}
              </option>
            ))}
          </select>
          {self && <span className="hint">{t('admin.users.selfRole')}</span>}
        </label>
        <label>
          <span className="field-label">{t('admin.users.language')}</span>
          <select
            value={form.preferred_language ?? 'en'}
            onChange={(e) =>
              setForm({ ...form, preferred_language: e.target.value as 'en' | 'ur' })
            }
          >
            <option value="en">English</option>
            <option value="ur">اردو</option>
          </select>
        </label>
      </div>
      {!user && <p className="muted small">{t('admin.users.tempPasswordNote')}</p>}
    </Modal>
  );
}

/** Users and roles (SRS §4.8, UC-08): create, edit role, deactivate/reactivate, reset password. */
export function AdminUsers() {
  const { t } = useTranslation();
  const me = useAuth((s) => s.user!);
  const [role, setRole] = useState<Role | ''>('');
  const [active, setActive] = useState<'' | 'true' | 'false'>('');
  const [q, setQ] = useState('');
  const [offset, setOffset] = useState(0);
  const list = useUsers({
    role: role || undefined,
    is_active: active === '' ? undefined : active === 'true',
    q,
    offset,
  });
  const deactivate = useDeactivateUser();
  const update = useUpdateUser();
  const reset = useResetPassword();
  const [editing, setEditing] = useState<UserOut | 'new' | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [secret, setSecret] = useState<{ username: string; password: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const total = list.data?.total ?? 0;

  return (
    <>
      <PageHeader
        page="admin"
        actions={
          <button
            type="button"
            className="btn primary"
            onClick={() => setEditing('new')}
            data-testid="new-user"
          >
            + {t('admin.users.new')}
          </button>
        }
      />
      <AdminTabs />
      {notice && (
        <div className="banner warn" role="status">
          <span>{notice}</span>
          <button
            type="button"
            className="btn"
            onClick={() => setNotice(null)}
            aria-label={t('common.cancel')}
          >
            ✕
          </button>
        </div>
      )}
      <div className="filters" role="search">
        <label className="grow">
          <span className="field-label">{t('admin.users.search')}</span>
          <input
            type="search"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
            data-testid="user-search"
          />
        </label>
        <label>
          <span className="field-label">{t('admin.users.role')}</span>
          <select
            value={role}
            onChange={(e) => {
              setRole(e.target.value as Role | '');
              setOffset(0);
            }}
          >
            <option value="">{t('reports.filters.all')}</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`roles.${r}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">{t('admin.users.state')}</span>
          <select
            value={active}
            onChange={(e) => {
              setActive(e.target.value as typeof active);
              setOffset(0);
            }}
          >
            <option value="">{t('reports.filters.all')}</option>
            <option value="true">{t('admin.users.active')}</option>
            <option value="false">{t('admin.users.inactive')}</option>
          </select>
        </label>
      </div>
      <div className="panel">
        <div className="panel-body table-wrap">
          <table className="table" data-testid="users-table">
            <thead>
              <tr>
                <th>{t('admin.users.fullName')}</th>
                <th>{t('admin.users.username')}</th>
                <th>{t('admin.users.role')}</th>
                <th>{t('admin.users.state')}</th>
                <th>{t('admin.users.lastLogin')}</th>
                <th>{t('admin.users.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {list.data?.items.map((u) => (
                <tr
                  key={u.id}
                  data-user={u.username}
                  className={u.is_active ? undefined : 'muted-row'}
                >
                  <td>{u.full_name}</td>
                  <td dir="ltr">{u.username}</td>
                  <td>{t(`roles.${u.role}`)}</td>
                  <td>
                    {u.is_active ? t('admin.users.active') : t('admin.users.inactive')}
                    {u.must_change_password && (
                      <span className="tag warn">{t('admin.users.mustChange')}</span>
                    )}
                  </td>
                  <td>{formatDateTime(u.last_login_at)}</td>
                  <td className="row-buttons">
                    <button
                      type="button"
                      className="btn"
                      onClick={() => setEditing(u)}
                      data-action="edit"
                    >
                      {t('admin.users.editShort')}
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => setPending({ kind: 'reset', user: u })}
                      data-action="reset"
                    >
                      {t('admin.users.reset')}
                    </button>
                    {u.id !== me.id &&
                      (u.is_active ? (
                        <button
                          type="button"
                          className="btn danger"
                          onClick={() => setPending({ kind: 'deactivate', user: u })}
                          data-action="deactivate"
                        >
                          {t('admin.users.deactivate')}
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn"
                          data-action="reactivate"
                          onClick={() =>
                            update.mutate(
                              { id: u.id, body: { is_active: true } },
                              {
                                onSuccess: () =>
                                  setNotice(t('admin.users.reactivated', { name: u.full_name })),
                              },
                            )
                          }
                        >
                          {t('admin.users.reactivate')}
                        </button>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {list.data?.items.length === 0 && <p className="muted">{t('admin.users.none')}</p>}
          {total > 50 && (
            <div className="pager">
              <button
                type="button"
                className="btn"
                disabled={offset === 0}
                onClick={() => setOffset(offset - 50)}
              >
                {t('common.back')}
              </button>
              <span className="muted small">
                {offset + 1}–{Math.min(offset + 50, total)} / {total}
              </span>
              <button
                type="button"
                className="btn"
                disabled={offset + 50 >= total}
                onClick={() => setOffset(offset + 50)}
              >
                {t('common.next')}
              </button>
            </div>
          )}
        </div>
      </div>

      {editing && (
        <UserForm
          user={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onCreated={(username, password) => {
            setEditing(null);
            if (password) setSecret({ username, password });
          }}
        />
      )}
      {pending?.kind === 'deactivate' && (
        <ConfirmDialog
          title={t('admin.users.deactivateTitle', { name: pending.user.full_name })}
          body={t('admin.users.deactivateBody')}
          confirmLabel={t('admin.users.deactivate')}
          busy={deactivate.isPending}
          onCancel={() => setPending(null)}
          onConfirm={() =>
            deactivate.mutate(pending.user.id, {
              onSuccess: () => {
                setPending(null);
                setNotice(t('admin.users.deactivated', { name: pending.user.full_name }));
              },
              onError: (e) => {
                setPending(null);
                setNotice(errText(e));
              },
            })
          }
        />
      )}
      {pending?.kind === 'reset' && (
        <ConfirmDialog
          title={t('admin.users.resetTitle', { name: pending.user.full_name })}
          body={t('admin.users.resetBody')}
          confirmLabel={t('admin.users.reset')}
          busy={reset.isPending}
          onCancel={() => setPending(null)}
          onConfirm={() =>
            reset.mutate(pending.user.id, {
              onSuccess: (r) => {
                setPending(null);
                setSecret({ username: pending.user.username, password: r.temporary_password });
              },
              onError: (e) => {
                setPending(null);
                setNotice(errText(e));
              },
            })
          }
        />
      )}
      {secret && (
        <Modal
          title={t('admin.users.tempTitle')}
          onClose={() => setSecret(null)}
          footer={
            <button
              type="button"
              className="btn primary"
              onClick={() => setSecret(null)}
              data-testid="close-secret"
            >
              {t('admin.users.done')}
            </button>
          }
        >
          <p>{t('admin.users.tempBody', { username: secret.username })}</p>
          <p className="secret" dir="ltr" data-testid="temp-password">
            {secret.password}
          </p>
          <button
            type="button"
            className="btn"
            onClick={() => void navigator.clipboard?.writeText(secret.password)}
          >
            {t('admin.users.copy')}
          </button>
        </Modal>
      )}
    </>
  );
}
