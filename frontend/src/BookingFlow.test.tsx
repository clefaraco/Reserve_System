import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BookingFlow } from './BookingFlow'

const session = vi.hoisted(() => ({ token: undefined as string | undefined }))

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  auth: {
    auth: {
      onAuthStateChange: (
        callback: (
          event: string,
          value: { access_token: string } | null,
        ) => void,
      ) => {
        if (session.token)
          callback('SIGNED_IN', { access_token: session.token })
        return { data: { subscription: { unsubscribe() {} } } }
      },
    },
  },
}))

const catalog = {
  tenant: 'Test Clinic',
  account_available: true,
  cancel_cutoff_minutes: 120,
  reschedule_cutoff_minutes: 120,
  services: [
    {
      service_id: 'service',
      resource_id: 'resource',
      service_name: 'Consulta',
      public_name: 'Dra. Test',
      branch: 'Centro',
      specialty: 'Medicina',
      timezone: 'America/Santiago',
      duration_minutes: 30,
      buffer_minutes: 15,
    },
  ],
  documents: [
    { id: 'terms', kind: 'terms', version: '1', body: 'Términos de prueba' },
    {
      id: 'sensitive',
      kind: 'sensitive_data',
      version: '1',
      body: 'Privacidad de prueba',
    },
  ],
}
const requests: { path: string; options: RequestInit }[] = []
let failBooking = false
let patientAppointments: {
  id: string
  patient_id: string
  starts_at: string
  ends_at: string
  status: string
  version: number
  service_name: string
  public_name: string
  timezone: string
}[] = []
beforeEach(() => {
  requests.length = 0
  failBooking = false
  session.token = undefined
  patientAppointments = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, options: RequestInit = {}) => {
      requests.push({ path, options })
      if (path.endsWith('/catalog'))
        return new Response(JSON.stringify(catalog))
      if (path.endsWith('/session'))
        return new Response(
          JSON.stringify({
            authenticated: true,
            role: null,
            capabilities: [],
            platform_role: null,
          }),
        )
      if (path.endsWith('/account/claim'))
        return new Response(JSON.stringify({ linked_profiles: 0 }))
      if (path.endsWith('/appointments'))
        return new Response(JSON.stringify(patientAppointments))
      if (options.method === 'PATCH') {
        const id = path.split('/').at(-1)
        patientAppointments = patientAppointments.map((a) =>
          a.id === id
            ? { ...a, status: 'cancelled', version: a.version + 1 }
            : a,
        )
        return new Response(JSON.stringify({ status: 'cancelled', version: 2 }))
      }
      if (path.includes('/availability'))
        return new Response(JSON.stringify({ slots: ['2030-05-10T14:00:00Z'] }))
      if (failBooking) throw new TypeError('Network failure')
      return new Response(
        JSON.stringify({
          starts_at: '2030-05-10T14:00:00Z',
          account: 'queued',
        }),
        { status: 201 },
      )
    }),
  )
})

async function checkout() {
  const user = userEvent.setup()
  render(<BookingFlow />)
  await user.selectOptions(await screen.findByLabelText('Servicio'), 'service')
  await user.selectOptions(screen.getByLabelText('Profesional'), 'resource')
  await user.click(screen.getByRole('button', { name: /Ver horarios/ }))
  await user.click(await screen.findByRole('button', { name: /10:00/ }))
  await user.click(screen.getByRole('button', { name: 'Continuar' }))
  await user.type(screen.getByLabelText('Nombre y apellido'), 'Paciente Test')
  await user.type(
    screen.getByLabelText('Correo electrónico'),
    'test@example.com',
  )
  return user
}

describe('Guest to Registered', () => {
  it('requires explicit consent and reuses the entered contact details for account enrollment', async () => {
    const user = await checkout()
    const create = screen.getByRole('checkbox', { name: /Crear cuenta/ })
    expect(create).not.toBeChecked()
    expect(screen.queryByLabelText(/Teléfono/)).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Reservar mi hora' }),
    ).toBeDisabled()
    await user.click(create)
    await user.click(
      screen.getByRole('checkbox', { name: /Acepto los términos/ }),
    )
    await user.click(
      screen.getByRole('checkbox', { name: /Consiento el tratamiento/ }),
    )
    await user.click(screen.getByRole('button', { name: 'Reservar mi hora' }))
    expect(
      await screen.findByText('Tu hora está reservada'),
    ).toBeInTheDocument()
    const request = requests.find((r) => r.path.endsWith('/bookings'))!
    const body = JSON.parse(request.options.body as string)
    expect(body).toMatchObject({
      create_account: true,
      patient: { name: 'Paciente Test', email: 'test@example.com' },
      consent_document_ids: ['terms', 'sensitive'],
    })
    expect(body.patient).not.toHaveProperty('phone')
    expect(
      new Headers(request.options.headers).get('Idempotency-Key'),
    ).toBeTruthy()
    expect(
      screen.getByText(/No necesitas volver a ingresar tus datos/),
    ).toBeInTheDocument()
  })

  it('preserves the idempotency key when retrying a network failure', async () => {
    const user = await checkout()
    await user.click(
      screen.getByRole('checkbox', { name: /Acepto los términos/ }),
    )
    await user.click(
      screen.getByRole('checkbox', { name: /Consiento el tratamiento/ }),
    )
    failBooking = true
    await user.click(screen.getByRole('button', { name: 'Reservar mi hora' }))
    expect(await screen.findByRole('alertdialog')).toHaveTextContent(
      'No pudimos conectar con la clínica',
    )
    await user.click(screen.getByRole('button', { name: 'Entendido' }))
    failBooking = false
    await user.click(screen.getByRole('button', { name: 'Reservar mi hora' }))
    await waitFor(() =>
      expect(requests.filter((r) => r.path.endsWith('/bookings'))).toHaveLength(
        2,
      ),
    )
    const [first, second] = requests.filter((r) => r.path.endsWith('/bookings'))
    expect(new Headers(first.options.headers).get('Idempotency-Key')).toBe(
      new Headers(second.options.headers).get('Idempotency-Key'),
    )
  })

  it('separates upcoming appointments from history and asks before cancelling', async () => {
    session.token = 'test-session'
    const common = {
      patient_id: 'patient',
      ends_at: '2030-05-10T14:30:00Z',
      version: 1,
      public_name: 'Dra. Test',
      timezone: 'America/Santiago',
    }
    patientAppointments = [
      {
        ...common,
        id: 'future',
        starts_at: '2030-05-10T14:00:00Z',
        status: 'confirmed',
        service_name: 'Próxima consulta',
      },
      {
        ...common,
        id: 'past',
        starts_at: '2020-05-10T14:00:00Z',
        status: 'completed',
        service_name: 'Consulta pasada',
      },
    ]
    const user = userEvent.setup()
    render(<BookingFlow />)
    await user.click(screen.getByRole('button', { name: 'Mi portal' }))
    expect(await screen.findByText('Próxima consulta')).toBeInTheDocument()
    expect(screen.queryByText('Consulta pasada')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Historial' }))
    expect(await screen.findByText('Consulta pasada')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Próximas citas' }))
    await user.click(screen.getByRole('button', { name: 'Anular hora' }))
    expect(await screen.findByRole('alertdialog')).toHaveAccessibleName(
      'Anular esta cita',
    )
    await user.click(screen.getByRole('button', { name: 'Volver' }))
    expect(requests.filter((r) => r.options.method === 'PATCH')).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Anular hora' }))
    await user.click(screen.getByRole('button', { name: 'Sí, anular cita' }))
    await waitFor(() =>
      expect(requests.filter((r) => r.options.method === 'PATCH')).toHaveLength(
        1,
      ),
    )
  })

  it('shows form errors inside a modal without submitting invalid contact details', async () => {
    const user = await checkout()
    await user.clear(screen.getByLabelText('Nombre y apellido'))
    await user.click(
      screen.getByRole('checkbox', { name: /Acepto los términos/ }),
    )
    await user.click(
      screen.getByRole('checkbox', { name: /Consiento el tratamiento/ }),
    )
    await user.click(screen.getByRole('button', { name: 'Reservar mi hora' }))
    expect(await screen.findByRole('alertdialog')).toHaveTextContent(
      'Revisa tus datos',
    )
    expect(requests.filter((r) => r.path.endsWith('/bookings'))).toHaveLength(0)
  })
})
