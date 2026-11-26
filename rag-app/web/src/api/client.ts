import type { ErrorResponse } from './types'

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  if (!('error' in value)) {
    return false
  }
  const error = (value as ErrorResponse).error
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof error.code === 'string' &&
    typeof error.message === 'string'
  )
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json()
    if (isErrorResponse(body)) {
      return new ApiError(response.status, body.error.code, body.error.message)
    }
  } catch {
    // fall through to generic http_error
  }
  return new ApiError(
    response.status,
    'http_error',
    response.statusText || 'HTTP error',
  )
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      signal,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Network error')
  }

  if (!response.ok) {
    throw await toApiError(response)
  }

  return (await response.json()) as T
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, { method: 'GET' }, signal)
}

export function apiPost<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  return requestJson<T>(
    path,
    { method: 'POST', body: JSON.stringify(body) },
    signal,
  )
}
