<template>
  <div class="gold-performance-chart">
    <canvas ref="chartCanvas" v-show="hasData"></canvas>
    <div v-show="!hasData" class="no-data-message">
      <el-empty description="No Comparison Data" :image-size="100" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChartConfiguration } from 'chart.js'
import zoomPlugin from 'chartjs-plugin-zoom'
import dayjs from 'dayjs'
import { computed, ref } from 'vue'
import { useChart } from '../composables/useChart'
import { buildZoomPluginOptions } from '../utils/chartZoom'
import type { GoldPerformance } from '../types/models'

const props = defineProps<{
  performance: GoldPerformance | null
}>()

const chartCanvas = ref<HTMLCanvasElement | null>(null)

const hasData = computed(() => (props.performance?.dates?.length ?? 0) > 0)

function lineDataset(
  label: string,
  data: (number | null)[],
  color: string
) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: color,
    fill: false,
    tension: 0.2,
    pointRadius: 0,
    pointHoverRadius: 4,
    borderWidth: 2,
    spanGaps: true
  }
}

const buildConfig = (): ChartConfiguration | null => {
  const performance = props.performance
  if (!performance || performance.dates.length === 0) return null

  const total = performance.dates.length
  const labels = performance.dates.map((day) =>
    total > 400 ? dayjs(day).format('YY/MM') : dayjs(day).format('MM/DD')
  )

  return {
    type: 'line',
    data: {
      labels,
      datasets: [
        lineDataset('User Gold Account', performance.user_nav, '#409EFF'),
        lineDataset('Strategy Model', performance.model_nav, '#67C23A'),
        lineDataset(`Buy & Hold ${performance.benchmark_symbol}`, performance.benchmark_nav, '#E6A23C')
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
          title: { display: true, text: 'NAV (start = 100)' }
        },
        x: {
          ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }
        }
      },
      plugins: {
        legend: { display: true, position: 'top' },
        zoom: buildZoomPluginOptions(),
        datalabels: { display: false },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: (context: { dataset: { label?: string }; parsed: { y: number | null } }) => {
              const value = context.parsed.y
              if (value === null || value === undefined) return `${context.dataset.label}: N/A`
              return `${context.dataset.label}: ${value.toFixed(2)}`
            }
          }
        }
      }
    }
  }
}

useChart(chartCanvas, buildConfig, {
  watchSource: () => props.performance,
  registerPlugins: [zoomPlugin]
})
</script>

<style scoped>
.gold-performance-chart {
  height: 340px;
  position: relative;
}

.no-data-message {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 220px;
}
</style>
