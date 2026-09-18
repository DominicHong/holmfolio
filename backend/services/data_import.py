"""Data import service for CSV and other data imports."""

import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlmodel import select
from backend.db.models import Asset, Currency, Transaction, Portfolio
from backend.services.base import BaseService
from backend.services.price_rate import PriceRateService
from backend import logger

# Import PositionService at the end to avoid circular imports
from backend.services.position import PositionService


class DataImportService(BaseService):
    """Service for importing data from various sources."""

    @staticmethod
    def detect_encoding(file_bytes: bytes) -> str:
        """Detect file encoding by trying common Chinese encodings."""
        encodings = ['gbk', 'gb2312', 'utf-8', 'utf-8-sig', 'gb18030']
        for encoding in encodings:
            try:
                file_bytes.decode(encoding)
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError("Cannot detect file encoding")

    @staticmethod
    def map_xueqiu_action_type(chinese_type: str) -> str:
        """Map Chinese action types to English."""
        action_map = {
            '买入': 'buy',
            '卖出': 'sell',
            '除权除息': 'dividends',
            '拆股': 'split',
            '现金转入': 'cash_in',
            '现金转出': 'cash_out',
            '利息': 'interest',
            '税': 'tax'
        }
        return action_map.get(chinese_type, chinese_type.lower())

    @staticmethod
    def parse_xueqiu_split_description(description: str) -> str | None:
        """Parse split/bonus descriptions from Chinese text."""
        if pd.isna(description) or description == '':
            return None

        # Pattern: 每X股拆股Y股
        pattern = r'每(\d+)股.*?拆股.*?(\d+)股'
        match = re.search(pattern, description)
        if match:
            from_shares = int(match.group(1))
            to_shares = int(match.group(2))
            return f"split {from_shares} to {to_shares}"

        # Pattern: 每X股送Y股
        pattern2 = r'每(\d+)股.*?送.*?(\d+)股'
        match2 = re.search(pattern2, description)
        if match2:
            from_shares = int(match2.group(1))
            to_shares = int(match2.group(2))
            return f"bonus {from_shares} to {to_shares}"

        # Pattern: X拆Y
        pattern3 = r'(\d+)拆([\d.]+)'
        match3 = re.search(pattern3, description)
        if match3:
            from_shares = int(match3.group(1))
            to_shares = float(match3.group(2))
            return f"split {from_shares} to {to_shares}"

        return description

    @staticmethod
    def clean_xueqiu_symbol(symbol: str) -> str:
        """Clean and normalize symbol from Xueqiu format."""
        if pd.isna(symbol):
            return ''
        symbol = str(symbol).strip()
        symbol = symbol.strip('\t')
        if symbol.startswith('"') and symbol.endswith('"'):
            symbol = symbol[1:-1]
        symbol = symbol.strip()

        if symbol.startswith('SZ'):
            return symbol[2:] + '.SZ'
        elif symbol.startswith('SH'):
            return symbol[2:] + '.SH'
        elif re.match(r'^\d{5}$', symbol):
            return symbol + '.HK'

        return symbol

    @staticmethod
    def get_currency_code_from_symbol(symbol: str) -> str:
        """Determine currency code from symbol suffix."""
        if symbol.endswith('.SZ') or symbol.endswith('.SH'):
            return 'CNY'
        elif symbol.endswith('.HK'):
            return 'HKD'
        return 'CNY'

    def import_xueqiu_transactions_from_dataframe(
        self, df: pd.DataFrame, portfolio_id: int
    ) -> list[Transaction]:
        """Import transactions from Xueqiu CSV format."""
        # Map Chinese column names to English
        column_mapping = {}
        for col in df.columns:
            col_stripped = col.strip()
            if '日期' in col_stripped:
                column_mapping[col] = 'trade_date'
            elif col_stripped == '类型':
                column_mapping[col] = 'action'
            elif '代码' in col_stripped:
                column_mapping[col] = 'symbol'
            elif '名称' in col_stripped:
                column_mapping[col] = 'name'
            elif '成交价' in col_stripped:
                column_mapping[col] = 'price'
            elif '数量' in col_stripped:
                column_mapping[col] = 'quantity'
            elif '金额' in col_stripped:
                column_mapping[col] = 'amount'
            elif col_stripped == '说明':
                column_mapping[col] = 'notes'
            elif col_stripped == '备注':
                column_mapping[col] = 'drop'

        df = df.rename(columns=column_mapping)

        if 'drop' in df.columns:
            df = df.drop(columns=['drop'])

        currencies = self.session.exec(select(Currency)).all()
        currency_map = {curr.code: curr.id for curr in currencies}

        portfolio = self.session.get(Portfolio, portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio with id {portfolio_id} not found")

        transactions = []

        for _, row in df.iterrows():
            if pd.isna(row.get('action')):
                continue

            action = self.map_xueqiu_action_type(str(row['action']).strip())

            asset = None
            currency_id = currency_map.get('CNY', 1)

            if 'symbol' in row and pd.notna(row['symbol']):
                symbol = self.clean_xueqiu_symbol(row['symbol'])

                if symbol:
                    asset = self.session.exec(
                        select(Asset).where(Asset.symbol == symbol)
                    ).first()

                    if not asset:
                        curr_code = self.get_currency_code_from_symbol(symbol)
                        currency_id = currency_map.get(curr_code, 1)

                        asset_name = row.get('name', symbol)
                        if pd.isna(asset_name):
                            asset_name = symbol

                        asset = Asset(
                            symbol=symbol,
                            name=str(asset_name).strip(),
                            type='stock',
                            isin=None,
                            currency_id=currency_id
                        )
                        self.session.add(asset)
                        self.session.commit()
                        self.session.refresh(asset)
                    else:
                        currency_id = asset.currency_id

            notes = None
            if 'notes' in row and pd.notna(row['notes']):
                notes = str(row['notes'])
                if action == 'split':
                    notes = self.parse_xueqiu_split_description(notes)

            quantity = None
            if 'quantity' in row and pd.notna(row['quantity']):
                quantity = Decimal(str(row['quantity']))

            price = None
            if 'price' in row and pd.notna(row['price']):
                price = Decimal(str(row['price']))

            amount = Decimal('0')
            if 'amount' in row and pd.notna(row['amount']):
                amount = Decimal(str(row['amount']))

            trade_date = None
            if 'trade_date' in row and pd.notna(row['trade_date']):
                trade_date = pd.to_datetime(row['trade_date']).date()
            else:
                trade_date = datetime.now().date()

            transaction = Transaction(
                portfolio_id=portfolio.id,
                trade_date=trade_date,
                action=action,
                asset_id=asset.id if asset else None,
                quantity=quantity,
                price=price,
                amount=amount,
                fees=Decimal('0'),
                currency_id=currency_id,
                notes=notes
            )
            transactions.append(transaction)

        return transactions

    @staticmethod
    def _parse_xueqiu_csv_sections(csv_text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Parse a Xueqiu CSV into trade records and transfer records DataFrames."""
        lines = csv_text.split('\n')
        trade_lines = []
        transfer_lines = []

        i = 0
        while i < len(lines):
            stripped = lines[i].strip().replace('\r', '')
            if stripped == '交易记录':
                i += 1
                if i < len(lines):
                    trade_lines.append(lines[i].strip().replace('\r', ''))
                    i += 1
                while i < len(lines):
                    line = lines[i].strip().replace('\r', '')
                    if line == '' or line == '转账记录':
                        break
                    trade_lines.append(line)
                    i += 1
                continue
            elif stripped == '转账记录':
                i += 1
                if i < len(lines):
                    transfer_lines.append(lines[i].strip().replace('\r', ''))
                    i += 1
                while i < len(lines):
                    line = lines[i].strip().replace('\r', '')
                    if line == '':
                        break
                    transfer_lines.append(line)
                    i += 1
                continue
            i += 1

        trade_df = pd.read_csv(io.StringIO('\n'.join(trade_lines))) if len(trade_lines) > 1 else pd.DataFrame()
        transfer_df = pd.read_csv(io.StringIO('\n'.join(transfer_lines))) if len(transfer_lines) > 1 else pd.DataFrame()

        return trade_df, transfer_df

    def _import_transfer_records(self, transfer_df: pd.DataFrame, portfolio_id: int) -> list[Transaction]:
        """Import transfer records as cash_in / cash_out transactions."""
        if transfer_df.empty:
            logger.info("Transfer DataFrame is empty, no transfer records to import")
            return []

        market_currency_map = {
            'A股(人民币)': 'CNY',
            'A股(￥)': 'CNY',
            '港股(HK$)': 'HKD',
            '港股(HKD)': 'HKD',
        }

        currencies = self.session.exec(select(Currency)).all()
        currency_map = {curr.code: curr for curr in currencies}

        cash_assets = self.session.exec(
            select(Asset).where(Asset.type == 'cash')
        ).all()
        cash_asset_map = {asset.symbol: asset for asset in cash_assets}

        transactions = []

        def _get_col(row, *names):
            for name in names:
                if name in row and pd.notna(row.get(name)):
                    return row.get(name)
            return None

        for _, row in transfer_df.iterrows():
            txn_type = str(_get_col(row, '类型', '操作') or '').strip()
            market = str(_get_col(row, '市场') or '').strip()
            amount_val = _get_col(row, '金额')
            date_val = _get_col(row, '日期')

            logger.debug(f"Processing transfer record: type={txn_type}, market={market}, amount={amount_val}, date={date_val}")

            if txn_type not in ('转入', '转出'):
                logger.warning(f"Unknown transfer type '{txn_type}', skipping")
                continue

            currency_code = market_currency_map.get(market)
            if not currency_code:
                logger.warning(f"Unknown market '{market}' in transfer record, skipping")
                continue

            currency = currency_map.get(currency_code)
            if not currency:
                logger.warning(f"Currency {currency_code} not found, skipping transfer")
                continue

            cash_symbol = f"{currency_code}_CASH"
            cash_asset = cash_asset_map.get(cash_symbol)
            if not cash_asset:
                logger.info(f"Cash asset {cash_symbol} not found, creating it automatically")
                cash_asset = Asset(
                    symbol=cash_symbol,
                    name=f"{currency_code} CASH",
                    type='cash',
                    currency_id=currency.id,
                    isin=f"CASH_{currency_code}",
                )
                self.session.add(cash_asset)
                self.session.commit()
                self.session.refresh(cash_asset)
                cash_asset_map[cash_symbol] = cash_asset
                logger.info(f"Created cash asset {cash_symbol} with id {cash_asset.id}")

            action = 'cash_in' if txn_type == '转入' else 'cash_out'
            trade_date = pd.to_datetime(date_val).date() if pd.notna(date_val) else date.today()
            amount = Decimal(str(amount_val)) if pd.notna(amount_val) else Decimal('0')

            transaction = Transaction(
                portfolio_id=portfolio_id,
                trade_date=trade_date,
                action=action,
                asset_id=cash_asset.id,
                quantity=amount,
                price=Decimal('1'),
                amount=amount,
                fees=Decimal('0'),
                currency_id=currency.id,
                notes=f"Transfer: {market}"
            )
            transactions.append(transaction)

        return transactions

    def align_portfolio_from_xueqiu(self, zip_bytes: bytes, portfolio_id: int) -> dict:
        """Align portfolio to Xueqiu data: clear transactions, import from zip, recalculate positions.

        Args:
            zip_bytes: The uploaded zip file contents.
            portfolio_id: The portfolio to align.

        Returns:
            Dict with counts and recalculation result.
        """
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            csv_files = [f for f in zf.namelist() if f.lower().endswith('.csv')]
            if not csv_files:
                raise ValueError("No CSV file found in the zip archive")
            csv_bytes = zf.read(csv_files[0])

        # Save the extracted CSV to tests directory as xueqiu_portfolio.csv
        tests_dir = Path(__file__).resolve().parents[2] / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        reference_csv_path = tests_dir / "xueqiu_portfolio.csv"
        reference_csv_path.write_bytes(csv_bytes)
        logger.info(f"Saved reference CSV to {reference_csv_path}")

        encoding = self.detect_encoding(csv_bytes)
        csv_text = csv_bytes.decode(encoding)
        trade_df, transfer_df = self._parse_xueqiu_csv_sections(csv_text)

        portfolio = self.session.get(Portfolio, portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio with id {portfolio_id} not found")

        existing_txns = self.session.exec(
            select(Transaction).where(Transaction.portfolio_id == portfolio_id)
        ).all()
        for txn in existing_txns:
            self.session.delete(txn)
        self.session.commit()
        deleted_count = len(existing_txns)

        trade_transactions = []
        if not trade_df.empty:
            trade_transactions = self.import_xueqiu_transactions_from_dataframe(trade_df, portfolio_id)
            self.session.add_all(trade_transactions)

        transfer_transactions = []
        if not transfer_df.empty:
            transfer_transactions = self._import_transfer_records(transfer_df, portfolio_id)
            self.session.add_all(transfer_transactions)

        self.session.commit()

        total_imported = len(trade_transactions) + len(transfer_transactions)

        # Update asset prices and exchange rates before recalculating positions
        primary_currency = self.session.exec(
            select(Currency).where(Currency.is_primary == True)
        ).first()
        if not primary_currency or primary_currency.code != "CNY":
            raise ValueError("Primary currency must be CNY")

        end_date = date.today()
        position_service = PositionService(self.session)
        first_txn_date = position_service.get_first_transaction_date(portfolio_id)

        price_update_errors = []
        if first_txn_date:
            price_rate_service = PriceRateService(self.session)
            update_result = price_rate_service.update_all(
                start_date=first_txn_date,
                end_date=end_date,
            )
            price_update_errors = update_result["errors"]
            if price_update_errors:
                logger.warning(f"Price/rate update errors during align: {price_update_errors}")

        recalc_result = position_service.recalculate_positions_daily(
            portfolio_id=portfolio_id,
            end_date=end_date,
        )

        return {
            "deleted_count": deleted_count,
            "trade_count": len(trade_transactions),
            "transfer_count": len(transfer_transactions),
            "total_imported": total_imported,
            "days_processed": recalc_result.get("days_processed", 0),
            "start_date": recalc_result.get("start_date"),
            "end_date": recalc_result.get("end_date"),
            "price_update_errors": price_update_errors,
        }
