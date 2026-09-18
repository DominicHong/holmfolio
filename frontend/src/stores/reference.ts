import { defineStore } from 'pinia'
import apiClient from '@/utils/apiClient'
import type { Currency, ExchangeRate, Tag, TagCategory, AssetTag, Benchmark } from '@/types/models'

interface ReferenceState {
  currencies: Currency[]
  exchangeRates: ExchangeRate[]
  primaryCurrency: Currency | null
  tagCategories: TagCategory[]
  tags: Tag[]
  assetTags: AssetTag[]
  benchmarks: Benchmark[]
}

export const useReferenceStore = defineStore('reference', {
  state: (): ReferenceState => ({
    currencies: [],
    exchangeRates: [],
    primaryCurrency: null,
    tagCategories: [],
    tags: [],
    assetTags: [],
    benchmarks: []
  }),

  getters: {},

  actions: {
    setCurrencies(currencies: Currency[]) {
      this.currencies = currencies
      this.primaryCurrency = currencies.find(c => c.is_primary) || null
    },

    setExchangeRates(rates: ExchangeRate[]) {
      this.exchangeRates = rates
    },

    setTagCategories(categories: TagCategory[]) {
      this.tagCategories = categories
    },

    setTags(tags: Tag[]) {
      this.tags = tags
    },

    setAssetTags(assetTags: AssetTag[]) {
      this.assetTags = assetTags
    },

    setBenchmarks(benchmarks: Benchmark[]) {
      this.benchmarks = benchmarks
    },

    async fetchCurrencies(): Promise<Currency[]> {
      const response = await apiClient.get<Currency[]>('/currencies/')
      this.setCurrencies(response.data)
      return response.data
    },

    async fetchExchangeRates(): Promise<ExchangeRate[]> {
      const response = await apiClient.get<ExchangeRate[]>('/currencies/exchange-rates/')
      this.setExchangeRates(response.data)
      return response.data
    },

    async fetchTagCategories(): Promise<TagCategory[]> {
      const response = await apiClient.get<TagCategory[]>('/tag-categories/')
      this.setTagCategories(response.data)
      return response.data
    },

    async createTagCategory(categoryData: Partial<TagCategory>): Promise<TagCategory> {
      const response = await apiClient.post<TagCategory>('/tag-categories/', categoryData)
      this.tagCategories.push(response.data)
      return response.data
    },

    async updateTagCategory(categoryId: number, categoryData: Partial<TagCategory>): Promise<TagCategory> {
      const response = await apiClient.put<TagCategory>(`/tag-categories/${categoryId}`, categoryData)
      const index = this.tagCategories.findIndex(c => c.id === categoryId)
      if (index !== -1) {
        this.tagCategories[index] = response.data
      }
      return response.data
    },

    async deleteTagCategory(categoryId: number): Promise<boolean> {
      await apiClient.delete(`/tag-categories/${categoryId}`)
      this.tagCategories = this.tagCategories.filter(c => c.id !== categoryId)
      return true
    },

    async fetchTags(categoryId: number | null = null): Promise<Tag[]> {
      const params = categoryId ? { category_id: categoryId } : {}
      const response = await apiClient.get<Tag[]>('/tags/', { params })
      this.setTags(response.data)
      return response.data
    },

    async createTag(tagData: Partial<Tag>): Promise<Tag> {
      const response = await apiClient.post<Tag>('/tags/', tagData)
      this.tags.push(response.data)
      return response.data
    },

    async updateTag(tagId: number, tagData: Partial<Tag>): Promise<Tag> {
      const response = await apiClient.put<Tag>(`/tags/${tagId}`, tagData)
      const index = this.tags.findIndex(t => t.id === tagId)
      if (index !== -1) {
        this.tags[index] = response.data
      }
      return response.data
    },

    async deleteTag(tagId: number): Promise<boolean> {
      await apiClient.delete(`/tags/${tagId}`)
      this.tags = this.tags.filter(t => t.id !== tagId)
      return true
    },

    async fetchAssetTags(assetId: number | null = null, tagId: number | null = null): Promise<AssetTag[]> {
      const params: Record<string, number> = {}
      if (assetId) params.asset_id = assetId
      if (tagId) params.tag_id = tagId
      const response = await apiClient.get<AssetTag[]>('/tags/asset-tags/', { params })
      this.setAssetTags(response.data)
      return response.data
    },

    async createAssetTag(assetTagData: Partial<AssetTag>): Promise<AssetTag> {
      const response = await apiClient.post<AssetTag>('/tags/asset-tags/', assetTagData)
      this.assetTags.push(response.data)
      return response.data
    },

    async updateAssetTag(assetTagId: number, assetTagData: Partial<AssetTag>): Promise<AssetTag> {
      const response = await apiClient.put<AssetTag>(`/tags/asset-tags/${assetTagId}`, assetTagData)
      const index = this.assetTags.findIndex(at => at.id === assetTagId)
      if (index !== -1) {
        this.assetTags[index] = response.data
      }
      return response.data
    },

    async deleteAssetTag(assetTagId: number): Promise<boolean> {
      await apiClient.delete(`/tags/asset-tags/${assetTagId}`)
      this.assetTags = this.assetTags.filter(at => at.id !== assetTagId)
      return true
    },

    async fetchBenchmarks(): Promise<Benchmark[]> {
      const response = await apiClient.get<Benchmark[]>('/benchmarks/')
      this.setBenchmarks(response.data)
      return response.data
    }
  }
})
