import { useAuthStore } from '@/store/authStore'
import { useDebugLogStore } from '@/store/debugLogStore'

function makeId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`
}

function safeStringify(value: unknown) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export type ApiError = {
  status: number
  message: string
  bodyText: string
}

export async function apiRequest<T>(
  path: string,
  options?: {
    method?: string
    body?: unknown
    headers?: Record<string, string>
  }
): Promise<T> {
  const startedAt = performance.now()
  const id = makeId()

  const token = useAuthStore.getState().token
  const method = options?.method ?? 'GET'
  const headers: Record<string, string> = {
    ...(options?.headers ?? {}),
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const hasBody = options && Object.prototype.hasOwnProperty.call(options, 'body')
  const requestBodyText = hasBody ? safeStringify(options?.body) : ''

  let body: BodyInit | undefined
  if (hasBody) {
    headers['Content-Type'] = headers['Content-Type'] ?? 'application/json'
    body = JSON.stringify(options?.body ?? {})
  }

  let status: number | null = null
  let responseText = ''
  let ok = false
  let errorMessage = ''

  try {
    const resp = await fetch(path, { method, headers, body })
    status = resp.status
    ok = resp.ok
    responseText = await resp.text()

    if (!resp.ok) {
      const bodyPreview = responseText ? `: ${responseText.slice(0, 500)}` : ''
      const err = Object.assign(
        new Error(`${resp.status} ${resp.statusText || 'Request failed'}`.trim() + bodyPreview),
        {
          status: resp.status,
          bodyText: responseText,
        }
      )
      throw err
    }

    if (!responseText) return undefined as T
    return JSON.parse(responseText) as T
  } catch (e) {
    if (typeof e === 'object' && e && 'status' in e && e instanceof Error) {
      const err = e as Error & { status?: number; bodyText?: string }
      const statusText = typeof err.status === 'number' ? String(err.status) : ''
      const bodyText = typeof err.bodyText === 'string' ? err.bodyText : ''
      const bodyPreview = bodyText ? `: ${bodyText.slice(0, 500)}` : ''
      errorMessage = `${statusText} ${err.message}`.trim() + bodyPreview
    } else {
      errorMessage = e instanceof Error ? e.message : String(e)
    }
    throw e
  } finally {
    const endedAt = performance.now()
    useDebugLogStore.getState().add({
      id,
      createdAt: Date.now(),
      method,
      path,
      status,
      durationMs: Math.max(0, Math.round(endedAt - startedAt)),
      ok,
      requestBody: requestBodyText,
      responseBody: responseText,
      errorMessage,
    })
  }
}
