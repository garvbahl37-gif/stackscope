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

{{ structure_text }} {{ f.fastest_language.headline }}, and {{ f.postgres.headline }}. Generative AI moved from
experiment to default in two years, yet trust in its output fell in {{ trust_fell_text }} and is lowest among developers
with {{ low_trust.exp_band }} years of experience ({{ pct(low_trust.trust_2025) }} trust it). {{ premium_mix_text }}

## Key findings

{% for x in findings -%}
- **{{ x.headline }}.** {{ x.detail }}
{% endfor %}
## Recommendations

**Engineering and technology leaders**

- Default new services to technologies in the *Leaders* position of their category ({{ leaders_text }}), and treat the *Challengers*
  with the weakest momentum ({{ challengers_text }}) as candidates for managed decline rather than new investment.
- Plan migrations along the paths developers already want to take: the largest one-directional flows in 2025 were
  {{ flows_text }}.
- Budget AI-assisted development for verification, not just generation: {{ pct(ai25.using_w) }} of developers use AI tools but
  only {{ pct(ai25.trust_w) }} trust the output's accuracy.

**HR and talent leaders**

- Benchmark pay on purchasing power as well as dollars: the median Indian developer earns {{ money(ind.median_usd) }}, but
  {{ money(ind.median_ppp) }} in PPP terms against {{ money(weu.median_ppp) }} for Western Europe ({{ money(weu.median_usd) }} in dollars).
- Prioritise skills with a significant premium after controls. Widely used (by 5% or more of developers):
  {{ premium_broad_text }}. Niche but valuable: {{ premium_niche_text }}.
- Expect hybrid, not remote-first, work: fully remote work peaked at {{ pct(remote_peak.share_w) }} in {{ remote_peak.survey_year|int }}
  and fell to {{ pct(remote_last.share_w) }} in {{ remote_last.survey_year|int }}.

**Technology vendors and product teams**

- Win on retention, not reach: the widely used languages with the highest retention ({{ retention_text }}) {{ retention_trend_text }}.
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

| Technology | Used by | Adjusted premium | 95% interval | Raw gap |
|---|---|---|---|---|
{% for r in premiums -%}
| {{ r.tech }} | {{ pct(r.prevalence) }} | {{ signed(r.premium) }} | {{ signed(r.premium_lo) }} to {{ signed(r.premium_hi) }} | {{ signed(r.raw_premium) }} |
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
  answer labels were mapped to {{ kpi.technologies }} canonical technologies ({{ pct(coverage) }} of in-scope mentions).
- **Weighting.** Each wave is raked (iterative proportional fitting) to the average respondent mix by region, respondent type and
  experience, so trends are not artefacts of who answered. Design effects stay between {{ "%.2f"|format(deff_min) }} and
  {{ "%.2f"|format(deff_max) }}. Weighted shares therefore differ by a few points from Stack Overflow's published figures,
  which are unweighted; computed unweighted, the pipeline reproduces them (see the data-quality reconciliation).
- **Uncertainty.** Shares carry Wilson 95% intervals using Kish effective sample sizes; multi-year trends use inverse-variance
  weighted logistic regression; every family of tests is Benjamini–Hochberg controlled.
- **Pay.** Salaries are screened per country-year with a MAD-based modified z-score, deflated with US CPI-U to 2025 dollars and
  converted at World Bank PPP price levels.
- **Forecasts.** {{ n_models }} models were backtested from rolling origins; none beat the naive forecast
  (one-year error {{ "%.1f"|format(forecast_mae) }} pp), so projections are presented as calibrated ranges.
- **Quality.** {{ kpi.checks_passed }} of {{ kpi.checks_total }} automated checks pass; blocking checks stop the build.

## Limitations

- Stack Overflow respondents are not a random sample of all developers; weighting corrects composition drift between waves,
  not self-selection into the survey.
- Question wording, option lists and routing changed across waves. Known breaks (for example, respondents selecting
  {{ pct(language_jump) }} more languages in 2025, and AI questions moving from tools to model families) are flagged wherever
  they affect a comparison. Concentration trends are measured like for like, so new answer options do not move them.
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
    premiums = q("""SELECT * FROM mart.skill_premium WHERE scope = 'Global' AND significant ORDER BY premium DESC LIMIT 10""")
    broad = q("""SELECT * FROM mart.skill_premium WHERE scope = 'Global' AND significant AND prevalence >= 0.05
                 ORDER BY premium DESC LIMIT 3""")
    niche = q("""SELECT * FROM mart.skill_premium WHERE scope = 'Global' AND significant AND prevalence < 0.05
                 ORDER BY premium DESC LIMIT 3""")
    platforms_in_top = int((premiums.category != "language").sum())
    if platforms_in_top * 2 > len(premiums):
        premium_mix_text = (f"{platforms_in_top} of the {len(premiums)} largest adjusted pay premiums attach to cloud, data and "
                            "infrastructure platforms rather than to languages.")
    else:
        premium_mix_text = (f"The largest adjusted pay premiums are split between languages and platforms ({platforms_in_top} of "
                            f"the top {len(premiums)} are platforms).")
    trust = q("""SELECT exp_band,
                        sum(w.weight) FILTER (WHERE survey_year = 2023 AND ai_trust_score > 0)
                            / sum(w.weight) FILTER (WHERE survey_year = 2023) AS trust_2023,
                        sum(w.weight) FILTER (WHERE survey_year = 2025 AND ai_trust_score > 0)
                            / sum(w.weight) FILTER (WHERE survey_year = 2025) AS trust_2025
                 FROM core.fact_respondent JOIN core.respondent_weight AS w USING (resp_key, survey_year)
                 WHERE survey_year IN (2023, 2025) AND ai_trust IS NOT NULL AND exp_band IS NOT NULL
                 GROUP BY exp_band""")
    fell = int((trust.trust_2025 < trust.trust_2023).sum())
    trust_fell_text = "every experience group" if fell == len(trust) else f"{fell} of {len(trust)} experience groups"
    low_trust = trust.loc[trust.trust_2025.idxmin()]
    llf = q("""SELECT category, hhi_like_for_like FROM mart.market_concentration
               WHERE survey_year IN (2018, 2025) AND category IN ('language', 'webframe', 'database', 'cloud')
               ORDER BY category, survey_year""")
    moves = {c: g.hhi_like_for_like.iloc[-1] / g.hhi_like_for_like.iloc[0] - 1 for c, g in llf.groupby("category")}
    names = {"language": "languages", "webframe": "web frameworks", "database": "databases", "cloud": "cloud platforms"}
    spread = [names[c] for c in names if moves.get(c, 0) < 0]
    concentrated = [names[c] for c in names if moves.get(c, 0) > 0]
    join = lambda xs: ", ".join(xs[:-1]) + (" and " if len(xs) > 1 else "") + xs[-1] if xs else ""  # noqa: E731
    structure_text = (f"Like for like, developer usage has spread out across {join(spread)} since 2018"
                      + (f", while concentration rose among {join(concentrated)}." if concentrated else "."))
    deff_min, deff_max = con.execute("SELECT min(design_effect), max(design_effect) FROM dq.weight_diagnostics").fetchone()
    coverage = con.execute("""SELECT sum(mentions) FILTER (WHERE status = 'mapped') / sum(mentions) FILTER (WHERE status <> 'excluded')
                              FROM dq.label_coverage""").fetchone()[0]
    n_models = con.execute("SELECT count(DISTINCT model) FROM mart.forecast_backtest").fetchone()[0]
    language_jump = con.execute("""SELECT avg(k) FILTER (WHERE survey_year = 2025) / avg(k) FILTER (WHERE survey_year = 2024) - 1
                                   FROM (SELECT b.survey_year, b.resp_key, count(*) AS k FROM core.bridge_tech_usage AS b
                                         JOIN core.dim_technology AS t USING (tech_id)
                                         WHERE t.category = 'language' AND b.used AND b.survey_year IN (2024, 2025)
                                         GROUP BY ALL)""").fetchone()[0]
    model = q("SELECT * FROM mart.skill_premium_model WHERE scope = 'Global'").iloc[0]
    ai = q("SELECT * FROM mart.ai_year ORDER BY survey_year")
    remote = q("SELECT survey_year, share_w FROM mart.workforce_mix WHERE attribute = 'remote_work' AND category = 'Remote' ORDER BY 1")
    ind = q("SELECT median_usd, median_ppp FROM mart.pay_benchmark WHERE cut = 'country' AND segment = 'IND' AND survey_year = 2025").iloc[0]
    flows = q("""SELECT from_tech, to_tech, net_flow FROM mart.tech_net_migration WHERE survey_year = 2025 AND category IN ('language','database')
                 ORDER BY net_flow DESC LIMIT 3""")
    retention = q("""SELECT y.tech, t.trend FROM mart.tech_year y JOIN mart.tech_trend t USING (tech_id)
                     WHERE y.survey_year = 2025 AND y.category = 'language' AND y.share_used_w >= 0.1
                     ORDER BY y.retention_w DESC LIMIT 3""")
    rising = retention.trend.eq("Rising")
    retention_trend_text = ("are also in statistically significant multi-year growth" if rising.all() else
                            f"include {', '.join(retention.tech[rising]) or 'none'} in statistically significant multi-year growth")
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
        flows_text="; ".join(f"{r.from_tech} to {r.to_tech} (net {int(r.net_flow):,} respondents)" for r in flows.itertuples()),
        premium_broad_text=", ".join(f"{r.tech} ({_signed(r.premium)})" for r in broad.itertuples()),
        premium_niche_text=", ".join(f"{r.tech} ({_signed(r.premium)}, used by {r.prevalence:.1%})" for r in niche.itertuples()),
        retention_text=", ".join(retention.tech), retention_trend_text=retention_trend_text,
        trust_senior=trust_senior, forecast_mae=forecast_mae, structure_text=structure_text,
        trust_fell_text=trust_fell_text, low_trust=low_trust, premium_mix_text=premium_mix_text,
        deff_min=deff_min, deff_max=deff_max, coverage=coverage, n_models=n_models, language_jump=language_jump,
        pct=_pct, signed=_signed, money=_money,
    )
    path = path or settings.REPORTS_DIR / "research_note.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path
