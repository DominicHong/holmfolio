<template>
  <div class="analytics">
    <div class="page-header">
      <div class="title-row">
        <h2 class="page-title">Portfolio Analytics</h2>
        <el-button :icon="Refresh" @click="handleRefresh" circle aria-label="Refresh" />
      </div>
    </div>

    <div class="controls-top">
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
      <div class="benchmark-controls-top">
        <div class="benchmark-label">Benchmark:</div>
        <el-select
          v-model="selectedBenchmarkId"
          placeholder="Select benchmark"
          style="width: 200px"
          aria-label="Select benchmark"
          @change="onBenchmarkChange"
        >
          <el-option
            v-for="benchmark in benchmarks"
            :key="benchmark.id"
            :label="benchmark.name"
            :value="benchmark.id"
          />
        </el-select>
      </div>
    </div>

    <!-- Row 1: Performance History + Asset Allocation -->
    <el-row :gutter="20" style="margin-top: 20px;" class="charts-row">
      <el-col :span="18">
        <el-card class="chart-card performance-chart-card">
          <template #header>
            <div class="card-header">
              <span>Performance History</span>
            </div>
          </template>
          <div v-if="loadingStates.performanceHistory" class="loading-message">
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
          <div v-if="loadingStates.assetAllocation" class="loading-message">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <span>Loading allocation data...</span>
          </div>
          <AllocationChart v-else :asset-allocation="assetAllocation" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Row 2: Performance Metrics + Recent Returns -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="10">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>Performance Metrics</span>
            </div>
          </template>
          <div v-if="loadingStates.performanceMetrics" class="loading-message">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <span>Loading metrics data...</span>
          </div>
          <template v-else>
            <el-descriptions :column="2" border class="metrics-descriptions">
              <el-descriptions-item label="Total Return">
                <span class="num-value" :class="signClass(performanceMetrics.total_return)">{{ formatPercentage(performanceMetrics.total_return) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Annualized Return">
                <span class="num-value" :class="signClass(performanceMetrics.annualized_return)">{{ formatPercentage(performanceMetrics.annualized_return) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Volatility">
                <span class="num-value">{{ formatPercentage(performanceMetrics.volatility) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Sharpe Ratio">
                <span class="num-value" :class="signClass(performanceMetrics.sharpe_ratio)">{{ formatNumber(performanceMetrics.sharpe_ratio) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Max Drawdown">
                <span class="num-value" :class="signClass(performanceMetrics.max_drawdown)">{{ formatPercentage(performanceMetrics.max_drawdown) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Beta">
                <span class="num-value" :class="signClass(performanceMetrics.beta)">{{ formatNumber(performanceMetrics.beta) }}</span>
              </el-descriptions-item>
            </el-descriptions>
            <div v-if="performanceMetrics.message" class="empty-state">
              <p>{{ performanceMetrics.message }}</p>
            </div>
          </template>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>Recent Returns</span>
            </div>
          </template>
          <div v-if="loadingStates.recentReturns" class="loading-message">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <span>Loading returns data...</span>
          </div>
          <template v-else>
            <el-table :data="recentReturns" style="width: 100%" class="analytics-table">
              <el-table-column prop="period" label="Period" width="120" />
              <el-table-column prop="return" label="Return" align="right">
                <template #default="scope">
                  <span class="num-value" :class="scope.row.return >= 0 ? 'positive' : 'negative'">
                    {{ formatPercentage(scope.row.return) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column v-if="selectedBenchmarkId" prop="benchmark_return" label="Benchmark Return" align="right">
                <template #default="scope">
                  <span class="num-value" :class="scope.row.benchmark_return >= 0 ? 'positive' : 'negative'">
                    {{ formatPercentage(scope.row.benchmark_return) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column v-if="selectedBenchmarkId" prop="excess_return" label="Excess Return(Aligned with Benchmark)" align="right">
                <template #default="scope">
                  <span class="num-value" :class="scope.row.excess_return >= 0 ? 'positive' : 'negative'">
                    {{ formatPercentage(scope.row.excess_return) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="start_nav" label="Start NAV" align="right">
                <template #default="scope">
                  <span class="num-value">{{ formatNumber(scope.row.start_nav) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="end_nav" label="End NAV" align="right">
                <template #default="scope">
                  <span class="num-value">{{ formatNumber(scope.row.end_nav) }}</span>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="recentReturns.length === 0" class="empty-state">
              <p>No recent returns data available. Please import some transactions first.</p>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- Row 3: Beta Analysis + Tag Correlation -->
    <el-row :gutter="20" style="margin-top: 20px;" class="charts-row">
      <el-col :span="10">
        <el-card class="chart-card">
      <template #header>
        <div class="card-header">
          <span>Beta Analysis</span>
        </div>
      </template>
      <div v-if="!selectedBenchmarkId" class="empty-state">
        <p>Please select a benchmark to view beta analysis.</p>
      </div>
      <template v-else>
        <el-tabs v-model="betaTab" class="beta-tabs">
          <el-tab-pane label="By Tag" name="tag">
            <div v-if="loadingStates.tagBeta" class="loading-message">
              <el-icon class="is-loading" :size="32"><Loading /></el-icon>
              <span>Loading beta data...</span>
            </div>
            <div v-else-if="!selectedAllocationCategory" class="empty-state">
              <p>Please select a tag category in Asset Allocation to view tag betas.</p>
            </div>
            <TagBetaChart v-else :data="tagBeta" />
          </el-tab-pane>
          <el-tab-pane label="By Asset(MV Top 10)" name="asset">
            <div v-if="loadingStates.assetBetaMvTop10" class="loading-message">
              <el-icon class="is-loading" :size="32"><Loading /></el-icon>
              <span>Loading asset beta data...</span>
            </div>
            <template v-else>
              <div class="asset-beta-search">
                <div class="asset-beta-autocomplete">
                  <el-input
                    v-model="assetBetaSearchQuery"
                    placeholder="Search asset by symbol or name to add"
                    clearable
                    class="asset-beta-search-input"
                    @input="onAssetBetaSearchInput"
                    @focus="onAssetBetaSearchFocus"
                    @blur="onAssetBetaSearchBlur"
                    @keydown="onAssetBetaSearchKeydown"
                    @clear="clearAssetBetaSelection"
                  />
                  <div v-if="showAssetBetaDropdown && filteredBetaAssets.length > 0" class="asset-beta-dropdown">
                    <div
                      v-for="(asset, index) in filteredBetaAssets"
                      :key="asset.id"
                      class="asset-beta-dropdown-item"
                      :class="{ active: index === highlightedAssetBetaIndex, selected: selectedAssetBetaId === asset.id }"
                      @mousedown.prevent="selectBetaAsset(asset)"
                      @mouseenter="highlightedAssetBetaIndex = index"
                    >
                      <span class="asset-beta-symbol">{{ asset.symbol }}</span>
                      <span class="asset-beta-name">{{ asset.name }}</span>
                    </div>
                  </div>
                  <div v-else-if="showAssetBetaDropdown && assetBetaSearchQuery && filteredBetaAssets.length === 0" class="asset-beta-dropdown">
                    <div class="asset-beta-dropdown-empty">No matching assets found</div>
                  </div>
                </div>
              </div>
              <AssetBetaChart :data="assetBetaMvTop10" />
            </template>
          </el-tab-pane>
          <el-tab-pane label="By Asset(Beta Top 5 and Bottom 5)" name="asset-beta-top-bottom">
            <div v-if="loadingStates.assetBetaTopBottom" class="loading-message">
              <el-icon class="is-loading" :size="32"><Loading /></el-icon>
              <span>Loading asset beta data...</span>
            </div>
            <template v-else>
              <div class="asset-beta-section">
                <h4 class="asset-beta-section-title">Top 5 (Highest Beta)</h4>
                <AssetBetaChart :data="assetBetaTop5" />
              </div>
              <div class="asset-beta-section">
                <h4 class="asset-beta-section-title">Bottom 5 (Lowest Beta)</h4>
                <AssetBetaChart :data="assetBetaBottom5" />
              </div>
            </template>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-card>
      </el-col>

      <el-col :span="14">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>Tag Correlation</span>
            </div>
          </template>
          <div v-if="loadingStates.tagCorrelation" class="loading-message">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <span>Loading correlation data...</span>
          </div>
          <div v-else-if="!selectedAllocationCategory" class="empty-state">
            <p>Please select a tag category in Asset Allocation to view tag correlations.</p>
          </div>
          <TagCorrelationChart v-else :data="tagCorrelation" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Analytics' })
import { ref, computed, watch, onMounted } from 'vue'
import { useAnalyticsStore } from '../stores'
import { useReferenceStore } from '../stores'
import { useTransactionStore } from '../stores'
import { usePortfolioStore } from '../stores'
import { useAssetStore } from '../stores'
import AllocationChart from '../components/AllocationChart.vue'
import PerformanceChart from '../components/PerformanceChart.vue'
import TagCorrelationChart from '../components/TagCorrelationChart.vue'
import TagBetaChart from '../components/TagBetaChart.vue'
import AssetBetaChart from '../components/AssetBetaChart.vue'
import { formatPercentage, formatNumber } from '../utils/formatters'
import { useTimeRange } from '../composables/useTimeRange'
import { useLoading } from '../composables/useLoading'
import { showWarning, handleApiError } from '../utils/errorHandler'
import { Refresh } from '@element-plus/icons-vue'

// Stores
const analyticsStore = useAnalyticsStore()
const referenceStore = useReferenceStore()
const transactionStore = useTransactionStore()
const portfolioStore = usePortfolioStore()
const assetStore = useAssetStore()

// Local state to prevent concurrent requests
const isInitializing = ref(false)

// Benchmark selection
const selectedBenchmarkId = ref<number | null>(null)
const benchmarks = computed(() => referenceStore.benchmarks || [])

// Asset allocation category selection
const selectedAllocationCategory = ref<number | string>('')
const tagCategories = computed(() => referenceStore.tagCategories)

// Independent loading states for each card
const { loadingStates, withLoading } = useLoading([
  'performanceHistory',
  'performanceMetrics',
  'assetAllocation',
  'recentReturns',
  'tagCorrelation',
  'tagBeta',
  'assetBetaMvTop10',
  'assetBetaTopBottom'
])

// Computed properties from stores (unified with Dashboard.vue)
const performanceHistory = computed(() => analyticsStore.performanceHistory)
const assetAllocation = computed(() => analyticsStore.assetAllocation)
const recentReturns = computed(() => analyticsStore.recentReturns)
const tagCorrelation = computed(() => analyticsStore.tagCorrelation)
const tagBeta = computed(() => analyticsStore.tagBeta)
const assetBetaMvTop10 = computed(() => analyticsStore.assetBetaMvTop10)
const assetBetaTopBottom = computed(() => analyticsStore.assetBetaTopBottom)
const primaryCurrency = computed(() => referenceStore.primaryCurrency)

// Asset beta top/bottom 5 by beta value (non-cash assets only)
const assetBetaTop5 = computed(() => {
  const data = assetBetaTopBottom.value
  if (!data || !data.assets || data.assets.length === 0) return null
  const sorted = [...data.assets]
    .filter(a => a.beta !== null && a.beta !== undefined)
    .sort((a, b) => b.beta - a.beta)
    .slice(0, 5)
  return { ...data, assets: sorted }
})

const assetBetaBottom5 = computed(() => {
  const data = assetBetaTopBottom.value
  if (!data || !data.assets || data.assets.length === 0) return null
  const sorted = [...data.assets]
    .filter(a => a.beta !== null && a.beta !== undefined)
    .sort((a, b) => a.beta - b.beta)
    .slice(0, 5)
  return { ...data, assets: sorted }
})

// Performance metrics from analytics store (mapped to component's expected structure)
const performanceMetrics = computed(() => {
  const stats = analyticsStore.portfolioStats || {}
  return {
    total_return: stats.time_weighted_return || 0,
    annualized_return: stats.annualized_return || 0,
    volatility: stats.volatility || 0,
    sharpe_ratio: stats.sharpe_ratio || 0,
    max_drawdown: stats.max_drawdown || 0,
    beta: stats.beta || 0,
    message: stats.message
  }
})

// Return a positive/negative class based on a value's sign (0 is uncolored)
function signClass(value: number | undefined | null): string {
  if (value === undefined || value === null) return ''
  if (value > 0) return 'positive'
  if (value < 0) return 'negative'
  return ''
}

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
    const portfolioId = portfolioStore.currentPortfolioId
    if (!portfolioId) {
      console.warn('No portfolio selected')
      return
    }
    try {
      console.log('Fetching analytics data for date range:', start, 'to', end)
      await fetchAllData(portfolioId)
    } catch (error) {
      handleApiError(error, 'Failed to load analytics data')
    }
  }
})

// Data fetching functions (unified with Dashboard.vue pattern)
// Load performance history data
const loadPerformanceHistoryData = async (portfolioId: number) => {
  await withLoading('performanceHistory', async () => {
    const options: { startDate: string | null; endDate: string | null; benchmarkId?: number } = { startDate: startDate.value, endDate: endDate.value }
    if (selectedBenchmarkId.value) {
      options.benchmarkId = selectedBenchmarkId.value
    }
    await analyticsStore.fetchPerformanceHistory(portfolioId, options)
  })
}

// Load performance metrics data
const loadPerformanceMetricsData = async (portfolioId: number) => {
  await withLoading('performanceMetrics', async () => {
    const options: { startDate: string | null; endDate: string | null; benchmarkId?: number } = { startDate: startDate.value, endDate: endDate.value }
    if (selectedBenchmarkId.value) {
      options.benchmarkId = selectedBenchmarkId.value
    }
    await analyticsStore.fetchPerformanceMetrics(portfolioId, options)
  })
}

// Load asset allocation data
const loadAssetAllocationData = async (portfolioId: number) => {
  await withLoading('assetAllocation', async () => {
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
  const portfolioId = portfolioStore.currentPortfolioId
  if (portfolioId) {
    loadAssetAllocationData(portfolioId)
    loadTagCorrelationData(portfolioId)
    loadTagBetaData(portfolioId)
  }
}

// Asset Beta search (reference: TagManagement.vue Asset Tags input)
const assetBetaSearchQuery = ref('')
const showAssetBetaDropdown = ref(false)
const highlightedAssetBetaIndex = ref(-1)
const selectedAssetBetaId = ref<number | null>(null)
const betaTab = ref('tag')

const assets = computed(() => assetStore.assets || [])

const filteredBetaAssets = computed(() => {
  const nonCashAssets = assets.value.filter(asset => asset.type !== 'cash')
  if (!assetBetaSearchQuery.value.trim()) {
    return nonCashAssets
  }
  const query = assetBetaSearchQuery.value.toLowerCase().trim()
  return nonCashAssets.filter(asset =>
    asset.symbol.toLowerCase().includes(query) ||
    asset.name.toLowerCase().includes(query)
  )
})

const onAssetBetaSearchInput = () => {
  showAssetBetaDropdown.value = true
  highlightedAssetBetaIndex.value = -1
}

const onAssetBetaSearchFocus = () => {
  showAssetBetaDropdown.value = true
}

const onAssetBetaSearchBlur = () => {
  setTimeout(() => {
    showAssetBetaDropdown.value = false
  }, 200)
}

const onAssetBetaSearchKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (filteredBetaAssets.value.length === 0) return
    highlightedAssetBetaIndex.value = Math.min(
      highlightedAssetBetaIndex.value + 1,
      filteredBetaAssets.value.length - 1
    )
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (filteredBetaAssets.value.length === 0) return
    highlightedAssetBetaIndex.value = Math.max(highlightedAssetBetaIndex.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (highlightedAssetBetaIndex.value >= 0 && highlightedAssetBetaIndex.value < filteredBetaAssets.value.length) {
      selectBetaAsset(filteredBetaAssets.value[highlightedAssetBetaIndex.value])
    }
  } else if (e.key === 'Escape') {
    showAssetBetaDropdown.value = false
    highlightedAssetBetaIndex.value = -1
  }
}

const selectBetaAsset = (asset: any) => {
  selectedAssetBetaId.value = asset.id
  assetBetaSearchQuery.value = `${asset.symbol} - ${asset.name}`
  showAssetBetaDropdown.value = false
  highlightedAssetBetaIndex.value = -1
  // Fetch asset beta with the selected asset
  const portfolioId = portfolioStore.currentPortfolioId
  if (portfolioId) {
    loadAssetBetaMvTop10Data(portfolioId)
  }
}

const clearAssetBetaSelection = () => {
  selectedAssetBetaId.value = null
  assetBetaSearchQuery.value = ''
  // Re-fetch without specific asset
  const portfolioId = portfolioStore.currentPortfolioId
  if (portfolioId) {
    loadAssetBetaMvTop10Data(portfolioId)
  }
}

// Load tag correlation data
const loadTagCorrelationData = async (portfolioId: number) => {
  await withLoading('tagCorrelation', async () => {
    if (!selectedAllocationCategory.value) {
      analyticsStore.setTagCorrelation(null)
      return
    }
    const options = {
      startDate: startDate.value,
      endDate: endDate.value,
      tagCategoryId: selectedAllocationCategory.value
    }
    await analyticsStore.fetchTagCorrelation(portfolioId, options)
  })
}

// Load tag beta data
const loadTagBetaData = async (portfolioId: number) => {
  await withLoading('tagBeta', async () => {
    if (!selectedAllocationCategory.value || !selectedBenchmarkId.value) {
      analyticsStore.setTagBeta(null)
      return
    }
    const options = {
      startDate: startDate.value,
      endDate: endDate.value,
      tagCategoryId: selectedAllocationCategory.value,
      benchmarkId: selectedBenchmarkId.value,
      frequency: 'daily' as const,
    }
    await analyticsStore.fetchTagBeta(portfolioId, options)
  })
}

// Load asset beta data (MV Top 10)
const loadAssetBetaMvTop10Data = async (portfolioId: number) => {
  await withLoading('assetBetaMvTop10', async () => {
    if (!selectedBenchmarkId.value) {
      analyticsStore.setAssetBetaMvTop10(null)
      return
    }
    const options = {
      startDate: startDate.value,
      endDate: endDate.value,
      benchmarkId: selectedBenchmarkId.value,
      assetId: selectedAssetBetaId.value,
      frequency: 'daily' as const,
    }
    await analyticsStore.fetchAssetBetaMvTop10(portfolioId, options)
  })
}

// Load asset beta data for top/bottom 5 by beta (all non-cash assets)
const loadAssetBetaTopBottomData = async (portfolioId: number) => {
  await withLoading('assetBetaTopBottom', async () => {
    if (!selectedBenchmarkId.value) {
      analyticsStore.setAssetBetaTopBottom(null)
      return
    }
    const options = {
      startDate: startDate.value,
      endDate: endDate.value,
      benchmarkId: selectedBenchmarkId.value,
      frequency: 'daily' as const,
    }
    await analyticsStore.fetchAssetBetaTopBottom(portfolioId, options)
  })
}

// Handle benchmark change
const onBenchmarkChange = () => {
  const portfolioId = portfolioStore.currentPortfolioId
  if (portfolioId) {
    loadPerformanceHistoryData(portfolioId)
    loadPerformanceMetricsData(portfolioId)
    loadRecentReturnsData(portfolioId)
    loadTagBetaData(portfolioId)
    loadAssetBetaMvTop10Data(portfolioId)
    loadAssetBetaTopBottomData(portfolioId)
  }
}

// Load recent returns data
const loadRecentReturnsData = async (portfolioId: number) => {
  await withLoading('recentReturns', async () => {
    const options: { endDate: string | null; benchmarkId?: number } = { endDate: endDate.value }
    if (selectedBenchmarkId.value) {
      options.benchmarkId = selectedBenchmarkId.value
    }
    await analyticsStore.fetchRecentReturns(portfolioId, options)
  })
}

// Fetch all data with concurrent loading
const fetchAllData = async (portfolioId: number) => {
  const results = await Promise.allSettled([
    loadPerformanceHistoryData(portfolioId),
    loadPerformanceMetricsData(portfolioId),
    loadAssetAllocationData(portfolioId),
    loadRecentReturnsData(portfolioId),
    loadTagCorrelationData(portfolioId),
    loadTagBetaData(portfolioId),
    loadAssetBetaMvTop10Data(portfolioId),
    loadAssetBetaTopBottomData(portfolioId),
  ])

  // Report individual failures without blocking other sections
  results.forEach((r) => {
    if (r.status === 'rejected') {
      handleApiError(r.reason, 'Failed to load analytics data')
    }
  })
}



// Initialize analytics
const initializeAnalytics = async () => {
  if (isInitializing.value) return
  isInitializing.value = true

  try {
    // Ensure portfolios are loaded and current portfolio is set
    if (!portfolioStore.currentPortfolio) {
      await portfolioStore.fetchPortfolios()
    }

    // Check if we have a valid portfolio ID
    if (!portfolioStore.currentPortfolioId) {
      showWarning('Please create or select a portfolio first')
      return
    }

    const portfolioId: number = portfolioStore.currentPortfolioId

    // Initialize time range with default values (1 year)
    initializeTimeRange()

    // Fetch transactions first (needed for time range calculations)
    await transactionStore.fetchTransactions(portfolioId)

    // Fetch benchmarks and set default (CSI 300 Total)
    await referenceStore.fetchBenchmarks()
    if (benchmarks.value && benchmarks.value.length > 0 && !selectedBenchmarkId.value) {
      const defaultBenchmark = benchmarks.value.find((b: { symbol?: string; id: number }) => b.symbol === 'H00300.CSI')
      selectedBenchmarkId.value = defaultBenchmark ? defaultBenchmark.id : benchmarks.value[0].id
    }

    // Fetch assets for asset beta search
    if (!assetStore.assets || assetStore.assets.length === 0) {
      await assetStore.fetchAssets()
    }

    // Fetch tag categories and set default category if none selected
    await referenceStore.fetchTagCategories()
    if (!selectedAllocationCategory.value && tagCategories.value && tagCategories.value.length > 0) {
      const defaultCategory = tagCategories.value.find((c: { name: string; id: number }) => c.name === '自定义类别')
      if (defaultCategory) {
        selectedAllocationCategory.value = defaultCategory.id
      }
    }

    // Fetch all card data independently
    await fetchAllData(portfolioId)
  } catch (error) {
    handleApiError(error, 'Failed to load analytics data')
  } finally {
    isInitializing.value = false
  }
}

// Refresh
const handleRefresh = () => {
  initializeAnalytics()
}

// Lifecycle hooks
onMounted(() => {
  initializeAnalytics()
})

// Watchers
watch(
  () => portfolioStore.currentPortfolio,
  (newPortfolio, oldPortfolio) => {
    // Ignore initial assignment when oldPortfolio is undefined
    if (oldPortfolio && (newPortfolio?.id !== oldPortfolio.id)) {
      initializeAnalytics()
    }
  }
)

</script>

<style scoped>
.analytics {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.positive {
  color: #1f883d;
}

.negative {
  color: #cf222e;
}

.num-value {
  font-size: 15px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.chart-card {
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
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

/* Charts row: equal height cards */
.charts-row {
  align-items: stretch;
}

.charts-row :deep(.el-col) {
  display: flex;
}

.charts-row :deep(.el-col > .el-card) {
  flex: 1;
}

/* Performance History chart */
.performance-chart-card :deep(.el-card__body) {
  min-height: 520px;
}

.performance-chart-card :deep(.chart-container) {
  height: 500px;
}

/* Asset Allocation card */
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

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin: 0;
}

.date-controls-top {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.benchmark-controls-top {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.benchmark-label {
  font-weight: 500;
  color: #606266;
}

.controls-top {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
}

.date-range-label {
  font-weight: 500;
  color: #606266;
}

.date-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.analytics-table :deep(.el-table__header th) {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
}

.analytics-table :deep(.el-table__body td) {
  font-size: 14px;
  padding: 12px 0;
}

.metrics-descriptions :deep(.el-descriptions__label) {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
}

.metrics-descriptions :deep(.el-descriptions__content) {
  font-size: 14px;
}

/* Asset Beta Search */
.asset-beta-search {
  margin-bottom: 16px;
}

.asset-beta-autocomplete {
  position: relative;
  width: 100%;
}

.asset-beta-search-input {
  width: 100%;
}

.asset-beta-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  max-height: 300px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  z-index: 100;
  margin-top: 4px;
}

.asset-beta-dropdown-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
  gap: 12px;
}

.asset-beta-dropdown-item:hover,
.asset-beta-dropdown-item.active {
  background-color: #f5f7fa;
}

.asset-beta-dropdown-item.selected {
  background-color: #ecf5ff;
}

.asset-beta-symbol {
  font-weight: 600;
  color: #409eff;
  min-width: 60px;
}

.asset-beta-name {
  color: #606266;
  flex: 1;
}

.asset-beta-dropdown-empty {
  padding: 20px;
  text-align: center;
  color: #909399;
  font-size: 14px;
}

.beta-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.asset-beta-section {
  margin-bottom: 20px;
}

.asset-beta-section:last-child {
  margin-bottom: 0;
}

.asset-beta-section-title {
  margin: 0 0 8px 0;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
</style>
