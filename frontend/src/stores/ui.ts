import { defineStore } from 'pinia'
import apiClient from '@/utils/apiClient'
import type { Setting } from '@/types/models'

interface UIState {
  loadingCount: number
  error: string | null
  settings: Record<string, Setting>
}

export const useUIStore = defineStore('ui', {
  state: (): UIState => ({
    loadingCount: 0,
    error: null,
    settings: {}
  }),

  getters: {
    loading: (state): boolean => state.loadingCount > 0
  },

  actions: {
    setLoading(isLoading: boolean) {
      if (isLoading) {
        this.loadingCount++
      } else {
        this.loadingCount = Math.max(0, this.loadingCount - 1)
      }
    },

    setError(error: string | null) {
      this.error = error
    },

    setSettings(settings: Record<string, Setting>) {
      this.settings = settings
    },

    setSetting(key: string, value: Setting) {
      this.settings[key] = value
    },

    async fetchSettings(): Promise<Setting[]> {
      try {
        this.setLoading(true)
        const response = await apiClient.get<Setting[]>('/settings/')
        const settingsObj: Record<string, Setting> = {}
        response.data.forEach(setting => {
          settingsObj[setting.key] = setting
        })
        this.setSettings(settingsObj)
        return response.data
      } catch (error: any) {
        this.setError(error.message)
        throw error
      } finally {
        this.setLoading(false)
      }
    },

    async fetchSetting(key: string): Promise<Setting> {
      try {
        const response = await apiClient.get<Setting>(`/settings/${key}`)
        this.setSetting(key, response.data)
        return response.data
      } catch (error: any) {
        this.setError(error.message)
        throw error
      }
    },

    async saveSetting(key: string, value: string | number, description: string | null = null): Promise<Setting> {
      try {
        this.setLoading(true)
        const settingData = {
          key: key,
          value: value.toString(),
          description: description
        }
        const response = await apiClient.post<Setting>('/settings/', settingData)
        this.setSetting(key, response.data)
        return response.data
      } catch (error: any) {
        this.setError(error.message)
        throw error
      } finally {
        this.setLoading(false)
      }
    },

    async updatePricesAndRates(endDate: string): Promise<any> {
      try {
        this.setLoading(true)
        const response = await apiClient.post('/import/update-prices-and-rates/', {
          end_date: endDate
        })
        return response.data
      } catch (error: any) {
        this.setError(error.message)
        throw error
      } finally {
        this.setLoading(false)
      }
    }
  }
})
