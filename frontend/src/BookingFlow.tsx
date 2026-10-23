import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  api,
  auth,
  ANONYMOUS,
  type Appointment,
  type Catalog,
  type Document,
  type SessionProfile,
} from './api'
import { DialogProvider, useDialog, validateForm } from './Dialog'
import { COMPANY_NAME, PRODUCT_NAME } from './brand'
import { ClinicalWorkspace, PlatformWorkspace } from './Workspace'
import { TeamAccess } from './Team'

function today(timezone: string) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  return ['year', 'month', 'day']
    .map((type) => parts.find((p) => p.type === type)!.value)
    .join('-')
}
function clock(value: string, timezone: string) {
  return new Intl.DateTimeFormat('es-CL', {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'shortOffset',
  }).format(new Date(value))
}
function dateTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat('es-CL', {
    timeZone: timezone,
    dateStyle: 'long',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function BookingFlow() {
  return (
    <DialogProvider>
      <BookingScreen />
    </DialogProvider>
  )
}

function BookingScreen() {
  const { notify, confirm } = useDialog()
  const [catalog, setCatalog] = useState<Catalog>()
  const [step, setStep] = useState(1)
  const [serviceId, setServiceId] = useState('')
  const [resourceId, setResourceId] = useState('')
  const [day, setDay] = useState('')
  const [slots, setSlots] = useState<string[]>([])
  const [slot, setSlot] = useState('')
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [whatsapp, setWhatsapp] = useState(false)
  const [createAccount, setCreateAccount] = useState(false)
  const [accepted, setAccepted] = useState<Record<string, boolean>>({})
  const [token, setToken] = useState<string>()
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false)
  const [error, setErrorState] = useState('')
  function setError(value: string) {
    setErrorState(value)
    if (value)
      notify({
        title: 'No pudimos completar la acción',
        message: value,
        tone: 'error',
      })
  }
  function setNotice(value: string) {
    if (value)
      notify({
        title: 'Información de tu cuenta',
        message: value,
        tone: 'success',
      })
  }
  const [success, setSuccess] = useState<{
    starts_at: string
    account: string
  }>()
  const [view, setView] = useState<
    'booking' | 'patient' | 'workspace' | 'platform'
  >(() =>
    window.location.hash.startsWith('#team-invite=') ? 'workspace' : 'booking',
  )
  const [invitation, setInvitation] = useState(() =>
    window.location.hash.startsWith('#team-invite=')
      ? window.location.hash.slice(13)
      : '',
  )
  const [sessionRevision, setSessionRevision] = useState(0)
  useEffect(() => {
    if (window.location.hash.startsWith('#team-invite='))
      window.history.replaceState(null, '', window.location.pathname)
  }, [])
  const portal = view === 'patient'
  const [profile, setProfile] = useState<SessionProfile>(ANONYMOUS)
  const [appointmentFilter, setAppointmentFilter] = useState<
    'upcoming' | 'history'
  >('upcoming')
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const attempt = useRef<{ body: string; key: string } | null>(null)
  const selected = catalog?.services.find(
    (s) => s.service_id === serviceId && s.resource_id === resourceId,
  )
  const tz = selected?.timezone ?? 'America/Santiago'

  async function loadCatalog() {
    const data = await api<Catalog>('/catalog')
    setCatalog(data)
  }
  useEffect(() => {
    loadCatalog().catch((e) => setError(e.message))
  }, [])
  useEffect(() => {
    if (!auth) return
    const { data } = auth.auth.onAuthStateChange((_event, session) =>
      setToken(session?.access_token),
    )
    return () => data.subscription.unsubscribe()
  }, [])
  useEffect(() => {
    if (!token) {
      setProfile(ANONYMOUS)
      setAppointments([])
      return
    }
    setAppointments([])
    setProfile(ANONYMOUS)
    let active = true
    api<SessionProfile>('/session', {}, token)
      .then((data) => {
        if (active) setProfile(data)
      })
      .catch((e) => setError(e.message))
    api('/account/claim', { method: 'POST' }, token)
      .then(() => api<Appointment[]>('/appointments', {}, token))
      .then((data) => {
        if (active) setAppointments(data)
      })
      .catch((e) => setError(e.message))
    return () => {
      active = false
    }
  }, [token, sessionRevision])
  useEffect(() => {
    if (!selected || !day) {
      setSlots([])
      return
    }
    let active = true
    setLoadingSlots(true)
    setSlot('')
    setError('')
    const query = new URLSearchParams({
      service_id: selected.service_id,
      resource_id: selected.resource_id,
      day,
    })
    api<{ slots: string[] }>(`/availability?${query}`)
      .then((data) => {
        if (active) setSlots(data.slots)
      })
      .catch((e) => {
        if (active) setError(e.message)
      })
      .finally(() => {
        if (active) setLoadingSlots(false)
      })
    return () => {
      active = false
    }
  }, [selected?.service_id, selected?.resource_id, day])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!validateForm(event.currentTarget as HTMLFormElement, notify)) return
    if (!selected || !slot || inFlight.current) return
    const docs = catalog!.documents.filter(
      (d) => d.kind !== 'whatsapp' || whatsapp,
    )
    if (docs.some((d) => !accepted[d.id])) {
      setError('Lee y acepta los documentos para continuar.')
      return
    }
    const body = JSON.stringify({
      service_id: serviceId,
      resource_id: resourceId,
      starts_at: slot,
      patient: { name, email, ...(whatsapp ? { phone } : {}) },
      whatsapp,
      create_account: createAccount && !token,
      consent_document_ids: docs.map((d) => d.id),
    })
    // Preserve the same key after a network failure; a changed payload gets a new key.
    if (attempt.current?.body !== body)
      attempt.current = { body, key: crypto.randomUUID() }
    inFlight.current = true
    setBusy(true)
    setError('')
    try {
      const result = await api<{ starts_at: string; account: string }>(
        '/bookings',
        {
          method: 'POST',
          headers: { 'Idempotency-Key': attempt.current.key },
          body,
        },
        token,
      )
      setSuccess(result)
      setName('')
      setEmail('')
      setPhone('')
      attempt.current = null
      notify({
        title: 'Tu hora está reservada',
        message: `${dateTime(result.starts_at, tz)}. ${result.account === 'queued' ? 'Solicitamos un enlace de verificación para activar tu cuenta con los mismos datos.' : 'Puedes revisar el detalle de la reserva en esta pantalla.'}`,
        tone: 'success',
      })
      if (token)
        setAppointments(await api<Appointment[]>('/appointments', {}, token))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
      inFlight.current = false
    }
  }

  async function login(event: FormEvent) {
    event.preventDefault()
    if (!validateForm(event.currentTarget as HTMLFormElement, notify) || !auth)
      return
    setBusy(true)
    setError('')
    try {
      const { error } = await auth.auth.signInWithOtp({
        email,
        options: {
          shouldCreateUser: false,
          emailRedirectTo: window.location.origin,
        },
      })
      if (error)
        setError(
          'No se pudo enviar el enlace. Comprueba tu correo o vuelve a intentarlo.',
        )
      else
        setNotice(
          'Si tu cuenta existe, recibirás un enlace para iniciar sesión.',
        )
    } catch {
      setError(
        'No pudimos conectar con el acceso a cuentas. Revisa tu conexión e inténtalo de nuevo.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function change(
    appointment: Appointment,
    action: string,
    starts_at?: string,
  ) {
    if (
      action !== 'confirm' &&
      !(await confirm({
        title: action === 'cancel' ? 'Anular esta cita' : 'Modificar tu cita',
        message:
          action === 'cancel'
            ? 'Liberaremos este horario. Puedes reservar una nueva cita cuando lo necesites.'
            : `La nueva hora será ${dateTime(starts_at!, appointment.timezone)}. Comprobaremos nuevamente la disponibilidad.`,
        confirmLabel:
          action === 'cancel' ? 'Sí, anular cita' : 'Validar y modificar',
        tone: action === 'cancel' ? 'danger' : 'info',
      }))
    )
      return
    setBusy(true)
    setError('')
    try {
      await api(
        `/appointments/${appointment.id}`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            action,
            expected_version: appointment.version,
            ...(starts_at ? { starts_at } : {}),
          }),
        },
        token,
      )
      setAppointments(await api<Appointment[]>('/appointments', {}, token))
      setNotice('Tu agenda está actualizada.')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function exportData() {
    setBusy(true)
    setError('')
    try {
      const data = await api('/privacy/export', {}, token)
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }),
      )
      const a = document.createElement('a')
      a.href = url
      a.download = 'mis-datos-medical-appointment-system.json'
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      notify({
        title: 'Exportación preparada',
        message:
          'Preparamos el archivo con tus datos para descargar. Guárdalo en un lugar privado.',
        tone: 'success',
      })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function anonymize(patientId: string) {
    if (
      !(await confirm({
        title: 'Solicitar anonimización',
        message:
          'La clínica revisará tu solicitud y las obligaciones de conservación. Este paso registra la solicitud; la revisión puede requerir resolver citas pendientes.',
        confirmLabel: 'Enviar solicitud',
        tone: 'danger',
      }))
    )
      return
    setBusy(true)
    setError('')
    try {
      await api(
        '/privacy/requests',
        {
          method: 'POST',
          body: JSON.stringify({ patient_id: patientId, kind: 'anonymize' }),
        },
        token,
      )
      setNotice(
        'Solicitud recibida. El responsable de privacidad revisará los plazos de conservación aplicables.',
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function logout() {
    try {
      const result = await auth?.auth.signOut()
      if (result?.error) throw result.error
      setAppointments([])
      setProfile(ANONYMOUS)
      setToken(undefined)
      notify({
        title: 'Sesión cerrada',
        message: 'Cerramos tu acceso a este dispositivo.',
        tone: 'success',
      })
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const visibleAppointments = appointments.filter((a) =>
    appointmentFilter === 'upcoming'
      ? ['booked', 'confirmed'].includes(a.status) &&
        new Date(a.starts_at).getTime() >= Date.now()
      : !['booked', 'confirmed'].includes(a.status) ||
        new Date(a.starts_at).getTime() < Date.now(),
  )
  const services = [
    ...new Map(catalog?.services.map((s) => [s.service_id, s]) ?? []).values(),
  ]
  return (
    <div className="app-shell min-h-screen text-slate-800">
      <header className="app-header">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-5 px-5 py-5 sm:px-6">
          <a href="/" className="flex min-w-0 items-center gap-3">
            <span className="brand-mark" aria-hidden="true">
              <svg width="27" height="27" viewBox="0 0 28 28" fill="none">
                <path
                  d="M3 14h6l3-7 5 14 3-7h5"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <span>
              <span className="block max-w-64 text-base font-bold tracking-tight text-slate-900 sm:max-w-none sm:text-lg">
                {PRODUCT_NAME}
              </span>
              <span className="mt-1 block text-[11px] font-medium tracking-wide text-slate-500">
                Desarrollado por {COMPANY_NAME}
              </span>
            </span>
          </a>
          <nav
            aria-label="Navegación principal"
            className="segmented w-full flex-wrap sm:w-auto"
          >
            <button
              aria-pressed={view === 'booking'}
              onClick={() => {
                setView('booking')
                setError('')
              }}
            >
              Reservar una cita
            </button>
            <button
              aria-pressed={portal}
              onClick={() => {
                setView('patient')
                setError('')
              }}
            >
              Mi portal
            </button>
            <button
              aria-pressed={view === 'workspace'}
              onClick={() => {
                setView('workspace')
                setError('')
              }}
            >
              Equipo clínico
            </button>
            {profile.platform_role && (
              <button
                aria-pressed={view === 'platform'}
                onClick={() => setView('platform')}
              >
                Admin SaaS
              </button>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10 md:py-16">
        <p className="mb-3 text-xs font-bold uppercase tracking-[.2em] text-indigo-700">
          {catalog?.tenant ?? 'Agenda de salud'}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
          {view === 'workspace'
            ? 'Un equipo conectado, una mejor atención.'
            : view === 'platform'
              ? 'Tu servicio, bajo control.'
              : portal
                ? 'Tu salud, en tus manos.'
                : 'Tu próxima cita, en un solo lugar.'}
        </h1>
        <p className="mt-3 max-w-xl text-slate-500">
          {view === 'workspace'
            ? 'Accede a tu agenda y a las funciones autorizadas de tu clínica.'
            : view === 'platform'
              ? 'Administración de organizaciones por Tresuryx SpA.'
              : portal
                ? 'Tus próximas citas y tu historial, siempre a mano.'
                : 'Agenda con tranquilidad. Elige tu atención, encuentra una hora y sigue con tu día.'}
        </p>

        {!catalog && !error && (
          <p role="status" className="mt-8">
            Cargando agenda…
          </p>
        )}
        {view === 'workspace' && (
          <TeamAccess
            token={token}
            invitation={invitation}
            onAccepted={() => {
              setInvitation('')
              setSessionRevision((x) => x + 1)
            }}
          />
        )}
        {view === 'workspace' && token ? (
          <ClinicalWorkspace token={token} profile={profile} />
        ) : view === 'platform' && token ? (
          <PlatformWorkspace token={token} />
        ) : view !== 'booking' ? (
          <section className="card mt-8 max-w-3xl">
            {!token ? (
              <form noValidate onSubmit={login} className="space-y-5">
                <h2 className="text-xl font-semibold">Ingresa a tu portal</h2>
                <p className="text-sm text-slate-500">
                  Recibe un enlace seguro en tu correo. No necesitas recordar
                  una contraseña.
                </p>
                <label className="field">
                  Correo electrónico
                  <input
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
                <button className="btn-primary" disabled={busy || !auth}>
                  Enviar enlace de acceso
                </button>
                {!auth && (
                  <p className="text-sm text-slate-500">
                    El acceso a cuentas estará disponible cuando la clínica
                    configure su proveedor de autenticación.
                  </p>
                )}
              </form>
            ) : (
              <div className="space-y-6">
                <div className="flex flex-wrap gap-3">
                  <button
                    disabled={busy}
                    className="btn-secondary"
                    onClick={exportData}
                  >
                    Exportar mis datos
                  </button>
                  <button className="btn-secondary" onClick={logout}>
                    Cerrar sesión
                  </button>
                </div>
                <div className="segmented w-fit">
                  <button
                    aria-pressed={appointmentFilter === 'upcoming'}
                    onClick={() => setAppointmentFilter('upcoming')}
                  >
                    Próximas citas
                  </button>
                  <button
                    aria-pressed={appointmentFilter === 'history'}
                    onClick={() => setAppointmentFilter('history')}
                  >
                    Historial
                  </button>
                </div>
                {!visibleAppointments.length && (
                  <p className="empty-state">
                    {appointmentFilter === 'upcoming'
                      ? 'No tienes próximas citas en esta clínica.'
                      : 'Tu historial aparecerá aquí cuando tengas citas pasadas o anuladas.'}
                  </p>
                )}
                {visibleAppointments.map((a) => (
                  <article
                    key={a.id}
                    className="rounded-xl border border-slate-200 p-5"
                  >
                    <div className="flex flex-wrap justify-between gap-2">
                      <h3 className="font-semibold">{a.service_name}</h3>
                      <span className="text-sm text-indigo-700">
                        {
                          {
                            booked: 'Reservada',
                            confirmed: 'Confirmada',
                            cancelled: 'Anulada',
                            completed: 'Realizada',
                            no_show: 'No asistió',
                          }[a.status]
                        }
                      </span>
                    </div>
                    <p className="mt-2">{dateTime(a.starts_at, a.timezone)}</p>
                    <p className="text-sm text-slate-500">{a.public_name}</p>
                    {['booked', 'confirmed'].includes(a.status) && (
                      <div className="mt-4 flex flex-wrap gap-3">
                        {a.status === 'booked' && (
                          <button
                            disabled={busy}
                            className="btn-secondary"
                            onClick={() => change(a, 'confirm')}
                          >
                            Confirmar
                          </button>
                        )}
                        <button
                          disabled={busy}
                          className="btn-secondary"
                          onClick={() => change(a, 'cancel')}
                        >
                          Anular hora
                        </button>
                        <Reschedule
                          appointment={a}
                          disabled={busy}
                          onChange={(value) => change(a, 'reschedule', value)}
                        />
                      </div>
                    )}
                  </article>
                ))}
                <p className="text-xs text-slate-500">
                  Anticipación mínima: {catalog?.cancel_cutoff_minutes} min para
                  anular; {catalog?.reschedule_cutoff_minutes} min para
                  modificar. Puedes modificar una hora confirmada.
                </p>
                {[...new Set(appointments.map((a) => a.patient_id))].map(
                  (id) => (
                    <button
                      key={id}
                      disabled={busy}
                      className="block text-sm text-slate-600 underline"
                      onClick={() => anonymize(id)}
                    >
                      Solicitar anonimización del perfil · {id.slice(-6)}
                    </button>
                  ),
                )}
              </div>
            )}
          </section>
        ) : success ? (
          <section className="card mt-8 max-w-2xl space-y-5" role="status">
            <span
              className="grid h-14 w-14 place-items-center rounded-full bg-indigo-50 text-2xl text-indigo-700"
              aria-hidden="true"
            >
              ✓
            </span>
            <h2 className="text-2xl font-semibold">Detalle de tu reserva</h2>
            <p>
              {selected?.service_name} · {dateTime(success.starts_at, tz)}
            </p>
            {success.account === 'queued' && (
              <p className="rounded-xl bg-indigo-50 p-4 text-sm">
                Solicitamos un enlace de acceso a <strong>tu correo</strong>.
                Verifícalo para activar tu cuenta y vincular esta reserva. No
                necesitas volver a ingresar tus datos.
              </p>
            )}
            <p className="text-sm text-slate-500">
              La entrega de mensajes depende del proveedor de la clínica. Si no
              recibes el correo, contacta a la clínica.
            </p>
            <button
              className="btn-secondary"
              onClick={() => {
                setSuccess(undefined)
                setStep(1)
                setSlot('')
                setAccepted({})
                setCreateAccount(false)
              }}
            >
              Reservar otra hora
            </button>
          </section>
        ) : (
          catalog && (
            <div className="mt-10 grid gap-8 md:grid-cols-[240px_1fr]">
              <aside>
                <ol
                  className="grid grid-cols-3 gap-3 md:block md:space-y-5"
                  aria-label="Pasos de reserva"
                >
                  {['Atención y profesional', 'Fecha y hora', 'Tus datos'].map(
                    (label, i) => (
                      <li
                        key={label}
                        aria-current={step === i + 1 ? 'step' : undefined}
                        className={`flex flex-col items-start gap-2 text-xs md:flex-row md:items-center md:gap-3 md:text-sm ${step === i + 1 ? 'font-semibold text-indigo-800' : 'text-slate-400'}`}
                      >
                        <span
                          className={`grid h-8 w-8 place-items-center rounded-full border ${step >= i + 1 ? 'border-indigo-700 bg-indigo-700 text-white' : 'border-slate-200 bg-white'}`}
                        >
                          {step > i + 1 ? '✓' : i + 1}
                        </span>
                        {label}
                      </li>
                    ),
                  )}
                </ol>
                <div className="mt-10 hidden rounded-xl bg-indigo-50 p-5 text-sm text-indigo-900 md:block">
                  <p className="font-semibold">Solo lo necesario</p>
                  <p className="mt-2 leading-relaxed text-indigo-800">
                    Para reservar pedimos tu nombre y correo. No necesitamos tu
                    RUT ni antecedentes médicos.
                  </p>
                </div>
              </aside>
              <section className="card">
                <div className="mb-7 flex items-center justify-between">
                  <h2 className="text-xl font-semibold">
                    {
                      [
                        'Elige tu atención',
                        'Encuentra tu horario',
                        'Completa tu reserva',
                      ][step - 1]
                    }
                  </h2>
                  <span className="text-xs text-slate-400">
                    PASO {step} DE 3
                  </span>
                </div>
                {step === 1 && (
                  <div className="space-y-6">
                    <label className="field">
                      Servicio
                      <select
                        value={serviceId}
                        onChange={(e) => {
                          setServiceId(e.target.value)
                          setResourceId('')
                          setSlot('')
                        }}
                      >
                        <option value="">Selecciona una atención</option>
                        {services.map((s) => (
                          <option key={s.service_id} value={s.service_id}>
                            {s.service_name} · {s.branch}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      Profesional
                      <select
                        value={resourceId}
                        disabled={!serviceId}
                        onChange={(e) => {
                          setResourceId(e.target.value)
                          setDay('')
                        }}
                      >
                        <option value="">Selecciona un profesional</option>
                        {catalog.services
                          .filter((s) => s.service_id === serviceId)
                          .map((s) => (
                            <option key={s.resource_id} value={s.resource_id}>
                              {s.public_name}
                            </option>
                          ))}
                      </select>
                    </label>
                    {selected && (
                      <div className="rounded-xl border border-slate-100 bg-slate-50 p-5 text-sm">
                        <p className="font-medium">
                          {selected.specialty} · {selected.branch}
                        </p>
                        <p className="mt-2 text-slate-500">
                          {selected.duration_minutes} minutos de atención. La
                          agenda reserva {selected.buffer_minutes} minutos
                          adicionales de preparación.
                        </p>
                      </div>
                    )}
                    <button
                      className="btn-primary"
                      disabled={!selected}
                      onClick={() => {
                        setDay(today(tz))
                        setStep(2)
                      }}
                    >
                      Ver horarios disponibles <span aria-hidden="true">→</span>
                    </button>
                  </div>
                )}
                {step === 2 && (
                  <div className="space-y-6">
                    <label className="field">
                      Fecha de atención
                      <input
                        type="date"
                        value={day}
                        min={today(tz)}
                        required
                        onChange={(e) => setDay(e.target.value)}
                      />
                    </label>
                    <p className="text-xs text-slate-500">
                      Horarios en {tz}. Se vuelven a validar al reservar.
                    </p>
                    {loadingSlots ? (
                      <p role="status">Buscando horarios disponibles…</p>
                    ) : (
                      <fieldset>
                        <legend className="mb-3 text-sm font-medium">
                          Horas disponibles
                        </legend>
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                          {slots.map((s) => (
                            <button
                              type="button"
                              aria-pressed={slot === s}
                              key={s}
                              onClick={() => setSlot(s)}
                              className={`rounded-xl border px-3 py-3 text-sm transition ${slot === s ? 'border-indigo-700 bg-indigo-700 text-white' : 'border-slate-200 hover:border-indigo-600 hover:bg-indigo-50'}`}
                            >
                              {clock(s, tz)}
                            </button>
                          ))}
                        </div>
                        {!slots.length && (
                          <p className="text-sm text-slate-500">
                            No hay horas disponibles para este día. Prueba con
                            otra fecha.
                          </p>
                        )}
                      </fieldset>
                    )}
                    <div className="flex justify-between gap-3">
                      <button
                        className="btn-secondary"
                        onClick={() => setStep(1)}
                      >
                        Volver
                      </button>
                      <button
                        className="btn-primary"
                        disabled={!slot || loadingSlots}
                        onClick={() => setStep(3)}
                      >
                        Continuar
                      </button>
                    </div>
                  </div>
                )}
                {step === 3 && (
                  <form noValidate onSubmit={submit} className="space-y-5">
                    <div className="rounded-xl bg-slate-50 p-4 text-sm">
                      <p className="font-medium">{selected?.service_name}</p>
                      <p className="mt-1 text-slate-500">
                        {slot && dateTime(slot, tz)} · {selected?.public_name}
                      </p>
                    </div>
                    <label className="field">
                      Nombre y apellido
                      <input
                        autoComplete="name"
                        minLength={2}
                        maxLength={120}
                        required
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      Correo electrónico
                      <input
                        type="email"
                        autoComplete="email"
                        maxLength={254}
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                      />
                    </label>
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={whatsapp}
                        onChange={(e) => {
                          setWhatsapp(e.target.checked)
                          setPhone('')
                        }}
                      />
                      Recibir recordatorios por WhatsApp (opcional)
                    </label>
                    {whatsapp && (
                      <label className="field">
                        Teléfono con código de país
                        <input
                          type="tel"
                          autoComplete="tel"
                          placeholder="+56912345678"
                          pattern="\+[1-9][0-9]{7,14}"
                          required
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                        />
                      </label>
                    )}
                    {!token && (
                      <div className="rounded-xl border border-indigo-100 bg-indigo-50 p-5">
                        <label className="check font-medium text-indigo-900">
                          <input
                            type="checkbox"
                            checked={createAccount}
                            disabled={!catalog.account_available || !auth}
                            onChange={(e) => setCreateAccount(e.target.checked)}
                          />
                          Crear cuenta para gestionar mis horas y ver exámenes
                        </label>
                        <p className="mt-2 pl-7 text-xs leading-relaxed text-indigo-800">
                          {catalog.account_available && auth
                            ? 'Usaremos estos mismos datos. Activa tu cuenta con un enlace de verificación enviado a tu correo.'
                            : 'La reserva como invitado está disponible. La clínica aún debe configurar el acceso a cuentas.'}
                        </p>
                      </div>
                    )}
                    <fieldset className="space-y-4 border-t border-slate-100 pt-5">
                      <legend className="sr-only">Consentimientos</legend>
                      {catalog.documents
                        .filter((d) => d.kind !== 'whatsapp' || whatsapp)
                        .map((d) => (
                          <Consent
                            key={d.id}
                            document={d}
                            checked={!!accepted[d.id]}
                            onChange={(value) =>
                              setAccepted({ ...accepted, [d.id]: value })
                            }
                          />
                        ))}
                    </fieldset>
                    <p className="text-xs leading-relaxed text-slate-500">
                      Puedes solicitar acceso, rectificación, oposición y
                      anonimización de tus datos. Las obligaciones legales de
                      conservación serán revisadas por la clínica.
                    </p>
                    <div className="flex justify-between gap-3">
                      <button
                        type="button"
                        disabled={busy}
                        className="btn-secondary"
                        onClick={() => setStep(2)}
                      >
                        Volver
                      </button>
                      <button
                        disabled={
                          busy ||
                          catalog.documents
                            .filter((d) => d.kind !== 'whatsapp' || whatsapp)
                            .some((d) => !accepted[d.id])
                        }
                        className="btn-primary"
                      >
                        {busy ? 'Reservando…' : 'Reservar mi hora'}
                      </button>
                    </div>
                  </form>
                )}
              </section>
            </div>
          )
        )}
        <footer className="mt-14 flex flex-wrap justify-between gap-3 border-t border-slate-200/70 pt-6 text-xs text-slate-500">
          <span>
            {PRODUCT_NAME} · Desarrollado por {COMPANY_NAME}.
          </span>{' '}
          {catalog?.documents.some((d) => d.version.startsWith('demo')) && (
            <span className="text-amber-700">
              Entorno de demostración. Utiliza datos ficticios.
            </span>
          )}
        </footer>
      </main>
    </div>
  )
}

function Consent({
  document,
  checked,
  onChange,
}: {
  document: Document
  checked: boolean
  onChange: (value: boolean) => void
}) {
  const label = {
    terms: 'Acepto los términos de la reserva',
    sensitive_data:
      'Consiento el tratamiento de mis datos sensibles para esta reserva',
    whatsapp: 'Acepto el tratamiento de mi teléfono para WhatsApp',
  }[document.kind]
  return (
    <div>
      <label className="check">
        <input
          type="checkbox"
          required
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        {label}
      </label>
      <details className="ml-7 mt-1 text-xs text-slate-500">
        <summary className="cursor-pointer underline">
          Leer documento · versión {document.version}
        </summary>
        <p className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 leading-relaxed">
          {document.body}
        </p>
      </details>
    </div>
  )
}

function Reschedule({
  appointment,
  disabled,
  onChange,
}: {
  appointment: Appointment
  disabled: boolean
  onChange: (value: string) => void
}) {
  const [value, setValue] = useState('')
  const { notify } = useDialog()
  return (
    <details className="w-full">
      <summary className="cursor-pointer text-sm text-indigo-700 underline">
        Modificar fecha y hora
      </summary>
      <form
        noValidate
        className="mt-3 flex flex-wrap gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (validateForm(e.currentTarget, notify))
            onChange(new Date(value).toISOString())
        }}
      >
        <label className="field text-xs">
          Nueva hora (zona de tu dispositivo; la clínica usa{' '}
          {appointment.timezone})
          <input
            type="datetime-local"
            required
            step={900}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </label>
        <button disabled={disabled || !value} className="btn-secondary">
          Validar y modificar
        </button>
      </form>
    </details>
  )
}
