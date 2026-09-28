/** Shared chart grammar: recessive hairline chrome, value-led tooltips, thin marks. */
import type { Tokens } from "../lib/theme";
import { escapeHtml } from "../lib/format";

export function axisStyle(t: Tokens) {
  return {
    axisLine: { show: true, lineStyle: { color: t.axis, width: 1 } },
    axisTick: { show: false },
    axisLabel: { color: t.axisInk, fontSize: 11, fontFamily: t.font },
    splitLine: { show: true, lineStyle: { color: t.grid, width: 1, type: "solid" as const } },
    nameTextStyle: { color: t.ink2, fontSize: 11.5, fontFamily: t.font },
  };
}

export function tooltip(t: Tokens, extra: Record<string, unknown> = {}) {
  return {
    backgroundColor: t.surface,
    borderColor: t.line,
    borderWidth: 1,
    padding: [9, 11],
    textStyle: { color: t.ink, fontFamily: t.font, fontSize: 12.5 },
    extraCssText: `border-radius:10px;box-shadow:0 10px 28px -12px rgba(0,0,0,${t.dark ? 0.7 : 0.25});`,
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
  const h = hex.replace("#", "");
  if (h.length !== 6) return "#ffffff";
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum > 0.224 ? "#0f2a33" : "#ffffff"; // crossover where both inks give equal contrast
}
