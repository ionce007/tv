import asyncio
from src.ingest.ticks import fetch_many, write_partitioned
from src.analysis.cvd import rebuild_cvd_for_symbol
from datetime import date

async def daily_job():
    symbols = ["sz000001", "sh600000"]  # 你的关注池
    today = date.today().strftime("%Y-%m-%d")
    
    # 1. 下载今天的逐笔
    df = await fetch_many(symbols, today)
    write_partitioned(df)
    
    # 2. 重算这些股票的 CVD（包含今天的新数据）
    for sym in symbols:
        rebuild_cvd_for_symbol(sym)

if __name__ == "__main__":
    asyncio.run(daily_job())