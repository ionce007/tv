# src/app/main.py
import streamlit as st
import plotly.graph_objects as go
import polars as pl

from src.analysis.price_adjust import load_qfq
from src.analysis.indicators import (
    calc_all_indicators, add_ttm_squeeze, add_ut_bot, add_anchored_vwap
)

# 1. 页面极简配置
st.set_page_config(page_title="量化终端", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        /* 减少页面留白，让图表更大 */
        .block-container { padding-top: 1rem; padding-left: 0.5rem; padding-right: 0.5rem; }
        h1 { font-size: 1.2rem !important; margin-top: 0rem !important; margin-bottom: 0rem !important; }
    </style>
""", unsafe_allow_html=True)

# 左侧 85% 画图，右侧 15% 放控制面板
col_chart, col_panel = st.columns([5.5, 1])

with col_panel:
    st.markdown("### ⚙️ 参数")
    
    # 表单防闪烁
    with st.form("config_form"):
        symbol = st.text_input("股票代码", value="sh600000")
        
        # 默认值改为了 200
        limit = st.number_input("初始 K线数量", min_value=100, max_value=5000, value=200, step=50)
        
        anchor_date = st.text_input("AVWAP 锚定日期", value="", help="YYYY-MM-DD")
        
        st.markdown("---")
        st.write("**主图叠加**")
        show_sma = st.checkbox("SMA20", value=True)
        show_kama = st.checkbox("KAMA10", value=False)
        show_boll = st.checkbox("布林带", value=False)
        show_avwap = st.checkbox("锚定 VWAP", value=False) # 默认关闭，避免被红框线困扰
        
        st.markdown("---")
        st.write("**副图指标**")
        sub_indicator = st.selectbox(
            "切换副图", 
            ["成交量 (Volume)", "MACD", "KDJ", "TTM Squeeze"],
            label_visibility="collapsed"
        )
        
        submitted = st.form_submit_button("应用设置", use_container_width=True)

@st.cache_data(ttl=3600)
def load_data(sym, anchor):
    df = load_qfq(sym)
    df = calc_all_indicators(df)
    df = add_ttm_squeeze(df)
    df = add_ut_bot(df)
    anchor_val = anchor.strip() if anchor.strip() else None
    df = add_anchored_vwap(df, anchor_date=anchor_val)
    return df

with col_chart:
    st.title("📈 A股量化终端")
    
    try:
        with st.spinner("加载数据中..."):
            df_full = load_data(symbol, anchor_date)
            if df_full.is_empty():
                st.error("未找到该股票数据")
                st.stop()
                
            df = df_full.tail(limit)
            pdf = df.to_pandas()
            pdf['trade_date'] = pdf['trade_date'].astype(str)

        fig = go.Figure()

        # 颜色逻辑：上涨/平盘红，下跌白
        k_colors = ['#ff3333' if c >= o else '#ffffff' for c, o in zip(pdf['close'], pdf['open'])]
        
        # 主图 K 线
        fig.add_trace(go.Candlestick(
            x=pdf['trade_date'], open=pdf['open'], high=pdf['high'], 
            low=pdf['low'], close=pdf['close'], name="K线",
            increasing_fillcolor='#ff3333', increasing_line_color='#ff3333',
            decreasing_fillcolor='#ffffff', decreasing_line_color='#ffffff',
            yaxis="y1"
        ))

        if show_sma:
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['sma_20'], line=dict(color='orange', width=1), name="SMA20", yaxis="y1"))
        if show_kama:
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['kama_10'], line=dict(color='cyan', width=1), name="KAMA10", yaxis="y1"))
        if show_boll:
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['boll_upper'], line=dict(color='gray', width=1, dash='dot'), name="BOLL上", yaxis="y1"))
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['boll_lower'], line=dict(color='gray', width=1, dash='dot'), name="BOLL下", yaxis="y1"))
        if show_avwap:
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['avwap'], line=dict(color='magenta', width=2), name="AVWAP", yaxis="y1"))

        # 副图指标
        if sub_indicator == "成交量 (Volume)":
            fig.add_trace(go.Bar(x=pdf['trade_date'], y=pdf['vol'], marker_color=k_colors, name="成交量", yaxis="y2"))
        elif sub_indicator == "MACD":
            macd_colors = ['#ff3333' if m >= 0 else '#ffffff' for m in pdf['macd_hist']]
            fig.add_trace(go.Bar(x=pdf['trade_date'], y=pdf['macd_hist'], marker_color=macd_colors, name="MACD柱", yaxis="y2"))
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['macd_dif'], line=dict(color='orange', width=1), name="DIF", yaxis="y2"))
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['macd_dea'], line=dict(color='yellow', width=1), name="DEA", yaxis="y2"))
        elif sub_indicator == "KDJ":
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['kdj_k'], line=dict(color='white', width=1), name="K", yaxis="y2"))
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['kdj_d'], line=dict(color='yellow', width=1), name="D", yaxis="y2"))
            fig.add_trace(go.Scatter(x=pdf['trade_date'], y=pdf['kdj_j'], line=dict(color='magenta', width=1), name="J", yaxis="y2"))
        elif sub_indicator == "TTM Squeeze":
            sq_colors = ['#ff3333' if m >= 0 else '#ffffff' for m in pdf['squeeze_momentum']]
            fig.add_trace(go.Bar(x=pdf['trade_date'], y=pdf['squeeze_momentum'], marker_color=sq_colors, name="动量", yaxis="y2"))
            sq_on = pdf[pdf['squeeze_on']]
            fig.add_trace(go.Scatter(x=sq_on['trade_date'], y=[0]*len(sq_on), mode='markers', marker=dict(color='#ff3333', symbol='circle', size=6), name="挤压状态", yaxis="y2"))

        # ================= 布局调整 =================
        fig.update_layout(
            height=850, 
            margin=dict(l=10, r=10, t=30, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
            hovermode="x unified",
            spikedistance=-1,
            dragmode="pan",
            # Y轴空间分配：主图 0.35~1.0，副图 0.0~0.25 (留出 10% 间隙避免覆盖)
            yaxis=dict(domain=[0.35, 1.0], showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
            yaxis2=dict(domain=[0.0, 0.25], anchor="x", side="right", showgrid=False)
        )

        # 开启全局十字线
        fig.update_xaxes(
            showspikes=True, spikecolor="gray", spikethickness=1, spikedash="dot",
            spikemode="across", spikesnap="cursor",
            rangeslider_visible=False, # 彻底关闭滑块，消除重影
            type='category',
            nticks=12,                 # 底部日期刻度显示数量
            showticklabels=True,
            showgrid=False
        )
        fig.update_yaxes(
            showspikes=True, spikecolor="gray", spikethickness=1, spikedash="dot"
        )

        # 调整底部的滑动条（Rangeslider）外观，使其更窄更精致
        fig.update_layout(
            xaxis_rangeslider=dict(
                visible=True,
                thickness=0.05, # 滑块高度
                bgcolor="rgba(0,0,0,0)"
            )
        )

        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': True})

    except Exception as e:
        st.error(f"加载失败: {e}")