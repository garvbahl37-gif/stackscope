import math

import pandas as pd
import pytest

from stackscope.harmonize import parsers as P


@pytest.mark.parametrize("raw, expected", [
    ("Less than a year", 0.5), ("Less than 1 year", 0.5), ("More than 50 years", 51.0),
    ("1 to 2 years", 1.5), ("20 or more years", 22.0),       # 2017 encodings
    ("0-2 years", 1.0), ("3-5 years", 4.0), ("30 or more years", 32.0),   # 2018 encodings
    ("7", 7.0), ("12.0", 12.0),                                # 2019+ numeric
])
def test_parse_years_all_encodings(raw, expected):
    assert P.parse_years(raw) == expected


@pytest.mark.parametrize("raw", [None, float("nan"), "NA", "not a number", "-3", "99"])
def test_parse_years_rejects_invalid(raw):
    assert math.isnan(P.parse_years(raw))


def test_experience_band_edges():
    bands = P.experience_band(pd.Series([0.5, 2.99, 3, 5.5, 6, 10.5, 11, 20, 21, None]))
    assert list(bands) == ["0-2", "0-2", "3-5", "3-5", "6-10", "6-10", "11-20", "11-20", "21+", None]


@pytest.mark.parametrize("raw, expected", [
    ("25 - 34 years old", "25-34"), ("25-34 years old", "25-34"), ("Under 18 years old", "Under 18"),
    ("65 years or older", "65+"), ("31", "25-34"), ("17", "Under 18"), ("Prefer not to say", None), ("4", None),
])
def test_parse_age(raw, expected):
    assert P.parse_age(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Bachelor’s degree (B.A., B.S., B.Eng., etc.)", "Bachelor's"),
    ("Master's degree", "Master's"),
    ("Professional degree (JD, MD, Ph.D, Ed.D, etc.)", "Doctoral/professional"),
    ("Other doctoral degree (Ph.D., Ed.D., etc.)", "Doctoral/professional"),
    ("Some college/university study without earning a degree", "Some college"),
    ("I never completed any formal education", "Primary"),
    ("I prefer not to answer", None),
])
def test_parse_ed_level(raw, expected):
    assert P.parse_ed_level(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Just me - I am a freelancer, sole proprietor, etc.", "<20"), ("Fewer than 10 employees", "<20"),
    ("Less than 20 employees", "<20"), ("20 to 99 employees", "20-99"), ("10,000 or more employees", "10,000+"),
    ("I don’t know", None),
])
def test_parse_org_size(raw, expected):
    assert P.parse_org_size(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("All or almost all the time (I'm full-time remote)", "Remote"), ("Fully remote", "Remote"), ("Remote", "Remote"),
    ("Less than once per month / Never", "In-person"), ("Full in-person", "In-person"),
    ("Hybrid (some remote, leans heavy to in-person)", "Hybrid"), ("About half the time", "Hybrid"),
    ("Your choice (very flexible, you can come in when you want or just as needed)", "Hybrid"),
    ("It's complicated", None),
])
def test_parse_remote(raw, expected):
    assert P.parse_remote(raw) == expected


def test_employment_multi_select_keeps_dominant_status():
    assert P.parse_employment("Student, full-time;Employed, part-time") == "Part-time"
    assert P.parse_employment("Employed, full-time;Independent contractor, freelancer, or self-employed") == "Full-time"
    assert P.parse_employment("Employed") == "Full-time"            # 2025 merged full/part time
    assert P.parse_employment("I prefer not to say") is None


def test_main_branch_mapping_across_years():
    assert P.parse_main_branch("Professional developer") == "Professional developer"
    assert P.parse_main_branch("I am a developer by profession") == "Professional developer"
    assert P.parse_main_branch("I am learning to code") == "Learner"
    assert P.parse_main_branch("I am not primarily a developer, but I write code sometimes as part of my work/studies") == "Codes for work (non-dev)"


def test_roles_web_subtype_and_full_stack_inference():
    assert P.parse_roles("Web developer", "Back-end Web developer") == ["Back-end developer"]
    roles = P.parse_roles("Developer, back-end;Developer, front-end")
    assert "Full-stack developer" in roles
    assert P.primary_role(roles) == "Full-stack developer"
    assert P.primary_role(P.parse_roles("Engineering manager;Developer, back-end")) == "Engineering manager"
    assert P.parse_roles(None) == []


def test_ai_scales():
    assert P.parse_ai_use("Yes, I use AI tools daily") == "Using"
    assert P.parse_ai_frequency("Yes, I use AI tools weekly") == "Weekly"
    assert P.parse_ai_agents("No, I use AI exclusively in copilot/autocomplete mode") == "Autocomplete only"
    assert P.TRUST_SCORE["Highly distrust"] == -2 and P.SENTIMENT_SCORE["Very favorable"] == 2


def test_map_unique_matches_elementwise_map():
    s = pd.Series(["3-5 years", "0-2 years", None, "3-5 years"])
    assert P.map_unique(s, P.parse_years).tolist()[:2] == [4.0, 1.0]
