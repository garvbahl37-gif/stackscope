import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
import { Shell } from "./components/Shell";
import "./styles/app.css";

const Overview = lazy(() => import("./pages/Overview"));
const Landscape = lazy(() => import("./pages/Landscape"));
const RadarPage = lazy(() => import("./pages/Radar"));
const Trends = lazy(() => import("./pages/Trends"));
const Retention = lazy(() => import("./pages/Retention"));
const Ecosystems = lazy(() => import("./pages/Ecosystems"));
const Pay = lazy(() => import("./pages/Pay"));
const Estimator = lazy(() => import("./pages/Estimator"));
const Personas = lazy(() => import("./pages/Personas"));
const AiPage = lazy(() => import("./pages/Ai"));
const Quality = lazy(() => import("./pages/Quality"));
const SqlLab = lazy(() => import("./pages/SqlLab"));
const NotFound = lazy(() => import("./pages/NotFound"));

const router = createBrowserRouter([
  {
    path: "/",
    Component: Shell,
    children: [
      { index: true, Component: Overview },
      { path: "landscape", Component: Landscape },
      { path: "radar", Component: RadarPage },
      { path: "trends", Component: Trends },
      { path: "retention", Component: Retention },
      { path: "ecosystems", Component: Ecosystems },
      { path: "pay", Component: Pay },
      { path: "estimator", Component: Estimator },
      { path: "personas", Component: Personas },
      { path: "ai", Component: AiPage },
      { path: "quality", Component: Quality },
      { path: "sql", Component: SqlLab },
      { path: "*", Component: NotFound },
    ],
  },
]);

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

// Reuse the root across dev hot-reloads of this module (production renders once).
const container = document.getElementById("root") as HTMLElement & { __root?: ReturnType<typeof createRoot> };
container.__root ??= createRoot(container);
container.__root.render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
