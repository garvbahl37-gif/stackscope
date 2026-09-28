"""Where every harmonised field lives in each year's raw file.

`None` means the question was not asked that year. Technology questions are listed per question
group as (used_column, want_column).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class YearSchema:
    year: int
    id: str
    cols: dict[str, str | None]
    tech: dict[str, tuple[str, str | None] | list[tuple[str, str | None]]]
    ai_tasks: tuple[str, ...] = ()           # columns listing tasks respondents currently use AI for
    ai_task_block: tuple[str, ...] = ()      # all columns of the AI-task grid (denominator)
    notes: list[str] = field(default_factory=list)


_BASE = dict(main_branch=None, employment=None, country="Country", ed_level=None, org_size=None, remote=None,
             years_code=None, years_pro=None, work_exp=None, age=None, dev_type=None, web_dev_type=None,
             comp=None, industry=None, ai_select=None, ai_sent=None, ai_trust=None, ai_complex=None,
             ai_threat=None, ai_agents=None, student=None)


def _cols(**overrides) -> dict[str, str | None]:
    return {**_BASE, **overrides}


_WW = {  # 2021-2024 naming convention
    "language": ("LanguageHaveWorkedWith", "LanguageWantToWorkWith"),
    "database": ("DatabaseHaveWorkedWith", "DatabaseWantToWorkWith"),
    "platform": ("PlatformHaveWorkedWith", "PlatformWantToWorkWith"),
    "webframe": ("WebframeHaveWorkedWith", "WebframeWantToWorkWith"),
    "misctech": ("MiscTechHaveWorkedWith", "MiscTechWantToWorkWith"),
    "toolstech": ("ToolsTechHaveWorkedWith", "ToolsTechWantToWorkWith"),
    "ide": ("NEWCollabToolsHaveWorkedWith", "NEWCollabToolsWantToWorkWith"),
}

SCHEMAS: dict[int, YearSchema] = {
    2017: YearSchema(
        2017, "Respondent",
        _cols(main_branch="Professional", employment="EmploymentStatus", ed_level="FormalEducation",
              org_size="CompanySize", remote="HomeRemote", years_code="YearsProgram", years_pro="YearsCodedJob",
              dev_type="DeveloperType", web_dev_type="WebDeveloperType", comp="Salary"),
        {"language": ("HaveWorkedLanguage", "WantWorkLanguage"), "framework": ("HaveWorkedFramework", "WantWorkFramework"),
         "database": ("HaveWorkedDatabase", "WantWorkDatabase"), "platform": ("HaveWorkedPlatform", "WantWorkPlatform"),
         "ide": ("IDE", None)},
        notes=["Salary is base salary in USD, top-coded near $200k by the publisher."],
    ),
    2018: YearSchema(
        2018, "Respondent",
        _cols(employment="Employment", ed_level="FormalEducation", org_size="CompanySize", years_code="YearsCoding",
              years_pro="YearsCodingProf", age="Age", dev_type="DevType", comp="ConvertedSalary", student="Student"),
        {"language": ("LanguageWorkedWith", "LanguageDesireNextYear"), "framework": ("FrameworkWorkedWith", "FrameworkDesireNextYear"),
         "database": ("DatabaseWorkedWith", "DatabaseDesireNextYear"), "platform": ("PlatformWorkedWith", "PlatformDesireNextYear"),
         "ide": ("IDE", None)},
        notes=["No MainBranch question — respondent type is derived from employment, student status and roles."],
    ),
    2019: YearSchema(
        2019, "Respondent",
        _cols(main_branch="MainBranch", employment="Employment", ed_level="EdLevel", org_size="OrgSize", remote="WorkRemote",
              years_code="YearsCode", years_pro="YearsCodePro", age="Age", dev_type="DevType", comp="ConvertedComp"),
        {"language": ("LanguageWorkedWith", "LanguageDesireNextYear"), "database": ("DatabaseWorkedWith", "DatabaseDesireNextYear"),
         "platform": ("PlatformWorkedWith", "PlatformDesireNextYear"), "webframe": ("WebFrameWorkedWith", "WebFrameDesireNextYear"),
         "misctech": ("MiscTechWorkedWith", "MiscTechDesireNextYear"), "ide": ("DevEnviron", None)},
    ),
    2020: YearSchema(
        2020, "Respondent",
        _cols(main_branch="MainBranch", employment="Employment", ed_level="EdLevel", org_size="OrgSize",
              years_code="YearsCode", years_pro="YearsCodePro", age="Age", dev_type="DevType", comp="ConvertedComp"),
        {"language": ("LanguageWorkedWith", "LanguageDesireNextYear"), "database": ("DatabaseWorkedWith", "DatabaseDesireNextYear"),
         "platform": ("PlatformWorkedWith", "PlatformDesireNextYear"), "webframe": ("WebframeWorkedWith", "WebframeDesireNextYear"),
         "misctech": ("MiscTechWorkedWith", "MiscTechDesireNextYear")},
        notes=["No IDE question (NEWCollabTools asked about collaboration suites this year)."],
    ),
    2021: YearSchema(
        2021, "ResponseId",
        _cols(main_branch="MainBranch", employment="Employment", ed_level="EdLevel", org_size="OrgSize",
              years_code="YearsCode", years_pro="YearsCodePro", age="Age", dev_type="DevType", comp="ConvertedCompYearly"),
        dict(_WW),
    ),
    2022: YearSchema(
        2022, "ResponseId",
        _cols(main_branch="MainBranch", employment="Employment", ed_level="EdLevel", org_size="OrgSize", remote="RemoteWork",
              years_code="YearsCode", years_pro="YearsCodePro", work_exp="WorkExp", age="Age", dev_type="DevType",
              comp="ConvertedCompYearly"),
        dict(_WW),
    ),
    2023: YearSchema(
        2023, "ResponseId",
        _cols(main_branch="MainBranch", employment="Employment", ed_level="EdLevel", org_size="OrgSize", remote="RemoteWork",
              years_code="YearsCode", years_pro="YearsCodePro", work_exp="WorkExp", age="Age", dev_type="DevType",
              comp="ConvertedCompYearly", industry="Industry", ai_select="AISelect", ai_sent="AISent",
              # Publisher defect: in 2023 the AIAcc and AIBen columns are swapped (validated on value domains).
              ai_trust="AIBen"),
        # 2023 split AI tools over two questions; they are pooled into one "ai" question so every AI
        # tool shares the same denominator (respondents who answered either).
        {**_WW, "ai": [("AISearchHaveWorkedWith", "AISearchWantToWorkWith"),
                       ("AIDevHaveWorkedWith", "AIDevWantToWorkWith")]},
        ai_tasks=("AIToolCurrently Using",),
        ai_task_block=("AIToolCurrently Using", "AIToolInterested in Using", "AIToolNot interested in Using"),
        notes=["AIAcc/AIBen columns are swapped in the published file; trust is read from AIBen.",
               "DevType became single-select."],
    ),
    2024: YearSchema(
        2024, "ResponseId",
        _cols(main_branch="MainBranch", employment="Employment", ed_level="EdLevel", org_size="OrgSize", remote="RemoteWork",
              years_code="YearsCode", years_pro="YearsCodePro", work_exp="WorkExp", age="Age", dev_type="DevType",
              comp="ConvertedCompYearly", industry="Industry", ai_select="AISelect", ai_sent="AISent", ai_trust="AIAcc",
              ai_complex="AIComplex", ai_threat="AIThreat"),
        {**_WW, "ai": ("AISearchDevHaveWorkedWith", "AISearchDevWantToWorkWith")},
        ai_tasks=("AIToolCurrently Using",),
        ai_task_block=("AIToolCurrently Using", "AIToolInterested in Using", "AIToolNot interested in Using"),
    ),
    2025: YearSchema(
        2025, "ResponseId",
        _cols(main_branch="MainBranch", employment="Employment", ed_level="EdLevel", org_size="OrgSize", remote="RemoteWork",
              years_code="YearsCode", work_exp="WorkExp", age="Age", dev_type="DevType", comp="ConvertedCompYearly",
              industry="Industry", ai_select="AISelect", ai_sent="AISent", ai_trust="AIAcc", ai_complex="AIComplex",
              ai_threat="AIThreat", ai_agents="AIAgents"),
        {"language": ("LanguageHaveWorkedWith", "LanguageWantToWorkWith"),
         "database": ("DatabaseHaveWorkedWith", "DatabaseWantToWorkWith"),
         "platform": ("PlatformHaveWorkedWith", "PlatformWantToWorkWith"),
         "webframe": ("WebframeHaveWorkedWith", "WebframeWantToWorkWith"),
         "ide": ("DevEnvsHaveWorkedWith", "DevEnvsWantToWorkWith"),
         "ai_models": ("AIModelsHaveWorkedWith", "AIModelsWantToWorkWith")},
        ai_tasks=("AIToolCurrently mostly AI", "AIToolCurrently partially AI"),
        ai_task_block=("AIToolCurrently mostly AI", "AIToolCurrently partially AI", "AIToolPlan to mostly use AI",
                       "AIToolPlan to partially use AI", "AIToolDon't plan to use AI for this task"),
        notes=["YearsCodePro dropped — WorkExp (years of work experience) is the professional-tenure proxy.",
               "Platform question now also lists DevOps and build tools (Docker, npm, Terraform...).",
               "Employment no longer distinguishes full- and part-time."],
    ),
}

FIELD_GROUPS = ["language", "database", "platform", "webframe", "misctech", "toolstech", "framework", "ide",
                "ai", "ai_models"]


def tech_columns(schema: YearSchema) -> list[tuple[str, str, str | None]]:
    """Flatten a year's technology questions into (group, used_column, want_column) triples."""
    out = []
    for group, spec in schema.tech.items():
        for used, want in (spec if isinstance(spec, list) else [spec]):
            out.append((group, used, want))
    return out
