// src/App.tsx
import { useState, useEffect } from "react";
import KLineChart from "./components/KLineChart";
import { themes } from "./themes";
import type { ThemeType } from "./themes";

const formatSymbol = (input: string): string => {
  const code = input.trim().toLowerCase();
  if (code.startsWith("sh") || code.startsWith("sz") || code.startsWith("bj"))
    return code;
  if (/^\d{6}$/.test(code)) {
    if (code.startsWith("6")) return `sh${code}`;
    if (code.startsWith("0") || code.startsWith("3")) return `sz${code}`;
    if (code.startsWith("4") || code.startsWith("8") || code.startsWith("9"))
      return `bj${code}`;
  }
  return code;
};

type SubIndicatorType = "volume" | "macd" | "kdj" | "cvd" | "squeeze";

function App() {
  const [symbol, setSymbol] = useState("sh600000");
  const [inputSymbol, setInputSymbol] = useState("600000");
  const [theme, setTheme] = useState<ThemeType>("dark");
  const [subIndicator, setSubIndicator] = useState<SubIndicatorType>("volume");
  const [overlays, setOverlays] = useState({
    sma20: true,
    sma60: false,
    kama10: false,
    boll: false,
    avwap: false,
  });
  const [anchorDate, setAnchorDate] = useState<string>("");
  // 临时测试股票池
  const [symbolPool] = useState<string[]>([
    "sh600000",
    "sz000001",
    "sh600519",
    "sz000002",
    "sh601318",
  ]);

  const handleLoad = () => {
    setSymbol(formatSymbol(inputSymbol));
    setInputSymbol(formatSymbol(inputSymbol));
  };

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");
  const toggleOverlay = (key: keyof typeof overlays) =>
    setOverlays((prev) => ({ ...prev, [key]: !prev[key] }));

  // 监听 PgUp / PgDn 切股票
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === "PageDown" || e.key === "PageUp") {
        e.preventDefault();
        const currentIndex = symbolPool.indexOf(symbol);
        if (currentIndex === -1) return;

        let nextIndex = currentIndex;
        if (e.key === "PageDown")
          nextIndex =
            currentIndex < symbolPool.length - 1 ? currentIndex + 1 : 0;
        else
          nextIndex =
            currentIndex > 0 ? currentIndex - 1 : symbolPool.length - 1;

        setSymbol(symbolPool[nextIndex]);
        setInputSymbol(symbolPool[nextIndex].replace(/[a-zA-Z]/g, ""));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [symbol, symbolPool]);

  const colors = themes[theme];

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        width: "100vw",
        backgroundColor: colors.background,
        color: colors.textColor,
        fontFamily: "sans-serif",
      }}
    >
      <div
        style={{
          width: "50px",
          borderRight: `1px solid ${colors.headerBorder}`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: "15px",
          gap: "20px",
          backgroundColor: colors.headerBg,
        }}
      >
        {(
          ["volume", "macd", "kdj", "cvd", "squeeze"] as SubIndicatorType[]
        ).map((type) => (
          <div
            key={type}
            onClick={() => setSubIndicator(type)}
            style={{
              cursor: "pointer",
              opacity: subIndicator === type ? 1 : 0.4,
              color: subIndicator === type ? "#2962ff" : colors.textColor,
            }}
          >
            <span style={{ fontSize: "10px", fontWeight: "bold" }}>
              {type === "volume"
                ? "VOL"
                : type === "squeeze"
                  ? "SQZ"
                  : type.toUpperCase()}
            </span>
          </div>
        ))}
      </div>

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "8px 15px",
            borderBottom: `1px solid ${colors.headerBorder}`,
            display: "flex",
            alignItems: "center",
            gap: "15px",
            backgroundColor: colors.headerBg,
          }}
        >
          <h2 style={{ margin: 0, fontSize: "16px" }}>📈 量化终端</h2>
          <input
            type="text"
            value={inputSymbol}
            onChange={(e) => setInputSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLoad()}
            style={{
              padding: "4px 8px",
              background: colors.inputBg,
              border: `1px solid ${colors.inputBorder}`,
              color: colors.textColor,
              borderRadius: "4px",
              width: "120px",
            }}
          />
          <button
            onClick={handleLoad}
            style={{
              padding: "4px 12px",
              background: "#2962ff",
              border: "none",
              color: "#fff",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            加载
          </button>

          <div
            style={{
              display: "flex",
              gap: "12px",
              fontSize: "12px",
              marginLeft: "20px",
            }}
          >
            {Object.entries(overlays).map(([key, val]) => (
              <label
                key={key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  cursor: "pointer",
                  opacity: val ? 1 : 0.6,
                }}
              >
                <input
                  type="checkbox"
                  checked={val}
                  onChange={() => toggleOverlay(key as keyof typeof overlays)}
                />
                {key.toUpperCase()}
              </label>
            ))}
            {/* 原来 AWWAP 复选框后面加这个 */}
            {overlays.avwap && (
              <input
                type="date"
                value={anchorDate}
                onChange={(e) => setAnchorDate(e.target.value)}
                style={{
                  padding: "2px 4px",
                  background: colors.inputBg,
                  border: `1px solid ${colors.inputBorder}`,
                  color: colors.textColor,
                  borderRadius: "4px",
                  fontSize: "12px",
                }}
                title="选择 AVWAP 锚定日期"
              />
            )}
          </div>

          <button
            onClick={toggleTheme}
            style={{
              marginLeft: "auto",
              padding: "4px 12px",
              background: theme === "dark" ? "#363a45" : "#e0e0e0",
              border: "none",
              color: colors.textColor,
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            {theme === "dark" ? "☀️ 浅色" : "🌙 深色"}
          </button>
        </div>

        <div style={{ flex: 1, position: "relative" }}>
          <KLineChart symbol={symbol} theme={theme} subIndicator={subIndicator} overlays={overlays} anchorDate={anchorDate} />
        </div>
      </div>
    </div>
  );
}

export default App;
