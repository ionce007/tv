# config.py
from pathlib import Path

# ===== 数据根目录（项目外，独立磁盘）=====
DATA_ROOT = Path(r"E:\StockData")

# ===== 派生路径 =====
TICKS_ROOT = DATA_ROOT / "ticks"                    # 逐笔数据
KLINE_ROOT = DATA_ROOT / "kline"                    # K 线数据
SYMBOL_CACHE = DATA_ROOT / "symbols.json"           # 标的清单缓存
PROGRESS_FILE = DATA_ROOT / "_progress.json"        # 下载进度（断点续传）

# 确保根目录存在（首次运行自动创建）
DATA_ROOT.mkdir(parents=True, exist_ok=True)