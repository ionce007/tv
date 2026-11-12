import asyncio
from src.analysis.price_adjust import load_qfq
import polars as pl

# 模拟前端请求：获取 1999-11-10 之前的数据
df = load_qfq("sz000006")  # 替换为你想测试的股票代码
print("原始数据总量:", df.height)
print("最早日期:", df["trade_date"].min())
print("最新日期:", df["trade_date"].max())

# 模拟 API 的过滤逻辑
before_date = "1999-11-10"
df_filtered = df.filter(pl.col("trade_date") < before_date)

print(f"\n过滤 < {before_date} 后的数据量:", df_filtered.height)
if df_filtered.height > 0:
    print("能拿到的最早 3 天:")
    print(df_filtered.head(3))
else:
    print("过滤后为空！说明本地数据确实没有 1999-11-10 之前的数据。")