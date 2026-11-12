# backend/scripts/daily_etl_all.py
import asyncio
import json
import polars as pl
from datetime import date, timedelta
from pathlib import Path

from config import DATA_ROOT
from src.ingest.ticks import fetch_many, write_partitioned
from src.analysis.cvd import aggregate_daily_cvd

BASIC_INFO_FILE = DATA_ROOT / "basic_info.parquet"
CVD_DIR = DATA_ROOT / "daily_cvd"
FAILED_LOG = DATA_ROOT / "failed_ticks.json"

# ================= 工具函数 =================

def get_trade_days(start_date: date, end_date: date) -> list[date]:
    """获取两个日期之间的所有工作日（排除周末）。"""
    days = []
    curr = start_date
    while curr <= end_date:
        if curr.weekday() < 5: # 0-4 是周一到周五
            days.append(curr)
        curr += timedelta(days=1)
    return days

def record_failed(symbols: list[str], trade_date: date):
    """记录失败的标的与日期，用于后续补全。"""
    failed = {}
    if FAILED_LOG.exists():
        failed = json.loads(FAILED_LOG.read_text())
    
    date_str = trade_date.strftime("%Y-%m-%d")
    if date_str not in failed:
        failed[date_str] = []
    
    failed[date_str].extend(symbols)
    failed[date_str] = list(set(failed[date_str])) # 去重
    FAILED_LOG.write_text(json.dumps(failed, indent=2))

def clear_failed(trade_date: date, symbols: list[str]):
    """如果补全成功，从失败列表中移除。"""
    if not FAILED_LOG.exists():
        return
    failed = json.loads(FAILED_LOG.read_text())
    date_str = trade_date.strftime("%Y-%m-%d")
    
    if date_str in failed:
        failed[date_str] = [s for s in failed[date_str] if s not in symbols]
        if not failed[date_str]:
            del failed[date_str]
        FAILED_LOG.write_text(json.dumps(failed, indent=2))

# ================= 核心下载逻辑 =================

async def download_with_retry(symbols: list[str], trade_date: date, max_retries: int = 3) -> bool:
    """带重试机制的下载。返回 True 表示成功，False 表示彻底失败。"""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"  [尝试 {attempt}/{max_retries}] 下载 {len(symbols)} 只标的...")
            df = await fetch_many(symbols, trade_date)
            if df.height > 0:
                write_partitioned(df)
                return True
            else:
                print(f"  [WARN] 返回空数据。")
                return True # 返回空说明停牌，不算网络失败
        except Exception as e:
            print(f"  [ERROR] 网络异常: {e}")
            if attempt == max_retries:
                print(f"  [FAIL] 彻底失败，记录到断点文件。")
                record_failed(symbols, trade_date)
                return False
            await asyncio.sleep(2 ** attempt) # 指数退避重试
    return False

async def process_single_day(symbols: list[str], trade_date: date, batch_size: int = 50):
    """处理单天的全市场下载。"""
    total = len(symbols)
    print(f"\n========== 处理日期: {trade_date} ==========")
    
    for i in range(0, total, batch_size):
        batch = symbols[i:i+batch_size]
        print(f"[{i+1} ~ {min(i+batch_size, total)} / {total}]")
        
        success = await download_with_retry(batch, trade_date)
        if success:
            clear_failed(trade_date, batch) # 成功则从失败列表中清除
        
        await asyncio.sleep(0.5) # 批次间稍微停顿，保护服务器

async def update_cvd_incremental(symbols: list[str], trade_date: date):
    """增量计算当天的 CVD。"""
    print(f"\n[INFO] 正在增量计算 {trade_date} 的 CVD...")
    today_str = trade_date.strftime("%Y-%m-%d")
    
    for i, sym in enumerate(symbols):
        tick_folder = DATA_ROOT / "ticks" / f"trade_date={today_str}" / f"symbol={sym}"
        if not tick_folder.exists():
            continue
            
        today_delta = aggregate_daily_cvd(sym, today_str)
        if not today_delta:
            continue
            
        cvd_file = CVD_DIR / f"symbol={sym}" / "data.parquet"
        new_row = pl.DataFrame([today_delta])
        
        if cvd_file.exists():
            old_df = pl.read_parquet(cvd_file)
            merged_df = pl.concat([old_df, new_row]).unique(subset=["trade_date"], keep="last").sort("trade_date")
        else:
            merged_df = new_row.sort("trade_date")

        final_df = merged_df.with_columns(pl.col("delta").cum_sum().alias("cvd"))
        cvd_file.parent.mkdir(parents=True, exist_ok=True)
        final_df.write_parquet(cvd_file)

        if (i + 1) % 200 == 0:
            print(f"[CVD PROGRESS] {i+1}/{len(symbols)}")

# ================= 主流程 =================

async def main(mode: str = "incremental", days_back: int = 1):
    """
    mode: "incremental" (拉取近几天) / "repair" (补全失败)
    days_back: 拉取过去多少天的数据
    """
    if not BASIC_INFO_FILE.exists():
        print("[ERROR] 缺少 basic_info.parquet！")
        return

    # 获取全市场代码池
    basic_df = pl.read_parquet(BASIC_INFO_FILE)
    all_symbols = basic_df["tdx_symbol"].drop_nulls().to_list()

    if mode == "repair":
        print("[INFO] 进入数据补全模式...")
        if not FAILED_LOG.exists():
            print("[INFO] 没有发现失败记录，无需补全。")
            return
        
        failed_data = json.loads(FAILED_LOG.read_text())
        for date_str, symbols in failed_data.items():
            trade_date = date.fromisoformat(date_str)
            await process_single_day(symbols, trade_date, batch_size=20)
            await update_cvd_incremental(symbols, trade_date)
            
        print("[DONE] 数据补全任务结束。")
        return

    # 正常拉取模式（支持多天）
    today = date.today()
    # 如果今天是周一，回溯 3 天把周末和周五补上
    start_date = today - timedelta(days=days_back)
    trade_days = get_trade_days(start_date, today)
    
    print(f"[INFO] 计划拉取 {len(trade_days)} 个交易日: {[d.strftime('%Y-%m-%d') for d in trade_days]}")

    for t_date in trade_days:
        await process_single_day(all_symbols, t_date)
        await update_cvd_incremental(all_symbols, t_date)

    print("\n[DONE] 全部任务完成！")

if __name__ == "__main__":
    import sys
    
    # 命令行参数控制
    # python -m scripts.daily_etl_all incremental 3  (拉取过去 3 天)
    # python -m scripts.daily_etl_all repair         (只补全失败的批次)
    mode_arg = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    days_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    asyncio.run(main(mode=mode_arg, days_back=days_arg))