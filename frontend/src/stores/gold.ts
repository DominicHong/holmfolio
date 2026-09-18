import { defineStore } from 'pinia'
import apiClient from '@/utils/apiClient'
import type { Asset, GoldOverview } from '@/types/models'

interface GoldOverviewParams {
  portfolio_id: number
  asset_id: number
  strategy: string
  start_date?: string
  end_date?: string
}

interface GoldState {
  assets: Asset[]
  overview: GoldOverview | null
  updatingPrices: boolean
}

export const useGoldStore = defineStore('gold', {
  state: (): GoldState => ({
    assets: [],
    overview: null,
    updatingPrices: false
  }),

  getters: {
    hasGoldAssets: (state): boolean => state.assets.length > 0
  },

  actions: {
    setOverview(overview: GoldOverview | null) {
      this.overview = overview
    },

    async fetchAssets(): Promise<Asset[]> {
      const response = await apiClient.get<Asset[]>('/gold/assets')
      this.assets = response.data
      return response.data
    },

    async fetchOverview(params: GoldOverviewParams): Promise<GoldOverview> {
      const response = await apiClient.get<GoldOverview>('/gold/overview', { params })
      this.setOverview(response.data)
      return response.data
    },

    async updatePrices(): Promise<{ added: number; errors: string[] }> {
      this.updatingPrices = true
      try {
        const response = await apiClient.post<{ added: number; errors: string[] }>(
          '/gold/update-prices'
        )
        return response.data
      } finally {
        this.updatingPrices = false
      }
    }
  }
})
