import { ElMessage } from 'element-plus'

export interface ApiError {
  message: string
  code?: string | number
  details?: string
}

export function extractErrorMessage(error: unknown): string {
  if (error === null || error === undefined) {
    return 'An unknown error occurred'
  }

  if (typeof error === 'string') {
    return error
  }

  if (error instanceof Error) {
    return error.message
  }

  if (typeof error === 'object') {
    const err = error as Record<string, unknown>

    if (err.response && typeof err.response === 'object') {
      const response = err.response as Record<string, unknown>

      if (response.data && typeof response.data === 'object') {
        const data = response.data as Record<string, unknown>

        if (typeof data.detail === 'string') {
          return data.detail
        }

        if (typeof data.message === 'string') {
          return data.message
        }

        if (Array.isArray(data.detail)) {
          return data.detail.join(', ')
        }
      }

      if (typeof response.statusText === 'string') {
        return `Request failed: ${response.statusText}`
      }
    }

    if (typeof err.message === 'string') {
      return err.message
    }
  }

  return 'An unknown error occurred'
}

export function showError(message: string, options?: { duration?: number }): void {
  ElMessage.error({
    message,
    duration: options?.duration ?? 5000,
    showClose: true
  })
}

export function showSuccess(message: string, options?: { duration?: number }): void {
  ElMessage.success({
    message,
    duration: options?.duration ?? 3000,
    showClose: true
  })
}

export function showWarning(message: string, options?: { duration?: number }): void {
  console.warn('[Warning]', message)
  ElMessage.warning({
    message,
    duration: options?.duration ?? 4000,
    showClose: true
  })
}

export function handleError(error: unknown, defaultMessage?: string): void {
  const message = defaultMessage || extractErrorMessage(error)
  console.error('[Error]', error)
  showError(message)
}

export function handleApiError(error: unknown, fallbackMessage = 'Operation failed'): void {
  const message = extractErrorMessage(error)
  console.error('[API Error]', error)
  showError(message || fallbackMessage)
}
