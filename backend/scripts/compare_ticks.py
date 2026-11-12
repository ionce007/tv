# backend/scripts/compare_ticks.py
import asyncio
import sys
import polars as pl
from config import DATA_ROOT
from pytdxdata import TdxData

TICKS_ROOT = DATA_ROOT / "ticks"

async def fetch_api_ticks(symbol: str, trade_date: str):
    """从 API 获取逐笔数据并转成 Polars DataFrame"""
    print(f"[INFO] 正在从 API 获取 {symbol} 在 {trade_date} 的数据...")
    async with TdxData() as td:
        try:
            date_int = int(trade_date.replace("-", ""))
            ticks = await td.get_ticks([symbol], date=date_int)
            if not ticks:
                return pl.DataFrame()
                
            rows = [{
                "time": t.time,
                "price": t.price,
                "vol": t.vol,
                "bs_flag": t.bs_flag,
                "trade_count": getattr(t, "trade_count", 0),
            } for t in ticks]
            return pl.DataFrame(rows)
        except Exception as e:
            print(f"[ERROR] API 获取失败: {e}")
            return pl.DataFrame()

def fetch_local_ticks(symbol: str, trade_date: str):
    """从本地读取逐笔数据并转成 Polars DataFrame"""
    print(f"[INFO] 正在从本地读取 {symbol} 在 {trade_date} 的数据...")
    tick_folder = TICKS_ROOT / f"trade_date={trade_date}" / f"symbol={symbol}"
    if not tick_folder.exists():
        print(f"[ERROR] 本地未找到该日数据文件夹: {tick_folder}")
        return pl.DataFrame()
        
    try:
        df = pl.read_parquet(tick_folder)
        if "trade_count" not in df.columns:
            df = df.with_columns(pl.lit(0).alias("trade_count"))
            
        return df.select(["time", "price", "vol", "bs_flag", "trade_count"])
    except Exception as e:
        print(f"[ERROR] 本地读取失败: {e}")
        return pl.DataFrame()

async def main(symbol: str, trade_date: str):
    df_api = await fetch_api_ticks(symbol, trade_date)
    df_local = fetch_local_ticks(symbol, trade_date)
    
    if df_api.is_empty() or df_local.is_empty():
        print("[WARN] 有一方数据为空，无法比较。")
        return

    print("\n" + "="*50)
    print(f"  数据对比: {symbol} @ {trade_date}")
    print("="*50)
    print(f"API 获取条数  : {df_api.height} 条")
    print(f"本地保存条数  : {df_local.height} 条")
    
    if df_api.height != df_local.height:
        print(f"⚠️ 数量差异: 相差 {abs(df_api.height - df_local.height)} 条")
    else:
        print("✅ 数量一致")

    print("\n--- 1. 时间范围对比 ---")
    print(f"API 时间范围 : {df_api['time'].min()} ~ {df_api['time'].max()}")
    print(f"本地时间范围 : {df_local['time'].min()} ~ {df_local['time'].max()}")

    print("\n--- 2. 买卖方向对比 (bs_flag: 0=买, 1=卖, 2=中性) ---")
    api_bs = df_api.group_by("bs_flag").len().sort("bs_flag")
    local_bs = df_local.group_by("bs_flag").len().sort("bs_flag")
    
    print("API 方向分布:")
    print(api_bs)
    print("本地方向分布:")
    print(local_bs)

    print("\n--- 3. 头尾切片数据比对 ---")
    df_api = df_api.sort("time")
    df_local = df_local.sort("time")

    print("\n【首条数据 (API vs 本地)】")
    print("API :", df_api.head(1).to_dicts()[0])
    print("本地:", df_local.head(1).to_dicts()[0])

    print("\n【尾条数据 (API vs 本地)】")
    print("API :", df_api.tail(1).to_dicts()[0])
    print("本地:", df_local.tail(1).to_dicts()[0])

    print("\n--- 4. 单笔最大成交量对比 ---")
    max_api = df_api.select(pl.col("vol").max().alias("max_vol"))["max_vol"][0]
    max_local = df_local.select(pl.col("vol").max().alias("max_vol"))["max_vol"][0]
    print(f"API 最大单笔成交: {max_api:.2f} 股")
    print(f"本地最大单笔成交: {max_local:.2f} 股")

if __name__ == "__main__":
    # 如果终端没有带参数，给出提示并退出
    if len(sys.argv) < 3:
        print("用法: python -m scripts.compare_ticks <股票代码> <日期>")
        print("示例: python -m scripts.compare_ticks sh688535 2026-02-24")
        sys.exit(1)
        
    symbol_input = sys.argv[1]
    trade_date_input = sys.argv[2]
    
    # 智能补全前缀
    if not (symbol_input.startswith("sh") or symbol_input.startswith("sz") or symbol_input.startswith("bj")):
        if symbol_input.startswith("6"):
            symbol_input = f"sh{symbol_input}"
        elif symbol_input.startswith("0") or symbol_input.startswith("3"):
            symbol_input = f"sz{symbol_input}"
        else:
            symbol_input = f"bj{symbol_input}"

    asyncio.run(main(symbol_input, trade_date_input))