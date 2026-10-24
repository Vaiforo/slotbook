import { useEffect, useState } from 'react'
import { getHealth } from '../lib/health'
import type { Health } from '../lib/health'

type Status =
  | { kind: 'loading' }
  | { kind: 'success'; health: Health }
  | { kind: 'error'; message: string }

export function App() {
  const [attempt, setAttempt] = useState(0)
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 5000)
    let active = true

    getHealth(controller.signal)
      .then((health) => {
        if (active) setStatus({ kind: 'success', health })
      })
      .catch((error: unknown) => {
        if (active) {
          setStatus({
            kind: 'error',
            message: controller.signal.aborted
              ? 'Сервер не ответил за 5 секунд.'
              : error instanceof Error ? error.message : 'Не удалось связаться с сервером.',
          })
        }
      })
      .finally(() => window.clearTimeout(timeout))

    return () => {
      active = false
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [attempt])

  function refresh() {
    setStatus({ kind: 'loading' })
    setAttempt((value) => value + 1)
  }

  return (
    <main className="shell">
      <header className="brand"><span className="brand-mark" aria-hidden="true">S</span>SlotBook</header>
      <section className="intro" aria-labelledby="page-title">
        <p className="eyebrow">Запись на консультации</p>
        <h1 id="page-title">Всё начинается<br />со связи.</h1>
        <p className="lead">SlotBook готовится помогать вам находить время для встреч.
          Сейчас доступна проверка соединения с сервисом.</p>
      </section>
      <section className="status-card" aria-labelledby="status-title">
        <div className="card-heading">
          <h2 id="status-title">Состояние сервиса</h2>
          <span className="badge">Этап 01</span>
        </div>
        <div role="status" aria-live="polite" aria-atomic="true">
          <p className={`connection ${status.kind}`}>
            <span className="dot" aria-hidden="true" />
            {status.kind === 'loading' ? 'Проверяем соединение…'
              : status.kind === 'success' ? 'API доступен' : 'API недоступен'}
          </p>
          <p className="detail">
            {status.kind === 'success'
              ? `Сервис ${status.health.service} ответил: ${status.health.status}.`
              : status.kind === 'error'
                ? `${status.message} Повторите проверку после восстановления соединения.`
                : 'Ждём ответ сервера.'}
          </p>
        </div>
        <button type="button" onClick={refresh} disabled={status.kind === 'loading'}>
          {status.kind === 'loading' ? 'Проверяем…' : 'Проверить ещё раз'}
        </button>
      </section>
      <footer>Расписание и бронирование появятся на следующих этапах.</footer>
    </main>
  )
}
