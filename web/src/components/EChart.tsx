import type { EChartsOption } from "echarts";
import { useEffect, useRef } from "react";
import { echarts } from "../lib/echarts";

type Handler = (params: any) => void; // eslint-disable-line @typescript-eslint/no-explicit-any
const EVENT_NAMES = ["click", "mouseover", "mouseout"] as const;

type Props = {
  option: EChartsOption;
  height: number | string;
  renderer?: "svg" | "canvas";
  events?: Partial<Record<(typeof EVENT_NAMES)[number], Handler>>;
  label: string;             // accessible name (every chart also has a table view)
  replaceSeries?: boolean;   // drop series missing from the next option (default true)
};

/**
 * ECharts host. The instance is created only once the container has a real size (avoids
 * zero-size init inside suspended or collapsed layouts), options are applied with replaceMerge
 * so series with stable ids animate between states, and events go through a ref dispatcher so
 * handlers can change without re-binding.
 */
export function EChart({ option, height, renderer = "svg", events, label, replaceSeries = true }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const optionRef = useRef(option);
  const eventsRef = useRef(events);
  optionRef.current = option;
  eventsRef.current = events;

  useEffect(() => {
    const node = el.current;
    if (!node) return;
    let instance: echarts.ECharts | null = null;
    const ensure = () => {
      if (instance || node.clientWidth === 0 || node.clientHeight === 0) return;
      instance = echarts.init(node, undefined, { renderer });
      chart.current = instance;
      instance.setOption(optionRef.current);
      EVENT_NAMES.forEach((name) => instance!.on(name, (p) => eventsRef.current?.[name]?.(p)));
    };
    const ro = new ResizeObserver(() => {
      if (!instance) ensure();
      else instance.resize({ animation: { duration: 0 } });
    });
    ro.observe(node);
    ensure();
    return () => {
      ro.disconnect();
      instance?.dispose();
      chart.current = null;
    };
  }, [renderer]);

  useEffect(() => {
    const instance = chart.current;
    if (!instance || instance.isDisposed()) return;
    instance.setOption(option, replaceSeries ? { replaceMerge: ["series", "graphic"] } : { notMerge: false });
  }, [option, replaceSeries]);

  return <div ref={el} className="chart-area" style={{ height, width: "100%" }} role="img" aria-label={label} />;
}
