import { reactive, computed } from 'vue'
import type { ComputedRef } from 'vue'

interface LoadingState {
  [key: string]: boolean
}

interface UseLoadingReturn {
  loadingStates: ComputedRef<LoadingState>
  isLoading: (key: string) => boolean
  setLoading: (key: string, value: boolean) => void
  withLoading: <T>(key: string, asyncFn: () => Promise<T>) => Promise<T>
  resetAll: () => void
  anyLoading: ComputedRef<boolean>
}

/**
 * Composable for managing independent loading states
 * @param keys - Array of loading state keys
 * @returns Loading state and methods
 *
 * @example
 * const { loadingStates, isLoading, setLoading, withLoading } = useLoading([
 *   'overview',
 *   'performanceChart',
 *   'positions'
 * ])
 */
export function useLoading(keys: string[] = []): UseLoadingReturn {
  const states = reactive<LoadingState>(
    keys.reduce((acc, key) => {
      acc[key] = false
      return acc
    }, {} as LoadingState)
  )

  const loadingStates = computed(() => ({ ...states }))

  const isLoading = (key: string): boolean => {
    return states[key] || false
  }

  const setLoading = (key: string, value: boolean): void => {
    if (key in states) {
      states[key] = value
    } else {
      console.warn(`Loading state key "${key}" not found. Available keys: ${Object.keys(states).join(', ')}`)
    }
  }

  const withLoading = async <T>(key: string, asyncFn: () => Promise<T>): Promise<T> => {
    if (!(key in states)) {
      console.warn(`Loading state key "${key}" not found. Available keys: ${Object.keys(states).join(', ')}`)
      return asyncFn()
    }

    try {
      states[key] = true
      return await asyncFn()
    } finally {
      states[key] = false
    }
  }

  const resetAll = (): void => {
    Object.keys(states).forEach(key => {
      states[key] = false
    })
  }

  const anyLoading = computed(() => {
    return Object.values(states).some(value => value)
  })

  return {
    loadingStates,
    isLoading,
    setLoading,
    withLoading,
    resetAll,
    anyLoading
  }
}
