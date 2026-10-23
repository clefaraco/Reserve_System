import { useEffect, useState } from 'react'
import { api, platformApi, type Appointment, type SessionProfile } from './api'
import { useDialog } from './Dialog'
import { Team } from './Team'

type Organization = {
  branches: {
    id: string
    name: string
    timezone: string
    organization_unit_id: string | null
  }[]
  units: { id: string; name: string; parent_id: string | null; kind: string }[]
}
type StaffAppointment = Appointment & {
  patient_name: string
  branch: string
  checked_in_at: string | null
}
const roles: Record<string, string> = {
  admin: 'Administración de la clínica',
  scheduler: 'Coordinación de agenda',
  reception: 'Recepción',
  clinician: 'Mi agenda médica',
  finance: 'Finanzas · resumen operativo',
  privacy: 'Responsable de privacidad',
}
export const statusNames: Record<string, string> = {
  booked: 'Reservada',
  confirmed: 'Confirmada',
  cancelled: 'Anulada',
  completed: 'Realizada',
  no_show: 'No asistió',
}

export function ClinicalWorkspace({
  token,
  profile,
}: {
  token: string
  profile: SessionProfile
}) {
  const { notify, confirm } = useDialog()
  const [organization, setOrganization] = useState<Organization>({
    branches: [],
    units: [],
  })
  const [day, setDay] = useState(
    new Intl.DateTimeFormat('en-CA').format(new Date()),
  )
  const [branch, setBranch] = useState('')
  const [offset, setOffset] = useState(0)
  const [appointments, setAppointments] = useState<StaffAppointment[]>([])
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<'calendar' | 'organization' | 'team'>(
    'calendar',
  )
  const [revision, setRevision] = useState(0)
  const can = (capability: string) => profile.capabilities.includes(capability)
  useEffect(() => {
    if (!can('organization.read')) return
    let active = true
    api<Organization>('/organization', {}, token)
      .then((data) => {
        if (active) setOrganization(data)
      })
      .catch((e) => {
        if (active)
          notify({
            title: 'No pudimos cargar tu organización',
            message: e.message,
            tone: 'error',
          })
      })
    return () => {
      active = false
    }
  }, [token, profile.role])
  useEffect(() => {
    if (!can('reports.read')) {
      setLoading(false)
      return
    }
    let active = true
    setLoading(true)
    const query = new URLSearchParams({
      day,
      offset: String(offset),
      ...(branch ? { branch_id: branch } : {}),
    })
    Promise.all([
      api<{ counts: Record<string, number> }>(
        `/staff/summary?${query}`,
        {},
        token,
      ),
      can('calendar.read')
        ? api<{ items: StaffAppointment[]; has_more: boolean }>(
            `/staff/appointments?${query}`,
            {},
            token,
          )
        : Promise.resolve({ items: [], has_more: false }),
    ])
      .then(([summary, calendar]) => {
        if (active) {
          setCounts(summary.counts)
          setAppointments(calendar.items)
          setHasMore(calendar.has_more)
        }
      })
      .catch((e) => {
        if (active) {
          setCounts({})
          setAppointments([])
          notify({
            title: 'No pudimos cargar la agenda',
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
  }, [token, profile.role, day, branch, offset, revision])

  async function mark(appointment: StaffAppointment, action: string) {
    const label =
      action === 'check_in'
        ? 'Registrar llegada'
        : action === 'complete'
          ? 'Cerrar atención'
          : 'Marcar inasistencia'
    if (
      !(await confirm({
        title: label,
        message: `${appointment.patient_name} · ${appointment.service_name}. Esta acción quedará registrada en la auditoría.`,
        confirmLabel: label,
        tone: action === 'no_show' ? 'danger' : 'info',
      }))
    )
      return
    setBusy(true)
    try {
      await api(
        `/staff/appointments/${appointment.id}/attendance`,
        {
          method: 'POST',
          body: JSON.stringify({
            action,
            expected_version: appointment.version,
          }),
        },
        token,
      )
      setRevision((value) => value + 1)
      notify({
        title: 'Agenda actualizada',
        message: 'El registro se guardó correctamente.',
        tone: 'success',
      })
    } catch (e) {
      notify({
        title: 'No pudimos guardar el cambio',
        message: (e as Error).message,
        tone: 'error',
      })
    } finally {
      setBusy(false)
    }
  }
  if (!profile.role)
    return (
      <section className="card mt-8">
        <h2 className="text-xl font-semibold">Tu cuenta está activa</h2>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          El administrador de la clínica debe asignarte un perfil y las
          sucursales o agendas correspondientes para acceder al equipo.
        </p>
      </section>
    )
  return (
    <section className="mt-8 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="eyebrow">Espacio de trabajo</p>
          <h2 className="mt-2 text-2xl font-semibold">
            {roles[profile.role] ?? 'Equipo de la clínica'}
          </h2>
        </div>
        <div className="segmented">
          <button
            aria-pressed={tab === 'calendar'}
            onClick={() => setTab('calendar')}
          >
            Agenda y actividad
          </button>
          {can('team.manage') && (
            <button
              aria-pressed={tab === 'team'}
              onClick={() => setTab('team')}
            >
              Equipo
            </button>
          )}
          {can('organization.read') && (
            <button
              aria-pressed={tab === 'organization'}
              onClick={() => setTab('organization')}
            >
              Organización
            </button>
          )}
        </div>
      </div>
      {tab === 'team' ? (
        <Team token={token} />
      ) : tab === 'organization' ? (
        <div className="card">
          <h3 className="text-lg font-semibold">
            Red y sucursales autorizadas
          </h3>
          <p className="mt-2 text-sm text-slate-500">
            Una clínica puede trabajar con una sola sede o con una red de
            regiones, comunas y agencias.
          </p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {organization.branches.map((b) => (
              <article className="soft-panel" key={b.id}>
                <h4 className="font-semibold">{b.name}</h4>
                <p className="mt-2 text-sm text-slate-500">{b.timezone}</p>
                <p className="mt-2 text-xs text-indigo-700">
                  {organization.units.find(
                    (u) => u.id === b.organization_unit_id,
                  )?.name ?? 'Sede independiente'}
                </p>
              </article>
            ))}
          </div>
          {!organization.branches.length && (
            <p className="mt-6 text-sm text-slate-500">
              Aún no tienes sucursales asignadas.
            </p>
          )}
          {organization.units.length > 0 && (
            <div className="mt-6 border-t border-slate-100 pt-4">
              <h4 className="text-sm font-semibold">
                Unidades organizativas visibles
              </h4>
              <ul className="mt-3 flex flex-wrap gap-2">
                {organization.units.map((u) => (
                  <li key={u.id} className="badge">
                    {u.name}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <>
          {can('reports.read') && (
            <div className="card flex flex-wrap items-end gap-4">
              <label className="field flex-1">
                Fecha de actividad
                <input
                  type="date"
                  value={day}
                  onChange={(e) => {
                    if (e.target.value) {
                      setDay(e.target.value)
                      setOffset(0)
                    }
                  }}
                />
              </label>
              <label className="field flex-1">
                Sucursal
                <select
                  value={branch}
                  onChange={(e) => {
                    setBranch(e.target.value)
                    setOffset(0)
                  }}
                >
                  <option value="">Todas mis sucursales</option>
                  {organization.branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="btn-secondary"
                disabled={loading || busy}
                onClick={() => setRevision((n) => n + 1)}
              >
                Actualizar
              </button>
            </div>
          )}
          {can('reports.read') && (
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                [
                  'Citas del día',
                  Object.values(counts).reduce((a, b) => a + b, 0),
                ],
                ['Atenciones realizadas', counts.completed ?? 0],
                ['Inasistencias', counts.no_show ?? 0],
              ].map(([label, value]) => (
                <article className="card" key={label}>
                  <p className="text-sm text-slate-500">{label}</p>
                  <p className="mt-3 text-3xl font-semibold tracking-tight">
                    {loading ? '—' : value}
                  </p>
                </article>
              ))}
            </div>
          )}
          {loading ? (
            <div className="card" role="status">
              Cargando tu actividad…
            </div>
          ) : can('calendar.read') ? (
            <div className="card">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">
                  {profile.role === 'clinician'
                    ? 'Mis citas agendadas'
                    : 'Agenda de atención'}
                </h3>
                <span className="badge">Acceso por perfil</span>
              </div>
              {!appointments.length && (
                <div className="empty-state">
                  No hay citas en esta fecha dentro de tus sucursales o recursos
                  autorizados.
                </div>
              )}
              <div className="mt-5 space-y-4">
                {appointments.map((a) => (
                  <article className="appointment-row" key={a.id}>
                    <div>
                      <p className="text-sm font-semibold text-indigo-700">
                        {new Intl.DateTimeFormat('es-CL', {
                          timeZone: a.timezone,
                          hour: '2-digit',
                          minute: '2-digit',
                        }).format(new Date(a.starts_at))}{' '}
                        · {statusNames[a.status]}
                      </p>
                      <h4 className="mt-2 font-semibold">{a.patient_name}</h4>
                      <p className="mt-1 text-sm text-slate-500">
                        {a.service_name} · {a.public_name}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {a.branch} · {a.timezone}
                        {a.checked_in_at ? ' · Llegada registrada' : ''}
                      </p>
                    </div>
                    {['booked', 'confirmed'].includes(a.status) && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {!a.checked_in_at && (
                          <button
                            disabled={busy}
                            className="btn-secondary"
                            onClick={() => mark(a, 'check_in')}
                          >
                            Registrar llegada
                          </button>
                        )}
                        {['admin', 'clinician'].includes(profile.role!) && (
                          <button
                            disabled={busy}
                            className="btn-secondary"
                            onClick={() => mark(a, 'complete')}
                          >
                            Atención realizada
                          </button>
                        )}
                        <button
                          disabled={busy}
                          className="btn-secondary"
                          onClick={() => mark(a, 'no_show')}
                        >
                          No asistió
                        </button>
                      </div>
                    )}
                  </article>
                ))}
              </div>
              <div className="mt-5 flex justify-between">
                <button
                  className="btn-secondary"
                  disabled={!offset || busy}
                  onClick={() => setOffset((value) => Math.max(0, value - 50))}
                >
                  Anterior
                </button>
                <button
                  className="btn-secondary"
                  disabled={!hasMore || busy}
                  onClick={() => setOffset((value) => value + 50)}
                >
                  Siguiente
                </button>
              </div>
            </div>
          ) : (
            <div className="card">
              <h3 className="text-lg font-semibold">
                {profile.role === 'finance'
                  ? 'Control financiero por etapas'
                  : 'Funciones específicas de tu perfil'}
              </h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                {profile.role === 'finance'
                  ? 'El resumen muestra actividad agregada. Caja, cobros, conciliación, facturación e informes contables requieren el módulo financiero y aún no están implementados.'
                  : 'Los flujos especializados de este perfil se incorporarán por módulo. Tus permisos no conceden acceso general a la agenda ni a los resultados.'}
              </p>
            </div>
          )}
          <p className="text-xs leading-6 text-slate-500">
            Las cifras representan citas y atenciones, no personas únicas. Cada
            sucursal usa su propio huso horario. Los avisos por correo y
            WhatsApp dependen de la configuración de la clínica.
          </p>
        </>
      )}
    </section>
  )
}

export function PlatformWorkspace({ token }: { token: string }) {
  const { notify } = useDialog()
  const [tenants, setTenants] = useState<
    { tenant_id: string; name: string; country: string; active: boolean }[]
  >([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let active = true
    platformApi<{ tenants: typeof tenants }>(token)
      .then((data) => {
        if (active) setTenants(data.tenants)
      })
      .catch((e) => {
        if (active)
          notify({
            title: 'Acceso a administración SaaS',
            message: e.message,
            tone: 'error',
          })
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [token])
  return (
    <section className="card mt-8">
      <p className="eyebrow">Tresuryx SpA · Control del servicio</p>
      <h2 className="mt-2 text-2xl font-semibold">Administración SaaS</h2>
      <p className="mt-3 text-sm leading-7 text-slate-500">
        Directorio de organizaciones. Este acceso no concede permisos sobre
        pacientes, citas ni resultados clínicos.
      </p>
      {loading ? (
        <p className="mt-6" role="status">
          Cargando organizaciones…
        </p>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {tenants.map((t) => (
            <article className="soft-panel" key={t.tenant_id}>
              <h3 className="font-semibold">{t.name}</h3>
              <p className="mt-2 text-sm text-slate-500">
                {t.country} · {t.active ? 'Activa' : 'Inactiva'}
              </p>
            </article>
          ))}
        </div>
      )}
      <p className="mt-6 text-xs leading-6 text-slate-500">
        Gestión comercial de planes, contratación, cobro de suscripciones y
        soporte con acceso excepcional: próximos módulos del plano de
        administración.
      </p>
    </section>
  )
}
