import { defineStore } from 'pinia'
import apiClient from '@/utils/apiClient'
import type { AddDividendsResponse, CheckDividendsResponse, MissingDividendItem, Transaction } from '@/types/models'

interface TransactionState {
  transactions: Transaction[]
}

export const useTransactionStore = defineStore('transaction', {
  state: (): TransactionState => ({
    transactions: []
  }),

  getters: {
    transactionsByType: (state): Record<string, Transaction[]> => {
      const grouped: Record<string, Transaction[]> = {}
      state.transactions.forEach(transaction => {
        if (!grouped[transaction.action]) {
          grouped[transaction.action] = []
        }
        grouped[transaction.action].push(transaction)
      })
      return grouped
    },

    recentTransactions: (state): Transaction[] => {
      return [...state.transactions]
        .sort((a, b) => new Date(b.trade_date).getTime() - new Date(a.trade_date).getTime())
        .slice(0, 10)
    }
  },

  actions: {
    setTransactions(transactions: Transaction[]) {
      this.transactions = transactions
    },

    addTransaction(transaction: Transaction) {
      this.transactions.push(transaction)
    },

    async fetchTransactions(portfolioId: number): Promise<Transaction[]> {
      const response = await apiClient.get<Transaction[]>('/transactions/', { params: { portfolio_id: portfolioId } })
      this.setTransactions(response.data)
      return response.data
    },

    async createTransaction(transactionData: Partial<Transaction>): Promise<Transaction> {
      const response = await apiClient.post<Transaction>('/transactions/', transactionData)
      this.addTransaction(response.data)
      return response.data
    },

    async importXueqiuTransactions(file: File, portfolioId: number): Promise<any> {
      const formData = new FormData()
      formData.append('file', file)

      const response = await apiClient.post('/import/xueqiu-transactions/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        params: { portfolio_id: portfolioId }
      })

      return response.data
    },

    async alignXueqiuTransactions(file: File, portfolioId: number): Promise<any> {
      const formData = new FormData()
      formData.append('file', file)

      const response = await apiClient.post('/import/xueqiu-align/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        params: { portfolio_id: portfolioId }
      })

      return response.data
    },

    async deleteAllTransactions(portfolioId: number): Promise<any> {
      const response = await apiClient.delete('/transactions/', { params: { portfolio_id: portfolioId } })
      this.setTransactions([])
      return response.data
    },

    async checkDividends(portfolioId: number): Promise<CheckDividendsResponse> {
      const response = await apiClient.post<CheckDividendsResponse>('/transactions/check-dividends/', { portfolio_id: portfolioId })
      return response.data
    },

    async addDividends(portfolioId: number, items: MissingDividendItem[]): Promise<AddDividendsResponse> {
      const response = await apiClient.post<AddDividendsResponse>('/transactions/add-dividends/', { portfolio_id: portfolioId, items })
      return response.data
    },

    async deleteTransaction(transactionId: number): Promise<any> {
      const response = await apiClient.delete(`/transactions/${transactionId}`)
      this.transactions = this.transactions.filter(t => t.id !== transactionId)
      return response.data
    },

    async updateTransaction(transactionId: number, transactionData: Partial<Transaction>): Promise<Transaction> {
      const response = await apiClient.put<Transaction>(`/transactions/${transactionId}`, transactionData)
      const index = this.transactions.findIndex(t => t.id === transactionId)
      if (index !== -1) {
        this.transactions[index] = response.data
      }
      return response.data
    }
  }
})
