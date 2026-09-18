<template>
  <div class="asset-beta">
    <div v-if="!data || !data.assets || data.assets.length === 0" class="no-data-message">
      <el-empty description="No beta data available" :image-size="100"></el-empty>
    </div>
    <div v-else>
      <el-table
        :data="tableData"
        style="width: 100%"
        border
      >
        <el-table-column prop="symbol" label="Symbol" width="100" />
        <el-table-column prop="name" label="Name" min-width="120" show-overflow-tooltip />
        <el-table-column prop="beta" label="Beta" align="center" width="100"
          :cell-style="betaCellStyle">
          <template #default="scope">
            <span class="num-value" :class="getBetaClass(scope.row.beta)">
              {{ formatBeta(scope.row.beta) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="Data Points" align="center" width="110">
          <template #default="scope">
            <span class="points-value">{{ scope.row.data_points ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="market_value" label="Market Value" align="right" width="130">
          <template #default="scope">
            <span class="num-value">{{ formatMarketValue(scope.row.market_value) }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="beta-footer">
        <div v-if="data.insufficient_data_assets && data.insufficient_data_assets.length > 0"
             class="insufficient-assets">
          <span class="warning-text">
            Insufficient data: {{ data.insufficient_data_assets.join(', ') }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface AssetBetaData {
  assets?: {
    asset_id: number
    symbol: string
    name: string
    beta: number
    market_value: number
    data_points?: number
  }[]
  insufficient_data_assets?: string[]
  data_points?: number
  frequency?: string
}

const props = defineProps<{
  data: AssetBetaData | null
}>()

interface TableRow {
  asset_id: number
  symbol: string
  name: string
  beta: number
  market_value: number
  data_points?: number
}

const tableData = computed<TableRow[]>(() => {
  if (!props.data || !props.data.assets) {
    return []
  }
  return props.data.assets
})

function formatBeta(value: number | undefined | null): string {
  if (value === undefined || value === null) return '-'
  return Number(value).toFixed(2)
}

function formatMarketValue(value: number | undefined | null): string {
  if (value === undefined || value === null) return '-'
  if (value >= 1e8) return (value / 1e8).toFixed(2) + '亿'
  if (value >= 1e4) return (value / 1e4).toFixed(2) + '万'
  return value.toFixed(2)
}

function getBetaClass(value: number | undefined | null): string {
  if (value === undefined || value === null) return ''
  if (value > 0) return 'positive'
  if (value < 0) return 'negative'
  return ''
}

function betaCellStyle({ row }: { row: { beta: number | undefined | null } }): Record<string, string> {
  const value = row.beta
  if (value === undefined || value === null) return {}

  const dist = Math.abs(value - 1)
  const intensity = Math.min(dist / 2, 0.35)

  if (value > 1) {
    const r = Math.round(255 - intensity * 100)
    const g = Math.round(248 - intensity * 120)
    const b = Math.round(240 - intensity * 120)
    return { backgroundColor: `rgb(${r}, ${g}, ${b})` }
  } else if (value > 0) {
    const r = Math.round(240 - intensity * 80)
    const g = Math.round(248 - intensity * 40)
    const b = Math.round(255 - intensity * 40)
    return { backgroundColor: `rgb(${r}, ${g}, ${b})` }
  } else if (value < 0) {
    const r = Math.round(255 - intensity * 40)
    const g = Math.round(240 - intensity * 120)
    const b = Math.round(240 - intensity * 120)
    return { backgroundColor: `rgb(${r}, ${g}, ${b})` }
  }
  return { backgroundColor: 'rgb(250, 250, 250)' }
}
</script>

<style scoped>
.asset-beta {
  width: 100%;
}

.asset-beta :deep(.el-table__header th) {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
}

.asset-beta :deep(.el-table__body td) {
  font-size: 14px;
  padding: 12px 0;
}

.no-data-message {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
}

.num-value {
  font-size: 15px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.positive {
  color: #1f883d;
}

.negative {
  color: #cf222e;
}

.beta-footer {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.insufficient-assets {
  font-size: 12px;
}

.points-value {
  font-size: 13px;
  color: #909399;
  font-variant-numeric: tabular-nums;
}

.warning-text {
  color: #e6a23c;
}

.info-text {
  color: #909399;
}
</style>
