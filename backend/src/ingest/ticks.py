# src/ingest/ticks.py
"""
逐笔成交拉取 → Parquet。
基于 [A7] 并发约束、[A9] pytdxdata 选型、[A17] bs_flag 实测修正。

字段确认（[A17]）：
  market, code, time, price, vol, trade_count, bs_flag, symbol,
  fields, trade_count_available
  - price: 浮点成交价
  - vol: 成交量（手）
  - bs_flag: 0=主动买, 1=主动卖, 2=中性（仅 09:25 首条集合竞价）
  - trade_count: 成交笔数，集合竞价段可能为负，勿对全表直接求 max/mean
  - time: HH:MM:SS，协议不带日期
"""

import asyncio
from datetime import date
from pathlib import Path

import polars as pl
from pytdxdata import TdxData
from config import TICKS_ROOT as DATA_ROOT


async def fetch_one(td: TdxData, symbol: str, trade_date: date) -> pl.DataFrame:
    """拉取单标的单日逐笔，返回 Polars DataFrame。"""
    ticks = await td.get_ticks([symbol], date=int(trade_date.strftime("%Y%m%d")))
    if not ticks:
        return pl.DataFrame()

    rows = [
        {
            "symbol": t.symbol,
            "time": t.time,
            "price": t.price,
            "vol": t.vol,
            "trade_count": t.trade_count,
            "bs_flag": t.bs_flag,
        }
        for t in ticks
    ]
    df = pl.DataFrame(rows)
    df = df.with_columns(
        pl.lit(str(trade_date)).alias("trade_date")
    )
    return df


async def fetch_many(
    symbols: list[str],
    trade_date: date,
    concurrency: int = 8,
) -> pl.DataFrame:
    """
    多标的并发拉取，Semaphore 控并发（[A7] 建议 5–10）。
    连接池由 pytdxdata 内部管理，单机默认上限 4。
    """
    sem = asyncio.Semaphore(concurrency)

    async with TdxData() as td:

        async def guarded(sym: str):
            async with sem:
                try:
                    return await fetch_one(td, sym, trade_date)
                except Exception as e:
                    print(f"[WARN] {sym} {trade_date} 失败: {e}")
                    return pl.DataFrame()

        frames = await asyncio.gather(*[guarded(s) for s in symbols])
        frames = [f for f in frames if f.height > 0]
        if not frames:
            return pl.DataFrame()
        return pl.concat(frames)


def write_partitioned(df: pl.DataFrame, root: Path = DATA_ROOT) -> None:
    """
    按 trade_date / symbol 分区写入 Parquet（Hive 风格），
    供 DuckDB read_parquet('data/ticks/**/*.parquet') 直接扫描（[A12]）。
    """
    if df.height == 0:
        print("[SKIP] 空 DataFrame，不写入")
        return
    root.mkdir(parents=True, exist_ok=True)
    df.write_parquet(
        root,
        partition_by=["trade_date", "symbol"],
        mkdir=True,
    )
    print(f"[OK] 写入 {df.height} 行 → {root}")


async def main(symbols: list[str], trade_date: date) -> None:
    df = await fetch_many(symbols, trade_date)
    write_partitioned(df)


if __name__ == "__main__":
    import sys

    syms = sys.argv[1].split(",") if len(sys.argv) > 1 else ["sz000001"]
    d = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2025, 11, 3)
    asyncio.run(main(syms, d))