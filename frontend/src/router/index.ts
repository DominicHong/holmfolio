import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Portfolio from '../views/Portfolio.vue'
import PositionDetail from '../views/PositionDetail.vue'
import Transactions from '../views/Transactions.vue'
import Assets from '../views/Assets.vue'
import Analytics from '../views/Analytics.vue'
import Settings from '../views/Settings.vue'
import TagManagement from '../views/TagManagement.vue'
import Financial from '../views/Financial.vue'
import Gold from '../views/Gold.vue'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard,
    meta: { keepAlive: true }
  },
  {
    path: '/portfolio',
    name: 'Portfolio',
    component: Portfolio,
    meta: { keepAlive: true }
  },
  {
    path: '/positions/:assetId',
    name: 'PositionDetail',
    component: PositionDetail,
    props: true,
    meta: { keepAlive: false }
  },
  {
    path: '/transactions',
    name: 'Transactions',
    component: Transactions,
    meta: { keepAlive: true }
  },
  {
    path: '/assets',
    name: 'Assets',
    component: Assets,
    meta: { keepAlive: true }
  },
  {
    path: '/tags',
    name: 'TagManagement',
    component: TagManagement,
    meta: { keepAlive: true }
  },
  {
    path: '/financial',
    name: 'Financial',
    component: Financial,
    meta: { keepAlive: true }
  },
  {
    path: '/gold',
    name: 'Gold',
    component: Gold,
    meta: { keepAlive: true }
  },
  {
    path: '/analytics',
    name: 'Analytics',
    component: Analytics,
    meta: { keepAlive: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
    meta: { keepAlive: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
