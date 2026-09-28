"""Silver layer — harmonise 9 years of raw survey microdata into analysis-ready Parquet tables.

Outputs (data/silver/):
  respondents.parquet     one row per respondent, harmonised demographics / work / pay / GenAI attitudes
  tech_usage.parquet      one row per respondent x technology: used / wanted flags (canonical names)
  answered.parquet        which technology questions each respondent answered (share denominators)
  tech_year_group.parquet which question group(s) carried each technology each year
  roles.parquet           respondent x developer role (multi-select years keep every role)
  ai_tasks.parquet        respondent x development task they currently use AI for (2023+)
  label_coverage.parquet  every raw technology label with its mapping outcome (data-quality evidence)
  countries.parquet       raw country label -> ISO3, analysis region, income group, coordinates
"""

from __future__ import annotations

import time

import duckdb
import numpy as np
import pandas as pd

from .. import settings
from ..ingest.kaggle import raw_file
from . import parsers as P
from .geo import build_country_dim
from .schema import SCHEMAS, YearSchema, tech_columns
from .taxonomy import alias_frame, catalog, excluded_labels

DEV_ROLES_2018 = {
    "Full-stack developer", "Back-end developer", "Front-end developer", "Mobile developer",
    "Desktop/enterprise developer", "Embedded developer", "Game/graphics developer", "QA/test engineer",
    "DevOps/SRE", "Data scientist/ML engineer", "Data engineer", "Engineering manager", "Executive/founder",
}


def _load_raw(con: duckdb.DuckDBPyConnection, year: int) -> None:
    con.execute(f"""
        CREATE OR REPLACE TABLE raw AS
        SELECT * FROM read_csv('{raw_file(year)}', all_varchar=true, header=true,
                               nullstr=['NA', ''], max_line_size=10000000)""")


def _col(frame: pd.DataFrame, name: str | None) -> pd.Series:
    if name is None or name not in frame:
        return pd.Series([None] * len(frame), index=frame.index, dtype="object")
    return frame[name].astype("object")


def _respondents(con: duckdb.DuckDBPyConnection, schema: YearSchema) -> tuple[pd.DataFrame, pd.DataFrame]:
    wanted = {c for c in schema.cols.values() if c} | {schema.id}
    wanted |= set(schema.ai_task_block)
    select = ", ".join(f'"{c}"' for c in sorted(wanted))
    raw = con.execute(f"SELECT {select} FROM raw").df()
    c = schema.cols
    y = schema.year

    out = pd.DataFrame(index=raw.index)
    out["resp_key"] = y * 1_000_000 + pd.to_numeric(raw[schema.id]).astype("int64")
    out["survey_year"] = np.int16(y)
    out["country_raw"] = _col(raw, c["country"])
    out["employment"] = P.map_unique(_col(raw, c["employment"]), P.parse_employment)
    out["ed_level"] = P.map_unique(_col(raw, c["ed_level"]), P.parse_ed_level)
    out["org_size"] = P.map_unique(_col(raw, c["org_size"]), P.parse_org_size)
    out["remote_work"] = P.map_unique(_col(raw, c["remote"]), P.parse_remote)
    out["age_band"] = P.map_unique(_col(raw, c["age"]), P.parse_age)
    out["industry"] = P.map_unique(_col(raw, c["industry"]), P.parse_industry)

    out["years_code"] = P.map_unique(_col(raw, c["years_code"]), P.parse_years).astype("float64")
    out["years_pro"] = P.map_unique(_col(raw, c["years_pro"]), P.parse_years).astype("float64")
    out["work_exp"] = P.map_unique(_col(raw, c["work_exp"]), P.parse_years).astype("float64")
    out["exp_band"] = P.experience_band(out["years_code"])
    # One professional-tenure measure across all years: years coding professionally (2017-2024),
    # falling back to years of work experience in 2025 when the former was no longer asked.
    out["pro_tenure"] = out["years_pro"].fillna(out["work_exp"]) if c["years_pro"] is None else out["years_pro"]
    out["pro_tenure_source"] = "work_exp" if c["years_pro"] is None else "years_code_pro"

    # Roles (multi-select through 2022, single-select from 2023)
    subtype = _col(raw, c["web_dev_type"])
    roles = [P.parse_roles(v, s) for v, s in zip(_col(raw, c["dev_type"]), subtype, strict=True)]
    out["dev_role"] = [P.primary_role(r) for r in roles]
    out["n_roles"] = np.array([len(r) for r in roles], dtype="int16")
    role_rows = pd.DataFrame({"resp_key": np.repeat(out["resp_key"].to_numpy(), [len(r) for r in roles]),
                              "role": [x for r in roles for x in r]})
    role_rows["survey_year"] = np.int16(y)

    if c["main_branch"]:
        out["respondent_type"] = P.map_unique(_col(raw, c["main_branch"]), P.parse_main_branch)
        out["respondent_type_derived"] = False
    else:  # 2018: no MainBranch — derive from employment, student status and roles
        student = _col(raw, c["student"]).fillna("")
        employed = out["employment"].isin(["Full-time", "Part-time", "Independent"])
        dev = pd.Series([bool(set(r) & DEV_ROLES_2018) for r in roles], index=out.index)
        learner = student.str.startswith("Yes") | pd.Series([r == ["Student"] for r in roles], index=out.index)
        out["respondent_type"] = np.select(
            [employed & dev, learner, employed], ["Professional developer", "Learner", "Codes for work (non-dev)"],
            default="Other")
        out["respondent_type_derived"] = True

    comp = pd.to_numeric(_col(raw, c["comp"]), errors="coerce")
    out["comp_usd_raw"] = comp.where(comp > 0)

    # Generative AI attitudes (2023+)
    out["ai_use"] = P.map_unique(_col(raw, c["ai_select"]), P.parse_ai_use)
    out["ai_frequency"] = P.map_unique(_col(raw, c["ai_select"]), P.parse_ai_frequency)
    out["ai_sentiment"] = _col(raw, c["ai_sent"]).where(lambda s: s.isin(list(P.SENTIMENT_SCORE) + ["Unsure"]))
    out["ai_sentiment_score"] = out["ai_sentiment"].map(P.SENTIMENT_SCORE).astype("float64")
    out["ai_trust"] = _col(raw, c["ai_trust"]).where(lambda s: s.isin(list(P.TRUST_SCORE)))
    out["ai_trust_score"] = out["ai_trust"].map(P.TRUST_SCORE).astype("float64")
    out["ai_complex"] = _col(raw, c["ai_complex"])
    out["ai_complex_score"] = out["ai_complex"].map(P.COMPLEX_SCORE).astype("float64")
    out["ai_threat"] = P.map_unique(_col(raw, c["ai_threat"]), P.parse_ai_threat)
    out["ai_agents"] = P.map_unique(_col(raw, c["ai_agents"]), P.parse_ai_agents)

    task_rows = []
    if schema.ai_tasks:
        block = raw[list(schema.ai_task_block)].notna().any(axis=1)
        out["ai_task_answered"] = block
        for colname in schema.ai_tasks:
            exploded = raw[[schema.id, colname]].dropna()
            exploded = exploded.assign(task=exploded[colname].str.split(";")).explode("task")
            exploded["task"] = exploded["task"].str.strip().map(P.AI_TASK_MAP)
            exploded = exploded.dropna(subset=["task"])
            task_rows.append(pd.DataFrame({"resp_key": y * 1_000_000 + pd.to_numeric(exploded[schema.id]).astype("int64"),
                                           "task": exploded["task"].to_numpy()}))
    else:
        out["ai_task_answered"] = False
    tasks = (pd.concat(task_rows).drop_duplicates() if task_rows
             else pd.DataFrame({"resp_key": pd.Series(dtype="int64"), "task": pd.Series(dtype="object")}))
    tasks["survey_year"] = np.int16(y)
    return out, role_rows, tasks


def _technology(con: duckdb.DuckDBPyConnection, schema: YearSchema) -> dict[str, pd.DataFrame]:
    y = schema.year
    parts = []
    for group, used_col, want_col in tech_columns(schema):
        for side, col in (("used", used_col), ("want", want_col)):
            if not col:
                continue
            parts.append(f"""
                SELECT {y} * 1000000 + CAST("{schema.id}" AS BIGINT) AS resp_key, '{group}' AS field_group,
                       '{side}' AS side, trim(label) AS raw_label
                FROM (SELECT "{schema.id}", unnest(string_split("{col}", ';')) AS label FROM raw WHERE "{col}" IS NOT NULL)
                WHERE trim(label) <> ''""")
    con.execute("CREATE OR REPLACE TEMP TABLE exploded AS " + " UNION ALL ".join(parts))

    answered = con.execute(f"""
        SELECT DISTINCT resp_key, CAST({y} AS SMALLINT) AS survey_year, field_group, side FROM exploded""").df()

    coverage = con.execute(f"""
        SELECT CAST({y} AS SMALLINT) AS survey_year, e.field_group, e.side, e.raw_label, count(*) AS mentions,
               any_value(a.tech) AS tech
        FROM exploded e LEFT JOIN aliases a ON a.field_group = e.field_group AND a.raw_label = e.raw_label
        GROUP BY ALL""").df()

    usage = con.execute(f"""
        SELECT e.resp_key, CAST({y} AS SMALLINT) AS survey_year, a.tech,
               bool_or(e.side = 'used') AS used, bool_or(e.side = 'want') AS wanted
        FROM exploded e JOIN aliases a ON a.field_group = e.field_group AND a.raw_label = e.raw_label
        GROUP BY ALL""").df()

    tech_groups = con.execute(f"""
        SELECT DISTINCT CAST({y} AS SMALLINT) AS survey_year, a.tech, e.field_group
        FROM exploded e JOIN aliases a ON a.field_group = e.field_group AND a.raw_label = e.raw_label""").df()
    return {"answered": answered, "coverage": coverage, "usage": usage, "tech_groups": tech_groups}


def build_silver(years: list[int] | None = None) -> dict[str, int]:
    settings.ensure_dirs()
    years = years or settings.survey_years()
    con = duckdb.connect()
    con.register("aliases", alias_frame())
    frames: dict[str, list[pd.DataFrame]] = {k: [] for k in
                                             ("respondents", "roles", "ai_tasks", "answered", "coverage", "usage", "tech_groups")}
    for year in years:
        t0 = time.time()
        schema = SCHEMAS[year]
        _load_raw(con, year)
        resp, roles, tasks = _respondents(con, schema)
        tech = _technology(con, schema)
        frames["respondents"].append(resp)
        frames["roles"].append(roles)
        frames["ai_tasks"].append(tasks)
        for key in ("answered", "coverage", "usage", "tech_groups"):
            frames[key].append(tech[key])
        print(f"  [silver] {year}: {len(resp):>6,} respondents  {len(tech['usage']):>9,} tech rows  "
              f"({time.time() - t0:.1f}s)")

    respondents = pd.concat(frames["respondents"], ignore_index=True)
    countries = build_country_dim(respondents["country_raw"].dropna().unique())
    coverage = pd.concat(frames["coverage"], ignore_index=True)
    excluded = excluded_labels()
    coverage["status"] = np.where(coverage["tech"].notna(), "mapped",
                                  np.where(coverage["raw_label"].isin(excluded), "excluded", "unmapped"))

    outputs = {
        "respondents": respondents,
        "roles": pd.concat(frames["roles"], ignore_index=True),
        "ai_tasks": pd.concat(frames["ai_tasks"], ignore_index=True),
        "answered": pd.concat(frames["answered"], ignore_index=True),
        "tech_usage": pd.concat(frames["usage"], ignore_index=True),
        "tech_year_group": pd.concat(frames["tech_groups"], ignore_index=True),
        "label_coverage": coverage,
        "countries": countries,
        "tech_catalog": catalog(),
    }
    counts = {}
    for name, frame in outputs.items():
        con.register("_out", frame)
        con.execute(f"COPY (SELECT * FROM _out) TO '{settings.SILVER_DIR / (name + '.parquet')}' "
                    "(FORMAT parquet, COMPRESSION zstd)")
        con.unregister("_out")
        counts[name] = len(frame)
    unmapped = coverage[coverage.status == "unmapped"].groupby("raw_label").mentions.sum().sort_values(ascending=False)
    share = coverage.loc[coverage.status == "mapped", "mentions"].sum() / coverage.loc[coverage.status != "excluded", "mentions"].sum()
    print(f"  [silver] label mapping coverage: {share:.2%} of in-scope mentions; "
          f"{len(unmapped)} unmapped labels{': ' + ', '.join(unmapped.index[:12]) if len(unmapped) else ''}")
    return counts
