from config import TICKS_ROOT

def query_footprint(con, symbol: str, trade_date: str):
    pattern = str(TICKS_ROOT / "**" / "*.parquet")
    return con.sql(f"""
        SELECT * FROM read_parquet('{pattern}')
        WHERE symbol = '{symbol}' AND trade_date = '{trade_date}'
        ORDER BY time
    """).pl()