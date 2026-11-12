import polars as pl
from src.analysis.orderflow import add_delta_cvd
from config import TICKS_ROOT

def main():
    pl.Config.set_tbl_cols(-1)
    pl.Config.set_tbl_width_chars(200)

    # 修改这里：直接传入 symbol 的目录，而不是写死具体的文件名
    folder = TICKS_ROOT / "trade_date=2026-11-06" / "symbol=sz000001"
    
    if not folder.exists():
        print(f"找不到文件夹: {folder}，请先运行逐笔下载。")
        return

    # 读取目录下的所有 parquet 文件
    ticks = pl.read_parquet(folder)
    print(f"逐笔数据行数: {ticks.height}")

    # 计算 1 分钟级别的 Delta 和 CVD
    res = add_delta_cvd(ticks, freq="1m")
    
    # 只打印核心列
    cols = ["dt", "close", "buy_vol", "sell_vol", "delta", "cum_delta"]
    print("\n前 5 分钟订单流：")
    print(res.head(5).select(cols))
    
    print("\n最后 5 分钟订单流：")
    print(res.tail(5).select(cols))

if __name__ == "__main__":
    main()