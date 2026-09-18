<template>
  <div class="allocation-chart-wrapper">
    <!-- Asset Allocation Chart -->
    <div class="chart-container">
      <canvas ref="allocationChartRef" v-show="hasAllocationData"></canvas>
      <div v-show="!hasAllocationData" class="no-data-message">
        <el-empty description="No Position" :image-size="100"></el-empty>
      </div>
    </div>

    <!-- Allocation Details -->
    <div class="allocation-details" v-if="Object.keys(assetAllocation).length > 0">
      <el-divider></el-divider>
      <div class="allocation-item" v-for="(percentage, type) in sortedAllocation" :key="type">
        <span class="allocation-label">{{ formatAllocationType(type) }}:</span>
        <span class="allocation-value">{{ formatPercentage(percentage) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ChartConfiguration } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { formatPercentage } from '../utils/formatters'
import { useChart } from '../composables/useChart'

// Props
const props = defineProps<{
  assetAllocation: Record<string, number>
}>()

// Refs
const allocationChartRef = ref<HTMLCanvasElement | null>(null)

// Computed properties
const hasAllocationData = computed(() => {
  const allocation = props.assetAllocation || {}
  return Object.values(allocation).some((percentage: number) => percentage > 0)
})

const sortedAllocation = computed(() => {
  const allocation = props.assetAllocation || {}
  return Object.entries(allocation)
    .filter(([, percentage]: [string, number]) => percentage > 0)
    .sort(([, a]: [string, number], [, b]: [string, number]) => b - a)
    .reduce((obj: Record<string, number>, [type, percentage]: [string, number]) => {
      obj[type] = percentage
      return obj
    }, {})
})

// Return types
interface AllocationChartData {
  labels: string[]
  data: number[]
}

const getAllocationData = (): AllocationChartData => {
  const allocation = props.assetAllocation || {}

  const filteredAllocation = Object.entries(allocation)
    .filter(([, percentage]: [string, number]) => percentage > 0)
    .sort(([, a]: [string, number], [, b]: [string, number]) => b - a)

  if (filteredAllocation.length === 0) {
    return {
      labels: [],
      data: []
    }
  }

  const labels = filteredAllocation.map(([type]: [string, number]) => {
    return type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' ')
  })

  const data = filteredAllocation.map(([, percentage]: [string, number]) => percentage)

  return { labels, data }
}

const formatAllocationType = (type: string): string => {
  if (!type) return 'Unknown'
  return type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' ')
}

const buildConfig = (_ctx: CanvasRenderingContext2D): ChartConfiguration | null => {
  const allocationData: AllocationChartData = getAllocationData()

  if (!allocationData.data || allocationData.data.length === 0 ||
    allocationData.data.every((val: number) => val === 0)) {
    return null
  }

  return {
    type: 'doughnut',
    data: {
      labels: allocationData.labels,
      datasets: [{
        data: allocationData.data,
        backgroundColor: [
          '#409EFF',
          '#67C23A',
          '#E6A23C',
          '#F56C6C',
          '#909399',
          '#00c0ef',
          '#ff851b',
          '#605ca8',
          '#d2d6de',
          '#001f3f'
        ],
        borderWidth: 2,
        borderColor: '#fff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: {
          display: false
        },
        datalabels: {
          display: true,
          color: '#fff',
          font: {
            weight: 'bold' as const,
            size: 12
          },
          formatter: (value: number, ctx: { chart: { data: { labels: string[] } }; dataIndex: number }): string => {
            const label = ctx.chart.data.labels?.[ctx.dataIndex] || ''
            const percentage = (value * 100).toFixed(1)
            return `${label}\n${percentage}%`
          },
          textAlign: 'center' as const
        } as any,
        tooltip: {
          callbacks: {
            label: function (context: { label?: string; parsed: number; dataset: { data: unknown[] } }) {
              const label = context.label || ''
              const value = context.parsed || 0
              const total = context.dataset.data.reduce<number>((sum: number, item) => sum + Number(item), 0)
              const percentage = (100 * value / total).toFixed(2)
              return `${label}: ${percentage}%`
            }
          }
        }
      }
    }
  }
}

useChart(allocationChartRef, buildConfig, {
  registerPlugins: [ChartDataLabels],
  watchSource: () => props.assetAllocation,
})
</script>

<style scoped>
.chart-container {
  height: 300px;
  position: relative;
}

.allocation-details {
  margin-top: 15px;
}

.allocation-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 13px;
}

.allocation-label {
  color: #606266;
  font-weight: 500;
}

.allocation-value {
  color: #303133;
  font-weight: 600;
}

.no-data-message {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
}
</style>