"""
全市场 K 线下载：全量 + 增量。
get_kline_batch 已废弃，统一走 get_bars（序列 + concurrency）。
SecurityBar 字段：market, code, open, high, low, close, vol, amount,
                  year, month, day, hour, minute, symbol, settle
"""
import asyncio
import json
from datetime import datetime

import polars as pl
from pytdxdata import TdxData
from pytdxdata.models import KlinePeriod

from config import KLINE_ROOT, PROGRESS_FILE
from src.ingest.universe import load_universe


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {}


def _save_progress(p: dict):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(p, ensure_ascii=False))


def _last_date(symbol: str, period_name: str) -> str | None:
    f = KLINE_ROOT / f"period={period_name}" / f"symbol={symbol}" / "data.parquet"
    if not f.exists():
        return None
    d = pl.read_parquet(f, columns=["trade_date"])
    return str(d["trade_date"].max()) if d.height > 0 else None


def _bars_to_df(bars: list) -> pl.DataFrame:
    if not bars:
        return pl.DataFrame()
    rows = [{
        "symbol": b.symbol,
        "trade_date": f"{b.year:04d}-{b.month:02d}-{b.day:02d}",
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
        "vol": b.vol,
        "amount": b.amount,
    } for b in bars]
    return pl.DataFrame(rows)


def _write_incremental(d: pl.DataFrame, period_name: str, mode: str):
    if d.height == 0:
        return
    for sym, g in d.group_by("symbol"):
        sym = sym[0] if isinstance(sym, tuple) else sym
        out = KLINE_ROOT / f"period={period_name}" / f"symbol={sym}"
        out.mkdir(parents=True, exist_ok=True)
        f = out / "data.parquet"
        if mode == "incremental" and f.exists():
            old = pl.read_parquet(f)
            g = pl.concat([old, g]).unique(subset=["trade_date"], keep="last")
        g.sort("trade_date").write_parquet(f)


async def download_bars(
    td: TdxData,
    symbols: list[str],
    period: KlinePeriod,
    period_name: str,
    mode: str = "incremental",
    count: int = 800,
    batch_size: int = 200,
):
    progress = _load_progress()
    total = len(symbols)

    for i in range(0, total, batch_size):
        batch = symbols[i:i + batch_size]
        try:
            bars = await td.get_bars(batch, period, count=count, concurrency=6)
        except Exception as e:
            print(f"[WARN] batch {i}-{i+len(batch)} 失败: {e}")
            continue

        if not bars:
            continue

        d = _bars_to_df(bars)
        if d.height == 0:
            continue

        if mode == "incremental":
            filtered = []
            for sym, g in d.group_by("symbol"):
                sym = sym[0] if isinstance(sym, tuple) else sym
                last = _last_date(sym, period_name)
                if last:
                    g = g.filter(pl.col("trade_date") > last)
                if g.height > 0:
                    filtered.append(g)
            d = pl.concat(filtered) if filtered else pl.DataFrame()

        _write_incremental(d, period_name, mode)

        for sym in batch:
            progress[f"{period_name}:{sym}"] = {
                "last_run": datetime.now().isoformat(),
                "mode": mode,
            }
        _save_progress(progress)
        print(f"[PROGRESS] {min(i + batch_size, total)}/{total}")


async def main(mode: str = "full", period: str = "day"):
    universe = load_universe()
    period_map = {"day": KlinePeriod.DAY, "week": KlinePeriod.WEEK, "month": KlinePeriod.MONTH}
    kp = period_map[period]
    count = 800 if mode == "incremental" else 2400

    async with TdxData() as td:
        await download_bars(td, universe["stocks"], kp, period, mode=mode, count=count)
        await download_bars(td, universe["indexes"], kp, period, mode=mode, count=count)