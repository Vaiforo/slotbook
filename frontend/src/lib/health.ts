export type Health = { status: 'ok'; service: string }

export async function getHealth(signal: AbortSignal): Promise<Health> {
  const response = await fetch('/health/live', {
    signal,
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error(`API вернул HTTP ${response.status}.`)

  const data: unknown = await response.json()
  if (
    typeof data !== 'object' || data === null ||
    !('status' in data) || data.status !== 'ok' ||
    !('service' in data) || typeof data.service !== 'string'
  ) {
    throw new Error('API вернул неожиданный ответ.')
  }
  return { status: data.status, service: data.service }
}
