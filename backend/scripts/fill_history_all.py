# scripts/fill_history_all.py
import asyncio
from src.ingest.history import fill_history_for_all

if __name__ == "__main__":
    asyncio.run(fill_history_for_all())