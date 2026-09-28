"""Value-level harmonisation rules.

Every function maps one raw survey answer (any year) to a canonical value. They are pure and
vectorised through `map_unique`, which evaluates each distinct raw label once — the surveys have
600k+ rows but only a few hundred distinct labels per field.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable

import numpy as np
import pandas as pd

NAN = float("nan")


def is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or value is pd.NA


def map_unique(series: pd.Series, fn: Callable) -> pd.Series:
    """Apply `fn` once per distinct value, then broadcast (orders of magnitude faster than .map(fn))."""
    uniques = series.dropna().unique()
    lookup = {u: fn(u) for u in uniques}
    return series.map(lookup)


def split_multi(value) -> list[str]:
    """Multi-select answers are ';'-delimited (2017 used '; ')."""
    if is_missing(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


# --------------------------------------------------------------------------------------------
# Experience
# --------------------------------------------------------------------------------------------
_RANGE_TO = re.compile(r"(\d+) to (\d+) years?")          # 2017: "1 to 2 years"
_RANGE_DASH = re.compile(r"(\d+)\s*-\s*(\d+) years?")     # 2018: "3-5 years"
_OR_MORE = re.compile(r"(\d+) or more years?")            # "20 or more years", "30 or more years"


def parse_years(value) -> float:
    """Convert every experience encoding used 2017-2025 to a numeric number of years.

    Ranges become midpoints; open-ended top bands get +2 years; "less than a year" becomes 0.5.
    """
    if is_missing(value):
        return NAN
    s = str(value).strip()
    if s in {"Less than a year", "Less than 1 year"}:
        return 0.5
    if s == "More than 50 years":
        return 51.0
    if m := _RANGE_TO.fullmatch(s):
        return (int(m[1]) + int(m[2])) / 2
    if m := _RANGE_DASH.fullmatch(s):
        return (int(m[1]) + int(m[2])) / 2
    if m := _OR_MORE.fullmatch(s):
        return float(m[1]) + 2
    try:
        years = float(s)
    except ValueError:
        return NAN
    return years if 0 <= years <= 60 else NAN


EXP_BANDS = ["0-2", "3-5", "6-10", "11-20", "21+"]


def experience_band(years: pd.Series) -> pd.Series:
    bins = [-0.01, 2.99, 5.99, 10.99, 20.99, np.inf]
    return pd.cut(years, bins=bins, labels=EXP_BANDS).astype("object").where(years.notna(), None)


# --------------------------------------------------------------------------------------------
# Demographics
# --------------------------------------------------------------------------------------------
AGE_BANDS = ["Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]


def parse_age(value) -> str | None:
    if is_missing(value):
        return None
    s = str(value).strip()
    if s.startswith("Under 18"):
        return "Under 18"
    if s.startswith("65"):
        return "65+"
    if m := re.match(r"(\d+)\s*-\s*(\d+) years old", s):
        return f"{m[1]}-{m[2]}"
    try:
        age = float(s)  # 2019-2020 recorded exact age
    except ValueError:
        return None  # "Prefer not to say"
    if not 12 <= age <= 99:
        return None
    for lo, hi, label in [(0, 18, "Under 18"), (18, 25, "18-24"), (25, 35, "25-34"), (35, 45, "35-44"),
                          (45, 55, "45-54"), (55, 65, "55-64"), (65, 200, "65+")]:
        if lo <= age < hi:
            return label
    return None


ED_LEVELS = ["Primary", "Secondary", "Some college", "Associate", "Bachelor's", "Master's",
             "Doctoral/professional", "Other"]


def parse_ed_level(value) -> str | None:
    if is_missing(value):
        return None
    s = str(value).lower()
    rules = [
        ("bachelor", "Bachelor's"), ("master", "Master's"), ("some college", "Some college"),
        ("secondary", "Secondary"), ("associate", "Associate"), ("doctoral", "Doctoral/professional"),
        ("professional degree", "Doctoral/professional"), ("primary", "Primary"),
        ("never completed", "Primary"), ("something else", "Other"), ("other", "Other"),
    ]
    for key, label in rules:
        if key in s:
            return label
    return None  # "I prefer not to answer"


ORG_SIZES = ["<20", "20-99", "100-499", "500-999", "1,000-4,999", "5,000-9,999", "10,000+"]


def parse_org_size(value) -> str | None:
    if is_missing(value):
        return None
    s = str(value)
    if s.startswith(("Just me", "2-9", "2 to 9", "Fewer than 10", "10 to 19", "Less than 20")):
        return "<20"
    table = {"20 to 99": "20-99", "100 to 499": "100-499", "500 to 999": "500-999",
             "1,000 to 4,999": "1,000-4,999", "5,000 to 9,999": "5,000-9,999", "10,000 or more": "10,000+"}
    for key, label in table.items():
        if s.startswith(key):
            return label
    return None  # "I don't know" / "I prefer not to answer"


def parse_remote(value) -> str | None:
    """Collapse five different remote-work scales into Remote / Hybrid / In-person."""
    if is_missing(value):
        return None
    s = str(value).strip()
    if s.startswith(("All or almost all", "Fully remote")) or s == "Remote":
        return "Remote"
    if s in {"Never", "A few days each month", "Less than once per month / Never", "Full in-person", "In-person"}:
        return "In-person"
    if s.startswith(("Hybrid", "Less than half the time", "About half", "More than half", "Your choice")):
        return "Hybrid"
    return None  # "It's complicated"


# --------------------------------------------------------------------------------------------
# Employment and respondent type
# --------------------------------------------------------------------------------------------
_EMPLOYMENT_PRIORITY = [  # multi-select years (2022-24): keep the dominant status
    ("employed, full-time", "Full-time"), ("employed full-time", "Full-time"),
    ("independent contractor", "Independent"),
    ("employed, part-time", "Part-time"), ("employed part-time", "Part-time"),
    ("student", "Student"), ("not employed", "Not employed"), ("retired", "Retired"),
]


def parse_employment(value) -> str | None:
    if is_missing(value):
        return None
    s = str(value).lower()
    if s == "employed":  # 2025 no longer separates full- and part-time
        return "Full-time"
    for key, label in _EMPLOYMENT_PRIORITY:
        if key in s:
            return label
    return None


RESPONDENT_TYPES = ["Professional developer", "Codes for work (non-dev)", "Learner", "Hobbyist",
                    "Former developer", "Other"]


def parse_main_branch(value) -> str | None:
    if is_missing(value):
        return None
    s = str(value)
    if s in {"Professional developer", "I am a developer by profession"}:
        return "Professional developer"
    if s.startswith(("Professional non-developer", "I am not primarily a developer")):
        return "Codes for work (non-dev)"
    if s in {"Student", "I am a student who is learning to code", "I am learning to code"}:
        return "Learner"
    if s == "I code primarily as a hobby":
        return "Hobbyist"
    if s.startswith(("Used to be", "I used to be")):
        return "Former developer"
    return "Other"


# --------------------------------------------------------------------------------------------
# Developer roles
# --------------------------------------------------------------------------------------------
ROLE_MAP = {
    "Full-stack developer": "Full-stack developer", "Developer, full-stack": "Full-stack developer",
    "Full stack Web developer": "Full-stack developer",
    "Back-end developer": "Back-end developer", "Developer, back-end": "Back-end developer",
    "Back-end Web developer": "Back-end developer",
    "Front-end developer": "Front-end developer", "Developer, front-end": "Front-end developer",
    "Front-end Web developer": "Front-end developer",
    "Web developer": "Web developer (general)",
    "Mobile developer": "Mobile developer", "Developer, mobile": "Mobile developer",
    "Desktop applications developer": "Desktop/enterprise developer",
    "Desktop or enterprise applications developer": "Desktop/enterprise developer",
    "Developer, desktop or enterprise applications": "Desktop/enterprise developer",
    "Embedded applications/devices developer": "Embedded developer",
    "Embedded applications or devices developer": "Embedded developer",
    "Developer, embedded applications or devices": "Embedded developer",
    "Game or graphics developer": "Game/graphics developer", "Developer, game or graphics": "Game/graphics developer",
    "Graphics programming": "Game/graphics developer",
    "Quality assurance engineer": "QA/test engineer", "QA or test developer": "QA/test engineer",
    "Developer, QA or test": "QA/test engineer",
    "DevOps specialist": "DevOps/SRE", "DevOps engineer or professional": "DevOps/SRE",
    "Engineer, site reliability": "DevOps/SRE",
    "Cloud infrastructure engineer": "Cloud infrastructure engineer",
    "Data scientist": "Data scientist/ML engineer", "Machine learning specialist": "Data scientist/ML engineer",
    "Data scientist or machine learning specialist": "Data scientist/ML engineer",
    "AI/ML engineer": "Data scientist/ML engineer", "Developer, AI": "Data scientist/ML engineer",
    "Developer, AI apps or physical AI": "Data scientist/ML engineer", "Applied scientist": "Data scientist/ML engineer",
    "Engineer, data": "Data engineer", "Data engineer": "Data engineer",
    "Data or business analyst": "Data/business analyst", "Financial analyst or engineer": "Data/business analyst",
    "Engineering manager": "Engineering manager",
    "C-suite executive (CEO, CTO, etc.)": "Executive/founder", "Senior executive/VP": "Executive/founder",
    "Senior Executive (C-Suite, VP, etc.)": "Executive/founder", "Senior executive (C-suite, VP, etc.)": "Executive/founder",
    "Founder, technology or otherwise": "Executive/founder",
    "Product manager": "Product/project manager", "Project manager": "Product/project manager",
    "Architect, software or solutions": "Architect",
    "System administrator": "Sysadmin/DBA", "Systems administrator": "Sysadmin/DBA",
    "Database administrator": "Sysadmin/DBA", "Database administrator or engineer": "Sysadmin/DBA",
    "Security professional": "Security professional", "Cybersecurity or InfoSec professional": "Security professional",
    "Academic researcher": "Researcher/educator", "Educator": "Researcher/educator",
    "Educator or academic researcher": "Researcher/educator", "Scientist": "Researcher/educator",
    "Research & Development role": "Researcher/educator",
    "Designer": "Designer", "Graphic designer": "Designer", "UX, Research Ops or UI design professional": "Designer",
    "Student": "Student",
}

# Precedence used to pick one primary role in multi-select years (2017-2022). Title-like roles
# first (people tend to identify by title), then core developer roles, then adjacent roles.
ROLE_PRIORITY = [
    "Executive/founder", "Engineering manager", "Full-stack developer", "Back-end developer",
    "Front-end developer", "Mobile developer", "Desktop/enterprise developer", "Embedded developer",
    "Game/graphics developer", "Data scientist/ML engineer", "Data engineer", "DevOps/SRE",
    "Cloud infrastructure engineer", "QA/test engineer", "Web developer (general)", "Architect",
    "Security professional", "Data/business analyst", "Product/project manager", "Sysadmin/DBA",
    "Researcher/educator", "Designer", "Student", "Other",
]
_ROLE_RANK = {role: i for i, role in enumerate(ROLE_PRIORITY)}


def parse_roles(value, web_subtype=None) -> list[str]:
    roles = []
    for raw in split_multi(value):
        if raw == "Web developer" and not is_missing(web_subtype):
            raw = str(web_subtype)
        roles.append(ROLE_MAP.get(raw, "Other"))
    if "Back-end developer" in roles and "Front-end developer" in roles and "Full-stack developer" not in roles:
        roles.append("Full-stack developer")
    return sorted(set(roles), key=_ROLE_RANK.get)


def primary_role(roles: Iterable[str]) -> str | None:
    roles = list(roles)
    return roles[0] if roles else None  # parse_roles already sorts by precedence


# --------------------------------------------------------------------------------------------
# Generative-AI block (2023-2025)
# --------------------------------------------------------------------------------------------
def parse_ai_use(value) -> str | None:
    if is_missing(value):
        return None
    s = str(value)
    if s.startswith("Yes"):
        return "Using"
    if s.startswith("No, but I plan"):
        return "Planning"
    if s.startswith("No, and I don"):
        return "Not planning"
    return None


def parse_ai_frequency(value) -> str | None:
    if is_missing(value):
        return None
    s = str(value)
    for key, label in (("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly or less")):
        if key in s:
            return label
    return None


SENTIMENT_SCORE = {"Very favorable": 2, "Favorable": 1, "Indifferent": 0, "Unfavorable": -1, "Very unfavorable": -2}
TRUST_SCORE = {"Highly trust": 2, "Somewhat trust": 1, "Neither trust nor distrust": 0,
               "Somewhat distrust": -1, "Highly distrust": -2}
COMPLEX_SCORE = {"Very well at handling complex tasks": 2, "Good, but not great at handling complex tasks": 1,
                 "Neither good or bad at handling complex tasks": 0, "Bad at handling complex tasks": -1,
                 "Very poor at handling complex tasks": -2}


def parse_ai_threat(value) -> str | None:
    if is_missing(value):
        return None
    return {"Yes": "Yes", "No": "No", "I'm not sure": "Not sure"}.get(str(value))


def parse_ai_agents(value) -> str | None:
    if is_missing(value):
        return None
    s = str(value)
    if s.startswith("Yes, I use AI agents at work daily"):
        return "Daily"
    if s.startswith("Yes, I use AI agents at work weekly"):
        return "Weekly"
    if s.startswith("Yes"):
        return "Monthly or less"
    if "copilot/autocomplete" in s:
        return "Autocomplete only"
    if s.startswith("No, but I plan"):
        return "Planning"
    if s.startswith("No, and I don"):
        return "Not planning"
    return None


AI_TASK_MAP = {
    "Debugging and getting help": "Debugging", "Debugging or fixing code": "Debugging",
    "Documenting code": "Documenting code", "Creating or maintaining documentation": "Documenting code",
    "Learning about a codebase": "Learning a codebase", "Learning new concepts or technologies": "Learning new tech",
    "Writing code": "Writing code", "Testing code": "Testing code", "Search for answers": "Search for answers",
    "Generating content or synthetic data": "Generating content/data", "Project planning": "Project planning",
    "Committing and reviewing code": "Code review & commits", "Deployment and monitoring": "Deployment & monitoring",
    "Predictive analytics": "Predictive analytics", "Collaborating with teammates": "Collaboration",
}


# --------------------------------------------------------------------------------------------
# Industry (2023-2025)
# --------------------------------------------------------------------------------------------
INDUSTRY_MAP = {
    "Information Services, IT, Software Development, or other Technology": "Software & IT",
    "Software Development": "Software & IT", "Internet, Telecomm or Information Services": "Software & IT",
    "Computer Systems Design and Services": "Software & IT",
    "Financial Services": "Financial services", "Fintech": "Financial services",
    "Banking/Financial Services": "Financial services", "Insurance": "Financial services",
    "Manufacturing, Transportation, or Supply Chain": "Manufacturing & logistics",
    "Manufacturing": "Manufacturing & logistics", "Transportation, or Supply Chain": "Manufacturing & logistics",
    "Healthcare": "Healthcare", "Retail and Consumer Services": "Retail & consumer", "Wholesale": "Retail & consumer",
    "Higher Education": "Education", "Government": "Government",
    "Advertising Services": "Media & advertising", "Media & Advertising Services": "Media & advertising",
    "Oil & Gas": "Energy", "Energy": "Energy", "Legal Services": "Other",
}


def parse_industry(value) -> str | None:
    if is_missing(value):
        return None
    return INDUSTRY_MAP.get(str(value), "Other")
