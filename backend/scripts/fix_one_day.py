# backend/scripts/fix_one_day.py
import asyncio
import sys
from datetime import date
from src.ingest.ticks import fetch_many, write_partitioned

async def main(symbol: str, date_str: str):
    # 将 2026-02-24 转换为 date 对象
    d = date.fromisoformat(date_str)
    print(f"[INFO] 正在强制补全 {symbol} 在 {date_str} 的逐笔数据...")
    
    df = await fetch_many([symbol], d)
    if df.height > 0:
        write_partitioned(df)
        print(f"[OK] 补全成功，共写入 {df.height} 条记录。")
    else:
        print("[WARN] 接口未返回数据，可能是该日停牌或无交易。")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python -m scripts.fix_one_day <股票代码> <日期 YYYY-MM-DD>")
        sys.exit(1)
        
    sym = sys.argv[1]
    if not (sym.startswith("sh") or sym.startswith("sz") or sym.startswith("bj")):
        sym = f"sh{sym}" if sym.startswith("6") else f"sz{sym}"
        
    asyncio.run(main(sym, sys.argv[2]))