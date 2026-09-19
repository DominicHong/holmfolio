import type { Chart } from 'chart.js'

/**
 * Rescale the given Y axes to fit the data inside the currently visible X range.
 * Used after wheel-zoom / drag-pan so the Y axis follows the visible window.
 */
export function rescaleYAxisToVisibleData(chart: Chart, yScaleIds: string[] = ['y']): void {
  const xScale = chart.scales.x
  const datasets = chart.data.datasets
  const datasetLength = datasets[0]?.data.length ?? 0
  if (!xScale || datasetLength === 0) return

  const startIndex = Math.max(0, Math.floor(xScale.min))
  const endIndex = Math.min(datasetLength - 1, Math.ceil(xScale.max))

  let minValue = Infinity
  let maxValue = -Infinity
  for (const dataset of datasets) {
    const data = dataset.data as (number | null)[]
    for (let i = startIndex; i <= endIndex; i++) {
      const value = data[i]
      if (typeof value === 'number' && Number.isFinite(value)) {
        minValue = Math.min(minValue, value)
        maxValue = Math.max(maxValue, value)
      }
    }
  }

  if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) return

  const scaleOptions = chart.options.scales as any
  if (!scaleOptions) return

  const padding = (maxValue - minValue) * 0.05 || Math.abs(maxValue) * 0.05 || 1
  let updated = false
  for (const scaleId of yScaleIds) {
    if (!scaleOptions[scaleId]) continue
    scaleOptions[scaleId].min = minValue - padding
    scaleOptions[scaleId].max = maxValue + padding
    updated = true
  }
  if (updated) chart.update('none')
}

/**
 * Shared mouse-wheel zoom + drag-pan plugin options for time-series charts.
 * @param yScaleIds Y axes to rescale to the visible window (empty to leave them untouched)
 * @param onRangeChange Called after the visible X range changed (e.g. to sync another chart)
 */
export function buildZoomPluginOptions(yScaleIds: string[] = ['y'], onRangeChange?: (chart: Chart) => void) {
  const handleRangeChange = ({ chart }: { chart: Chart }) => {
    rescaleYAxisToVisibleData(chart, yScaleIds)
    onRangeChange?.(chart)
  }

  return {
    zoom: {
      wheel: { enabled: true },
      pinch: { enabled: true },
      mode: 'x' as const,
      onZoomComplete: handleRangeChange
    },
    pan: {
      enabled: true,
      mode: 'x' as const,
      threshold: 5,
      onPanComplete: handleRangeChange
    },
    limits: {
      x: {
        min: 'original' as const,
        max: 'original' as const,
        minRange: 5
      }
    }
  }
}
