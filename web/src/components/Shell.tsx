import {
  ArrowLeftRight, BrainCircuit, Calculator, Database, Grid2x2, LayoutDashboard, Menu, Moon, Network, Radar,
  ShieldCheck, Sun, TrendingUp, Users, Wallet, X,
} from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { setThemePref, useThemePref } from "../lib/theme";
import { Loading } from "./ui";

export const NAV = [
  { group: "Market", items: [
    { to: "/", label: "Overview", icon: LayoutDashboard },
    { to: "/landscape", label: "Market landscape", icon: Grid2x2 },
    { to: "/radar", label: "Technology radar", icon: Radar },
    { to: "/trends", label: "Adoption & forecasts", icon: TrendingUp },
    { to: "/retention", label: "Retention & churn", icon: ArrowLeftRight },
    { to: "/ecosystems", label: "Ecosystems", icon: Network },
  ] },
  { group: "Talent", items: [
    { to: "/pay", label: "Pay & skills", icon: Wallet },
    { to: "/estimator", label: "Salary estimator", icon: Calculator },
    { to: "/personas", label: "Developer personas", icon: Users },
  ] },
  { group: "Generative AI", items: [
    { to: "/ai", label: "AI adoption & trust", icon: BrainCircuit },
  ] },
  { group: "Method", items: [
    { to: "/quality", label: "Data quality", icon: ShieldCheck },
    { to: "/sql", label: "SQL lab", icon: Database },
  ] },
];

export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg className="brand__mark" width={size} height={size} viewBox="0 0 28 28" aria-hidden>
      <rect className="brand__frame" x="1" y="1" width="26" height="26" rx="8" fill="none" strokeWidth="1.75" />
      <path className="brand__frame" d="M14 5v18M5 14h18" strokeWidth="1.75" />
      <circle className="brand__dot" cx="19.5" cy="8.5" r="3" />
    </svg>
  );
}

function ThemeToggle() {
  const pref = useThemePref();
  const dark = pref === "dark" || (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  const label = dark ? "Light theme" : "Dark theme";
  return (
    <button type="button" className="theme-toggle" onClick={() => setThemePref(dark ? "light" : "dark")} aria-label={label}>
      {dark ? <Sun aria-hidden /> : <Moon aria-hidden />}
      <span className="nav-link__label" aria-hidden>{label}</span>
    </button>
  );
}

export function Shell() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => {
    setOpen(false);
    window.scrollTo({ top: 0 });
  }, [pathname]);

  return (
    <div className="shell" data-nav-open={open}>
      <div className="topbar">
        <span className="topbar__brand"><BrandMark size={26} /><span className="brand__name">StackScope</span></span>
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label="Menu">
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden />}
      <nav className="rail" aria-label="Main">
        <NavLink to="/" className="brand" aria-label="StackScope home">
          <BrandMark />
          <span className="brand__name topbar-only">StackScope</span>
        </NavLink>
        {NAV.map((g) => (
          <div className="nav-group" key={g.group}>
            <div className="nav-group__label">{g.group}</div>
            {g.items.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} end={to === "/"} className="nav-link" aria-label={label}>
                <span className="nav-link__icon"><Icon aria-hidden /></span>
                <span className="nav-link__label" aria-hidden>{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
        <div className="rail__foot">
          <ThemeToggle />
        </div>
      </nav>
      <main className="content">
        <div className="page">
          <Suspense fallback={<Loading height={420} />}>
            <Outlet />
          </Suspense>
        </div>
        <footer className="page-foot">
          StackScope, technology market intelligence. Data: Stack Overflow Developer Survey 2017–2025 (ODbL), World Bank,
          FRED. Independent project, not affiliated with Gartner or Stack Overflow.
        </footer>
      </main>
    </div>
  );
}
