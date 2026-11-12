import polars as pl

# data/ticks/ 下的逐笔数据（含 bs_flag：0=主动买，1=主动卖，2=中性，[A16]）。
# Delta 的计算逻辑就是主动买量减去主动卖量，然后按时间周期聚合、累加得到 CVD。
# 关键提醒：bs_flag=2（09:25 集合竞价首条）不计入买/卖，vol 不参与 delta 计算，但保留在原始数据中。
# CVD 与价格的背离是订单流的核心信号——价格新高而 CVD 未新高，说明买压不足。但你的逐笔是 3 秒聚合
# 切片（[A17]），CVD 曲线平滑度不如原生 tick，信号衰减较快，适合盘后复盘而非盘中实时。
def add_delta_cvd(ticks: pl.DataFrame, freq: str = "1m") -> pl.DataFrame:
    """
    ticks 需含: trade_date, time, price, vol, bs_flag
    返回按 freq 聚合的 delta 和 cum_delta。
    """
    df = ticks.with_columns(
        (pl.col("trade_date") + " " + pl.col("time"))
        .str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
        .alias("dt")
    ).with_columns([
        pl.when(pl.col("bs_flag") == 0).then(pl.col("vol")).otherwise(0).alias("buy_vol"),
        pl.when(pl.col("bs_flag") == 1).then(pl.col("vol")).otherwise(0).alias("sell_vol"),
    ])

    out = (
        df.group_by_dynamic("dt", every=freq)
        .agg([
            pl.col("buy_vol").sum(),
            pl.col("sell_vol").sum(),
            pl.col("price").last().alias("close"),
        ])
        .with_columns(
            (pl.col("buy_vol") - pl.col("sell_vol")).alias("delta")
        )
        .with_columns(
            pl.col("delta").cum_sum().alias("cum_delta")
        )
        .sort("dt")
    )
    return out