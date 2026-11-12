// src/themes.ts
export const themes = {
  dark: {
    background: "#131722",
    textColor: "#d1d4dc",
    gridLines: "rgba(42, 46, 57, 0.5)",
    borderColor: "rgba(197, 203, 206, 0.8)",
    upColor: "#ef5350", // 红
    downColor: "#ffffff", // 白
    volumeColor: "#ef5350", // 默认主色
    headerBg: "#1e222d",
    headerBorder: "#2a2e39",
    inputBg: "#1e222d",
    inputBorder: "#363a45",
  },
  light: {
    background: "#ffffff",
    textColor: "#333333",
    gridLines: "rgba(200, 200, 200, 0.3)",
    borderColor: "rgba(0, 0, 0, 0.2)",
    upColor: "#ef5350", // 依然红涨
    downColor: "#26a69a", // 浅色下用绿跌更容易看清
    volumeColor: "#26a69a",
    headerBg: "#f5f5f5",
    headerBorder: "#e0e0e0",
    inputBg: "#ffffff",
    inputBorder: "#cccccc",
  },
};

export type ThemeType = "dark" | "light";
