import { useEffect, useState } from "react";

const THEME_EVENT = "epoch-theme";

export interface ChartColors {
  text: string;
  muted: string;
  line: string;
  gain: string;
  loss: string;
  accent: string;
}

export function readChartColors(): ChartColors {
  const css = getComputedStyle(document.documentElement);
  const get = (name: string) => css.getPropertyValue(name).trim();
  return {
    text: get("--text"),
    muted: get("--muted"),
    line: get("--line"),
    gain: get("--gain"),
    loss: get("--loss"),
    accent: get("--accent"),
  };
}

export function toggleTheme() {
  const root = document.documentElement;
  const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
  try {
    localStorage.setItem("epoch.theme", root.dataset.theme);
  } catch {
    /* storage unavailable */
  }
  window.dispatchEvent(new Event(THEME_EVENT));
}

/** Returns the current chart colors and updates when the theme changes. */
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState(readChartColors);
  useEffect(() => {
    const update = () => setColors(readChartColors());
    const media = matchMedia("(prefers-color-scheme: dark)");
    window.addEventListener(THEME_EVENT, update);
    media.addEventListener("change", update);
    return () => {
      window.removeEventListener(THEME_EVENT, update);
      media.removeEventListener("change", update);
    };
  }, []);
  return colors;
}
