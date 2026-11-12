import asyncio
from src.ingest.history_hfq import download_hfq_for_all

if __name__ == "__main__":
    asyncio.run(download_hfq_for_all())