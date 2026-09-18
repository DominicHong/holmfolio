"""Currency service for currency conversion and management."""

from datetime import date
from decimal import Decimal
from sqlmodel import select
from backend.db.models import Currency, ExchangeRate
from backend.services.base import BaseService


class CurrencyService(BaseService):
    """Service for currency conversion and management."""

    def get_primary_currency(self) -> Currency:
        """Get the primary currency."""
        primary = self.session.exec(
            select(Currency).where(Currency.is_primary == True)
        ).first()
        if not primary:
            # Create CNY as default primary currency
            primary = Currency(
                code="CNY", name="Chinese Yuan", symbol="¥", is_primary=True
            )
            self.session.add(primary)
            self.session.commit()
            self.session.refresh(primary)
        return primary

    def get_exchange_rate(self, currency_id: int, rate_date: date) -> Decimal:
        """Get exchange rate for converting currency to primary currency on a specific date."""
        primary_currency = self.get_primary_currency()
        if currency_id == primary_currency.id:
            return Decimal("1.0")

        # Get the most recent exchange rate before or on the date
        # Try direct rate: currency -> primary
        rate = self.session.exec(
            select(ExchangeRate)
            .where(ExchangeRate.from_currency_id == currency_id)
            .where(ExchangeRate.to_currency_id == primary_currency.id)
            .where(ExchangeRate.rate_date <= rate_date)
            .order_by(ExchangeRate.rate_date.desc())
        ).first()

        if rate:
            return rate.rate

        # Try inverse rate: primary -> currency, then calculate reciprocal
        inverse_rate = self.session.exec(
            select(ExchangeRate)
            .where(ExchangeRate.from_currency_id == primary_currency.id)
            .where(ExchangeRate.to_currency_id == currency_id)
            .where(ExchangeRate.rate_date <= rate_date)
            .order_by(ExchangeRate.rate_date.desc())
        ).first()

        if inverse_rate and inverse_rate.rate != 0:
            return Decimal("1.0") / inverse_rate.rate

        return Decimal("1.0")

    def get_exchange_rates(
        self,
        currency_ids: list[int],
        rate_date: date,
        raise_on_missing: bool = False,
    ) -> dict[int, Decimal]:
        """Batch fetch exchange rates for multiple currencies.

        Returns a dict mapping currency_id to rate (primary-currency terms).
        Missing rates default to 1.0, unless *raise_on_missing* is True in
        which case a ``ValueError`` is raised for the first missing currency.
        """
        primary_currency = self.get_primary_currency()
        result: dict[int, Decimal] = {}
        missing_ids: list[int] = []

        for cid in currency_ids:
            if cid == primary_currency.id:
                result[cid] = Decimal("1.0")
            else:
                missing_ids.append(cid)

        if not missing_ids:
            return result

        # Direct rates
        rates = self.session.exec(
            select(ExchangeRate)
            .where(ExchangeRate.from_currency_id.in_(missing_ids))
            .where(ExchangeRate.to_currency_id == primary_currency.id)
            .where(ExchangeRate.rate_date <= rate_date)
            .order_by(ExchangeRate.from_currency_id, ExchangeRate.rate_date.desc())
        ).all()

        found: set[int] = set()
        for rate in rates:
            if rate.from_currency_id not in found:
                result[rate.from_currency_id] = rate.rate
                found.add(rate.from_currency_id)

        # Inverse rates for missing
        still_missing = set(missing_ids) - found
        if still_missing:
            inverse_rates = self.session.exec(
                select(ExchangeRate)
                .where(ExchangeRate.from_currency_id == primary_currency.id)
                .where(ExchangeRate.to_currency_id.in_(list(still_missing)))
                .where(ExchangeRate.rate_date <= rate_date)
                .order_by(ExchangeRate.to_currency_id, ExchangeRate.rate_date.desc())
            ).all()

            for rate in inverse_rates:
                if rate.to_currency_id in still_missing and rate.rate != 0:
                    result[rate.to_currency_id] = Decimal("1.0") / rate.rate
                    still_missing.discard(rate.to_currency_id)

        for cid in still_missing:
            if raise_on_missing:
                raise ValueError(
                    f"Exchange rate not found for currency {cid} on {rate_date}"
                )
            result[cid] = Decimal("1.0")

        return result

    def convert_to_primary_currency(
        self, amount: Decimal, currency_id: int, rate_date: date
    ) -> Decimal:
        """Convert amount to primary currency."""
        rate = self.get_exchange_rate(currency_id, rate_date)
        return amount * rate
