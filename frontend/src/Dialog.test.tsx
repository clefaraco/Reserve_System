import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { DialogProvider, useDialog } from './Dialog'

function Harness() {
  const { confirm, notify } = useDialog()
  const [result, setResult] = useState('sin cambios')
  return (
    <>
      <button
        onClick={async () => {
          if (
            await confirm({
              title: 'Anular cita',
              message: 'Liberaremos el horario',
              tone: 'danger',
              confirmLabel: 'Sí, anular',
            })
          )
            setResult('anulada')
        }}
      >
        Solicitar anulación
      </button>
      <button
        onClick={() => {
          notify({ title: 'Primero', message: 'Primer mensaje' })
          notify({ title: 'Segundo', message: 'Segundo mensaje' })
        }}
      >
        Dos mensajes
      </button>
      <p>{result}</p>
    </>
  )
}

describe('Accessible application dialogs', () => {
  it('cancels a destructive action on Escape and requires explicit confirmation', async () => {
    const user = userEvent.setup()
    render(
      <DialogProvider>
        <Harness />
      </DialogProvider>,
    )
    await user.click(
      screen.getByRole('button', { name: 'Solicitar anulación' }),
    )
    const dialog = await screen.findByRole('alertdialog', {
      name: 'Anular cita',
    })
    fireEvent(dialog, new Event('cancel', { cancelable: true }))
    expect(screen.getByText('sin cambios')).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: 'Solicitar anulación' }),
    )
    await user.click(screen.getByRole('button', { name: 'Sí, anular' }))
    expect(await screen.findByText('anulada')).toBeInTheDocument()
  })
  it('queues messages so one notice does not overwrite another', async () => {
    const user = userEvent.setup()
    render(
      <DialogProvider>
        <Harness />
      </DialogProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'Dos mensajes' }))
    expect(await screen.findByRole('dialog')).toHaveAccessibleName('Primero')
    await user.click(screen.getByRole('button', { name: 'Entendido' }))
    expect(await screen.findByRole('dialog')).toHaveAccessibleName('Segundo')
  })
})
