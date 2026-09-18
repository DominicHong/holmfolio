<template>
  <div class="tag-correlation">
    <div v-if="!data || !data.tags || data.tags.length === 0" class="no-data-message">
      <el-empty description="No correlation data available" :image-size="100"></el-empty>
    </div>
    <div v-else>
      <el-table
        :data="tableData"
        style="width: 100%"
        :cell-style="cellStyle"
        border
      >
        <el-table-column prop="tag" label="Tag" width="120" fixed />
        <el-table-column
          v-for="tag in data.tags"
          :key="tag"
          :prop="tag"
          :label="tag"
          align="center"
          min-width="90"
        >
          <template #default="scope">
            <span class="num-value" :class="getValueClass(scope.row[tag])">
              {{ formatCorrelation(scope.row[tag]) }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div class="correlation-footer">
        <div v-if="data.insufficient_data_tags && data.insufficient_data_tags.length > 0" class="insufficient-tags">
          <span class="warning-text">
            Insufficient data: {{ data.insufficient_data_tags.join(', ') }}
          </span>
        </div>
        <div v-if="data.data_points" class="data-points">
          <span class="info-text">
            Based on {{ data.data_points }} daily returns
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface TagCorrelationData {
  tags?: string[]
  correlation_matrix?: number[][]
  insufficient_data_tags?: string[]
  data_points?: number
}

const props = defineProps<{
  data: TagCorrelationData | null
}>()

interface TableRow {
  tag: string
  [key: string]: any
}

const tableData = computed<TableRow[]>(() => {
  if (!props.data || !props.data.tags || !props.data.correlation_matrix) {
    return []
  }
  const tags: string[] = props.data.tags
  const matrix: number[][] = props.data.correlation_matrix
  return tags.map((tag: string, rowIndex: number) => {
    const row: TableRow = { tag }
    tags.forEach((colTag: string, colIndex: number) => {
      row[colTag] = matrix[rowIndex][colIndex]
    })
    return row
  })
})

function formatCorrelation(value: number | undefined | null): string {
  if (value === undefined || value === null) return '-'
  return value.toFixed(2)
}

function getValueClass(value: number | undefined | null): string {
  if (value === undefined || value === null) return ''
  if (value > 0) return 'positive'
  if (value < 0) return 'negative'
  return ''
}

function cellStyle({ row, column, columnIndex }: { row: TableRow; column: { property: string }; rowIndex: number; columnIndex: number }): Record<string, string> {
  if (columnIndex === 0) return {}
  const value = row[column.property] as number | undefined | null
  if (value === undefined || value === null) return {}

  const intensity = Math.min(Math.abs(value), 1)
  let backgroundColor: string
  if (value > 0) {
    const r = Math.round(240 - intensity * 80)
    const g = Math.round(248 - intensity * 40)
    const b = Math.round(240 - intensity * 80)
    backgroundColor = `rgb(${r}, ${g}, ${b})`
  } else if (value < 0) {
    const r = Math.round(248 - intensity * 40)
    const g = Math.round(240 - intensity * 80)
    const b = Math.round(240 - intensity * 80)
    backgroundColor = `rgb(${r}, ${g}, ${b})`
  } else {
    backgroundColor = 'rgb(250, 250, 250)'
  }

  return {
    backgroundColor,
    fontWeight: Math.abs(value) > 0.8 ? 'bold' : 'normal'
  }
}
</script>

<style scoped>
.tag-correlation {
  width: 100%;
}

.tag-correlation :deep(.el-table__header th) {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
}

.tag-correlation :deep(.el-table__body td) {
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

.correlation-footer {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.insufficient-tags {
  font-size: 12px;
}

.data-points {
  font-size: 12px;
}

.warning-text {
  color: #e6a23c;
}

.info-text {
  color: #909399;
}
</style>
