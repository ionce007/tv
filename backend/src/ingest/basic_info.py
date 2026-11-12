# backend/src/ingest/basic_info.py
# 在文件最顶部（import akshare 之前）添加：
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 猴子补丁：禁用所有请求的 SSL 验证
_original_request = requests.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs['verify'] = False
    return _original_request(self, method, url, **kwargs)
requests.Session.request = _patched_request


import akshare as ak
import polars as pl
from config import DATA_ROOT

BASIC_INFO_FILE = DATA_ROOT / "basic_info.parquet"

def fetch_basic_info_akshare():
    print("[INFO] 正在通过 AKShare 拉取全市场基础信息...")
    # 获取全市场实时行情快照
    df_spot = ak.stock_zh_a_spot_em()

    # 转换为 Polars，提取代码、名称、流通市值、总市值
    df = pl.from_pandas(df_spot).select([
        pl.col("代码").alias("code"),
        pl.col("名称").alias("name"),
        pl.col("流通市值").cast(pl.Float64, strict=False).alias("float_mv"),
        pl.col("总市值").cast(pl.Float64, strict=False).alias("total_mv"),
    ])

    # 生成 symbol 前缀
    df = df.with_columns(
        pl.when(pl.col("code").str.starts_with("6"))
        .then(pl.concat_str([pl.lit("sh"), pl.col("code")]))
        .when(pl.col("code").str.starts_with("0") | pl.col("code").str.starts_with("3"))
        .then(pl.concat_str([pl.lit("sz"), pl.col("code")]))
        .otherwise(pl.lit(None))
        .alias("symbol")
    ).filter(pl.col("symbol").is_not_null()).drop("code")

    # 强制全量覆盖写入（旧数据全是 0，没必要合并保留了）
    df.write_parquet(BASIC_INFO_FILE)
    print(f"[OK] 已覆盖保存 {df.height} 只股票的基础信息（含真实流通市值）。")
    print("样例数据:\n", df.head(3))

if __name__ == "__main__":
    fetch_basic_info_akshare()