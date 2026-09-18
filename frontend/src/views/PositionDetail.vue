<template>
  <div class="position-detail">
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="goBack" plain>Back</el-button>
        <h2 v-if="asset" class="page-title">
          {{ asset.symbol }}
          <span class="asset-name">{{ asset.name }}</span>
        </h2>
        <h2 v-else class="page-title">Position Detail</h2>
        <el-button :icon="Refresh" @click="handleRefresh" circle aria-label="Refresh" />
      </div>
    </div>

    <!-- Position Summary -->
    <el-card v-if="position" class="summary-card-section">
      <div class="position-summary">
        <el-row :gutter="20">
          <el-col :span="6">
            <div class="summary-card">
              <div class="summary-label">Quantity</div>
              <div class="summary-value">{{ formatQuantity(position.quantity ?? 0) }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card">
              <div class="summary-label">Average Cost</div>
              <div class="summary-value">
                {{ formatCurrency(position.average_cost ?? null, position.currency ?? null) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card">
              <div class="summary-label">Current Price</div>
              <div class="summary-value">
                {{ formatCurrency(position.current_price ?? 0, position.currency ?? null) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card">
              <div class="summary-label">Market Value</div>
              <div class="summary-value">
                {{ formatCurrency(position.market_value, position.currency ?? null, 0) }}
              </div>
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20" style="margin-top: 16px;">
          <el-col :span="6">
            <div class="summary-card">
              <div class="summary-label">
                <span :class="getPnlClass(position.total_pnl)">
                  {{ getPnlIcon(position.total_pnl) }}
                </span>
                Total P&L
              </div>
              <div class="summary-value" :class="getPnlClass(position.total_pnl)">
                {{ formatCurrency(position.total_pnl, position.currency ?? null, 0) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card">
              <div class="summary-label">
                <span :class="getPnlClass(pnlPercent)">
                  {{ getPnlIcon(pnlPercent) }}
                </span>
                P&L %
              </div>
              <div class="summary-value" :class="getPnlClass(pnlPercent)">
                {{ formatPercentage(pnlPercent) }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card">
              <div class="summary-label">Position Date</div>
              <div class="summary-value">{{ formatDate(position.position_date) }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-card">
              <div class="summary-label">Currency</div>
              <div class="summary-value">{{ position.currency?.code || 'N/A' }}</div>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <!-- Transactions Table -->
    <div class="transactions-section">
      <div class="transactions-header">
        <h3 class="transactions-title">All Transactions</h3>
      </div>
      <SharedDataTable :data="assetTransactions" :columns="tableColumns" :loading="loading"
        :empty-text="'No transactions found for this position'" class="transactions-table" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'PositionDetail' })
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { usePortfolioStore, useTransactionStore, useAssetStore, useUIStore } from '../stores'
import SharedDataTable from '../components/SharedDataTable.vue'
import { formatCurrency, formatDate, formatQuantity, formatPercentage } from '../utils/formatters'
import { handleApiError } from '../utils/errorHandler'

const route = useRoute()
const router = useRouter()

// Stores
const portfolioStore = usePortfolioStore()
const transactionStore = useTransactionStore()
const assetStore = useAssetStore()
const uiStore = useUIStore()

// Get asset id from route params
const assetId = computed<number>(() => {
  const id = route.params.assetId
  return parseInt(Array.isArray(id) ? id[0] : id)
})

// Computed properties from stores
const loading = computed(() => uiStore.loading)
const currentPortfolio = computed(() => portfolioStore.currentPortfolio)
const positions = computed(() => portfolioStore.positions)

// Find the asset for this position
const asset = computed(() => {
  if (!assetId.value) return null
  return assetStore.assets.find((a: { id: number }) => a.id === assetId.value) || null
})

// Find the position for this asset
const position = computed(() => {
  if (!assetId.value) return null
  return positions.value.find((p: { asset_id: number }) => p.asset_id === assetId.value) || null
})

// P&L percentage = Total P&L / Market Value
const pnlPercent = computed(() => {
  if (!position.value) return 0
  const marketValue: number = position.value.market_value || 0
  const totalPnl: number = position.value.total_pnl || 0
  return marketValue > 0 ? totalPnl / marketValue : 0
})

// Filter transactions for this specific asset
const assetTransactions = computed(() => {
  if (!assetId.value) return []
  return transactionStore.transactions
    .filter((t: { asset_id: number }) => t.asset_id === assetId.value)
    .sort((a: { trade_date: string }, b: { trade_date: string }) => new Date(b.trade_date).getTime() - new Date(a.trade_date).getTime())
})

// Tag type mapping for action column
const actionTagTypeMap = {
  'buy': 'success',
  'sell': 'danger',
  'dividends': 'info',
  'cash_in': 'success',
  'cash_out': 'warning',
  'interest': 'info',
  'split': 'warning',
  'tax': 'warning'
}

// Table columns for transactions table
const tableColumns = computed(() => [
  { prop: 'trade_date', label: 'Date', minWidth: '120', sortable: true, type: 'date' },
  { prop: 'action', label: 'Action', minWidth: '100', type: 'tag', tagTypeMap: actionTagTypeMap },
  { prop: 'quantity', label: 'Quantity', minWidth: '120', align: 'right', type: 'quantity' },
  { prop: 'price', label: 'Price', minWidth: '120', align: 'right', type: 'currency' },
  { prop: 'amount', label: 'Amount', minWidth: '120', align: 'right', type: 'currency', decimalPlaces: 0 },
  { prop: 'fees', label: 'Fees', minWidth: '100', align: 'right', type: 'currency' },
  { prop: 'notes', label: 'Notes', minWidth: '180' }
])

// Helper functions for P&L
const getPnlClass = (value: number | null | undefined): string => {
  if (value == null || value === 0) return ''
  return value > 0 ? 'positive' : 'negative'
}

const getPnlIcon = (value: number | null | undefined): string => {
  if (value == null || value === 0) return '▶'
  return value > 0 ? '▲' : '▼'
}

const goBack = () => {
  router.push({ name: 'Portfolio' })
}

const handleRefresh = () => {
  initialize()
}

// Initialize data
const initialize = async () => {
  try {
    if (!currentPortfolio.value) {
      await portfolioStore.fetchPortfolios()
    }

    const portfolioId = currentPortfolio.value?.id
    if (!portfolioId) return

    const tasks = []
    if (assetStore.assets.length === 0) {
      tasks.push(assetStore.fetchAssets())
    }
    if (positions.value.length === 0) {
      tasks.push(portfolioStore.fetchPositions(portfolioId))
    }
    tasks.push(transactionStore.fetchTransactions(portfolioId))

    await Promise.all(tasks)
  } catch (error) {
    handleApiError(error, 'Failed to load position detail')
  }
}

onMounted(() => {
  initialize()
})
</script>

<style scoped>
.position-detail {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  margin: 0;
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.asset-name {
  font-size: 16px;
  font-weight: 400;
  color: #909399;
}

.summary-card-section {
  margin-bottom: 20px;
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.position-summary {
  padding: 10px;
}

.summary-card {
  text-align: center;
  padding: 16px 8px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.summary-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.summary-value {
  font-size: 22px;
  font-weight: bold;
  color: #303133;
}

.summary-value.positive {
  color: #67c23a;
}

.summary-value.negative {
  color: #f56c6c;
}

.summary-label .positive {
  color: #67c23a;
  margin-right: 4px;
}

.summary-label .negative {
  color: #f56c6c;
  margin-right: 4px;
}

.transactions-section {
  background: #ffffff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.transactions-header {
  padding: 20px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.transactions-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 10px;
  letter-spacing: 0.5px;
}

.transactions-title::before {
  content: '';
  width: 4px;
  height: 20px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 2px;
}

.positive {
  color: #67c23a;
  font-weight: 500;
}

.negative {
  color: #f56c6c;
  font-weight: 500;
}

/* Responsive design */
@media (max-width: 1023px) {
  .position-summary .el-col {
    margin-bottom: 16px;
  }

  .summary-value {
    font-size: 18px;
  }
}

@media (max-width: 767px) {
  .header-left {
    flex-wrap: wrap;
    gap: 10px;
  }

  .header-left h2 {
    font-size: 18px;
  }

  .asset-name {
    font-size: 14px;
  }

  .summary-card {
    padding: 12px 4px;
  }

  .summary-label {
    font-size: 12px;
  }

  .summary-value {
    font-size: 16px;
  }

  .transactions-header {
    padding: 14px 16px;
  }

  .transactions-title {
    font-size: 15px;
  }
}
</style>
