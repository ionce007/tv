# backend/scripts/find_stocks_by_age.py
import polars as pl
from datetime import datetime, date
from config import DATA_ROOT

BASIC_INFO_FILE = DATA_ROOT / "basic_info.parquet"

def find_stocks():
    if not BASIC_INFO_FILE.exists():
        print(f"[ERROR] 找不到文件: {BASIC_INFO_FILE}")
        return

    # 1. 读取基础信息
    df = pl.read_parquet(BASIC_INFO_FILE)
    
    # 2. 计算上市天数
    today = date.today()
    # 过滤掉 list_date 为空的数据
    df = df.filter(pl.col("list_date").is_not_null() & (pl.col("list_date") != ""))
    
    # 将 '19991110' 格式的字符串转为真正的日期类型
    df = df.with_columns(
        pl.col("list_date").str.strptime(pl.Date, format="%Y%m%d", strict=False).alias("listed_date")
    ).drop_nulls("listed_date")

    # 计算距离今天过去了多少年（按 365.25 天计算，精确到小数）
    df = df.with_columns(
        ((pl.lit(today) - pl.col("listed_date")).dt.total_days() / 365.25).alias("years_listed")
    )

    # 3. 定义查找逻辑并打印
    def print_category(min_years, max_years, label, limit=2):
        print(f"\n--- {label} (上市 {min_years} ~ {max_years} 年) ---")
        
        # 过滤范围并去重，按上市日期排序
        result = df.filter(
            (pl.col("years_listed") >= min_years) & 
            (pl.col("years_listed") < max_years)
        ).unique(subset=["tdx_symbol"]).sort("listed_date")
        
        # 如果没有找到，提示；找到则选取前 limit 只
        if result.height == 0:
            print("未找到符合条件的股票。")
            return

        # 随机抽取 2 只以增加测试多样性
        sample = result.sample(n=min(limit, result.height), seed=42)
        
        for row in sample.iter_rows(named=True):
            # 格式化日期为 YYYY-MM-DD 用于打印
            date_str = row['listed_date'].strftime("%Y-%m-%d")
            print(f"代码: {row['tdx_symbol']} | 名称: {row['name']} | 上市日期: {date_str} (约 {row['years_listed']:.1f} 年)")

    # 按需求查询
    print_category(8, 11, "上市 10 年左右")
    print_category(3, 5, "上市 5 年左右")
    print_category(1, 2, "上市 3 年左右")

if __name__ == "__main__":
    find_stocks()