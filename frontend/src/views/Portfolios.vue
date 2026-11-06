<template>
  <div class="portfolios">
    <div class="page-header">
      <div class="title-row">
        <h2 class="page-title">Overview</h2>
        <el-button
          :icon="Refresh"
          circle
          aria-label="Refresh"
          @click="loadData"
        />
      </div>

      <div class="portfolio-controls">
        <el-tooltip content="Snapshot date for all portfolios" placement="top">
          <el-date-picker
            v-model="asOfDate"
            type="date"
            placeholder="As of date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            :disabled-date="disabledDate"
            style="width: 150px"
            @change="loadData"
          />
        </el-tooltip>
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          New Portfolio
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="overview-cards">
      <el-col :span="6">
        <OverviewCard
          title="Total Value"
          :value="formatCurrency(summary?.total_value ?? 0, { symbol: primarySymbol }, 0)"
          :subtitle="`${summary?.portfolio_count ?? 0} portfolios`"
          :loading="loading"
        />
      </el-col>
      <el-col :span="6">
        <OverviewCard
          title="Total P&L"
          :value="formatCurrency(summary?.total_pnl ?? 0, { symbol: primarySymbol }, 0)"
          :value-class="totalPnlClass"
          :subtitle="`${summary?.asset_count ?? 0} assets held`"
          :loading="loading"
        >
          <template #title-prefix>
            <span :class="totalPnlClass">
              {{ (summary?.total_pnl ?? 0) > 0 ? '▲' : (summary?.total_pnl ?? 0) < 0 ? '▼' : '▶' }}
            </span>
          </template>
        </OverviewCard>
      </el-col>
      <el-col :span="6">
        <OverviewCard
          title="Total Cash"
          :value="formatCurrency(summary?.total_cash ?? 0, { symbol: primarySymbol }, 0)"
          subtitle="Across all portfolios"
          :loading="loading"
        />
      </el-col>
      <el-col :span="6">
        <OverviewCard
          title="Portfolios"
          :value="summary?.portfolio_count ?? 0"
          :subtitle="`${summary?.asset_count ?? 0} combined holdings`"
          :loading="loading"
        />
      </el-col>
    </el-row>

    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <span>Portfolio Breakdown</span>
          <span class="as-of-label">As of {{ asOfDate || 'today' }}</span>
        </div>
      </template>

      <SharedDataTable
        :data="summary?.portfolios ?? []"
        :columns="portfolioColumns"
        :loading="loading"
        empty-text="No portfolios found"
        @action="handlePortfolioAction"
      >
        <template #name="{ row }">
          <div class="portfolio-name-cell">
            <div class="portfolio-name-line">
              <span class="portfolio-name-text">{{ row.name }}</span>
              <el-tag
                v-if="row.id === portfolioStore.currentPortfolioId"
                size="small"
                type="success"
                effect="plain"
              >
                Current
              </el-tag>
            </div>
            <div v-if="row.description" class="portfolio-description">
              {{ row.description }}
            </div>
          </div>
        </template>
        <template #first_transaction_date="{ row }">
          {{ row.first_transaction_date ? formatDate(row.first_transaction_date) : '—' }}
        </template>
      </SharedDataTable>
    </el-card>

    <el-row :gutter="20" class="detail-row">
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span>Combined Allocation</span>
          </template>
          <AllocationChart :asset-allocation="summary?.allocation_by_type ?? {}" />
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card class="table-card holdings-card">
          <template #header>
            <div class="card-header">
              <span>Combined Holdings</span>
              <span class="as-of-label">Non-cash · quantities use each asset's native unit</span>
            </div>
          </template>

          <SharedDataTable
            :data="summary?.combined_holdings ?? []"
            :columns="holdingColumns"
            :loading="loading"
            empty-text="No holdings found"
          >
            <template #type="{ row }">
              <el-tag size="small" type="info" effect="plain">{{ row.type }}</el-tag>
            </template>
            <template #quantity="{ row }">
              {{ formatQuantity(row.quantity) }}
            </template>
          </SharedDataTable>
        </el-card>
      </el-col>
    </el-row>

    <!-- Create / Edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingPortfolioId === null ? 'New Portfolio' : 'Edit Portfolio'"
      width="480px"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px">
        <el-form-item label="Name" prop="name">
          <el-input v-model="form.name" placeholder="e.g. Main Portfolio" />
        </el-form-item>
        <el-form-item label="Description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="Optional description"
          />
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="All portfolios are valued in the global primary currency."
        />
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="saving" @click="savePortfolio">
          {{ editingPortfolioId === null ? 'Create' : 'Save' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Portfolios' })

import { computed, onActivated, onMounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import {
  usePortfolioStore,
  useReferenceStore
} from '../stores'
import OverviewCard from '../components/OverviewCard.vue'
import AllocationChart from '../components/AllocationChart.vue'
import SharedDataTable from '../components/SharedDataTable.vue'
import {
  formatCurrency,
  formatDate,
  formatQuantity
} from '../utils/formatters'
import {
  handleApiError,
  showError,
  showSuccess,
  showWarning
} from '../utils/errorHandler'
import type { PortfolioSummaryItem } from '../types/models'

const portfolioStore = usePortfolioStore()
const referenceStore = useReferenceStore()

const asOfDate = ref(formatDate(new Date()))
const loading = ref(false)

const summary = computed(() => portfolioStore.summary)
const primarySymbol = computed(
  () =>
    summary.value?.primary_currency?.symbol ||
    referenceStore.primaryCurrency?.symbol ||
    '¥'
)

const totalPnlClass = computed<'positive' | 'negative' | 'neutral'>(() => {
  const value = summary.value?.total_pnl ?? 0
  if (value > 0) return 'positive'
  if (value < 0) return 'negative'
  return 'neutral'
})

const currencyOptions = computed(() => ({ symbol: primarySymbol.value }))

const portfolioColumns = computed(() => [
  { prop: 'name', label: 'Portfolio', minWidth: '220', type: 'custom' },
  {
    prop: 'total_value',
    label: 'Total Value',
    minWidth: '130',
    align: 'right',
    type: 'currency',
    decimalPlaces: 0,
    currency: currencyOptions.value
  },
  {
    prop: 'value_weight',
    label: 'Weight',
    minWidth: '90',
    align: 'right',
    type: 'percentage',
    decimalPlaces: 2
  },
  {
    prop: 'total_pnl',
    label: 'P&L',
    minWidth: '120',
    align: 'right',
    type: 'pnl',
    decimalPlaces: 0,
    currency: currencyOptions.value
  },
  {
    prop: 'cash_value',
    label: 'Cash',
    minWidth: '120',
    align: 'right',
    type: 'currency',
    decimalPlaces: 0,
    currency: currencyOptions.value
  },
  {
    prop: 'holding_count',
    label: 'Holdings',
    minWidth: '90',
    align: 'right'
  },
  {
    prop: 'first_transaction_date',
    label: 'Since',
    minWidth: '110',
    type: 'custom'
  },
  {
    prop: 'actions',
    label: 'Actions',
    minWidth: '210',
    type: 'actions',
    actions: [
      { name: 'use', label: 'Use', size: 'small', type: 'success' },
      { name: 'edit', label: 'Edit', size: 'small', type: 'primary' },
      { name: 'delete', label: 'Delete', size: 'small', type: 'danger' }
    ]
  }
])

const holdingColumns = computed(() => [
  { prop: 'symbol', label: 'Symbol', minWidth: '110' },
  { prop: 'name', label: 'Name', minWidth: '180' },
  { prop: 'type', label: 'Type', minWidth: '90', type: 'custom' },
  { prop: 'quantity', label: 'Quantity', minWidth: '130', align: 'right', type: 'custom' },
  {
    prop: 'market_value_primary',
    label: 'Market Value',
    minWidth: '130',
    align: 'right',
    type: 'currency',
    decimalPlaces: 0,
    currency: currencyOptions.value
  },
  {
    prop: 'total_pnl_primary',
    label: 'P&L',
    minWidth: '120',
    align: 'right',
    type: 'pnl',
    decimalPlaces: 0,
    currency: currencyOptions.value
  },
  {
    prop: 'portfolio_count',
    label: 'Portfolios',
    minWidth: '90',
    align: 'right'
  }
])

const disabledDate = (time: Date): boolean => time.getTime() > Date.now()

const loadData = async () => {
  loading.value = true
  try {
    await Promise.all([
      portfolioStore.fetchPortfolios(),
      portfolioStore.fetchPortfolioSummary(asOfDate.value)
    ])
  } catch (error) {
    handleApiError(error, 'Failed to load portfolio summary')
  } finally {
    loading.value = false
  }
}

// --- Create / edit ---------------------------------------------------------

const dialogVisible = ref(false)
const saving = ref(false)
const editingPortfolioId = ref<number | null>(null)
const formRef = ref()
const form = reactive({
  name: '',
  description: ''
})
const formRules = {
  name: [{ required: true, message: 'Please enter a name', trigger: 'blur' }]
}

const openCreateDialog = () => {
  editingPortfolioId.value = null
  form.name = ''
  form.description = ''
  dialogVisible.value = true
}

const openEditDialog = (row: PortfolioSummaryItem) => {
  editingPortfolioId.value = row.id
  form.name = row.name
  form.description = row.description ?? ''
  dialogVisible.value = true
}

const savePortfolio = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    if (editingPortfolioId.value === null) {
      await portfolioStore.createPortfolio({
        name: form.name.trim(),
        description: form.description.trim() || null
      })
      showSuccess('Portfolio created')
    } else {
      await portfolioStore.updatePortfolio(editingPortfolioId.value, {
        name: form.name.trim(),
        description: form.description.trim() || null
      })
      showSuccess('Portfolio updated')
    }
    dialogVisible.value = false
    await loadData()
  } catch (error) {
    handleApiError(error, 'Failed to save portfolio')
  } finally {
    saving.value = false
  }
}

// --- Row actions -----------------------------------------------------------

const usePortfolio = (row: PortfolioSummaryItem) => {
  if (portfolioStore.currentPortfolioId === row.id) {
    showWarning('This portfolio is already selected')
    return
  }
  portfolioStore.selectPortfolioById(row.id)
  showSuccess(`Switched to ${row.name}`)
}

const deletePortfolio = async (row: PortfolioSummaryItem) => {
  if (portfolioStore.portfolios.length <= 1) {
    showError('The last portfolio cannot be deleted')
    return
  }

  try {
    await ElMessageBox.confirm(
      `Delete "${row.name}"? Its positions and transactions will be permanently removed.`,
      'Delete Portfolio',
      {
        type: 'warning',
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel'
      }
    )
  } catch {
    return
  }

  try {
    await portfolioStore.deletePortfolio(row.id)
    showSuccess('Portfolio deleted')
    await loadData()
  } catch (error) {
    handleApiError(error, 'Failed to delete portfolio')
  }
}

const handlePortfolioAction = (actionName: string, row: Record<string, any>) => {
  if (actionName === 'use') {
    usePortfolio(row as PortfolioSummaryItem)
  } else if (actionName === 'edit') {
    openEditDialog(row as PortfolioSummaryItem)
  } else if (actionName === 'delete') {
    deletePortfolio(row as PortfolioSummaryItem)
  }
}

// --- Lifecycle -------------------------------------------------------------

let activatedOnce = false

onMounted(() => {
  loadData()
})

onActivated(() => {
  if (activatedOnce) {
    loadData()
  } else {
    activatedOnce = true
  }
})
</script>

<style scoped>
.portfolios {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}

.portfolio-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #ffffff;
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.overview-cards {
  margin-bottom: 20px;
}

.table-card,
.chart-card {
  border: none;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.as-of-label {
  color: #909399;
  font-size: 12px;
  font-weight: 400;
}

.portfolio-name-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.portfolio-name-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.portfolio-name-text {
  font-weight: 600;
  color: #303133;
}

.portfolio-description {
  color: #909399;
  font-size: 12px;
}

.detail-row {
  margin-top: 4px;
}

.holdings-card {
  margin-bottom: 0;
}

@media (max-width: 1200px) {
  .detail-row :deep(.el-col) {
    width: 100%;
    max-width: 100%;
    flex: 0 0 100%;
  }
}
</style>
