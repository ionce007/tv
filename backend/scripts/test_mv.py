import polars as pl
from config import DATA_ROOT

f = DATA_ROOT / "basic_info.parquet"
df = pl.read_parquet(f)

print("总行数:", df.height)
print("前 5 行数据:\n", df.head(5))
print("\n浮点数列的统计信息:")
print(df.select(["float_mv", "total_mv"]).describe())