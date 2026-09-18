<template>
  <el-table 
    :data="data" 
    style="width: 100%" 
    v-loading="loading"
    :empty-text="emptyText"
    :fit="true"
    :show-summary="showSummary"
    :summary-method="summaryMethod"
  >
    <el-table-column 
      v-for="column in columns" 
      :key="column.prop"
      :prop="column.prop"
      :label="column.label"
      :width="column.width"
      :min-width="column.minWidth"
      :align="column.align || 'left'"
      :sortable="column.sortable"
    >
      <template #default="scope">
        <div v-if="column.type === 'date'">
          {{ formatDate(scope.row[column.prop]) }}
        </div>
        <div v-else-if="column.type === 'currency'">
          {{ formatCurrency(scope.row[column.prop], column.currency || scope.row.currency, column.decimalPlaces !== undefined ? column.decimalPlaces : 2) }}
        </div>
        <div v-else-if="column.type === 'quantity'">
          {{ formatQuantity(scope.row[column.prop]) }}
        </div>
        <div v-else-if="column.type === 'tag'">
          <el-tag :type="getTagType(scope.row[column.prop], column.tagTypeMap)">
            {{ scope.row[column.prop] }}
          </el-tag>
        </div>
        <div v-else-if="column.type === 'pnl'">
          <span :class="scope.row[column.prop] >= 0 ? 'positive' : 'negative'">
            {{ formatCurrency(scope.row[column.prop], column.currency || scope.row.currency, column.decimalPlaces !== undefined ? column.decimalPlaces : 2) }}
          </span>
        </div>
        <div v-else-if="column.type === 'percentage'">
          {{ formatPercentage(scope.row[column.prop], column.decimalPlaces !== undefined ? column.decimalPlaces : 2) }}
        </div>
        <div v-else-if="column.type === 'pnl_percentage'">
          <span :class="scope.row[column.prop] >= 0 ? 'positive' : 'negative'">
            {{ formatPercentage(scope.row[column.prop], column.decimalPlaces !== undefined ? column.decimalPlaces : 2) }}
          </span>
        </div>
        <div v-else-if="column.type === 'actions'">
          <el-button 
            v-for="action in column.actions" 
            :key="action.name"
            :size="action.size || 'small'"
            :type="action.type || 'default'"
            @click="emit('action', action.name, scope.row)"
          >
            {{ action.label }}
          </el-button>
        </div>
        <div v-else-if="column.type === 'custom'">
          <slot :name="column.prop" :row="scope.row" :value="scope.row[column.prop]">
            {{ scope.row[column.prop] }}
          </slot>
        </div>
        <div v-else>
          {{ scope.row[column.prop] }}
        </div>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { formatCurrency, formatDate, formatQuantity, formatPercentage } from '../utils/formatters'

// Column type definitions
interface TableColumnAction {
  name: string
  label: string
  size?: string
  type?: string
}

export interface TableColumn {
  prop: string
  label: string
  width?: string
  minWidth?: string
  align?: string
  sortable?: boolean
  type?: string
  currency?: any
  decimalPlaces?: number
  tagTypeMap?: Record<string, string>
  actions?: TableColumnAction[]
}

interface TableRow {
  [key: string]: any
}

// Props definition
const props = defineProps<{
  data?: TableRow[]
  columns: TableColumn[]
  loading?: boolean
  emptyText?: string
  showSummary?: boolean
  summaryMethod?: ((param: { columns: TableColumn[]; data: TableRow[] }) => (string | any)[]) | null
}>()

// Emits definition
const emit = defineEmits<{
  action: [actionName: string, row: Record<string, any>]
}>()

// Methods
const getTagType = (value: string, tagTypeMap: Record<string, string> | undefined): string => {
  if (!tagTypeMap) return 'info'
  return tagTypeMap[value] || 'info'
}
</script>

<style scoped>
.el-table {
  border-radius: 0 0 12px 12px;
}

.el-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.el-table :deep(.el-table__body-wrapper) {
  border-radius: 0 0 12px 12px;
}

.positive {
  color: #67C23A;
  font-weight: 500;
}

.negative {
  color: #F56C6C;
  font-weight: 500;
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .el-table :deep(.el-table__body td) {
    font-size: 12px;
  }
  
  .el-table :deep(.el-table__header th) {
    font-size: 11px;
  }
}

@media (max-width: 479px) {
  .el-table :deep(.el-table__body td) {
    font-size: 11px;
    padding: 6px 0;
  }
  
  .el-table :deep(.el-table__header th) {
    font-size: 10px;
    padding: 8px 0;
  }
}
</style>