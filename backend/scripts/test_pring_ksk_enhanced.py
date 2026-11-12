# scripts/test_pring_ksk_enhanced.py

import polars as pl
from src.analysis.price_adjust import load_qfq
from src.analysis.indicators import calc_all_indicators, add_pring_ksk_enhanced

def main():
    # 1. 配置 Polars 展开所有列打印
    pl.Config.set_tbl_cols(-1)
    pl.Config.set_tbl_width_chars(200)

    # 选一只上市较短的股票：sz301656（创业板新股）
    symbol = "sz301656"
    print(f"正在加载 {symbol} 的前复权数据...")
    
    # 加载前复权数据
    df = load_qfq(symbol)
    
    # 2. 运行基础指标（这里主要为了验证代码不报错，你可以不跑）
    df_ind = calc_all_indicators(df)
    
    # 3. 关键步骤：显式调用增强版 Pring KSK
    # 原版 k=1.0 的最长周期是 530，新股只有 267 根数据，原版会全是 null
    # 我们用 k=0.3 压缩周期（530 * 0.3 = 159），让它能算出来
    df_ind_short = add_pring_ksk_enhanced(df_ind, k=0.3, smooth_method="sma")
    
    # 4. 查看结果
    print(f"\n数据总行数: {df_ind_short.height}")
    print("最后 5 天的计算结果：")
    print(df_ind_short.tail(5).select([
        "trade_date", 
        "close", 
        "pring_ksk_enh_k0.3"  # 增强版的列名会自动带上 k 值
    ]))

    # 附加：验证一下原版是不是真的是 null
    print("\n验证原版 Pring KSK（应该大量为 null）：")
    if "pring_ksk" in df_ind_short.columns:
        print(df_ind_short.tail(3).select(["trade_date", "pring_ksk"]))
    else:
        print("原版 pring_ksk 未在基础指标中计算。")
        
     # 验证 SMC 列
    print("\nDataFrame 的所有列名：")
    print(df_ind_short.columns)
    
    # 如果有 SMC 列，选几行出来看看
    smc_cols = [c for c in df_ind_short.columns if 'fvg' in c.lower() or 'swing' in c.lower() or 'bos' in c.lower()]
    if smc_cols:
        print("\nSMC 指标计算结果：")
        # 垂直打印最后一行，一目了然
        last_row = df_ind_short.tail(1).transpose(include_header=True)
        print(last_row.filter(pl.col("column").is_in(["trade_date", "close", "fvg_bullish", "swing_low", "swing_low_price", "bos_bullish"])))
        

if __name__ == "__main__":
    main()