import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { Team, TeamAccess } from './Team'
import { DialogProvider } from './Dialog'
const requests: { path: string; options: RequestInit }[] = []
let unavailable = false
beforeEach(() => {
  requests.length = 0
  unavailable = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, options: RequestInit = {}) => {
      requests.push({ path, options })
      if (unavailable)
        return new Response(
          JSON.stringify({ detail: 'Acceso retirado; contacta a la clínica' }),
          { status: 403 },
        )
      if (path.endsWith('/options'))
        return new Response(
          JSON.stringify({
            branches: [{ id: 'branch', name: 'Centro ficticio' }],
            resources: [],
            permissions: {
              reception: 'Solo sucursal asignada, sin cierre clínico',
              admin: 'Administra la clínica',
            },
          }),
        )
      if (options.method)
        return new Response(JSON.stringify({ state: 'queued' }), {
          status: 201,
        })
      return new Response(
        JSON.stringify({
          items: [
            {
              id: 'fake',
              kind: 'member',
              email: 'equipo@example.com',
              role: 'reception',
              active: true,
              state: 'active',
              version: 2,
              branches: ['branch'],
              resources: [],
              delivery_state: null,
              expires_at: null,
            },
          ],
          has_more: false,
        }),
      )
    }),
  )
})
function view() {
  render(
    <DialogProvider>
      <Team token="synthetic-test-token" />
    </DialogProvider>,
  )
}
it('shows minimum staff data and requires confirmation; cancelling never mutates', async () => {
  const user = userEvent.setup()
  view()
  expect(await screen.findByText('equipo@example.com')).toBeInTheDocument()
  expect(screen.getByText('Alcance: Centro ficticio')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Desactivar' }))
  const dialog = await screen.findByRole('alertdialog', {
    name: 'Desactivar acceso',
  })
  expect(screen.getByRole('button', { name: 'Volver' })).toHaveFocus()
  fireEvent(dialog, new Event('cancel', { cancelable: true }))
  expect(requests.filter((r) => r.options.method)).toHaveLength(0)
  await user.click(screen.getByRole('button', { name: 'Desactivar' }))
  await user.click(
    screen.getAllByRole('button', { name: 'Desactivar' }).at(-1)!,
  )
  await waitFor(() =>
    expect(requests.filter((r) => r.options.method === 'PATCH')).toHaveLength(
      1,
    ),
  )
  expect(
    JSON.parse(
      requests.find((r) => r.options.method === 'PATCH')!.options
        .body as string,
    ).expected_version,
  ).toBe(2)
})
it('previews invitation scope and distinguishes queued email from delivery', async () => {
  const user = userEvent.setup()
  view()
  await screen.findByText('equipo@example.com')
  await user.click(screen.getByRole('button', { name: 'Invitar personal' }))
  await user.type(
    screen.getByLabelText('Correo del destinatario'),
    'ficticio@example.com',
  )
  await user.click(screen.getByLabelText('Centro ficticio'))
  await user.click(
    screen.getByRole('button', { name: 'Revisar permisos y confirmar' }),
  )
  expect(await screen.findByRole('alertdialog')).toHaveTextContent(
    'Encolar no confirma el envío',
  )
  expect(requests.filter((r) => r.options.method === 'POST')).toHaveLength(0)
  await user.click(screen.getByRole('button', { name: 'Crear invitación' }))
  await screen.findByRole('dialog', { name: 'Equipo actualizado' })
  expect(requests.filter((r) => r.options.method === 'POST')).toHaveLength(1)
})
it('clears old directory on session change and shows denial in modal', async () => {
  const { rerender } = render(
    <DialogProvider>
      <Team token="first-test-token" />
    </DialogProvider>,
  )
  await screen.findByText('equipo@example.com')
  unavailable = true
  rerender(
    <DialogProvider>
      <Team token="second-test-token" />
    </DialogProvider>,
  )
  expect(await screen.findByRole('alertdialog')).toHaveTextContent(
    'Acceso retirado',
  )
  expect(screen.queryByText('equipo@example.com')).not.toBeInTheDocument()
})
it('keeps staff sign-in disabled when Auth is absent', () => {
  render(
    <DialogProvider>
      <TeamAccess invitation="" onAccepted={() => {}} />
    </DialogProvider>,
  )
  expect(
    screen.getByRole('button', { name: 'Solicitar código de acceso' }),
  ).toBeDisabled()
  expect(screen.getByText(/Auth aún no está configurado/)).toBeInTheDocument()
})

it('edits a pending invitation with its version and no membership activation field', async () => {
  const user = userEvent.setup()
  const writes: RequestInit[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, options: RequestInit = {}) => {
      if (options.method) {
        writes.push(options)
        expect(path).toContain('/team/invitations/pending-demo')
        return new Response(JSON.stringify({ state: 'pending' }))
      }
      if (path.endsWith('/options'))
        return new Response(
          JSON.stringify({
            branches: [{ id: 'branch', name: 'Centro ficticio' }],
            resources: [],
            permissions: {
              reception: 'Recepción por sede',
              finance: 'Agregados sin nombres',
            },
          }),
        )
      return new Response(
        JSON.stringify({
          items: [
            {
              id: 'pending-demo',
              kind: 'invitation',
              email: 'ficticio@example.com',
              role: 'reception',
              active: false,
              state: 'pending',
              version: 3,
              branches: ['branch'],
              resources: [],
              delivery_state: 'queued',
              expires_at: null,
            },
          ],
          has_more: false,
        }),
      )
    }),
  )
  view()
  await screen.findByText('ficticio@example.com')
  await user.click(screen.getByRole('button', { name: 'Editar permisos' }))
  await user.selectOptions(screen.getByLabelText('Perfil principal'), 'finance')
  await user.click(screen.getByLabelText('Centro ficticio'))
  await user.click(
    screen.getByRole('button', { name: 'Revisar permisos y confirmar' }),
  )
  await user.click(screen.getByRole('button', { name: 'Guardar permisos' }))
  await screen.findByRole('dialog', { name: 'Equipo actualizado' })
  expect(writes).toHaveLength(1)
  expect(JSON.parse(writes[0].body as string)).toEqual({
    role: 'finance',
    branches: ['branch'],
    resources: [],
    expected_version: 3,
  })
})
