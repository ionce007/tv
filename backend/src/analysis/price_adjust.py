# src/analysis/price_adjust.py
import polars as pl
from config import KLINE_ROOT

def load_qfq(symbol: str) -> pl.DataFrame:
    """
    读取本地数据并实时计算前复权行情。
    返回包含全部列（open, high, low, close, vol, amount）的前复权 DataFrame。
    """
    base_dir = KLINE_ROOT / "period=day" / f"symbol={symbol}"
    f_raw = base_dir / "data.parquet"
    f_hfq = base_dir / "data_hfq.parquet"

    if not f_raw.exists() or not f_hfq.exists():
        raise FileNotFoundError(f"{symbol} 缺少原始或后复权数据文件")

    # 只读取需要的列，提升加载速度
    cols = ["trade_date", "open", "high", "low", "close", "vol", "amount"]
    df_raw = pl.read_parquet(f_raw, columns=cols)
    df_hfq = pl.read_parquet(f_hfq, columns=cols)

    # 获取最新交易日的价格作为锚点（以不复权的最新价为基准）
    last_raw = df_raw.sort("trade_date").tail(1)
    last_hfq = df_hfq.sort("trade_date").tail(1)

    # 提取标量值
    latest_raw_close = last_raw["close"][0]
    latest_hfq_close = last_hfq["close"][0]

    # 计算复权因子 (如果最新后复权价为 0，说明数据异常，防除零)
    factor = latest_raw_close / latest_hfq_close if latest_hfq_close != 0 else 1.0

    # 将后复权数据的 OHLC 乘以因子，得到前复权序列
    # 注意：vol 和 amount 保持原样，不参与复权缩放
    df_qfq = df_hfq.with_columns([
        (pl.col("open") * factor).alias("open"),
        (pl.col("high") * factor).alias("high"),
        (pl.col("low") * factor).alias("low"),
        (pl.col("close") * factor).alias("close"),
        pl.lit(symbol).alias("symbol")
    ])
    
    return df_qfq