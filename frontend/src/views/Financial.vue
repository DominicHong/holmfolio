<template>
  <div class="financial">
    <div class="page-header">
      <div class="title-row">
        <h2 class="page-title">Financial</h2>
        <el-button :icon="Refresh" @click="handleRefresh" circle aria-label="Refresh" />
      </div>
      <div class="position-controls">
        <el-tooltip content="Select the date for viewing financial data" placement="top">
          <div>
            <el-date-picker
              v-model="selectedDate"
              type="date"
              placeholder="Select date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              :disabled-date="disabledDate"
              style="margin-right: 10px;"
            />
          </div>
        </el-tooltip>
        <el-button type="primary" @click="handleShowFinancials" :loading="loading" size="default">
          Show Financials
        </el-button>
        <el-button type="success" @click="handleFetchFinancials" :loading="loading" size="default" style="margin-left: 10px;">
          Fetch Financials
        </el-button>
      </div>
    </div>

    <div v-if="positions.length === 0 && !loading" class="empty-state-card">
      <div class="empty-state">
        <p>No financial data found.</p>
        <p>Select a date and click "Show Financials" to view cached data, or "Fetch Financials" to pull fresh data from THS.</p>
      </div>
    </div>

    <template v-else>
      <div v-if="positions.length > 0" class="positions-table-section">
        <div class="positions-table-header">
          <h3 class="positions-table-title">Stock Financials</h3>
          <el-button type="primary" @click="downloadPositionsCSV" class="download-btn">
            Download
          </el-button>
        </div>
        <SharedDataTable :data="positions" :columns="tableColumns" :loading="loading"
          :empty-text="'No positions found'" class="positions-table" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Financial' })
import { computed, ref, onMounted } from 'vue'
import { usePortfolioStore } from '../stores'
import { useUIStore } from '../stores'
import SharedDataTable from '../components/SharedDataTable.vue'
import { formatDate } from '../utils/formatters'
import { showError, showSuccess, handleApiError } from '../utils/errorHandler'
import { Refresh } from '@element-plus/icons-vue'
import apiClient from '@/utils/apiClient'

// Financial position interface
interface FinancialPosition {
  symbol: string
  name: string
  current_price: number
  dividend_after_tax: number
  dividend_yield: number
  pe: number | null
  pb: number | null
}

const portfolioStore = usePortfolioStore()
const uiStore = useUIStore()

const selectedDate = ref(formatDate(new Date()))
const positions = ref<FinancialPosition[]>([])

const loading = computed(() => uiStore.loading)
const currentPortfolio = computed(() => portfolioStore.currentPortfolio)

const tableColumns = computed(() => [
  { prop: 'symbol', label: 'Symbol', minWidth: '100' },
  { prop: 'name', label: 'Name', minWidth: '150' },
  { prop: 'current_price', label: 'Close Price', minWidth: '120', align: 'right', type: 'currency', sortable: true },
  { prop: 'dividend_after_tax', label: 'Dividend (After Tax)', minWidth: '150', align: 'right', type: 'currency', decimalPlaces: 4, sortable: true },
  { prop: 'dividend_yield', label: 'Dividend Yield', minWidth: '130', align: 'right', type: 'percentage', decimalPlaces: 2, sortable: true },
  { prop: 'pe', label: 'PE', minWidth: '80', align: 'right', sortable: true },
  { prop: 'pb', label: 'PB', minWidth: '80', align: 'right', sortable: true },
])

const disabledDate = (time: Date): boolean => {
  return time.getTime() > Date.now()
}

const initializePortfolio = async () => {
  try {
    if (!currentPortfolio.value) {
      await portfolioStore.fetchPortfolios()
    }
  } catch (error) {
    handleApiError(error, 'Failed to load portfolio data')
  }
}

const validateOperation = () => {
  if (!currentPortfolio.value) {
    showError('No portfolio selected')
    return false
  }

  if (!selectedDate.value) {
    showError('Please select a date')
    return false
  }

  return true
}

const handleShowFinancials = async () => {
  if (!validateOperation()) return
  const portfolio = currentPortfolio.value
  if (!portfolio) return

  try {
    uiStore.setLoading(true)
    const response = await apiClient.get(
      `/portfolios/${portfolio.id}/financial-positions`,
      { params: { as_of_date: selectedDate.value } }
    )
    positions.value = response.data
    if (response.data.length > 0) {
      showSuccess(`Found ${response.data.length} stock positions with financial data`)
    } else {
      showSuccess('No stock positions found for the selected date')
    }
  } catch (error) {
    handleApiError(error, 'Failed to fetch financial positions')
  } finally {
    uiStore.setLoading(false)
  }
}

const handleFetchFinancials = async () => {
  if (!validateOperation()) return
  const portfolio = currentPortfolio.value
  if (!portfolio) return

  try {
    uiStore.setLoading(true)
    const response = await apiClient.post(
      `/portfolios/${portfolio.id}/financial-positions`,
      null,
      { params: { as_of_date: selectedDate.value } }
    )
    positions.value = response.data
    if (response.data.length > 0) {
      showSuccess(`Fetched and saved financial data for ${response.data.length} stock positions`)
    } else {
      showSuccess('No stock positions found for the selected date')
    }
  } catch (error) {
    handleApiError(error, 'Failed to fetch financial positions from THS')
  } finally {
    uiStore.setLoading(false)
  }
}

const downloadPositionsCSV = () => {
  if (!positions.value || positions.value.length === 0) {
    showError('No positions to download')
    return
  }

  const headers = ['Symbol', 'Name', 'Close Price', 'Dividend (After Tax)', 'Dividend Yield', 'PE', 'PB']

  const rows = positions.value.map((pos: FinancialPosition) => {
    return [
      `"${pos.symbol || ''}"`,
      `"${pos.name || ''}"`,
      pos.current_price || 0,
      pos.dividend_after_tax || 0,
      pos.dividend_yield != null ? (pos.dividend_yield * 100).toFixed(2) + '%' : '0.00%',
      pos.pe != null ? pos.pe.toFixed(2) : '',
      pos.pb != null ? pos.pb.toFixed(2) : '',
    ].join(',')
  })

  const csvContent = [headers.join(','), ...rows].join('\n')
  const filename = `financial_positions_${selectedDate.value || 'today'}.csv`

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
  showSuccess('Positions downloaded successfully')
}

// Refresh
const handleRefresh = () => {
  handleShowFinancials()
}

onMounted(() => {
  initializePortfolio()
})
</script>

<style scoped>
.financial {
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

.positions-table-section {
  margin-bottom: 32px;
  background: #ffffff;
  border-radius: 16px;
  border: none;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.positions-table-section:hover {
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.positions-table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  border-bottom: none;
}

.positions-table-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 10px;
  letter-spacing: 0.5px;
}

.positions-table-title::before {
  content: '';
  width: 4px;
  height: 20px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 2px;
}

.download-btn {
  border-radius: 8px;
}
</style>
