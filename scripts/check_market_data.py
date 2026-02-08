#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from src.models.base import SessionLocal
from src.models.market_data import StockPrice, OptionsChain, OptionsMetrics
from sqlalchemy import func

db = SessionLocal()

# Count stock prices
price_count = db.query(func.count(StockPrice.id)).filter(StockPrice.ticker == 'UBER').scalar()
print(f'Stock Prices: {price_count} daily records')

# Get date range
if price_count > 0:
    min_date = db.query(func.min(StockPrice.date)).filter(StockPrice.ticker == 'UBER').scalar()
    max_date = db.query(func.max(StockPrice.date)).filter(StockPrice.ticker == 'UBER').scalar()
    print(f'  Date range: {min_date} to {max_date}')

    # Get recent prices
    recent = db.query(StockPrice).filter(StockPrice.ticker == 'UBER').order_by(StockPrice.date.desc()).limit(5).all()
    print(f'\n  Recent prices:')
    for p in recent:
        print(f'    {p.date}: Close=${p.close:.2f}, Volume={p.volume:,}')

# Count options
options_count = db.query(func.count(OptionsChain.id)).filter(OptionsChain.ticker == 'UBER').scalar()
print(f'\nOptions Contracts: {options_count} contracts')

# Get expiration breakdown
if options_count > 0:
    expirations = db.query(
        OptionsChain.expiration_date,
        func.count(OptionsChain.id).label('count')
    ).filter(
        OptionsChain.ticker == 'UBER'
    ).group_by(OptionsChain.expiration_date).order_by(OptionsChain.expiration_date).all()

    print(f'\n  Expirations:')
    for exp, count in expirations[:10]:
        print(f'    {exp}: {count} contracts')
    if len(expirations) > 10:
        print(f'    ... and {len(expirations) - 10} more expirations')

# Options metrics
metrics_count = db.query(func.count(OptionsMetrics.id)).filter(OptionsMetrics.ticker == 'UBER').scalar()
if metrics_count > 0:
    metrics = db.query(OptionsMetrics).filter(OptionsMetrics.ticker == 'UBER').order_by(OptionsMetrics.date.desc()).first()
    print(f'\nOptions Metrics (latest snapshot):')
    print(f'  Date: {metrics.date}')
    if metrics.put_call_ratio_volume:
        print(f'  P/C Ratio (Volume): {metrics.put_call_ratio_volume:.2f}')
    if metrics.put_call_ratio_oi:
        print(f'  P/C Ratio (OI): {metrics.put_call_ratio_oi:.2f}')
    if metrics.iv_30day:
        print(f'  30-day IV: {metrics.iv_30day:.1%}')
    print(f'  Total Call Volume: {metrics.total_call_volume:,}')
    print(f'  Total Put Volume: {metrics.total_put_volume:,}')

db.close()
