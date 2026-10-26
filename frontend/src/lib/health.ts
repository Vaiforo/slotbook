import { request } from './api'
import type { components } from '../generated/api-types'

export type Health = components['schemas']['LiveResponse']

export async function getHealth(signal: AbortSignal): Promise<Health> {
  const data = await request<unknown>('/health/live', { basePath: '', signal })
  if (
    typeof data !== 'object' || data === null ||
    !('status' in data) || data.status !== 'ok' ||
    !('service' in data) || typeof data.service !== 'string'
  ) {
    throw new Error('API вернул неожиданный ответ.')
  }
  return { status: data.status, service: data.service }
}
