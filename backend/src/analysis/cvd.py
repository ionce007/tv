# backend/src/analysis/cvd.py
import polars as pl
from pathlib import Path
from config import DATA_ROOT

TICKS_ROOT = DATA_ROOT / "ticks"
CVD_DIR = DATA_ROOT / "daily_cvd"

def aggregate_daily_cvd(symbol: str, trade_date: str) -> dict | None:
    """
    读取指定股票某天的逐笔数据，计算日线级别的 Delta 和 CVD。
    trade_date 格式：YYYY-MM-DD
    """
    # 逐笔数据存放路径：data/ticks/trade_date=2026-11-06/symbol=sz000001/
    tick_folder = TICKS_ROOT / f"trade_date={trade_date}" / f"symbol={symbol}"
    if not tick_folder.exists():
        return None

    try:
        # 1. 读取当天所有逐笔数据
        ticks = pl.read_parquet(tick_folder)
        if ticks.is_empty():
            return None

        # 2. 计算当天的主动买量、主动卖量和 Delta
        # bs_flag: 0=主动买, 1=主动卖, 2=中性 (忽略 2)
        agg = ticks.select([
            pl.when(pl.col("bs_flag") == 0).then(pl.col("vol")).otherwise(0).sum().alias("buy_vol"),
            pl.when(pl.col("bs_flag") == 1).then(pl.col("vol")).otherwise(0).sum().alias("sell_vol"),
        ])
        
        buy_vol = agg["buy_vol"][0] or 0.0
        sell_vol = agg["sell_vol"][0] or 0.0
        delta = buy_vol - sell_vol

        return {
            "symbol": symbol,
            "trade_date": trade_date,
            "buy_vol": buy_vol,
            "sell_vol": sell_vol,
            "delta": delta
        }
    except Exception as e:
        print(f"[WARN] 计算 {symbol} {trade_date} 的 Delta 失败: {e}")
        return None

def rebuild_cvd_for_symbol(symbol: str):
    """
    针对某只股票，读取所有已下载的逐笔数据，重算全历史 CVD 并保存。
    """
    print(f"正在为 {symbol} 计算历史 CVD...")
    # 找出该股票所有存在逐笔数据的日期
    date_folders = TICKS_ROOT.glob("trade_date=*")
    results = []

    for folder in date_folders:
        trade_date = folder.name.replace("trade_date=", "")
        res = aggregate_daily_cvd(symbol, trade_date)
        if res:
            results.append(res)

    if not results:
        print(f"[INFO] {symbol} 没有可用的逐笔数据。")
        return

    # 转为 Polars 并计算累积 CVD
    df = pl.DataFrame(results).sort("trade_date")
    df = df.with_columns(
        pl.col("delta").cum_sum().alias("cvd")
    )

    # 保存结果到 data/daily_cvd/symbol=xxx/data.parquet
    CVD_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = CVD_DIR / f"symbol={symbol}"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_dir / "data.parquet")
    
    print(f"[OK] {symbol} 历史 CVD 已生成，共 {df.height} 天。")