import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, auth, type Appointment, type Catalog, type Document, type Service } from './api'

function today(timezone: string) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  return ['year', 'month', 'day'].map(type => parts.find(p => p.type === type)!.value).join('-')
}
function clock(value: string, timezone: string) {
  return new Intl.DateTimeFormat('es-CL', { timeZone: timezone, hour: '2-digit', minute: '2-digit', timeZoneName: 'shortOffset' }).format(new Date(value))
}
function dateTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat('es-CL', { timeZone: timezone, dateStyle: 'long', timeStyle: 'short' }).format(new Date(value))
}

export function BookingFlow() {
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
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [success, setSuccess] = useState<{ starts_at: string; account: string }>()
  const [portal, setPortal] = useState(false)
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const attempt = useRef<{ body: string; key: string } | null>(null)
  const selected = catalog?.services.find(s => s.service_id === serviceId && s.resource_id === resourceId)
  const tz = selected?.timezone ?? 'America/Santiago'

  async function loadCatalog() {
    const data = await api<Catalog>('/catalog')
    setCatalog(data)
  }
  useEffect(() => { loadCatalog().catch(e => setError(e.message)) }, [])
  useEffect(() => {
    if (!auth) return
    const { data } = auth.auth.onAuthStateChange((_event, session) => setToken(session?.access_token))
    return () => data.subscription.unsubscribe()
  }, [])
  useEffect(() => {
    if (!token) return
    api('/account/claim', { method: 'POST' }, token)
      .then(() => api<Appointment[]>('/appointments', {}, token))
      .then(setAppointments).catch(e => setError(e.message))
  }, [token])
  useEffect(() => {
    if (!selected || !day) { setSlots([]); return }
    let active = true
    setLoadingSlots(true); setSlot(''); setError('')
    const query = new URLSearchParams({ service_id: selected.service_id, resource_id: selected.resource_id, day })
    api<{ slots: string[] }>(`/availability?${query}`)
      .then(data => { if (active) setSlots(data.slots) })
      .catch(e => { if (active) setError(e.message) })
      .finally(() => { if (active) setLoadingSlots(false) })
    return () => { active = false }
  }, [selected?.service_id, selected?.resource_id, day])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!selected || !slot || inFlight.current) return
    const docs = catalog!.documents.filter(d => d.kind !== 'whatsapp' || whatsapp)
    if (docs.some(d => !accepted[d.id])) { setError('Lee y acepta los documentos para continuar.'); return }
    const body = JSON.stringify({ service_id: serviceId, resource_id: resourceId, starts_at: slot,
      patient: { name, email, ...(whatsapp ? { phone } : {}) }, whatsapp,
      create_account: createAccount && !token, consent_document_ids: docs.map(d => d.id) })
    // Preserve the same key after a network failure; a changed payload gets a new key.
    if (attempt.current?.body !== body) attempt.current = { body, key: crypto.randomUUID() }
    inFlight.current = true; setBusy(true); setError('')
    try {
      const result = await api<{ starts_at: string; account: string }>('/bookings', {
        method: 'POST', headers: { 'Idempotency-Key': attempt.current.key }, body,
      }, token)
      setSuccess(result); setName(''); setEmail(''); setPhone(''); attempt.current = null
      if (token) setAppointments(await api<Appointment[]>('/appointments', {}, token))
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false); inFlight.current = false }
  }

  async function login(event: FormEvent) {
    event.preventDefault()
    if (!auth) return
    setBusy(true); setError('')
    const { error } = await auth.auth.signInWithOtp({ email, options: {
      shouldCreateUser: false, emailRedirectTo: window.location.origin,
    } })
    setBusy(false)
    if (error) setError('No se pudo enviar el enlace. Comprueba tu correo o vuelve a intentarlo.')
    else setNotice('Si tu cuenta existe, recibirás un enlace para iniciar sesión.')
  }

  async function change(appointment: Appointment, action: string, starts_at?: string) {
    setBusy(true); setError('')
    try {
      await api(`/appointments/${appointment.id}`, { method: 'PATCH', body: JSON.stringify({
        action, expected_version: appointment.version, ...(starts_at ? { starts_at } : {}),
      }) }, token)
      setAppointments(await api<Appointment[]>('/appointments', {}, token))
      setNotice('Tu agenda está actualizada.')
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  async function exportData() {
    setBusy(true); setError('')
    try {
      const data = await api('/privacy/export', {}, token)
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      const a = document.createElement('a'); a.href = url; a.download = 'mis-datos-healthsync.json'; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  async function anonymize(patientId: string) {
    setBusy(true); setError('')
    try {
      await api('/privacy/requests', { method: 'POST', body: JSON.stringify({ patient_id: patientId, kind: 'anonymize' }) }, token)
      setNotice('Solicitud recibida. El responsable de privacidad revisará los plazos de conservación aplicables.')
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  const services = [...new Map(catalog?.services.map(s => [s.service_id, s]) ?? []).values()]
  return <div className="min-h-screen bg-slate-50 text-slate-800">
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <a href="/" className="flex items-center gap-3 text-xl font-bold tracking-tight text-teal-900">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal-700 text-2xl text-white" aria-hidden="true">+</span>HealthSync
        </a>
        <button className="btn-secondary" onClick={() => { setPortal(!portal); setError(''); setNotice('') }}>{portal ? 'Reservar una hora' : 'Mis horas'}</button>
      </div>
    </header>
    <main className="mx-auto max-w-6xl px-6 py-10 md:py-16">
      <p className="mb-3 text-xs font-bold uppercase tracking-[.2em] text-teal-700">{catalog?.tenant ?? 'Agenda de salud'}</p>
      <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">{portal ? 'Tu salud, en tus manos.' : 'Tu próxima hora, más cerca.'}</h1>
      <p className="mt-3 max-w-xl text-slate-500">{portal ? 'Confirma, modifica o anula tus reservas desde un mismo lugar.' : 'Elige la atención que necesitas. Puedes reservar sin crear una cuenta.'}</p>
      {error && <div role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</div>}
      {notice && <div role="status" className="mt-6 rounded-xl bg-teal-50 p-4 text-teal-900">{notice}</div>}
      {!catalog && !error && <p role="status" className="mt-8">Cargando agenda…</p>}
      {portal ? <section className="card mt-8 max-w-3xl">
        {!token ? <form onSubmit={login} className="space-y-5">
          <h2 className="text-xl font-semibold">Ingresa a tu portal</h2>
          <p className="text-sm text-slate-500">Recibe un enlace seguro en tu correo. No necesitas recordar una contraseña.</p>
          <label className="field">Correo electrónico<input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} /></label>
          <button className="btn-primary" disabled={busy || !auth}>Enviar enlace de acceso</button>
          {!auth && <p className="text-sm text-slate-500">El acceso a cuentas estará disponible cuando la clínica configure su proveedor de autenticación.</p>}
        </form> : <div className="space-y-6">
          <div className="flex flex-wrap gap-3"><button disabled={busy} className="btn-secondary" onClick={exportData}>Exportar mis datos</button>
            <button className="btn-secondary" onClick={() => auth?.auth.signOut()}>Cerrar sesión</button></div>
          {!appointments.length && <p>Aún no tienes horas vinculadas a esta cuenta.</p>}
          {appointments.map(a => <article key={a.id} className="rounded-xl border border-slate-200 p-5">
            <div className="flex flex-wrap justify-between gap-2"><h3 className="font-semibold">{a.service_name}</h3><span className="text-sm text-teal-700">{{ booked: 'Reservada', confirmed: 'Confirmada', cancelled: 'Anulada', completed: 'Realizada', no_show: 'No asistió' }[a.status]}</span></div>
            <p className="mt-2">{dateTime(a.starts_at, a.timezone)}</p><p className="text-sm text-slate-500">{a.public_name}</p>
            {['booked', 'confirmed'].includes(a.status) && <div className="mt-4 flex flex-wrap gap-3">
              {a.status === 'booked' && <button disabled={busy} className="btn-secondary" onClick={() => change(a, 'confirm')}>Confirmar</button>}
              <button disabled={busy} className="btn-secondary" onClick={() => change(a, 'cancel')}>Anular hora</button>
              <Reschedule appointment={a} disabled={busy} onChange={value => change(a, 'reschedule', value)} />
            </div>}
          </article>)}
          <p className="text-xs text-slate-500">Anticipación mínima: {catalog?.cancel_cutoff_minutes} min para anular; {catalog?.reschedule_cutoff_minutes} min para modificar. Puedes modificar una hora confirmada.</p>
          {[...new Set(appointments.map(a => a.patient_id))].map(id => <button key={id} disabled={busy} className="block text-sm text-slate-600 underline" onClick={() => anonymize(id)}>Solicitar anonimización del perfil · {id.slice(-6)}</button>)}
        </div>}
      </section> : success ? <section className="card mt-8 max-w-2xl space-y-5" role="status">
        <span className="grid h-14 w-14 place-items-center rounded-full bg-teal-50 text-2xl text-teal-700" aria-hidden="true">✓</span>
        <h2 className="text-2xl font-semibold">Tu hora está reservada</h2>
        <p>{selected?.service_name} · {dateTime(success.starts_at, tz)}</p>
        {success.account === 'queued' && <p className="rounded-xl bg-teal-50 p-4 text-sm">Solicitamos un enlace de acceso a <strong>tu correo</strong>. Verifícalo para activar tu cuenta y vincular esta reserva. No necesitas volver a ingresar tus datos.</p>}
        <p className="text-sm text-slate-500">La entrega de mensajes depende del proveedor de la clínica. Si no recibes el correo, contacta a la clínica.</p>
        <button className="btn-secondary" onClick={() => { setSuccess(undefined); setStep(1); setSlot(''); setAccepted({}); setCreateAccount(false) }}>Reservar otra hora</button>
      </section> : catalog && <div className="mt-10 grid gap-8 md:grid-cols-[240px_1fr]">
        <aside>
          <ol className="space-y-5" aria-label="Pasos de reserva">{['Atención y profesional', 'Fecha y hora', 'Tus datos'].map((label, i) => <li key={label} aria-current={step === i + 1 ? 'step' : undefined} className={`flex items-center gap-3 text-sm ${step === i + 1 ? 'font-semibold text-teal-800' : 'text-slate-400'}`}><span className={`grid h-8 w-8 place-items-center rounded-full border ${step >= i + 1 ? 'border-teal-700 bg-teal-700 text-white' : 'border-slate-200 bg-white'}`}>{step > i + 1 ? '✓' : i + 1}</span>{label}</li>)}</ol>
          <div className="mt-10 rounded-xl bg-teal-50 p-5 text-sm text-teal-900"><p className="font-semibold">Solo lo necesario</p><p className="mt-2 leading-relaxed text-teal-800">Para reservar pedimos tu nombre y correo. No necesitamos tu RUT ni antecedentes médicos.</p></div>
        </aside>
        <section className="card">
          <div className="mb-7 flex items-center justify-between"><h2 className="text-xl font-semibold">{['Elige tu atención', 'Encuentra tu horario', 'Completa tu reserva'][step - 1]}</h2><span className="text-xs text-slate-400">PASO {step} DE 3</span></div>
          {step === 1 && <div className="space-y-6">
            <label className="field">Servicio<select value={serviceId} onChange={e => { setServiceId(e.target.value); setResourceId(''); setSlot('') }}><option value="">Selecciona una atención</option>{services.map(s => <option key={s.service_id} value={s.service_id}>{s.service_name} · {s.branch}</option>)}</select></label>
            <label className="field">Profesional<select value={resourceId} disabled={!serviceId} onChange={e => { setResourceId(e.target.value); setDay('') }}><option value="">Selecciona un profesional</option>{catalog.services.filter(s => s.service_id === serviceId).map(s => <option key={s.resource_id} value={s.resource_id}>{s.public_name}</option>)}</select></label>
            {selected && <div className="rounded-xl border border-slate-100 bg-slate-50 p-5 text-sm"><p className="font-medium">{selected.specialty} · {selected.branch}</p><p className="mt-2 text-slate-500">{selected.duration_minutes} minutos de atención. La agenda reserva {selected.buffer_minutes} minutos adicionales de preparación.</p></div>}
            <button className="btn-primary" disabled={!selected} onClick={() => { setDay(today(tz)); setStep(2) }}>Ver horarios disponibles <span aria-hidden="true">→</span></button>
          </div>}
          {step === 2 && <div className="space-y-6">
            <label className="field">Fecha de atención<input type="date" value={day} min={today(tz)} required onChange={e => setDay(e.target.value)} /></label>
            <p className="text-xs text-slate-500">Horarios en {tz}. Se vuelven a validar al reservar.</p>
            {loadingSlots ? <p role="status">Buscando horarios disponibles…</p> : <fieldset><legend className="mb-3 text-sm font-medium">Horas disponibles</legend><div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{slots.map(s => <button type="button" aria-pressed={slot === s} key={s} onClick={() => setSlot(s)} className={`rounded-xl border px-3 py-3 text-sm transition ${slot === s ? 'border-teal-700 bg-teal-700 text-white' : 'border-slate-200 hover:border-teal-600 hover:bg-teal-50'}`}>{clock(s, tz)}</button>)}</div>{!slots.length && <p className="text-sm text-slate-500">No hay horas disponibles para este día. Prueba con otra fecha.</p>}</fieldset>}
            <div className="flex justify-between gap-3"><button className="btn-secondary" onClick={() => setStep(1)}>Volver</button><button className="btn-primary" disabled={!slot || loadingSlots} onClick={() => setStep(3)}>Continuar</button></div>
          </div>}
          {step === 3 && <form onSubmit={submit} className="space-y-5">
            <div className="rounded-xl bg-slate-50 p-4 text-sm"><p className="font-medium">{selected?.service_name}</p><p className="mt-1 text-slate-500">{slot && dateTime(slot, tz)} · {selected?.public_name}</p></div>
            <label className="field">Nombre y apellido<input autoComplete="name" minLength={2} maxLength={120} required value={name} onChange={e => setName(e.target.value)} /></label>
            <label className="field">Correo electrónico<input type="email" autoComplete="email" maxLength={254} required value={email} onChange={e => setEmail(e.target.value)} /></label>
            <label className="check"><input type="checkbox" checked={whatsapp} onChange={e => { setWhatsapp(e.target.checked); setPhone('') }} />Recibir recordatorios por WhatsApp (opcional)</label>
            {whatsapp && <label className="field">Teléfono con código de país<input type="tel" autoComplete="tel" placeholder="+56912345678" pattern="\+[1-9][0-9]{7,14}" required value={phone} onChange={e => setPhone(e.target.value)} /></label>}
            {!token && <div className="rounded-xl border border-teal-100 bg-teal-50 p-5"><label className="check font-medium text-teal-900"><input type="checkbox" checked={createAccount} disabled={!catalog.account_available || !auth} onChange={e => setCreateAccount(e.target.checked)} />Crear cuenta para gestionar mis horas y ver exámenes</label><p className="mt-2 pl-7 text-xs leading-relaxed text-teal-800">{catalog.account_available && auth ? 'Usaremos estos mismos datos. Activa tu cuenta con un enlace de verificación enviado a tu correo.' : 'La reserva como invitado está disponible. La clínica aún debe configurar el acceso a cuentas.'}</p></div>}
            <fieldset className="space-y-4 border-t border-slate-100 pt-5"><legend className="sr-only">Consentimientos</legend>{catalog.documents.filter(d => d.kind !== 'whatsapp' || whatsapp).map(d => <Consent key={d.id} document={d} checked={!!accepted[d.id]} onChange={value => setAccepted({ ...accepted, [d.id]: value })} />)}</fieldset>
            <p className="text-xs leading-relaxed text-slate-500">Puedes solicitar acceso, rectificación, oposición y anonimización de tus datos. Las obligaciones legales de conservación serán revisadas por la clínica.</p>
            <div className="flex justify-between gap-3"><button type="button" disabled={busy} className="btn-secondary" onClick={() => setStep(2)}>Volver</button><button disabled={busy || catalog.documents.filter(d => d.kind !== 'whatsapp' || whatsapp).some(d => !accepted[d.id])} className="btn-primary">{busy ? 'Reservando…' : 'Reservar mi hora'}</button></div>
          </form>}
        </section>
      </div>}
      <footer className="mt-14 border-t border-slate-200 pt-6 text-xs text-slate-400">HealthSync · Atención conectada, datos protegidos. {catalog?.documents.some(d => d.version.startsWith('demo')) && <span className="text-amber-700">Entorno de demostración. Utiliza datos ficticios.</span>}</footer>
    </main>
  </div>
}

function Consent({ document, checked, onChange }: { document: Document; checked: boolean; onChange: (value: boolean) => void }) {
  const label = { terms: 'Acepto los términos de la reserva', sensitive_data: 'Consiento el tratamiento de mis datos sensibles para esta reserva', whatsapp: 'Acepto el tratamiento de mi teléfono para WhatsApp' }[document.kind]
  return <div><label className="check"><input type="checkbox" required checked={checked} onChange={e => onChange(e.target.checked)} />{label}</label><details className="ml-7 mt-1 text-xs text-slate-500"><summary className="cursor-pointer underline">Leer documento · versión {document.version}</summary><p className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 leading-relaxed">{document.body}</p></details></div>
}

function Reschedule({ appointment, disabled, onChange }: { appointment: Appointment; disabled: boolean; onChange: (value: string) => void }) {
  const [value, setValue] = useState('')
  return <details className="w-full"><summary className="cursor-pointer text-sm text-teal-700 underline">Modificar fecha y hora</summary><form className="mt-3 flex flex-wrap gap-3" onSubmit={e => { e.preventDefault(); onChange(new Date(value).toISOString()) }}><label className="field text-xs">Nueva hora (zona de tu dispositivo; la clínica usa {appointment.timezone})<input type="datetime-local" required step={900} value={value} onChange={e => setValue(e.target.value)} /></label><button disabled={disabled || !value} className="btn-secondary">Validar y modificar</button></form></details>
}
