# backend/src/api/controllers/kline_controller.py
import polars as pl
from datetime import date, timedelta
from config import DATA_ROOT
from src.analysis.price_adjust import load_qfq
from src.analysis.indicators import calc_all_indicators, add_anchored_vwap

# 数据文件路径常量
BASIC_INFO_FILE = DATA_ROOT / "basic_info.parquet"
CAPITAL_CHANGES_FILE = DATA_ROOT / "capital_changes.parquet"
CVD_DIR = DATA_ROOT / "daily_cvd"

def get_kline_data(symbol: str, limit: int, before_date: str | None = None, anchor_date: str | None = None):
    """
    获取指定股票的前复权 K 线，并计算全套指标、动态换手率、AVWAP 和日线 CVD。
    """
    df = load_qfq(symbol)
    if df.is_empty():
        return None

    # 1. 基础指标计算
    df = calc_all_indicators(df)
    
    # 把 SQZ 指标算进去！
    from src.analysis.indicators import add_ttm_squeeze
    df = add_ttm_squeeze(df)
    
    # 2. 计算 AVWAP (如果前端未传，默认锚定 1 年前的今天)
    # 如果前端没传，默认不截取（即从前端的 limit 截取的起点开始算）
    if anchor_date:
        df = add_anchored_vwap(df, anchor_date=anchor_date)
    else:
        # 不传日期，意味着从数据的第一天开始累积，曲线平滑
        df = add_anchored_vwap(df) 
    df = add_anchored_vwap(df, anchor_date=anchor_date)

    # 3. 动态历史换手率计算
    tdx_symbol_val = symbol
    current_float_shares = 0.0
    
    if BASIC_INFO_FILE.exists():
        basic_df = pl.read_parquet(BASIC_INFO_FILE).filter(pl.col("tdx_symbol") == tdx_symbol_val)
        if not basic_df.is_empty():
            current_float_shares = basic_df["float_shares"][0] or 0.0
    
    shares_df = pl.DataFrame()
    if CAPITAL_CHANGES_FILE.exists():
        shares_df = pl.read_parquet(CAPITAL_CHANGES_FILE).filter(pl.col("tdx_symbol") == tdx_symbol_val)
    
    if not shares_df.is_empty():
        df = df.with_columns(pl.col("trade_date").cast(pl.Utf8)).sort("trade_date")
        shares_df = shares_df.with_columns(pl.col("change_date").cast(pl.Utf8)).sort("change_date")
        
        df = df.join_asof(
            shares_df.select(["change_date", "prev_float_shares", "new_float_shares"]),
            left_on="trade_date",
            right_on="change_date",
            strategy="backward"
        )
        
        first_event_prev = shares_df["prev_float_shares"][0] if len(shares_df) > 0 and shares_df["prev_float_shares"][0] > 0 else current_float_shares
        fallback_shares = first_event_prev if first_event_prev > 0 else current_float_shares
        
        df = df.with_columns(
            pl.coalesce([pl.col("new_float_shares"), pl.lit(fallback_shares)]).alias("current_float_shares")
        )
        
        df = df.with_columns(
            pl.when(pl.col("current_float_shares") <= 0)
            .then(fallback_shares)
            .otherwise(pl.col("current_float_shares"))
            .alias("current_float_shares")
        )
    else:
        df = df.with_columns(pl.lit(current_float_shares).alias("current_float_shares"))

    df = df.with_columns([
        pl.when(pl.col("current_float_shares") > 0)
        .then((pl.col("vol")) / pl.col("current_float_shares") * 100)
        .otherwise(0.0)
        .alias("turnover_rate")
    ])

    drop_cols = ["change_date", "prev_float_shares", "new_float_shares", "current_float_shares"]
    df = df.drop([c for c in drop_cols if c in df.columns])

    # 4. 合并日线 CVD
    cvd_file = CVD_DIR / f"symbol={symbol}" / "data.parquet"
    if cvd_file.exists():
        cvd_df = pl.read_parquet(cvd_file).select(["trade_date", "cvd"])
        df = df.join(cvd_df, on="trade_date", how="left")
        # 对于没有逐笔数据的日子，填充为 0 (或者前向填充，根据你的业务口径)
        df = df.with_columns(pl.col("cvd").fill_null(0.0))
    else:
        df = df.with_columns(pl.lit(0.0).alias("cvd"))

    # 5. 过滤日期与切片返回
    if before_date:
        df_slice = df.filter(pl.col("trade_date") < before_date)
    else:
        df_slice = df
        
    if df_slice.height == 0:
        return []  # 返回空列表，表示没有更多数据了
        
    df_result = df_slice.tail(limit)
    
    # 6. 数据清洗
    float_cols = [c for c, t in zip(df_result.columns, df_result.dtypes) if t == pl.Float64]
    df_result = df_result.with_columns([
        pl.col(c).fill_nan(None).fill_null(0.0) for c in float_cols
    ])
    
    return df_result.to_dicts()