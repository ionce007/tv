# scripts/fetch_universe.py
import asyncio
from pytdxdata import TdxData
from src.ingest.universe import fetch_universe

async def main():
    async with TdxData() as td:
        universe = await fetch_universe(td)
        print(f"个股: {len(universe['stocks'])} 只")
        print(f"指数: {len(universe['indexes'])} 个")
        print(f"个股样例: {universe['stocks'][:5]}")
        print(f"指数样例: {universe['indexes'][:5]}")

if __name__ == "__main__":
    asyncio.run(main())