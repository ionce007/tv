# backend/scripts/download_single_all_ticks.py
import asyncio
import sys
import json
from datetime import date, datetime, timedelta
import polars as pl
from config import DATA_ROOT
from src.ingest.ticks import fetch_many, write_partitioned
from src.analysis.cvd import aggregate_daily_cvd

BASIC_INFO_FILE = DATA_ROOT / "basic_info.parquet"
CVD_DIR = DATA_ROOT / "daily_cvd"
PROGRESS_FILE = DATA_ROOT / "_single_ticks_progress.json"

def get_list_date(symbol: str) -> date | None:
    if not BASIC_INFO_FILE.exists():
        return None
    try:
        basic_df = pl.read_parquet(BASIC_INFO_FILE).filter(pl.col("tdx_symbol") == symbol)
        if not basic_df.is_empty() and "list_date" in basic_df.columns:
            date_str = basic_df["list_date"][0]
            if date_str and len(str(date_str)) == 8:
                return datetime.strptime(str(date_str), "%Y%m%d").date()
    except Exception:
        pass
    return None

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {}

def save_progress(symbol: str, last_date: str):
    progress = load_progress()
    progress[symbol] = last_date
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))

async def download_with_retry(symbol: str, t_date: date, max_retries: int = 3) -> bool:
    date_str = t_date.strftime("%Y-%m-%d")
    for attempt in range(1, max_retries + 1):
        try:
            df = await fetch_many([symbol], t_date)
            if df.height > 0:
                write_partitioned(df)
                return True
            else:
                return True # 停牌或空数据
        except Exception as e:
            if attempt == max_retries:
                print(f"\n  [FAIL] {date_str} 重试 {max_retries} 次依然失败: {e}")
                return False
            await asyncio.sleep(2 ** attempt)
    return False

def process_cvd_logic(symbol: str, trade_days_to_calc: list[date]):
    """统一处理 CVD 计算与合并，剥离了下载逻辑。"""
    print("[INFO] 开始增量计算并更新 CVD...")
    cvd_results = []
    
    for t_date in trade_days_to_calc:
        date_str = t_date.strftime("%Y-%m-%d")
        tick_folder = DATA_ROOT / "ticks" / f"trade_date={date_str}" / f"symbol={symbol}"
        if not tick_folder.exists():
            continue
            
        res = aggregate_daily_cvd(symbol, date_str)
        if res:
            cvd_results.append(res)

    if not cvd_results:
        print("[WARN] 未找到任何本地逐笔数据，CVD 未更新。")
        return

    df_cvd = pl.DataFrame(cvd_results).sort("trade_date")
    cvd_file = CVD_DIR / f"symbol={symbol}" / "data.parquet"
    
    if cvd_file.exists():
        old_df = pl.read_parquet(cvd_file)
        base_cols = ["symbol", "trade_date", "buy_vol", "sell_vol", "delta"]
        
        # 兼容处理：防止老文件缺列或有多余的 6 列引发 ShapeError
        for col in base_cols:
            if col not in old_df.columns:
                old_df = old_df.with_columns(pl.lit(None).alias(col))
                
        old_df = old_df.select(base_cols)
        df_cvd = df_cvd.select(base_cols)
        
        merged_df = pl.concat([old_df, df_cvd]).unique(subset=["trade_date"], keep="last").sort("trade_date")
    else:
        merged_df = df_cvd.sort("trade_date")
        
    # 重新计算累积值
    final_df = merged_df.with_columns(pl.col("delta").cum_sum().alias("cvd"))
    
    cvd_file.parent.mkdir(parents=True, exist_ok=True)
    final_df.write_parquet(cvd_file)
    print(f"[OK] {symbol} CVD 更新完成！共 {final_df.height} 天历史数据。")

async def download_history(symbol: str, param: str, calc_only: bool = False):
    today = date.today()

    # ================= 纯计算模式 =================
    if calc_only:
        print(f"[INFO] 进入【纯计算模式】，不下载网络数据，直接扫描本地历史...")
        
        # 扫描该股票在本地已有的所有交易日
        all_tick_folders = list((DATA_ROOT / "ticks").glob("trade_date=*"))
        existing_days = []
        for f in all_tick_folders:
            date_str = f.name.replace("trade_date=", "")
            if (f / f"symbol={symbol}").exists():
                existing_days.append(datetime.strptime(date_str, "%Y-%m-%d").date())
                
        existing_days.sort()
        if not existing_days:
            print(f"[WARN] 本地没有找到 {symbol} 的任何逐笔数据，无法计算。")
            return
            
        print(f"[INFO] 找到 {len(existing_days)} 个本地交易日，准备重算...")
        process_cvd_logic(symbol, existing_days)
        return

    # ================= 下载 + 计算模式 =================
    if param.lower() == "all":
        list_date = get_list_date(symbol)
        if not list_date:
            print(f"[ERROR] 找不到 {symbol} 的上市日期。")
            return
        start_date = list_date
        print(f"[INFO] {symbol} 上市日期 {start_date}，执行全历史回溯。")
    else:
        try:
            days_back = int(param)
            start_date = today - timedelta(days=days_back)
            print(f"[INFO] 准备回溯 {symbol} 过去 {days_back} 天。")
        except ValueError:
            print("[ERROR] 参数错误：请输入天数或 all。")
            return

    progress = load_progress()
    if symbol in progress and param.lower() == "all":
        last_downloaded = datetime.strptime(progress[symbol], "%Y-%m-%d").date()
        print(f"[INFO] 发现断点记录，上次已下载至 {last_downloaded}。")
        if last_downloaded >= today:
            print("[INFO] 该股票数据已是最新，无需下载。")
            return
        start_date = last_downloaded + timedelta(days=1)

    trade_days = []
    curr = start_date
    while curr <= today:
        if curr.weekday() < 5:
            trade_days.append(curr)
        curr += timedelta(days=1)

    print(f"[INFO] 计划下载 {len(trade_days)} 个交易日，从 {start_date} 开始...")
    success_count = 0
    fail_count = 0
    last_success_date = None

    for i, t_date in enumerate(trade_days):
        date_str = t_date.strftime("%Y-%m-%d")
        
        tick_folder = DATA_ROOT / "ticks" / f"trade_date={date_str}" / f"symbol={symbol}"
        if tick_folder.exists():
            success_count += 1
            last_success_date = date_str
            if i % 10 == 0 or i == len(trade_days) - 1:
                print(f"[{i+1}/{len(trade_days)}] 下载 {date_str} ... [本地已存在, 跳过]")
            continue

        if i % 10 == 0 or i == len(trade_days) - 1:
            print(f"[{i+1}/{len(trade_days)}] 下载 {date_str} ...", end=" ")
            
        success = await download_with_retry(symbol, t_date)
        
        if success:
            success_count += 1
            last_success_date = date_str
            print("OK")
        else:
            fail_count += 1
            if last_success_date:
                save_progress(symbol, last_success_date)
            print(f"\n[WARN] {date_str} 彻底失败，已保存断点至 {last_success_date}。")
            break
            
        await asyncio.sleep(0.3)

    if last_success_date and len(trade_days) > 0 and trade_days[-1] == t_date:
        save_progress(symbol, trade_days[-1].strftime("%Y-%m-%d"))

    print(f"\n[INFO] 下载结束: 成功 {success_count} 天，失败 {fail_count} 天。")
    
    # 下载完成后，进行 CVD 计算
    process_cvd_logic(symbol, trade_days)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("1. 下载并计算: python -m scripts.download_single_all_ticks <代码> <天数或all>")
        print("2. 纯算 CVD : python -m scripts.download_single_all_ticks <代码> calc_only")
        sys.exit(1)
        
    symbol_input = sys.argv[1]
    param_input = sys.argv[2] if len(sys.argv) > 2 else "30"
    
    calc_only_flag = False
    if param_input.lower() == "calc_only":
        calc_only_flag = True
    
    if not (symbol_input.startswith("sh") or symbol_input.startswith("sz") or symbol_input.startswith("bj")):
        if symbol_input.startswith("6"):
            symbol_input = f"sh{symbol_input}"
        elif symbol_input.startswith("0") or symbol_input.startswith("3"):
            symbol_input = f"sz{symbol_input}"
        else:
            symbol_input = f"bj{symbol_input}"

    asyncio.run(download_history(symbol_input, param_input, calc_only=calc_only_flag))