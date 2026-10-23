import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, auth } from './api'
import { useDialog, validateForm } from './Dialog'
const roles: Record<string, string> = {
  admin: 'Administración',
  scheduler: 'Coordinación',
  reception: 'Recepción',
  clinician: 'Médico',
  finance: 'Finanzas',
  privacy: 'Privacidad',
}
type Item = {
  id: string
  kind: 'member' | 'invitation'
  email: string
  role: string
  active: boolean
  state: string
  version: number
  branches: string[]
  resources: string[]
  delivery_state: string | null
  expires_at: string | null
}
type Options = {
  branches: { id: string; name: string }[]
  resources: { id: string; name: string; branch_id: string }[]
  permissions: Record<string, string>
}
const states: Record<string, string> = {
  active: 'Activo',
  inactive: 'Desactivado',
  pending: 'Pendiente',
  accepted: 'Aceptada',
  expired: 'Vencida',
  revoked: 'Revocada',
  queued: 'Encolado · aún no enviado',
  delivered: 'Entrega confirmada',
  failed: 'Fallido',
  unknown: 'Resultado desconocido',
  superseded: 'Sustituido',
}
export function Team({ token }: { token: string }) {
  const { notify, confirm } = useDialog()
  const [items, setItems] = useState<Item[]>([]),
    [opts, setOpts] = useState<Options>({
      branches: [],
      resources: [],
      permissions: {},
    })
  const [loading, setLoading] = useState(true),
    [failed, setFailed] = useState(false),
    [busy, setBusy] = useState(false),
    [offset, setOffset] = useState(0),
    [more, setMore] = useState(false),
    [revision, setRevision] = useState(0)
  const [search, setSearch] = useState(''),
    [filter, setFilter] = useState(''),
    [edit, setEdit] = useState<Item | null>(null),
    [open, setOpen] = useState(false),
    [email, setEmail] = useState(''),
    [role, setRole] = useState('reception'),
    [branches, setBranches] = useState<string[]>([]),
    [resources, setResources] = useState<string[]>([])
  const inFlight = useRef(false)
  useEffect(() => {
    setOpen(false)
    setEdit(null)
    setEmail('')
    setSearch('')
    setFilter('')
    setBranches([])
    setResources([])
    setOffset(0)
    setOpts({ branches: [], resources: [], permissions: {} })
  }, [token])
  useEffect(() => {
    let active = true
    setItems([])
    setLoading(true)
    setFailed(false)
    Promise.all([
      api<{ items: Item[]; has_more: boolean }>(
        `/team${filter ? '/search' : ''}?offset=${offset}&limit=20`,
        filter
          ? { method: 'POST', body: JSON.stringify({ email: filter }) }
          : {},
        token,
      ),
      api<Options>('/team/options', {}, token),
    ])
      .then(([list, options]) => {
        if (active) {
          setItems(list.items)
          setMore(list.has_more)
          setOpts(options)
        }
      })
      .catch((e) => {
        if (active) {
          setFailed(true)
          notify({
            title: 'No pudimos cargar el equipo',
            message: e.message,
            tone: 'error',
          })
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [token, offset, filter, revision])
  function editing(item?: Item) {
    setEdit(item ?? null)
    setEmail(item?.email ?? '')
    setRole(item?.role ?? 'reception')
    setBranches(item?.branches ?? [])
    setResources(item?.resources ?? [])
    setOpen(true)
  }
  async function perform(
    path: string,
    method: string,
    body: unknown,
    message: string,
  ) {
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true)
    try {
      await api(path, { method, body: JSON.stringify(body) }, token)
      setOpen(false)
      setRevision((x) => x + 1)
      notify({ title: 'Equipo actualizado', message, tone: 'success' })
    } catch (e) {
      notify({
        title: 'No pudimos guardar el cambio',
        message: (e as Error).message,
        tone: 'error',
      })
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!validateForm(e.currentTarget, notify) || busy) return
    if (
      !(await confirm({
        title: edit ? 'Guardar permisos' : 'Invitar al equipo',
        message: `${opts.permissions[role]}\nSucursales: ${branches.map((id) => opts.branches.find((b) => b.id === id)?.name).join(', ') || 'ninguna'}\nAgendas: ${resources.map((id) => opts.resources.find((r) => r.id === id)?.name).join(', ') || 'ninguna'}\n${edit ? 'Los cambios actúan en la siguiente operación protegida.' : 'Dura 48 horas. Si ya hay una invitación pendiente, edítala o reenvíala desde Equipo. Encolar no confirma el envío.'}`,
        confirmLabel: edit ? 'Guardar permisos' : 'Crear invitación',
      }))
    )
      return
    await perform(
      edit
        ? `/team/${edit.kind === 'member' ? 'members' : 'invitations'}/${edit.id}`
        : '/team/invitations',
      edit ? 'PATCH' : 'POST',
      {
        role,
        branches,
        resources,
        ...(edit
          ? {
              expected_version: edit.version,
              ...(edit.kind === 'member' ? { active: edit.active } : {}),
            }
          : { email }),
      },
      edit
        ? 'Permisos guardados y auditados.'
        : 'Invitación encolada. Consulta su estado de entrega.',
    )
  }
  async function toggle(item: Item) {
    if (
      !(await confirm({
        title: item.active ? 'Desactivar acceso' : 'Reactivar acceso',
        message:
          'Se conservan citas e historia. Debe permanecer un administrador activo.',
        confirmLabel: item.active ? 'Desactivar' : 'Reactivar',
        tone: item.active ? 'danger' : 'info',
      }))
    )
      return
    await perform(
      `/team/members/${item.id}`,
      'PATCH',
      {
        role: item.role,
        branches: item.branches,
        resources: item.resources,
        active: !item.active,
        expected_version: item.version,
      },
      'Estado del acceso actualizado.',
    )
  }
  async function invitationAction(item: Item, action: 'revoke' | 'resend') {
    if (
      !(await confirm({
        title:
          action === 'revoke' ? 'Revocar invitación' : 'Reenviar invitación',
        message:
          action === 'revoke'
            ? 'El enlace deja de conceder acceso.'
            : 'El enlace anterior se revoca y se encola otro por 48 horas.',
        confirmLabel:
          action === 'revoke' ? 'Revocar' : 'Encolar nueva invitación',
        tone: action === 'revoke' ? 'danger' : 'info',
      }))
    )
      return
    await perform(
      `/team/invitations/${item.id}/${action}`,
      'POST',
      { expected_version: item.version },
      'Invitación actualizada. Encolado y entrega son estados distintos.',
    )
  }
  const choices = role === 'clinician' ? opts.resources : opts.branches,
    selected = role === 'clinician' ? resources : branches
  function select(id: string) {
    const value = selected.includes(id)
      ? selected.filter((x) => x !== id)
      : [...selected, id]
    if (role === 'clinician') setResources(value)
    else setBranches(value)
  }
  return (
    <div className="space-y-5" aria-busy={loading || busy}>
      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold">Equipo y accesos</h3>
            <p className="mt-2 text-sm text-slate-600">
              Un perfil por persona y clínica. Invitación, membresía y entrega
              son estados diferentes.
            </p>
          </div>
          <button
            className="btn-primary"
            disabled={busy || loading}
            onClick={() => editing()}
          >
            Invitar personal
          </button>
        </div>
        <form
          noValidate
          className="mt-5 flex flex-wrap gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            setFilter(search.trim())
            setOffset(0)
          }}
        >
          <label className="field grow">
            Buscar por correo exacto
            <input
              type="email"
              value={search}
              maxLength={254}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <button className="btn-secondary">Buscar</button>
        </form>
      </div>
      {open && (
        <form noValidate className="card space-y-5" onSubmit={save}>
          <h3 className="text-lg font-semibold">
            {edit ? 'Editar perfil y alcance' : 'Nueva invitación'}
          </h3>
          {edit && <p className="break-all text-sm">{edit.email}</p>}
          {!edit && (
            <label className="field">
              Correo del destinatario
              <input
                type="email"
                autoComplete="off"
                required
                maxLength={254}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
          )}
          <label className="field">
            Perfil principal
            <select
              value={role}
              onChange={(e) => {
                setRole(e.target.value)
                setBranches([])
                setResources([])
              }}
            >
              {Object.entries(roles).map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <p className="soft-panel text-sm" aria-live="polite">
            {opts.permissions[role]}
          </p>
          {!['admin', 'privacy'].includes(role) && (
            <fieldset className="space-y-3">
              <legend className="mb-3 font-semibold">
                {role === 'clinician'
                  ? 'Agendas permitidas'
                  : 'Sucursales permitidas'}
              </legend>
              {choices.map((c) => (
                <label key={c.id} className="check">
                  <input
                    type="checkbox"
                    checked={selected.includes(c.id)}
                    onChange={() => select(c.id)}
                  />
                  {c.name}
                </label>
              ))}
              {!choices.length && (
                <p>
                  No hay asignaciones disponibles. Configura el catálogo antes
                  de invitar.
                </p>
              )}
            </fieldset>
          )}
          <div className="flex flex-wrap gap-3">
            <button disabled={busy} className="btn-primary">
              Revisar permisos y confirmar
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={busy}
              onClick={() => setOpen(false)}
            >
              Cancelar edición
            </button>
          </div>
        </form>
      )}
      {loading ? (
        <p role="status">Cargando equipo…</p>
      ) : failed ? (
        <button
          className="btn-secondary"
          onClick={() => setRevision((x) => x + 1)}
        >
          Reintentar carga
        </button>
      ) : !items.length ? (
        <p className="card">No hay accesos para esta búsqueda.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li className="card min-w-0" key={item.kind + item.id}>
              <p className="break-all font-semibold">{item.email}</p>
              <p className="mt-2 text-sm">
                {roles[item.role]} ·{' '}
                {item.kind === 'member' ? 'Acceso' : 'Invitación'}:{' '}
                {states[item.state] ?? item.state}
              </p>
              <p className="mt-2 text-sm text-slate-600">
                {opts.permissions[item.role]}
              </p>
              <p className="mt-2 text-sm">
                Alcance:{' '}
                {item.role === 'admin'
                  ? 'toda la clínica'
                  : item.role === 'privacy'
                    ? 'procedimientos de privacidad'
                    : [
                        ...item.branches.map(
                          (id) =>
                            opts.branches.find((b) => b.id === id)?.name ??
                            'Sucursal',
                        ),
                        ...item.resources.map(
                          (id) =>
                            opts.resources.find((r) => r.id === id)?.name ??
                            'Agenda',
                        ),
                      ].join(', ') || 'sin asignación'}
              </p>
              {item.kind === 'invitation' && (
                <p className="mt-2 text-sm">
                  Correo:{' '}
                  {item.delivery_state === 'accepted'
                    ? 'Aceptado por proveedor · entrega no confirmada'
                    : (states[item.delivery_state ?? ''] ?? 'Sin evidencia')}
                  {item.expires_at &&
                    ` · Vence ${new Date(item.expires_at).toLocaleString()}`}
                </p>
              )}
              <div className="mt-4 flex flex-wrap gap-3">
                {item.kind === 'member' ? (
                  <>
                    <button
                      className="btn-secondary"
                      disabled={busy}
                      onClick={() => editing(item)}
                    >
                      Editar permisos
                    </button>
                    <button
                      className="btn-secondary"
                      disabled={busy}
                      onClick={() => toggle(item)}
                    >
                      {item.active ? 'Desactivar' : 'Reactivar'}
                    </button>
                  </>
                ) : (
                  ['pending', 'expired'].includes(item.state) && (
                    <>
                      <button
                        className="btn-secondary"
                        disabled={busy}
                        onClick={() => editing(item)}
                      >
                        Editar permisos
                      </button>
                      <button
                        className="btn-secondary"
                        disabled={busy}
                        onClick={() => invitationAction(item, 'resend')}
                      >
                        Reenviar
                      </button>
                      <button
                        className="btn-secondary"
                        disabled={busy}
                        onClick={() => invitationAction(item, 'revoke')}
                      >
                        Revocar
                      </button>
                    </>
                  )
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <nav
        aria-label="Paginación del equipo"
        className="flex flex-wrap items-center gap-3"
      >
        <button
          className="btn-secondary"
          disabled={loading || offset === 0}
          onClick={() => setOffset((x) => Math.max(0, x - 20))}
        >
          Anterior
        </button>
        <span>Página {offset / 20 + 1}</span>
        <button
          className="btn-secondary"
          disabled={loading || !more}
          onClick={() => setOffset((x) => x + 20)}
        >
          Siguiente
        </button>
      </nav>
    </div>
  )
}

export function TeamAccess({
  token,
  invitation,
  onAccepted,
}: {
  token?: string
  invitation: string
  onAccepted: () => void
}) {
  const { notify, confirm } = useDialog()
  const [email, setEmail] = useState(''),
    [otp, setOtp] = useState(''),
    [code, setCode] = useState(''),
    [factor, setFactor] = useState(''),
    [qr, setQr] = useState(''),
    [busy, setBusy] = useState(false)
  useEffect(() => {
    setFactor('')
    setQr('')
    setCode('')
    setOtp('')
  }, [token])
  async function action(fn: () => Promise<void>) {
    setBusy(true)
    try {
      await fn()
    } catch (e) {
      notify({
        title: 'No pudimos verificar el acceso',
        message: (e as Error).message,
        tone: 'error',
      })
    } finally {
      setBusy(false)
    }
  }
  async function mfa() {
    if (!auth)
      throw new Error('Auth no está configurado. El equipo permanece cerrado.')
    const listed = await auth.auth.mfa.listFactors()
    if (listed.error) throw listed.error
    const existing = listed.data.totp.find((f) => f.status === 'verified')
    if (existing) {
      setFactor(existing.id)
      return
    }
    const enrolled = await auth.auth.mfa.enroll({ factorType: 'totp' })
    if (enrolled.error) throw enrolled.error
    setFactor(enrolled.data.id)
    setQr(enrolled.data.totp.qr_code)
  }
  return (
    <section className="card mt-6 space-y-4">
      <h3 className="text-lg font-semibold">
        Acceso del equipo · verificación en dos pasos
      </h3>
      <p className="text-sm text-slate-600">
        Usa el correo destinatario. El segundo factor se comprueba en el
        servidor.{' '}
        {invitation
          ? 'Hay una invitación en esta pestaña; no la compartas.'
          : ''}
      </p>
      {!auth && (
        <p>
          Auth aún no está configurado. El acceso del equipo permanece cerrado.
        </p>
      )}
      {!token ? (
        <>
          <form
            noValidate
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (!validateForm(e.currentTarget, notify)) return
              void action(async () => {
                const r = await auth!.auth.signInWithOtp({ email })
                if (r.error) throw r.error
                notify({
                  title: 'Solicitud recibida',
                  message:
                    'Si corresponde, recibirás un código. Esto no concede permisos.',
                })
              })
            }}
          >
            <label className="field">
              Correo de acceso
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <button disabled={!auth || busy} className="btn-secondary">
              Solicitar código de acceso
            </button>
          </form>
          <form
            noValidate
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (!validateForm(e.currentTarget, notify)) return
              void action(async () => {
                const r = await auth!.auth.verifyOtp({
                  email,
                  token: otp,
                  type: 'email',
                })
                if (r.error) throw r.error
                setOtp('')
              })
            }}
          >
            <label className="field">
              Código del correo
              <input
                required
                autoComplete="one-time-code"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
              />
            </label>
            <button disabled={!auth || busy} className="btn-secondary">
              Verificar correo
            </button>
          </form>
        </>
      ) : (
        <>
          <button
            disabled={!auth || busy}
            className="btn-secondary"
            onClick={() => void action(mfa)}
          >
            Preparar segundo factor
          </button>
          {qr && (
            <div>
              <p className="mb-3 text-sm">
                Escanea con tu aplicación autenticadora. No compartas este
                código.
              </p>
              <img
                alt="Código QR privado para configurar segundo factor"
                className="max-w-full"
                src={qr}
              />
            </div>
          )}
          {factor && (
            <form
              noValidate
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault()
                if (!validateForm(e.currentTarget, notify)) return
                void action(async () => {
                  const r = await auth!.auth.mfa.challengeAndVerify({
                    factorId: factor,
                    code,
                  })
                  if (r.error) throw r.error
                  setCode('')
                  setQr('')
                  notify({
                    title: 'Segundo factor verificado',
                    message:
                      'El servidor comprobará tus permisos en cada operación.',
                    tone: 'success',
                  })
                })
              }}
            >
              <label className="field">
                Código del autenticador
                <input
                  required
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </label>
              <button disabled={busy} className="btn-primary">
                Verificar segundo factor
              </button>
            </form>
          )}
          {invitation && (
            <button
              disabled={busy}
              className="btn-primary"
              onClick={() =>
                void action(async () => {
                  if (
                    !(await confirm({
                      title: 'Aceptar invitación',
                      message:
                        'Se asignará el perfil y alcance definidos por la clínica. Debes verificar la identidad destinataria con MFA.',
                      confirmLabel: 'Aceptar acceso',
                    }))
                  )
                    return
                  await api(
                    '/team/accept',
                    {
                      method: 'POST',
                      body: JSON.stringify({ token: invitation }),
                    },
                    token,
                  )
                  onAccepted()
                  notify({
                    title: 'Acceso activado',
                    message: 'La invitación se consumió una sola vez.',
                    tone: 'success',
                  })
                })
              }
            >
              Aceptar invitación del equipo
            </button>
          )}
        </>
      )}
    </section>
  )
}
