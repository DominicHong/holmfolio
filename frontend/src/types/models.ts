export interface Portfolio {
  id: number
  name: string
  description?: string
  base_currency_id?: number
  created_at?: string
  updated_at?: string
}

export interface Position {
  id: number
  portfolio_id: number
  asset_id: number
  symbol: string
  name?: string
  quantity?: number
  average_cost?: number
  current_price?: number
  market_value: number
  market_value_primary?: number
  total_pnl: number
  total_pnl_primary?: number
  position_date?: string
  currency_code?: string
  currency?: Currency
  dividends?: number | null
  dividends_primary?: number | null
  is_history?: boolean
}

export type AssetType = 'stock' | 'bond' | 'fund' | 'etf' | 'cash' | 'gold'

export interface Asset {
  id: number
  symbol: string
  name: string
  type: AssetType
  isin?: string
  currency_id: number
  currency?: Currency
  created_at?: string
  updated_at?: string
}

export type TransactionAction =
  | 'buy'
  | 'sell'
  | 'cash_in'
  | 'cash_out'
  | 'tax'
  | 'dividends'
  | 'split'
  | 'interest'

export interface Transaction {
  id: number
  portfolio_id: number
  asset_id: number
  action: TransactionAction
  trade_date: string
  quantity?: number
  price?: number
  amount: number
  fees?: number
  currency_id: number
  currency?: Currency
  notes?: string
  created_at?: string
  updated_at?: string
}

export interface Currency {
  id: number
  code: string
  symbol: string
  name: string
  is_primary: boolean
}

export interface MissingDividendItem {
  asset_id: number
  symbol: string
  name: string
  record_date: string
  received_date: string
  report_date?: string | null
  per_share: number
  quantity: number
  amount: number
  currency_id: number
  currency: string
  holding_start: string
  holding_end: string
  scheme?: string | null
  notes?: string | null
}

export interface CheckDividendsResponse {
  assets_checked: number
  dividend_events_found: number
  missing: MissingDividendItem[]
}

export interface AddDividendsResponse {
  added: number
  positions_recalculated: boolean
}

export interface ExchangeRate {
  id: number
  from_currency_id: number
  to_currency_id: number
  rate: number
  rate_date?: string
  source?: string
  // UI-derived fields added when rendering tables
  currency_code?: string
  target_currency_code?: string
}

export interface Tag {
  id: number
  name: string
  category_id?: number
  description?: string
  color?: string
  created_at?: string
  updated_at?: string
}

export interface TagCategory {
  id: number
  name: string
  description?: string
  display_order?: number
  created_at?: string
  updated_at?: string
}

export interface AssetTag {
  id: number
  asset_id: number
  tag_id: number
  weight?: number
  notes?: string
  tag?: Tag
  asset?: Asset
  created_at?: string
  updated_at?: string
}

export interface BenchmarkComponent {
  component_benchmark_id: number
  weight: number
}

export interface Benchmark {
  id: number
  name: string
  symbol?: string
  description?: string
  is_composite?: boolean
  components?: BenchmarkComponent[]
  created_at?: string
  updated_at?: string
}

export interface Setting {
  key: string
  value: string
  description?: string | null
  created_at?: string
  updated_at?: string
}

// ---------------------------------------------------------------------------
// Gold trading module
// ---------------------------------------------------------------------------

export type GoldSignalAction = 'buy' | 'sell'

export interface GoldSignal {
  signal_date: string
  action: GoldSignalAction
  reason: string
  exec_date?: string | null
  exec_price?: number | null
  size?: number | null
}

export interface GoldPendingSignal {
  signal_date: string
  action: GoldSignalAction
  reason: string
}

export interface GoldRoundTrip {
  entry_signal_date: string
  entry_date?: string | null
  entry_price?: number | null
  exit_signal_date: string
  exit_date: string
  exit_price?: number | null
  reason: string
  gross_return?: number | null
  net_return?: number | null
}

export interface GoldModelState {
  position_size: number
  entry_date?: string | null
  entry_price?: number | null
  stop_price?: number | null
  peak_close?: number | null
  last_bar_date?: string | null
  pending_signal?: GoldPendingSignal | null
}

export interface GoldMetrics {
  total_return: number
  annualized_return?: number | null
  max_drawdown: number
  volatility: number
  sharpe: number
  trades: number
  win_rate?: number | null
  realized_pnl?: number | null
}

export interface GoldPerformance {
  dates: string[]
  user_nav: number[]
  model_nav: number[]
  benchmark_nav: (number | null)[]
  benchmark_symbol: string
  initial_capital: number
  risk_free_rate: number
  metrics?: Record<string, GoldMetrics | null> | null
}

export interface GoldUserPosition {
  quantity: number
  average_cost: number
  latest_price?: number | null
  market_value?: number | null
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
  sells: number
  win_rate?: number | null
  transactions: number
}

export interface GoldOverview {
  asset: Asset
  strategy: string
  strategy_label: string
  signals: GoldSignal[]
  round_trips: GoldRoundTrip[]
  model_state?: GoldModelState | null
  series_dates: string[]
  series: Record<string, (number | null)[]>
  performance: GoldPerformance
  user_position: GoldUserPosition
  initial_capital: number
}
