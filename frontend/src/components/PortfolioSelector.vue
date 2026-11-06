<template>
  <el-dropdown
    class="portfolio-selector"
    :class="{ collapsed }"
    trigger="click"
    placement="bottom-start"
    @command="handleCommand"
  >
    <button class="portfolio-trigger" type="button" :title="currentName">
      <el-icon class="portfolio-icon"><Briefcase /></el-icon>
      <template v-if="!collapsed">
        <span class="portfolio-name">{{ currentName }}</span>
        <el-icon class="caret"><ArrowDown /></el-icon>
      </template>
    </button>

    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-for="portfolio in portfolios"
          :key="portfolio.id"
          :command="portfolio.id"
          :class="{ 'is-current': portfolio.id === currentPortfolioId }"
        >
          <span class="menu-name">{{ portfolio.name }}</span>
          <el-icon v-if="portfolio.id === currentPortfolioId" class="check">
            <Check />
          </el-icon>
        </el-dropdown-item>

        <el-dropdown-item v-if="portfolios.length === 0" disabled>
          No portfolios
        </el-dropdown-item>

        <el-dropdown-item divided command="manage">
          <el-icon><Setting /></el-icon>
          Manage Portfolios
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, Briefcase, Check, Setting } from '@element-plus/icons-vue'
import { usePortfolioStore } from '@/stores'

withDefaults(
  defineProps<{
    collapsed?: boolean
  }>(),
  {
    collapsed: false
  }
)

const portfolioStore = usePortfolioStore()
const router = useRouter()

const portfolios = computed(() => portfolioStore.portfolios)
const currentPortfolioId = computed(() => portfolioStore.currentPortfolioId)
const currentName = computed(
  () => portfolioStore.currentPortfolio?.name || 'Select Portfolio'
)

const handleCommand = (command: string | number) => {
  if (command === 'manage') {
    router.push({ name: 'Portfolios' })
    return
  }
  if (typeof command === 'number') {
    portfolioStore.selectPortfolioById(command)
  }
}

onMounted(() => {
  if (portfolioStore.portfolios.length === 0) {
    portfolioStore.fetchPortfolios().catch(() => {
      // The page-level error handlers report API failures. The selector can
      // stay empty until the next refresh.
    })
  }
})
</script>

<style scoped>
.portfolio-selector {
  display: block;
  width: 100%;
  padding: 10px 12px 4px;
  box-sizing: border-box;
}

.portfolio-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #ffffff;
  color: #303133;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease;
}

.portfolio-trigger:hover {
  border-color: #409eff;
  color: #409eff;
}

.portfolio-icon {
  flex-shrink: 0;
}

.portfolio-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.caret {
  flex-shrink: 0;
  font-size: 12px;
  color: #909399;
}

.collapsed {
  padding-left: 8px;
  padding-right: 8px;
}

.collapsed .portfolio-trigger {
  justify-content: center;
  padding: 8px;
}

.menu-name {
  margin-right: 16px;
}

.check {
  color: #409eff;
  margin-left: auto;
}

:deep(.el-dropdown-menu__item.is-current) {
  color: #409eff;
  font-weight: 600;
}
</style>
