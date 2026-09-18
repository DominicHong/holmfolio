<template>
  <div class="tag-management">
    <div class="page-header">
      <div>
        <div class="title-row">
          <h2 class="page-title">Tag Management</h2>
          <el-button :icon="Refresh" @click="handleRefresh" circle aria-label="Refresh" />
        </div>
        <p class="page-description">Manage tags, categories, and assign tags to assets with weights</p>
      </div>
    </div>

    <el-row :gutter="20">
      <!-- Asset Tag Assignment Section -->
      <el-col :xs="24" :sm="24" :md="6" :lg="6">
        <el-card class="section-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon><Link /></el-icon>
                Asset Tags
              </span>
            </div>
          </template>
          <div class="asset-tag-section">
            <div class="asset-autocomplete">
              <el-input
                v-model="assetSearchQuery"
                placeholder="Search asset by symbol or name"
                clearable
                class="asset-search-input"
                @input="onAssetSearchInput"
                @focus="onAssetSearchFocus"
                @blur="onAssetSearchBlur"
                @keydown.down.prevent="onAssetSearchKeyDown"
                @keydown.up.prevent="onAssetSearchKeyUp"
                @keydown.enter.prevent="onAssetSearchEnter"
                @keydown.esc.prevent="onAssetSearchEsc"
              />
              <div v-if="showAssetDropdown && filteredAssets.length > 0" class="asset-dropdown">
                <div
                  v-for="(asset, index) in filteredAssets"
                  :key="asset.id"
                  class="asset-dropdown-item"
                  :class="{ active: index === highlightedAssetIndex, selected: selectedAssetId === asset.id }"
                  @mousedown.prevent="selectAsset(asset)"
                  @mouseenter="highlightedAssetIndex = index"
                >
                  <span class="asset-symbol">{{ asset.symbol }}</span>
                  <span class="asset-name">{{ asset.name }}</span>
                </div>
              </div>
              <div v-else-if="showAssetDropdown && assetSearchQuery && filteredAssets.length === 0" class="asset-dropdown">
                <div class="asset-dropdown-empty">No matching assets found</div>
              </div>
            </div>

            <div v-if="selectedAssetId" class="asset-tags-area">
              <!-- Assigned Tags Group -->
              <div class="category-group assigned-tags-group">
                <div class="category-group-header static">
                  <div class="category-group-info">
                    <span class="category-group-name">Assigned Tags</span>
                  </div>
                  <el-tag size="small" type="info" round class="category-count">{{ currentAssetTags.length }}</el-tag>
                  <div class="category-actions visible">
                    <el-button type="primary" size="small" @click="openAssetTagDialog()">
                      <el-icon><Plus /></el-icon> Add
                    </el-button>
                  </div>
                </div>
                <div class="category-group-tags asset-tag-list">
                  <div
                    v-for="assetTag in currentAssetTags"
                    :key="assetTag.id"
                    class="asset-tag-item"
                    :style="{ borderLeftColor: assetTag.tag?.color || '#409EFF' }"
                  >
                    <div class="asset-tag-info">
                      <el-tag
                        :color="assetTag.tag?.color"
                        effect="dark"
                        size="small"
                      >
                        {{ assetTag.tag?.name }}
                      </el-tag>
                      <div class="weight-bar-container">
                        <el-progress
                          :percentage="assetTag.weight"
                          :color="getWeightColor(assetTag.weight)"
                          :stroke-width="8"
                          :show-text="false"
                        />
                        <span class="weight-text">{{ assetTag.weight }}%</span>
                      </div>
                    </div>
                    <div class="asset-tag-actions">
                      <el-button type="primary" link size="small" @click="openAssetTagDialog(assetTag)">
                        <el-icon><Edit /></el-icon>
                      </el-button>
                      <el-button type="danger" link size="small" @click="deleteAssetTag(assetTag)">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </div>
                  </div>
                  <el-empty v-if="currentAssetTags.length === 0 && pendingAssetTags.length === 0" description="No tags assigned" />
                </div>
              </div>

              <!-- Pending Tags Group -->
              <div v-if="pendingAssetTags.length > 0" class="category-group">
                <div class="category-group-header static">
                  <div class="category-group-info">
                    <span class="category-group-name">Pending Tags</span>
                  </div>
                  <el-tag size="small" type="warning" round class="category-count">{{ pendingAssetTags.length }}</el-tag>
                  <div class="category-actions visible">
                    <el-button type="success" size="small" @click="savePendingTags" :disabled="!isPendingTagsValid">
                      <el-icon><Check /></el-icon> Save
                    </el-button>
                    <el-button type="info" size="small" @click="clearPendingTags">
                      <el-icon><Close /></el-icon> Cancel
                    </el-button>
                  </div>
                </div>
                <div class="category-group-tags">
                  <div
                    v-for="(pendingTag, index) in pendingAssetTags"
                    :key="index"
                    class="pending-tag-item"
                    :class="{ invalid: !isPendingTagValid(pendingTag) }"
                  >
                    <div class="pending-tag-info">
                      <el-tag
                        :color="pendingTag.tag?.color"
                        effect="dark"
                        size="small"
                      >
                        {{ pendingTag.tag?.name }}
                      </el-tag>
                      <div class="weight-bar-container">
                        <el-progress
                          :percentage="pendingTag.weight"
                          :color="getWeightColor(pendingTag.weight)"
                          :stroke-width="8"
                          :show-text="false"
                        />
                        <span class="weight-text">{{ pendingTag.weight }}%</span>
                      </div>
                    </div>
                    <div class="pending-tag-actions">
                      <el-button type="primary" link size="small" @click="editPendingTag(index)">
                        <el-icon><Edit /></el-icon>
                      </el-button>
                      <el-button type="danger" link size="small" @click="removePendingTag(index)">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </div>
                  </div>
                </div>

                <!-- Pending Tags Weight Validation Summary -->
                <div class="weight-summary">
                  <div class="weight-summary-title">Pending Tags Validation</div>
                  <div
                    v-for="summary in pendingCategoryWeightSummary"
                    :key="summary.categoryId"
                    class="weight-summary-item"
                  >
                    <span class="summary-category">{{ summary.categoryName }}</span>
                    <el-progress
                      :percentage="Math.min(summary.totalWeight, 100)"
                      :status="summary.isComplete ? 'success' : 'exception'"
                      :stroke-width="6"
                    />
                    <span
                      class="summary-status"
                      :class="{ complete: summary.isComplete, incomplete: !summary.isComplete }"
                    >
                      {{ summary.totalWeight }}%
                    </span>
                  </div>
                  <el-alert
                    v-if="!isPendingTagsValid"
                    title="Weight validation failed"
                    description="Each category's total weight must equal 100%"
                    type="error"
                    :closable="false"
                    show-icon
                    class="validation-alert"
                  />
                </div>
              </div>

              <!-- Category Weight Summary Group -->
              <div v-if="categoryWeightSummary.length > 0" class="category-group">
                <div class="category-group-header static">
                  <div class="category-group-info">
                    <span class="category-group-name">Category Weight Check</span>
                  </div>
                </div>
                <div class="category-group-tags">
                  <div
                    v-for="summary in categoryWeightSummary"
                    :key="summary.categoryId"
                    class="weight-summary-item"
                  >
                    <span class="summary-category">{{ summary.categoryName }}</span>
                    <el-progress
                      :percentage="Math.min(summary.totalWeight, 100)"
                      :status="summary.isComplete ? 'success' : 'exception'"
                      :stroke-width="6"
                    />
                    <span
                      class="summary-status"
                      :class="{ complete: summary.isComplete, incomplete: !summary.isComplete }"
                    >
                      {{ summary.totalWeight }}%
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <el-empty v-else description="Select an asset to manage tags" />
          </div>
        </el-card>
      </el-col>

      <!-- Categories & Tags Section -->
      <el-col :xs="24" :sm="24" :md="18" :lg="18">
        <el-card class="section-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">
                <el-icon><CollectionTag /></el-icon>
                Categories & Tags
              </span>
              <div class="header-actions">
                <el-button type="primary" size="small" @click="openCategoryDialog()">
                  <el-icon><Plus /></el-icon> Category
                </el-button>
                <el-button type="primary" size="small" @click="openTagDialog()">
                  <el-icon><Plus /></el-icon> Tag
                </el-button>
              </div>
            </div>
          </template>
          <div class="category-tags-list">
            <div v-for="group in categoryGroups" :key="group.key" class="category-group">
              <div class="category-group-header" @click="toggleCategoryGroup(group)">
                <el-icon class="expand-arrow" :class="{ expanded: isGroupExpanded(group) }">
                  <ArrowRight />
                </el-icon>
                <div class="category-group-info">
                  <span class="category-group-name">{{ group.name }}</span>
                  <span v-if="group.description" class="category-group-desc">{{ group.description }}</span>
                </div>
                <el-tag size="small" type="info" round class="category-count">{{ group.tags.length }}</el-tag>
                <div class="category-actions" @click.stop>
                  <el-button type="primary" link size="small" @click="openTagDialog(null, group.categoryId)">
                    <el-icon><Plus /></el-icon>
                  </el-button>
                  <el-button v-if="!group.uncategorized" type="primary" link size="small" @click="openCategoryDialog(group.category)">
                    <el-icon><Edit /></el-icon>
                  </el-button>
                  <el-button v-if="!group.uncategorized" type="danger" link size="small" @click="deleteCategory(group.category)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
              <div v-if="isGroupExpanded(group)" class="category-group-tags">
                <template v-for="tag in group.tags" :key="tag.id">
                  <div
                    class="tag-item"
                    :class="{ active: selectedTagId === tag.id }"
                    :style="{ borderLeftColor: tag.color || '#409EFF' }"
                    @click="selectTag(tag)"
                  >
                    <div class="tag-info">
                      <el-tag
                        :color="tag.color"
                        effect="dark"
                        size="small"
                        class="tag-name"
                      >
                        {{ tag.name }}
                      </el-tag>
                      <span v-if="tag.description" class="tag-desc">{{ tag.description }}</span>
                    </div>
                    <el-tag
                      size="small"
                      type="info"
                      round
                      class="tag-asset-count"
                    >
                      {{ assetTagCounts[tag.id] || 0 }}
                    </el-tag>
                    <div class="tag-actions" @click.stop>
                      <el-button type="primary" link size="small" @click="openTagDialog(tag)">
                        <el-icon><Edit /></el-icon>
                      </el-button>
                      <el-button type="danger" link size="small" @click="deleteTag(tag)">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </div>
                  </div>
                  <div v-if="selectedTagId === tag.id" class="tag-assets-panel">
                    <div class="tag-assets-header">
                      <span>Linked Assets</span>
                      <span class="tag-assets-count">{{ currentTagAssets.length }}</span>
                    </div>
                    <div v-loading="loadingTagAssets" class="tag-assets-list">
                      <div
                        v-for="assetTag in currentTagAssets"
                        :key="assetTag.id"
                        class="tag-asset-item"
                      >
                        <div class="tag-asset-info">
                          <span class="tag-asset-symbol">{{ assetTag.asset?.symbol }}</span>
                          <span class="tag-asset-name">{{ assetTag.asset?.name }}</span>
                        </div>
                        <div class="weight-bar-container">
                          <el-progress
                            :percentage="assetTag.weight"
                            :color="getWeightColor(assetTag.weight)"
                            :stroke-width="6"
                            :show-text="false"
                          />
                          <span class="weight-text">{{ assetTag.weight }}%</span>
                        </div>
                      </div>
                      <el-empty
                        v-if="!loadingTagAssets && currentTagAssets.length === 0"
                        description="No assets assigned"
                        :image-size="60"
                      />
                    </div>
                  </div>
                </template>
                <div v-if="group.tags.length === 0" class="category-group-empty">
                  No tags in this category
                </div>
              </div>
            </div>
            <el-empty v-if="categoryGroups.length === 0" description="No categories yet" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Category Dialog -->
    <el-dialog
      v-model="categoryDialogVisible"
      :title="isEditCategory ? 'Edit Category' : 'Add Category'"
      width="400px"
    >
      <el-form :model="categoryForm" :rules="categoryRules" ref="categoryFormRef">
        <el-form-item label="Name" prop="name">
          <el-input v-model="categoryForm.name" placeholder="e.g., Industry, Region" />
        </el-form-item>
        <el-form-item label="Description">
          <el-input
            v-model="categoryForm.description"
            type="textarea"
            rows="2"
            placeholder="Optional description"
          />
        </el-form-item>
        <el-form-item label="Display Order">
          <el-input-number v-model="categoryForm.display_order" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="categoryDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveCategory">Save</el-button>
      </template>
    </el-dialog>

    <!-- Tag Dialog -->
    <el-dialog
      v-model="tagDialogVisible"
      :title="isEditTag ? 'Edit Tag' : 'Add Tag'"
      width="400px"
    >
      <el-form :model="tagForm" :rules="tagRules" ref="tagFormRef">
        <el-form-item label="Name" prop="name">
          <el-input v-model="tagForm.name" placeholder="e.g., Banking, Domestic" />
        </el-form-item>
        <el-form-item label="Category" prop="category_id">
          <el-select v-model="tagForm.category_id" placeholder="Select category" clearable>
            <el-option
              v-for="category in tagCategories"
              :key="category.id"
              :label="category.name"
              :value="category.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Color">
          <el-color-picker v-model="tagForm.color" show-alpha />
        </el-form-item>
        <el-form-item label="Description">
          <el-input
            v-model="tagForm.description"
            type="textarea"
            rows="2"
            placeholder="Optional description"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tagDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveTag">Save</el-button>
      </template>
    </el-dialog>

    <!-- Asset Tag Dialog -->
    <el-dialog
      v-model="assetTagDialogVisible"
      :title="isEditAssetTag ? 'Edit Asset Tag' : 'Add Tag to Asset'"
      width="450px"
    >
      <el-form :model="assetTagForm" :rules="assetTagRules" ref="assetTagFormRef">
        <el-form-item label="Tag" prop="tag_id">
          <el-select v-model="assetTagForm.tag_id" placeholder="Select tag" filterable @change="onTagChange">
            <el-option-group
              v-for="category in tagsByCategory"
              :key="category.id"
              :label="category.name"
            >
              <el-option
                v-for="tag in category.tags"
                :key="tag.id"
                :label="tag.name"
                :value="tag.id"
              >
                <el-tag :color="tag.color" effect="dark" size="small">{{ tag.name }}</el-tag>
              </el-option>
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="Weight (%)" prop="weight">
          <el-slider v-model="assetTagForm.weight" :min="0" :max="100" show-input />
          <div class="weight-hint">
            <el-alert
              v-if="selectedCategoryWeightInfo"
              :title="selectedCategoryWeightInfo.message"
              :type="selectedCategoryWeightInfo.type"
              :closable="false"
              show-icon
              size="small"
            />
            <p class="weight-tip">Tip: You can add multiple tags to reach 100%. For example: 10% Bond + 90% Equity.</p>
          </div>
        </el-form-item>
        <el-form-item label="Notes">
          <el-input
            v-model="assetTagForm.notes"
            type="textarea"
            rows="2"
            placeholder="Optional notes"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assetTagDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="saveAssetTag">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// @ts-nocheck
defineOptions({ name: 'TagManagement' })
import { ref, computed, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useReferenceStore } from '../stores'
import { useAssetStore } from '../stores'
import { useUIStore } from '../stores'
import { showSuccess, handleApiError } from '../utils/errorHandler'
import {
  ArrowRight,
  CollectionTag,
  Link,
  Plus,
  Edit,
  Delete,
  Check,
  Close,
  Refresh
} from '@element-plus/icons-vue'

const referenceStore = useReferenceStore()
const assetStore = useAssetStore()
const uiStore = useUIStore()

// Data
const tagCategories = computed(() => referenceStore.tagCategories || [])
const tags = computed(() => referenceStore.tags || [])
const assets = computed(() => assetStore.assets || [])

const selectedAssetId = ref<number | null>(null)
const currentAssetTags = ref<any[]>([])

// Tag → Assets
const selectedTagId = ref<number | null>(null)
const currentTagAssets = ref<any[]>([])
const loadingTagAssets = ref(false)
const collapsedGroupKeys = ref(new Set<string>())
const assetTagCounts = ref<Record<number, number>>({})

// Asset autocomplete
const assetSearchQuery = ref('')
const showAssetDropdown = ref(false)
const highlightedAssetIndex = ref(-1)
const selectedAssetDisplay = ref('')

// Dialog visibility
const categoryDialogVisible = ref(false)
const tagDialogVisible = ref(false)
const assetTagDialogVisible = ref(false)

// Edit mode
const isEditCategory = ref(false)
const isEditTag = ref(false)
const isEditAssetTag = ref(false)
const editingCategoryId = ref<number | null>(null)
const editingTagId = ref<number | null>(null)
const editingAssetTagId = ref<number | null>(null)

// Form refs
const categoryFormRef = ref()
const tagFormRef = ref()
const assetTagFormRef = ref()

// Forms
const categoryForm = ref({
  name: '',
  description: '',
  display_order: 0
})

const tagForm = ref({
  name: '',
  category_id: null,
  color: '#409EFF',
  description: ''
})

const assetTagForm = ref({
  tag_id: null,
  weight: 100,
  notes: ''
})

// Pending asset tags for pre-add functionality
const pendingAssetTags = ref<any[]>([])
const editingPendingTagIndex = ref(-1)

// Rules
const categoryRules = {
  name: [{ required: true, message: 'Please input category name', trigger: 'blur' }]
}

const tagRules = {
  name: [{ required: true, message: 'Please input tag name', trigger: 'blur' }]
}

const assetTagRules = {
  tag_id: [{ required: true, message: 'Please select a tag', trigger: 'change' }],
  weight: [{ required: true, message: 'Please set weight', trigger: 'change' }]
}

// Computed
const sortedCategories = computed(() => {
  return [...tagCategories.value].sort((a, b) => a.display_order - b.display_order)
})

const categoryGroups = computed(() => {
  const groups = sortedCategories.value.map(category => ({
    key: `cat-${category.id}`,
    categoryId: category.id,
    category,
    uncategorized: false,
    name: category.name,
    description: category.description || '',
    tags: tags.value.filter(tag => tag.category_id === category.id)
  }))
  const uncategorized = tags.value.filter(tag => !tag.category_id)
  if (uncategorized.length > 0) {
    groups.push({
      key: 'uncategorized',
      categoryId: null,
      category: null,
      uncategorized: true,
      name: 'Uncategorized',
      description: '',
      tags: uncategorized
    })
  }
  return groups
})

const filteredAssets = computed(() => {
  // Exclude cash assets from the dropdown
  const nonCashAssets = assets.value.filter(asset => asset.type !== 'cash')
  if (!assetSearchQuery.value.trim()) {
    return nonCashAssets
  }
  const query = assetSearchQuery.value.toLowerCase().trim()
  return nonCashAssets.filter(asset =>
    asset.symbol.toLowerCase().includes(query) ||
    asset.name.toLowerCase().includes(query)
  )
})

const tagsByCategory = computed(() => {
  const grouped = []
  tagCategories.value.forEach(category => {
    const categoryTags = tags.value.filter(tag => tag.category_id === category.id)
    if (categoryTags.length > 0) {
      grouped.push({
        ...category,
        tags: categoryTags
      })
    }
  })
  // Add uncategorized tags
  const uncategorized = tags.value.filter(tag => !tag.category_id)
  if (uncategorized.length > 0) {
    grouped.push({
      id: null,
      name: 'Uncategorized',
      tags: uncategorized
    })
  }
  return grouped
})

const categoryWeightSummary = computed(() => {
  const summary = []
  const categoryMap = {}

  currentAssetTags.value.forEach(assetTag => {
    const tag = assetTag.tag
    if (!tag || !tag.category_id) return

    const category = tagCategories.value.find(c => c.id === tag.category_id)
    if (!category) return

    if (!categoryMap[category.id]) {
      categoryMap[category.id] = {
        categoryId: category.id,
        categoryName: category.name,
        totalWeight: 0
      }
    }
    categoryMap[category.id].totalWeight += assetTag.weight
  })

  Object.values(categoryMap).forEach(item => {
    item.isComplete = item.totalWeight === 100
    summary.push(item)
  })

  return summary.sort((a, b) => a.categoryName.localeCompare(b.categoryName))
})

// Compute weight summary for pending tags grouped by category
const pendingCategoryWeightSummary = computed(() => {
  const summary = []
  const categoryMap = {}

  pendingAssetTags.value.forEach(pendingTag => {
    const tag = pendingTag.tag
    if (!tag || !tag.category_id) return

    const category = tagCategories.value.find(c => c.id === tag.category_id)
    if (!category) return

    if (!categoryMap[category.id]) {
      categoryMap[category.id] = {
        categoryId: category.id,
        categoryName: category.name,
        totalWeight: 0
      }
    }
    categoryMap[category.id].totalWeight += pendingTag.weight
  })

  Object.values(categoryMap).forEach(item => {
    item.isComplete = item.totalWeight === 100
    summary.push(item)
  })

  return summary.sort((a, b) => a.categoryName.localeCompare(b.categoryName))
})

// Check if all pending tags are valid (each category's total weight equals 100%)
const isPendingTagsValid = computed(() => {
  if (pendingAssetTags.value.length === 0) return false

  const categoryMap = {}

  pendingAssetTags.value.forEach(pendingTag => {
    const tag = pendingTag.tag
    if (!tag || !tag.category_id) return

    if (!categoryMap[tag.category_id]) {
      categoryMap[tag.category_id] = 0
    }
    categoryMap[tag.category_id] += pendingTag.weight
  })

  // All categories with pending tags must have exactly 100% weight
  return Object.values(categoryMap).every(weight => weight === 100)
})

// Compute weight info for the currently selected tag's category
const selectedCategoryWeightInfo = computed(() => {
  if (!assetTagForm.value.tag_id || !selectedAssetId.value) return null

  const selectedTag = tags.value.find(t => t.id === assetTagForm.value.tag_id)
  if (!selectedTag || !selectedTag.category_id) return null

  const category = tagCategories.value.find(c => c.id === selectedTag.category_id)
  if (!category) return null

  // Calculate existing weight for this category (excluding current tag if editing)
  let existingWeight = 0
  currentAssetTags.value.forEach(assetTag => {
    if (assetTag.tag?.category_id === selectedTag.category_id) {
      // If editing, exclude the current tag's weight
      if (isEditAssetTag.value && assetTag.tag_id === selectedTag.id) {
        return
      }
      existingWeight += assetTag.weight
    }
  })

  const newWeight = assetTagForm.value.weight || 0
  const totalWeight = existingWeight + newWeight
  const remainingWeight = 100 - totalWeight

  if (totalWeight === 100) {
    return {
      message: `Current total for ${category.name}: ${totalWeight}% (Complete!)`,
      type: 'success'
    }
  } else if (totalWeight < 100) {
    return {
      message: `Current total for ${category.name}: ${totalWeight}%. Need ${remainingWeight}% more to reach 100%.`,
      type: 'warning'
    }
  } else {
    return {
      message: `Current total for ${category.name}: ${totalWeight}%. Exceeds 100% by ${totalWeight - 100}%.`,
      type: 'error'
    }
  }
})

// Methods
const isGroupExpanded = (group) => !collapsedGroupKeys.value.has(group.key)

const toggleCategoryGroup = (group) => {
  const next = new Set(collapsedGroupKeys.value)
  if (next.has(group.key)) {
    next.delete(group.key)
  } else {
    next.add(group.key)
    // Clear tag selection if the selected tag is inside the collapsed group
    const tagIds = new Set(group.tags.map(t => t.id))
    if (selectedTagId.value !== null && tagIds.has(selectedTagId.value)) {
      selectedTagId.value = null
      currentTagAssets.value = []
    }
  }
  collapsedGroupKeys.value = next
}

const openCategoryDialog = (category = null) => {
  if (category) {
    isEditCategory.value = true
    editingCategoryId.value = category.id
    categoryForm.value = {
      name: category.name,
      description: category.description || '',
      display_order: category.display_order || 0
    }
  } else {
    isEditCategory.value = false
    editingCategoryId.value = null
    categoryForm.value = {
      name: '',
      description: '',
      display_order: 0
    }
  }
  categoryDialogVisible.value = true
}

const saveCategory = async () => {
  try {
    await categoryFormRef.value.validate()

    if (isEditCategory.value) {
      await referenceStore.updateTagCategory(editingCategoryId.value, categoryForm.value)
      showSuccess('Category updated successfully')
    } else {
      await referenceStore.createTagCategory(categoryForm.value)
      showSuccess('Category created successfully')
    }

    categoryDialogVisible.value = false
    await referenceStore.fetchTagCategories()
  } catch (error) {
    handleApiError(error)
  }
}

const deleteCategory = async (category) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete "${category.name}"?`,
      'Confirm Delete',
      { type: 'warning' }
    )
    await referenceStore.deleteTagCategory(category.id)
    showSuccess('Category deleted successfully')
    if (selectedTagId.value !== null) {
      const selectedTag = tags.value.find(t => t.id === selectedTagId.value)
      if (selectedTag?.category_id === category.id) {
        selectedTagId.value = null
        currentTagAssets.value = []
      }
    }
    await referenceStore.fetchTagCategories()
  } catch (error) {
    if (error !== 'cancel') {
      handleApiError(error)
    }
  }
}

const openTagDialog = (tag = null, categoryId: number | null = null) => {
  if (tag) {
    isEditTag.value = true
    editingTagId.value = tag.id
    tagForm.value = {
      name: tag.name,
      category_id: tag.category_id,
      color: tag.color || '#409EFF',
      description: tag.description || ''
    }
  } else {
    isEditTag.value = false
    editingTagId.value = null
    tagForm.value = {
      name: '',
      category_id: categoryId,
      color: '#409EFF',
      description: ''
    }
  }
  tagDialogVisible.value = true
}

const saveTag = async () => {
  try {
    await tagFormRef.value.validate()

    if (isEditTag.value) {
      await referenceStore.updateTag(editingTagId.value, tagForm.value)
      showSuccess('Tag updated successfully')
    } else {
      await referenceStore.createTag(tagForm.value)
      showSuccess('Tag created successfully')
    }

    tagDialogVisible.value = false
    await referenceStore.fetchTags()
  } catch (error) {
    handleApiError(error)
  }
}

const deleteTag = async (tag) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete "${tag.name}"?`,
      'Confirm Delete',
      { type: 'warning' }
    )
    await referenceStore.deleteTag(tag.id)
    showSuccess('Tag deleted successfully')
    if (selectedTagId.value === tag.id) {
      selectedTagId.value = null
      currentTagAssets.value = []
    }
    await referenceStore.fetchTags()
    if (selectedAssetId.value) {
      await loadAssetTags()
    }
  } catch (error) {
    if (error !== 'cancel') {
      handleApiError(error)
    }
  }
}

const onAssetChange = async () => {
  if (selectedAssetId.value) {
    await loadAssetTags()
  } else {
    currentAssetTags.value = []
  }
}

// Asset autocomplete methods
const onAssetSearchInput = () => {
  showAssetDropdown.value = true
  highlightedAssetIndex.value = -1
}

const onAssetSearchFocus = () => {
  showAssetDropdown.value = true
}

const onAssetSearchBlur = () => {
  setTimeout(() => {
    showAssetDropdown.value = false
  }, 200)
}

const onAssetSearchKeyDown = () => {
  if (filteredAssets.value.length === 0) return
  highlightedAssetIndex.value = Math.min(
    highlightedAssetIndex.value + 1,
    filteredAssets.value.length - 1
  )
}

const onAssetSearchKeyUp = () => {
  if (filteredAssets.value.length === 0) return
  highlightedAssetIndex.value = Math.max(highlightedAssetIndex.value - 1, 0)
}

const onAssetSearchEnter = () => {
  if (highlightedAssetIndex.value >= 0 && highlightedAssetIndex.value < filteredAssets.value.length) {
    selectAsset(filteredAssets.value[highlightedAssetIndex.value])
  }
}

const onAssetSearchEsc = () => {
  showAssetDropdown.value = false
  highlightedAssetIndex.value = -1
}

const selectAsset = async (asset) => {
  selectedAssetId.value = asset.id
  assetSearchQuery.value = `${asset.symbol} - ${asset.name}`
  selectedAssetDisplay.value = assetSearchQuery.value
  showAssetDropdown.value = false
  highlightedAssetIndex.value = -1
  // Clear pending tags when switching assets
  pendingAssetTags.value = []
  editingPendingTagIndex.value = -1
  await onAssetChange()
}

const clearAssetSelection = () => {
  selectedAssetId.value = null
  assetSearchQuery.value = ''
  selectedAssetDisplay.value = ''
  currentAssetTags.value = []
}

const loadAssetTags = async () => {
  try {
    currentAssetTags.value = await referenceStore.fetchAssetTags(selectedAssetId.value)
  } catch (error) {
    handleApiError(error)
  }
}

const refreshAssetTagCounts = async () => {
  try {
    const allAssetTags = await referenceStore.fetchAssetTags()
    const counts: Record<number, number> = {}
    allAssetTags.forEach(at => {
      counts[at.tag_id] = (counts[at.tag_id] || 0) + 1
    })
    assetTagCounts.value = counts
  } catch {
    assetTagCounts.value = {}
  }
}

const openAssetTagDialog = (assetTag = null) => {
  if (assetTag) {
    isEditAssetTag.value = true
    editingAssetTagId.value = assetTag.id
    editingPendingTagIndex.value = -1
    assetTagForm.value = {
      tag_id: assetTag.tag_id,
      weight: assetTag.weight,
      notes: assetTag.notes || ''
    }
  } else {
    isEditAssetTag.value = false
    editingAssetTagId.value = null
    editingPendingTagIndex.value = -1
    assetTagForm.value = {
      tag_id: null,
      weight: 100,
      notes: ''
    }
  }
  assetTagDialogVisible.value = true
}

const editPendingTag = (index) => {
  const pendingTag = pendingAssetTags.value[index]
  if (!pendingTag) return

  editingPendingTagIndex.value = index
  isEditAssetTag.value = false
  editingAssetTagId.value = null
  assetTagForm.value = {
    tag_id: pendingTag.tag_id,
    weight: pendingTag.weight,
    notes: pendingTag.notes || ''
  }
  assetTagDialogVisible.value = true
}

const removePendingTag = (index) => {
  pendingAssetTags.value.splice(index, 1)
}

const clearPendingTags = () => {
  pendingAssetTags.value = []
  editingPendingTagIndex.value = -1
}

const isPendingTagValid = (pendingTag) => {
  const tag = pendingTag.tag
  if (!tag || !tag.category_id) return true

  // Calculate total weight for this category in pending tags
  let totalWeight = 0
  pendingAssetTags.value.forEach(pt => {
    if (pt.tag?.category_id === tag.category_id) {
      totalWeight += pt.weight
    }
  })

  return totalWeight === 100
}

const savePendingTags = async () => {
  if (!isPendingTagsValid.value) {
    return
  }

  try {
    for (const pendingTag of pendingAssetTags.value) {
      const data = {
        asset_id: selectedAssetId.value,
        tag_id: pendingTag.tag_id,
        weight: pendingTag.weight,
        notes: pendingTag.notes || null
      }
      await referenceStore.createAssetTag(data)
    }

    showSuccess('All pending tags saved successfully')
    pendingAssetTags.value = []
    editingPendingTagIndex.value = -1
    await loadAssetTags()
    await refreshAssetTagCounts()
  } catch (error) {
    handleApiError(error)
  }
}

const onTagChange = () => {
  // Reset weight to 100 when tag changes, or suggest remaining weight
  if (!assetTagForm.value.tag_id || !selectedAssetId.value) return

  const selectedTag = tags.value.find(t => t.id === assetTagForm.value.tag_id)
  if (!selectedTag || !selectedTag.category_id) return

  // Calculate existing weight for this category
  let existingWeight = 0
  currentAssetTags.value.forEach(assetTag => {
    if (assetTag.tag?.category_id === selectedTag.category_id) {
      existingWeight += assetTag.weight
    }
  })

  // Suggest remaining weight to reach 100%
  const suggestedWeight = Math.max(0, 100 - existingWeight)
  if (suggestedWeight > 0 && suggestedWeight !== 100) {
    assetTagForm.value.weight = suggestedWeight
  }
}

const saveAssetTag = async () => {
  try {
    await assetTagFormRef.value.validate()

    const selectedTag = tags.value.find(t => t.id === assetTagForm.value.tag_id)

    if (isEditAssetTag.value) {
      // Editing existing asset tag - save directly
      const data = {
        asset_id: selectedAssetId.value,
        tag_id: assetTagForm.value.tag_id,
        weight: assetTagForm.value.weight,
        notes: assetTagForm.value.notes || null
      }
      await referenceStore.updateAssetTag(editingAssetTagId.value, data)
      showSuccess('Asset tag updated successfully')
      assetTagDialogVisible.value = false
      await loadAssetTags()
      await refreshAssetTagCounts()
    } else if (editingPendingTagIndex.value >= 0) {
      // Editing pending tag - update in pending list
      pendingAssetTags.value[editingPendingTagIndex.value] = {
        tag_id: assetTagForm.value.tag_id,
        weight: assetTagForm.value.weight,
        notes: assetTagForm.value.notes || '',
        tag: selectedTag
      }
      showSuccess('Pending tag updated')
      assetTagDialogVisible.value = false
      editingPendingTagIndex.value = -1
    } else {
      // Adding new tag - add to pending list
      pendingAssetTags.value.push({
        tag_id: assetTagForm.value.tag_id,
        weight: assetTagForm.value.weight,
        notes: assetTagForm.value.notes || '',
        tag: selectedTag
      })
      showSuccess('Tag added to pending list')
      assetTagDialogVisible.value = false
    }
  } catch (error) {
    handleApiError(error)
  }
}

const deleteAssetTag = async (assetTag) => {
  try {
    await ElMessageBox.confirm(
      `Remove tag "${assetTag.tag?.name}" from this asset?`,
      'Confirm Remove',
      { type: 'warning' }
    )
    await referenceStore.deleteAssetTag(assetTag.id)
    showSuccess('Tag removed from asset')
    await loadAssetTags()
    await refreshAssetTagCounts()
  } catch (error) {
    if (error !== 'cancel') {
      handleApiError(error)
    }
  }
}

const selectTag = async (tag) => {
  if (selectedTagId.value === tag.id) {
    selectedTagId.value = null
    currentTagAssets.value = []
  } else {
    selectedTagId.value = tag.id
    await loadTagAssets(tag.id)
  }
}

const loadTagAssets = async (tagId) => {
  loadingTagAssets.value = true
  try {
    currentTagAssets.value = await referenceStore.fetchAssetTags(null, tagId)
  } catch (error) {
    handleApiError(error)
    currentTagAssets.value = []
  } finally {
    loadingTagAssets.value = false
  }
}

const getWeightColor = (weight) => {
  if (weight >= 80) return '#67C23A'
  if (weight >= 50) return '#E6A23C'
  if (weight >= 20) return '#409EFF'
  return '#909399'
}

// Refresh
const handleRefresh = async () => {
  await Promise.all([
    referenceStore.fetchTagCategories(),
    referenceStore.fetchTags(),
    assetStore.fetchAssets(),
    refreshAssetTagCounts()
  ])
}

// Lifecycle
onMounted(async () => {
  await Promise.all([
    referenceStore.fetchTagCategories(),
    referenceStore.fetchTags(),
    assetStore.fetchAssets(),
    refreshAssetTagCounts()
  ])
})
</script>

<style scoped>
.tag-management {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  gap: 12px;
}

.page-description {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.section-card {
  height: calc(100vh - 200px);
  display: flex;
  flex-direction: column;
}

.section-card :deep(.el-card__header) {
  padding: 16px 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-bottom: 1px solid #e6e6e6;
}

.section-card :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-weight: 600;
  font-size: 16px;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title .el-icon {
  font-size: 18px;
  color: #409EFF;
}

/* Categories & Tags List */
.category-tags-list {
  height: 100%;
  overflow-y: auto;
  padding: 8px;
}

.category-group {
  margin-bottom: 10px;
  border: 1px solid #e6e6e6;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.category-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  background: #f5f7fa;
  transition: background-color 0.2s;
}

.category-group-header:hover {
  background: #ecf5ff;
}

.expand-arrow {
  color: #909399;
  font-size: 14px;
  transition: transform 0.2s;
  flex-shrink: 0;
}

.expand-arrow.expanded {
  transform: rotate(90deg);
}

.category-group-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-group-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.category-group-desc {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.category-count {
  flex-shrink: 0;
}

.category-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.3s;
}

.category-group-header:hover .category-actions {
  opacity: 1;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.category-group-header.static {
  cursor: default;
}

.category-group-header.static:hover {
  background: #f5f7fa;
}

.category-actions.visible {
  opacity: 1;
}

.category-group-tags {
  padding: 8px 10px 4px;
}

.category-group-tags .tag-item {
  margin-bottom: 8px;
}

.category-group-empty {
  padding: 4px 4px 12px;
  color: #909399;
  font-size: 12px;
  text-align: center;
}

/* Tag Item */
.tag-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  margin-bottom: 8px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e6e6e6;
  border-left-width: 4px;
  transition: all 0.3s ease;
}

.tag-item:hover {
  background: #f5f7fa;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.tag-item.active {
  background: #ecf5ff;
  border-color: #409EFF;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.2);
  border-radius: 8px 8px 0 0;
  margin-bottom: 0;
  border-bottom: none;
}

.tag-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tag-name {
  font-weight: 500;
}

.tag-desc {
  font-size: 12px;
  color: #909399;
}

.tag-asset-count {
  flex-shrink: 0;
  margin-left: auto;
}

.tag-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.3s;
}

.tag-item:hover .tag-actions {
  opacity: 1;
}

/* Tag Assets Panel */
.tag-assets-panel {
  background: #ecf5ff;
  border: 1px solid #409EFF;
  border-top: none;
  border-radius: 0 0 8px 8px;
  padding: 12px 16px;
  margin-bottom: 8px;
}

.tag-assets-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

.tag-assets-count {
  font-size: 11px;
  color: #409EFF;
  background: #fff;
  padding: 2px 8px;
  border-radius: 10px;
  border: 1px solid #409EFF;
}

.tag-assets-list {
  max-height: 40vh;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.tag-assets-list .el-empty {
  grid-column: 1 / -1;
}

.tag-asset-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid #d9ecff;
  border-radius: 6px;
  background: #fff;
}

.tag-asset-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
  padding-right: 12px;
}

.tag-asset-symbol {
  font-weight: 600;
  font-size: 13px;
  color: #409EFF;
}

.tag-asset-name {
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Asset Tag Section */
.asset-tag-section {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.asset-autocomplete {
  position: relative;
  width: 100%;
  margin-bottom: 16px;
}

.asset-search-input {
  width: 100%;
}

.asset-dropdown {
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

.asset-dropdown-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
  gap: 12px;
}

.asset-dropdown-item:hover,
.asset-dropdown-item.active {
  background-color: #f5f7fa;
}

.asset-dropdown-item.selected {
  background-color: #ecf5ff;
}

.asset-dropdown-item .asset-symbol {
  font-weight: 600;
  color: #409eff;
  min-width: 60px;
}

.asset-dropdown-item .asset-name {
  color: #606266;
  flex: 1;
}

.asset-dropdown-empty {
  padding: 20px;
  text-align: center;
  color: #909399;
  font-size: 14px;
}

.asset-tags-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.assigned-tags-group {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.asset-tag-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.asset-tag-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e6e6e6;
  border-left-width: 4px;
  transition: all 0.3s ease;
}

.asset-tag-item:hover {
  background: #f5f7fa;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.asset-tag-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.weight-bar-container {
  display: flex;
  align-items: center;
  gap: 8px;
}

.weight-bar-container .el-progress {
  flex: 1;
}

.weight-text {
  font-size: 12px;
  color: #606266;
  min-width: 40px;
  text-align: right;
}

.asset-tag-actions {
  display: flex;
  gap: 4px;
  margin-left: 8px;
  opacity: 0;
  transition: opacity 0.3s;
}

.asset-tag-item:hover .asset-tag-actions {
  opacity: 1;
}

/* Pending Tags */
.pending-tag-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e6e6e6;
  border-left: 4px solid #409EFF;
  transition: all 0.3s ease;
}

.pending-tag-item.invalid {
  background: #fef0f0;
  border-color: #F56C6C;
  border-left-color: #F56C6C;
}

.pending-tag-item:hover {
  background: #f5f7fa;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.pending-tag-item.invalid:hover {
  background: #fde2e2;
}

.pending-tag-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pending-tag-actions {
  display: flex;
  gap: 4px;
  margin-left: 8px;
  opacity: 0;
  transition: opacity 0.3s;
}

.pending-tag-item:hover .pending-tag-actions {
  opacity: 1;
}

.validation-alert {
  margin-top: 12px;
}

/* Weight Summary */
.weight-summary {
  margin: 8px 10px 12px;
  padding: 12px;
  border-radius: 8px;
  background: #f5f7fa;
}

.weight-summary-title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  font-size: 14px;
}

.weight-summary-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.summary-category {
  min-width: 80px;
  font-size: 13px;
  color: #606266;
}

.weight-summary-item .el-progress {
  flex: 1;
}

.summary-status {
  min-width: 50px;
  text-align: right;
  font-size: 13px;
  font-weight: 500;
}

.summary-status.complete {
  color: #67C23A;
}

.summary-status.incomplete {
  color: #F56C6C;
}

/* Weight hint in dialog */
.weight-hint {
  margin-top: 8px;
}

.weight-hint .el-alert {
  margin-bottom: 8px;
}

.weight-tip {
  margin: 8px 0 0 0;
  font-size: 12px;
  color: #909399;
  font-style: italic;
}

/* Scrollbar styling */
.category-tags-list::-webkit-scrollbar,
.asset-tag-list::-webkit-scrollbar,
.tag-assets-list::-webkit-scrollbar {
  width: 6px;
}

.category-tags-list::-webkit-scrollbar-thumb,
.asset-tag-list::-webkit-scrollbar-thumb,
.tag-assets-list::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 3px;
}

.category-tags-list::-webkit-scrollbar-track,
.asset-tag-list::-webkit-scrollbar-track,
.tag-assets-list::-webkit-scrollbar-track {
  background: #f5f7fa;
}

/* Responsive */
@media (max-width: 768px) {
  .section-card {
    height: auto;
    min-height: 400px;
    margin-bottom: 16px;
  }
}
</style>
