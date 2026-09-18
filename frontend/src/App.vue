<template>
  <div id="app">
    <el-container style="height: 100vh">
      <!-- Sidebar -->
      <div
        class="sidebar"
        :class="{ collapsed: isCollapsed, resizing: isResizing }"
        :style="{ width: currentWidth + 'px' }"
      >
        <div class="sidebar-header">
          <span v-show="!isCollapsed" class="logo-text">HolmFolio</span>
        </div>

        <el-menu
          :default-active="$route.path"
          :collapse="isCollapsed"
          :collapse-transition="false"
          mode="vertical"
          router
          class="sidebar-menu"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>Dashboard</span>
          </el-menu-item>
          <el-menu-item index="/analytics">
            <el-icon><DataAnalysis /></el-icon>
            <span>Analytics</span>
          </el-menu-item>
          <el-menu-item index="/portfolio">
            <el-icon><TrendCharts /></el-icon>
            <span>Portfolio</span>
          </el-menu-item>
          <el-menu-item index="/financial">
            <el-icon><Coin /></el-icon>
            <span>Financial</span>
          </el-menu-item>
          <el-menu-item index="/gold">
            <el-icon><GoldMedal /></el-icon>
            <span>Gold</span>
          </el-menu-item>
          <el-menu-item index="/transactions">
            <el-icon><List /></el-icon>
            <span>Transactions</span>
          </el-menu-item>
          <el-menu-item index="/assets">
            <el-icon><Goods /></el-icon>
            <span>Assets</span>
          </el-menu-item>
          <el-menu-item index="/tags">
            <el-icon><CollectionTag /></el-icon>
            <span>Tags</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>Settings</span>
          </el-menu-item>
        </el-menu>

        <div class="sidebar-footer">
          <el-button
            class="collapse-btn"
            :class="{ collapsed: isCollapsed }"
            text
            @click="toggleCollapse"
          >
            <el-icon>
              <Fold v-if="!isCollapsed" />
              <Expand v-else />
            </el-icon>
            <span v-show="!isCollapsed">Collapse</span>
          </el-button>
        </div>

        <div
          v-if="!isCollapsed"
          class="resize-handle"
          @mousedown="startResize"
        />
      </div>

      <!-- Main Content -->
      <el-main
        v-loading="uiStore.loading"
        element-loading-text="Loading..."
        element-loading-background="rgba(255, 255, 255, 0.7)"
        style="background-color: #ffffff"
      >
        <router-view v-slot="{ Component }">
          <keep-alive :include="cachedViewNames" :max="8">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import { useUIStore } from './stores/ui'
import {
  TrendCharts,
  HomeFilled,
  List,
  Goods,
  CollectionTag,
  DataAnalysis,
  Setting,
  Coin,
  GoldMedal,
  Fold,
  Expand
} from '@element-plus/icons-vue'

const uiStore = useUIStore()

const cachedViewNames = [
  'Dashboard',
  'Portfolio',
  'Financial',
  'Gold',
  'Transactions',
  'Assets',
  'TagManagement',
  'Analytics',
  'Settings'
]

const DEFAULT_WIDTH = 200
const COLLAPSED_WIDTH = 64
const MIN_WIDTH = 160
const MAX_WIDTH = 360

const sidebarWidth = ref(DEFAULT_WIDTH)
const isCollapsed = ref(false)
const isResizing = ref(false)

let resizeMoveHandler: ((e: MouseEvent) => void) | null = null
let resizeUpHandler: (() => void) | null = null

const currentWidth = computed(() =>
  isCollapsed.value ? COLLAPSED_WIDTH : sidebarWidth.value
)

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

function startResize(event: MouseEvent) {
  if (isCollapsed.value) return
  event.preventDefault()
  isResizing.value = true
  document.body.classList.add('resizing')
  const startX = event.clientX
  const startWidth = sidebarWidth.value

  function onMouseMove(e: MouseEvent) {
    const delta = e.clientX - startX
    sidebarWidth.value = Math.max(
      MIN_WIDTH,
      Math.min(MAX_WIDTH, startWidth + delta)
    )
  }

  function onMouseUp() {
    isResizing.value = false
    document.body.classList.remove('resizing')
    if (resizeMoveHandler) {
      document.removeEventListener('mousemove', resizeMoveHandler)
      resizeMoveHandler = null
    }
    if (resizeUpHandler) {
      document.removeEventListener('mouseup', resizeUpHandler)
      resizeUpHandler = null
    }
  }

  resizeMoveHandler = onMouseMove
  resizeUpHandler = onMouseUp
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

onBeforeUnmount(() => {
  document.body.classList.remove('resizing')
  if (resizeMoveHandler) {
    document.removeEventListener('mousemove', resizeMoveHandler)
  }
  if (resizeUpHandler) {
    document.removeEventListener('mouseup', resizeUpHandler)
  }
})
</script>

<style>
#app {
  font-family: 'Avenir', Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}

body {
  margin: 0;
  padding: 0;
}

.el-main {
  padding: 20px;
  overflow: auto;
}

body.resizing {
  user-select: none;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
  color: #606266;
  letter-spacing: 0.3px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sidebar {
  display: flex;
  flex-direction: column;
  position: relative;
  background-color: #f8f9fa;
  border-right: 1px solid #e6e6e6;
  transition: width 0.25s ease;
  flex-shrink: 0;
}

.sidebar.resizing {
  transition: none;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 56px;
  background-color: #f0f2f5;
  color: #303133;
  border-bottom: 1px solid #e6e6e6;
  gap: 10px;
  padding: 0 16px;
  overflow: hidden;
  white-space: nowrap;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #303133;
}

.sidebar-menu {
  flex: 1;
  height: 0;
  border-right: none !important;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 100%;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid #e6e6e6;
  display: flex;
  justify-content: center;
}

.collapse-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #606266;
}

.collapse-btn:hover {
  color: #409eff;
}

.collapse-btn.collapsed {
  width: auto;
  padding: 8px;
}

.resize-handle {
  position: absolute;
  top: 0;
  right: -3px;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  z-index: 10;
  background: transparent;
}

.resize-handle:hover {
  background: rgba(64, 158, 255, 0.3);
}
</style>
