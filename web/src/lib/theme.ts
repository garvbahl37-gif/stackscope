import { useEffect, useState, useSyncExternalStore } from "react";

/** Chart palette resolved from CSS custom properties, so charts always match the active theme. */
export type Tokens = {
  dark: boolean;
  surface: string; surface2: string; plane: string;
  ink: string; ink2: string; ink3: string; line: string;
  grid: string; axis: string; axisInk: string; deemph: string; brand: string;
  series: string[]; seq: string[];
  div: { neg2: string; neg1: string; mid: string; pos1: string; pos2: string };
  status: { good: string; warning: string; serious: string; critical: string };
  font: string;
};

function read(): Tokens {
  const s = getComputedStyle(document.documentElement);
  const v = (name: string) => s.getPropertyValue(name).trim();
  return {
    dark: s.getPropertyValue("color-scheme").trim() === "dark",
    surface: v("--surface"), surface2: v("--surface-2"), plane: v("--plane"),
    ink: v("--ink"), ink2: v("--ink-2"), ink3: v("--ink-3"), line: v("--line"),
    grid: v("--grid"), axis: v("--axis"), axisInk: v("--axis-ink"), deemph: v("--deemph"), brand: v("--brand"),
    series: ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s7", "--s8"].map(v),
    seq: ["--q1", "--q2", "--q3", "--q4", "--q5", "--q6", "--q7"].map(v),
    div: { neg2: v("--d-neg-2"), neg1: v("--d-neg-1"), mid: v("--d-mid"), pos1: v("--d-pos-1"), pos2: v("--d-pos-2") },
    status: { good: v("--good"), warning: v("--warning"), serious: v("--serious"), critical: v("--critical") },
    font: v("--font") || "system-ui, sans-serif",
  };
}

// --- theme preference store (light | dark | system) ---------------------------------------
type Pref = "light" | "dark" | "system";
const KEY = "stackscope-theme";
const listeners = new Set<() => void>();

function getPref(): Pref {
  try {
    const saved = localStorage.getItem(KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

export function setThemePref(pref: Pref): void {
  try {
    if (pref === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, pref);
  } catch {
    /* storage unavailable: still apply for this session */
  }
  if (pref === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = pref;
  listeners.forEach((l) => l());
}

export function useThemePref(): Pref {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    getPref,
    () => "system",
  );
}

/** Resolved chart tokens; re-reads when the theme preference or OS scheme changes. */
export function useTokens(): Tokens {
  const pref = useThemePref();
  const [tokens, setTokens] = useState<Tokens>(read);
  useEffect(() => {
    setTokens(read());
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setTokens(read());
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [pref]);
  return tokens;
}
