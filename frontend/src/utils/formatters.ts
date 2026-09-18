import dayjs from 'dayjs'

/**
 * Format a number with fixed decimal places
 * @param value - The number to format
 * @param decimalPlaces - Number of decimal places (default: 2)
 * @returns Formatted number string
 */
export const formatNumber = (value: number | string | null | undefined, decimalPlaces = 2): string => {
  if (value == null) return '0.00'
  return Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces
  })
}

interface CurrencyLike {
  symbol?: string
}

/**
 * Format a value as currency with symbol
 * @param value - The currency amount
 * @param currency - Currency object with symbol property
 * @param decimalPlaces - Number of decimal places (default: 2)
 * @returns Formatted currency string
 */
export const formatCurrency = (value: number | string | null | undefined, currency: CurrencyLike | null = null, decimalPlaces = 2): string => {
  const symbol = currency?.symbol || '¥'
  if (value == null) return symbol + formatNumber(0, decimalPlaces)
  return symbol + formatNumber(value, decimalPlaces)
}

/**
 * Format a date as YYYY-MM-DD
 * @param date - The date to format
 * @returns Formatted date string
 */
export const formatDate = (date: string | Date | null | undefined): string => {
  if (!date) return ''
  return dayjs(date).format('YYYY-MM-DD')
}

/**
 * Format a value as percentage
 * @param value - The percentage value (e.g., 0.15 for 15%)
 * @param decimalPlaces - Number of decimal places (default: 2)
 * @returns Formatted percentage string
 */
export const formatPercentage = (value: number | string | null | undefined, decimalPlaces = 2): string => {
  if (value == null) return '0.00%'
  return (100 * Number(value)).toFixed(decimalPlaces) + '%'
}

/**
 * Format quantity with 0 decimal places (rounded to integer)
 * @param value - The quantity to format
 * @returns Formatted quantity string
 */
export const formatQuantity = (value: number | string | null | undefined): string => {
  if (value == null) return '0'
  return formatNumber(value, 0)
}
