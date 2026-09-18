<template>
  <div class="settings">
    <div class="page-header">
      <div class="title-row">
        <h2 class="page-title">Settings</h2>
        <el-button :icon="Refresh" @click="handleRefresh" circle aria-label="Refresh" />
      </div>
    </div>
    
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>Data Update</span>
          </template>

          <el-form label-width="120px">
            <el-form-item label="End Date">
              <el-date-picker
                id="update-end-date"
                v-model="updateEndDate"
                type="date"
                placeholder="Select end date"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width: 100%"
                :disabled="updatingData"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                @click="updatePricesAndRates"
                :loading="updatingData"
                :disabled="updatingData"
              >
                {{ updatingData ? 'Updating...' : 'Update Prices & Rates' }}
              </el-button>
            </el-form-item>
          </el-form>

          <el-alert
            v-if="updateResult"
            :title="updateResult.message"
            :type="updateResult.success ? 'success' : 'error'"
            :description="updateResult.errors && updateResult.errors.length > 0 ? updateResult.errors.join('; ') : undefined"
            show-icon
            closable
            @close="updateResult = null"
            style="margin-top: 15px;"
          />

          <div v-if="updateResult && updateResult.success" style="margin-top: 10px;">
            <el-tag type="success">Prices added: {{ updateResult.prices_added }}</el-tag>
            <el-tag type="success" style="margin-left: 10px;">Rates added: {{ updateResult.rates_added }}</el-tag>
            <el-tag type="success" style="margin-left: 10px;">Benchmark prices added: {{ updateResult.benchmark_prices_added }}</el-tag>
          </div>
        </el-card>

        <el-card style="margin-top: 20px;">
          <template #header>
            <span>Currency Settings</span>
          </template>

          <el-form :model="currencySettings" label-width="120px">
            <el-form-item label="Primary Currency">
              <el-select id="primary-currency" v-model="currencySettings.primary_currency" style="width: 100%">
                <el-option v-for="currency in currencies" :key="currency.id" :label="currency.code" :value="currency.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="Display Format">
              <el-radio-group id="display-format" v-model="currencySettings.display_format">
                <el-radio value="primary">Primary Currency</el-radio>
                <el-radio value="original">Original Currency</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveCurrencySettings">Save</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card style="margin-top: 20px;">
          <template #header>
            <span>Portfolio Settings</span>
          </template>

          <el-form :model="portfolioSettings" label-width="120px">
            <el-form-item label="Tax Rate">
              <el-input-number id="tax-rate" v-model="portfolioSettings.tax_rate" :precision="2" :min="0" :max="100" />
              <span style="margin-left: 10px;">%</span>
            </el-form-item>
            <el-form-item label="Risk-Free Rate">
              <el-input-number id="risk-free-rate" v-model="portfolioSettings.risk_free_rate" :precision="2" :min="0" :max="100" />
              <span style="margin-left: 10px;">%</span>
            </el-form-item>
            <el-form-item label="Gold Initial Capital">
              <el-input-number id="gold-initial-capital" v-model="portfolioSettings.gold_initial_capital" :precision="2" :min="0" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="savePortfolioSettings">Save</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card style="margin-top: 20px;">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>Benchmarks</span>
              <el-button type="primary" size="small" @click="showAddBenchmarkDialog = true">Add</el-button>
            </div>
          </template>

          <el-table :data="referenceStore.benchmarks" style="width: 100%" v-loading="loadingBenchmarks">
            <el-table-column prop="symbol" label="Symbol" width="120" />
            <el-table-column prop="name" label="Name" />
            <el-table-column prop="description" label="Description" show-overflow-tooltip />
            <el-table-column label="Type" width="110">
              <template #default="scope">
                <el-tag v-if="scope.row.is_composite" type="warning" size="small">Composite</el-tag>
                <el-tag v-else type="info" size="small">Single</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Components" min-width="200">
              <template #default="scope">
                <div v-if="scope.row.is_composite && scope.row.components && scope.row.components.length > 0">
                  <el-tag
                    v-for="comp in scope.row.components"
                    :key="comp.id"
                    type="primary"
                    size="small"
                    style="margin-right: 5px; margin-bottom: 3px"
                  >
                    {{ getBenchmarkName(comp.component_benchmark_id) }} {{ (comp.weight * 100).toFixed(0) }}%
                  </el-tag>
                </div>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="150">
              <template #default="scope">
                <el-button size="small" @click="editBenchmark(scope.row)">Edit</el-button>
                <el-button size="small" type="danger" @click="deleteBenchmark(scope.row)">Delete</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <span>Exchange Rates</span>
          </template>

          <el-form :inline="true" style="margin-bottom: 15px;">
            <el-form-item label="Currency Pair">
              <el-select id="currency-pair" v-model="selectedCurrencyPair" style="width: 150px">
                <el-option
                  v-for="pair in currencyPairs"
                  :key="pair"
                  :label="pair"
                  :value="pair"
                />
              </el-select>
            </el-form-item>
          </el-form>

          <el-table :data="paginatedExchangeRates" style="width: 100%">
            <el-table-column prop="currency_code" label="From" width="100" />
            <el-table-column prop="target_currency_code" label="To" width="100" />
            <el-table-column prop="rate" label="Rate" align="right" :formatter="(row: any) => Number(row.rate).toFixed(4)" />
            <el-table-column prop="rate_date" label="Date" width="120" />
            <el-table-column label="Actions" width="100">
              <template #default="scope">
                <el-button size="small" @click="editRate(scope.row)">Edit</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="totalExchangeRates"
            layout="total, sizes, prev, pager, next"
            style="margin-top: 15px;"
          />

          <div style="margin-top: 20px;">
            <el-button type="primary" @click="showAddRateDialog = true">Add Rate</el-button>
            <el-button @click="importRates">Import from CSV</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- Add Exchange Rate Dialog -->
    <el-dialog v-model="showAddRateDialog" title="Add Exchange Rate" width="400px">
      <el-form :model="rateForm" ref="rateFormRef">
        <el-form-item label="Currency" prop="currency_id">
          <el-select id="rate-currency" v-model="rateForm.currency_id" style="width: 100%">
            <el-option v-for="currency in currencies" :key="currency.id" :label="currency.code" :value="currency.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Rate" prop="rate">
          <el-input-number id="rate-value" v-model="rateForm.rate" :precision="4" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Date" prop="rate_date">
          <el-date-picker
            id="rate-date"
            v-model="rateForm.rate_date"
            type="date"
            placeholder="Select date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddRateDialog = false">Cancel</el-button>
        <el-button type="primary" @click="saveRate">Save</el-button>
      </template>
    </el-dialog>

    <!-- Add/Edit Benchmark Dialog -->
    <el-dialog v-model="showAddBenchmarkDialog" :title="editingBenchmark ? 'Edit Benchmark' : 'Add Benchmark'" width="600px">
      <el-form :model="benchmarkForm" ref="benchmarkFormRef" label-width="100px">
        <el-form-item label="Symbol" prop="symbol" required>
          <el-input id="benchmark-symbol" v-model="benchmarkForm.symbol" placeholder="e.g., 000300.SH" />
        </el-form-item>
        <el-form-item label="Name" prop="name" required>
          <el-input id="benchmark-name" v-model="benchmarkForm.name" placeholder="e.g., CSI 300" />
        </el-form-item>
        <el-form-item label="Description" prop="description">
          <el-input id="benchmark-description" v-model="benchmarkForm.description" type="textarea" placeholder="Optional description" />
        </el-form-item>
        <el-form-item label="Composite">
          <el-checkbox v-model="benchmarkForm.is_composite">Is Composite Benchmark</el-checkbox>
        </el-form-item>

        <template v-if="benchmarkForm.is_composite">
          <el-divider content-position="left">Components</el-divider>
          <div v-for="(component, index) in benchmarkForm.components" :key="index" class="component-row">
            <el-form-item :label="`#${index + 1}`" style="margin-bottom: 10px;">
              <el-select
                v-model="component.component_benchmark_id"
                placeholder="Select benchmark"
                style="width: 220px"
                filterable
              >
                <el-option
                  v-for="b in availableComponents"
                  :key="b.id"
                  :label="b.name"
                  :value="b.id"
                />
              </el-select>
              <el-input-number
                v-model="component.weight"
                :precision="4"
                :min="0"
                :max="1"
                style="width: 130px; margin-left: 10px"
                placeholder="Weight"
              />
              <el-button
                type="danger"
                size="small"
                @click="removeComponent(index)"
                style="margin-left: 10px"
              >
                Remove
              </el-button>
            </el-form-item>
          </div>
          <div style="display: flex; align-items: center; gap: 10px; margin-top: 10px;">
            <el-button type="primary" size="small" @click="addComponent">Add Component</el-button>
            <span
              :style="{ color: Math.abs(totalComponentWeight - 1.0) <= 0.0001 ? '#67C23A' : '#F56C6C', fontWeight: 500 }"
            >
              Total Weight: {{ (totalComponentWeight * 100).toFixed(2) }}%
            </span>
          </div>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="closeBenchmarkDialog">Cancel</el-button>
        <el-button type="primary" @click="saveBenchmark">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Settings' })
import { ref, computed, onMounted } from 'vue'
import { useReferenceStore } from '../stores'
import { useUIStore } from '../stores'
import type { ExchangeRate } from '../types/models'
import { showSuccess, handleApiError } from '../utils/errorHandler'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

// Pinia stores
const referenceStore = useReferenceStore()
const uiStore = useUIStore()

// Reactive data
const showAddRateDialog = ref(false)
const currencySettings = ref({
  primary_currency: 1,
  display_format: 'primary'
})
const portfolioSettings = ref({
  tax_rate: 0.2,
  risk_free_rate: 1.5,
  gold_initial_capital: 1000000
})
const rateForm = ref({
  currency_id: null,
  rate: null,
  rate_date: null
})
const exchangeRates = ref<ExchangeRate[]>([])
const selectedCurrencyPair = ref('HKD/CNY')
const currentPage = ref(1)
const pageSize = ref(10)

// Data update related
interface UpdateResult {
  success: boolean
  message: string
  errors?: string[]
  prices_added?: number
  rates_added?: number
  benchmark_prices_added?: number
}

const updateEndDate = ref(dayjs().format('YYYY-MM-DD'))
const updatingData = ref(false)
const updateResult = ref<UpdateResult | null>(null)

// Benchmark related
const showAddBenchmarkDialog = ref(false)
const loadingBenchmarks = ref(false)
const editingBenchmark = ref<Record<string, any> | null>(null)
interface BenchmarkComponent {
  component_benchmark_id: number | null
  weight: number
}

interface BenchmarkFormData {
  symbol: string
  name: string
  description: string
  is_composite: boolean
  components: BenchmarkComponent[]
}

const benchmarkForm = ref<BenchmarkFormData>({
  symbol: '',
  name: '',
  description: '',
  is_composite: false,
  components: []
})

// Computed properties
const currencies = computed(() => referenceStore.currencies)

// Computed property for unique currency pairs
const currencyPairs = computed(() => {
  const pairs = new Set()
  exchangeRates.value.forEach(rate => {
    const fromCode = currencies.value.find(c => c.id === rate.from_currency_id)?.code || ''
    const toCode = currencies.value.find(c => c.id === rate.to_currency_id)?.code || ''
    if (fromCode && toCode) {
      pairs.add(`${fromCode}/${toCode}`)
    }
  })
  return Array.from(pairs).sort()
})

// Computed property for filtered exchange rates based on selected pair
const filteredExchangeRates = computed(() => {
  if (!selectedCurrencyPair.value) return exchangeRates.value

  const [fromCode, toCode] = selectedCurrencyPair.value.split('/')
  const fromCurrency = currencies.value.find(c => c.code === fromCode)
  const toCurrency = currencies.value.find(c => c.code === toCode)

  if (!fromCurrency || !toCurrency) return exchangeRates.value

  // Filter by currency pair and sort by date (newest first)
  const filtered = exchangeRates.value.filter(rate =>
    rate.from_currency_id === fromCurrency.id &&
    rate.to_currency_id === toCurrency.id
  ).map(rate => ({
    ...rate,
    currency_code: fromCode,
    target_currency_code: toCode
  }))

  // Sort by rate_date descending (newest first)
  filtered.sort((a: any, b: any) => new Date(b.rate_date || '').getTime() - new Date(a.rate_date || '').getTime())

  return filtered
})

// Computed property for paginated exchange rates
const paginatedExchangeRates = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredExchangeRates.value.slice(start, end)
})

// Computed property for total count
const totalExchangeRates = computed(() => filteredExchangeRates.value.length)

// Methods
const saveRate = () => {
  showAddRateDialog.value = false
  showSuccess('Exchange rate saved')
}

const editRate = (_rate: Record<string, any>): void => {
  showSuccess('Edit rate functionality to be implemented')
}

const importRates = () => {
  showSuccess('Import rates functionality to be implemented')
}

const updatePricesAndRates = async () => {
  try {
    updatingData.value = true
    updateResult.value = null

    // Format date as YYYY-MM-DD
    const formattedDate = dayjs(updateEndDate.value).format('YYYY-MM-DD')

    const result = await uiStore.updatePricesAndRates(formattedDate)
    updateResult.value = result

    // Refresh exchange rates after update
    if (result.success) {
      await loadExchangeRates()
    }
  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error)
    updateResult.value = {
      success: false,
      message: 'Failed to update prices and rates',
      errors: [errMsg]
    }
  } finally {
    updatingData.value = false
  }
}

// Methods
const saveCurrencySettings = async () => {
  try {
    await uiStore.saveSetting('primary_currency', currencySettings.value.primary_currency, 'Primary currency for display')
    await uiStore.saveSetting('display_format', currencySettings.value.display_format, 'Currency display format')
    showSuccess('Currency settings saved')
  } catch (error) {
    handleApiError(error, 'Failed to save currency settings')
  }
}

const savePortfolioSettings = async () => {
  try {
    // Convert tax rate from percentage to decimal before saving
    const taxRateDecimal = portfolioSettings.value.tax_rate / 100
    await uiStore.saveSetting('tax_rate', taxRateDecimal, 'Tax rate percentage')
    // Convert risk-free rate from percentage to decimal before saving
    const riskFreeRateDecimal = portfolioSettings.value.risk_free_rate / 100
    await uiStore.saveSetting('risk_free_rate', riskFreeRateDecimal, 'Risk-free rate for calculations')
    await uiStore.saveSetting(
      'gold_initial_capital',
      portfolioSettings.value.gold_initial_capital,
      'Initial capital for the gold account normalized NAV'
    )
    showSuccess('Portfolio settings saved')
  } catch (error) {
    handleApiError(error, 'Failed to save portfolio settings')
  }
}

const loadSettings = async () => {
  try {
    await uiStore.fetchSettings()

    // Load currency settings
    if (uiStore.settings.primary_currency) {
      currencySettings.value.primary_currency = parseInt(uiStore.settings.primary_currency.value)
    }
    if (uiStore.settings.display_format) {
      currencySettings.value.display_format = uiStore.settings.display_format.value
    }

    // Load portfolio settings
    if (uiStore.settings.tax_rate) {
      // Convert tax rate from decimal to percentage for display
      portfolioSettings.value.tax_rate = parseFloat(uiStore.settings.tax_rate.value) * 100
    }
    if (uiStore.settings.risk_free_rate) {
      // Convert risk-free rate from decimal to percentage for display
      portfolioSettings.value.risk_free_rate = parseFloat(uiStore.settings.risk_free_rate.value) * 100
    }
    if (uiStore.settings.gold_initial_capital) {
      portfolioSettings.value.gold_initial_capital = parseFloat(uiStore.settings.gold_initial_capital.value)
    }
  } catch (error) {
    handleApiError(error, 'Failed to load settings')
  }
}

const loadExchangeRates = async () => {
  try {
    await referenceStore.fetchExchangeRates()
    exchangeRates.value = referenceStore.exchangeRates
  } catch (error) {
    handleApiError(error, 'Failed to load exchange rates')
  }
}

// Benchmark methods
const loadBenchmarks = async () => {
  try {
    loadingBenchmarks.value = true
    await referenceStore.fetchBenchmarks()
  } catch (error) {
    handleApiError(error, 'Failed to load benchmarks')
  } finally {
    loadingBenchmarks.value = false
  }
}

const closeBenchmarkDialog = () => {
  showAddBenchmarkDialog.value = false
  editingBenchmark.value = null
  benchmarkForm.value = {
    symbol: '',
    name: '',
    description: '',
    is_composite: false,
    components: []
  }
}

const editBenchmark = (benchmark: Record<string, any>): void => {
  editingBenchmark.value = benchmark
  benchmarkForm.value = {
    symbol: benchmark.symbol,
    name: benchmark.name,
    description: benchmark.description || '',
    is_composite: benchmark.is_composite || false,
    components: benchmark.components
      ? benchmark.components.map((c: { component_benchmark_id: number; weight: number }) => ({
          component_benchmark_id: c.component_benchmark_id,
          weight: c.weight
        }))
      : []
  }
  showAddBenchmarkDialog.value = true
}

const saveBenchmark = async () => {
  try {
    if (!benchmarkForm.value.symbol || !benchmarkForm.value.name) {
      handleApiError(new Error('Symbol and name are required'), 'Validation Error')
      return
    }

    if (benchmarkForm.value.is_composite) {
      if (benchmarkForm.value.components.length === 0) {
        handleApiError(new Error('Composite benchmark must have at least one component'), 'Validation Error')
        return
      }
      if (Math.abs(totalComponentWeight.value - 1.0) > 0.0001) {
        handleApiError(new Error(`Component weights must sum to 100%. Current: ${(totalComponentWeight.value * 100).toFixed(2)}%`), 'Validation Error')
        return
      }
    }

    const data = {
      symbol: benchmarkForm.value.symbol,
      name: benchmarkForm.value.name,
      description: benchmarkForm.value.description || null,
      is_composite: benchmarkForm.value.is_composite,
      components: benchmarkForm.value.is_composite ? benchmarkForm.value.components : []
    }

    if (editingBenchmark.value) {
      await (referenceStore as any).updateBenchmark(editingBenchmark.value.id, data)
      showSuccess('Benchmark updated successfully')
    } else {
      await (referenceStore as any).createBenchmark(data)
      showSuccess('Benchmark created successfully')
    }

    closeBenchmarkDialog()
    await loadBenchmarks()
  } catch (error) {
    handleApiError(error, 'Failed to save benchmark')
  }
}

const availableComponents = computed(() => {
  const selectedIds = new Set(
    benchmarkForm.value.components
      .filter(c => c.component_benchmark_id != null)
      .map(c => c.component_benchmark_id)
  )
  return referenceStore.benchmarks.filter(b => {
    if (editingBenchmark.value && b.id === editingBenchmark.value.id) return false
    if (b.is_composite) return false
    if (selectedIds.has(b.id)) return false
    return true
  })
})

const totalComponentWeight = computed(() => {
  if (!benchmarkForm.value.components) return 0
  return benchmarkForm.value.components.reduce((sum, c) => sum + (c.weight || 0), 0)
})

const addComponent = () => {
  benchmarkForm.value.components.push({
    component_benchmark_id: null,
    weight: 0
  })
}

const removeComponent = (index: number): void => {
  benchmarkForm.value.components.splice(index, 1)
}

const getBenchmarkName = (id: number): string => {
  const b = referenceStore.benchmarks.find((bm: { id: number; name: string }) => bm.id === id)
  return b ? b.name : String(id)
}

const deleteBenchmark = async (benchmark: Record<string, any>): Promise<void> => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete benchmark "${benchmark.name}"?`,
      'Confirm Delete',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning'
      }
    )
    await (referenceStore as any).deleteBenchmark(benchmark.id)
    showSuccess('Benchmark deleted successfully')
    await loadBenchmarks()
  } catch (error) {
    if (error !== 'cancel') {
      handleApiError(error, 'Failed to delete benchmark')
    }
  }
}

// Refresh
const handleRefresh = async () => {
  await referenceStore.fetchCurrencies()
  await loadSettings()
  await loadExchangeRates()
  await loadBenchmarks()
}

// Lifecycle
onMounted(async () => {
  await referenceStore.fetchCurrencies()
  await loadSettings()
  await loadExchangeRates()
  await loadBenchmarks()
})
</script>

<style scoped>
.settings {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  gap: 12px;
}

.el-card {
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
}

.el-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-bottom: 1px solid #e6e6e6;
}

.component-row {
  background-color: #f8f9fa;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 8px;
}
</style>