<template>
  <div class="gold">
    <div class="page-header">
      <div class="title-row">
        <h2 class="page-title">Gold Trading</h2>
        <el-button :icon="Refresh" circle aria-label="Refresh" @click="handleRefresh" />
      </div>
      <div class="header-actions">
        <el-button
          type="primary"
          :icon="RefreshRight"
          :loading="goldStore.updatingPrices"
          @click="handleUpdatePrices"
        >
          Update Gold Prices
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!goldStore.hasGoldAssets"
      type="warning"
      :closable="false"
      title="No gold assets found. Run `python -m backend.init_data` to seed AU9999.SHG and 518880.SH."
      class="empty-alert"
    />

    <el-card class="filter-card">
      <el-form inline>
        <el-form-item label="Asset">
          <el-select v-model="selectedAssetId" style="width: 220px">
            <el-option
              v-for="asset in goldStore.assets"
              :key="asset.id"
              :label="`${asset.symbol} - ${asset.name}`"
              :value="asset.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Strategy">
          <el-select v-model="selectedStrategy" style="width: 300px">
            <el-option
              v-for="option in strategyOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Date Range">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="Start"
            end-placeholder="End"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="cards-row">
      <el-col :span="6">
        <OverviewCard
          title="Latest Signal"
          :value="latestSignalText"
          :subtitle="latestSignalSubtitle"
          :value-class="latestSignalClass"
          :loading="loading"
        />
      </el-col>
      <el-col :span="6">
        <OverviewCard
          title="Strategy Position"
          :value="modelPositionText"
          :subtitle="modelPositionSubtitle"
          :loading="loading"
        />
      </el-col>
      <el-col :span="6">
        <OverviewCard
          title="Your Gold Position"
          :value="userPositionText"
          :subtitle="userPositionSubtitle"
          :loading="loading"
        />
      </el-col>
      <el-col :span="6">
        <OverviewCard
          title="Your Total P&L"
          :value="formatCurrency(userPosition?.total_pnl)"
          :subtitle="userPnlSubtitle"
          :value-class="pnlClass"
          :loading="loading"
        />
      </el-col>
    </el-row>

    <el-card class="chart-card">
      <template #header>
        <div class="chart-header">
          <span class="chart-title">Normalized NAV Comparison (start = 100)</span>
          <span class="chart-subtitle">{{ strategyLabel }} · initial capital {{ formatCurrency(overview?.initial_capital) }}</span>
        </div>
      </template>
      <GoldPerformanceChart :performance="performance" />
    </el-card>

    <el-card class="chart-card">
      <template #header>
        <span class="chart-title">{{ currentAssetSymbol }} Price &amp; Strategy Signals</span>
      </template>
      <GoldSignalChart
        :series-dates="chartSeries.dates"
        :series="chartSeries.series"
        :signals="chartSeries.signals"
      />
    </el-card>

    <el-card class="table-card">
      <template #header>
        <div class="chart-header">
          <span class="chart-title">Performance Metrics</span>
          <span class="chart-subtitle">Sharpe uses Settings risk-free rate ({{ formatPercentage(performance?.risk_free_rate) }})</span>
        </div>
      </template>
      <el-table :data="metricRows" size="small" stripe>
        <el-table-column prop="label" label="Series" min-width="180" />
        <el-table-column label="Total Return" align="right" min-width="120">
          <template #default="{ row }">
            <span :class="row.total_return >= 0 ? 'positive' : 'negative'">{{ formatPercentage(row.total_return) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Annualized" align="right" min-width="110">
          <template #default="{ row }">{{ row.annualized_return === null ? 'N/A' : formatPercentage(row.annualized_return) }}</template>
        </el-table-column>
        <el-table-column label="Max Drawdown" align="right" min-width="120">
          <template #default="{ row }">{{ formatPercentage(row.max_drawdown) }}</template>
        </el-table-column>
        <el-table-column label="Volatility" align="right" min-width="100">
          <template #default="{ row }">{{ formatPercentage(row.volatility) }}</template>
        </el-table-column>
        <el-table-column label="Sharpe" align="right" min-width="90">
          <template #default="{ row }">{{ formatNumber(row.sharpe, 2) }}</template>
        </el-table-column>
        <el-table-column prop="trades" label="Trades" align="right" min-width="80" />
        <el-table-column label="Win Rate" align="right" min-width="90">
          <template #default="{ row }">{{ row.win_rate === null ? 'N/A' : formatPercentage(row.win_rate) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="table-card">
      <template #header>
        <div class="chart-header">
          <span class="chart-title">Signal History</span>
          <span class="chart-subtitle">{{ signalRows.length }} signals</span>
        </div>
      </template>
      <SharedDataTable :data="signalRows" :columns="signalColumns" :loading="loading" empty-text="No signals yet" />
    </el-card>

    <el-card class="table-card">
      <template #header>
        <div class="chart-header">
          <span class="chart-title">Your Gold Trades</span>
          <el-button type="primary" size="small" :icon="Plus" @click="openFillDialog()">Record Trade</el-button>
        </div>
      </template>
      <SharedDataTable
        :data="userTransactions"
        :columns="transactionColumns"
        :loading="loading"
        empty-text="No gold transactions recorded yet"
        @action="handleTransactionAction"
      />
    </el-card>

    <el-dialog v-model="showFillDialog" title="Record Gold Trade" width="520px">
      <el-form :model="fillForm" label-width="110px">
        <el-form-item label="Date">
          <el-date-picker v-model="fillForm.trade_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Action">
          <el-radio-group v-model="fillForm.action">
            <el-radio-button value="buy">Buy</el-radio-button>
            <el-radio-button value="sell">Sell</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="Quantity">
          <el-input-number v-model="fillForm.quantity" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Price">
          <el-input-number v-model="fillForm.price" :min="0" :precision="3" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Amount">
          <el-input-number v-model="fillForm.amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Fees">
          <el-input-number v-model="fillForm.fees" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Notes">
          <el-input v-model="fillForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFillDialog = false">Cancel</el-button>
        <el-button type="primary" @click="saveFill">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Gold' })
import dayjs from 'dayjs'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Plus, Refresh, RefreshRight } from '@element-plus/icons-vue'
import { useGoldStore, usePortfolioStore, useTransactionStore } from '../stores'
import { formatCurrency, formatNumber, formatPercentage, formatQuantity } from '../utils/formatters'
import { handleApiError, showSuccess, showWarning } from '../utils/errorHandler'
import OverviewCard from '../components/OverviewCard.vue'
import SharedDataTable from '../components/SharedDataTable.vue'
import GoldPerformanceChart from '../components/GoldPerformanceChart.vue'
import GoldSignalChart from '../components/GoldSignalChart.vue'
import type { GoldSignal, TransactionAction } from '../types/models'

const goldStore = useGoldStore()
const portfolioStore = usePortfolioStore()
const transactionStore = useTransactionStore()

const strategyOptions = [
  { value: 's1a_ma_cross_trailing', label: 's1a Dual-MA trend + ATR trailing stop (default)' },
  { value: 's3_bollinger_squeeze', label: 's3 Bollinger squeeze breakout' }
]

const selectedAssetId = ref<number | null>(null)
const selectedStrategy = ref('s1a_ma_cross_trailing')
const defaultStart = dayjs().subtract(1, 'year').format('YYYY-MM-DD')
const dateRange = ref<[string, string] | null>([defaultStart, dayjs().format('YYYY-MM-DD')])
const loading = ref(false)
const showFillDialog = ref(false)

const fillForm = reactive({
  trade_date: dayjs().format('YYYY-MM-DD'),
  action: 'buy' as 'buy' | 'sell',
  quantity: 0,
  price: 0,
  amount: 0,
  fees: 0,
  notes: ''
})

watch(
  () => [fillForm.quantity, fillForm.price],
  () => {
    fillForm.amount = Number(((fillForm.quantity || 0) * (fillForm.price || 0)).toFixed(2))
  }
)

const overview = computed(() => goldStore.overview)
const performance = computed(() => overview.value?.performance ?? null)
const signals = computed(() => overview.value?.signals ?? [])
const modelState = computed(() => overview.value?.model_state ?? null)
const userPosition = computed(() => overview.value?.user_position ?? null)
const strategyLabel = computed(() => overview.value?.strategy_label ?? '')
const currentAssetSymbol = computed(() => overview.value?.asset?.symbol ?? '')

const latestSignal = computed<GoldSignal | null>(() =>
  signals.value.length ? signals.value[signals.value.length - 1] : null
)

const latestSignalText = computed(() => {
  const signal = modelState.value?.pending_signal ?? latestSignal.value
  return signal ? signal.action.toUpperCase() : 'NONE'
})

const latestSignalSubtitle = computed(() => {
  const signal = modelState.value?.pending_signal ?? latestSignal.value
  if (!signal) return 'No signal on record'
  const prefix = modelState.value?.pending_signal ? 'Pending next open · ' : ''
  return `${prefix}${signal.signal_date} · ${signal.reason}`
})

const latestSignalClass = computed(() => {
  const signal = modelState.value?.pending_signal ?? latestSignal.value
  if (!signal) return 'neutral'
  return signal.action === 'buy' ? 'positive' : 'negative'
})

const modelPositionText = computed(() => {
  const size = modelState.value?.position_size ?? 0
  return size > 0 ? `${formatQuantity(size)} units` : 'Flat'
})

const modelPositionSubtitle = computed(() => {
  const state = modelState.value
  const capital = overview.value?.initial_capital
  const accountNote = capital ? `Model account ${formatCurrency(capital, null, 0)}` : ''
  if (!state || !state.position_size) {
    return accountNote ? `${accountNote} · waiting for entry` : 'Waiting for entry'
  }
  return accountNote
    ? `${accountNote} · Entry ${formatNumber(state.entry_price, 3)} · Stop ${formatNumber(state.stop_price, 3)}`
    : `Entry ${formatNumber(state.entry_price, 3)} · Stop ${formatNumber(state.stop_price, 3)}`
})

const userPositionText = computed(() =>
  userPosition.value ? `${formatQuantity(userPosition.value.quantity)} units` : '-'
)

const userPositionSubtitle = computed(() => {
  const position = userPosition.value
  if (!position) return 'No transactions'
  return `Avg cost ${formatNumber(position.average_cost, 3)} · MV ${formatCurrency(position.market_value)}`
})

const pnlClass = computed(() => {
  const pnl = userPosition.value?.total_pnl ?? 0
  if (pnl > 0) return 'positive'
  if (pnl < 0) return 'negative'
  return 'neutral'
})

const userPnlSubtitle = computed(() => {
  const position = userPosition.value
  if (!position) return ''
  return `Realized ${formatCurrency(position.realized_pnl)} · Unrealized ${formatCurrency(position.unrealized_pnl)}`
})

interface MetricRow {
  key: string
  label: string
  total_return: number
  annualized_return: number | null
  max_drawdown: number
  volatility: number
  sharpe: number
  trades: number
  win_rate: number | null
}

const metricRows = computed<MetricRow[]>(() => {
  const metrics = performance.value?.metrics
  if (!metrics) return []
  const labels: Record<string, string> = {
    user: 'User Gold Account',
    model: 'Strategy Model',
    benchmark: `Buy & Hold ${performance.value?.benchmark_symbol ?? ''}`
  }
  return ['user', 'model', 'benchmark']
    .filter((key) => metrics[key])
    .map((key) => {
      const metric = metrics[key]
      return {
        key,
        label: labels[key] ?? key,
        total_return: metric?.total_return ?? 0,
        annualized_return: metric?.annualized_return ?? null,
        max_drawdown: metric?.max_drawdown ?? 0,
        volatility: metric?.volatility ?? 0,
        sharpe: metric?.sharpe ?? 0,
        trades: metric?.trades ?? 0,
        win_rate: metric?.win_rate ?? null
      }
    })
})

const signalRows = computed(() => {
  const range = dateRange.value
  const list = range
    ? signals.value.filter(
        (signal) => signal.signal_date >= range[0] && signal.signal_date <= range[1]
      )
    : signals.value
  return [...list].slice().reverse()
})

const signalColumns = computed(() => [
  { prop: 'signal_date', label: 'Signal Date', minWidth: '120', sortable: true, type: 'date' },
  { prop: 'action', label: 'Action', minWidth: '90', type: 'tag', tagTypeMap: { buy: 'success', sell: 'danger' } },
  { prop: 'reason', label: 'Reason', minWidth: '220' },
  { prop: 'exec_date', label: 'Executed', minWidth: '120', type: 'date' },
  { prop: 'exec_price', label: 'Exec Price', minWidth: '110', align: 'right', type: 'currency' },
  { prop: 'size', label: 'Units', minWidth: '90', align: 'right', type: 'quantity' }
])

const transactionColumns = computed(() => [
  { prop: 'trade_date', label: 'Date', minWidth: '110', sortable: true, type: 'date' },
  { prop: 'action', label: 'Action', minWidth: '90', type: 'tag', tagTypeMap: { buy: 'success', sell: 'danger' } },
  { prop: 'quantity', label: 'Quantity', minWidth: '100', align: 'right', type: 'quantity' },
  { prop: 'price', label: 'Price', minWidth: '100', align: 'right', type: 'currency' },
  { prop: 'amount', label: 'Amount', minWidth: '120', align: 'right', type: 'currency', decimalPlaces: 0 },
  { prop: 'fees', label: 'Fees', minWidth: '90', align: 'right', type: 'currency' },
  { prop: 'notes', label: 'Notes', minWidth: '140' },
  {
    prop: 'actions',
    label: '',
    minWidth: '90',
    type: 'actions',
    actions: [{ name: 'delete', label: 'Delete', size: 'small', type: 'danger' }]
  }
])

const userTransactions = computed(() =>
  transactionStore.transactions.filter(
    (transaction) => transaction.asset_id === selectedAssetId.value
  )
)

const chartSeries = computed(() => {
  const data = overview.value
  if (!data) {
    return {
      dates: [] as string[],
      series: {} as Record<string, (number | null)[]>,
      signals: [] as GoldSignal[]
    }
  }
  const range = dateRange.value
  let indices = data.series_dates.map((_, index) => index)
  if (range) {
    indices = indices.filter(
      (index) => data.series_dates[index] >= range[0] && data.series_dates[index] <= range[1]
    )
  }
  const dates = indices.map((index) => data.series_dates[index])
  const series: Record<string, (number | null)[]> = {}
  for (const [key, values] of Object.entries(data.series)) {
    series[key] = indices.map((index) => values[index] ?? null)
  }
  const signalList = range
    ? data.signals.filter((signal) => signal.signal_date >= range[0] && signal.signal_date <= range[1])
    : data.signals
  return { dates, series, signals: signalList }
})

async function loadOverview() {
  const portfolioId = portfolioStore.currentPortfolio?.id
  const assetId = selectedAssetId.value
  if (!portfolioId || !assetId) return
  loading.value = true
  try {
    const range = dateRange.value
    await goldStore.fetchOverview({
      portfolio_id: portfolioId,
      asset_id: assetId,
      strategy: selectedStrategy.value,
      start_date: range?.[0],
      end_date: range?.[1]
    })
  } catch (error) {
    handleApiError(error, 'Failed to load gold overview')
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  const portfolioId = portfolioStore.currentPortfolio?.id
  if (portfolioId) {
    await transactionStore.fetchTransactions(portfolioId)
  }
  await loadOverview()
}

async function handleUpdatePrices() {
  try {
    const result = await goldStore.updatePrices()
    if (result.added > 0) {
      showSuccess(`Added ${result.added} new gold bars`)
    } else {
      showWarning('No new gold bars to add')
    }
    if (result.errors.length > 0) {
      showWarning(result.errors.join('; '))
    }
    await loadOverview()
  } catch (error) {
    handleApiError(error, 'Failed to update gold prices')
  }
}

function openFillDialog(signal?: GoldSignal) {
  const pending = modelState.value?.pending_signal
  const target = signal ?? (pending
    ? {
        signal_date: pending.signal_date,
        action: pending.action,
        reason: pending.reason,
        exec_date: null,
        exec_price: null
      }
    : null)
  fillForm.trade_date = target?.exec_date ?? dayjs().format('YYYY-MM-DD')
  fillForm.action = (target?.action as 'buy' | 'sell') ?? 'buy'
  fillForm.quantity = 0
  fillForm.price = target?.exec_price ?? userPosition.value?.latest_price ?? 0
  fillForm.amount = 0
  fillForm.fees = 0
  fillForm.notes = target ? `Signal: ${target.reason}` : ''
  showFillDialog.value = true
}

async function saveFill() {
  const portfolioId = portfolioStore.currentPortfolio?.id
  const asset = overview.value?.asset
  if (!portfolioId || !asset) return
  if (!fillForm.quantity || !fillForm.price || !fillForm.amount) {
    showWarning('Quantity, price and amount are required')
    return
  }
  try {
    await transactionStore.createTransaction({
      portfolio_id: portfolioId,
      asset_id: asset.id,
      trade_date: fillForm.trade_date,
      action: fillForm.action as TransactionAction,
      quantity: fillForm.quantity,
      price: fillForm.price,
      amount: fillForm.amount,
      fees: fillForm.fees,
      currency_id: asset.currency_id,
      notes: fillForm.notes
    })
    showFillDialog.value = false
    await portfolioStore.recalculatePositions({ portfolioId, asOfDate: null })
    await Promise.all([transactionStore.fetchTransactions(portfolioId), loadOverview()])
    showSuccess('Gold trade recorded')
  } catch (error) {
    handleApiError(error, 'Failed to record gold trade')
  }
}

async function handleTransactionAction(actionName: string, row: Record<string, any>) {
  if (actionName !== 'delete') return
  const portfolioId = portfolioStore.currentPortfolio?.id
  if (!portfolioId) return
  try {
    await ElMessageBox.confirm(
      'Delete this transaction and recalculate positions?',
      'Confirm Delete',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await transactionStore.deleteTransaction(row.id)
    await portfolioStore.recalculatePositions({ portfolioId, asOfDate: null })
    await Promise.all([transactionStore.fetchTransactions(portfolioId), loadOverview()])
    showSuccess('Transaction deleted')
  } catch (error) {
    handleApiError(error, 'Failed to delete transaction')
  }
}

watch([selectedAssetId, selectedStrategy, dateRange], () => {
  loadOverview()
})

onMounted(async () => {
  try {
    await portfolioStore.fetchPortfolios()
    await goldStore.fetchAssets()
    if (!selectedAssetId.value && goldStore.assets.length > 0) {
      selectedAssetId.value = goldStore.assets[0].id
    }
    const portfolioId = portfolioStore.currentPortfolio?.id
    if (portfolioId) {
      await transactionStore.fetchTransactions(portfolioId)
    }
    await loadOverview()
  } catch (error) {
    handleApiError(error, 'Failed to initialize gold page')
  }
})
</script>

<style scoped>
.gold {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.empty-alert {
  margin-bottom: 16px;
}

.filter-card {
  margin-bottom: 16px;
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08);
}

.filter-card :deep(.el-card__body) {
  padding-bottom: 0;
}

.cards-row {
  margin-bottom: 16px;
}

.chart-card {
  margin-bottom: 16px;
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08);
}

.table-card {
  margin-bottom: 16px;
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08);
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.chart-subtitle {
  font-size: 12px;
  color: #909399;
}

.positive {
  color: #67c23a;
  font-weight: 500;
}

.negative {
  color: #f56c6c;
  font-weight: 500;
}
</style>
