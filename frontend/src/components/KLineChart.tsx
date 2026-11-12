// src/components/KLineChart.tsx
import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createTextWatermark,
} from "lightweight-charts";
import type {
  IChartApi,
  ISeriesApi,
  LogicalRange,
  MouseEventParams,
} from "lightweight-charts";
import { themes } from "../themes";
import type { ThemeType } from "../themes";

interface Props {
  symbol: string;
  theme: ThemeType;
  subIndicator: "volume" | "macd" | "kdj" | "cvd" | "squeeze";
  overlays: {
    sma20: boolean;
    sma60: boolean;
    kama10: boolean;
    boll: boolean;
    avwap: boolean;
  };
  anchorDate?: string; // 新增
}

export default function KLineChart({
  symbol,
  theme,
  subIndicator,
  overlays,
  anchorDate,
}: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  // Series 引用
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const sma20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const sma60SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const kama10SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bollUpperRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bollLowerRef = useRef<ISeriesApi<"Line"> | null>(null);
  const avwapSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const macdHistSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const macdDifSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdDeaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const kdjKSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const kdjDSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const kdjJSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const cvdSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const squeezeMomentumRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const squeezeOnRef = useRef<ISeriesApi<"Line"> | null>(null);

  // 水印引用
  const mainLegendRef = useRef<any>(null);
  const subLegendRef = useRef<any>(null);

  const [loading, setLoading] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const [hoverData, setHoverData] = useState<any>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [chartWidth, setChartWidth] = useState(1000);

  const dataRef = useRef<any[]>([]);
  const hasMoreRef = useRef(true);
  const firstDateRef = useRef<string | null>(null);
  const isFetchingRef = useRef(false);
  const loadDebounceRef = useRef<any>(null);

  // 穿透闭包的状态
  const symbolRef = useRef(symbol);
  const themeRef = useRef(theme);
  const overlaysRef = useRef(overlays);
  const subIndicatorRef = useRef(subIndicator);

  useEffect(() => {
    symbolRef.current = symbol;
  }, [symbol]);
  useEffect(() => {
    themeRef.current = theme;
  }, [theme]);
  useEffect(() => {
    overlaysRef.current = overlays;
  }, [overlays]);
  useEffect(() => {
    subIndicatorRef.current = subIndicator;
  }, [subIndicator]);

  const loadHistoryRef = useRef<() => void>(() => {});

  // 核心：生成文字并写入到 Pane 左上角的水印
  const updateLegends = (hoverItem: any) => {
    if (!chartRef.current || !mainLegendRef.current || !subLegendRef.current)
      return;

    const lastData =
      dataRef.current.length > 0
        ? dataRef.current[dataRef.current.length - 1]
        : null;
    const d = hoverItem || lastData;
    if (!d) return;

    const colors = themes[themeRef.current];
    const currentOverlays = overlaysRef.current;
    const currentSub = subIndicatorRef.current;

    // 主图文本
    let mainText = "";
    if (currentOverlays.sma20)
      mainText += `SMA20: ${d.sma_20?.toFixed(2) || "-"}   `;
    if (currentOverlays.sma60)
      mainText += `SMA60: ${d.sma_60?.toFixed(2) || "-"}   `;
    if (currentOverlays.kama10)
      mainText += `KAMA10: ${d.kama_10?.toFixed(2) || "-"}   `;
    if (currentOverlays.boll)
      mainText += `BOLL: ${d.boll_upper?.toFixed(2) || "-"} / ${d.boll_lower?.toFixed(2) || "-"}   `;
    if (currentOverlays.avwap)
      mainText += `AVWAP: ${d.avwap?.toFixed(2) || "-"}   `;

    mainLegendRef.current.applyOptions({
      lines: [{ text: mainText.trim(), color: colors.textColor, fontSize: 12 }],
    });

    // 副图文本
    let subText = "";
    if (currentSub === "volume") {
      subText = `VOL: ${d.vol ? (d.vol / 100).toFixed(0) + "手" : "-"}`;
    } else if (currentSub === "macd") {
      subText = `MACD: ${d.macd_hist?.toFixed(2) || "-"}   DIF: ${d.macd_dif?.toFixed(2) || "-"}   DEA: ${d.macd_dea?.toFixed(2) || "-"}`;
    } else if (currentSub === "kdj") {
      subText = `K: ${d.kdj_k?.toFixed(2) || "-"}   D: ${d.kdj_d?.toFixed(2) || "-"}   J: ${d.kdj_j?.toFixed(2) || "-"}`;
    } else if (currentSub === "cvd") {
      subText = `CVD: ${d.cvd?.toLocaleString() || "-"}`;
    } else if (currentSub === "squeeze") {
      const sqzVal = d.squeeze_momentum ?? d.squeeze ?? 0;
      // 强制保留 4 位小数，防止被格式化成 0
      subText = `SQZ: ${Number(sqzVal).toFixed(4)}   ${d.squeeze_on ? "【挤压中】" : ""}`;
    }

    subLegendRef.current.applyOptions({
      lines: [{ text: subText.trim(), color: colors.textColor, fontSize: 12 }],
    });
  };

  // 1. 初始化图表
  useEffect(() => {
    if (!chartContainerRef.current) return;
    const chart = createChart(chartContainerRef.current, {
      autoSize: true,
      crosshair: { mode: 0 },
      timeScale: { timeVisible: true, secondsVisible: false },
      layout: { fontSize: 12 },
    });

    const resizeObserver = new ResizeObserver((entries) => {
      if (entries[0]) setChartWidth(entries[0].contentRect.width);
    });
    resizeObserver.observe(chartContainerRef.current);

    candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
      borderVisible: false,
      lastValueVisible: true,
    });

    sma20SeriesRef.current = chart.addSeries(LineSeries, {
      color: "orange",
      lineWidth: 1,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    sma60SeriesRef.current = chart.addSeries(LineSeries, {
      color: "cyan",
      lineWidth: 1,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    kama10SeriesRef.current = chart.addSeries(LineSeries, {
      color: "#ff9800",
      lineWidth: 1,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    bollUpperRef.current = chart.addSeries(LineSeries, {
      color: "gray",
      lineWidth: 1,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    bollLowerRef.current = chart.addSeries(LineSeries, {
      color: "gray",
      lineWidth: 1,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    avwapSeriesRef.current = chart.addSeries(LineSeries, {
      color: "magenta",
      lineWidth: 2,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    volumeSeriesRef.current = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: {
          type: "custom",
          formatter: (price) => (price / 100).toFixed(0),
        },
        priceScaleId: "vol_scale",
        lastValueVisible: true,
        priceLineVisible: false,
      },
      1,
    );

    macdHistSeriesRef.current = chart.addSeries(
      HistogramSeries,
      {
        priceScaleId: "macd_scale",
        lastValueVisible: false,
        priceLineVisible: false,
      },
      1,
    );
    macdDifSeriesRef.current = chart.addSeries(
      LineSeries,
      {
        color: "orange",
        lineWidth: 1,
        priceScaleId: "macd_scale",
        lastValueVisible: false,
        priceLineVisible: false,
      },
      1,
    );
    macdDeaSeriesRef.current = chart.addSeries(
      LineSeries,
      {
        color: "yellow",
        lineWidth: 1,
        priceScaleId: "macd_scale",
        lastValueVisible: false,
        priceLineVisible: false,
      },
      1,
    );

    kdjKSeriesRef.current = chart.addSeries(
      LineSeries,
      {
        color: "white",
        lineWidth: 1,
        priceScaleId: "kdj_scale",
        lastValueVisible: false,
        priceLineVisible: false,
      },
      1,
    );
    kdjDSeriesRef.current = chart.addSeries(
      LineSeries,
      {
        color: "yellow",
        lineWidth: 1,
        priceScaleId: "kdj_scale",
        lastValueVisible: false,
        priceLineVisible: false,
      },
      1,
    );
    kdjJSeriesRef.current = chart.addSeries(
      LineSeries,
      {
        color: "magenta",
        lineWidth: 1,
        priceScaleId: "kdj_scale",
        lastValueVisible: false,
        priceLineVisible: false,
      },
      1,
    );

    cvdSeriesRef.current = chart.addSeries(
      LineSeries,
      {
        color: "#2962ff",
        lineWidth: 2,
        priceScaleId: "cvd_scale",
        lastValueVisible: false,
        priceLineVisible: false,
      },
      1,
    );

    squeezeMomentumRef.current = chart.addSeries(
      HistogramSeries,
      {
        priceScaleId: "sqz_scale",
        lastValueVisible: false,
        priceLineVisible: false,
      },
      1,
    );
    squeezeOnRef.current = chart.addSeries(
      LineSeries,
      {
        color: "yellow",
        lineWidth: 2,
        lineStyle: 1,
        priceScaleId: "sqz_scale",
        lastValueVisible: false,
        priceLineVisible: false,
      },
      1,
    );

    chart.panes()[0].setHeight(400);
    chart.panes()[1].setHeight(150);
    chartRef.current = chart;

    // 初始化原生水印（绑定 Pane，永远贴合左上角）
    mainLegendRef.current = createTextWatermark(chart.panes()[0], {
      horzAlign: "left",
      vertAlign: "top",
      lines: [{ text: "", color: "#fff", fontSize: 12 }],
    });
    subLegendRef.current = createTextWatermark(chart.panes()[1], {
      horzAlign: "left",
      vertAlign: "top",
      lines: [{ text: "", color: "#fff", fontSize: 12 }],
    });

    // 十字光标
    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      if (!param.point || !param.time) {
        setHoverData(null);
        updateLegends(null);
        return;
      }

      setMousePos({ x: param.point.x, y: param.point.y });
      const dateStr = String(param.time).substring(0, 10);
      const idx = dataRef.current.findIndex(
        (d) => String(d.trade_date).substring(0, 10) === dateStr,
      );

      if (idx !== -1) {
        const d = dataRef.current[idx];
        const prevClose = idx > 0 ? dataRef.current[idx - 1].close : d.open;

        setHoverData({
          ...d,
          prevClose,
          amplitude: ((d.high - d.low) / prevClose) * 100,
        });

        updateLegends(d);
      }
    });

    // 懒加载
    chart
      .timeScale()
      .subscribeVisibleLogicalRangeChange((range: LogicalRange | null) => {
        if (
          !range ||
          isFetchingRef.current ||
          !hasMoreRef.current ||
          dataRef.current.length === 0
        )
          return;
        if (range.from < 5) {
          if (loadDebounceRef.current) clearTimeout(loadDebounceRef.current);
          loadDebounceRef.current = setTimeout(
            () => loadHistoryRef.current(),
            200,
          );
        }
      });

    return () => {
      chart.remove();
      resizeObserver.disconnect();
      if (loadDebounceRef.current) clearTimeout(loadDebounceRef.current);
    };
  }, []);

  // 在 KLineChart 组件内部的初始化 useEffect 之后，再增加一个 useEffect 处理键盘事件
  // 图表内部的快捷键：左右平移，上下缩放
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      const chart = chartRef.current;
      if (!chart) return;

      const timeScale = chart.timeScale();
      
      // 1. 左右箭头平移
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        const visibleRange = timeScale.getVisibleLogicalRange();
        if (visibleRange) {
          const shift = e.key === 'ArrowLeft' ? -2 : 2;
          timeScale.setVisibleLogicalRange({
            from: visibleRange.from + shift,
            to: visibleRange.to + shift
          });
        }
      }
      
      // 2. 上下箭头缩放
      if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault();
        const currentBarSpacing = timeScale.options().barSpacing;
        let newSpacing = currentBarSpacing;
        if (e.key === 'ArrowUp') newSpacing = currentBarSpacing * 1.1; // 放大
        if (e.key === 'ArrowDown') newSpacing = currentBarSpacing * 0.9; // 缩小
        timeScale.applyOptions({ barSpacing: Math.max(1, newSpacing) });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // 2. 监听配置变化，刷新图例
  useEffect(() => {
    if (dataRef.current.length > 0) {
      updateLegends(dataRef.current[dataRef.current.length - 1]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overlays, subIndicator]);

  // 3. 副图切换逻辑
  useEffect(() => {
    if (!volumeSeriesRef.current) return;

    volumeSeriesRef.current.applyOptions({ visible: false });
    macdHistSeriesRef.current?.applyOptions({ visible: false });
    macdDifSeriesRef.current?.applyOptions({ visible: false });
    macdDeaSeriesRef.current?.applyOptions({ visible: false });
    kdjKSeriesRef.current?.applyOptions({ visible: false });
    kdjDSeriesRef.current?.applyOptions({ visible: false });
    kdjJSeriesRef.current?.applyOptions({ visible: false });
    cvdSeriesRef.current?.applyOptions({ visible: false });
    squeezeMomentumRef.current?.applyOptions({ visible: false });
    squeezeOnRef.current?.applyOptions({ visible: false });

    if (subIndicator === "volume") {
      volumeSeriesRef.current.applyOptions({
        visible: true,
        lastValueVisible: true,
      });
      volumeSeriesRef.current.priceScale().applyOptions({ autoScale: true });
    } else if (subIndicator === "macd") {
      macdHistSeriesRef.current!.applyOptions({
        visible: true,
        lastValueVisible: true,
      });
      macdDifSeriesRef.current!.applyOptions({ visible: true });
      macdDeaSeriesRef.current!.applyOptions({ visible: true });
      macdHistSeriesRef.current!.priceScale().applyOptions({ autoScale: true });
    } else if (subIndicator === "kdj") {
      kdjKSeriesRef.current!.applyOptions({
        visible: true,
        lastValueVisible: true,
      });
      kdjDSeriesRef.current!.applyOptions({ visible: true });
      kdjJSeriesRef.current!.applyOptions({ visible: true });
      kdjKSeriesRef.current!.priceScale().applyOptions({ autoScale: true });
    } else if (subIndicator === "cvd") {
      cvdSeriesRef.current!.applyOptions({
        visible: true,
        lastValueVisible: true,
      });
      cvdSeriesRef.current!.priceScale().applyOptions({ autoScale: true });
    } else if (subIndicator === "squeeze") {
      squeezeMomentumRef.current!.applyOptions({
        visible: true,
        lastValueVisible: true,
      });
      squeezeOnRef.current!.applyOptions({ visible: true });
      squeezeMomentumRef
        .current!.priceScale()
        .applyOptions({ autoScale: true });
    }
  }, [subIndicator]);

  // 4. 主图开关逻辑
  useEffect(() => {
    sma20SeriesRef.current?.applyOptions({ visible: overlays.sma20 });
    sma60SeriesRef.current?.applyOptions({ visible: overlays.sma60 });
    kama10SeriesRef.current?.applyOptions({ visible: overlays.kama10 });
    bollUpperRef.current?.applyOptions({ visible: overlays.boll });
    bollLowerRef.current?.applyOptions({ visible: overlays.boll });
    avwapSeriesRef.current?.applyOptions({ visible: overlays.avwap });
  }, [overlays]);

  // 5. 渲染数据
  const updateAllSeries = (data: any[]) => {
    if (!candleSeriesRef.current) return;
    const colors = themes[themeRef.current];
    const fd = (d: any) => String(d).substring(0, 10);

    // 终极安全防线：不管是 null, undefined 还是 NaN，统统变成 0
    const num = (v: any) => {
      if (v === null || v === undefined || isNaN(v) || !Number.isFinite(v))
        return 0;
      return Number(v);
    };

    // 1. 渲染 K 线 (防弹处理)
    candleSeriesRef.current.setData(
      data.map((i) => ({
        time: fd(i.trade_date),
        open: num(i.open),
        high: num(i.high),
        low: num(i.low),
        close: num(i.close),
      })),
    );

    // 2. 渲染主图指标
    sma20SeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.sma_20) })),
    );
    sma60SeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.sma_60) })),
    );
    kama10SeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.kama_10) })),
    );
    bollUpperRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.boll_upper) })),
    );
    bollLowerRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.boll_lower) })),
    );
    avwapSeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.avwap) })),
    );

    // 3. 渲染副图指标
    volumeSeriesRef.current!.setData(
      data.map((i) => ({
        time: fd(i.trade_date),
        value: num(i.vol),
        color: i.close >= i.open ? colors.upColor : colors.downColor,
      })),
    );

    macdHistSeriesRef.current!.setData(
      data.map((i) => ({
        time: fd(i.trade_date),
        value: num(i.macd_hist),
        color: num(i.macd_hist) >= 0 ? colors.upColor : colors.downColor,
      })),
    );
    macdDifSeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.macd_dif) })),
    );
    macdDeaSeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.macd_dea) })),
    );

    kdjKSeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.kdj_k) })),
    );
    kdjDSeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.kdj_d) })),
    );
    kdjJSeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.kdj_j) })),
    );

    cvdSeriesRef.current!.setData(
      data.map((i) => ({ time: fd(i.trade_date), value: num(i.cvd) })),
    );

    // 4. 渲染 SQZ (重点修复)
    // 动量柱状图
    squeezeMomentumRef.current!.setData(
      data.map((i) => ({
        time: fd(i.trade_date),
        value: num(i.squeeze_momentum ?? i.squeeze),
        color: i.squeeze_on
          ? "#ffeb3b"
          : num(i.squeeze_momentum ?? i.squeeze) >= 0
            ? colors.upColor
            : colors.downColor,
      })),
    );

    // 挤压状态零轴线 (这里原来写的是 i.squeeze_on ? 0 : null，null 会导致报错)
    squeezeOnRef.current!.setData(
      data
        .map((i) => ({
          time: fd(i.trade_date),
          value: i.squeeze_on ? 0 : NaN, // 如果不用 null，给 NaN 图表会自动断开，不报错
        }))
        .filter((item) => !isNaN(item.value)),
    ); // 过滤掉 NaN，只画挤压状态的点
  };

  const loadHistoryData = async () => {
    if (isFetchingRef.current || !hasMoreRef.current || !firstDateRef.current)
      return;
    isFetchingRef.current = true;
    setLoadingHistory(true);
    try {
      const url = `${import.meta.env.VITE_API_URL}/kline?symbol=${symbol}&limit=300&before_date=${firstDateRef.current}${anchorDate ? `&anchor_date=${anchorDate}` : ''}`;
      const res = await fetch(url);
      const resData = await res.json();
      if (resData.code !== 200 || resData.data.length === 0) {
        hasMoreRef.current = false;
        return;
      }
      dataRef.current = [...resData.data, ...dataRef.current];
      firstDateRef.current = String(resData.data[0].trade_date).substring(
        0,
        10,
      );
      updateAllSeries(dataRef.current);
    } finally {
      isFetchingRef.current = false;
      setLoadingHistory(false);
    }
  };
  loadHistoryRef.current = loadHistoryData;

  useEffect(() => {
    setLoading(true);
    dataRef.current = [];
    firstDateRef.current = null;
    hasMoreRef.current = true;
    isFetchingRef.current = false;

    fetch(`${import.meta.env.VITE_API_URL}/kline?symbol=${symbol}&limit=300${anchorDate ? `&anchor_date=${anchorDate}` : ''}`)
      .then((res) => res.json())
      .then((res) => {
        if (res.code !== 200) throw new Error(res.msg);
        dataRef.current = res.data;
        if (res.data.length > 0) {
          firstDateRef.current = String(res.data[0].trade_date).substring(
            0,
            10,
          );
        }
        updateAllSeries(dataRef.current);
        chartRef.current?.timeScale().fitContent();
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, [symbol, anchorDate]);

  useEffect(() => {
    if (!chartRef.current || !candleSeriesRef.current) return;
    const colors = themes[theme];
    chartRef.current.applyOptions({
      layout: {
        background: { type: ColorType.Solid, color: colors.background },
        textColor: colors.textColor,
      },
      grid: {
        vertLines: { color: colors.gridLines },
        horzLines: { color: colors.gridLines },
      },
    });
    candleSeriesRef.current.applyOptions({
      upColor: colors.upColor,
      downColor: colors.downColor,
      wickUpColor: colors.upColor,
      wickDownColor: colors.downColor,
    });

    // 更新水印颜色
    if (mainLegendRef.current) {
      mainLegendRef.current.applyOptions({
        lines: [{ color: colors.textColor, fontSize: 12 }],
      });
    }
    if (subLegendRef.current) {
      subLegendRef.current.applyOptions({
        lines: [{ color: colors.textColor, fontSize: 12 }],
      });
    }

    if (dataRef.current.length > 0) updateAllSeries(dataRef.current);
  }, [theme]);

  const formatNum = (num: number | undefined | null) =>
    num === undefined || num === null || isNaN(num) ? "-" : num.toFixed(2);
  const renderPct = (pct: number) => {
    const color = pct >= 0 ? themes[theme].upColor : themes[theme].downColor;
    return (
      <span style={{ color, marginLeft: "4px", fontSize: "11px" }}>
        ({pct >= 0 ? "+" : ""}
        {pct.toFixed(2)}%)
      </span>
    );
  };

  const tooltipWidth = 220;
  const isRightSide = mousePos.x > chartWidth - tooltipWidth - 30;
  const tooltipLeft = isRightSide
    ? mousePos.x - tooltipWidth - 15
    : mousePos.x + 15;

  return (
    <div
      ref={containerRef}
      style={{ position: "relative", width: "100%", height: "100%" }}
    >
      {loading && (
        <div
          style={{
            position: "absolute",
            zIndex: 10,
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            color: "#2962ff",
          }}
        >
          加载中...
        </div>
      )}
      {loadingHistory && (
        <div
          style={{
            position: "absolute",
            zIndex: 10,
            top: "10px",
            left: "10px",
            background: "rgba(41, 98, 255, 0.8)",
            color: "#fff",
            padding: "4px 8px",
            borderRadius: "4px",
            fontSize: "12px",
          }}
        >
          加载历史...
        </div>
      )}

      {/* 鼠标跟随 Tooltip (仅 OHLC) */}
      {hoverData && (
        <div
          style={{
            position: "absolute",
            top: mousePos.y + 15,
            left: tooltipLeft,
            zIndex: 20,
            width: `${tooltipWidth}px`,
            backgroundColor: themes[theme].headerBg,
            border: `1px solid ${themes[theme].headerBorder}`,
            borderRadius: "6px",
            padding: "8px 12px",
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
            pointerEvents: "none",
            fontSize: "12px",
            color: themes[theme].textColor,
            display: "flex",
            flexDirection: "column",
            gap: "6px",
          }}
        >
          <div
            style={{
              fontWeight: "bold",
              borderBottom: `1px solid ${themes[theme].headerBorder}`,
              paddingBottom: "4px",
              marginBottom: "2px",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>{hoverData.trade_date}</span>
            <span
              style={{
                color:
                  hoverData.close >= hoverData.prevClose
                    ? themes[theme].upColor
                    : themes[theme].downColor,
              }}
            >
              {formatNum(hoverData.close)}
            </span>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "4px 10px",
            }}
          >
            <span>
              开: {formatNum(hoverData.open)}{" "}
              {renderPct(
                ((hoverData.open - hoverData.prevClose) / hoverData.prevClose) *
                  100,
              )}
            </span>
            <span>
              高: {formatNum(hoverData.high)}{" "}
              {renderPct(
                ((hoverData.high - hoverData.prevClose) / hoverData.prevClose) *
                  100,
              )}
            </span>
            <span>
              低: {formatNum(hoverData.low)}{" "}
              {renderPct(
                ((hoverData.low - hoverData.prevClose) / hoverData.prevClose) *
                  100,
              )}
            </span>
            <span>
              收: {formatNum(hoverData.close)}{" "}
              {renderPct(
                ((hoverData.close - hoverData.prevClose) /
                  hoverData.prevClose) *
                  100,
              )}
            </span>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "4px 10px",
              borderTop: `1px solid ${themes[theme].headerBorder}`,
              paddingTop: "4px",
            }}
          >
            <span>振幅: {formatNum(hoverData.amplitude)}%</span>
            <span>换手: {formatNum(hoverData.turnover_rate)}%</span>
            <span>
              量:{" "}
              {hoverData.vol
                ? (hoverData.vol / 100).toLocaleString() + "手"
                : "0"}
            </span>
          </div>
        </div>
      )}

      <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}
