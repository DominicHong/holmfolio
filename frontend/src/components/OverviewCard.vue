<template>
  <el-card class="overview-card">
    <div class="card-header">
      <span class="card-title">
        <slot name="title-prefix" />
        {{ title }}
      </span>
    </div>
    <div v-if="loading" class="card-loading">
      <el-icon class="is-loading">
        <Loading />
      </el-icon>
    </div>
    <template v-else>
      <div class="card-value" :class="valueClass">
        {{ value }}
      </div>
      <div v-if="subtitle" class="card-subtitle">
        {{ subtitle }}
      </div>
    </template>
  </el-card>
</template>

<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'

interface Props {
  title: string
  value: string | number
  subtitle?: string
  valueClass?: 'positive' | 'negative' | 'neutral' | ''
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  subtitle: '',
  valueClass: '',
  loading: false
})
</script>

<style scoped>
.overview-card {
  text-align: center;
  border: none;
  border-radius: 16px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.overview-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}

.overview-card :deep(.el-card__body) {
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
}

.card-title {
  font-size: 13px;
  color: #606266;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.card-value {
  font-size: 24px;
  font-weight: 800;
  color: #303133;
  margin-bottom: 6px;
  line-height: 1.2;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.card-subtitle {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-weight: 500;
}

.card-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  color: #409eff;
}

.card-loading .el-icon {
  font-size: 24px;
}

.positive {
  color: #67c23a !important;
}

.negative {
  color: #f56c6c !important;
}

.neutral {
  color: #909399 !important;
}

/* Delta triangle colors in card title */
.card-title :deep(.positive),
.card-title :deep(.negative),
.card-title :deep(.neutral) {
  margin-right: 4px;
}
</style>
