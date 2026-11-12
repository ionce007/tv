# scripts/download_test_ticks.py
import asyncio
from datetime import date
from src.ingest.ticks import fetch_many, write_partitioned

async def main():
    symbols = ["sz000001"]
    # 注意日期：昨天是 2026-11-06
    trade_date = date(2026, 11, 6) 
    
    print(f"开始下载 {symbols} 在 {trade_date} 的逐笔数据...")
    df = await fetch_many(symbols, trade_date)
    
    if df.height > 0:
        write_partitioned(df)
        print(f"下载成功，共 {df.height} 条记录。")
    else:
        print("未获取到数据，可能是该日无交易或接口限制。")

if __name__ == "__main__":
    asyncio.run(main())