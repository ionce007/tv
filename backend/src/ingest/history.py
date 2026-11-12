# src/ingest/history.py
import asyncio
import polars as pl
from pytdxdata import TdxData
from pytdxdata.models import KlinePeriod, SecurityBar

from config import KLINE_ROOT
from src.ingest.universe import load_universe


def _bar_to_dict(b: SecurityBar) -> dict:
    return {
        "symbol": b.symbol,
        "trade_date": f"{b.year:04d}-{b.month:02d}-{b.day:02d}",
        "open": b.open, "high": b.high, "low": b.low, "close": b.close,
        "vol": b.vol, "amount": b.amount,
    }


async def fetch_full_history(td, symbol):
    """一直向前翻页，直到没有数据或不足一页，获取全部历史。"""
    all_bars = []
    start = 0
    page_size = 800
    max_pages = 15  # 12页应该够上证指数，留点余量

    for _ in range(max_pages):
        bars = await td.get_bars(symbol, KlinePeriod.DAY, start=start, count=page_size)
        if not bars:
            break
        all_bars.extend(bars)
        start += page_size
        
        # 核心修改：只有当返回数量不足 800 时，说明到底了，才停止
        if len(bars) < page_size:
            break

    return all_bars


async def fill_history_for_all(batch_size: int = 50):
    universe = load_universe()
    symbols = universe["stocks"] + universe["indexes"]
    total = len(symbols)

    async with TdxData() as td:
        for i, sym in enumerate(symbols):
            f = KLINE_ROOT / "period=day" / f"symbol={sym}" / "data.parquet"
            
            try:
                # 直接拉取全历史
                bars = await fetch_full_history(td, sym)
            except Exception as e:
                print(f"[WARN] {sym} 失败: {e}")
                continue

            if not bars:
                continue

            # 重新构建 DataFrame 并覆盖写入，保证数据纯净
            combined = pl.DataFrame([_bar_to_dict(b) for b in bars]).sort("trade_date")
            
            # 去重防弹（防止接口偶尔返回重复K线）
            combined = combined.unique(subset=["trade_date"], keep="first")

            f.parent.mkdir(parents=True, exist_ok=True)
            combined.write_parquet(f)

            if (i + 1) % batch_size == 0:
                print(f"[PROGRESS] {i+1}/{total} {sym} 行数={combined.height}")

    print("[DONE] 全历史覆盖完成")