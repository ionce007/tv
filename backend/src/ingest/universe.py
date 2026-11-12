"""枚举全市场个股与指数，缓存到磁盘避免每次重拉。"""
import json
from pathlib import Path
from datetime import date

from pytdxdata import TdxData
from config import SYMBOL_CACHE

async def fetch_universe(td: TdxData) -> dict:
    """返回 {'stocks': [...], 'indexes': [...]}。"""
    stocks, indexes = [], []

    # 个股：深市 market=0，沪市 market=1
    for market, prefix in [(0, "sz"), (1, "sh")]:
        n = await td.get_security_count(market)
        for start in range(0, n, 1000):
            batch = await td.get_security_list(market, start=start, count=1000)
            for item in batch:
                code = item.code
                # 过滤：仅保留 A 股（00/30/60/68 开头），排除基金/债券
                if code[:2] in ("00", "30", "60", "68"):
                    stocks.append(f"{prefix}{code}")

    # 指数：上证指数、深证成指等，用 get_security_list 同市场枚举后按代码过滤
    # 更稳妥的方式是维护一个常用指数清单，避免全量枚举噪音
    known_indexes = [
        "sh000001", "sh000300", "sh000905", "sh000016",
        "sz399001", "sz399006", "sz399905",
    ]
    indexes = known_indexes

    universe = {"stocks": sorted(set(stocks)), "indexes": indexes}
    SYMBOL_CACHE.write_text(json.dumps(universe, ensure_ascii=False, indent=2))
    return universe

def load_universe() -> dict:
    if SYMBOL_CACHE.exists():
        return json.loads(SYMBOL_CACHE.read_text())
    raise FileNotFoundError("先运行一次 fetch_universe 生成标的清单")