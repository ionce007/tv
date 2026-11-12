# 存为 scripts/test_qfq.py
from src.analysis.price_adjust import load_qfq
import polars as pl

df = load_qfq("sh600000")

print("--- 最新 3 天（前复权价应等于不复权真实价）---")
print(df.tail(3).select(["trade_date", "close"]))

print("\n--- 上市初期 3 天（前复权价应远低于不复权真实价）---")
raw = pl.read_parquet("E:/StockData/kline/period=day/symbol=sh600000/data.parquet")
print("原始不复权:")
print(raw.head(3).select(["trade_date", "close"]))
print("前复权(QFQ):")
print(df.head(3).select(["trade_date", "close"]))