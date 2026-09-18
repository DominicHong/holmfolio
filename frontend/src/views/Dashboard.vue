<template>
  <div class="dashboard">
    <div class="page-header">
      <div class="title-row">
        <h2 class="page-title">Dashboard</h2>
        <el-button :icon="Refresh" @click="handleRefresh" circle aria-label="Refresh" />
      </div>

      <!-- Date Range Controls -->
      <div class="date-controls-top">
        <div class="date-range-label">From:</div>
        <el-date-picker
          v-model="startDate"
          type="date"
          placeholder="Start date"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="onDateRangeChange"
        />
        <div class="date-range-label">To:</div>
        <el-date-picker
          v-model="endDate"
          type="date"
          placeholder="End date"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="onDateRangeChange"
        />
        <el-button-group>
          <el-button :type="timeRange === 30 ? 'primary' : 'default'" @click="setTimeRange(30)">1M</el-button>
          <el-button :type="timeRange === 90 ? 'primary' : 'default'" @click="setTimeRange(90)">3M</el-button>
          <el-button :type="timeRange === 180 ? 'primary' : 'default'" @click="setTimeRange(180)">6M</el-button>
          <el-button :type="timeRange === 365 ? 'primary' : 'default'" @click="setTimeRange(365)">1Y</el-button>
          <el-button :type="timeRange === 0 ? 'primary' : 'default'" @click="setTimeRange(0)">ALL</el-button>
        </el-button-group>
      </div>
    </div>

    <!-- Portfolio Overview Cards -->
    <el-row :gutter="20" class="overview-cards">
      <el-col :span="6">
        <OverviewCard
          title="Total Value"
          :value="formatCurrency(totalPortfolioValue, { symbol: primaryCurrency?.symbol || '¥' }, 0)"
          :subtitle="formatPercentage(totalReturn, 2)"
          value-class="positive"
          :loading="loadingStates.overview"
        />
      </el-col>

      <el-col :span="6">
        <OverviewCard
          title="Market Value"
          :value="formatCurrency(marketValueChange, { symbol: primaryCurrency?.symbol || '¥' }, 0)"
          :subtitle="`Today: ${formatCurrency(todayChange, { symbol: primaryCurrency?.symbol || '¥' })}`"
          :value-class="marketValueChange >= 0 ? 'positive' : 'negative'"
          :loading="loadingStates.overview"
        >
          <template #title-prefix>
            <span
              :class="{ 'positive': marketValueChange > 0, 'negative': marketValueChange < 0, 'neutral': marketValueChange === 0 }"
            >
              {{ marketValueChange > 0 ? '▲' : marketValueChange < 0 ? '▼' : '▶' }}
            </span>
          </template>
        </OverviewCard>
      </el-col>

      <el-col :span="6">
        <OverviewCard
          title="NAV"
          :value="formatNumber(analyticsStore.portfolioStats?.ending_nav, 4)"
          subtitle="Net Asset Value"
          :loading="loadingStates.overview"
        />
      </el-col>

      <el-col :span="6">
        <OverviewCard
          title="Performance"
          :value="formatPercentage(annualizedReturn, 2)"
          subtitle="Annualized"
          :loading="loadingStates.overview"
        />
      </el-col>
    </el-row>

    <!-- Charts and Tables Row -->
    <el-row :gutter="20" class="charts-row">
      <el-col :span="18">
        <el-card class="chart-card performance-chart-card">
          <template #header>
            <div class="card-header">
              <span>Portfolio Performance</span>

            </div>
          </template>

          <!-- Portfolio Performance Chart -->
          <div v-if="loadingStates.performanceChart" class="loading-message">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <span>Loading performance data...</span>
          </div>
          <div v-else-if="performanceHistory && performanceHistory.length > 0">
            <PerformanceChart
              :performance-history="performanceHistory"
              :currency-symbol="primaryCurrency?.symbol || '¥'"
            />
          </div>
          <div v-else class="no-data-message">
            <el-empty description="No performance history data available" :image-size="100"></el-empty>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="chart-card allocation-chart-card">
          <template #header>
            <div class="card-header">
              <span>Asset Allocation</span>
              <el-select
                v-model="selectedAllocationCategory"
                placeholder="Select category"
                size="small"
                style="width: 150px"
                clearable
                aria-label="Allocation category"
                @change="onAllocationCategoryChange"
              >
                <el-option label="Asset Type" value="" />
                <el-option
                  v-for="category in tagCategories"
                  :key="category.id"
                  :label="category.name"
                  :value="category.id"
                />
              </el-select>
            </div>
          </template>
          <div v-if="loadingStates.allocationChart" class="loading-message">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <span>Loading allocation data...</span>
          </div>
          <AllocationChart v-else :asset-allocation="assetAllocation" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Positions and Transactions Row -->
    <el-row :gutter="20" class="tables-row">
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Top Positions</span>
              <el-button link @click="$router.push('/portfolio')">View All</el-button>
            </div>
          </template>

          <div v-if="loadingStates.positions" class="loading-message">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <span>Loading positions data...</span>
          </div>
          <SharedDataTable
            v-else
            :data="topPositions"
            :columns="topPositionsColumns"
            :loading="false"
          />
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Recent Transactions</span>
              <el-button link @click="$router.push('/transactions')">View All</el-button>
            </div>
          </template>

          <div v-if="loadingStates.transactions" class="loading-message">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <span>Loading transactions data...</span>
          </div>
          <SharedDataTable
            v-else
            :data="recentTransactions"
            :columns="recentTransactionsColumns"
            :loading="false"
          >
            <template #symbol="{ row }">
              {{ getAssetSymbol(row.asset_id) }}
            </template>
          </SharedDataTable>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Dashboard' })
import { ref, computed, watch, onMounted } from 'vue'
import { usePortfolioStore } from '../stores'
import { useAnalyticsStore } from '../stores'
import { useReferenceStore } from '../stores'
import { useAssetStore } from '../stores'
import { useTransactionStore } from '../stores'
import { formatCurrency, formatPercentage, formatNumber } from '../utils/formatters'
import AllocationChart from '../components/AllocationChart.vue'
import PerformanceChart from '../components/PerformanceChart.vue'
import SharedDataTable from '../components/SharedDataTable.vue'
import OverviewCard from '../components/OverviewCard.vue'
import { useTimeRange } from '../composables/useTimeRange'
import { useLoading } from '../composables/useLoading'
import { handleApiError } from '../utils/errorHandler'
import { Refresh } from '@element-plus/icons-vue'

// Stores
const portfolioStore = usePortfolioStore()
const analyticsStore = useAnalyticsStore()
const referenceStore = useReferenceStore()
const assetStore = useAssetStore()
const transactionStore = useTransactionStore()

// Asset allocation category selection
const selectedAllocationCategory = ref<number | string>('')
const tagCategories = computed(() => referenceStore.tagCategories)

// Independent loading states for each section
const { loadingStates, withLoading } = useLoading([
  'overview',
  'performanceChart',
  'allocationChart',
  'positions',
  'transactions'
])

// Time range composable
const {
  startDate,
  endDate,
  timeRange,
  setTimeRange,
  onDateRangeChange,
  initialize: initializeTimeRange
} = useTimeRange({
  transactions: () => transactionStore.transactions,
  onChange: async (start, end) => {
    const portfolioId = currentPortfolio.value?.id
    if (!portfolioId) {
      console.warn('No portfolio selected')
      return
    }
    try {
      console.log('Fetching data for date range:', start, 'to', end)
      await fetchAllData(portfolioId)
    } catch (error) {
      handleApiError(error, 'Failed to load dashboard data')
    }
  }
})

// Computed properties from stores
const positions = computed(() => portfolioStore.positions)
const currentPortfolio = computed(() => portfolioStore.currentPortfolio)
const assetAllocation = computed(() => analyticsStore.assetAllocation)
const performanceHistory = computed(() => analyticsStore.performanceHistory)
const recentTransactions = computed(() =>
  (transactionStore.recentTransactions || []).slice(0, 10)
)
const primaryCurrency = computed(() => referenceStore.primaryCurrency)

// Derived computed properties
const totalPortfolioValue = computed(() => {
  const history = performanceHistory.value || []
  if (history.length === 0) return 0
  return history[history.length - 1]?.value || 0
})
const marketValueChange = computed(() => {
  const history = analyticsStore.performanceHistory || []
  if (history.length === 0) return 0
  const beginning = history[0]?.value || 0
  const ending = history[history.length - 1]?.value || 0
  return ending - beginning
})
const todayChange = computed(() => 0) // Placeholder for future implementation
const totalReturn = computed(() => analyticsStore.portfolioStats?.time_weighted_return || 0)
const annualizedReturn = computed(() => analyticsStore.portfolioStats?.annualized_return || 0)

const topPositions = computed(() =>
  positions.value
    .filter((position: { asset_id: number; [key: string]: any }) => {
      const asset = assetStore.assets.find((a: { id: number; type: string }) => a.id === position.asset_id)
      return asset && asset.type !== 'cash'
    })
    .sort((a: { market_value_primary?: number }, b: { market_value_primary?: number }) => (b.market_value_primary || 0) - (a.market_value_primary || 0))
    .slice(0, 10)
)

// Define table columns for Top Positions
const topPositionsColumns = computed(() => [
  { prop: 'symbol', label: 'Symbol' },
  { prop: 'name', label: 'Name' },
  { prop: 'quantity', label: 'Quantity', align: 'right', type: 'quantity' },
  { prop: 'current_price', label: 'Price', align: 'right', type: 'currency' },
  { prop: 'market_value_primary', label: 'Market Value', align: 'right', type: 'currency', decimalPlaces: 0, currency: { symbol: referenceStore.primaryCurrency?.symbol || '¥' } },
  { prop: 'total_pnl_primary', label: 'P&L', align: 'right', type: 'pnl', decimalPlaces: 0, currency: { symbol: referenceStore.primaryCurrency?.symbol || '¥' } }
])

// Define table columns for Recent Transactions
const recentTransactionsColumns = computed(() => [
  { prop: 'trade_date', label: 'Date', type: 'date' },
  { prop: 'action', label: 'Action', type: 'tag', tagTypeMap: {
      'buy': 'success',
      'sell': 'danger',
      'dividends': 'info',
      'cash_in': 'success',
      'cash_out': 'warning'
    } 
  },
  { prop: 'symbol', label: 'Symbol', type: 'custom' },
  { prop: 'amount', label: 'Amount', align: 'right', type: 'currency' }
])

// Methods
const getAssetSymbol = (assetId: number | null): string => {
  if (!assetId || !assetStore.assets) return 'N/A'
  const asset = assetStore.assets.find((a: { id: number; symbol: string }) => a.id === assetId)
  return asset ? asset.symbol : 'Unknown'
}

// Load overview data (Total Value, Total P&L, NAV, Performance)
const loadOverviewData = async (portfolioId: number) => {
  await withLoading('overview', async () => {
    await analyticsStore.fetchPerformanceMetrics(portfolioId, { startDate: startDate.value, endDate: endDate.value })
  })
}

// Load performance chart data
const loadPerformanceChartData = async (portfolioId: number) => {
  await withLoading('performanceChart', async () => {
    await analyticsStore.fetchPerformanceHistory(portfolioId, { startDate: startDate.value, endDate: endDate.value })
  })
}

// Load allocation chart data
const loadAllocationChartData = async (portfolioId: number) => {
  await withLoading('allocationChart', async () => {
    const options: { by: string; tagCategoryId?: number | string } = { by: 'type' }
    if (selectedAllocationCategory.value) {
      options.by = 'tag'
      options.tagCategoryId = selectedAllocationCategory.value
    }
    await analyticsStore.fetchAssetAllocation(portfolioId, endDate.value, options)
  })
}

// Handle allocation category change
const onAllocationCategoryChange = () => {
  const portfolioId = currentPortfolio.value?.id
  if (portfolioId) {
    loadAllocationChartData(portfolioId)
  }
}

// Load positions data
const loadPositionsData = async (portfolioId: number) => {
  await withLoading('positions', async () => {
    await Promise.all([
      portfolioStore.fetchPositions(portfolioId, endDate.value),
      assetStore.fetchAssets()
    ])
  })
}

// Load transactions data
const loadTransactionsData = async (portfolioId: number) => {
  await withLoading('transactions', async () => {
    await transactionStore.fetchTransactions(portfolioId)
  })
}

// Fetch all data with concurrent loading
const fetchAllData = async (portfolioId: number) => {
  const results = await Promise.allSettled([
    loadPerformanceChartData(portfolioId),
    loadOverviewData(portfolioId),
    loadAllocationChartData(portfolioId),
    loadPositionsData(portfolioId),
    loadTransactionsData(portfolioId),
  ])

  // Report individual failures without blocking other sections
  results.forEach((r) => {
    if (r.status === 'rejected') {
      handleApiError(r.reason, 'Failed to load dashboard data')
    }
  })
}

// Initialize dashboard with progressive loading
const initializeDashboard = async () => {
  try {
    await portfolioStore.fetchPortfolios()
    if (currentPortfolio.value) {
      const portfolioId = currentPortfolio.value.id

      // Initialize time range with default values
      initializeTimeRange()

      // Load tag categories first and set default category
      await referenceStore.fetchTagCategories()
      if (tagCategories.value && tagCategories.value.length > 0) {
        const defaultCategory = tagCategories.value.find((c: { name: string; id: number }) => c.name === '自定义类别')
        if (defaultCategory) {
          selectedAllocationCategory.value = defaultCategory.id
        }
      }

      // Fetch all card data independently
      await fetchAllData(portfolioId)
    }
  } catch (error) {
    handleApiError(error, 'Failed to initialize dashboard')
  }
}



// Watchers
watch(() => portfolioStore.currentPortfolio, (newPortfolio, oldPortfolio) => {
  // Ignore initial assignment when oldPortfolio is undefined
  if (oldPortfolio && (newPortfolio?.id !== oldPortfolio.id)) {
    initializeDashboard()
  }
})

// Refresh
const handleRefresh = () => {
  initializeDashboard()
}

// Lifecycle
onMounted(async () => {
  await initializeDashboard()
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 24px;
}

.date-controls-top {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.date-range-label {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.overview-cards {
  margin-bottom: 24px;
}

.charts-row {
  margin-bottom: 24px;
  align-items: stretch;
}

.charts-row :deep(.el-col) {
  display: flex;
}

.charts-row :deep(.el-col > .el-card) {
  flex: 1;
}

.chart-card {
  border: none;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.chart-card :deep(.el-card__header) {
  display: flex;
  align-items: center;
  height: 42px;
  padding: 0 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-bottom: 1px solid #e6e6e6;
}

.chart-card :deep(.el-card__body) {
  padding: 20px;
}

.performance-chart-card :deep(.el-card__body) {
  min-height: 520px;
}

.performance-chart-card :deep(.chart-container) {
  height: 500px;
}

.allocation-chart-card :deep(.el-card__body) {
  min-height: 520px;
  display: flex;
  flex-direction: column;
}

.allocation-chart-card :deep(.allocation-chart-wrapper) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.no-data-message {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
}

.loading-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
  gap: 12px;
  color: #909399;
}

.loading-message .el-icon {
  color: #409EFF;
}

.tables-row {
  margin-bottom: 24px;
}

.tables-row :deep(.el-card) {
  border: none;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.tables-row :deep(.el-card__header) {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-bottom: 1px solid #e6e6e6;
  padding: 16px 20px;
}

.tables-row :deep(.el-card__body) {
  padding: 20px;
}

.el-table {
  --el-table-border-color: #f0f2f5;
  --el-table-header-bg-color: #fafbfc;
  --el-table-row-hover-bg-color: #f5f7fa;
  --el-table-text-color: #606266;
  --el-table-header-text-color: #303133;
  border-radius: 8px;
  overflow: hidden;
}

.el-table :deep(.el-table__header-wrapper) {
  border-radius: 8px 8px 0 0;
}

.el-table :deep(.el-table__header th) {
  font-weight: 600;
  color: #303133;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
  padding: 16px 0;
  font-size: 13px;
  letter-spacing: 0.3px;
  border-bottom: 2px solid #e4e7ed;
}

.el-table :deep(.el-table__body td) {
  font-size: 14px;
  border-bottom: 1px solid #f0f2f5;
}

.el-table :deep(.el-table__row) {
  transition: all 0.2s ease;
}

.el-table :deep(.el-table__row:hover) {
  background-color: #f5f7fa;
}

.el-table :deep(.el-table__row:hover td) {
  background-color: transparent;
}

.allocation-details {
  margin-top: 15px;
}

.allocation-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  font-size: 13px;
  border-bottom: 1px solid #f0f0f0;
}

.allocation-item:last-child {
  border-bottom: none;
}

.allocation-label {
  color: #606266;
  font-weight: 500;
}

.allocation-value {
  color: #303133;
  font-weight: 600;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin: 0;
}

:deep(.el-button) {
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.2s ease;
}

:deep(.el-button:hover) {
  transform: translateY(-1px);
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s ease;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2), 0 4px 12px rgba(64, 158, 255, 0.15);
}
</style>
