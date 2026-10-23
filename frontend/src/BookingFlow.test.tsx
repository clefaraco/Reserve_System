import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { BookingFlow } from './BookingFlow'

vi.mock('./api', async importOriginal => ({
  ...await importOriginal<typeof import('./api')>(),
  auth: { auth: { onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }) } },
}))

const catalog = {
  tenant: 'Test Clinic', account_available: true, cancel_cutoff_minutes: 120, reschedule_cutoff_minutes: 120,
  services: [{ service_id: 'service', resource_id: 'resource', service_name: 'Consulta',
    public_name: 'Dra. Test', branch: 'Centro', specialty: 'Medicina', timezone: 'America/Santiago',
    duration_minutes: 30, buffer_minutes: 15 }],
  documents: [{ id: 'terms', kind: 'terms', version: '1', body: 'Términos de prueba' },
    { id: 'sensitive', kind: 'sensitive_data', version: '1', body: 'Privacidad de prueba' }],
}
const requests: { path: string; options: RequestInit }[] = []
let failBooking = false
beforeEach(() => {
  requests.length = 0; failBooking = false
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit = {}) => {
    requests.push({ path, options })
    if (path.endsWith('/catalog')) return new Response(JSON.stringify(catalog))
    if (path.includes('/availability')) return new Response(JSON.stringify({ slots: ['2030-05-10T14:00:00Z'] }))
    if (failBooking) throw new TypeError('Network failure')
    return new Response(JSON.stringify({ starts_at: '2030-05-10T14:00:00Z', account: 'queued' }), { status: 201 })
  }))
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
  await user.type(screen.getByLabelText('Correo electrónico'), 'test@example.com')
  return user
}

describe('Guest to Registered', () => {
  it('requires explicit consent and reuses the entered contact details for account enrollment', async () => {
    const user = await checkout()
    const create = screen.getByRole('checkbox', { name: /Crear cuenta/ })
    expect(create).not.toBeChecked()
    expect(screen.queryByLabelText(/Teléfono/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reservar mi hora' })).toBeDisabled()
    await user.click(create)
    await user.click(screen.getByRole('checkbox', { name: /Acepto los términos/ }))
    await user.click(screen.getByRole('checkbox', { name: /Consiento el tratamiento/ }))
    await user.click(screen.getByRole('button', { name: 'Reservar mi hora' }))
    expect(await screen.findByText('Tu hora está reservada')).toBeInTheDocument()
    const request = requests.find(r => r.path.endsWith('/bookings'))!
    const body = JSON.parse(request.options.body as string)
    expect(body).toMatchObject({ create_account: true, patient: { name: 'Paciente Test', email: 'test@example.com' }, consent_document_ids: ['terms', 'sensitive'] })
    expect(body.patient).not.toHaveProperty('phone')
    expect(new Headers(request.options.headers).get('Idempotency-Key')).toBeTruthy()
    expect(screen.getByText(/No necesitas volver a ingresar tus datos/)).toBeInTheDocument()
  })

  it('preserves the idempotency key when retrying a network failure', async () => {
    const user = await checkout()
    await user.click(screen.getByRole('checkbox', { name: /Acepto los términos/ }))
    await user.click(screen.getByRole('checkbox', { name: /Consiento el tratamiento/ }))
    failBooking = true
    await user.click(screen.getByRole('button', { name: 'Reservar mi hora' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Network failure')
    failBooking = false
    await user.click(screen.getByRole('button', { name: 'Reservar mi hora' }))
    await waitFor(() => expect(requests.filter(r => r.path.endsWith('/bookings'))).toHaveLength(2))
    const [first, second] = requests.filter(r => r.path.endsWith('/bookings'))
    expect(new Headers(first.options.headers).get('Idempotency-Key')).toBe(new Headers(second.options.headers).get('Idempotency-Key'))
  })
})
