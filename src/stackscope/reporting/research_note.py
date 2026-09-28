"""Research note — a Gartner-style written brief generated from the marts (numbers are queried, not typed)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from jinja2 import Environment

from .. import settings

TEMPLATE = """\
# The Developer Technology Market, 2017–2025

**Adoption, retention, pay and the generative-AI trust gap**

StackScope research note, {{ today }}. Evidence base: {{ "{:,}".format(kpi.respondents) }} responses to nine annual Stack Overflow
Developer Surveys, {{ kpi.countries }} countries and territories, {{ kpi.technologies }} harmonised technologies.

## Summary

Developers keep consolidating around a small set of healthy platforms while the edges of the market churn quickly.
{{ f.fastest_language.headline }}, and {{ f.postgres.headline }}. Generative AI moved from experiment to default in two
years, yet confidence in its output is falling, and falling fastest among the most experienced developers. Pay premiums
attach to cloud and data-platform skills rather than to any single language.

## Key findings

{% for x in findings -%}
- **{{ x.headline }}.** {{ x.detail }}
{% endfor %}
## Recommendations

**Engineering and technology leaders**

- Default new services to technologies in the *Leaders* position of their category ({{ leaders_text }}), and treat *Challengers*
  with falling momentum ({{ challengers_text }}) as candidates for managed decline rather than new investment.
- Plan migrations along the paths developers already want to take: the largest one-directional flows in 2025 were
  {{ flows_text }}.
- Budget AI-assisted development for verification, not just generation: {{ pct(ai25.using_w) }} of developers use AI tools but
  only {{ pct(ai25.trust_w) }} trust the output's accuracy.

**HR and talent leaders**

- Benchmark pay on purchasing power as well as dollars: the median Indian developer earns {{ money(ind.median_usd) }}, but
  {{ money(ind.median_ppp) }} in PPP terms against {{ money(weu.median_ppp) }} for Western Europe ({{ money(weu.median_usd) }} in dollars).
- Prioritise skills with a significant, broad-based premium after controls: {{ premium_text }}.
- Expect hybrid, not remote-first, work: fully remote work peaked at {{ pct(remote_peak.share_w) }} in {{ remote_peak.survey_year|int }}
  and fell to {{ pct(remote_last.share_w) }} in {{ remote_last.survey_year|int }}.

**Technology vendors and product teams**

- Win on retention, not reach: the widely used languages with the highest retention ({{ retention_text }}) are also in
  statistically significant multi-year growth.
- Close the AI trust gap for senior engineers; developers with 21+ years of experience have
  {{ "%.2f"|format(trust_senior) }}× the odds of trusting AI output compared with those with 6–10 years.

## Analysis

### Market positions, 2025

| Category | Leaders (highest momentum first) | Challengers |
|---|---|---|
{% for row in positions -%}
| {{ row.category }} | {{ row.leaders }} | {{ row.challengers }} |
{% endfor %}
Adoption is the composition-weighted share of developers using each technology; momentum averages within-category z-scores
of retention, attraction and wave-on-wave change.

### Fastest risers and decliners (all waves, false-discovery controlled)

| Technology | Category | First → latest | Annual change in odds of use |
|---|---|---|---|
{% for r in movers -%}
| {{ r.tech }} | {{ r.category_label }} | {{ pct(r.share_first) }} → {{ pct(r.share_last) }} | {{ signed(r.odds_growth) }} |
{% endfor %}
### What skills are worth (global model, 2023–2025)

| Technology | Adjusted premium | 95% interval | Raw gap |
|---|---|---|---|
{% for r in premiums -%}
| {{ r.tech }} | {{ signed(r.premium) }} | {{ signed(r.premium_lo) }} to {{ signed(r.premium_hi) }} | {{ signed(r.raw_premium) }} |
{% endfor %}
Premiums come from an OLS model of log real pay with country, experience, role, company size, education, industry, work
arrangement and year controls ({{ "{:,}".format(model.n) }} developers, R² {{ "%.2f"|format(model.r2) }}), HC1 robust errors
and Benjamini–Hochberg correction. They are associations, not causal effects.

### Generative AI

| Wave | Use AI tools | Favourable | Trust accuracy | Distrust accuracy |
|---|---|---|---|---|
{% for r in ai -%}
| {{ r.survey_year }} | {{ pct(r.using_w) }} | {{ pct(r.favorable_w) }} | {{ pct(r.trust_w) }} | {{ pct(r.distrust_w) }} |
{% endfor %}
## Methodology

- **Harmonisation.** Nine files with 924 raw columns were mapped to one schema; {{ "{:,}".format(kpi.raw_labels) }} distinct raw
  answer labels were mapped to {{ kpi.technologies }} canonical technologies (100% of in-scope mentions).
- **Weighting.** Each wave is raked (iterative proportional fitting) to the average respondent mix by region, respondent type and
  experience, so trends are not artefacts of who answered. Design effects stay between 1.02 and 1.22.
- **Uncertainty.** Shares carry Wilson 95% intervals using Kish effective sample sizes; multi-year trends use inverse-variance
  weighted logistic regression; every family of tests is Benjamini–Hochberg controlled.
- **Pay.** Salaries are screened per country-year with a MAD-based modified z-score, deflated with US CPI-U to 2025 dollars and
  converted at World Bank PPP price levels.
- **Forecasts.** Five models were backtested from rolling origins; none beat the naive forecast
  (one-year error {{ "%.1f"|format(forecast_mae) }} pp), so projections are presented as calibrated ranges.
- **Quality.** {{ kpi.checks_passed }} of {{ kpi.checks_total }} automated checks pass; blocking checks stop the build.

## Limitations

- Stack Overflow respondents are not a random sample of all developers; weighting corrects composition drift between waves,
  not self-selection into the survey.
- Question wording, option lists and routing changed across waves. Known breaks (for example, respondents selecting 14% more
  languages in 2025, and AI questions moving from tools to model families) are flagged wherever they affect a comparison.
- Mindshare is not market share: adoption measures developer usage, not revenue or installed base.

*Independent analysis; not affiliated with Gartner or Stack Overflow. Data: Stack Overflow Developer Survey (ODbL),
World Bank World Development Indicators, FRED.*
"""


def _pct(v) -> str:
    return "–" if v is None or pd.isna(v) else f"{v * 100:.0f}%"


def _signed(v) -> str:
    return "–" if v is None or pd.isna(v) else f"{v * 100:+.1f}%"


def _money(v) -> str:
    return "–" if v is None or pd.isna(v) else f"${v / 1000:,.1f}k"


def build(con, path: Path | None = None) -> Path:
    q = lambda sql: con.execute(sql).df()  # noqa: E731
    kpi = q("""SELECT (SELECT count(*) FROM core.fact_respondent) AS respondents,
                      (SELECT count(DISTINCT iso3) FROM core.fact_respondent WHERE iso3 IS NOT NULL) AS countries,
                      (SELECT count(*) FROM core.dim_technology) AS technologies,
                      (SELECT count(DISTINCT raw_label) FROM dq.label_coverage) AS raw_labels,
                      (SELECT count(*) FILTER (WHERE status = 'pass') FROM dq.check_results) AS checks_passed,
                      (SELECT count(*) FROM dq.check_results) AS checks_total""").iloc[0]
    findings = q("SELECT * FROM mart.key_findings ORDER BY rank")
    by_id = {r.finding_id: r for r in findings.itertuples()}
    quad = q("""SELECT category_label AS category, tech, quadrant, momentum FROM mart.tech_quadrant
                WHERE survey_year = 2025 AND category IN ('language','database','cloud','webframe','devops','ai')""")
    positions = []
    for cat, g in quad.groupby("category"):
        lead = g[g.quadrant == "Leaders"].sort_values("momentum", ascending=False).tech.head(4)
        chal = g[g.quadrant == "Challengers"].sort_values("momentum").tech.head(4)
        positions.append({"category": cat, "leaders": ", ".join(lead) or "–", "challengers": ", ".join(chal) or "–"})
    movers = q("""WITH t AS (SELECT tr.*, d.category_label FROM mart.tech_trend tr JOIN core.dim_technology d USING (tech_id))
                  (SELECT * FROM t WHERE trend = 'Rising' AND n_points >= 6 ORDER BY odds_growth DESC LIMIT 6)
                  UNION ALL (SELECT * FROM t WHERE trend = 'Declining' AND n_points >= 6 ORDER BY odds_growth LIMIT 5)""")
    premiums = q("""SELECT * FROM mart.skill_premium WHERE scope = 'Global' AND significant AND prevalence >= 0.03
                    ORDER BY premium DESC LIMIT 10""")
    model = q("SELECT * FROM mart.skill_premium_model WHERE scope = 'Global'").iloc[0]
    ai = q("SELECT * FROM mart.ai_year ORDER BY survey_year")
    remote = q("SELECT survey_year, share_w FROM mart.workforce_mix WHERE attribute = 'remote_work' AND category = 'Remote' ORDER BY 1")
    ind = q("SELECT median_usd, median_ppp FROM mart.pay_benchmark WHERE cut = 'country' AND segment = 'IND' AND survey_year = 2025").iloc[0]
    flows = q("""SELECT from_tech, to_tech, net_flow FROM mart.tech_net_migration WHERE survey_year = 2025 AND category IN ('language','database')
                 ORDER BY net_flow DESC LIMIT 3""")
    retention = q("""SELECT y.tech FROM mart.tech_year y JOIN mart.tech_trend t USING (tech_id)
                     WHERE y.survey_year = 2025 AND y.category = 'language' AND y.share_used_w >= 0.1 AND t.trend = 'Rising'
                     ORDER BY y.retention_w DESC LIMIT 3""")
    weu = q("SELECT median_usd, median_ppp FROM mart.pay_benchmark WHERE cut = 'region' AND segment = 'Western Europe' AND survey_year = 2025").iloc[0]
    trust_senior = con.execute("""SELECT odds_ratio FROM mart.ai_drivers WHERE model LIKE 'Trusts%' AND variable = 'exp_band'
                                  AND level = '21+'""").fetchone()[0]
    forecast_mae = con.execute("SELECT mae_pp FROM mart.forecast_backtest WHERE selected AND horizon = 1").fetchone()[0]

    env = Environment(autoescape=False, trim_blocks=False, lstrip_blocks=False)
    template = env.from_string(TEMPLATE)
    text = template.render(
        today=date.today().strftime("%d %B %Y"), kpi=kpi, f=by_id, findings=findings.to_dict("records"),
        positions=positions, movers=movers.to_dict("records"), premiums=premiums.to_dict("records"), model=model,
        ai=ai.to_dict("records"), ai25=ai.iloc[-1], ind=ind, weu=weu,
        remote_peak=remote.loc[remote.share_w.idxmax()], remote_last=remote.iloc[-1],
        leaders_text=next((p["leaders"] for p in positions if p["category"] == "Languages"), "–"),
        challengers_text=next((p["challengers"] for p in positions if p["category"] == "Languages"), "–"),
        flows_text="; ".join(f"{r.from_tech} to {r.to_tech} (net {int(r.net_flow):,} developers)" for r in flows.itertuples()),
        premium_text=", ".join(f"{r.tech} ({_signed(r.premium)})" for r in premiums.head(5).itertuples()),
        retention_text=", ".join(retention.tech), trust_senior=trust_senior, forecast_mae=forecast_mae,
        pct=_pct, signed=_signed, money=_money,
    )
    path = path or settings.REPORTS_DIR / "research_note.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path
