<template>
  <div class="transactions">
    <div class="page-header">
      <div class="title-row">
        <h2 class="page-title">Transaction Management</h2>
        <el-button :icon="Refresh" @click="handleRefresh" circle aria-label="Refresh" />
      </div>
    </div>

    <!-- Filters -->
    <el-card class="filter-card">
      <el-row :gutter="28">
        <el-col :span="5">
          <el-select
            v-model="filters.action"
            placeholder="Select Action"
            multiple
            clearable
            collapse-tags
            style="width: 100%"
          >
            <el-option label="Buy" value="buy" />
            <el-option label="Sell" value="sell" />
            <el-option label="Dividends" value="dividends" />
            <el-option label="Cash In" value="cash_in" />
            <el-option label="Cash Out" value="cash_out" />
          </el-select>
        </el-col>
        <el-col :span="9">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="To"
            start-placeholder="Start date"
            end-placeholder="End date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-col>
        <el-col :span="5">
          <el-input v-model="filters.symbol" placeholder="Symbol" clearable style="width: 100%" />
        </el-col>
        <el-col :span="5">
          <el-button @click="resetFilters" style="width: 100%">Reset</el-button>
        </el-col>
      </el-row>
      <el-row :gutter="20" class="filter-actions-row">
        <el-col :span="24">
          <div class="filter-actions">
            <el-button type="primary" @click="showAddDialog = true">
              <el-icon><Plus /></el-icon>
              Add Transaction
            </el-button>
            <el-button type="warning" @click="showXueqiuImportDialog = true">
              <el-icon><Upload /></el-icon>
              Import Xueqiu
            </el-button>
            <el-button type="info" @click="showAlignDialog = true">
              <el-icon><RefreshRight /></el-icon>
              Align to Xueqiu
            </el-button>
            <el-button type="success" :loading="checkingDividends" @click="handleCheckDividends">
              <el-icon><Coin /></el-icon>
              Check Dividends/Splits
            </el-button>
            <el-button type="danger" @click="confirmDeleteAll">
              <el-icon><Delete /></el-icon>
              Delete All
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <!-- Transactions Table -->
    <el-card>
      <SharedDataTable 
        :data="filteredTransactions" 
        :columns="tableColumns" 
        :loading="loading"
        @action="handleTableAction"
      >
        <template #symbol="{ row }">
          {{ getAssetSymbol(row.asset_id) }}
        </template>
        <template #name="{ row }">
          {{ getAssetName(row.asset_id) }}
        </template>
      </SharedDataTable>
    </el-card>
    
    <!-- Add/Edit Transaction Dialog -->
    <el-dialog v-model="showAddDialog" :title="isEditing ? 'Edit Transaction' : 'Add Transaction'" width="600px">
      <el-form :model="transactionForm" :rules="transactionRules" ref="transactionFormRef">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="Date" prop="trade_date">
              <el-date-picker
                v-model="transactionForm.trade_date"
                type="date"
                placeholder="Select date"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Action" prop="action">
              <el-select v-model="transactionForm.action" style="width: 100%">
                <el-option label="Buy" value="buy" />
                <el-option label="Sell" value="sell" />
                <el-option label="Dividends" value="dividends" />
                <el-option label="Cash In" value="cash_in" />
                <el-option label="Cash Out" value="cash_out" />
                <el-option label="Interest" value="interest" />
                <el-option label="Split" value="split" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="Asset" prop="asset_id">
              <el-select v-model="transactionForm.asset_id" filterable placeholder="Select Asset" style="width: 100%">
                <el-option
                  v-for="asset in assets"
                  :key="asset.id"
                  :label="asset.symbol + ' - ' + asset.name"
                  :value="asset.id">
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Quantity" prop="quantity">
              <el-input-number v-model="transactionForm.quantity" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="Price" prop="price">
              <el-input-number v-model="transactionForm.price" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Amount" prop="amount">
              <el-input-number v-model="transactionForm.amount" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="Fees" prop="fees">
              <el-input-number v-model="transactionForm.fees" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Currency" prop="currency_id">
              <el-select v-model="transactionForm.currency_id" style="width: 100%">
                <el-option v-for="currency in currencies" :key="currency.id" :label="currency.code" :value="currency.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="Notes" prop="notes">
          <el-input v-model="transactionForm.notes" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">Cancel</el-button>
        <el-button type="primary" @click="saveTransaction">{{ isEditing ? 'Update' : 'Save' }}</el-button>
      </template>
    </el-dialog>
    
    <!-- Import Xueqiu Dialog -->
    <el-dialog v-model="showXueqiuImportDialog" title="Import Xueqiu Transactions" width="500px">
      <el-upload
        class="upload-demo"
        drag
        action=""
        :before-upload="handleXueqiuImportFile"
        accept=".csv"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          Drop Xueqiu CSV file here or <em>click to upload</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            Xueqiu CSV file with Chinese columns: 日期, 类型, 代码, 名称, 成交价, 数量, 金额, 说明
            <br>
            <small>Assets will be auto-created if not exist. .SZ/.SH → CNY, .HK → HKD</small>
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showXueqiuImportDialog = false">Close</el-button>
      </template>
    </el-dialog>

    <!-- Align to Xueqiu Dialog -->
    <el-dialog v-model="showAlignDialog" title="Align to Xueqiu" width="500px">
      <el-alert
        title="This will delete all existing transactions and replace them with data from the Xueqiu zip file."
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      />
      <el-upload
        class="upload-demo"
        drag
        action=""
        :before-upload="handleXueqiuAlignFile"
        accept=".zip"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          Drop Xueqiu zip file here or <em>click to upload</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            Xueqiu zip file containing a CSV with trade records (交易记录) and transfer records (转账记录).
            <br>
            <small>All existing transactions will be deleted. Positions will be recalculated automatically.</small>
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showAlignDialog = false">Close</el-button>
      </template>
    </el-dialog>

    <!-- Check Dividends/Splits Dialog -->
    <el-dialog v-model="showDividendCheckDialog" title="Check Dividends/Splits" width="960px">
      <template v-if="dividendCheckResult">
        <el-alert
          :title="`Checked ${dividendCheckResult.assets_checked} assets, found ${dividendCheckResult.dividend_events_found} dividend events, ${dividendCheckResult.missing.length} missing.`"
          :type="dividendCheckResult.missing.length > 0 ? 'warning' : 'success'"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        />
        <el-table
          :data="dividendCheckResult.missing"
          @selection-change="handleDividendSelectionChange"
          max-height="420"
          style="width: 100%"
        >
          <el-table-column type="selection" width="40" />
          <el-table-column prop="symbol" label="Symbol" min-width="100" />
          <el-table-column prop="name" label="Name" min-width="130" show-overflow-tooltip />
          <el-table-column prop="received_date" label="Dividend Date" min-width="110" />
          <el-table-column prop="record_date" label="Record Date" min-width="110" />
          <el-table-column prop="per_share" label="Per Share" min-width="90" align="right" />
          <el-table-column prop="quantity" label="Quantity" min-width="90" align="right" />
          <el-table-column prop="amount" label="Amount" min-width="100" align="right" />
          <el-table-column prop="currency" label="CCY" min-width="60" />
          <el-table-column prop="scheme" label="Scheme" min-width="150" show-overflow-tooltip />
        </el-table>
      </template>
      <template #footer>
        <el-button @click="showDividendCheckDialog = false">Close</el-button>
        <el-button
          type="primary"
          :disabled="selectedMissingItems.length === 0"
          :loading="addingDividends"
          @click="addSelectedDividends"
        >
          Add Selected ({{ selectedMissingItems.length }})
        </el-button>
        <el-button
          type="primary"
          :disabled="!dividendCheckResult || dividendCheckResult.missing.length === 0"
          :loading="addingDividends"
          @click="addAllDividends"
        >
          Add All
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Transactions' })
import { ref, computed, reactive, onMounted } from 'vue'
import { useTransactionStore } from '../stores'
import { useReferenceStore } from '../stores'
import { usePortfolioStore } from '../stores'
import { useAssetStore } from '../stores'
import { useUIStore } from '../stores'
import type { Transaction, Asset, MissingDividendItem, CheckDividendsResponse } from '../types/models'
import dayjs from 'dayjs'
import SharedDataTable from '../components/SharedDataTable.vue'
import { ElMessageBox } from 'element-plus'
import { showError, showSuccess, showWarning, handleApiError } from '../utils/errorHandler'
import { Refresh } from '@element-plus/icons-vue'

// Stores
const transactionStore = useTransactionStore()
const referenceStore = useReferenceStore()
const portfolioStore = usePortfolioStore()
const assetStore = useAssetStore()
const uiStore = useUIStore()

// Reactive state
const showAddDialog = ref(false)
const showXueqiuImportDialog = ref(false)
const showAlignDialog = ref(false)
const showDividendCheckDialog = ref(false)
const dividendCheckResult = ref<CheckDividendsResponse | null>(null)
const selectedMissingItems = ref<MissingDividendItem[]>([])
const checkingDividends = ref(false)
const addingDividends = ref(false)
const transactionFormRef = ref()
const isEditing = ref(false)
const editingTransactionId = ref<number | null>(null)

const filters = reactive<{
  action: string[]
  dateRange: [string, string] | []
  symbol: string
}>({
  action: [],
  dateRange: [],
  symbol: ''
})

interface TransactionFormData {
  trade_date: string | null
  action: string
  asset_id: number | null
  quantity: number | null
  price: number | null
  amount: number | null
  fees: number
  currency_id: number
  notes: string
  portfolio_id?: number
}

const transactionForm = reactive<TransactionFormData>({
  trade_date: null,
  action: '',
  asset_id: null,
  quantity: null,
  price: null,
  amount: null,
  fees: 0,
  currency_id: 1,
  notes: ''
})

const transactionRules = {
  trade_date: [{ required: true, message: 'Please select date', trigger: 'change' }],
  action: [{ required: true, message: 'Please select action', trigger: 'change' }],
  asset_id: [{ required: true, message: 'Please select an asset', trigger: 'change' }],
  amount: [{ required: true, message: 'Please enter amount', trigger: 'blur' }]
}

// Computed properties
const transactions = computed(() => transactionStore.transactions)
const currencies = computed(() => referenceStore.currencies)
const loading = computed(() => uiStore.loading)
const assets = computed(() => assetStore.assets)
const currentPortfolio = computed(() => portfolioStore.currentPortfolio)

const actionTagTypeMap = computed(() => ({
  'buy': 'success',
  'sell': 'danger',
  'dividends': 'info',
  'cash_in': 'success',
  'cash_out': 'warning',
  'interest': 'info',
  'split': 'warning'
}))

const tableColumns = computed(() => [
  { prop: 'trade_date', label: 'Date', minWidth: '120', sortable: true, type: 'date' },
  { prop: 'action', label: 'Action', minWidth: '100', type: 'tag', tagTypeMap: actionTagTypeMap.value },
  { prop: 'symbol', label: 'Symbol', minWidth: '100', type: 'custom' },
  { prop: 'name', label: 'Name', minWidth: '150', type: 'custom' },
  { prop: 'quantity', label: 'Quantity', minWidth: '100', align: 'right', type: 'quantity' },
  { prop: 'price', label: 'Price', minWidth: '100', align: 'right', type: 'currency' },
  { prop: 'amount', label: 'Amount', minWidth: '120', align: 'right', type: 'currency', decimalPlaces: 0 },
  { prop: 'fees', label: 'Fees', minWidth: '100', align: 'right', type: 'currency' },
  { prop: 'notes', label: 'Notes', minWidth: '150' },
  { 
    prop: 'actions', 
    label: 'Actions', 
    minWidth: '180', 
    type: 'actions',
    actions: [
      { name: 'edit', label: 'Edit', size: 'small', type: 'primary' },
      { name: 'delete', label: 'Delete', size: 'small', type: 'danger' }
    ]
  }
])

const filteredTransactions = computed(() => {
  let filtered = [...transactions.value]
  
  if (filters.action.length > 0) {
    filtered = filtered.filter(t => filters.action.includes(t.action))
  }
  
  if (filters.symbol) {
    const symbolFilter = filters.symbol.toLowerCase()
    filtered = filtered.filter(t => {
      const symbol = getAssetSymbol(t.asset_id)
      return symbol && symbol.toLowerCase().includes(symbolFilter)
    })
  }
  
  if (filters.dateRange && filters.dateRange.length === 2) {
    const [startDate, endDate] = filters.dateRange
    filtered = filtered.filter(t => {
      const date = dayjs(t.trade_date)
      return date.isAfter(startDate, 'day') && date.isBefore(endDate, 'day')
    })
  }
  
  return filtered.sort((a, b) => dayjs(b.trade_date).valueOf() - dayjs(a.trade_date).valueOf())
})

// Methods
const initializeData = async () => {
  try {
    await portfolioStore.fetchPortfolios()
    const portfolioId = currentPortfolio.value?.id
    if (!portfolioId) {
      showError("No portfolio is provided.")
      return
    }
    await Promise.all([
      transactionStore.fetchTransactions(portfolioId),
      referenceStore.fetchCurrencies(),
      assetStore.fetchAssets()
    ])
  } catch (error) {
    handleApiError(error, 'Failed to load data')
  }
}

const getAssetSymbol = (assetId: number | null): string => {
  if (!assetId || !assetStore.assets) return 'N/A'
  const asset = assetStore.assets.find((a: Asset) => a.id === assetId)
  return asset ? asset.symbol : 'Unknown'
}

const getAssetName = (assetId: number | null): string => {
  if (!assetId || !assetStore.assets) return 'N/A'
  const asset = assetStore.assets.find((a: Asset) => a.id === assetId)
  return asset ? asset.name : 'Unknown'
}

const handleTableAction = (actionName: string, row: Record<string, any>): void => {
  if (actionName === 'edit') {
    editTransaction(row as Transaction)
  } else if (actionName === 'delete') {
    deleteTransaction(row as Transaction)
  }
}

const resetFilters = () => {
  filters.action = []
  filters.dateRange = []
  filters.symbol = ''
}

const saveTransaction = async () => {
  try {
    if (!transactionFormRef.value) return

    const valid = await transactionFormRef.value.validate()
    if (!valid) return

    const portfolioId = currentPortfolio.value?.id
    if (!portfolioId) {
      showWarning('Please select a portfolio first')
      return
    }

    const transactionData = {
      ...transactionForm,
      portfolio_id: portfolioId
    }

    if (isEditing.value && editingTransactionId.value !== null) {
      await transactionStore.updateTransaction(editingTransactionId.value, transactionData as any)
      showSuccess('Transaction updated successfully')
    } else {
      await transactionStore.createTransaction(transactionData as any)
      showSuccess('Transaction saved successfully')
    }

    showAddDialog.value = false
    resetTransactionForm()
    // Refresh transactions after creating a new one
    await transactionStore.fetchTransactions(portfolioId)
  } catch (error) {
    handleApiError(error, 'Failed to save transaction')
  }
}

const resetTransactionForm = () => {
  transactionForm.trade_date = null
  transactionForm.action = ''
  transactionForm.asset_id = null
  transactionForm.quantity = null
  transactionForm.price = null
  transactionForm.amount = null
  transactionForm.fees = 0
  transactionForm.currency_id = 1
  transactionForm.notes = ''
  isEditing.value = false
  editingTransactionId.value = null
}

const editTransaction = (transaction: Transaction): void => {
  isEditing.value = true
  editingTransactionId.value = transaction.id
  transactionForm.trade_date = transaction.trade_date
  transactionForm.action = transaction.action
  transactionForm.asset_id = transaction.asset_id
  transactionForm.quantity = transaction.quantity ?? null
  transactionForm.price = transaction.price ?? null
  transactionForm.amount = transaction.amount ?? null
  transactionForm.fees = transaction.fees || 0
  transactionForm.currency_id = transaction.currency_id ?? 1
  transactionForm.notes = transaction.notes || ''
  showAddDialog.value = true
}

const deleteTransaction = async (transaction: Transaction): Promise<void> => {
  try {
    await ElMessageBox.confirm(
      'This will permanently delete this transaction. This action cannot be undone.',
      'Delete Transaction',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )

    await transactionStore.deleteTransaction(transaction.id)
    showSuccess('Transaction deleted successfully')
  } catch (error) {
    if (error !== 'cancel') {
      handleApiError(error, 'Failed to delete transaction')
    }
  }
}

const confirmDeleteAll = async () => {
  try {
    const portfolioId = currentPortfolio.value?.id
    if (!portfolioId) {
      showWarning('Please select a portfolio first')
      return
    }

    await ElMessageBox.confirm(
      'This will permanently delete all transactions. This action cannot be undone.',
      'Delete All Transactions',
      {
        confirmButtonText: 'Delete All',
        cancelButtonText: 'Cancel',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )

    await transactionStore.deleteAllTransactions(portfolioId)
    showSuccess('All transactions deleted successfully')
  } catch (error) {
    if (error !== 'cancel') {
      handleApiError(error, 'Failed to delete transactions')
    }
  }
}

const handleXueqiuImportFile = async (file: File): Promise<boolean> => {
  try {
    const portfolioId = currentPortfolio.value?.id
    if (!portfolioId) {
      showWarning('Please select a portfolio first')
      return false
    }

    const result = await transactionStore.importXueqiuTransactions(file, portfolioId)
    showSuccess(result.message)
    showXueqiuImportDialog.value = false
    // Refresh both transactions and assets after import
    await Promise.all([
      transactionStore.fetchTransactions(portfolioId),
      assetStore.fetchAssets()
    ])
  } catch (error) {
    handleApiError(error, 'Failed to import Xueqiu transactions')
  }
  return false // Prevent default upload
}

const handleXueqiuAlignFile = async (file: File): Promise<boolean> => {
  const portfolioId = currentPortfolio.value?.id
  if (!portfolioId) {
    showWarning('Please select a portfolio first')
    return false
  }

  try {
    // Confirm the destructive action
    await ElMessageBox.confirm(
      'This will delete ALL existing transactions and replace them with data from the uploaded zip file. Positions will be recalculated automatically.',
      'Align to Xueqiu',
      {
        confirmButtonText: 'Proceed',
        cancelButtonText: 'Cancel',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )

    showAlignDialog.value = false
    uiStore.setLoading(true)

    const result = await transactionStore.alignXueqiuTransactions(file, portfolioId)
    showSuccess(result.message)
    showAlignDialog.value = false
    // Refresh transactions and assets after alignment
    await Promise.all([
      transactionStore.fetchTransactions(portfolioId),
      assetStore.fetchAssets()
    ])
  } catch (error) {
    if (error !== 'cancel') {
      handleApiError(error, 'Failed to align Xueqiu portfolio')
    }
  } finally {
    uiStore.setLoading(false)
  }
  return false // Prevent default upload
}

// Check Dividends/Splits
const handleCheckDividends = async () => {
  const portfolioId = currentPortfolio.value?.id
  if (!portfolioId) {
    showWarning('Please select a portfolio first')
    return
  }

  checkingDividends.value = true
  try {
    const result = await transactionStore.checkDividends(portfolioId)
    dividendCheckResult.value = result
    selectedMissingItems.value = []

    if (result.missing.length === 0) {
      showSuccess(
        `No missing dividends found (checked ${result.assets_checked} assets, ${result.dividend_events_found} dividend events).`
      )
      return
    }

    showDividendCheckDialog.value = true
  } catch (error) {
    handleApiError(error, 'Failed to check dividends')
  } finally {
    checkingDividends.value = false
  }
}

const handleDividendSelectionChange = (rows: MissingDividendItem[]): void => {
  selectedMissingItems.value = rows
}

const addMissingDividends = async (items: MissingDividendItem[]) => {
  const portfolioId = currentPortfolio.value?.id
  if (!portfolioId) return

  try {
    await ElMessageBox.confirm(
      `This will add ${items.length} dividend transaction(s) and recalculate positions. Continue?`,
      'Add Dividends',
      {
        confirmButtonText: 'Add',
        cancelButtonText: 'Cancel',
        type: 'warning'
      }
    )
  } catch (error) {
    if (error !== 'cancel') {
      handleApiError(error, 'Failed to add dividends')
    }
    return
  }

  addingDividends.value = true
  try {
    const result = await transactionStore.addDividends(portfolioId, items)
    showSuccess(`${result.added} dividend transaction(s) added. Positions recalculated.`)
    showDividendCheckDialog.value = false
    dividendCheckResult.value = null
    selectedMissingItems.value = []
    await transactionStore.fetchTransactions(portfolioId)
  } catch (error) {
    handleApiError(error, 'Failed to add dividends')
  } finally {
    addingDividends.value = false
  }
}

const addSelectedDividends = () => {
  if (selectedMissingItems.value.length === 0) {
    showWarning('Please select at least one dividend to add')
    return
  }
  addMissingDividends([...selectedMissingItems.value])
}

const addAllDividends = () => {
  if (!dividendCheckResult.value || dividendCheckResult.value.missing.length === 0) return
  addMissingDividends([...dividendCheckResult.value.missing])
}

// Refresh
const handleRefresh = () => {
  initializeData()
}

// Lifecycle
onMounted(() => {
  initializeData()
})
</script>

<style scoped>
.transactions {
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

.filter-card {
  margin-bottom: 20px;
}

.filter-actions-row {
  margin-top: 16px;
}

.filter-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.el-card {
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
}

.upload-demo {
  text-align: center;
}
</style>