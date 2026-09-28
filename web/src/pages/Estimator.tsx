import { useEffect, useMemo, useState } from "react";
import { simpleBarOption } from "../charts/bars";
import { waterfallOption } from "../charts/misc";
import { EChart } from "../components/EChart";
import { ErrorState, Loading, PageHeader, Panel, Segmented, Select } from "../components/ui";
import { type Estimate, type EstimatorOptions, type Profile, useEstimate, useEstimatorOptions } from "../lib/api";
import { int, money, pct, signedPct } from "../lib/format";
import { useTokens } from "../lib/theme";

const DEFAULT: Profile = {
  country: "IND", dev_role: "Back-end developer", years_code: 4, org_size: "1,000-4,999", ed_level: "Bachelor's",
  remote_work: "Hybrid", industry: "Software & IT", age_band: "18-24", ai_use: "Using",
  technologies: ["Python", "SQL", "PostgreSQL", "AWS", "Docker"],
};
const CATEGORY_ORDER = ["Languages", "Databases", "Cloud Platforms", "Web Frameworks & Runtimes", "DevOps & Infrastructure"];

function RangeBar({ est }: { est: Estimate }) {
  const lo = Math.min(est.p10, est.country_median ?? est.p10) * 0.85;
  const hi = Math.max(est.p90, est.country_median ?? est.p90) * 1.08;
  const pos = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="range" aria-label={`Estimated range ${money(est.p10)} to ${money(est.p90)}, median ${money(est.p50)}`}>
      <div className="range__track">
        <div className="range__band" style={{ left: pos(est.p10), width: `calc(${pos(est.p90)} - ${pos(est.p10)})` }} />
        <div className="range__mid" style={{ left: pos(est.p50) }} />
        {est.country_median != null && <div className="range__ref" style={{ left: pos(est.country_median) }} title="Country median" />}
      </div>
      <div className="range__labels">
        <span style={{ left: pos(est.p10) }}>{money(est.p10, { compact: true })}<small>10th percentile</small></span>
        <span style={{ left: pos(est.p90) }}>{money(est.p90, { compact: true })}<small>90th percentile</small></span>
      </div>
      {est.country_median != null && (
        <p className="small muted" style={{ marginTop: 34 }}>
          <span className="range__ref-key" /> Country median for full-time professionals: {money(est.country_median)}
        </p>
      )}
    </div>
  );
}

function TechToggles({ options, selected, onToggle }: { options: EstimatorOptions["technologies"]; selected: string[]; onToggle: (t: string) => void }) {
  const groups = useMemo(() => {
    const g = new Map<string, string[]>();
    options.forEach((o) => g.set(o.category, [...(g.get(o.category) ?? []), o.tech]));
    return [...g.entries()].sort((a, b) => CATEGORY_ORDER.indexOf(a[0]) - CATEGORY_ORDER.indexOf(b[0]));
  }, [options]);
  return (
    <div className="tech-groups">
      {groups.map(([cat, techs]) => (
        <fieldset key={cat}>
          <legend>{cat}</legend>
          <div className="chips">
            {techs.sort().map((tech) => (
              <button key={tech} type="button" className="chip" aria-pressed={selected.includes(tech)} onClick={() => onToggle(tech)}>{tech}</button>
            ))}
          </div>
        </fieldset>
      ))}
    </div>
  );
}

export default function Estimator() {
  const t = useTokens();
  const opts = useEstimatorOptions();
  const estimate = useEstimate();
  const [profile, setProfile] = useState<Profile>(DEFAULT);
  const set = <K extends keyof Profile>(key: K, value: Profile[K]) => setProfile((p) => ({ ...p, [key]: value }));

  useEffect(() => {
    const id = window.setTimeout(() => estimate.mutate(profile), 250);
    return () => window.clearTimeout(id);
  }, [profile]); // eslint-disable-line react-hooks/exhaustive-deps

  const est = estimate.data;
  const waterfall = useMemo(() => {
    if (!est) return null;
    let running = est.baseline;
    const steps = est.contributions.filter((c) => Math.abs(c.log_effect) > 0.005).map((c) => {
      running *= c.multiplier;
      return { label: c.group, value: running };
    });
    return waterfallOption({ label: "Typical developer", value: est.baseline }, steps, t, (v) => money(v));
  }, [est, t]);
  const importance = useMemo(() => opts.data ? simpleBarOption(
    opts.data.importance.map((g) => ({ label: g.group, value: g.share })), t, (v) => pct(v, 0)) : null, [opts.data, t]);

  if (opts.isError) return <><PageHeader title="Salary estimator" /><ErrorState error={opts.error} /></>;
  const o = opts.data;
  const m = o?.metrics;
  return (
    <>
      <PageHeader
        title="Salary estimator"
        lede="A gradient-boosted model trained on 71,000 validated 2023–2025 salaries predicts the 10th, 50th and 90th percentile of pay for a profile, then widens the range with conformal calibration so it covers 80% of real salaries. Every estimate is explained."
      />
      {!o ? <Loading height={600} /> : (
        <div className="grid">
          <Panel className="span-5" title="Profile" caption="Estimates update as you change the profile.">
            <div className="form">
              <Select id="country" label="Country" value={profile.country} onChange={(v) => set("country", v)}
                      options={o.countries.map((c) => ({ value: c.iso3, label: c.country }))} />
              <Select id="role" label="Role" value={profile.dev_role} onChange={(v) => set("dev_role", v)}
                      options={o.roles.map((r) => ({ value: r, label: r }))} />
              <label className="control control--stack" htmlFor="yc">
                <span>Years of coding experience <strong>{profile.years_code}</strong></span>
                <input id="yc" type="range" min={0} max={40} value={profile.years_code} onChange={(e) => set("years_code", Number(e.target.value))} />
              </label>
              <Select id="org" label="Company size" value={profile.org_size} onChange={(v) => set("org_size", v)}
                      options={o.org_sizes.map((r) => ({ value: r, label: `${r} employees` }))} />
              <Select id="ed" label="Education" value={profile.ed_level} onChange={(v) => set("ed_level", v)}
                      options={o.education.map((r) => ({ value: r, label: r }))} />
              <Select id="ind" label="Industry" value={profile.industry} onChange={(v) => set("industry", v)}
                      options={o.industries.map((r) => ({ value: r, label: r }))} />
              <Select id="age" label="Age" value={profile.age_band} onChange={(v) => set("age_band", v)}
                      options={o.age_bands.map((r) => ({ value: r, label: r }))} />
              <div className="control control--stack">
                <span>Work arrangement</span>
                <Segmented label="Work arrangement" options={o.remote.map((r) => ({ value: r, label: r }))} value={profile.remote_work} onChange={(v) => set("remote_work", v)} />
              </div>
              <div className="control control--stack">
                <span>Uses AI tools</span>
                <Segmented label="AI use" options={o.ai_use.map((r) => ({ value: r, label: r }))} value={profile.ai_use} onChange={(v) => set("ai_use", v)} />
              </div>
              <div className="control control--stack">
                <span>Technologies used <strong>{profile.technologies.length}</strong></span>
                <TechToggles options={o.technologies} selected={profile.technologies}
                             onToggle={(tech) => set("technologies", profile.technologies.includes(tech)
                               ? profile.technologies.filter((x) => x !== tech) : [...profile.technologies, tech])} />
              </div>
            </div>
          </Panel>

          <div className="span-7" style={{ display: "grid", gap: 18, alignContent: "start" }}>
            <Panel hero stale={estimate.isPending} title="Estimated annual pay" caption={`Constant ${o.price_base_year} US dollars, before tax, full-time.`}>
              {estimate.isError ? <ErrorState error={estimate.error} /> : !est ? <Loading height={220} /> : (
                <>
                  <div className="hero-figure">{money(est.p50, { compact: false })}</div>
                  <p className="small muted">Median estimate. Eight in ten developers with this profile earn between {money(est.p10, { compact: true })} and {money(est.p90, { compact: true })}.</p>
                  <RangeBar est={est} />
                </>
              )}
            </Panel>
            <Panel title="Why this estimate" caption="How each part of the profile moves pay from a typical respondent's, using exact TreeSHAP contributions from the median model."
                   table={est ? { columns: [
                     { key: "group", label: "Factor" },
                     { key: "multiplier", label: "Effect", numeric: true, render: (r: Estimate["contributions"][number]) => signedPct(r.multiplier - 1, 1), value: (r: Estimate["contributions"][number]) => r.multiplier - 1 },
                   ], rows: est.contributions, filename: "estimate_explanation.csv" } : undefined}>
              {waterfall ? <EChart option={waterfall} height={330} label="Contribution waterfall" /> : <Loading height={330} />}
              {est && est.tech_effects.length > 0 && (
                <p className="small" style={{ marginTop: 8 }}>
                  <strong>Technology effects: </strong>
                  {est.tech_effects.map((e) => `${e.tech} ${signedPct(e.multiplier - 1, 1)}`).join(", ")}
                </p>
              )}
            </Panel>
          </div>

          <Panel className="span-12" title="Model card"
                 caption="Evaluated on 10,700 salaries the model never saw. The baseline is the median salary for the same country and year.">
            {m && (
              <div className="model-card">
                <div className="stats stats--inline">
                  <div className="stat"><div className="stat__label">Variance explained (log pay)</div><div className="stat__value">{m.r2_log.toFixed(2)}</div><div className="stat__note">baseline {m.r2_log_baseline.toFixed(2)}</div></div>
                  <div className="stat"><div className="stat__label">Median error</div><div className="stat__value">{pct(m.median_ape, 0)}</div><div className="stat__note">baseline {pct(m.median_ape_baseline, 0)}</div></div>
                  <div className="stat"><div className="stat__label">80% range coverage</div><div className="stat__value">{pct(m.coverage_conformal, 1)}</div><div className="stat__note">{pct(m.coverage_raw, 1)} before conformal calibration</div></div>
                  <div className="stat"><div className="stat__label">Training salaries</div><div className="stat__value">{int(m.n_train)}</div><div className="stat__note">{int(m.n_calib)} for calibration</div></div>
                </div>
                <div className="grid" style={{ marginTop: 16 }}>
                  <div className="span-6">
                    <h3 className="panel__title" style={{ fontSize: 14 }}>What drives pay predictions</h3>
                    <p className="panel__caption">Share of mean absolute SHAP contribution by feature group.</p>
                    {importance ? <EChart option={importance} height={260} label="Feature group importance" /> : null}
                  </div>
                  <div className="span-6 prose small">
                    <h3 className="panel__title" style={{ fontSize: 14, color: "var(--ink)" }}>How it works</h3>
                    <p>Three LightGBM models fit the 10th, 50th and 90th percentiles of log pay (pinball loss) with early stopping on a validation split. Conformalized quantile regression then widens the 10–90 band by the error quantile observed on a separate calibration split, which guarantees the stated coverage on new data.</p>
                    <p>Features: country, role, coding experience, work experience, company size, education, industry, age band, work arrangement, AI use and 60 technology flags. Pay is in constant 2025 US dollars. Estimates describe survey respondents, not a salary offer.</p>
                  </div>
                </div>
              </div>
            )}
          </Panel>
        </div>
      )}
    </>
  );
}
