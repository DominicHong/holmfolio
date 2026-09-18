import { defineStore } from 'pinia'
import apiClient from '@/utils/apiClient'
import type { Portfolio, Position } from '@/types/models'

interface PortfolioState {
  portfolios: Portfolio[]
  currentPortfolio: Portfolio | null
  positions: Position[]
}

export const usePortfolioStore = defineStore('portfolio', {
  state: (): PortfolioState => ({
    portfolios: [],
    currentPortfolio: null,
    positions: []
  }),

  getters: {
    currentPortfolioId: (state): number | undefined => state.currentPortfolio?.id,

    totalPortfolioValue: (state): number => {
      return state.positions.reduce((total, position) => {
        return total + (position.market_value || 0)
      }, 0)
    },

    totalPnL: (state): number => {
      return state.positions.reduce((total, position) => {
        return total + (position.total_pnl || 0)
      }, 0)
    }
  },

  actions: {
    setPortfolios(portfolios: Portfolio[]) {
      this.portfolios = portfolios
    },

    setCurrentPortfolio(portfolio: Portfolio | null) {
      this.currentPortfolio = portfolio
    },

    setPositions(positions: Position[]) {
      this.positions = positions
    },

    async fetchPortfolios(): Promise<Portfolio[]> {
      const response = await apiClient.get<Portfolio[]>('/portfolios/')
      this.setPortfolios(response.data)

      if (response.data.length > 0 && !this.currentPortfolio) {
        this.setCurrentPortfolio(response.data[0])
      }
      return response.data
    },

    async createPortfolio(portfolioData: Partial<Portfolio>): Promise<Portfolio> {
      const response = await apiClient.post<Portfolio>('/portfolios/', portfolioData)
      this.setCurrentPortfolio(response.data)
      return response.data
    },

    async fetchPositions(portfolioId: number, asOfDate: string | null = null): Promise<Position[]> {
      const params = asOfDate ? { as_of_date: asOfDate } : {}
      const response = await apiClient.get<Position[]>(`/portfolios/${portfolioId}/positions`, { params })
      this.setPositions(response.data)
      return response.data
    },

    async recalculatePositions({ portfolioId, asOfDate }: { portfolioId: number; asOfDate: string | null }): Promise<any> {
      const params = asOfDate ? { as_of_date: asOfDate } : {}
      const response = await apiClient.post(`/portfolios/${portfolioId}/recalculate-positions`, null, { params })
      const positionsParams = asOfDate ? { as_of_date: asOfDate } : {}
      const positionsResponse = await apiClient.get<Position[]>(`/portfolios/${portfolioId}/positions`, { params: positionsParams })
      this.setPositions(positionsResponse.data)
      return response.data
    }
  }
})
