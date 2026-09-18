"""API models for the gold trading module."""

from datetime import date

from pydantic import BaseModel


class GoldAssetResponse(BaseModel):
    id: int
    symbol: str
    name: str
    currency_id: int


class GoldSignalResponse(BaseModel):
    signal_date: date
    action: str
    reason: str
    exec_date: date | None = None
    exec_price: float | None = None
    size: float | None = None


class GoldPendingSignalResponse(BaseModel):
    signal_date: date
    action: str
    reason: str


class GoldRoundTripResponse(BaseModel):
    entry_signal_date: date
    entry_date: date | None = None
    entry_price: float | None = None
    exit_signal_date: date
    exit_date: date
    exit_price: float | None = None
    reason: str
    gross_return: float | None = None
    net_return: float | None = None


class GoldModelStateResponse(BaseModel):
    position_size: float
    entry_date: date | None = None
    entry_price: float | None = None
    stop_price: float | None = None
    peak_close: float | None = None
    last_bar_date: date | None = None
    pending_signal: GoldPendingSignalResponse | None = None


class GoldSignalsResponse(BaseModel):
    strategy: str
    strategy_label: str
    signals: list[GoldSignalResponse]
    round_trips: list[GoldRoundTripResponse]
    model_state: GoldModelStateResponse | None = None


class GoldMetricsResponse(BaseModel):
    total_return: float
    annualized_return: float | None = None
    max_drawdown: float
    volatility: float
    sharpe: float
    trades: int
    win_rate: float | None = None
    realized_pnl: float | None = None


class GoldPerformanceResponse(BaseModel):
    dates: list[date]
    user_nav: list[float]
    model_nav: list[float]
    benchmark_nav: list[float | None]
    benchmark_symbol: str
    initial_capital: float
    risk_free_rate: float = 0.0
    metrics: dict[str, GoldMetricsResponse | None] | None = None


class GoldUserPositionResponse(BaseModel):
    quantity: float
    average_cost: float
    latest_price: float | None = None
    market_value: float | None = None
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    sells: int
    win_rate: float | None = None
    transactions: int


class GoldOverviewResponse(BaseModel):
    asset: GoldAssetResponse
    strategy: str
    strategy_label: str
    signals: list[GoldSignalResponse]
    round_trips: list[GoldRoundTripResponse]
    model_state: GoldModelStateResponse | None = None
    series_dates: list[date] = []
    series: dict[str, list[float | None]] = {}
    performance: GoldPerformanceResponse
    user_position: GoldUserPositionResponse
    initial_capital: float


class UpdateGoldPricesResponse(BaseModel):
    added: int
    errors: list[str]
