/** Shared chart grammar: recessive hairline chrome, solid petrol-pill tooltips, thin marks. */
import type { Tokens } from "../lib/theme";
import { escapeHtml } from "../lib/format";

export function axisStyle(t: Tokens) {
  return {
    axisLine: { show: false, lineStyle: { color: t.axis, width: 1 } },
    axisTick: { show: false },
    axisLabel: { color: t.axisInk, fontSize: 11, fontFamily: t.font, margin: 10 },
    splitLine: { show: true, lineStyle: { color: t.grid, width: 1, type: [4, 4] as number[] } },
    nameTextStyle: { color: t.ink2, fontSize: 11.5, fontFamily: t.font },
  };
}

/** Axis-tooltip pointer for bars: a soft column highlight behind the hovered band. */
export function shadowPointer(t: Tokens) {
  return { type: "shadow" as const, shadowStyle: { color: t.dark ? "rgba(255,255,255,0.05)" : "rgba(15,42,51,0.05)" } };
}

/** Axis-tooltip pointer for lines: a dashed ink crosshair. */
export function linePointer(t: Tokens) {
  return { type: "line" as const, lineStyle: { color: t.ink, width: 1, type: [4, 4] as number[], opacity: 0.55 }, z: 1 };
}

/** The pale full-length track drawn behind each bar. */
export function barTrack(t: Tokens) {
  return { showBackground: true, backgroundStyle: { color: t.surface2, borderRadius: 999 } };
}

/** A pill-shaped data label: solid fill with ink chosen for contrast against it. */
export function pillLabel(t: Tokens, fill: string, extra: Record<string, unknown> = {}) {
  return {
    show: true, color: inkOn(fill), backgroundColor: fill, borderRadius: 999, padding: [4, 9],
    fontFamily: t.font, fontSize: 11, fontWeight: 600, lineHeight: 13, ...extra,
  };
}

/** Hex colour with alpha, for translucent fills derived from series colours. */
export function withAlpha(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

/** Vertical gradient from a translucent series colour to transparent, for the area under a line. */
export function areaFade(hex: string, top = 0.24) {
  return {
    type: "linear" as const, x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [{ offset: 0, color: withAlpha(hex, top) }, { offset: 1, color: withAlpha(hex, 0) }],
  };
}

export function tooltip(t: Tokens, extra: Record<string, unknown> = {}) {
  return {
    backgroundColor: t.inverse,
    borderWidth: 0,
    padding: [10, 14],
    textStyle: { color: t.inverseInk, fontFamily: t.font, fontSize: 12.5 },
    extraCssText: `border-radius:16px;box-shadow:0 14px 32px -12px rgba(0,0,0,${t.dark ? 0.7 : 0.35});`,
    confine: true,
    ...extra,
  };
}

export function base(t: Tokens) {
  return {
    animationDuration: 450,
    animationDurationUpdate: 650,
    animationEasing: "cubicOut" as const,
    animationEasingUpdate: "cubicInOut" as const,
    textStyle: { fontFamily: t.font, color: t.ink2 },
    aria: { enabled: true },
    color: t.series,
  };
}

// ---- tooltip HTML (labels escaped: names come from data) ---------------------------------
export function ttTitle(title: string): string {
  return `<div class="tt"><div class="tt__title">${escapeHtml(title)}</div>`;
}
export function ttRow(color: string | null, label: string, value: string, shape: "line" | "dot" | "rect" = "line"): string {
  const radius = shape === "dot" ? "50%" : "2px";
  const size = shape === "line" ? "width:12px;height:3px" : "width:9px;height:9px";
  const key = color ? `<span class="tt__key" style="${size};border-radius:${radius};background:${color}"></span>` : "<span></span>";
  return `<div class="tt__row">${key}<span class="tt__label">${escapeHtml(label)}</span><span class="tt__value">${escapeHtml(value)}</span></div>`;
}
export function ttSub(text: string): string {
  return `<div class="tt__sub">${escapeHtml(text)}</div>`;
}
export const ttEnd = "</div>";

/** Emphasis: highlighted entity gets the accent, the rest recede to the de-emphasis gray. */
export function emphasisColor(t: Tokens, active: boolean): string {
  return active ? t.series[0] : t.deemph;
}

/** Nice symmetric bound for a z-score axis. */
export function symmetricBound(values: number[], pad = 0.25): number {
  const m = Math.max(1, ...values.map((v) => Math.abs(v)));
  return Math.ceil((m + pad) * 2) / 2;
}

/** White or dark ink for text set inside a coloured fill, by relative luminance. */
export function inkOn(hex: string): string {
  if (!hex.startsWith("#")) return "#ffffff";
  const h = hex.replace("#", "");
  if (h.length !== 6) return "#ffffff";
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 0.224 ? "#0f2a33" : "#ffffff"; // crossover where both inks give equal contrast
}
