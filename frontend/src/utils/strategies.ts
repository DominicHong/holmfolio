/**
 * Gold strategy options shared by the Gold and Transactions pages.
 *
 * Keys must stay in sync with backend/strat/gold/__init__.py (STRATEGIES /
 * STRATEGY_LABELS); the `strategy` field on a transaction stores the key.
 */

export interface StrategyOption {
  /** Strategy key stored on the transaction `strategy` field. */
  value: string
  /** Full label shown in selects. */
  label: string
  /** Short label shown in tables. */
  shortLabel: string
  /** True for the backend default strategy. */
  isDefault?: boolean
}

export const STRATEGY_OPTIONS: StrategyOption[] = [
  {
    value: 's1a_ma_cross_trailing',
    label: 's1a Dual-MA trend + ATR trailing stop (default)',
    shortLabel: 's1a',
    isDefault: true
  },
  {
    value: 's1b_vol_target_ma_cross',
    label: 's1b Dual-MA trend + vol-target position sizing',
    shortLabel: 's1b'
  }
]

export const DEFAULT_STRATEGY =
  STRATEGY_OPTIONS.find((option) => option.isDefault)?.value ?? ''

/** Short label for a strategy key; unknown keys are returned as-is. */
export function strategyShortLabel(value: string | null | undefined): string {
  if (!value) return ''
  const option = STRATEGY_OPTIONS.find((item) => item.value === value)
  return option ? option.shortLabel : value
}
