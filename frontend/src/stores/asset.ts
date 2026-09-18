import { defineStore } from 'pinia'
import apiClient from '@/utils/apiClient'
import type { Asset } from '@/types/models'

interface AssetState {
  assets: Asset[]
  prices: any[]
}

export const useAssetStore = defineStore('asset', {
  state: (): AssetState => ({
    assets: [],
    prices: []
  }),

  getters: {
    assetsByType: (state): Record<string, Asset[]> => {
      const grouped: Record<string, Asset[]> = {}
      state.assets.forEach(asset => {
        if (!grouped[asset.type]) {
          grouped[asset.type] = []
        }
        grouped[asset.type].push(asset)
      })
      return grouped
    }
  },

  actions: {
    setAssets(assets: Asset[]) {
      this.assets = assets
    },

    addAsset(asset: Asset) {
      this.assets.push(asset)
    },

    setPrices(prices: any[]) {
      this.prices = prices
    },

    async fetchAssets(): Promise<Asset[]> {
      const response = await apiClient.get<Asset[]>('/assets/')
      this.setAssets(response.data)
      return response.data
    },

    async createAsset(assetData: Partial<Asset>): Promise<Asset> {
      const response = await apiClient.post<Asset>('/assets/', assetData)
      this.addAsset(response.data)
      return response.data
    },

    async updateAsset(assetId: number, assetData: Partial<Asset>): Promise<Asset> {
      const response = await apiClient.put<Asset>(`/assets/${assetId}`, assetData)
      const index = this.assets.findIndex(asset => asset.id === assetId)
      if (index !== -1) {
        this.assets[index] = response.data
      }
      return response.data
    },

    async deleteAsset(assetId: number): Promise<boolean> {
      await apiClient.delete(`/assets/${assetId}`)
      this.assets = this.assets.filter(asset => asset.id !== assetId)
      return true
    }
  }
})
