import { ref } from 'vue'
import type { Ref } from 'vue'
import { formatDate } from '../utils/formatters'

interface TimeRangeOptions {
  onChange?: (startDate: string, endDate: string) => void | Promise<void>
  transactions?: any[] | Ref<any[]> | (() => any[])
}

interface DateRange {
  startDate: string
  endDate: string
}

/**
 * Composable for managing time range selection
 * @param options - Configuration options
 * @returns Time range state and methods
 */
export function useTimeRange(options: TimeRangeOptions = {}) {
  const { onChange, transactions = [] } = options

  const startDate = ref<string | null>(null)
  const endDate = ref<string | null>(null)
  const timeRange = ref(365) // Default to 1 year

  const getTransactions = (): any[] => {
    let txs: any[]
    if (typeof transactions === 'function') {
      txs = transactions()
    } else if ((transactions as Ref<any[]>).value !== undefined) {
      txs = (transactions as Ref<any[]>).value
    } else {
      txs = transactions as any[]
    }
    return Array.isArray(txs) ? txs : []
  }

  const calculateDateRange = (days: number): DateRange => {
    const today = new Date()
    let startDateCalc: Date

    if (days === 0) {
      const txs = getTransactions()
      if (txs.length > 0) {
        const sortedTransactions = [...txs].sort((a, b) =>
          new Date(a.trade_date).getTime() - new Date(b.trade_date).getTime()
        )
        startDateCalc = new Date(sortedTransactions[0].trade_date)
      } else {
        startDateCalc = new Date(today)
        startDateCalc.setDate(startDateCalc.getDate() - 365)
      }
    } else {
      startDateCalc = new Date(today)
      startDateCalc.setDate(startDateCalc.getDate() - days)
    }

    return {
      startDate: formatDate(startDateCalc),
      endDate: formatDate(today)
    }
  }

  const setTimeRange = async (days: number): Promise<void> => {
    timeRange.value = days
    const dates = calculateDateRange(days)
    startDate.value = dates.startDate
    endDate.value = dates.endDate

    if (onChange) {
      await onChange(dates.startDate, dates.endDate)
    }
  }

  const onDateRangeChange = async (): Promise<void> => {
    if (startDate.value && endDate.value && onChange) {
      await onChange(startDate.value, endDate.value)
    }
  }

  const initialize = (): DateRange => {
    const dates = calculateDateRange(timeRange.value)
    startDate.value = dates.startDate
    endDate.value = dates.endDate
    return dates
  }

  return {
    startDate,
    endDate,
    timeRange,
    setTimeRange,
    onDateRangeChange,
    calculateDateRange,
    initialize
  }
}
