# scripts/test_indicators.py

import polars as pl
from src.analysis.price_adjust import load_qfq
from src.analysis.indicators import calc_all_indicators

def main():
    # 1. 配置 Polars 终端打印（不折叠列，防止出现 ...）
    pl.Config.set_tbl_cols(-1)          # 显示所有列
    pl.Config.set_tbl_width_chars(250)  # 增加终端表格宽度
    pl.Config.set_fmt_str_lengths(20)

    symbol = "sz300053"
    print(f"正在加载 {symbol} 的前复权数据并计算全部指标...\n")
    
    # 2. 加载前复权行情数据
    df = load_qfq(symbol)
    
    # 3. 计算所有指标（基础 + 高级）
    df_ind = calc_all_indicators(df)
    
    # 4. 提取最后 5 天的数据，分为两块打印，避免终端过度拥挤
    
    print("="*80)
    print("基础指标 (SMA / EMA / MACD / KDJ / RSI / BOLL / ATR / KAMA)")
    print("="*80)
    base_cols = [
        "trade_date", "close", 
        "sma_20", "ema_12", "macd_dif", "macd_hist",
        "kdj_k", "kdj_d", "rsi_14", "atr_14", "kama_10"
    ]
    # 过滤出实际存在的列并打印
    base_exist = [c for c in base_cols if c in df_ind.columns]
    print(df_ind.tail(5).select(base_exist))
    
    print("\n" + "="*80)
    print("新增高级指标 (Chandelier / CHOP / CRSI / Ulcer / Pring KSK / VWAP)")
    print("="*80)
    adv_cols = [
        "trade_date", "close",
        "chandelier_long", "chop_14", "crsi", 
        "ulcer_14", "vwap_cum",
        "pring_ksk",
        "pring_ksk_enh_k1.0", # 增强版(等于原版，用于验证)
        # "pring_ksk_enh_k0.5", # 如果你对短历史股票测试，可以加上这列
    ]
    # 过滤出实际存在的列并打印
    adv_exist = [c for c in adv_cols if c in df_ind.columns]
    print(df_ind.tail(5).select(adv_exist))

if __name__ == "__main__":
    main()