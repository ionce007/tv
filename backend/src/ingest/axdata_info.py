# backend/src/ingest/axdata_info.py
import axdata as ax
import polars as pl
from config import DATA_ROOT

BASIC_INFO_FILE = DATA_ROOT / "basic_info.parquet"
CAPITAL_CHANGES_FILE = DATA_ROOT / "capital_changes.parquet"


def sync_axdata():
    client = ax.AxDataClient()

    print("1. 拉取交易所基础信息...")
    # 不传 code 默认拉取全部
    exchange_data = client.call("stock_basic_info_exchange")
    df_ex = pl.DataFrame(exchange_data)

    # 清洗交易所数据，转换为规范格式
    df_basic = df_ex.select([
        pl.col("symbol"),
        (pl.when(pl.col("exchange") == "SSE").then(pl.lit("sh"))
         .when(pl.col("exchange") == "SZSE").then(pl.lit("sz"))
         .when(pl.col("exchange") == "BSE").then(pl.lit("bj"))
         .otherwise(pl.lit("")) + pl.col("symbol")).alias("tdx_symbol"),
        pl.col("name"),
        pl.col("industry"),
        pl.col("list_date"),
        # 交易所的股本单位是亿股，统一转为股 (乘 1e8)
        (pl.col("total_share").cast(pl.Float64) * 1e8).alias("total_shares"),
        (pl.col("float_share").cast(pl.Float64) * 1e8).alias("float_shares"),
    ]).filter(pl.col("tdx_symbol") != "")

    print("2. 拉取每日股本(盘前)修正最新总股本和流通股...")
    daily_data = client.call("stock_daily_share_tdx")
    df_daily = pl.DataFrame(daily_data)

    # 用每日股本的最新数据去覆盖基础信息中的股本数据
    if not df_daily.is_empty():
        # 每日股本接口的 total_share 和 float_share 单位已经是股了，不用乘
        latest_daily = df_daily.sort("trade_date").group_by("tdx_code").last()

        # 剥离 tdx_code 的前缀得到纯 symbol 进行 join (例如 sh600000 -> 600000)
        latest_daily = latest_daily.with_columns(
            pl.col("tdx_code").str.slice(2).alias("symbol")
        )

        df_basic = df_basic.join(
            latest_daily.select(["symbol", "total_share", "float_share"]),
            on="symbol",
            how="left"
        ).with_columns([
            # 如果每日股本有数据，就用每日股本，否则用交易所的；总股本和流通股都要修正
            pl.coalesce([pl.col("total_share"), pl.col("total_shares")]).alias("total_shares"),
            pl.coalesce([pl.col("float_share"), pl.col("float_shares")]).alias("float_shares")
        ]).drop(["total_share", "float_share"])

    print("3. 拉取股本变迁数据（用于计算历史换手率）...")
    changes_data = client.call("stock_capital_changes_tdx", category="1")  # 只看除权除息类别
    df_changes = pl.DataFrame(changes_data)

    # 提取前流通股本(c3)和后流通股本(c4)
    # 【核心修复】：AxData 变迁接口 c3/c4 的单位是“亿股”，需转换为“股”
    df_changes_clean = df_changes.select([
        pl.col("tdx_code").alias("tdx_symbol"),
        pl.col("event_date").alias("change_date"),
        pl.col("category_name"),
        (pl.col("c3").cast(pl.Float64) * 1e8).alias("prev_float_shares"),
        (pl.col("c4").cast(pl.Float64) * 1e8).alias("new_float_shares"),
    ]).filter(
        pl.col("new_float_shares").is_not_null() & (pl.col("new_float_shares") > 0)
    ).sort("tdx_symbol", "change_date")

    # 保存数据
    df_basic.write_parquet(BASIC_INFO_FILE)
    df_changes_clean.write_parquet(CAPITAL_CHANGES_FILE)

    print(f"[OK] 基础信息已更新 {df_basic.height} 条。")
    print(f"[OK] 股本变迁已更新 {df_changes_clean.height} 条。")
    print("\n--- 基础信息样例 ---")
    print(df_basic.head(3))
    print("\n--- 股本变迁样例 ---")
    print(df_changes_clean.head(3))


if __name__ == "__main__":
    sync_axdata()