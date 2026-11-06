import { defineStore } from 'pinia'
import apiClient from '@/utils/apiClient'
import type { Portfolio, PortfolioSummary, Position } from '@/types/models'

const CURRENT_PORTFOLIO_STORAGE_KEY = 'holmfolio.currentPortfolioId'

let portfolioFetchSequence = 0
let summaryFetchSequence = 0

function readStoredPortfolioId(): number | null {
  try {
    const raw = localStorage.getItem(CURRENT_PORTFOLIO_STORAGE_KEY)
    if (!raw) return null
    const id = Number(raw)
    return Number.isInteger(id) ? id : null
  } catch {
    return null
  }
}

function writeStoredPortfolioId(id: number | null): void {
  try {
    if (id === null) {
      localStorage.removeItem(CURRENT_PORTFOLIO_STORAGE_KEY)
    } else {
      localStorage.setItem(CURRENT_PORTFOLIO_STORAGE_KEY, String(id))
    }
  } catch {
    // Storage can be unavailable in private/locked-down browser contexts.
  }
}

interface PortfolioState {
  portfolios: Portfolio[]
  currentPortfolio: Portfolio | null
  positions: Position[]
  summary: PortfolioSummary | null
}

export const usePortfolioStore = defineStore('portfolio', {
  state: (): PortfolioState => ({
    portfolios: [],
    currentPortfolio: null,
    positions: [],
    summary: null
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
      writeStoredPortfolioId(portfolio?.id ?? null)
    },

    selectPortfolio(portfolio: Portfolio) {
      this.setCurrentPortfolio(portfolio)
    },

    selectPortfolioById(portfolioId: number) {
      const portfolio = this.portfolios.find((item) => item.id === portfolioId)
      if (portfolio) {
        this.setCurrentPortfolio(portfolio)
      }
    },

    setPositions(positions: Position[]) {
      this.positions = positions
    },

    setSummary(summary: PortfolioSummary | null) {
      this.summary = summary
    },

    async fetchPortfolios(): Promise<Portfolio[]> {
      const requestId = ++portfolioFetchSequence
      const response = await apiClient.get<Portfolio[]>('/portfolios/')
      if (requestId !== portfolioFetchSequence) {
        return this.portfolios
      }

      const portfolios = response.data
      this.setPortfolios(portfolios)

      // Keep the user's current selection if it still exists. Otherwise
      // restore the last persisted selection, then fall back to the first
      // portfolio. This makes the selection survive navigation and reloads.
      const preferredId = this.currentPortfolio?.id ?? readStoredPortfolioId()
      const selected =
        portfolios.find((portfolio) => portfolio.id === preferredId) ??
        portfolios[0] ??
        null

      if (selected) {
        this.setCurrentPortfolio(selected)
      } else {
        this.setCurrentPortfolio(null)
      }

      return portfolios
    },

    async createPortfolio(portfolioData: Partial<Portfolio>): Promise<Portfolio> {
      const response = await apiClient.post<Portfolio>('/portfolios/', portfolioData)
      const created = response.data
      if (!this.portfolios.some((portfolio) => portfolio.id === created.id)) {
        this.portfolios.push(created)
      }
      this.setCurrentPortfolio(created)
      return created
    },

    async updatePortfolio(
      portfolioId: number,
      portfolioData: Partial<Portfolio>
    ): Promise<Portfolio> {
      const response = await apiClient.put<Portfolio>(
        `/portfolios/${portfolioId}`,
        portfolioData
      )
      const updated = response.data
      const index = this.portfolios.findIndex(
        (portfolio) => portfolio.id === portfolioId
      )
      if (index !== -1) {
        this.portfolios[index] = updated
      }
      if (this.currentPortfolio?.id === portfolioId) {
        this.currentPortfolio = updated
      }
      return updated
    },

    async deletePortfolio(portfolioId: number): Promise<void> {
      await apiClient.delete(`/portfolios/${portfolioId}`)
      this.portfolios = this.portfolios.filter(
        (portfolio) => portfolio.id !== portfolioId
      )

      if (this.currentPortfolio?.id === portfolioId) {
        this.setCurrentPortfolio(this.portfolios[0] ?? null)
      }
    },

    async fetchPortfolioSummary(asOfDate: string | null = null): Promise<PortfolioSummary> {
      const requestId = ++summaryFetchSequence
      const params = asOfDate ? { as_of_date: asOfDate } : {}
      const response = await apiClient.get<PortfolioSummary>('/portfolios/summary', {
        params
      })
      if (requestId === summaryFetchSequence) {
        this.setSummary(response.data)
      }
      return response.data
    },

    async fetchPositions(portfolioId: number, asOfDate: string | null = null): Promise<Position[]> {
      const params = asOfDate ? { as_of_date: asOfDate } : {}
      const response = await apiClient.get<Position[]>(`/portfolios/${portfolioId}/positions`, { params })
      // Ignore responses that belong to a portfolio the user has already
      // switched away from.
      if (this.currentPortfolioId === portfolioId) {
        this.setPositions(response.data)
      }
      return response.data
    },

    async recalculatePositions({ portfolioId, asOfDate }: { portfolioId: number; asOfDate: string | null }): Promise<any> {
      const params = asOfDate ? { as_of_date: asOfDate } : {}
      const response = await apiClient.post(`/portfolios/${portfolioId}/recalculate-positions`, null, { params })
      const positionsParams = asOfDate ? { as_of_date: asOfDate } : {}
      const positionsResponse = await apiClient.get<Position[]>(`/portfolios/${portfolioId}/positions`, { params: positionsParams })
      if (this.currentPortfolioId === portfolioId) {
        this.setPositions(positionsResponse.data)
      }
      return response.data
    }
  }
})
