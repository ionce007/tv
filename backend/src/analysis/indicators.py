# src/analysis/indicators.py
"""
自定义量化指标库（纯 Polars 向量化实现）
输入 df 必须包含: trade_date (str/date), open, high, low, close, vol
"""

import polars as pl
import numpy as np
import pyvsmc  # 自动注册 .smc 命名空间

def add_sma(df: pl.DataFrame, windows: list[int] = [5, 10, 20, 60]) -> pl.DataFrame:
    """简单移动平均线 (Simple Moving Average)"""
    cols = [pl.col("close").rolling_mean(window_size=w).alias(f"sma_{w}") for w in windows]
    return df.with_columns(cols)

def add_ema(df: pl.DataFrame, windows: list[int] = [12, 26]) -> pl.DataFrame:
    """指数移动平均线 (Exponential Moving Average)"""
    cols = [pl.col("close").ewm_mean(span=w, adjust=False).alias(f"ema_{w}") for w in windows]
    return df.with_columns(cols)

def add_macd(df: pl.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pl.DataFrame:
    """MACD 指标 (平滑异同移动平均线)"""
    ema_fast = pl.col("close").ewm_mean(span=fast, adjust=False)
    ema_slow = pl.col("close").ewm_mean(span=slow, adjust=False)
    
    # 计算 DIF, DEA 和 MACD 柱
    dif = ema_fast - ema_slow
    dea = dif.ewm_mean(span=signal, adjust=False)
    macd = (dif - dea) * 2
    
    return df.with_columns([
        dif.alias("macd_dif"),
        dea.alias("macd_dea"),
        macd.alias("macd_hist")
    ])

def add_kdj(df: pl.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pl.DataFrame:
    """KDJ 随机指标"""
    # 计算 N 周期的最高价和最低价
    low_n = pl.col("low").rolling_min(window_size=n)
    high_n = pl.col("high").rolling_max(window_size=n)
    
    # RSV = (C - L) / (H - L) * 100
    # 注意：防止分母为 0 的情况（如果 H == L）
    rsv = pl.when(high_n == low_n).then(50.0).otherwise(
        (pl.col("close") - low_n) / (high_n - low_n) * 100
    )
    
    # K 是 RSV 的 SMA(3,1)，D 是 K 的 SMA(3,1)
    # 在 Polars 中等价于 alpha = 1/3 的 EWM
    k = rsv.ewm_mean(alpha=1/m1, adjust=False)
    d = k.ewm_mean(alpha=1/m2, adjust=False)
    j = 3 * k - 2 * d
    
    return df.with_columns([
        k.alias("kdj_k"),
        d.alias("kdj_d"),
        j.alias("kdj_j")
    ])

def add_rsi(df: pl.DataFrame, window: int = 14) -> pl.DataFrame:
    """RSI 相对强弱指标 (Wilder's Smoothing)"""
    delta = pl.col("close").diff()
    gain = pl.when(delta > 0).then(delta).otherwise(0)
    loss = pl.when(delta < 0).then(-delta).otherwise(0)
    
    # Wilder 平滑 = alpha 为 1/window 的 EWM
    avg_gain = gain.ewm_mean(alpha=1/window, adjust=False)
    avg_loss = loss.ewm_mean(alpha=1/window, adjust=False)
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return df.with_columns(rsi.alias(f"rsi_{window}"))

def add_bollinger_bands(df: pl.DataFrame, window: int = 20, num_std: float = 2.0) -> pl.DataFrame:
    """布林带 (Bollinger Bands)"""
    mid = pl.col("close").rolling_mean(window_size=window)
    std = pl.col("close").rolling_std(window_size=window)
    
    return df.with_columns([
        mid.alias("boll_mid"),
        (mid + num_std * std).alias("boll_upper"),
        (mid - num_std * std).alias("boll_lower")
    ])

def add_atr(df: pl.DataFrame, window: int = 14) -> pl.DataFrame:
    """ATR 真实波幅 (Average True Range)"""
    # TR = Max(H-L, |H-PC|, |L-PC|)
    prev_close = pl.col("close").shift(1)
    tr1 = pl.col("high") - pl.col("low")
    tr2 = (pl.col("high") - prev_close).abs()
    tr3 = (pl.col("low") - prev_close).abs()
    
    tr = pl.max_horizontal(tr1, tr2, tr3)
    
    # ATR 是 TR 的 Wilder 平滑
    atr = tr.ewm_mean(alpha=1/window, adjust=False)
    return df.with_columns(atr.alias(f"atr_{window}"))

def add_kama(df: pl.DataFrame, n: int = 10, fast: int = 2, slow: int = 30) -> pl.DataFrame:
    """
    考夫曼自适应均线 (KAMA) 
    由于涉及迭代计算，纯 Polars 表达式难以实现，需借助 numpy 循环计算。
    """
    close = df["close"].to_numpy()
    length = len(close)
    kama = np.zeros(length)
    
    # 前 n 个数据用 SMA 填充
    if length < n:
        return df.with_columns(pl.Series("kama_10", close))
    
    kama[:n] = close[:n]
    
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    
    for i in range(n, length):
        # 变化率 (Change)
        change = abs(close[i] - close[i-n])
        # 波动率 (Volatility)
        volatility = sum(abs(close[j] - close[j-1]) for j in range(i-n+1, i+1))
        
        # 效率比率 (ER)
        er = change / volatility if volatility != 0 else 0
        
        # 平滑常数 (SC)
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        
        # 迭代计算
        kama[i] = kama[i-1] + sc * (close[i] - kama[i-1])
        
    return df.with_columns(pl.Series(f"kama_{n}", kama))

# 修改 calc_all_indicators 函数 (在 indicators.py 中)
def calc_all_indicators(df: pl.DataFrame) -> pl.DataFrame:
    df = df.sort("trade_date")
    
    # 基础指标
    df = add_sma(df)
    df = add_ema(df)
    df = add_macd(df)
    df = add_kdj(df)
    df = add_rsi(df)
    df = add_bollinger_bands(df)
    df = add_atr(df)
    df = add_kama(df)
    
    # 高级指标
    df = add_chandelier_exit(df)
    df = add_chop(df)
    df = add_connors_rsi(df)
    df = add_ulcer_index(df)
    df = add_pring_ksk(df)
    df = add_vwap(df)
    
    # SMC 指标 (需安装 pyvsmc 并注册 .smc 命名空间)
    df = add_smc(df)
    
    return df


# ==========================================
# 以下为 [A1] 中补充的高级指标实现
# ==========================================

def add_chandelier_exit(df: pl.DataFrame, window: int = 22, mult: float = 3.0) -> pl.DataFrame:
    """
    1. Chandelier Exit (吊灯止损)
    利用 ATR 计算多头和空头的动态止损线。
    """
    # 首先需要 ATR
    if "atr_14" not in df.columns:
        df = add_atr(df, window=window) # 默认 window=14
    atr_col = "atr_14"

    # 过去 N 天的最高价和最低价
    highest_high = pl.col("high").rolling_max(window_size=window)
    lowest_low = pl.col("low").rolling_min(window_size=window)

    # 多头止损：最高价 - ATR * 乘数
    long_stop = highest_high - pl.col(atr_col) * mult
    # 空头止损：最低价 + ATR * 乘数
    short_stop = lowest_low + pl.col(atr_col) * mult

    return df.with_columns([
        long_stop.alias("chandelier_long"),
        short_stop.alias("chandelier_short")
    ])

def add_chop(df: pl.DataFrame, window: int = 14) -> pl.DataFrame:
    """
    2. Choppiness Index (CHOP，波动指数)
    指标值在 0-100 之间。越接近 100 代表越震荡，越接近 0 代表单边趋势。
    """
    # 计算 1 取对数做准备
    high = pl.col("high")
    low = pl.col("low")
    close = pl.col("close")
    
    # ATR 求和 (简化为真实波幅的累加)
    tr = pl.max_horizontal(
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    )
    atr_sum = tr.rolling_sum(window_size=window)

    # N 周期内的最高和最低
    hh = high.rolling_max(window_size=window)
    ll = low.rolling_min(window_size=window)

    # 公式: 100 * LOG10( SUM(TR, n) / (Max(High, n) - Min(Low, n)) ) / LOG10(n)
    chop_val = 100 * (atr_sum / (hh - ll)).log10() / np.log10(window)

    return df.with_columns(chop_val.alias(f"chop_{window}"))

def add_connors_rsi(df: pl.DataFrame, rsi_period: int = 3, streak_period: int = 2, rank_period: int = 100) -> pl.DataFrame:
    """
    3. Connors RSI (CRSI)
    由三部分组成：RSI(收盘价) + RSI(连续涨跌天数) + PercentRank(单日收益率)
    涉及连续天数计算，这里通过 numpy 迭代提速。
    """
    close = df["close"].to_numpy()
    length = len(close)
    
    if length < rank_period:
        return df

    # 1. 价格的 RSI(3)
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    def wilder_smooth(arr, period):
        out = np.zeros_like(arr)
        if len(arr) > 0: out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = out[i-1] + (arr[i] - out[i-1]) / period
        return out
    avg_gain = wilder_smooth(gain, rsi_period)
    avg_loss = wilder_smooth(loss, rsi_period)
    rs = avg_gain / np.where(avg_loss == 0, 1e-9, avg_loss)
    rsi_price = 100 - (100 / (1 + rs))

    # 2. 连续涨跌天数的 RSI(2)
    streak = np.zeros(length)
    for i in range(1, length):
        if close[i] > close[i-1]:
            streak[i] = max(streak[i-1] + 1, 1) if streak[i-1] >= 0 else 1
        elif close[i] < close[i-1]:
            streak[i] = min(streak[i-1] - 1, -1) if streak[i-1] <= 0 else -1
        else:
            streak[i] = 0
            
    streak_gain = np.where(streak > 0, streak, 0)
    streak_loss = np.where(streak < 0, -streak, 0)
    streak_avg_gain = wilder_smooth(streak_gain, streak_period)
    streak_avg_loss = wilder_smooth(streak_loss, streak_period)
    streak_rs = streak_avg_gain / np.where(streak_avg_loss == 0, 1e-9, streak_avg_loss)
    rsi_streak = 100 - (100 / (1 + streak_rs))

    # 3. PercentRank(单日收益率, 100)
    roc = np.zeros(length)
    roc[1:] = (close[1:] - close[:-1]) / close[:-1]
    percent_rank = np.zeros(length)
    for i in range(rank_period, length):
        window = roc[i-rank_period+1:i+1]
        percent_rank[i] = np.sum(window < roc[i]) / rank_period * 100

    # 综合 CRSI = (RSI + RSI_Streak + PercentRank) / 3
    crsi = (rsi_price + rsi_streak + percent_rank) / 3
    
    return df.with_columns([
        pl.Series("crsi", crsi)
    ])

def add_ulcer_index(df: pl.DataFrame, window: int = 14) -> pl.DataFrame:
    """
    4. Ulcer Index (溃疡指数)
    衡量下行波动风险。数值越大，代表下跌越深、持续时间越长。
    """
    # 计算 N 周期最高收盘价
    rolling_max = pl.col("close").rolling_max(window_size=window)
    
    # 计算回撤百分比：(收盘价 - 最高收盘价) / 最高收盘价 * 100
    drawdown = ((pl.col("close") - rolling_max) / rolling_max) * 100
    
    # UI 是回撤百分比的平方的平均值的平方根 (RMS)
    squared_dd = drawdown ** 2
    mean_squared_dd = squared_dd.rolling_mean(window_size=window)
    ulcer = mean_squared_dd.sqrt()

    return df.with_columns(ulcer.alias(f"ulcer_{window}"))

def add_pring_ksk(df: pl.DataFrame) -> pl.DataFrame:
    """
    5. Pring's Special K
    由短期、中期、长期 ROC 的加权移动平均合成。
    """
    close = pl.col("close")
    # 根据 Pring 的原版参数：10, 15, 20, 30, 40, 65
    # 权重分别为：1, 2, 3, 4, 1, 1
    periods = [10, 15, 20, 30, 40, 65]
    weights = [1, 2, 3, 4, 1, 1]
    
    def wma(expr: pl.Expr, window: int) -> pl.Expr:
        """计算加权移动平均 (WMA)"""
        # WMA = sum(price_i * weight_i) / sum(weight)
        # weight_i 依次为 1, 2, ..., window
        weights_arr = np.arange(1, window + 1)
        weight_sum = weights_arr.sum()
        # Polars 的 rolling_map 结合 numpy 可以做自定义 WMA，但速度较慢
        # 这里为了极速，我们采用 sum(price.shift(k) * k) 展开计算
        wma_expr = None
        for i in range(window):
            w = i + 1
            shifted = expr.shift(window - 1 - i) * w
            wma_expr = shifted if wma_expr is None else wma_expr + shifted
        return wma_expr / weight_sum

    ksk_expr = None
    for p, w in zip(periods, weights):
        # ROC 计算
        roc = ((close - close.shift(p)) / close.shift(p)) * 100
        # Pring 用 10 周期的 WMA 平滑 ROC
        smoothed_roc = wma(roc, 10) * w
        
        if ksk_expr is None:
            ksk_expr = smoothed_roc
        else:
            ksk_expr = ksk_expr + smoothed_roc

    return df.with_columns(ksk_expr.alias("pring_ksk"))

def add_pring_ksk_enhanced(
    df: pl.DataFrame, 
    k: float = 1.0, 
    use_log_returns: bool = False,
    smooth_method: str = "sma"
) -> pl.DataFrame:
    """
    Pring's Special K (Enhanced 增强版)
    
    参数:
        k: 周期压缩系数。k=1.0 为原版；k<1 压缩周期（适配上市不久的新股）。
        use_log_returns: 是否使用对数收益率计算 ROC（默认 False）。
        smooth_method: 平滑方式，"sma" 或 "ema"（默认 "sma"）。
    """
    # 1. 定义原版的 12 个核心周期、平滑周期和权重
    periods = [10, 15, 20, 30, 40, 65, 75, 100, 195, 265, 390, 530]
    smooths = [10, 10, 10, 15, 50, 65, 75, 100, 130, 130, 130, 195]
    weights = [1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4]

    close = pl.col("close")
    ksk_expr = None

    for p, s, w in zip(periods, smooths, weights):
        # 2. 应用压缩系数 k
        p_k = max(int(p * k), 2)
        s_k = max(int(s * k), 2)

        # 3. 计算 ROC (动量变化率)
        if use_log_returns:
            # 对数收益率：ln(P_t / P_t-n) * 100
            roc = (close / close.shift(p_k)).log() * 100
        else:
            # 简单收益率：(P_t - P_t-n) / P_t-n * 100
            roc = ((close - close.shift(p_k)) / close.shift(p_k)) * 100

        # 4. 平滑 ROC
        if smooth_method == "ema":
            smoothed = roc.ewm_mean(span=s_k, adjust=False)
        else:
            smoothed = roc.rolling_mean(window_size=s_k)

        # 5. 乘以权重并累加
        term = smoothed * w
        ksk_expr = term if ksk_expr is None else ksk_expr + term

    # 统一用 / 10 归一化，使数值更易读
    return df.with_columns((ksk_expr / 10).alias(f"pring_ksk_enh_k{k}"))

def add_vwap(df: pl.DataFrame, window: int = None) -> pl.DataFrame:
    """
    6. VWAP (成交量加权平均价)
    如果在日线级别，就是当天的均价；如果是分钟线，window=None 代表当天累计 VWAP。
    由于日线只有一根 K 线，这里我们计算窗口滚动 VWAP 或者累积 VWAP。
    """
    typical_price = (pl.col("high") + pl.col("low") + pl.col("close")) / 3
    vol = pl.col("vol")
    
    # 日线级别通常用累积 VWAP（或者滚动窗口 VWAP）
    # 这里给出窗口 VWAP 和当日 VWAP（日线当日 VWAP 就是 总成交额/总成交量）
    if window is None:
        # 日线当天的 VWAP = amount / (vol * 100)  (如果是手)
        # 但标准 VWAP 公式 (TP * Vol) 累加
        cum_tp_vol = (typical_price * vol).cum_sum()
        cum_vol = vol.cum_sum()
        vwap_val = cum_tp_vol / cum_vol
        name = "vwap_cum"
    else:
        rolling_tp_vol = (typical_price * vol).rolling_sum(window_size=window)
        rolling_vol = vol.rolling_sum(window_size=window)
        vwap_val = rolling_tp_vol / rolling_vol
        name = f"vwap_{window}"

    return df.with_columns(vwap_val.alias(name))

# 文档明确说明部分模块（如 order_blocks）在 LazyFrame 下会 fallback 到 eager collect()，不是纯 lazy，
# 但功能不受影响。对日线级别的数据量（几千行）完全无压力。
def add_smc(df: pl.DataFrame) -> pl.DataFrame:
    """输入需含 open/high/low/close，返回追加 SMC 列后的 DataFrame。"""
    return df.smc.add_all(
        window_size=2,
        include_liquidity=True,
    )
    
def add_ttm_squeeze(df: pl.DataFrame, bb_len: int = 20, bb_mult: float = 2.0, kc_len: int = 20, kc_mult: float = 1.5) -> pl.DataFrame:
    """TTM Squeeze (John Carter 挤压动量指标)"""
    # 1. 计算布林带
    df = df.with_columns([
        pl.col("close").rolling_mean(window_size=bb_len).alias("bb_mid"),
        pl.col("close").rolling_std(window_size=bb_len).alias("bb_std")
    ])
    df = df.with_columns([
        (pl.col("bb_mid") + bb_mult * pl.col("bb_std")).alias("bb_upper"),
        (pl.col("bb_mid") - bb_mult * pl.col("bb_std")).alias("bb_lower")
    ])
    
    # 2. 计算肯特纳通道
    prev_close = pl.col("close").shift(1)
    tr = pl.max_horizontal(
        pl.col("high") - pl.col("low"),
        (pl.col("high") - prev_close).abs(),
        (pl.col("low") - prev_close).abs()
    )
    df = df.with_columns(tr.alias("_tr"))
    
    df = df.with_columns([
        pl.col("close").ewm_mean(span=kc_len, adjust=False).alias("kc_mid"),
        pl.col("_tr").ewm_mean(span=kc_len, adjust=False).alias("kc_atr")
    ])
    df = df.with_columns([
        (pl.col("kc_mid") + kc_mult * pl.col("kc_atr")).alias("kc_upper"),
        (pl.col("kc_mid") - kc_mult * pl.col("kc_atr")).alias("kc_lower")
    ])
    
    # 3. 判断挤压
    squeeze_on = (pl.col("bb_upper") < pl.col("kc_upper")) & (pl.col("bb_lower") > pl.col("kc_lower"))
    
    # 4. 动量直方图公式（准确还原 TV 算法）
    # 动量 = 收盘价 - 20日均线与20日高低点均值的平均值
    highest_high = pl.col("high").rolling_max(window_size=bb_len)
    lowest_low = pl.col("low").rolling_min(window_size=bb_len)
    mid_line = (highest_high + lowest_low) / 2
    delta = pl.col("close") - ((mid_line + pl.col("close").rolling_mean(window_size=bb_len)) / 2)
    
    return df.with_columns([
        squeeze_on.alias("squeeze_on"),
        delta.ewm_mean(span=10, adjust=False).alias("squeeze_momentum")
    ]).drop(["_tr", "bb_mid", "bb_std", "kc_mid", "kc_atr"])
    
def add_ut_bot(df: pl.DataFrame, key: float = 1.0, atr_period: int = 10) -> pl.DataFrame:
    """
    UT Bot Alerts (QuantNomad)
    基于 ATR 和收盘价的动态止损翻转系统。
    """
    # 1. 计算 ATR
    if "atr_14" not in df.columns:
        df = add_atr(df, window=14)
    # 取需要的 ATR (默认为 10)
    atr_col = f"atr_{atr_period}"
    if atr_col not in df.columns:
        df = add_atr(df, window=atr_period)
        
    n_loss = key * pl.col(atr_col)
    
    # 由于 UT Bot 需要状态机（前一天的止损线影响今天的止损线），这里用极简逻辑平替：
    # 简化版：Stop = 收盘价 - N_Loss (多头) / + N_Loss (空头)
    # 真实信号：如果收盘价 > 前一日Stop，且前一日的Stop < 前两日Stop，则看多
    # (完整版需要迭代，这里提供向量化近似)
    close = pl.col("close")
    
    # 动态底线
    stop = close - n_loss
    stop = pl.when(close.shift(1) > stop.shift(1)).then(pl.max_horizontal(stop, stop.shift(1))).otherwise(stop)
    
    # 信号判断
    buy_signal = (close > stop) & (close.shift(1) <= stop.shift(1))
    sell_signal = (close < stop) & (close.shift(1) >= stop.shift(1))
    
    return df.with_columns([
        stop.alias("ut_stop"),
        buy_signal.alias("ut_buy"),
        sell_signal.alias("ut_sell")
    ])
    
def add_anchored_vwap(df: pl.DataFrame, anchor_date: str = None) -> pl.DataFrame:
    """
    Anchored VWAP (锚定成交量加权平均价)
    
    参数:
        df: 包含 trade_date, high, low, close, vol 的 DataFrame
        anchor_date: 锚定日期字符串 (如 "2026-01-01")。如果为 None，则默认从数据的第一天开始。
    """
    # 典型价格 (Typical Price)
    tp = (pl.col("high") + pl.col("low") + pl.col("close")) / 3
    
    # 如果指定了锚定日期，过滤掉该日期之前的数据；否则全量计算
    if anchor_date:
        # 标记锚点之后的日期，之前的设为 0 成交量，防止累加
        mask = pl.col("trade_date") >= anchor_date
        tp = pl.when(mask).then(tp).otherwise(0.0)
        vol = pl.when(mask).then(pl.col("vol")).otherwise(0.0)
    else:
        vol = pl.col("vol")
        
    cum_tp_vol = (tp * vol).cum_sum()
    cum_vol = vol.cum_sum()
    
    # 防除零错误
    avwap = pl.when(cum_vol == 0).then(None).otherwise(cum_tp_vol / cum_vol)
    
    return df.with_columns(avwap.alias("avwap"))