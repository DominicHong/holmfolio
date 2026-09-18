<template>
  <div class="gold-signal-chart">
    <div class="price-chart-wrapper">
      <canvas ref="chartCanvas" v-show="hasData"></canvas>
      <div v-show="!hasData" class="no-data-message">
        <el-empty description="No Signal Data" :image-size="100" />
      </div>
    </div>
    <div v-show="hasPositionData" class="position-chart-wrapper">
      <div class="position-chart-title">Strategy Position (% of equity)</div>
      <canvas ref="positionCanvas"></canvas>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChartConfiguration } from 'chart.js'
import dayjs from 'dayjs'
import { computed, ref } from 'vue'
import { useChart } from '../composables/useChart'
import type { GoldSignal } from '../types/models'

const props = defineProps<{
  seriesDates: string[]
  series: Record<string, (number | null)[]>
  signals: GoldSignal[]
}>()

const chartCanvas = ref<HTMLCanvasElement | null>(null)
const positionCanvas = ref<HTMLCanvasElement | null>(null)

const hasData = computed(
  () => props.seriesDates.length > 0 && (props.series.close?.length ?? 0) > 0
)

const hasPositionData = computed(
  () => props.seriesDates.length > 0 && (props.series.position_pct?.length ?? 0) > 0
)

function chartLabels(): string[] {
  const total = props.seriesDates.length
  return props.seriesDates.map((day) =>
    total > 400 ? dayjs(day).format('YY/MM') : dayjs(day).format('MM/DD')
  )
}

function overlayDataset(
  label: string,
  data: (number | null)[],
  color: string,
  dashed = false
) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: color,
    borderWidth: dashed ? 1 : 1.5,
    borderDash: dashed ? [5, 4] : undefined,
    fill: false,
    tension: 0.2,
    pointRadius: 0,
    pointHoverRadius: 0,
    spanGaps: true
  }
}

function markerDataset(
  label: string,
  points: (number | null)[],
  color: string,
  rotation: number
) {
  return {
    label,
    data: points,
    borderColor: color,
    backgroundColor: color,
    showLine: false,
    pointRadius: 6,
    pointHoverRadius: 8,
    pointRotation: rotation
  }
}

function buildConfig(): ChartConfiguration | null {
  if (!hasData.value) return null

  const labels = chartLabels()
  const total = props.seriesDates.length
  const close = props.series.close ?? []
  const indexByDate = new Map(props.seriesDates.map((day, index) => [day, index]))

  const buyPoints: (number | null)[] = new Array(total).fill(null)
  const sellPoints: (number | null)[] = new Array(total).fill(null)
  const reasons = new Map<number, string>()

  for (const signal of props.signals) {
    const day = signal.exec_date ?? signal.signal_date
    const index = indexByDate.get(day)
    if (index === undefined) continue
    const value = signal.exec_price ?? close[index] ?? null
    if (signal.action === 'buy') {
      buyPoints[index] = value
    } else {
      sellPoints[index] = value
    }
    reasons.set(index, `${signal.action.toUpperCase()} (${signal.reason})`)
  }

  const datasets: any[] = [overlayDataset('Close', close, '#303133')]
  if (props.series.fast) datasets.push(overlayDataset('Fast MA', props.series.fast, '#67C23A'))
  if (props.series.slow) datasets.push(overlayDataset('Slow MA', props.series.slow, '#909399'))
  if (props.series.mid) datasets.push(overlayDataset('Middle Band', props.series.mid, '#E6A23C', true))
  if (props.series.top) datasets.push(overlayDataset('Upper Band', props.series.top, '#E6A23C', true))
  if (props.series.bottom) datasets.push(overlayDataset('Lower Band', props.series.bottom, '#E6A23C', true))
  if (props.series.stop) datasets.push(overlayDataset('Stop Price', props.series.stop, '#F56C6C', true))
  datasets.push(markerDataset('Buy', buyPoints, '#67C23A', 0))
  datasets.push(markerDataset('Sell', sellPoints, '#F56C6C', 180))

  return {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          title: { display: true, text: 'Price' }
        },
        x: {
          ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }
        }
      },
      plugins: {
        legend: { display: true, position: 'top' },
        datalabels: { display: false },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: (context: { dataset: { label?: string }; dataIndex: number; parsed: { y: number | null } }) => {
              if (context.dataset.label === 'Buy' || context.dataset.label === 'Sell') {
                const reason = reasons.get(context.dataIndex)
                return reason ?? `${context.dataset.label} signal`
              }
              const value = context.parsed.y
              if (value === null || value === undefined) return `${context.dataset.label}: N/A`
              return `${context.dataset.label}: ${value.toFixed(3)}`
            }
          }
        }
      }
    }
  }
}

function buildPositionConfig(): ChartConfiguration | null {
  if (!hasPositionData.value) return null

  return {
    type: 'bar',
    data: {
      labels: chartLabels(),
      datasets: [
        {
          label: 'Strategy Position %',
          data: props.series.position_pct ?? [],
          backgroundColor: 'rgba(64, 158, 255, 0.45)',
          borderColor: '#409EFF',
          borderWidth: 1,
          barPercentage: 0.9,
          categoryPercentage: 0.9
        } as any
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          min: 0,
          max: 100,
          title: { display: true, text: 'Position %' },
          ticks: {
            callback: (value: string | number) => `${value}%`
          }
        },
        x: {
          ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }
        }
      },
      plugins: {
        legend: { display: false },
        datalabels: { display: false },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: (context: { parsed: { y: number | null } }) => {
              const value = context.parsed.y
              return value === null || value === undefined
                ? 'Position: 0%'
                : `Position: ${value.toFixed(1)}%`
            }
          }
        }
      }
    }
  }
}

useChart(chartCanvas, buildConfig, {
  watchSource: () => [props.seriesDates, props.series, props.signals]
})

useChart(positionCanvas, buildPositionConfig, {
  watchSource: () => [props.seriesDates, props.series]
})
</script>

<style scoped>
.price-chart-wrapper {
  height: 340px;
  position: relative;
}

.position-chart-wrapper {
  height: 150px;
  position: relative;
  margin-top: 8px;
}

.position-chart-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.no-data-message {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 220px;
}
</style>
