import type { components, operations } from '../generated/api-types'

type ErrorBody = components['schemas']['ErrorResponse']
export type PublicSpecialist = components['schemas']['PublicSpecialist']
export type SlotPage = components['schemas']['SlotPage']
export type SlotFilters = operations['get_available_slots']['parameters']['query']

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function isErrorBody(body: unknown): body is ErrorBody {
  if (typeof body !== 'object' || body === null || !('error' in body)) return false
  const detail = body.error
  return typeof detail === 'object' && detail !== null &&
    'code' in detail && typeof detail.code === 'string' &&
    'message' in detail && typeof detail.message === 'string' &&
    'request_id' in detail && typeof detail.request_id === 'string'
}

type RequestOptions = Omit<RequestInit, 'credentials'> & {
  basePath?: '/api/v1' | ''
  csrfToken?: string
}

/** One request only: no automatic retry, especially for future mutations. */
export async function request<T>(path: `/${string}`, options: RequestOptions = {}): Promise<T> {
  const { basePath = '/api/v1', csrfToken, ...init } = options
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (csrfToken && !['GET', 'HEAD', 'OPTIONS'].includes((init.method ?? 'GET').toUpperCase())) {
    headers.set('X-CSRF-Token', csrfToken)
  }
  const response = await fetch(`${basePath}${path}`, {
    ...init, headers, credentials: 'same-origin', cache: 'no-store',
  })
  const requestId = response.headers.get('X-Request-ID') ?? undefined
  if (response.status === 204) return undefined as T
  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiError(response.status, 'invalid_response', 'Сервер вернул некорректный ответ.', requestId)
  }
  if (!response.ok) {
    if (isErrorBody(body)) {
      throw new ApiError(response.status, body.error.code, body.error.message, body.error.request_id)
    }
    throw new ApiError(response.status, 'http_error', `Ошибка HTTP ${response.status}.`, requestId)
  }
  return body as T
}

export function getSpecialist(slug: string, signal?: AbortSignal): Promise<PublicSpecialist> {
  return request(`/specialists/${encodeURIComponent(slug)}`, { signal })
}

export function getAvailableSlots(slug: string, filters: SlotFilters, signal?: AbortSignal): Promise<SlotPage> {
  const query = new URLSearchParams({
    from: filters.from, to: filters.to,
    limit: String(filters.limit ?? 100), offset: String(filters.offset ?? 0),
  })
  return request(`/specialists/${encodeURIComponent(slug)}/slots?${query}`, { signal })
}
