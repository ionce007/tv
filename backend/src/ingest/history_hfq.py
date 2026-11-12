# src/ingest/history_hfq.py
import asyncio
import polars as pl
from pytdxdata import TdxData
from pytdxdata.models import KlinePeriod, SecurityBar, Adjust

from config import KLINE_ROOT
from src.ingest.universe import load_universe

def _bar_to_dict(b: SecurityBar) -> dict:
    return {
        "symbol": b.symbol,
        "trade_date": f"{b.year:04d}-{b.month:02d}-{b.day:02d}",
        "open": b.open, "high": b.high, "low": b.low, "close": b.close,
        "vol": b.vol, "amount": b.amount,
    }

async def fetch_full_hfq(td, symbol):
    """拉取全部历史，指定 adjust=Adjust.HFQ"""
    all_bars = []
    start = 0
    page_size = 800
    max_pages = 15

    for _ in range(max_pages):
        # 这里增加了 adjust=Adjust.HFQ
        bars = await td.get_bars(
            symbol, KlinePeriod.DAY, start=start, count=page_size, adjust=Adjust.HFQ
        )
        if not bars:
            break
        all_bars.extend(bars)
        start += page_size
        if len(bars) < page_size:
            break
    return all_bars

async def download_hfq_for_all(batch_size: int = 50):
    universe = load_universe()
    symbols = universe["stocks"] + universe["indexes"]
    total = len(symbols)

    async with TdxData() as td:
        for i, sym in enumerate(symbols):
            # 目标文件改为 data_hfq.parquet
            f = KLINE_ROOT / "period=day" / f"symbol={sym}" / "data_hfq.parquet"
            
            try:
                bars = await fetch_full_hfq(td, sym)
            except Exception as e:
                print(f"[WARN] {sym} 失败: {e}")
                continue

            if not bars:
                continue

            combined = pl.DataFrame([_bar_to_dict(b) for b in bars]).sort("trade_date")
            # 去重
            combined = combined.unique(subset=["trade_date"], keep="first")

            f.parent.mkdir(parents=True, exist_ok=True)
            combined.write_parquet(f)

            if (i + 1) % batch_size == 0:
                print(f"[PROGRESS] {i+1}/{total} {sym} 行数={combined.height}")

    print("[DONE] 后复权全历史下载完成")