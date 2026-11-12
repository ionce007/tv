# scripts/download_all.py
import asyncio, sys
from src.ingest.bulk import main

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"   # full | incremental
    period = sys.argv[2] if len(sys.argv) > 2 else "day"
    asyncio.run(main(mode, period))