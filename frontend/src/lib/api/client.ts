/**
 * Typed fetch wrapper with in-memory access token and single-flight refresh.
 *
 * Access tokens live in memory only (spec 05). The refresh token is an
 * HttpOnly cookie, so refresh requests must send `credentials: 'include'`.
 */

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
export const API_PREFIX = '/api/v1'

export interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
    request_id?: string
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  readonly requestId: string

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
    requestId = '',
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
  }
}

let accessToken: string | null = null
const listeners = new Set<(token: string | null) => void>()

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
  for (const listener of listeners) listener(token)
}

export function subscribeToAccessToken(listener: (token: string | null) => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

let refreshPromise: Promise<string | null> | null = null

/** Refresh once, no matter how many callers ask at the same time. */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}${API_PREFIX}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
      },
    })
      .then(async (response) => {
        if (!response.ok) {
          setAccessToken(null)
          return null
        }
        const body = (await response.json()) as { access_token?: string }
        const token = body.access_token ?? null
        setAccessToken(token)
        return token
      })
      .catch(() => {
        setAccessToken(null)
        return null
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

export interface ApiRequestOptions extends Omit<RequestInit, 'headers'> {
  headers?: Record<string, string>
  skipAuth?: boolean
  skipRefresh?: boolean
}

function withJsonBody(options: ApiRequestOptions): RequestInit {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...options.headers,
  }
  const isFormData = options.body instanceof FormData
  if (options.body && !isFormData && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  return { ...options, headers }
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: ApiErrorBody | null = null
  try {
    payload = (await response.json()) as ApiErrorBody
  } catch {
    payload = null
  }
  const error = payload?.error
  return new ApiError(
    response.status,
    error?.code ?? 'HTTP_ERROR',
    error?.message ?? response.statusText ?? 'Request failed',
    error?.details ?? {},
    error?.request_id ?? response.headers.get('X-Request-ID') ?? '',
  )
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { skipAuth = false, skipRefresh = false, ...init } = options
  const requestInit = withJsonBody(init)
  const token = getAccessToken()
  if (token && !skipAuth) {
    requestInit.headers = {
      ...(requestInit.headers as Record<string, string>),
      Authorization: `Bearer ${token}`,
    }
  }

  let response = await fetch(`${API_BASE}${path}`, requestInit)

  if (response.status === 401 && !skipAuth && !skipRefresh) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      requestInit.headers = {
        ...(requestInit.headers as Record<string, string>),
        Authorization: `Bearer ${refreshed}`,
      }
      response = await fetch(`${API_BASE}${path}`, requestInit)
    }
  }

  if (!response.ok) {
    throw await parseError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function jsonBody(value: unknown): string {
  return JSON.stringify(value)
}

/** Liveness/readiness are outside the versioned API prefix. */
export const healthApi = {
  check: () => apiRequest<{ status: string }>('/health', { skipAuth: true, skipRefresh: true }),
  ready: () =>
    apiRequest<{ status: string; database: string }>('/health/ready', {
      skipAuth: true,
      skipRefresh: true,
    }),
}
