import { onActivated, onDeactivated, onMounted, ref, watch } from 'vue'
import { usePortfolioStore } from '@/stores'
import { handleApiError } from '@/utils/errorHandler'

/**
 * Run a page loader for the currently selected portfolio.
 *
 * - Loads once on mount.
 * - Reloads when the global portfolio selector changes.
 * - Defers reloads while a keep-alive page is inactive and refreshes it on
 *   activation instead.
 * - Queues a reload if the selection changes while a load is already running,
 *   so the last selected portfolio always wins.
 */
export function usePortfolioRefresh(
  load: (portfolioId: number) => Promise<void> | void
) {
  const portfolioStore = usePortfolioStore()
  const loadedPortfolioId = ref<number | null>(null)

  let running = false
  let queued = false
  let bootstrapping = false
  let active = false
  let activatedOnce = false

  const run = async () => {
    if (running) {
      queued = true
      return
    }

    running = true
    try {
      if (!portfolioStore.currentPortfolio) {
        bootstrapping = true
        try {
          await portfolioStore.fetchPortfolios()
        } finally {
          bootstrapping = false
        }
      }

      const portfolioId = portfolioStore.currentPortfolioId
      if (!portfolioId) {
        loadedPortfolioId.value = null
        return
      }

      loadedPortfolioId.value = portfolioId
      await load(portfolioId)
    } catch (error) {
      handleApiError(error, 'Failed to load portfolio data')
    } finally {
      running = false
      const currentId = portfolioStore.currentPortfolioId
      if (
        queued ||
        (currentId !== undefined && currentId !== loadedPortfolioId.value)
      ) {
        queued = false
        run()
      }
    }
  }

  onMounted(() => {
    active = true
    run()
  })

  onActivated(() => {
    active = true
    if (!activatedOnce) {
      activatedOnce = true
      return
    }

    const currentId = portfolioStore.currentPortfolioId
    if (currentId && currentId !== loadedPortfolioId.value) {
      queued = false
      run()
    }
  })

  onDeactivated(() => {
    active = false
  })

  watch(
    () => portfolioStore.currentPortfolioId,
    (portfolioId) => {
      if (
        bootstrapping ||
        !portfolioId ||
        portfolioId === loadedPortfolioId.value
      ) {
        return
      }

      if (active) {
        run()
      } else {
        queued = true
      }
    }
  )

  return { reload: run }
}
