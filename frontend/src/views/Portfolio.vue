<template>
  <div class="portfolio">
    <div class="page-header">
      <div class="title-row">
        <h2 class="page-title">Portfolio Positions</h2>
        <el-button :icon="Refresh" @click="handleRefresh" circle aria-label="Refresh" />
      </div>
      <div class="position-controls">
        <el-tooltip content="Select the date for viewing positions, or as the end date when recalculating positions for every day from the first transaction" placement="top">
          <div>
            <el-date-picker
              v-model="recalculateDate"
              type="date"
              placeholder="Select date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              :disabled-date="disabledDate"
              style="margin-right: 10px;"
            />
          </div>
        </el-tooltip>
        <el-button type="success" @click="handleShowPositions" :loading="loading" size="default"
          style="margin-right: 10px;">
          Show Positions
        </el-button>
        <el-tooltip content="Recalculate positions for every day from the first transaction date up to the selected date and replace existing records in the database" placement="top">
          <el-button type="primary" @click="handleRecalculate" :loading="loading" size="default">
            Recalculate Positions
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <div v-if="positions.length === 0 && !loading" class="empty-state-card">
      <div class="empty-state">
        <p>No positions found. Your portfolio appears to be empty.</p>
        <p>If you have transactions, click "Recalculate Positions" to generate positions from your transactions.</p>
      </div>
    </div>

    <template v-else>
      <!-- Portfolio Summary -->
      <div v-if="positions.length > 0" class="portfolio-summary">
        <el-row :gutter="20" class="overview-cards">
          <el-col :span="6">
            <OverviewCard
              title="Total Market Value"
              :value="formatCurrency(totalPortfolioMarketValue, { symbol: primaryCurrency?.symbol || '¥' }, 0)"
            />
          </el-col>
          <el-col :span="6">
            <OverviewCard
              title="Total P&L"
              :value="formatCurrency(totalPnlPrimary, { symbol: primaryCurrency?.symbol || '¥' }, 0)"
              :value-class="totalPnlPrimary >= 0 ? 'positive' : 'negative'"
            >
              <template #title-prefix>
                <span
                  :class="{ 'positive': totalPnlPrimary > 0, 'negative': totalPnlPrimary < 0, 'neutral': totalPnlPrimary === 0 }"
                >
                  {{ totalPnlPrimary > 0 ? '▲' : totalPnlPrimary < 0 ? '▼' : '▶' }}
                </span>
              </template>
            </OverviewCard>
          </el-col>
          <el-col :span="6">
            <OverviewCard
              title="Dividends"
              :value="formatCurrency(totalDividendsPrimary, { symbol: primaryCurrency?.symbol || '¥' }, 0)"
            />
          </el-col>
          <el-col :span="6">
            <OverviewCard
              title="Positions"
              :value="positionCount"
            />
          </el-col>
        </el-row>
      </div>

      <!-- All Positions Summary Table -->
      <div v-if="allPositionsSorted.length > 0" class="summary-table-section">
        <div class="summary-table-header">
          <h3 class="summary-table-title">All Positions</h3>
          <el-button type="primary" @click="downloadPositionsCSV(allPositionsSorted, 'ALL', true)"
            class="download-btn">
            Download
          </el-button>
        </div>
        <SharedDataTable :data="allPositionsSorted" :columns="summaryTableColumns" :loading="loading"
          :empty-text="'No positions found'" class="summary-table" :show-summary="true"
          :summary-method="(p: any) => getAllPositionsSummaryRow(p)">
          <template #symbol="{ row }">
            <router-link :to="{ name: 'PositionDetail', params: { assetId: row.asset_id } }" class="symbol-link">
              {{ row.symbol }}
            </router-link>
          </template>
        </SharedDataTable>
      </div>

      <!-- History Positions (collapsed by default) -->
      <div v-if="historyPositionsSorted.length > 0" class="history-table-section">
        <el-collapse v-model="historyCollapseActive" class="history-collapse">
          <el-collapse-item name="history">
            <template #title>
              <div class="history-collapse-title">
                <h3 class="summary-table-title history-title">History Positions</h3>
                <el-tag size="small" type="info" effect="plain" class="history-count-tag">
                  {{ historyPositionsSorted.length }}
                </el-tag>
              </div>
            </template>
            <div class="history-content">
              <div class="history-download-bar">
                <el-button type="primary" size="small"
                  @click.stop="downloadPositionsCSV(historyPositionsSorted, 'HISTORY', true)">
                  Download
                </el-button>
              </div>
              <SharedDataTable :data="historyPositionsSorted" :columns="historyTableColumns" :loading="loading"
                :empty-text="'No history positions'" class="summary-table history-table" :show-summary="true"
                :summary-method="(p: any) => getHistorySummaryRow(p)">
                <template #symbol="{ row }">
                  <router-link :to="{ name: 'PositionDetail', params: { assetId: row.asset_id } }"
                    class="symbol-link">
                    {{ row.symbol }}
                  </router-link>
                </template>
              </SharedDataTable>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- Currency Grouped Tables -->
      <div v-for="currencyGroup in groupedPositions" :key="currencyGroup.currencyCode"
        class="currency-table-section">
        <div class="currency-table-header">
          <h3 class="currency-table-title">Positions in {{ currencyGroup.currencyCode }}</h3>
          <el-button type="primary" @click="downloadPositionsCSV(currencyGroup.positions, currencyGroup.currencyCode)"
            class="download-btn">
            Download
          </el-button>
        </div>

        <SharedDataTable :data="currencyGroup.positions" :columns="tableColumns" :loading="loading"
          :empty-text="'No positions found in ' + currencyGroup.currencyCode" class="currency-table"
          :show-summary="true" :summary-method="(p: any) => getSummaryRow(p, currencyGroup)">
          <template #symbol="{ row }">
            <router-link :to="{ name: 'PositionDetail', params: { assetId: row.asset_id } }" class="symbol-link">
              {{ row.symbol }}
            </router-link>
          </template>
        </SharedDataTable>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Portfolio' })
import { computed, ref, onMounted, h } from 'vue'
import { usePortfolioStore } from '../stores'
import { useReferenceStore } from '../stores'
import { useUIStore } from '../stores'
import SharedDataTable from '../components/SharedDataTable.vue'
import OverviewCard from '../components/OverviewCard.vue'
import { formatCurrency, formatDate } from '../utils/formatters'
import { showError, showSuccess, showWarning, handleApiError } from '../utils/errorHandler'
import { Refresh } from '@element-plus/icons-vue'

// Pinia stores
const portfolioStore = usePortfolioStore()
const referenceStore = useReferenceStore()
const uiStore = useUIStore()

// Reactive state
const recalculateDate = ref(formatDate(new Date()))
// History Positions table is collapsed by default
const historyCollapseActive = ref<string[]>([])

// Computed properties from stores
const positions = computed(() => portfolioStore.positions)
const loading = computed(() => uiStore.loading)
const currentPortfolio = computed(() => portfolioStore.currentPortfolio)
const primaryCurrency = computed(() => referenceStore.primaryCurrency)

// Split positions into currently-held and historical (fully closed) ones.
// The backend flags closed non-cash positions with ``is_history=true``.
const currentPositions = computed(() =>
  positions.value.filter((p) => !p.is_history)
)
const historyPositions = computed(() =>
  positions.value.filter((p) => p.is_history)
)

// Total portfolio market value for MV% calculation (calculated from positions)
const totalPortfolioMarketValue = computed(() => {
  return positions.value.reduce((sum, p) => sum + (p.market_value_primary || 0), 0)
})

// Total P&L (calculated from all positions, including history's realized P&L)
const totalPnlPrimary = computed(() => {
  return positions.value.reduce((sum, p) => sum + (p.total_pnl_primary || 0), 0)
})

// Total dividends (all positions incl. history) in primary currency
const totalDividendsPrimary = computed(() => {
  return positions.value.reduce((sum, p) => sum + (p.dividends_primary || 0), 0)
})

// Position count (currently held only)
const positionCount = computed(() => currentPositions.value.length)

// Position with calculated percentages
interface PositionWithPct {
  asset_id: number
  symbol: string
  name?: string
  market_value: number
  market_value_primary: number
  total_pnl: number
  total_pnl_primary: number
  quantity?: number
  current_price?: number
  currency?: { code: string; symbol: string }
  mv_percent: number
  pnl_percent: number
  dividends?: number | null
  dividends_primary?: number | null
  is_history?: boolean
  [key: string]: any
}

// Currency group interface
interface CurrencyGroup {
  currencyCode: string
  currencySymbol: string
  positions: PositionWithPct[]
  totalMarketValue: number
  totalMarketValuePrimary: number
  totalPnl: number
  totalPnlPrimary: number
  totalDividends: number
}

// Group positions by currency, sorted with primary currency first
const groupedPositions = computed<CurrencyGroup[]>(() => {
  const groups: Record<string, CurrencyGroup> = {}

  currentPositions.value.forEach((position) => {
    const currencyCode: string = position.currency?.code || 'Unknown'
    const currencySymbol: string = position.currency?.symbol || '¥'

    if (!groups[currencyCode]) {
      groups[currencyCode] = {
        currencyCode: currencyCode,
        positions: [],
        totalMarketValue: 0,
        totalMarketValuePrimary: 0,
        totalPnl: 0,
        totalPnlPrimary: 0,
        totalDividends: 0,
        currencySymbol: currencySymbol
      }
    }

    const positionWithPercentages: PositionWithPct = calculatePositionPercentages(position)

    groups[currencyCode].positions.push(positionWithPercentages)
    groups[currencyCode].totalMarketValue += position.market_value || 0
    groups[currencyCode].totalMarketValuePrimary += position.market_value_primary || 0
    groups[currencyCode].totalPnl += position.total_pnl || 0
    groups[currencyCode].totalPnlPrimary += position.total_pnl_primary || 0
    groups[currencyCode].totalDividends += position.dividends || 0
  })

  // Sort positions within each currency group by market value (descending)
  Object.values(groups).forEach((group: CurrencyGroup) => {
    group.positions.sort((a: PositionWithPct, b: PositionWithPct) => (b.market_value || 0) - (a.market_value || 0))
  })

  // Convert to array and sort: primary currency first, then alphabetically
  const primaryCurrencyCode = primaryCurrency.value?.code
  const sortedGroups = Object.values(groups).sort((a: CurrencyGroup, b: CurrencyGroup) => {
    if (a.currencyCode === primaryCurrencyCode) return -1
    if (b.currencyCode === primaryCurrencyCode) return 1
    return a.currencyCode.localeCompare(b.currencyCode)
  })

  return sortedGroups
})

// Define table columns for SharedDataTable (currency grouped tables)
const tableColumns = computed(() => [
  { prop: 'symbol', label: 'Symbol', minWidth: '100', type: 'custom' },
  { prop: 'name', label: 'Name', minWidth: '150' },
  { prop: 'quantity', label: 'Quantity', minWidth: '120', align: 'right', type: 'quantity', sortable: true },
  { prop: 'current_price', label: 'Current Price', minWidth: '120', align: 'right', type: 'currency', sortable: true },
  { prop: 'market_value', label: 'Market Value', minWidth: '120', align: 'right', type: 'currency', decimalPlaces: 0, sortable: true },
  { prop: 'mv_percent', label: 'MV(%)', minWidth: '100', align: 'right', type: 'percentage', decimalPlaces: 2, sortable: true },
  { prop: 'total_pnl', label: 'Total P&L', minWidth: '120', align: 'right', type: 'pnl', decimalPlaces: 0, sortable: true },
  { prop: 'pnl_percent', label: 'P&L(%)', minWidth: '100', align: 'right', type: 'pnl_percentage', decimalPlaces: 2, sortable: true },
  { prop: 'dividends', label: 'Div', minWidth: '110', align: 'right', type: 'currency', decimalPlaces: 0, sortable: true }
])



// Always-truthy currency object for table columns. Avoids falling back to
// each asset's own currency in SharedDataTable when primaryCurrency is not
// yet loaded. Mirrors the pattern used in Dashboard.vue.
const primaryCurrencyForColumns = computed(() => ({
  symbol: primaryCurrency.value?.symbol || '¥'
}))

// Define table columns for summary table (all positions sorted by market value in primary currency)
const summaryTableColumns = computed(() => [
  { prop: 'symbol', label: 'Symbol', minWidth: '100', type: 'custom' },
  { prop: 'name', label: 'Name', minWidth: '150' },
  { prop: 'quantity', label: 'Quantity', minWidth: '120', align: 'right', type: 'quantity', sortable: true },
  { prop: 'current_price', label: 'Current Price', minWidth: '120', align: 'right', type: 'currency', currency: primaryCurrencyForColumns.value, sortable: true },
  { prop: 'market_value_primary', label: 'Market Value', minWidth: '120', align: 'right', type: 'currency', currency: primaryCurrencyForColumns.value, decimalPlaces: 0, sortable: true },
  { prop: 'mv_percent', label: 'MV(%)', minWidth: '100', align: 'right', type: 'percentage', decimalPlaces: 2, sortable: true },
  { prop: 'total_pnl_primary', label: 'Total P&L', minWidth: '120', align: 'right', type: 'pnl', currency: primaryCurrencyForColumns.value, decimalPlaces: 0, sortable: true },
  { prop: 'pnl_percent', label: 'P&L(%)', minWidth: '100', align: 'right', type: 'pnl_percentage', decimalPlaces: 2, sortable: true },
  { prop: 'dividends_primary', label: 'Div', minWidth: '110', align: 'right', type: 'currency', currency: primaryCurrencyForColumns.value, decimalPlaces: 0, sortable: true }
])

// Columns for the History Positions table (same shape as the All Positions summary)
const historyTableColumns = computed(() => [
  { prop: 'symbol', label: 'Symbol', minWidth: '100', type: 'custom' },
  { prop: 'name', label: 'Name', minWidth: '150' },
  { prop: 'quantity', label: 'Quantity', minWidth: '120', align: 'right', type: 'quantity', sortable: true },
  { prop: 'current_price', label: 'Current Price', minWidth: '120', align: 'right', type: 'currency', currency: primaryCurrencyForColumns.value, sortable: true },
  { prop: 'market_value_primary', label: 'Market Value', minWidth: '120', align: 'right', type: 'currency', currency: primaryCurrencyForColumns.value, decimalPlaces: 0, sortable: true },
  { prop: 'total_pnl_primary', label: 'Total P&L', minWidth: '120', align: 'right', type: 'pnl', currency: primaryCurrencyForColumns.value, decimalPlaces: 0, sortable: true },
  { prop: 'dividends_primary', label: 'Div', minWidth: '110', align: 'right', type: 'currency', currency: primaryCurrencyForColumns.value, decimalPlaces: 0, sortable: true }
])

// All positions sorted by market value (primary currency) in descending order
const allPositionsSorted = computed<PositionWithPct[]>(() => {
  const positionsWithPercentages = currentPositions.value.map((position) => {
    const marketValuePrimary: number = position.market_value_primary || 0
    const totalPnlPrimary: number = position.total_pnl_primary || 0

    return {
      ...position,
      mv_percent: totalPortfolioMarketValue.value > 0
        ? marketValuePrimary / totalPortfolioMarketValue.value
        : 0,
      pnl_percent: marketValuePrimary > 0
        ? totalPnlPrimary / marketValuePrimary
        : 0
    } as PositionWithPct
  })

  // Sort by market_value_primary in descending order
  return positionsWithPercentages.sort((a: PositionWithPct, b: PositionWithPct) => (b.market_value_primary || 0) - (a.market_value_primary || 0))
})

// History positions sorted by realized P&L (primary currency) descending.
// These all have market_value=0, so sorting by P&L is the most useful ordering.
const historyPositionsSorted = computed<PositionWithPct[]>(() => {
  const positionsWithPercentages = historyPositions.value.map((position) => {
    const totalPnlPrimary: number = position.total_pnl_primary || 0

    return {
      ...position,
      // MV% and P&L% are not meaningful for closed positions
      mv_percent: 0,
      pnl_percent: 0,
      total_pnl_primary: totalPnlPrimary
    } as PositionWithPct
  })

  return positionsWithPercentages.sort((a: PositionWithPct, b: PositionWithPct) =>
    (b.total_pnl_primary || 0) - (a.total_pnl_primary || 0))
})

// ===== UTILITY FUNCTIONS =====

/**
 * Calculate MV% and P&L% for a position
 */
const calculatePositionPercentages = (position: { market_value_primary?: number; total_pnl_primary?: number; [key: string]: any }): PositionWithPct => {
  const marketValuePrimary: number = position.market_value_primary || 0
  const totalPnlPrimary: number = position.total_pnl_primary || 0

  return {
    ...position,
    mv_percent: totalPortfolioMarketValue.value > 0
      ? marketValuePrimary / totalPortfolioMarketValue.value
      : 0,
    pnl_percent: marketValuePrimary > 0
      ? totalPnlPrimary / marketValuePrimary
      : 0
  } as PositionWithPct
}

/**
 * Disable future dates in date picker
 */
const disabledDate = (time: Date): boolean => {
  return time.getTime() > Date.now()
}

/**
 * Generate summary row for all positions summary table
 */
const getAllPositionsSummaryRow = (param: { columns: Array<{ property?: string }>; data: PositionWithPct[] }): (string | ReturnType<typeof h>)[] => {
  const { columns, data } = param
  const sums: (string | ReturnType<typeof h>)[] = []
  const primarySymbol = primaryCurrency.value?.symbol || '¥'

  // Calculate totals from table data (all positions in the table)
  const totalMarketValue = data.reduce((sum: number, pos: PositionWithPct) => sum + (pos.market_value_primary || 0), 0)
  const totalPnl = data.reduce((sum: number, pos: PositionWithPct) => sum + (pos.total_pnl_primary || 0), 0)
  const totalDividends = data.reduce((sum: number, pos: PositionWithPct) => sum + (pos.dividends_primary || 0), 0)

  columns.forEach((column, index: number) => {
    if (index === 0) {
      sums[index] = 'Total All:'
      return
    }

    switch (column.property) {
      case 'market_value_primary':
        sums[index] = formatCurrency(totalMarketValue, { symbol: primarySymbol }, 0)
        break
      case 'mv_percent': {
        const totalMvPercent = data.reduce((sum: number, pos: PositionWithPct) => sum + (pos.mv_percent || 0), 0)
        sums[index] = (totalMvPercent * 100).toFixed(2) + '%'
        break
      }
      case 'total_pnl_primary': {
        const pnlClass = totalPnl >= 0 ? 'positive' : 'negative'
        sums[index] = h('span', { class: pnlClass }, formatCurrency(totalPnl, { symbol: primarySymbol }, 0))
        break
      }
      case 'pnl_percent': {
        const pnlPercentValue = totalMarketValue > 0 ? totalPnl / totalMarketValue : 0
        const pnlPercentClass = pnlPercentValue >= 0 ? 'positive' : 'negative'
        const pnlPercentText = (pnlPercentValue * 100).toFixed(2) + '%'
        sums[index] = h('span', { class: pnlPercentClass }, pnlPercentText)
        break
      }
      case 'dividends_primary':
        sums[index] = formatCurrency(totalDividends, { symbol: primarySymbol }, 0)
        break
      default:
        sums[index] = ''
    }
  })

  return sums
}

/**
 * Generate summary row for the History Positions table
 */
const getHistorySummaryRow = (param: { columns: Array<{ property?: string }>; data: PositionWithPct[] }): (string | ReturnType<typeof h>)[] => {
  const { columns, data } = param
  const sums: (string | ReturnType<typeof h>)[] = []
  const primarySymbol = primaryCurrency.value?.symbol || '¥'

  const totalPnl = data.reduce((sum: number, pos: PositionWithPct) => sum + (pos.total_pnl_primary || 0), 0)
  const totalDividends = data.reduce((sum: number, pos: PositionWithPct) => sum + (pos.dividends_primary || 0), 0)

  columns.forEach((column, index: number) => {
    if (index === 0) {
      sums[index] = 'Total History:'
      return
    }

    switch (column.property) {
      case 'total_pnl_primary': {
        const pnlClass = totalPnl >= 0 ? 'positive' : 'negative'
        sums[index] = h('span', { class: pnlClass }, formatCurrency(totalPnl, { symbol: primarySymbol }, 0))
        break
      }
      case 'dividends_primary':
        sums[index] = formatCurrency(totalDividends, { symbol: primarySymbol }, 0)
        break
      default:
        sums[index] = ''
    }
  })

  return sums
}

/**
 * Generate summary row for currency group table
 */
const getSummaryRow = (param: { columns: Array<{ property?: string }>; data: PositionWithPct[] }, currencyGroup: CurrencyGroup): (string | ReturnType<typeof h>)[] => {
  const { columns } = param
  const sums: (string | ReturnType<typeof h>)[] = []

  columns.forEach((column, index: number) => {
    if (index === 0) {
      sums[index] = `Total ${currencyGroup.positions[0]?.currency?.code || ''}:`
      return
    }

    switch (column.property) {
      case 'market_value':
        sums[index] = formatCurrency(currencyGroup.totalMarketValue, { symbol: currencyGroup.currencySymbol }, 0)
        break
      case 'mv_percent':
        sums[index] = totalPortfolioMarketValue.value > 0
          ? ((currencyGroup.totalMarketValuePrimary / totalPortfolioMarketValue.value) * 100).toFixed(2) + '%'
          : '0.00%'
        break
      case 'total_pnl': {
        const pnlValue = currencyGroup.totalPnl
        const pnlClass = pnlValue >= 0 ? 'positive' : 'negative'
        sums[index] = h('span', { class: pnlClass }, formatCurrency(pnlValue, { symbol: currencyGroup.currencySymbol }, 0))
        break
      }
      case 'pnl_percent': {
        const pnlPercentValue = currencyGroup.totalMarketValuePrimary > 0
          ? (currencyGroup.totalPnlPrimary / currencyGroup.totalMarketValuePrimary)
          : 0
        const pnlPercentClass = pnlPercentValue >= 0 ? 'positive' : 'negative'
        const pnlPercentText = (pnlPercentValue * 100).toFixed(2) + '%'
        sums[index] = h('span', { class: pnlPercentClass }, pnlPercentText)
        break
      }
      case 'dividends':
        sums[index] = formatCurrency(currencyGroup.totalDividends, { symbol: currencyGroup.currencySymbol }, 0)
        break
      default:
        sums[index] = ''
    }
  })

  return sums
}

// ===== INITIALIZATION FUNCTIONS =====

/**
 * Initialize portfolio data on component creation
 * Fetches portfolios and positions if portfolio exists
 */
const initializePortfolio = async () => {
  try {
    // Ensure currencies (and thus primaryCurrency) are loaded so the
    // All Positions / History tables render in the primary currency
    // instead of each asset's own currency.
    if (!referenceStore.primaryCurrency) {
      await referenceStore.fetchCurrencies()
    }

    if (!currentPortfolio.value) {
      await portfolioStore.fetchPortfolios()
    }

    if (currentPortfolio.value) {
      await portfolioStore.fetchPositions(currentPortfolio.value.id, recalculateDate.value)
    }
  } catch (error) {
    handleApiError(error, 'Failed to load portfolio data')
  }
}



// ===== DATA OPERATIONS =====

/**
 * Validate required data before operations
 * @returns {boolean} True if validation passes
 */
const validateOperation = () => {
  if (!currentPortfolio.value) {
    showError('No portfolio selected')
    return false
  }

  if (!recalculateDate.value) {
    showError('Please select a date')
    return false
  }

  return true
}

/**
 * Recalculate positions for the selected date
 */
const handleRecalculate = async () => {
  if (!validateOperation()) return
  const portfolio = currentPortfolio.value
  if (!portfolio) return

  uiStore.setLoading(true)
  try {
    const result = await portfolioStore.recalculatePositions({
      portfolioId: portfolio.id,
      asOfDate: recalculateDate.value
    })

    showSuccess(result.message || 'Positions recalculated successfully')
    await portfolioStore.fetchPositions(portfolio.id, recalculateDate.value)
  } catch (error) {
    handleApiError(error, 'Failed to recalculate positions')
  } finally {
    uiStore.setLoading(false)
  }
}

/**
 * Show positions for the selected date
 * Recalculates if no positions exist for the date
 */
const handleShowPositions = async () => {
  if (!validateOperation()) return
  const portfolio = currentPortfolio.value
  if (!portfolio) return

  uiStore.setLoading(true)
  try {
    const positions = await portfolioStore.fetchPositions(portfolio.id, recalculateDate.value)

    if (!positions || positions.length === 0) {
      await recalculateForDate()
    } else {
      showSuccess(`Found ${positions.length} positions for ${recalculateDate.value}`)
    }
  } catch (error) {
    handleApiError(error, 'Failed to show positions')
  } finally {
    uiStore.setLoading(false)
  }
}

/**
 * Recalculate positions for a specific date when none exist
 */
const recalculateForDate = async () => {
  const portfolio = currentPortfolio.value
  if (!portfolio) return

  showWarning('No positions found for the selected date. Recalculating positions...')

  try {
    const result = await portfolioStore.recalculatePositions({
      portfolioId: portfolio.id,
      asOfDate: recalculateDate.value
    })

    showSuccess(result.message || 'Positions recalculated successfully')

    await portfolioStore.fetchPositions(portfolio.id, recalculateDate.value)
  } catch (error) {
    handleApiError(error, 'Failed to recalculate positions')
  }
}

// ===== EXPORT/DOWNLOAD FUNCTIONS =====

/**
 * Download positions for a specific currency as CSV
 * @param {Array} positions - Array of position objects
 * @param {string} currencyCode - Currency code for filename
 * @param {boolean} usePrimaryCurrency - Whether to use primary currency for monetary values
 */
const downloadPositionsCSV = (positions: PositionWithPct[], currencyCode: string, usePrimaryCurrency = false): void => {
  if (!positions || positions.length === 0) {
    showWarning('No positions to download')
    return
  }

  const csvData = generateCSVData(positions, usePrimaryCurrency)
  const filename = `positions_${currencyCode}_${recalculateDate.value || 'today'}.csv`

  triggerDownload(csvData, filename)
  showSuccess(`Positions for ${currencyCode} downloaded successfully`)
}

/**
 * Generate CSV content from positions
 */
const generateCSVData = (positions: PositionWithPct[], usePrimaryCurrency = false): string => {
  const primarySymbol = primaryCurrency.value?.symbol || '¥'
  const headers = ['Symbol', 'Name', 'Quantity', 'Current Price', 'Market Value', 'MV(%)', 'Total P&L', 'P&L(%)', 'Div', 'Currency']

  const rows = positions.map((pos: PositionWithPct) => {
    // Use primary currency values when specified
    const marketValue = usePrimaryCurrency ? (pos.market_value_primary || 0) : (pos.market_value || 0)
    const totalPnl = usePrimaryCurrency ? (pos.total_pnl_primary || 0) : (pos.total_pnl || 0)
    const dividends = usePrimaryCurrency ? (pos.dividends_primary || 0) : (pos.dividends || 0)
    const currencyCode = usePrimaryCurrency ? primarySymbol : (pos.currency?.code || 'Unknown')

    return [
      `"${pos.symbol || ''}"`,
      `"${pos.name || ''}"`,
      pos.quantity || 0,
      pos.current_price || 0,
      marketValue,
      pos.mv_percent != null ? (pos.mv_percent * 100).toFixed(2) + '%' : '0.00%',
      totalPnl,
      pos.pnl_percent != null ? (pos.pnl_percent * 100).toFixed(2) + '%' : '0.00%',
      dividends,
      `"${currencyCode}"`
    ].join(',')
  })

  return [headers.join(','), ...rows].join('\n')
}

/**
 * Trigger browser download for CSV content
 */
const triggerDownload = (csvContent: string, filename: string): void => {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)

  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.display = 'none'

  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  setTimeout(() => URL.revokeObjectURL(url), 100)
}

// Refresh
const handleRefresh = () => {
  initializePortfolio()
}

// Initialize on component mount
onMounted(() => {
  initializePortfolio()
})
</script>

<style scoped>
.portfolio {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.position-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  background: #ffffff;
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #666;
}

.empty-state-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.empty-state {
  text-align: center;
  color: #666;
}

.empty-state p {
  margin: 10px 0;
}

.portfolio-summary {
  margin-bottom: 24px;
}

.overview-cards {
  margin-bottom: 0;
}

/* Modern Table Section Styles */
.summary-table-section,
.currency-table-section,
.history-table-section {
  margin-bottom: 32px;
  background: #ffffff;
  border-radius: 16px;
  border: none;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.summary-table-section:hover,
.currency-table-section:hover,
.history-table-section:hover {
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.summary-table-header,
.currency-table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-bottom: none;
}

.currency-table-header {
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
}

.summary-table-title,
.currency-table-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 10px;
  letter-spacing: 0.5px;
}

.summary-table-title::before,
.currency-table-title::before {
  content: '';
  width: 4px;
  height: 20px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 2px;
}

.download-btn {
  border-radius: 8px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #ffffff;
  backdrop-filter: blur(10px);
  transition: all 0.3s ease;
}

.download-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.5);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  color: #ffffff;
}

/* History Positions collapse section */
.history-collapse {
  border: none;
}

.history-collapse :deep(.el-collapse-item__header) {
  height: auto;
  line-height: 1.4;
  padding: 18px 24px;
  background: linear-gradient(135deg, #8e9eab 0%, #6c7a89 100%);
  border-bottom: none;
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
}

.history-collapse :deep(.el-collapse-item__header:hover) {
  background: linear-gradient(135deg, #9faab2 0%, #7a8794 100%);
}

.history-collapse :deep(.el-collapse-item__arrow) {
  color: #ffffff;
  font-size: 16px;
  margin-right: 8px;
}

.history-collapse :deep(.el-collapse-item__wrap) {
  background: #ffffff;
  border-bottom: none;
}

.history-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.history-collapse-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.history-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 10px;
  letter-spacing: 0.5px;
}

.history-title::before {
  content: '';
  width: 4px;
  height: 20px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 2px;
}

.history-count-tag {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
  color: #ffffff;
  font-weight: 600;
}

.history-content {
  padding: 0;
}

.history-download-bar {
  display: flex;
  justify-content: flex-end;
  padding: 12px 24px;
  background: #fafbfc;
  border-bottom: 1px solid #f0f2f5;
}

/* Table Styles */
.summary-table,
.currency-table,
.history-table {
  --el-table-border-color: #f0f2f5;
  --el-table-header-bg-color: #fafbfc;
  --el-table-row-hover-bg-color: #f5f7fa;
  --el-table-text-color: #606266;
  --el-table-header-text-color: #303133;
}

.summary-table :deep(.el-table__header-wrapper),
.currency-table :deep(.el-table__header-wrapper),
.history-table :deep(.el-table__header-wrapper) {
  background: #fafbfc;
}

.summary-table :deep(.el-table__header th),
.currency-table :deep(.el-table__header th),
.history-table :deep(.el-table__header th) {
  font-weight: 600;
  color: #303133;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
  padding: 16px 0;
  font-size: 13px;
  letter-spacing: 0.3px;
  border-bottom: 2px solid #e4e7ed;
}

.summary-table :deep(.el-table__body td),
.currency-table :deep(.el-table__body td),
.history-table :deep(.el-table__body td) {
  font-size: 14px;
  border-bottom: 1px solid #f0f2f5;
}

.summary-table :deep(.el-table__row),
.currency-table :deep(.el-table__row),
.history-table :deep(.el-table__row) {
  transition: all 0.2s ease;
}

.summary-table :deep(.el-table__row:hover),
.currency-table :deep(.el-table__row:hover),
.history-table :deep(.el-table__row:hover) {
  background-color: #f5f7fa;
}

.summary-table :deep(.el-table__row:hover td),
.currency-table :deep(.el-table__row:hover td),
.history-table :deep(.el-table__row:hover td) {
  background-color: transparent;
}

/* Summary Row Styles */
.summary-table :deep(.el-table__footer-wrapper),
.currency-table :deep(.el-table__footer-wrapper),
.history-table :deep(.el-table__footer-wrapper) {
  background: linear-gradient(180deg, #f8f9fc 0%, #f0f2f8 100%);
  font-weight: 600;
}

.summary-table :deep(.el-table__footer td),
.currency-table :deep(.el-table__footer td),
.history-table :deep(.el-table__footer td) {
  background: linear-gradient(180deg, #f8f9fc 0%, #f0f2f8 100%);
  color: #303133;
  font-weight: 600;
  padding: 16px 0;
  border-top: 2px solid #667eea;
  font-size: 14px;
}

.currency-table :deep(.el-table__footer td) {
  border-top-color: #11998e;
}

.history-table :deep(.el-table__footer td) {
  border-top-color: #909399;
}

/* Positive/Negative Colors */
.positive {
  color: #67c23a;
  font-weight: 500;
}

.negative {
  color: #f56c6c;
  font-weight: 500;
}

/* Symbol hyperlink styles */
.symbol-link {
  color: #409eff;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease, text-decoration 0.2s ease;
}

.symbol-link:hover {
  color: #66b1ff;
  text-decoration: underline;
}

.symbol-link:active {
  color: #3a8ee6;
}

/* Empty State Enhancement */
.empty-state {
  text-align: center;
  padding: 60px 40px;
  color: #909399;
  background: #fafbfc;
  border-radius: 8px;
  margin: 20px;
}

.empty-state p {
  margin: 12px 0;
  font-size: 14px;
}

.empty-state p:first-child {
  font-size: 16px;
  font-weight: 500;
  color: #606266;
}

/* Deep selectors for Element Plus table summary row */
:deep(.el-table__footer-wrapper .el-table__footer .positive) {
  color: #67c23a !important;
}

:deep(.el-table__footer-wrapper .el-table__footer .negative) {
  color: #f56c6c !important;
}

/* ===== RESPONSIVE DESIGN ===== */

/* Large screens (1400px and up) */
@media (min-width: 1400px) {
  .summary-table-header,
  .currency-table-header {
    padding: 24px 32px;
  }

  .summary-table-title,
  .currency-table-title {
    font-size: 20px;
  }
}

/* Medium screens (1024px - 1399px) */
@media (max-width: 1399px) and (min-width: 1024px) {
  .summary-table-header,
  .currency-table-header {
    padding: 18px 24px;
  }

  .summary-table-title,
  .currency-table-title {
    font-size: 17px;
  }
}

/* Tablet screens (768px - 1023px) */
@media (max-width: 1023px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .position-controls {
    flex-wrap: wrap;
    gap: 10px;
    width: 100%;
  }

  .position-controls .el-date-picker {
    width: 100% !important;
    max-width: 200px;
  }

  .portfolio-summary .el-col {
    margin-bottom: 16px;
  }

  .summary-table-header,
  .currency-table-header {
    padding: 16px 20px;
    flex-wrap: wrap;
    gap: 12px;
  }

  .summary-table-title,
  .currency-table-title {
    font-size: 16px;
  }

  .download-btn {
    font-size: 13px;
    padding: 8px 16px;
  }

  .summary-table :deep(.el-table__header th),
  .currency-table :deep(.el-table__header th),
  .history-table :deep(.el-table__header th) {
    padding: 12px 0;
    font-size: 12px;
  }

  .summary-table :deep(.el-table__body td),
  .currency-table :deep(.el-table__body td),
  .history-table :deep(.el-table__body td) {
    font-size: 13px;
  }

  .summary-table :deep(.el-table__footer td),
  .currency-table :deep(.el-table__footer td),
  .history-table :deep(.el-table__footer td) {
    padding: 12px 0;
    font-size: 13px;
  }

  .history-collapse :deep(.el-collapse-item__header) {
    padding: 16px 20px;
  }
}

/* Mobile screens (below 768px) */
@media (max-width: 767px) {
  .portfolio {
    padding: 0 8px;
  }

  .page-header {
    margin-bottom: 16px;
  }

  .position-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .position-controls .el-button {
    width: 100%;
    margin-right: 0 !important;
    margin-bottom: 8px;
  }

  .position-controls .el-date-picker {
    width: 100% !important;
    max-width: none;
    margin-right: 0 !important;
    margin-bottom: 8px;
  }

  .portfolio-summary {
    margin-bottom: 16px;
  }

  .portfolio-summary .el-col {
    margin-bottom: 12px;
  }

  .summary-table-section,
  .currency-table-section,
  .history-table-section {
    margin-bottom: 20px;
    border-radius: 12px;
  }

  .summary-table-header,
  .currency-table-header {
    padding: 14px 16px;
    flex-direction: column;
    align-items: flex-start;
  }

  .summary-table-title,
  .currency-table-title {
    font-size: 15px;
    margin-bottom: 10px;
  }

  .download-btn {
    width: 100%;
    justify-content: center;
  }

  .summary-table :deep(.el-table__header th),
  .currency-table :deep(.el-table__header th),
  .history-table :deep(.el-table__header th) {
    padding: 10px 4px;
    font-size: 11px;
  }

  .summary-table :deep(.el-table__body td),
  .currency-table :deep(.el-table__body td),
  .history-table :deep(.el-table__body td) {
    font-size: 12px;
  }

  .summary-table :deep(.el-table__footer td),
  .currency-table :deep(.el-table__footer td),
  .history-table :deep(.el-table__footer td) {
    padding: 10px 4px;
    font-size: 12px;
  }

  .history-collapse :deep(.el-collapse-item__header) {
    padding: 14px 16px;
  }

  .history-title {
    font-size: 15px;
    margin-bottom: 0;
  }

  .history-download-bar {
    padding: 10px 16px;
  }

  .empty-state {
    padding: 40px 20px;
    margin: 16px;
  }

  .empty-state p {
    font-size: 13px;
  }

  .empty-state p:first-child {
    font-size: 14px;
  }
}

/* Extra small screens (below 480px) */
@media (max-width: 479px) {
  .summary-table-title,
  .currency-table-title {
    font-size: 14px;
  }

  .summary-table :deep(.el-table__header th),
  .currency-table :deep(.el-table__header th),
  .history-table :deep(.el-table__header th) {
    font-size: 10px;
  }

  .summary-table :deep(.el-table__body td),
  .currency-table :deep(.el-table__body td),
  .history-table :deep(.el-table__body td) {
    font-size: 11px;
  }
}

/* Smooth transitions for window resize */
.summary-table-section,
.currency-table-section,
.history-table-section {
  transition: all 0.3s ease;
}

.summary-table :deep(.el-table__header th),
.summary-table :deep(.el-table__body td),
.summary-table :deep(.el-table__footer td),
.currency-table :deep(.el-table__header th),
.currency-table :deep(.el-table__body td),
.currency-table :deep(.el-table__footer td),
.history-table :deep(.el-table__header th),
.history-table :deep(.el-table__body td),
.history-table :deep(.el-table__footer td) {
  transition: padding 0.2s ease, font-size 0.2s ease;
}
</style>