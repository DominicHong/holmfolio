"""API models (Pydantic) for request/response schemas."""

from backend.api.models.currency import CurrencyResponse
from backend.api.models.transaction import (
    TransactionResponse,
    CheckDividendsRequest,
    MissingDividendItem,
    CheckDividendsResponse,
    AddDividendsRequest,
    AddDividendsResponse,
)
from backend.api.models.position import PositionResponse, DividendPositionResponse, FinancialPositionResponse
from backend.api.models.settings import SettingsResponse
from backend.api.models.benchmark import BenchmarkResponse, BenchmarkPriceResponse, BenchmarkComponentResponse
from backend.api.models.tag import AssetTagCreate, AssetTagResponse
from backend.api.models.price import UpdatePricesRequest, UpdatePricesResponse
from backend.api.models.gold import (
    GoldAssetResponse,
    GoldSignalResponse,
    GoldPendingSignalResponse,
    GoldRoundTripResponse,
    GoldModelStateResponse,
    GoldSignalsResponse,
    GoldMetricsResponse,
    GoldPerformanceResponse,
    GoldUserPositionResponse,
    GoldOverviewResponse,
    UpdateGoldPricesResponse,
)

__all__ = [
    "CurrencyResponse",
    "TransactionResponse",
    "CheckDividendsRequest",
    "MissingDividendItem",
    "CheckDividendsResponse",
    "AddDividendsRequest",
    "AddDividendsResponse",
    "PositionResponse",
    "DividendPositionResponse",
    "FinancialPositionResponse",
    "SettingsResponse",
    "BenchmarkResponse",
    "BenchmarkPriceResponse",
    "BenchmarkComponentResponse",
    "AssetTagCreate",
    "AssetTagResponse",
    "UpdatePricesRequest",
    "UpdatePricesResponse",
    "GoldAssetResponse",
    "GoldSignalResponse",
    "GoldPendingSignalResponse",
    "GoldRoundTripResponse",
    "GoldModelStateResponse",
    "GoldSignalsResponse",
    "GoldMetricsResponse",
    "GoldPerformanceResponse",
    "GoldUserPositionResponse",
    "GoldOverviewResponse",
    "UpdateGoldPricesResponse",
]
