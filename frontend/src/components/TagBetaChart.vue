<template>
  <div class="tag-beta">
    <div v-if="!data || !data.tags || data.tags.length === 0" class="no-data-message">
      <el-empty description="No beta data available" :image-size="100"></el-empty>
    </div>
    <div v-else>
      <el-table
        :data="tableData"
        style="width: 100%"
        border
      >
        <el-table-column prop="tag" label="Tag" width="150" />
        <el-table-column prop="beta" label="Beta" align="center" min-width="100"
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
      </el-table>

      <div class="beta-footer">
        <div v-if="data.insufficient_data_tags && data.insufficient_data_tags.length > 0"
             class="insufficient-tags">
          <span class="warning-text">
            Insufficient data: {{ data.insufficient_data_tags.join(', ') }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface TagBetaData {
  tags?: string[]
  betas?: number[]
  tag_data_points?: number[]
  insufficient_data_tags?: string[]
  data_points?: number
  frequency?: string
}

const props = defineProps<{
  data: TagBetaData | null
}>()

interface TableRow {
  tag: string
  beta: number
  data_points?: number
}

const tableData = computed<TableRow[]>(() => {
  if (!props.data || !props.data.tags || !props.data.betas) {
    return []
  }
  const tags = props.data.tags
  const betas = props.data.betas
  return tags.map((tag: string, index: number) => ({
    tag,
    beta: betas[index],
    data_points: props.data?.tag_data_points?.[index]
  }))
})

function formatBeta(value: number | undefined | null): string {
  if (value === undefined || value === null) return '-'
  return Number(value).toFixed(2)
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
.tag-beta {
  width: 100%;
}

.tag-beta :deep(.el-table__header th) {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
}

.tag-beta :deep(.el-table__body td) {
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

.insufficient-tags {
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
