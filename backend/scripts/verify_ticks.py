# scripts/verify_pipeline.py
"""端到端验证：入库 → 读回 → Footprint → 校验。"""

import asyncio
from datetime import date

import polars as pl

from src.ingest.ticks import fetch_many, write_partitioned
from src.analysis.footprint import (
    footprint_from_ticks,
    intraday_delta_series,
    validate_footprint,
)
from src.storage.duck import connect, query_footprint


async def main():
    symbol = "sz300053"
    trade_date = date(2026, 11, 6)

    # 1) 拉取 + 入库
    df = await fetch_many([symbol], trade_date)
    write_partitioned(df)

    # 2) 从 DuckDB 读回，验证 Parquet 可扫描
    con = connect()
    back = query_footprint(con, symbol, str(trade_date))
    print(f"[READBACK] {back.height} 行，列: {back.columns}")

    # 3) Footprint 聚合
    fp = footprint_from_ticks(back)
    print(f"[FOOTPRINT] {fp.height} 个价位")
    print(fp.head(10))

    # 4) 校验 residual
    checked = validate_footprint(fp)
    if not checked["check"].all():
        bad = checked.filter(~pl.col("check"))
        print("[FAIL] 有价位 residual 非零：")
        print(bad)
    else:
        print("[OK] 所有价位 buy+sell+neutral == total_vol")

    # 5) 分钟 Delta 序列
    delta = intraday_delta_series(back, freq="1m")
    print(f"[DELTA] {delta.height} 分钟")
    print(delta.head(10))
    print(f"[DELTA] 全天累计 cum_delta 末值: {delta['cum_delta'][-1]}")


if __name__ == "__main__":
    asyncio.run(main())