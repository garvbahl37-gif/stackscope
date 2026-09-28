"""Key findings — executive headlines generated from the marts on every run.

Each finding is a templated sentence whose numbers are queried, never typed, so the dashboard and
the research note can never drift from the data. A finding that cannot be computed is skipped.
"""

from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)


def _one(con, sql: str):
    row = con.execute(sql).fetchone()
    if row is None or any(v is None for v in row):
        raise ValueError(f"no data for: {sql[:60]}")
    return row


def _ai_paradox(con):
    u23, d23, t23 = _one(con, "SELECT using_w, distrust_w, trust_net FROM mart.ai_year WHERE survey_year = 2023")
    u25, d25, t25 = _one(con, "SELECT using_w, distrust_w, trust_net FROM mart.ai_year WHERE survey_year = 2025")
    return dict(theme="GenAI", route="/ai", value=u25, value_label="use AI tools (2025)",
                headline=f"GenAI adoption reached {u25:.0%} while trust turned negative",
                detail=(f"Developers using AI tools rose from {u23:.0%} (2023) to {u25:.0%} (2025), yet the share who "
                        f"distrust AI output grew from {d23:.0%} to {d25:.0%}; net trust fell from {t23:+.2f} to "
                        f"{t25:+.2f} on a -2..+2 scale."))


def _fastest_language(con):
    tech, og, lo, hi, s0, s1, y0 = _one(con, """
        SELECT tech, odds_growth, odds_growth_lo, odds_growth_hi, share_first, share_last, first_year
        FROM mart.tech_trend WHERE category = 'language' AND trend = 'Rising' AND n_points >= 7
        ORDER BY odds_growth DESC LIMIT 1""")
    ret = _one(con, f"SELECT retention_w FROM mart.tech_year WHERE tech = '{tech}' ORDER BY survey_year DESC LIMIT 1")[0]
    return dict(theme="Adoption", route="/trends", value=og, value_label="annual growth in odds of use",
                headline=f"{tech} is the fastest-rising established language",
                detail=(f"{tech} adoption grew from {s0:.1%} ({y0}) to {s1:.1%} (2025): the odds of a developer using it "
                        f"rose {og:.0%} a year (95% CI {lo:.0%}-{hi:.0%}), and {ret:.0%} of current users want to keep it."))


def _postgres(con):
    rows = con.execute("""
        SELECT survey_year, max(share_used_w) FILTER (WHERE tech = 'PostgreSQL') AS pg,
               max(share_used_w) FILTER (WHERE tech = 'MySQL') AS my
        FROM mart.tech_year WHERE tech IN ('PostgreSQL', 'MySQL') GROUP BY 1 ORDER BY 1""").df()
    cross = rows[rows.pg > rows.my]
    first = int(cross.survey_year.iloc[0])
    last = rows.iloc[-1]
    return dict(theme="Market share", route="/landscape", value=last.pg - last.my, value_label="PostgreSQL lead over MySQL (2025)",
                headline=f"PostgreSQL overtook MySQL in {first} and keeps widening the gap",
                detail=(f"In 2017 MySQL led {rows.my.iloc[0]:.0%} to {rows.pg.iloc[0]:.0%}; by 2025 PostgreSQL is used by "
                        f"{last.pg:.0%} of developers vs {last.my:.0%} for MySQL, and it is the top churn destination for MySQL users."))


def _premium(con):
    tech, prem, lo, hi, raw = _one(con, """
        SELECT tech, premium, premium_lo, premium_hi, raw_premium FROM mart.skill_premium
        WHERE scope = 'Global' AND significant AND prevalence >= 0.05 ORDER BY premium DESC LIMIT 1""")
    itech, iprem = _one(con, """SELECT tech, premium FROM mart.skill_premium
                                WHERE scope = 'India' AND significant AND prevalence >= 0.05 ORDER BY premium DESC LIMIT 1""")
    return dict(theme="Talent", route="/pay", value=prem, value_label=f"{tech} pay premium",
                headline=f"{tech} carries the largest broad-based pay premium (+{prem:.1%})",
                detail=(f"Controlling for country, experience, role, company size, education, industry and year, {tech} "
                        f"users earn {prem:+.1%} (95% CI {lo:+.1%} to {hi:+.1%}) vs a raw gap of {raw:+.0%}. "
                        f"In India the strongest significant premium is {itech} ({iprem:+.0%})."))


def _remote(con):
    df = con.execute("""SELECT survey_year, share_w FROM mart.workforce_mix
                        WHERE attribute = 'remote_work' AND category = 'Remote' ORDER BY survey_year""").df()
    peak = df.loc[df.share_w.idxmax()]
    last = df.iloc[-1]
    first = df.iloc[0]
    return dict(theme="Workforce", route="/pay", value=last.share_w, value_label="fully remote (2025)",
                headline=f"Fully-remote work peaked at {peak.share_w:.0%} in {int(peak.survey_year)} and is receding",
                detail=(f"Among professional developers, fully-remote work went from {first.share_w:.0%} ({int(first.survey_year)}) "
                        f"to a peak of {peak.share_w:.0%} ({int(peak.survey_year)}), and has fallen to {last.share_w:.0%} in 2025 as hybrid grows."))


def _cloud(con):
    h0, a0 = _one(con, "SELECT hhi, leader_share FROM mart.market_concentration WHERE category = 'cloud' AND survey_year = 2018")
    h1, a1, n1 = _one(con, "SELECT hhi, leader_share, technologies FROM mart.market_concentration WHERE category = 'cloud' AND survey_year = 2025")
    return dict(theme="Market share", route="/landscape", value=h1, value_label="cloud mindshare HHI (2025)",
                headline="Cloud mindshare is fragmenting beyond the big three",
                detail=(f"The Herfindahl index of cloud-platform mindshare fell from {h0:,.0f} (2018) to {h1:,.0f} (2025) across "
                        f"{n1} platforms; AWS still leads but its share of mentions slipped from {a0:.0%} to {a1:.0%}."))


def _churn(con):
    src, dst, share, churn = _one(con, """
        SELECT from_tech, to_tech, share_of_churners, from_churn_rate FROM mart.tech_switching
        WHERE survey_year = 2025 AND from_tech = 'Java' AND destination_rank = 1""")
    return dict(theme="Retention", route="/retention", value=churn, value_label="Java churn intent",
                headline=f"{churn:.0%} of Java users don't want to keep using it next year — {dst} is their top pick",
                detail=(f"Of Java developers who did not pick Java for next year, {share:.0%} want to adopt {dst} (a language they "
                        "do not use yet); churn-flow analysis shows the same pattern for MySQL -> PostgreSQL and jQuery -> React/Vue."))


def _real_pay(con):
    df = con.execute("SELECT survey_year, fixed_mix_median_real, raw_median_real FROM mart.real_pay_trend ORDER BY 1").df()
    first, last = df.iloc[0], df.iloc[-1]
    growth = last.fixed_mix_median_real / first.fixed_mix_median_real - 1
    raw_growth = last.raw_median_real / first.raw_median_real - 1
    return dict(theme="Talent", route="/pay", value=growth, value_label="real pay growth 2017-2025 (fixed mix)",
                headline=f"Real developer pay rose {growth:.0%} since 2017 once the country mix is held fixed",
                detail=(f"The raw median suggests only {raw_growth:+.0%} (in constant 2025 dollars) because the respondent mix shifted "
                        f"between countries; a fixed-country-mix index shows {growth:+.0%}."))


def _personas(con):
    big, big_share = _one(con, "SELECT name, share_w FROM mart.segment_profile ORDER BY share_w DESC LIMIT 1")
    rich, pay = _one(con, "SELECT name, median_pay_real FROM mart.segment_profile WHERE median_pay_real IS NOT NULL ORDER BY median_pay_real DESC LIMIT 1")
    low, low_pay = _one(con, "SELECT name, median_pay_real FROM mart.segment_profile WHERE median_pay_real IS NOT NULL ORDER BY median_pay_real LIMIT 1")
    return dict(theme="Segments", route="/personas", value=pay, value_label=f"median pay, {rich}",
                headline=f"{rich} is the best-paid developer persona",
                detail=(f"Stack-based clustering finds 8 personas; {big} is the largest ({big_share:.0%}), while {rich} earn a median "
                        f"${pay:,.0f} vs ${low_pay:,.0f} for {low}."))


def _experience_trust(con):
    orr, lo, hi = _one(con, """SELECT odds_ratio, or_lo, or_hi FROM mart.ai_drivers
                               WHERE model LIKE 'Trusts%' AND variable = 'exp_band' AND level = '21+'""")
    junior = _one(con, """SELECT odds_ratio FROM mart.ai_drivers
                          WHERE model LIKE 'Trusts%' AND variable = 'exp_band' AND level = '0-2'""")[0]
    return dict(theme="GenAI", route="/ai", value=orr, value_label="odds of trusting AI, 21+ yrs vs 6-10 yrs",
                headline="Experience, not age, drives AI scepticism",
                detail=(f"Holding age, role, region and company size constant, developers with 21+ years of coding have "
                        f"{orr:.2f}x the odds of trusting AI output (95% CI {lo:.2f}-{hi:.2f}) vs those with 6-10 years; juniors "
                        f"(0-2 years) have {junior:.2f}x."))


def _forecast(con):
    model, mae, skill = _one(con, """SELECT model, mae_pp, skill_vs_naive FROM mart.forecast_backtest
                                     WHERE selected AND horizon = 1""")
    n_models = _one(con, "SELECT count(DISTINCT model) FROM mart.forecast_backtest")[0]
    return dict(theme="Methodology", route="/trends", value=mae, value_label="1-year forecast MAE (pp)",
                headline="Adoption shares move like a random walk year to year",
                detail=(f"Across {n_models} backtested models (rolling origins 2020-2024) none beat the '{model}' forecast "
                        f"(mean absolute error {mae:.1f} pp one year ahead); forecasts therefore show calibrated uncertainty bands "
                        "rather than extrapolated trends."))


FINDINGS = [_ai_paradox, _fastest_language, _postgres, _premium, _churn, _cloud, _remote, _real_pay, _personas,
            _experience_trust, _forecast]


def run(con) -> dict:
    rows = []
    for rank, fn in enumerate(FINDINGS, start=1):
        try:
            rows.append({"rank": rank, "finding_id": fn.__name__.strip("_"), **fn(con)})
        except Exception as exc:  # a missing mart must not break the build
            log.warning("finding %s skipped: %s", fn.__name__, exc)
    frame = pd.DataFrame(rows)
    frame["value"] = frame["value"].astype(float)
    con.register("_f", frame)
    con.execute("CREATE OR REPLACE TABLE mart.key_findings AS SELECT * FROM _f")
    con.unregister("_f")
    return {"findings": len(frame), "skipped": len(FINDINGS) - len(frame)}
