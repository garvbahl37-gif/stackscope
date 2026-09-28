/** Tree-shaken ECharts build: only the charts, components and renderers the app uses. */
import { BarChart, CustomChart, GraphChart, HeatmapChart, LineChart, MapChart, SankeyChart, ScatterChart } from "echarts/charts";
import {
  AriaComponent, DatasetComponent, GeoComponent, GraphicComponent, GridComponent, MarkAreaComponent,
  MarkLineComponent, MarkPointComponent, TooltipComponent, VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { LabelLayout, UniversalTransition } from "echarts/features";
import { CanvasRenderer, SVGRenderer } from "echarts/renderers";

echarts.use([
  LineChart, BarChart, ScatterChart, HeatmapChart, SankeyChart, GraphChart, MapChart, CustomChart,
  GridComponent, TooltipComponent, MarkLineComponent, MarkAreaComponent, MarkPointComponent, VisualMapComponent,
  GeoComponent, GraphicComponent, DatasetComponent, AriaComponent,
  LabelLayout, UniversalTransition, SVGRenderer, CanvasRenderer,
]);

export { echarts };
