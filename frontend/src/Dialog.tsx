import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from 'react'

type Tone = 'info' | 'success' | 'error' | 'danger'
type Message = {
  title: string
  message: string
  tone?: Tone
  confirmLabel?: string
}
type Request = Message & {
  id: number
  confirmation: boolean
  resolve?: (answer: boolean) => void
}
type DialogApi = {
  notify: (message: Message) => void
  confirm: (message: Message) => Promise<boolean>
}
const Context = createContext<DialogApi | null>(null)

export function DialogProvider({ children }: { children: ReactNode }) {
  const [queue, setQueue] = useState<Request[]>([])
  const sequence = useRef(0)
  const pending = useRef(new Set<(answer: boolean) => void>())
  const element = useRef<HTMLDialogElement>(null)
  const initialFocus = useRef<HTMLButtonElement>(null)
  const id = useId()
  const active = queue[0]
  const notify = useCallback((message: Message) => {
    setQueue((items) => [
      ...items,
      { ...message, id: ++sequence.current, confirmation: false },
    ])
  }, [])
  const confirm = useCallback(
    (message: Message) =>
      new Promise<boolean>((resolve) => {
        pending.current.add(resolve)
        setQueue((items) => [
          ...items,
          { ...message, id: ++sequence.current, confirmation: true, resolve },
        ])
      }),
    [],
  )
  function finish(answer: boolean) {
    if (!active) return
    active.resolve?.(answer)
    if (active.resolve) pending.current.delete(active.resolve)
    setQueue((items) => items.slice(1))
  }
  useEffect(() => {
    const dialog = element.current
    const opener =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    if (active && dialog && !dialog.open) {
      dialog.showModal()
      initialFocus.current?.focus()
    }
    return () => {
      if (dialog?.open) dialog.close()
      if (opener?.isConnected) opener.focus()
    }
  }, [active?.id])
  useEffect(
    () => () => {
      for (const resolve of pending.current) resolve(false)
      pending.current.clear()
    },
    [],
  )
  return (
    <Context.Provider value={{ notify, confirm }}>
      {children}
      {active && (
        <dialog
          ref={element}
          className="message-dialog"
          role={
            active.confirmation || active.tone === 'error'
              ? 'alertdialog'
              : 'dialog'
          }
          aria-modal="true"
          aria-labelledby={`${id}-title`}
          aria-describedby={`${id}-body`}
          onCancel={(event) => {
            event.preventDefault()
            finish(false)
          }}
          onKeyDown={(event) => {
            if (event.key !== 'Tab') return
            const buttons = Array.from(
              event.currentTarget.querySelectorAll<HTMLButtonElement>(
                'button:not(:disabled)',
              ),
            )
            const first = buttons[0]
            const last = buttons[buttons.length - 1]
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault()
              last?.focus()
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault()
              first?.focus()
            }
          }}
        >
          <div className="p-7 sm:p-8">
            <div className="flex items-start justify-between gap-4">
              <span
                aria-hidden="true"
                className={`dialog-icon dialog-${active.tone ?? 'info'}`}
              >
                {active.tone === 'success'
                  ? '✓'
                  : active.tone === 'error' || active.tone === 'danger'
                    ? '!'
                    : 'i'}
              </span>
              <button
                type="button"
                aria-label="Cerrar mensaje"
                className="icon-button"
                onClick={() => finish(false)}
              >
                ×
              </button>
            </div>
            <h2
              id={`${id}-title`}
              className="mt-5 text-xl font-semibold tracking-tight text-slate-900"
            >
              {active.title}
            </h2>
            <p
              id={`${id}-body`}
              className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-600"
            >
              {active.message}
            </p>
            <div className="mt-7 flex flex-wrap justify-end gap-3">
              {active.confirmation && (
                <button
                  type="button"
                  autoFocus
                  ref={initialFocus}
                  className="btn-secondary"
                  onClick={() => finish(false)}
                >
                  Volver
                </button>
              )}
              <button
                type="button"
                autoFocus={!active.confirmation}
                ref={active.confirmation ? undefined : initialFocus}
                className={
                  active.tone === 'danger' ? 'btn-danger' : 'btn-primary'
                }
                onClick={() => finish(true)}
              >
                {active.confirmLabel ?? 'Entendido'}
              </button>
            </div>
          </div>
        </dialog>
      )}
    </Context.Provider>
  )
}

export function useDialog() {
  const context = useContext(Context)
  if (!context) throw new Error('DialogProvider is required')
  return context
}

// checkValidity reads validity without opening the browser's validation bubbles.
export function validateForm(
  form: HTMLFormElement,
  notify: DialogApi['notify'],
) {
  const invalid = Array.from(
    form.querySelectorAll<HTMLInputElement | HTMLSelectElement>('input,select'),
  ).find((input) => !input.validity.valid)
  if (!invalid) return true
  const label =
    invalid.labels?.[0]?.textContent?.trim() ?? 'los datos del formulario'
  notify({
    title: 'Revisa tus datos',
    message: `Completa correctamente el campo: ${label}.`,
    tone: 'error',
  })
  invalid.focus()
  return false
}
