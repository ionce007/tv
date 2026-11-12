
import asyncio
from src.ingest.history import fill_history_for_all

if __name__ == "__main__":
    mode = "missing"  # 默认只补缺口
    asyncio.run(fill_history_for_all(mode))
 