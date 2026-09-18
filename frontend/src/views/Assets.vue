<template>
  <div class="assets">
    <div class="page-header">
      <div class="title-row">
        <h2 class="page-title">Asset Management</h2>
        <el-button :icon="Refresh" @click="handleRefresh" circle aria-label="Refresh" />
      </div>
      <el-button type="primary" @click="openAddDialog">Add Asset</el-button>
    </div>
    
    <el-card>
      <SharedDataTable 
        :data="assets" 
        :columns="tableColumns" 
        :loading="loading"
        @action="handleTableAction"
      />
    </el-card>
    
    <!-- Add/Edit Asset Dialog -->
    <el-dialog v-model="showDialog" :title="dialogTitle" width="500px">
      <el-form :model="assetForm" ref="assetFormRef" :rules="assetRules">
        <el-form-item label="Symbol" prop="symbol">
          <el-input v-model="assetForm.symbol" />
        </el-form-item>
        <el-form-item label="Name" prop="name">
          <el-input v-model="assetForm.name" />
        </el-form-item>
        <el-form-item label="Type" prop="type">
          <el-select v-model="assetForm.type" style="width: 100%">
            <el-option label="Stock" value="stock" />
            <el-option label="Bond" value="bond" />
            <el-option label="Fund" value="fund" />
            <el-option label="ETF" value="etf" />
            <el-option label="Gold" value="gold" />
            <el-option label="Cash" value="cash" />
          </el-select>
        </el-form-item>
        <el-form-item label="ISIN" prop="isin">
          <el-input v-model="assetForm.isin" />
        </el-form-item>
        <el-form-item label="Currency" prop="currency_id">
          <el-select v-model="assetForm.currency_id" style="width: 100%">
            <el-option v-for="currency in currencies" :key="currency.id" :label="currency.code" :value="currency.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">Cancel</el-button>
        <el-button type="primary" @click="saveAsset">{{ isEditMode ? 'Update' : 'Save' }}</el-button>
      </template>
    </el-dialog>

    <!-- Delete Confirmation Dialog -->
    <el-dialog v-model="showDeleteDialog" title="Confirm Delete" width="400px">
      <p>Are you sure you want to delete the asset "{{ assetToDelete?.name }}"?</p>
      <p>This action cannot be undone.</p>
      <template #footer>
        <el-button @click="showDeleteDialog = false">Cancel</el-button>
        <el-button type="danger" @click="confirmDelete">Delete</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Assets' })
import { ref, computed, onMounted } from 'vue'
import { useAssetStore } from '../stores'
import { useReferenceStore } from '../stores'
import { useUIStore } from '../stores'
import type { Asset, AssetType } from '../types/models'
import SharedDataTable from '../components/SharedDataTable.vue'
import { showSuccess, handleApiError } from '../utils/errorHandler'
import { Refresh } from '@element-plus/icons-vue'

// Pinia stores
const assetStore = useAssetStore()
const referenceStore = useReferenceStore()
const uiStore = useUIStore()

// Reactive state
const showDialog = ref(false)
const showDeleteDialog = ref(false)
const isEditMode = ref(false)
const editingAssetId = ref<number | null>(null)
const assetToDelete = ref<Asset | null>(null)
const assetFormRef = ref()

const assetForm = ref<{
  symbol: string
  name: string
  type: AssetType
  isin: string
  currency_id: number
}>({
  symbol: '',
  name: '',
  type: 'stock',
  isin: '',
  currency_id: 1
})

const assetRules = {
  symbol: [{ required: true, message: 'Please input symbol', trigger: 'blur' }],
  name: [{ required: true, message: 'Please input name', trigger: 'blur' }],
  type: [{ required: true, message: 'Please select type', trigger: 'change' }],
  currency_id: [{ required: true, message: 'Please select currency', trigger: 'change' }]
}

// Computed properties from stores
const assets = computed(() => assetStore.assets)
const currencies = computed(() => referenceStore.currencies)
const loading = computed(() => uiStore.loading)

const dialogTitle = computed(() => isEditMode.value ? 'Edit Asset' : 'Add Asset')

const tableColumns = computed(() => [
  { prop: 'symbol', label: 'Symbol', minWidth: '100' },
  { prop: 'name', label: 'Name', minWidth: '150' },
  { prop: 'type', label: 'Type', minWidth: '100' },
  { prop: 'isin', label: 'ISIN', minWidth: '150' },
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

// Methods
const resetAssetForm = () => {
  assetForm.value = {
    symbol: '',
    name: '',
    type: 'stock',
    isin: '',
    currency_id: 1
  }
  isEditMode.value = false
  editingAssetId.value = null
}

const openAddDialog = () => {
  resetAssetForm()
  showDialog.value = true
}

const editAsset = (asset: Asset) => {
  isEditMode.value = true
  editingAssetId.value = asset.id
  assetForm.value = {
    symbol: asset.symbol,
    name: asset.name,
    type: asset.type,
    isin: asset.isin || '',
    currency_id: asset.currency_id ?? 1
  }
  showDialog.value = true
}

const saveAsset = async () => {
  try {
    await assetFormRef.value.validate()

    if (isEditMode.value && editingAssetId.value !== null) {
      await assetStore.updateAsset(editingAssetId.value, assetForm.value)
      showSuccess('Asset updated successfully')
    } else {
      await assetStore.createAsset(assetForm.value)
      showSuccess('Asset created successfully')
    }

    showDialog.value = false
    resetAssetForm()
  } catch (error) {
    handleApiError(error)
  }
}

const deleteAsset = (asset: Asset) => {
  assetToDelete.value = asset
  showDeleteDialog.value = true
}

const handleTableAction = (actionName: string, row: Record<string, any>) => {
  if (actionName === 'edit') {
    editAsset(row as Asset)
  } else if (actionName === 'delete') {
    deleteAsset(row as Asset)
  }
}

const confirmDelete = async () => {
  if (!assetToDelete.value) return
  try {
    await assetStore.deleteAsset(assetToDelete.value.id)
    showDeleteDialog.value = false
    assetToDelete.value = null
    showSuccess('Asset deleted successfully')
  } catch (error) {
    handleApiError(error, 'Failed to delete asset')
  }
}

// Refresh
const handleRefresh = async () => {
  await Promise.all([
    assetStore.fetchAssets(),
    referenceStore.fetchCurrencies()
  ])
}

// Lifecycle hooks
onMounted(async () => {
  await Promise.all([
    assetStore.fetchAssets(),
    referenceStore.fetchCurrencies()
  ])
})
</script>

<style scoped>
.assets {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.el-card {
  border: none;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
}
</style>