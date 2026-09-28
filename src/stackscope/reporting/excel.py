"""Excel analyst workbook — a live, formula-driven pack for business users.

Nothing on the Dashboard or Summary sheets is pasted as a value: KPIs, the trend table behind the
chart and every summary cell are Excel formulas (INDEX/MATCH, CHOOSE, SUMIFS, COUNTIFS, AVERAGEIFS,
MAXIFS/MINIFS, IFERROR) with data validation and conditional formatting, so the workbook keeps
working when the data sheets are refreshed. A PivotTable-ready respondent sheet is included.
(MAXIFS/MINIFS need Excel 2019+, Microsoft 365 or LibreOffice.)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name, xl_rowcol_to_cell

from .. import settings

INK = "#0F2A33"
SOFT = "#D8EAEE"
GRID = "#D9E0DE"
METRICS = ["adoption", "desire", "retention", "attraction"]


def _frames(con) -> dict[str, pd.DataFrame]:
    q = lambda sql: con.execute(sql).df()  # noqa: E731
    tech = q("""SELECT tech, category_label AS category, survey_year AS year, share_used_w AS adoption,
                       share_used_w_lo AS adoption_lo, share_used_w_hi AS adoption_hi, share_wanted_w AS desire,
                       retention_w AS retention, attraction_w AS attraction, base_n AS answered
                FROM mart.tech_year ORDER BY tech, year""")
    tech.insert(0, "key", tech.tech + "|" + tech.year.astype(str))
    return {
        "tech": tech,
        "pay": q("""SELECT c.country, b.segment AS iso3, c.region, b.n AS salaries, b.p25_usd, b.median_usd, b.p75_usd,
                           b.median_ppp FROM mart.pay_benchmark b JOIN core.dim_country c ON c.iso3 = b.segment
                    WHERE b.cut = 'country' AND b.survey_year = 2025 ORDER BY b.median_usd DESC"""),
        "premium": q("""SELECT scope, tech, category, premium, premium_lo, premium_hi, raw_premium, q_value, significant, n_users
                        FROM mart.skill_premium ORDER BY scope, premium DESC"""),
        "findings": q("SELECT rank, theme, headline, detail FROM mart.key_findings ORDER BY rank"),
        "respondents": q("""SELECT r.survey_year AS year, c.country, r.region, r.respondent_type, r.dev_role AS role,
                                   r.exp_band AS experience, r.org_size, r.remote_work, r.ed_level AS education,
                                   r.ai_use, r.ai_trust, CASE WHEN r.in_pay_benchmark THEN round(r.comp_usd) END AS pay_usd,
                                   CASE WHEN r.in_pay_benchmark THEN round(r.comp_ppp) END AS pay_ppp
                            FROM core.fact_respondent r LEFT JOIN core.dim_country c USING (iso3)
                            WHERE r.survey_year = 2025"""),
    }


def build(con, path: Path | None = None) -> Path:
    data = _frames(con)
    tech = data["tech"]
    path = path or settings.REPORTS_DIR / "StackScope_Analyst_Pack.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    # use_future_functions writes MAXIFS/MINIFS with the _xlfn. prefix Excel requires (else #NAME?)
    wb = xlsxwriter.Workbook(str(path), {"nan_inf_to_errors": True, "use_future_functions": True})
    wb.set_properties({"title": "StackScope analyst pack", "subject": "Developer technology market intelligence, 2017-2025"})

    # sheets are created in presentation order, then filled
    sheets = {name: wb.add_worksheet(name) for name in
              ["Dashboard", "Summary", "Findings", "README", "TechData", "PayByCountry", "SkillPremium", "PivotReady_2025", "Lists"]}

    fmt = lambda **kw: wb.add_format(kw)  # noqa: E731
    f = {
        "title": fmt(bold=True, font_size=20, font_color=INK),
        "h2": fmt(bold=True, font_size=13, font_color=INK),
        "muted": fmt(font_color="#48595F"),
        "hdr": fmt(bold=True, bg_color=SOFT, font_color=INK, bottom=1, border_color=GRID),
        "pct": fmt(num_format="0.0%"), "pct0": fmt(num_format="0%"), "usd": fmt(num_format="$#,##0"), "int": fmt(num_format="#,##0"),
        "kpi_label": fmt(font_color="#48595F", font_size=10),
        "kpi_pct": fmt(bold=True, font_size=18, font_color=INK, num_format="0.0%"),
        "kpi_num": fmt(bold=True, font_size=18, font_color=INK, num_format="#,##0"),
        "kpi_pp": fmt(bold=True, font_size=18, font_color=INK, num_format="+0.0;-0.0"),
        "kpi_txt": fmt(bold=True, font_size=14, font_color=INK),
        "input": fmt(bold=True, bg_color="#FFF7D6", border=1, border_color="#E5C35C", font_color=INK),
        "wrap": fmt(text_wrap=True, valign="top"),
    }

    # ------------------------------------------------------------------ data sheets as Excel tables
    def fill_table(name: str, frame: pd.DataFrame, formats: dict, widths: dict | None = None) -> int:
        ws = sheets[name]
        frame = frame.copy()
        for col in frame.columns:
            if frame[col].dtype == bool:
                frame[col] = frame[col].map({True: "Yes", False: "No"})
        rows = frame.astype(object).where(frame.notna(), None).values.tolist()
        ws.add_table(0, 0, len(rows), len(frame.columns) - 1, {
            "name": f"t_{name}", "style": "Table Style Light 9", "data": rows,
            "columns": [{"header": c, "format": formats.get(c)} for c in frame.columns],
        })
        for i, c in enumerate(frame.columns):
            ws.set_column(i, i, (widths or {}).get(c, max(10, min(34, len(c) + 4))))
        ws.freeze_panes(1, 0)
        return len(rows)

    pct_cols = {c: f["pct"] for c in ("adoption", "adoption_lo", "adoption_hi", "desire", "retention", "attraction")}
    n_tech = fill_table("TechData", tech, {**pct_cols, "answered": f["int"]}, {"key": 26, "tech": 24, "category": 26})
    fill_table("PayByCountry", data["pay"], {"p25_usd": f["usd"], "median_usd": f["usd"], "p75_usd": f["usd"],
                                             "median_ppp": f["usd"], "salaries": f["int"]}, {"country": 24, "region": 28})
    n_prem = fill_table("SkillPremium", data["premium"], {"premium": f["pct"], "premium_lo": f["pct"], "premium_hi": f["pct"],
                                                          "raw_premium": f["pct"], "n_users": f["int"]}, {"scope": 16, "tech": 22})
    sheets["SkillPremium"].conditional_format(1, 3, n_prem, 3, {"type": "3_color_scale", "min_color": "#E98A89",
                                                                 "mid_color": "#F3F6F5", "max_color": "#86B6EF",
                                                                 "mid_type": "num", "mid_value": 0})
    fill_table("PivotReady_2025", data["respondents"], {"pay_usd": f["usd"], "pay_ppp": f["usd"]}, {"country": 22, "role": 28})

    lists = sheets["Lists"]
    techs = sorted(tech.tech.unique())
    lists.write_column(0, 0, ["Technology", *techs])
    lists.write_column(0, 1, ["Metric", *METRICS])
    wb.define_name("TechList", f"=Lists!$A$2:$A${len(techs) + 1}")
    wb.define_name("MetricList", f"=Lists!$B$2:$B${len(METRICS) + 1}")
    lists.hide()

    last = n_tech + 1
    col = {c: xl_col_to_name(i) for i, c in enumerate(tech.columns)}
    rng = lambda c: f"TechData!${col[c]}$2:${col[c]}${last}"  # noqa: E731

    # ------------------------------------------------------------------ Dashboard: inputs, KPI formulas, live chart
    ws = sheets["Dashboard"]
    ws.hide_gridlines(2)
    ws.set_column("A:A", 3)
    ws.set_column("B:L", 13)
    ws.write("B2", "StackScope technology dashboard", f["title"])
    ws.write("B3", "Pick a technology and a metric in the yellow cells; every number and the chart recalculate from TechData.", f["muted"])
    ws.write("B5", "Technology", f["kpi_label"])
    ws.write("D5", "Metric", f["kpi_label"])
    ws.write("B6", "Python", f["input"])
    ws.write("D6", "adoption", f["input"])
    ws.data_validation("B6", {"validate": "list", "source": "=TechList", "error_message": "Pick a technology from the list."})
    ws.data_validation("D6", {"validate": "list", "source": "=MetricList"})
    ws.write_formula("F6", '=B6&" – "&D6', f["muted"])     # chart title helper
    ws.write_formula("H6", f'=MAXIFS({rng("year")},{rng("tech")},$B$6)', f["muted"])  # latest wave for the tech
    ws.write_formula("J6", f'=MINIFS({rng("year")},{rng("tech")},$B$6)', f["muted"])  # first wave for the tech
    ws.write("H5", "Latest wave", f["kpi_label"])
    ws.write("J5", "First wave", f["kpi_label"])

    lookup = lambda field, year_cell: f'INDEX({rng(field)},MATCH($B$6&"|"&{year_cell},{rng("key")},0))'  # noqa: E731
    ws.write("B8", "Adoption, latest wave", f["kpi_label"])
    ws.write_formula("B9", f'=IFERROR({lookup("adoption", "$H$6")},"n/a")', f["kpi_pct"])
    ws.write("E8", "Retention, latest wave", f["kpi_label"])
    ws.write_formula("E9", f'=IFERROR({lookup("retention", "$H$6")},"n/a")', f["kpi_pct"])
    ws.write("H8", "Adoption change since first wave (pp)", f["kpi_label"])
    ws.write_formula("H9", f'=IFERROR(100*({lookup("adoption", "$H$6")}-{lookup("adoption", "$J$6")}),"n/a")', f["kpi_pp"])
    ws.write("K8", "Waves observed", f["kpi_label"])
    ws.write_formula("K9", f'=COUNTIFS({rng("tech")},$B$6)', f["kpi_num"])

    for i, h in enumerate(["Year", "Value", "Low (95%)", "High (95%)"]):
        ws.write(11, 1 + i, h, f["hdr"])
    years = sorted(int(y) for y in tech.year.unique())
    choose = ",".join(rng(m) for m in METRICS)
    for i, year in enumerate(years):
        r = 12 + i
        ws.write_number(r, 1, year)
        key = f'$B$6&"|"&{xl_rowcol_to_cell(r, 1)}'
        ws.write_formula(r, 2, f'=IFERROR(INDEX(CHOOSE(MATCH($D$6,MetricList,0),{choose}),MATCH({key},{rng("key")},0)),NA())', f["pct"])
        ws.write_formula(r, 3, f'=IF($D$6="adoption",IFERROR(INDEX({rng("adoption_lo")},MATCH({key},{rng("key")},0)),NA()),NA())', f["pct"])
        ws.write_formula(r, 4, f'=IF($D$6="adoption",IFERROR(INDEX({rng("adoption_hi")},MATCH({key},{rng("key")},0)),NA()),NA())', f["pct"])
    end = 12 + len(years) - 1
    ws.conditional_format(12, 2, end, 2, {"type": "data_bar", "bar_color": "#86B6EF", "bar_solid": True})

    chart = wb.add_chart({"type": "line"})
    chart.add_series({"name": "Value", "categories": ["Dashboard", 12, 1, end, 1], "values": ["Dashboard", 12, 2, end, 2],
                      "line": {"color": "#2A78D6", "width": 2.25},
                      "marker": {"type": "circle", "size": 6, "fill": {"color": "#2A78D6"}, "border": {"color": "#FFFFFF"}}})
    for c, name in ((3, "Low (95%)"), (4, "High (95%)")):
        chart.add_series({"name": name, "categories": ["Dashboard", 12, 1, end, 1], "values": ["Dashboard", 12, c, end, c],
                          "line": {"color": "#9EC5F4", "width": 1}, "marker": {"type": "none"}})
    chart.set_title({"name": "=Dashboard!$F$6", "name_font": {"size": 12, "color": INK}})
    chart.set_y_axis({"num_format": "0%", "major_gridlines": {"visible": True, "line": {"color": GRID}}, "line": {"none": True}})
    chart.set_x_axis({"line": {"color": GRID}})
    chart.set_legend({"position": "bottom"})
    chart.show_na_as_empty_cell()
    chart.set_size({"width": 640, "height": 310})
    ws.insert_chart("G12", chart)

    # ------------------------------------------------------------------ Summary: conditional aggregation formulas
    ss = sheets["Summary"]
    ss.hide_gridlines(2)
    ss.set_column("A:A", 3)
    ss.set_column("B:B", 30)
    ss.set_column("C:I", 17)
    ss.write("B2", "Category summary, latest wave", f["title"])
    ss.write("B3", "Every cell below is a COUNTIFS / AVERAGEIFS / MAXIFS / INDEX-MATCH formula over TechData.", f["muted"])
    ss.write("B5", "Each category is summarised at its own latest wave (some questions were not asked in every year).", f["muted"])
    headers = ["Category", "Latest wave", "Technologies", "Avg adoption", "Avg retention", "Top adoption", "Leader", "Retention above 50%"]
    for i, h in enumerate(headers):
        ss.write(6, 1 + i, h, f["hdr"])
    cats = sorted(tech.category.unique())
    for i, cat in enumerate(cats):
        r = 7 + i
        c_ = xl_rowcol_to_cell(r, 1, col_abs=True)
        y_ = xl_rowcol_to_cell(r, 2, col_abs=True)
        ss.write(r, 1, cat)
        ss.write_formula(r, 2, f'=MAXIFS({rng("year")},{rng("category")},{c_})')
        ss.write_formula(r, 3, f'=COUNTIFS({rng("category")},{c_},{rng("year")},{y_})', f["int"])
        ss.write_formula(r, 4, f'=IFERROR(AVERAGEIFS({rng("adoption")},{rng("category")},{c_},{rng("year")},{y_}),"")', f["pct"])
        ss.write_formula(r, 5, f'=IFERROR(AVERAGEIFS({rng("retention")},{rng("category")},{c_},{rng("year")},{y_}),"")', f["pct"])
        ss.write_formula(r, 6, f'=IFERROR(MAXIFS({rng("adoption")},{rng("category")},{c_},{rng("year")},{y_}),"")', f["pct"])
        ss.write_formula(r, 7, (f'=IFERROR(INDEX({rng("tech")},MATCH(1,INDEX(({rng("category")}={c_})*({rng("year")}={y_})*'
                                f'({rng("adoption")}={xl_rowcol_to_cell(r, 6)}),0),0)),"")'))
        ss.write_formula(r, 8, f'=IFERROR(COUNTIFS({rng("category")},{c_},{rng("year")},{y_},{rng("retention")},">0.5")/{xl_rowcol_to_cell(r, 3)},"")', f["pct0"])
    ss.conditional_format(7, 5, 7 + len(cats) - 1, 5, {"type": "2_color_scale", "min_color": "#F3F6F5", "max_color": "#6DA7EC"})

    # ------------------------------------------------------------------ Findings & README
    wf = sheets["Findings"]
    wf.set_column("A:A", 4)
    wf.set_column("B:B", 16)
    wf.set_column("C:C", 60)
    wf.set_column("D:D", 95)
    wf.write("B2", "Key findings", f["title"])
    for i, h in enumerate(["#", "Theme", "Headline", "Detail"]):
        wf.write(3, i, h, f["hdr"])
    for i, row in enumerate(data["findings"].itertuples()):
        wf.write_row(4 + i, 0, [row.rank, row.theme, row.headline, row.detail], f["wrap"])
        wf.set_row(4 + i, 48)

    wr = sheets["README"]
    wr.set_column("B:B", 115)
    lines = [
        ("StackScope analyst pack", "title"),
        ("Developer technology market intelligence from nine Stack Overflow Developer Surveys (2017–2025, 664,042 responses).", "muted"),
        ("", None),
        ("Sheets", "h2"),
        ("Dashboard: choose a technology and a metric (yellow cells); KPIs, the trend table and the chart are live formulas.", None),
        ("Summary: category roll-up for the latest wave built from COUNTIFS, AVERAGEIFS, MAXIFS and INDEX-MATCH.", None),
        ("Findings: the pipeline's evidence-backed headlines.", None),
        ("TechData: technology x year KPIs (composition-weighted shares, 95% intervals, retention, attraction).", None),
        ("PayByCountry and SkillPremium: 2025 pay benchmarks and regression-adjusted skill premiums.", None),
        ("PivotReady_2025: one row per 2025 respondent. Insert > PivotTable to slice pay or AI adoption by any field.", None),
        ("", None),
        ("Definitions", "h2"),
        ("Adoption: share of respondents who answered the question and used the technology in the past year (weighted).", None),
        ("Retention: share of current users who want to keep using it next year. Attraction: share of non-users who want to start.", None),
        ("Pay: full-time professional developers, cleaned per market; USD, constant-2025 USD, or PPP international dollars.", None),
        ("", None),
        ("Sources: Stack Overflow Developer Survey (ODbL), World Bank WDI, FRED CPI-U. Independent project, not affiliated with Gartner or Stack Overflow.", "muted"),
    ]
    for i, (text, style) in enumerate(lines):
        if style:
            wr.write(1 + i, 1, text, f[style])
        else:
            wr.write(1 + i, 1, text)

    ws.activate()
    wb.close()
    return path
