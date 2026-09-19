<template>
  <div class="performance-chart-wrapper">
    <!-- Portfolio Performance Chart -->
    <div class="chart-container">
      <canvas ref="performanceChart" v-show="hasPerformanceData"></canvas>
      <div v-show="!hasPerformanceData" class="no-data-message">
        <el-empty description="No Performance Data" :image-size="100"></el-empty>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChartConfiguration } from 'chart.js'
import zoomPlugin from 'chartjs-plugin-zoom'
import dayjs from 'dayjs'
import { ref, computed } from 'vue'
import { useChart } from '../composables/useChart'
import { buildZoomPluginOptions } from '../utils/chartZoom'

// Performance history item interface
interface PerformanceHistoryItem {
  date: string
  value: number
  nav?: number
  benchmark_price?: number | null
}

// Raw data cache interface
interface RawDataCache {
  portfolioValues: number[]
  navValues: number[]
  benchmarkValues: (number | null)[]
  navScaleRatio: number
  benchmarkScaleRatio: number | null
}

// Props definition
const props = defineProps<{
  performanceHistory: PerformanceHistoryItem[]
  currencySymbol?: string
}>()

// Template ref for canvas
const performanceChart = ref<HTMLCanvasElement | null>(null)

// Store raw data and scale ratios for tooltip and axis display
const rawDataCache: RawDataCache = {
  portfolioValues: [],
  navValues: [],
  benchmarkValues: [],
  navScaleRatio: 1,
  benchmarkScaleRatio: null
}

// Computed property to check if performance data exists
const hasPerformanceData = computed(() => {
  return props.performanceHistory && props.performanceHistory.length > 0
})

// Check if benchmark data exists
const hasBenchmarkData = computed(() => {
  return props.performanceHistory && props.performanceHistory.length > 0 &&
    props.performanceHistory.some((item: PerformanceHistoryItem) => item.benchmark_price !== undefined)
})

// Return type for preparePerformanceData
interface PreparedChartData {
  labels: string[]
  portfolioValues: number[]
  navValuesForDisplay: number[]
  benchmarkValuesForDisplay: (number | null)[]
}

// Prepare performance data for chart
const preparePerformanceData = (): PreparedChartData => {
  if (!props.performanceHistory || props.performanceHistory.length === 0) {
    return { labels: [], portfolioValues: [], navValuesForDisplay: [], benchmarkValuesForDisplay: [] }
  }

  const labels = props.performanceHistory.map((item: PerformanceHistoryItem) =>
    dayjs(item.date).format('MM/DD')
  )

  // Get raw data
  const portfolioValues = props.performanceHistory.map((item: PerformanceHistoryItem) => item.value)
  const navValues = props.performanceHistory.map((item: PerformanceHistoryItem) => item.nav || 1.0)

  // Fill missing benchmark prices with last known value
  let lastBenchmarkPrice: number | null = null
  const benchmarkValues: (number | null)[] = props.performanceHistory.map((item: PerformanceHistoryItem) => {
    if (item.benchmark_price !== undefined && item.benchmark_price !== null) {
      lastBenchmarkPrice = item.benchmark_price
      return item.benchmark_price
    }
    return lastBenchmarkPrice
  })

  // Calculate ratio using FIRST day's data to ensure all curves start at the same point
  // This ensures day 1: portfolioValue = navDisplay = benchmarkDisplay
  const firstPortfolioValue = portfolioValues[0]
  const firstNavValue = navValues[0]
  // Use first non-null benchmark value to handle ranges starting on weekends/holidays
  const firstBenchmarkValue = benchmarkValues.find((v: number | null) => v !== null && v !== undefined) ?? null

  // Scale NAV: navDisplay = nav * (firstPortfolioValue / firstNavValue)
  // This makes first navDisplay = firstPortfolioValue
  const navScaleRatio = (firstNavValue && firstNavValue !== 0)
    ? firstPortfolioValue / firstNavValue
    : 1
  const navValuesForDisplay = navValues.map((nav: number) => nav * navScaleRatio)

  // Scale Benchmark: benchmarkDisplay = benchmark * (firstPortfolioValue / firstBenchmarkValue)
  // This makes first benchmarkDisplay = firstPortfolioValue
  const benchmarkScaleRatio: number | null = (firstBenchmarkValue && firstBenchmarkValue !== 0)
    ? firstPortfolioValue / firstBenchmarkValue
    : null

  const benchmarkValuesForDisplay: (number | null)[] = benchmarkScaleRatio
    ? benchmarkValues.map((bm: number | null) => (bm !== null && bm !== undefined) ? bm * benchmarkScaleRatio : null)
    : benchmarkValues

  // Cache raw data and scale ratios
  rawDataCache.portfolioValues = portfolioValues
  rawDataCache.navValues = navValues
  rawDataCache.benchmarkValues = benchmarkValues
  rawDataCache.navScaleRatio = navScaleRatio
  rawDataCache.benchmarkScaleRatio = benchmarkScaleRatio

  return { labels, portfolioValues, navValuesForDisplay, benchmarkValuesForDisplay }
}

const buildConfig = (_ctx: CanvasRenderingContext2D): ChartConfiguration | null => {
  const { labels, portfolioValues, navValuesForDisplay, benchmarkValuesForDisplay } = preparePerformanceData()

  if (labels.length === 0 || portfolioValues.length === 0) {
    console.warn('No performance data available for chart')
    return null
  }

  // Build datasets array - all use the same y-axis for proper alignment
  const datasets = [{
    label: 'Portfolio Value',
    data: portfolioValues,
    borderColor: '#409EFF',
    backgroundColor: 'rgba(64, 158, 255, 0.1)',
    fill: false,
    tension: 0.4,
    pointRadius: 0,
    pointHoverRadius: 0,
    yAxisID: 'y'
  }, {
    label: 'NAV',
    data: navValuesForDisplay,
    borderColor: '#67C23A',
    backgroundColor: 'rgba(103, 194, 58, 0.1)',
    fill: false,
    tension: 0.4,
    pointRadius: 0,
    pointHoverRadius: 0,
    yAxisID: 'y'
  }]

  // Add benchmark dataset if data exists
  if (hasBenchmarkData.value && benchmarkValuesForDisplay.length > 0) {
    const benchmarkData: (number | null)[] = benchmarkValuesForDisplay
    datasets.push({
      label: 'Benchmark',
      data: benchmarkData as any,
      borderColor: '#E6A23C',
      backgroundColor: 'rgba(230, 162, 60, 0.1)',
      fill: false,
      tension: 0.4,
      pointRadius: 0,
      pointHoverRadius: 0,
      yAxisID: 'y'
    } as any)
  }

  // Calculate min/max for display
  const minPortfolio = Math.min(...portfolioValues.filter(v => v !== null))
  const maxPortfolio = Math.max(...portfolioValues.filter(v => v !== null))

  // Calculate actual min/max considering all data on y axis (including benchmark)
  let minDisplay = minPortfolio
  let maxDisplay = maxPortfolio
  if (hasBenchmarkData.value && benchmarkValuesForDisplay.length > 0) {
    const minBenchmark = Math.min(...benchmarkValuesForDisplay.filter(v => v !== null))
    const maxBenchmark = Math.max(...benchmarkValuesForDisplay.filter(v => v !== null))
    minDisplay = Math.min(minDisplay, minBenchmark)
    maxDisplay = Math.max(maxDisplay, maxBenchmark)
  }

  const scales = {
    y: {
      type: 'linear' as const,
      display: true,
      position: 'left' as const,
      beginAtZero: false,
      title: {
        display: true,
        text: 'Portfolio Value'
      },
      ticks: {
        callback: (value: string | number) => {
          return props.currencySymbol + Number(value).toLocaleString()
        }
      },
      min: minDisplay,
      max: maxDisplay
    },
    y1: {
      type: 'linear' as const,
      display: true,
      position: 'right' as const,
      beginAtZero: false,
      title: {
        display: true,
        text: 'NAV'
      },
      ticks: {
        callback: (value: string | number) => {
          // Convert displayed value back to actual NAV using the same scale ratio
          const actualNav = Number(value) / rawDataCache.navScaleRatio
          return actualNav.toFixed(4)
        }
      },
      grid: {
        drawOnChartArea: false,
      },
      // Set y1 axis to have the same range as y axis (including benchmark)
      min: minDisplay,
      max: maxDisplay
    },
    x: {
      ticks: {
        maxRotation: 0,
        autoSkip: true,
        maxTicksLimit: 10
      }
    }
  }

  return {
    type: 'line',
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      scales: scales,
      plugins: {
        legend: {
          display: true,
          position: 'top'
        },
        zoom: buildZoomPluginOptions(['y', 'y1']),
        datalabels: {
          display: false
        },
        tooltip: {
          mode: 'index' as const,
          intersect: false,
          callbacks: {
            label: function(context: { dataset: { label?: string }; dataIndex: number; parsed: { y: number } }) {
              const datasetLabel = context.dataset.label || ''
              const dataIndex = context.dataIndex

              if (datasetLabel === 'Portfolio Value') {
                const value = rawDataCache.portfolioValues[dataIndex]
                return `Portfolio Value: ${props.currencySymbol}${value ? value.toLocaleString() : 'N/A'}`
              } else if (datasetLabel === 'NAV') {
                const value = rawDataCache.navValues[dataIndex]
                return `NAV: ${value ? value.toFixed(4) : 'N/A'}`
              } else if (datasetLabel === 'Benchmark') {
                const value = rawDataCache.benchmarkValues[dataIndex]
                return `Benchmark: ${value ? value.toFixed(2) : 'N/A'}`
              }
              return `${datasetLabel}: ${context.parsed.y}`
            }
          }
        }
      }
    }
  }
}

useChart(performanceChart, buildConfig, {
  watchSource: () => props.performanceHistory,
  registerPlugins: [zoomPlugin],
})
</script>

<style scoped>
.chart-container {
  height: 300px;
  position: relative;
}

.no-data-message {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
}
</style>
