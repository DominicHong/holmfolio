import { defineStore } from 'pinia'
import dayjs from 'dayjs'
import apiClient from '@/utils/apiClient'

interface AnalyticsOptions {
  startDate?: string | null
  endDate?: string | null
  benchmarkId?: number | null
  tagCategoryId?: number | string | null
  by?: string
  frequency?: string
  assetId?: number | null
  topN?: number | null
}

interface AnalyticsState {
  portfolioStats: any
  assetAllocation: any
  performanceHistory: any[]
  recentReturns: any[]
  tagCorrelation: any
  tagBeta: any
  assetBetaMvTop10: any
  assetBetaTopBottom: any
}

export const useAnalyticsStore = defineStore('analytics', {
  state: (): AnalyticsState => ({
    portfolioStats: {},
    assetAllocation: {},
    performanceHistory: [],
    recentReturns: [],
    tagCorrelation: null,
    tagBeta: null,
    assetBetaMvTop10: null,
    assetBetaTopBottom: null
  }),

  getters: {},

  actions: {
    setPortfolioStats(stats: any) {
      this.portfolioStats = stats
    },

    setAssetAllocation(allocation: any) {
      this.assetAllocation = allocation
    },

    setPerformanceHistory(history: any[]) {
      this.performanceHistory = history
    },

    setRecentReturns(returns: any[]) {
      this.recentReturns = returns
    },

    setTagCorrelation(data: any) {
      this.tagCorrelation = data
    },

    setTagBeta(data: any) {
      this.tagBeta = data
    },

    setAssetBetaMvTop10(data: any) {
      this.assetBetaMvTop10 = data
    },

    setAssetBetaTopBottom(data: any) {
      this.assetBetaTopBottom = data
    },

    async fetchPerformanceMetrics(portfolioId: number, options: AnalyticsOptions = {}): Promise<any> {
      const params: Record<string, any> = {}
      if (options.startDate) params.start_date = options.startDate
      if (options.endDate) params.end_date = options.endDate
      if (options.benchmarkId) params.benchmark_id = options.benchmarkId
      const response = await apiClient.get(`/portfolios/${portfolioId}/performance-metrics`, { params })
      this.setPortfolioStats(response.data)
      return response.data
    },

    async fetchPerformanceHistory(portfolioId: number, options: AnalyticsOptions = {}): Promise<any> {
      const { startDate, endDate, benchmarkId } = options

      let params: Record<string, string> = {}
      if (startDate && endDate) {
        params = { start_date: startDate, end_date: endDate }
      } else {
        const end = new Date()
        const start = new Date(end)
        start.setDate(start.getDate() - 365)

        params = {
          start_date: dayjs(start).format('YYYY-MM-DD'),
          end_date: dayjs(end).format('YYYY-MM-DD')
        }
      }

      if (benchmarkId) {
        params.benchmark_id = String(benchmarkId)
      }

      const response = await apiClient.get(`/portfolios/${portfolioId}/performance-history`, { params })
      this.setPerformanceHistory(response.data)
      return response.data
    },

    async fetchRecentReturns(portfolioId: number, options: AnalyticsOptions = {}): Promise<any> {
      const params: Record<string, any> = {}
      if (options.endDate) {
        params.end_date = options.endDate
      }
      if (options.benchmarkId) {
        params.benchmark_id = options.benchmarkId
      }
      const response = await apiClient.get(`/portfolios/${portfolioId}/recent-returns`, { params })
      this.setRecentReturns(response.data)
      return response.data
    },

    async fetchAssetAllocation(portfolioId: number, asOfDate: string | null, options: AnalyticsOptions = {}): Promise<any> {
      const params: Record<string, any> = { by: options.by || 'type' }
      if (asOfDate) {
        params.as_of_date = asOfDate
      }
      if (options.tagCategoryId) {
        params.tag_category_id = options.tagCategoryId
      }
      const response = await apiClient.get(`/portfolios/${portfolioId}/allocation`, { params })
      this.setAssetAllocation(response.data.asset_allocation || {})
      return response.data
    },

    async fetchTagCorrelation(portfolioId: number, options: AnalyticsOptions = {}): Promise<any> {
      try {
        const params = {
          start_date: options.startDate,
          end_date: options.endDate,
          tag_category_id: options.tagCategoryId
        }
        const response = await apiClient.get(`/portfolios/${portfolioId}/tag-correlation`, { params })
        this.setTagCorrelation(response.data)
        return response.data
      } catch (error) {
        this.setTagCorrelation(null)
        throw error
      }
    },

    async fetchTagBeta(portfolioId: number, options: AnalyticsOptions = {}): Promise<any> {
      try {
        const params = {
          start_date: options.startDate,
          end_date: options.endDate,
          tag_category_id: options.tagCategoryId,
          benchmark_id: options.benchmarkId,
          frequency: options.frequency || 'daily',
        }
        const response = await apiClient.get(`/portfolios/${portfolioId}/tag-beta`, { params })
        this.setTagBeta(response.data)
        return response.data
      } catch (error) {
        this.setTagBeta(null)
        throw error
      }
    },

    async fetchAssetBetaMvTop10(portfolioId: number, options: AnalyticsOptions = {}): Promise<any> {
      try {
        const params: Record<string, any> = {
          start_date: options.startDate,
          end_date: options.endDate,
          benchmark_id: options.benchmarkId,
          frequency: options.frequency || 'daily',
        }
        if (options.assetId) {
          params.asset_id = options.assetId
        }
        if (options.topN) {
          params.top_n = options.topN
        }
        const response = await apiClient.get(`/portfolios/${portfolioId}/asset-beta`, { params })
        this.setAssetBetaMvTop10(response.data)
        return response.data
      } catch (error) {
        this.setAssetBetaMvTop10(null)
        throw error
      }
    },

    async fetchAssetBetaTopBottom(portfolioId: number, options: AnalyticsOptions = {}): Promise<any> {
      try {
        const params: Record<string, any> = {
          start_date: options.startDate,
          end_date: options.endDate,
          benchmark_id: options.benchmarkId,
          frequency: options.frequency || 'daily',
          top_n: options.topN || 1000,
        }
        const response = await apiClient.get(`/portfolios/${portfolioId}/asset-beta`, { params })
        this.setAssetBetaTopBottom(response.data)
        return response.data
      } catch (error) {
        this.setAssetBetaTopBottom(null)
        throw error
      }
    }
  }
})
