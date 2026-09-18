import { Chart, registerables } from 'chart.js'
import type { Chart as ChartType, ChartConfiguration, Plugin } from 'chart.js'
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import type { Ref, WatchSource } from 'vue'

Chart.register(...registerables)

interface UseChartOptions {
  registerPlugins?: Plugin[]
  watchSource?: WatchSource | WatchSource[]
  watchDeep?: boolean
}

export function useChart(
  canvasRef: Ref<HTMLCanvasElement | null>,
  buildConfig: (ctx: CanvasRenderingContext2D) => ChartConfiguration | null,
  options: UseChartOptions = {}
) {
  const chartInstance = ref<ChartType | null>(null)

  if (options.registerPlugins) {
    Chart.register(...options.registerPlugins)
  }

  const destroyChart = () => {
    if (chartInstance.value) {
      try {
        chartInstance.value.destroy()
      } catch {
        // Ignore errors during cleanup
      }
      chartInstance.value = null
    }
  }

  const createChart = () => {
    nextTick(() => {
      const canvas = canvasRef.value
      if (!canvas) return

      if (canvas.offsetWidth === 0 || canvas.offsetHeight === 0) return

      const ctx = canvas.getContext('2d')
      if (!ctx) {
        console.warn('Could not get 2D context from chart canvas')
        return
      }

      destroyChart()

      try {
        const config = buildConfig(ctx)
        if (config) {
          chartInstance.value = new Chart(ctx, config)
        }
      } catch (error) {
        console.error('Error creating chart:', error)
        chartInstance.value = null
      }
    })
  }

  onMounted(() => {
    createChart()
  })

  onBeforeUnmount(() => {
    destroyChart()
  })

  if (options.watchSource) {
    watch(
      options.watchSource,
      () => { createChart() },
      { deep: options.watchDeep ?? true }
    )
  }

  return { chartInstance, createChart, destroyChart }
}
