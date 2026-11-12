# src/analysis/footprint.py
"""
Footprint / Delta 聚合。
基于 [A6] Polars 聚合框架、[A11] 竞价分析用途、[A17] bs_flag 实测修正。

bs_flag 语义（[A17] 实测确认）：
  0 = 主动买
  1 = 主动卖
  2 = 中性（仅 09:25 首条集合竞价成交）
中性量单独保留为 neutral_vol，不计入 delta。
"""

import polars as pl


def footprint_from_ticks(ticks: pl.DataFrame) -> pl.DataFrame:
    """
    按价格档位聚合 Footprint。

    输入列：time, price, vol, bs_flag
    输出列：price, buy_vol, sell_vol, neutral_vol, total_vol, delta
    """
    if ticks.height == 0:
        return pl.DataFrame()

    return (
        ticks
        .with_columns([
            pl.when(pl.col("bs_flag") == 0).then(pl.col("vol")).otherwise(0.0).alias("buy_vol"),
            pl.when(pl.col("bs_flag") == 1).then(pl.col("vol")).otherwise(0.0).alias("sell_vol"),
            pl.when(pl.col("bs_flag") == 2).then(pl.col("vol")).otherwise(0.0).alias("neutral_vol"),
        ])
        .group_by("price")
        .agg([
            pl.col("buy_vol").sum(),
            pl.col("sell_vol").sum(),
            pl.col("neutral_vol").sum(),
            pl.col("vol").sum().alias("total_vol"),
        ])
        .with_columns(
            (pl.col("buy_vol") - pl.col("sell_vol")).alias("delta")
        )
        .sort("price")
    )


def intraday_delta_series(ticks: pl.DataFrame, freq: str = "1m") -> pl.DataFrame:
    if ticks.height == 0:
        return pl.DataFrame()

    df = (
        ticks
        .with_columns(
            # trade_date 可能是 Date 或 Utf8，统一转字符串再拼 time
            (
                pl.col("trade_date").cast(pl.Utf8)
                + pl.lit(" ")
                + pl.col("time").cast(pl.Utf8)
            )
            .str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
            .alias("dt")
        )
        .with_columns([
            pl.when(pl.col("bs_flag") == 0).then(pl.col("vol")).otherwise(0.0).alias("buy_vol"),
            pl.when(pl.col("bs_flag") == 1).then(pl.col("vol")).otherwise(0.0).alias("sell_vol"),
        ])
    )

    return (
        df.group_by_dynamic("dt", every=freq)
        .agg([
            pl.col("buy_vol").sum(),
            pl.col("sell_vol").sum(),
        ])
        .with_columns(
            (pl.col("buy_vol") - pl.col("sell_vol")).alias("delta")
        )
        .with_columns(
            pl.col("delta").cum_sum().alias("cum_delta")
        )
        .sort("dt")
    )

def validate_footprint(fp: pl.DataFrame) -> pl.DataFrame:
    """
    校验：buy_vol + sell_vol + neutral_vol == total_vol。
    返回带 check 列的 DataFrame，方便人工核对。
    """
    return fp.with_columns(
        (
            (pl.col("buy_vol") + pl.col("sell_vol") + pl.col("neutral_vol"))
            - pl.col("total_vol")
        ).abs().alias("residual")
    ).with_columns(
        (pl.col("residual") < 1e-6).alias("check")
    )