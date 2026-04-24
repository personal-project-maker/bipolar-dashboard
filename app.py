"""
Bipolar Dashboard — full featured build.

Features:
  • Baseline band system with personal baseline (episode periods excluded)
  • Meta question force multipliers + insight-inverse items for Psychosis
  • Domain-specific sleep weight overrides
  • Episode labelling with chart overlays and pre-episode score context
  • Medication notes from form field, shown in journal and on charts
  • Clinician export: structured 30-day summary (copyable markdown)
  • Journal: searchable, colour-coded by band, keyword extraction
  • Snapshot component charts: radar + bar breakdown per domain
  • Global date/domain filters with 7-day rolling average toggle
  • Refresh button + last-updated timestamp in sidebar
  • Consecutive-day streak detection and movement alerts
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from collections import Counter
import re
import gspread
from typing import Any

# ──────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────
st.set_page_config(page_title="Bipolar Dashboard", layout="wide")
st.title("Bipolar Dashboard")

# ──────────────────────────────────────────────────────────
# AUTHENTICATION
# ──────────────────────────────────────────────────────────
def check_password() -> bool:
    def _on_change() -> None:
        st.session_state["authenticated"] = (
            st.session_state["password"] == st.secrets["auth"]["password"]
        )
    if not st.session_state.get("authenticated", False):
        st.text_input("Enter password", type="password", on_change=_on_change, key="password")
        if "authenticated" in st.session_state:
            st.error("Wrong password")
        return False
    return True

if not check_password():
    st.stop()

# ──────────────────────────────────────────────────────────
# GOOGLE SHEETS
# ──────────────────────────────────────────────────────────
SHEET_NAME   = "Bipolar Dashboard"
NEW_FORM_TAB = "Updated Bipolar Form"
SETTINGS_TAB = "Scoring Settings"
BASELINE_TAB = "Baseline Settings"
EPISODE_TAB  = "Episode Log"
COMMENTS_TAB = "Journal Comments"

@st.cache_resource
def _gspread_client() -> gspread.Client:
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))

@st.cache_resource
def _workbook() -> gspread.Spreadsheet:
    return _gspread_client().open(SHEET_NAME)

@st.cache_data(ttl=60)
def load_sheet(tab_name: str) -> pd.DataFrame:
    values = _workbook().worksheet(tab_name).get_all_values()
    if not values:
        return pd.DataFrame()
    headers = [str(h).strip() if h else f"Unnamed_{i+1}" for i, h in enumerate(values[0])]
    return pd.DataFrame(values[1:], columns=headers)

def safe_worksheet(tab_name: str):
    try:
        return _workbook().worksheet(tab_name)
    except Exception:
        return None

# ──────────────────────────────────────────────────────────
# JOURNAL COMMENTS
# ──────────────────────────────────────────────────────────
# Stored in a Google Sheet tab with columns:
#   submission_id | commented_at | comment_text
# submission_id matches the wide table so comments are tied
# to a specific submission, not just a date.

@st.cache_data(ttl=30)
def load_comments() -> pd.DataFrame:
    """Load all journal comments from the Comments sheet tab."""
    ws = safe_worksheet(COMMENTS_TAB)
    if ws is None:
        return pd.DataFrame(columns=["submission_id", "commented_at", "comment_text"])
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame(columns=["submission_id", "commented_at", "comment_text"])
    headers = [str(h).strip() for h in values[0]]
    df = pd.DataFrame(values[1:], columns=headers)
    # Keep only rows with actual comment text
    df = df[df["comment_text"].astype(str).str.strip() != ""].copy()
    return df.reset_index(drop=True)


def save_comment(submission_id: str, comment_text: str) -> tuple[bool, str]:
    """Append a single comment row to the Comments sheet tab."""
    ws = safe_worksheet(COMMENTS_TAB)
    if ws is None:
        return False, (
            f"Worksheet '{COMMENTS_TAB}' not found. Create a tab with that exact name "
            "in your Google Sheet, then comments will save correctly."
        )
    # Initialise headers if sheet is empty
    existing = ws.get_all_values()
    if not existing:
        ws.append_row(["submission_id", "commented_at", "comment_text"])

    import datetime as dt
    commented_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([submission_id, commented_at, comment_text.strip()])
    load_comments.clear()
    return True, "Comment saved."


def get_comments_for_submission(submission_id: str, comments_df: pd.DataFrame) -> list[dict]:
    """Return all comments for a given submission_id, oldest first."""
    if comments_df.empty or "submission_id" not in comments_df.columns:
        return []
    rows = comments_df[comments_df["submission_id"] == submission_id]
    return rows.to_dict("records")

# ──────────────────────────────────────────────────────────
# BASELINE BAND DEFINITIONS
# ──────────────────────────────────────────────────────────
DEFAULT_BASELINE_BANDS: dict[str, dict[str, float]] = {
    "Depression": {"well": 20.0, "watch": 40.0, "caution": 60.0, "warning": 75.0},
    "Mania":      {"well": 20.0, "watch": 40.0, "caution": 60.0, "warning": 75.0},
    "Mixed":      {"well": 18.0, "watch": 35.0, "caution": 55.0, "warning": 70.0},
    "Psychosis":  {"well": 12.0, "watch": 28.0, "caution": 50.0, "warning": 68.0},
}

DEFAULT_MOVEMENT_THRESHOLD: float = 10.0
SELF_HARM_FLAG_THRESHOLD: int = 1
PERSONAL_BASELINE_MIN_DAYS: int = 14

BAND_COLOURS = {
    "well":     "rgba(52,  199, 89,  0.12)",
    "watch":    "rgba(255, 204, 0,   0.12)",
    "caution":  "rgba(255, 149, 0,   0.12)",
    "warning":  "rgba(255, 59,  48,  0.12)",
    "critical": "rgba(175, 82,  222, 0.12)",
}
BAND_LINE_COLOURS = {
    "well":    "rgba(52,  199, 89,  0.5)",
    "watch":   "rgba(255, 204, 0,   0.5)",
    "caution": "rgba(255, 149, 0,   0.5)",
    "warning": "rgba(255, 59,  48,  0.5)",
}
BAND_EMOJI = {
    "well": "🟢", "watch": "🟡", "caution": "🟠",
    "warning": "🔴", "critical": "🟣", "unknown": "⚪",
}
BAND_COLOUR_HEX = {
    "well": "#34C759", "watch": "#FFCC00", "caution": "#FF9500",
    "warning": "#FF3B30", "critical": "#AF52DE", "unknown": "#8E8E93",
}
DOMAIN_COLOURS = {
    "Depression": "#FF3B30", "Mania": "#FF9500",
    "Psychosis":  "#AF52DE", "Mixed": "#1C7EF2",
}

# ──────────────────────────────────────────────────────────
# QUESTION CATALOG
# ──────────────────────────────────────────────────────────
QUESTION_CATALOG: list[dict[str, Any]] = [
    # DEPRESSION
    dict(code="dep_low_mood",           text="Have I felt a low mood?",                                               group="depression", rtype="scale_1_5", polarity="higher_worse",  domains=["Depression"],              order=10),
    dict(code="dep_slowed_low_energy",  text="Have I felt slowed down or low on energy?",                            group="depression", rtype="scale_1_5", polarity="higher_worse",  domains=["Depression"],              order=20),
    dict(code="dep_low_motivation",     text="Have I felt low on motivation or had difficulty initiating tasks?",     group="depression", rtype="scale_1_5", polarity="higher_worse",  domains=["Depression"],              order=30),
    dict(code="dep_anhedonia",          text="Have I felt a lack of interest or pleasure in activities?",             group="depression", rtype="scale_1_5", polarity="higher_worse",  domains=["Depression"],              order=40),
    dict(code="dep_withdrawal",         text="Have I been socially or emotionally withdrawn?",                        group="depression", rtype="scale_1_5", polarity="higher_worse",  domains=["Depression"],              order=50),
    dict(code="dep_self_harm_ideation", text="Have I had ideation around self-harming or suicidal behaviours?",       group="depression", rtype="scale_1_5", polarity="higher_worse",  domains=["Depression"],              order=60),
    # MANIA
    dict(code="man_elevated_mood",      text="Have I felt an elevated mood?",                                         group="mania",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mania"],                   order=70),
    dict(code="man_sped_up_high_energy",text="Have I felt sped up or high on energy?",                               group="mania",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mania","Mixed"],           order=80),
    dict(code="man_racing_thoughts",    text="Have I had racing thoughts or speech?",                                 group="mania",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mania"],                   order=90),
    dict(code="man_goal_drive",         text="Have I had an increased drive towards goal-directed activity?",          group="mania",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mania"],                   order=100),
    dict(code="man_impulsivity",        text="Have I felt impulsivity or an urge to take risky actions?",             group="mania",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mania"],                   order=110),
    dict(code="man_agitation",          text="Have I felt agitated or restless?",                                     group="mania",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mania","Mixed"],           order=120),
    dict(code="man_irritability",       text="Have I been more irritable and reactive than normal?",                  group="mania",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mania","Mixed"],           order=130),
    dict(code="man_cant_settle",        text="Have I been unable to settle or switch off?",                           group="mania",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mania"],                   order=140),
    # MIXED
    dict(code="mix_high_energy_low_mood",   text="Have I had a high energy combined with low mood?",                 group="mixed",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mixed"],                   order=150),
    dict(code="mix_rapid_emotional_shifts", text="Have I experienced rapid emotional shifts?",                        group="mixed",      rtype="scale_1_5", polarity="higher_worse",  domains=["Mixed"],                   order=160),
    # PSYCHOSIS
    dict(code="psy_heard_saw",          text="Have I heard or seen things others didn't?",                            group="psychosis",  rtype="scale_1_5", polarity="higher_worse",  domains=["Psychosis"],               order=170),
    dict(code="psy_suspicious",         text="Have I felt watched, followed, targeted or suspicious?",                group="psychosis",  rtype="scale_1_5", polarity="higher_worse",  domains=["Psychosis"],               order=180),
    dict(code="psy_trust_perceptions",  text="Have I had trouble trusting my perceptions and thoughts?",              group="psychosis",  rtype="scale_1_5", polarity="higher_worse",  domains=["Psychosis"],               order=190),
    dict(code="psy_confidence_reality", text="How confident have I been in the reality of these experiences?",        group="psychosis",  rtype="scale_1_5", polarity="higher_worse",  domains=["Psychosis"],               order=200),
    dict(code="psy_distress",           text="How distressed have I been by these beliefs and experiences?",          group="psychosis",  rtype="scale_1_5", polarity="higher_worse",  domains=["Psychosis"],               order=210),
    # FUNCTIONING
    dict(code="func_work",              text="How effectively have I been functioning at work?",                      group="functioning",rtype="scale_1_5", polarity="higher_better", domains=["Depression","Mania"],       order=220),
    dict(code="func_daily",             text="How well have I been functioning in my daily life?",                    group="functioning",rtype="scale_1_5", polarity="higher_better", domains=["Depression","Mania"],       order=230),
    # Sleep: included in Mania + Mixed at full weight; deprioritised in Depression via domain_weight_overrides
    dict(code="func_sleep_hours",       text="How many hours did I sleep last night?",                                group="functioning",rtype="numeric",   polarity="custom_sleep",  domains=["Depression","Mania","Mixed"], order=450, score_in_snapshot=False),
    dict(code="func_sleep_quality",     text="How poor was my sleep quality last night",                              group="functioning",rtype="scale_1_5", polarity="higher_worse",  domains=["Depression","Mania","Mixed"], order=460, score_in_snapshot=False),
    # META
    # FORCE MULTIPLIERS — amplify all domain scores post-calculation
    # meta_role="force_multiplier" flags these for the multiplier pipeline
    dict(code="meta_unlike_self",             text="Do I feel unlike my usual self?",                                 group="meta", rtype="scale_1_5", polarity="higher_worse", domains=[], order=240, meta_role="force_multiplier"),
    dict(code="meta_intensifying",            text="Is my state intensifying (in any direction)?",                    group="meta", rtype="scale_1_5", polarity="higher_worse", domains=[], order=300, meta_role="force_multiplier"),
    dict(code="meta_towards_episode",         text="Do I feel like I'm moving towards an episode?",                   group="meta", rtype="scale_1_5", polarity="higher_worse", domains=[], order=310, meta_role="force_multiplier"),
    # INSIGHT ITEMS — contribute normally to Dep/Mania/Mixed; INVERSE to Psychosis
    # (low concern/insight in psychosis = higher risk, not lower)
    # meta_role="insight_inverse_psychosis" flags these for domain-specific polarity flip
    dict(code="meta_something_wrong",         text="Do I think something may be wrong or changing?",                  group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Depression","Mania","Mixed","Psychosis"], order=250, meta_role="insight_inverse_psychosis"),
    dict(code="meta_concerned",               text="Am I concerned about my current state?",                           group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Depression","Mania","Mixed","Psychosis"], order=260, meta_role="insight_inverse_psychosis"),
    # DIRECT CONTRIBUTORS — added to specific domains at face value
    dict(code="meta_disorganised_thoughts",   text="Do my thoughts feel disorganised or hard to follow?",              group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Psychosis","Mixed"],             order=270, meta_role="contributor"),
    dict(code="meta_attention_unstable",      text="Is my attention unstable or jumping?",                             group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Mania","Mixed"],                 order=280, meta_role="contributor"),
    dict(code="meta_driven_without_thinking", text="Do I feel driven to act without thinking?",                        group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Mania","Mixed"],                 order=290, meta_role="contributor"),
    # FLAGS
    dict(code="flag_not_myself",          text="I've been feeling \"not like myself\"",                               group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis"],         order=320),
    dict(code="flag_mood_shift",          text="I noticed a sudden mood shift",                                       group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis","Mixed"],  order=330),
    dict(code="flag_missed_medication",   text="I missed medication",                                                 group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis"],         order=340),
    dict(code="flag_sleep_medication",    text="I took sleeping or anti-anxiety medication",                          group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=[],                                        order=350),
    dict(code="flag_routine_disruption",  text="There were significant disruptions to my routine",                   group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis","Mixed"],  order=360),
    dict(code="flag_physiological_stress",text="I had a major physiological stress",                                 group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis"],         order=370),
    dict(code="flag_psychological_stress",text="I had a major psychological stress",                                 group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis"],         order=380),
    # OBSERVATIONS
    dict(code="obs_up_now",      text="Observations [I feel like I'm experiencing an up]",           group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Mania"],             order=390),
    dict(code="obs_down_now",    text="Observations [I feel like I'm experiencing a down]",          group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression"],        order=400),
    dict(code="obs_mixed_now",   text="Observations [I feel like I'm experiencing a mixed]",         group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Psychosis","Mixed"], order=410),
    dict(code="obs_up_coming",   text="Observations [I feel like I'm going to experience an up]",    group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Mania"],             order=420),
    dict(code="obs_down_coming", text="Observations [I feel like I'm going to experience a down]",   group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression"],        order=430),
    dict(code="obs_mixed_coming",text="Observations [I feel like I'm going to experience a mixed]",  group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Psychosis","Mixed"], order=440),
    # NOTES
    dict(code="experience_description", text="How would I describe my experiences?",                    group="notes", rtype="text", polarity="not_applicable", domains=[], order=470),
    dict(code="medication_notes",       text="Have there been any medication changes? If so, what?",    group="notes", rtype="text", polarity="not_applicable", domains=[], order=480),
    dict(code="submission_type",        text="What kind of entry is this?",                             group="notes", rtype="text", polarity="not_applicable", domains=[], order=5),
]

for _q in QUESTION_CATALOG:
    _q.setdefault("score_in_snapshot", True)
    _q.setdefault("score_in_daily", True)

DOMAINS = ["Depression", "Mania", "Psychosis", "Mixed"]

# ──────────────────────────────────────────────────────────
# DOMAIN-SPECIFIC WEIGHT OVERRIDES
# Sleep is deprioritised in Depression (where it's a symptom, not a cause)
# but kept at full weight in Mania and Mixed (where it's a major driver).
# Format: {domain: {question_code: multiplier}}
# Multiplier is applied to the base weight for that domain only.
# ──────────────────────────────────────────────────────────
DOMAIN_WEIGHT_MULTIPLIERS: dict[str, dict[str, float]] = {
    "Depression": {
        "func_sleep_hours":   0.35,   # sleep hrs has low predictive value for dep onset
        "func_sleep_quality": 0.45,   # sleep quality similarly deprioritised
    },
    "Mania": {
        "func_sleep_hours":   1.0,    # full weight — sleep loss is a core mania driver
        "func_sleep_quality": 1.0,
    },
    "Mixed": {
        "func_sleep_hours":   1.0,
        "func_sleep_quality": 1.0,
    },
    "Psychosis": {},
}

# ──────────────────────────────────────────────────────────
# DEFAULT WEIGHTS
# ──────────────────────────────────────────────────────────
DEFAULT_WEIGHTS: dict[str, float] = {
    "dep_low_mood": 3.0, "dep_slowed_low_energy": 1.5, "dep_low_motivation": 2.0,
    "dep_anhedonia": 2.0, "dep_withdrawal": 1.0, "dep_self_harm_ideation": 4.0,
    "man_elevated_mood": 2.0, "man_sped_up_high_energy": 1.5, "man_racing_thoughts": 1.5,
    "man_goal_drive": 1.5, "man_impulsivity": 2.0, "man_agitation": 1.5,
    "man_irritability": 1.5, "man_cant_settle": 1.0,
    "mix_high_energy_low_mood": 3.0, "mix_rapid_emotional_shifts": 2.0,
    "psy_heard_saw": 2.0, "psy_suspicious": 1.5, "psy_trust_perceptions": 1.5,
    "psy_confidence_reality": 2.0, "psy_distress": 1.5,
    "func_work": 1.0, "func_daily": 1.0, "func_sleep_quality": 1.25, "func_sleep_hours": 1.25,
    "flag_not_myself": 1.0, "flag_mood_shift": 1.0, "flag_missed_medication": 1.25,
    "flag_sleep_medication": 0.75, "flag_routine_disruption": 1.0,
    "flag_physiological_stress": 1.0, "flag_psychological_stress": 1.0,
    "obs_up_now": 1.0, "obs_down_now": 1.0, "obs_mixed_now": 1.0,
    "obs_up_coming": 0.75, "obs_down_coming": 0.75, "obs_mixed_coming": 0.75,
    # Meta contributors (force multipliers have no weight here — they act post-scoring)
    "meta_something_wrong": 1.25,          # insight item — moderate weight in Dep/Mania/Mixed
    "meta_concerned": 1.0,                 # insight item — lower weight, more reactive
    "meta_disorganised_thoughts": 1.75,    # strong Psychosis/Mixed contributor
    "meta_attention_unstable": 1.25,       # Mania/Mixed contributor
    "meta_driven_without_thinking": 1.5,   # Mania/Mixed contributor — reinforces impulsivity
}

# ──────────────────────────────────────────────────────────
# CATALOG HELPERS
# ──────────────────────────────────────────────────────────
@st.cache_data
def catalog_df() -> pd.DataFrame:
    return pd.DataFrame(QUESTION_CATALOG).sort_values("order").reset_index(drop=True)

def _catalog_by_text() -> dict[str, dict]:
    return {q["text"]: q for q in QUESTION_CATALOG}

def _catalog_by_code() -> dict[str, dict]:
    return {q["code"]: q for q in QUESTION_CATALOG}

def _effective_weight(code: str, domain: str, base_weights: dict[str, float]) -> float:
    """Apply domain-specific multiplier to base weight."""
    base = base_weights.get(code, 0.0)
    multiplier = DOMAIN_WEIGHT_MULTIPLIERS.get(domain, {}).get(code, 1.0)
    return base * multiplier

# ──────────────────────────────────────────────────────────
# META QUESTION ROLES
# ──────────────────────────────────────────────────────────
# Force multipliers: amplify all domain scores post-calculation.
# Range: 1.0 (no amplification) to META_MULTIPLIER_MAX (full amplification).
# The composite of the three items is mapped linearly into this range.
META_MULTIPLIER_MAX: float = 1.35   # max 35% amplification at full score

FORCE_MULTIPLIER_CODES = [
    q["code"] for q in QUESTION_CATALOG if q.get("meta_role") == "force_multiplier"
]

# Insight-inverse items: in Psychosis, LOW concern/insight = HIGHER risk.
# In all other domains they contribute normally (higher score = worse).
INSIGHT_INVERSE_CODES = [
    q["code"] for q in QUESTION_CATALOG if q.get("meta_role") == "insight_inverse_psychosis"
]

def _normalise_meta_item(raw_value: Any) -> float:
    """Normalise a single scale_1_5 meta item to 0–100."""
    v = pd.to_numeric(raw_value, errors="coerce")
    if pd.isna(v):
        return 0.0
    return float(min(max((v - 1.0) / 4.0 * 100.0, 0.0), 100.0))

def compute_meta_multiplier(row: pd.Series) -> float:
    """
    Compute the force-multiplier scalar for one row (submission).

    Takes the mean of the three multiplier items (meta_unlike_self,
    meta_intensifying, meta_towards_episode), each normalised to 0–100,
    then maps that average linearly to [1.0, META_MULTIPLIER_MAX].

    Returns a scalar in [1.0, META_MULTIPLIER_MAX].
    """
    scores = []
    for code in FORCE_MULTIPLIER_CODES:
        if code in row.index:
            scores.append(_normalise_meta_item(row[code]))
    if not scores:
        return 1.0
    avg = float(np.mean(scores))  # 0–100
    return 1.0 + (avg / 100.0) * (META_MULTIPLIER_MAX - 1.0)

def _psychosis_insight_score(row: pd.Series) -> float:
    """
    For Psychosis only: low concern/insight = higher risk.
    Inverts the normalised insight item scores (100 - score),
    then returns the mean as an additive contribution (0–100).
    """
    scores = []
    for code in INSIGHT_INVERSE_CODES:
        if code in row.index:
            norm = _normalise_meta_item(row[code])
            scores.append(100.0 - norm)   # invert: low concern → high score
    return float(np.mean(scores)) if scores else 0.0

# ──────────────────────────────────────────────────────────
# SUBMISSION TYPE
# ──────────────────────────────────────────────────────────
# Values from the form question "What kind of entry is this?"
SUBMISSION_TYPE_REVIEW   = "review"    # covers both "Review of today" and "Review of yesterday"
SUBMISSION_TYPE_SNAPSHOT = "snapshot"

# Weight applied to review submissions in the daily aggregate
# Snapshots are 1.0 (ground truth); reviews are 0.5 (retrospective, subject to recall bias)
REVIEW_WEIGHT   = 0.5
SNAPSHOT_WEIGHT = 1.0

def _classify_submission_type(row: pd.Series) -> str:
    """
    Classify a submission as 'review' or 'snapshot'.

    Priority:
    1. If the form field is filled, use it directly.
    2. For historical data (no form field): if func_sleep_hours is present
       and non-null, treat as review of yesterday; otherwise treat as snapshot.
    """
    # Check explicit form field first
    st_val = str(row.get("submission_type", "") or "").strip().lower()
    if "review" in st_val:
        return SUBMISSION_TYPE_REVIEW
    if "snapshot" in st_val:
        return SUBMISSION_TYPE_SNAPSHOT

    # Historical heuristic: sleep hours present → review
    sleep = row.get("func_sleep_hours")
    if sleep is not None and not (isinstance(sleep, float) and np.isnan(sleep)):
        try:
            if pd.notna(pd.to_numeric(sleep, errors="coerce")):
                return SUBMISSION_TYPE_REVIEW
        except Exception:
            pass

    return SUBMISSION_TYPE_SNAPSHOT

# ──────────────────────────────────────────────────────────
# RAW DATA PROCESSING
# ──────────────────────────────────────────────────────────
def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "y", "checked"}

def add_submission_indexing(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    w = df.copy()
    w["submitted_at"] = pd.to_datetime(w["Timestamp"], errors="coerce", dayfirst=True)
    w = w.dropna(subset=["submitted_at"]).sort_values("submitted_at").reset_index(drop=True)
    w["submitted_date"] = w["submitted_at"].dt.date
    w["submission_order_in_day"] = w.groupby("submitted_date").cumcount() + 1
    w["is_first_of_day"] = w["submission_order_in_day"] == 1
    w["submission_id"] = w["submitted_at"].dt.strftime("%Y%m%d%H%M%S") + "_" + w.index.astype(str)
    return w

def clean_and_widen(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    by_text = _catalog_by_text()
    w = df.copy()
    base_cols = ["submission_id", "submitted_at", "submitted_date",
                 "submission_order_in_day", "is_first_of_day"]
    wide = w[base_cols].copy()
    for text, meta in by_text.items():
        if text not in w.columns:
            continue
        code, raw = meta["code"], w[text]
        if meta["rtype"] == "boolean_yes_no":
            wide[code] = raw.apply(_bool)
        elif meta["rtype"] in ("scale_1_5", "numeric"):
            wide[code] = pd.to_numeric(raw, errors="coerce")
        else:
            wide[code] = raw

    # Derive a clean submission type column after all other columns are set
    wide["submission_type_derived"] = wide.apply(_classify_submission_type, axis=1)
    return wide

# ──────────────────────────────────────────────────────────
# SCORING
# ──────────────────────────────────────────────────────────
def _normalise(series: pd.Series, meta: dict) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    rtype, polarity, code = meta["rtype"], meta["polarity"], meta["code"]
    if rtype == "boolean_yes_no":
        return series.astype(bool).astype(float) * 100.0
    if code == "func_sleep_hours":
        bins = [(0, 3, 100), (3, 4, 85), (4, 5, 70), (5, 6, 50),
                (6, 9, 20), (9, 10, 40), (10, np.inf, 60)]
        out = pd.Series(np.nan, index=s.index)
        for lo, hi, score in bins:
            out = out.mask((s >= lo) & (s < hi), score)
        return out.fillna(0.0)
    if rtype == "scale_1_5":
        base = ((s - 1).clip(0, 4) / 4.0) * 100.0
        return (100.0 - base if polarity == "higher_better" else base).fillna(0.0)
    return s.fillna(0.0)

def _domain_score(frame: pd.DataFrame, domain: str, weights: dict[str, float],
                  snapshot: bool = False) -> pd.Series:
    codes = [
        q["code"] for q in QUESTION_CATALOG
        if domain in q["domains"]
        and q["code"] in frame.columns
        and _effective_weight(q["code"], domain, weights) > 0
        and (not snapshot or q.get("score_in_snapshot", True))
    ]
    if not codes:
        return pd.Series(0.0, index=frame.index)

    num = pd.Series(0.0, index=frame.index)
    den = 0.0
    for c in codes:
        ew = _effective_weight(c, domain, weights)
        col_vals = frame[c].fillna(0.0)
        # Insight-inverse items: flip in Psychosis (low concern = higher risk)
        if domain == "Psychosis" and c in INSIGHT_INVERSE_CODES:
            col_vals = 100.0 - col_vals
        num += col_vals * ew
        den += ew

    return num / den if den else pd.Series(0.0, index=frame.index)

def build_scored_table(wide: pd.DataFrame, weights: dict[str, float],
                       daily_only: bool = False) -> pd.DataFrame:
    if wide.empty:
        return pd.DataFrame()
    src = wide[wide["is_first_of_day"]].copy() if daily_only else wide.copy()
    if not daily_only:
        src["minutes_since_first"] = (
            src["submitted_at"]
            - src.groupby("submitted_date")["submitted_at"].transform("min")
        ).dt.total_seconds() / 60.0

    # Normalise all scoreable questions
    by_code = _catalog_by_code()
    for code, meta in by_code.items():
        if code in src.columns and meta["rtype"] != "text":
            src[f"_n_{code}"] = _normalise(src[code], meta)
    norm_frame = src.copy()
    for code in by_code:
        if f"_n_{code}" in norm_frame.columns:
            norm_frame[code] = norm_frame[f"_n_{code}"]

    # Raw domain scores (pre-multiplier)
    for domain in DOMAINS:
        src[f"{domain} Score % (raw)"] = _domain_score(
            norm_frame, domain, weights, snapshot=not daily_only
        )

    # Compute force multiplier per row from the three meta items
    # We use the raw (un-normalised) meta columns from src for this
    src["meta_multiplier"] = src.apply(compute_meta_multiplier, axis=1)

    # Apply multiplier and cap at 100
    for domain in DOMAINS:
        src[f"{domain} Score %"] = (
            src[f"{domain} Score % (raw)"] * src["meta_multiplier"]
        ).clip(upper=100.0)

    src["Overall Score %"] = src[[f"{d} Score %" for d in DOMAINS]].mean(axis=1)
    src = src.drop(columns=[c for c in src.columns if c.startswith("_n_")])

    if daily_only:
        src = src.rename(columns={"submitted_date": "date"})
        for col in [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]:
            src[f"{col} Delta"] = src[col].diff()
            src[f"{col} 7d Avg"] = src[col].rolling(7, min_periods=1).mean()

    return src.reset_index(drop=True)

# ──────────────────────────────────────────────────────────
# DAILY AGGREGATE MODEL
# Replaces the old "first submission of day" approach.
# Groups all submissions by date and produces one row per day by:
#   - Averaging numeric/scale scores, weighting snapshots at 1.0 and reviews at 0.5
#   - Boolean flags: any-true across all submissions that day
#   - Text fields: taken from the review submission if present, else latest snapshot
#   - Sleep: taken from review submissions only (that's where it's meaningful)
# ──────────────────────────────────────────────────────────
def build_daily_aggregate(wide: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """
    Produce one scored row per calendar day by aggregating all submissions.
    Snapshot submissions are weighted at SNAPSHOT_WEIGHT (1.0).
    Review submissions are weighted at REVIEW_WEIGHT (0.5).
    """
    if wide.empty:
        return pd.DataFrame()

    by_code = _catalog_by_code()

    # Score every individual submission (full snapshot mode)
    scored_all = build_scored_table(wide, weights, daily_only=False)

    # Attach submission_type_derived directly from wide using positional alignment
    # (both share the same index after build_scored_table resets it)
    if "submission_type_derived" in wide.columns:
        # Map by submission_id for safety
        type_map = wide.set_index("submission_id")["submission_type_derived"].to_dict()
        scored_all["submission_type_derived"] = scored_all["submission_id"].map(type_map).fillna(SUBMISSION_TYPE_SNAPSHOT)
    else:
        scored_all["submission_type_derived"] = SUBMISSION_TYPE_SNAPSHOT

    # Also bring submitted_date into scored_all if not already present
    if "submitted_date" not in scored_all.columns and "submitted_date" in wide.columns:
        date_map = wide.set_index("submission_id")["submitted_date"].to_dict()
        scored_all["submitted_date"] = scored_all["submission_id"].map(date_map)

    # Per-submission weight scalar
    scored_all["_sw"] = scored_all["submission_type_derived"].map({
        SUBMISSION_TYPE_SNAPSHOT: SNAPSHOT_WEIGHT,
        SUBMISSION_TYPE_REVIEW:   REVIEW_WEIGHT,
    }).fillna(SNAPSHOT_WEIGHT)

    # ── Aggregate by date ────────────────────────────────────
    agg_rows: list[dict] = []

    for date, group in scored_all.groupby("submitted_date"):
        row: dict = {"date": date}

        # Submission counts
        row["n_snapshots"] = int((group["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT).sum())
        row["n_reviews"]   = int((group["submission_type_derived"] == SUBMISSION_TYPE_REVIEW).sum())
        row["n_total"]     = len(group)

        weights_arr = group["_sw"].values.astype(float)
        total_w     = weights_arr.sum()

        # Domain scores — weighted mean across all submissions
        for domain in DOMAINS:
            col = f"{domain} Score %"
            col_raw = f"{domain} Score % (raw)"
            if col in group.columns:
                row[col]     = float(np.average(group[col].fillna(0), weights=weights_arr))
            if col_raw in group.columns:
                row[col_raw] = float(np.average(group[col_raw].fillna(0), weights=weights_arr))

        row["Overall Score %"] = float(np.mean([row.get(f"{d} Score %", 0) for d in DOMAINS]))

        # Meta multiplier — weighted mean
        if "meta_multiplier" in group.columns:
            row["meta_multiplier"] = float(np.average(
                group["meta_multiplier"].fillna(1.0), weights=weights_arr
            ))

        # Raw question scores
        for code, meta in by_code.items():
            if code not in wide.columns:
                continue
            # Merge raw values from wide into group via submission_id
            raw_vals = wide[wide["submitted_date"] == date][[code, "submission_type_derived"]].copy()
            if raw_vals.empty:
                continue

            if meta["rtype"] == "boolean_yes_no":
                # Any-true across all submissions that day
                row[code] = bool(raw_vals[code].any())

            elif code in ("func_sleep_hours", "func_sleep_quality"):
                # Sleep only from review submissions; fall back to any if no review
                review_vals = raw_vals[raw_vals["submission_type_derived"] == SUBMISSION_TYPE_REVIEW][code].dropna()
                if not review_vals.empty:
                    row[code] = float(review_vals.mean())
                else:
                    all_vals = raw_vals[code].dropna()
                    row[code] = float(all_vals.mean()) if not all_vals.empty else np.nan

            elif meta["rtype"] in ("scale_1_5", "numeric"):
                # Weighted mean (snapshot 1.0, review 0.5)
                rv = raw_vals[[code, "submission_type_derived"]].copy()
                rv["_w"] = rv["submission_type_derived"].map({
                    SUBMISSION_TYPE_SNAPSHOT: SNAPSHOT_WEIGHT,
                    SUBMISSION_TYPE_REVIEW:   REVIEW_WEIGHT,
                }).fillna(SNAPSHOT_WEIGHT)
                rv = rv.dropna(subset=[code])
                if not rv.empty:
                    row[code] = float(np.average(
                        pd.to_numeric(rv[code], errors="coerce").fillna(0),
                        weights=rv["_w"]
                    ))

            elif meta["rtype"] == "text":
                # Text: prefer review, fall back to latest snapshot
                review_text = raw_vals[raw_vals["submission_type_derived"] == SUBMISSION_TYPE_REVIEW][code]
                review_text = review_text[review_text.notna() & (review_text.astype(str).str.strip() != "")]
                if not review_text.empty:
                    row[code] = str(review_text.iloc[-1])
                else:
                    snap_text = raw_vals[raw_vals["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT][code]
                    snap_text = snap_text[snap_text.notna() & (snap_text.astype(str).str.strip() != "")]
                    row[code] = str(snap_text.iloc[-1]) if not snap_text.empty else ""

        # Track the latest submitted_at for this day
        row["submitted_at"] = group["submitted_at"].max()

        # Has a review?
        row["has_review"]   = row["n_reviews"] > 0
        row["has_snapshot"] = row["n_snapshots"] > 0

        agg_rows.append(row)

    if not agg_rows:
        return pd.DataFrame()

    daily = pd.DataFrame(agg_rows).sort_values("date").reset_index(drop=True)

    # Delta and rolling average on final scores
    for col in [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]:
        if col in daily.columns:
            daily[f"{col} Delta"] = daily[col].diff()
            daily[f"{col} 7d Avg"] = daily[col].rolling(7, min_periods=1).mean()

    return daily
# Returns normalised per-item contribution for a single snapshot row
# ──────────────────────────────────────────────────────────
def get_snapshot_components(row: pd.Series, domain: str, weights: dict[str, float]) -> pd.DataFrame:
    """
    For a single row (snapshot), return each contributing item's
    normalised score (0-100), effective weight, and weighted contribution.
    Handles psychosis insight inversion and shows pre/post multiplier scores.
    """
    by_code = _catalog_by_code()
    items = [
        q for q in QUESTION_CATALOG
        if domain in q["domains"]
        and q["code"] in row.index
        and q.get("score_in_snapshot", True)
        and _effective_weight(q["code"], domain, weights) > 0
    ]
    if not items:
        return pd.DataFrame()

    multiplier = compute_meta_multiplier(row)
    rows = []
    for q in items:
        code = q["code"]
        raw_val = row.get(code)
        norm_score = float(_normalise(pd.Series([raw_val]), q).iloc[0])

        # Flip insight items in Psychosis
        inverted = domain == "Psychosis" and code in INSIGHT_INVERSE_CODES
        display_score = 100.0 - norm_score if inverted else norm_score

        eff_w = _effective_weight(code, domain, weights)
        label = q["text"]
        label = re.sub(r"^(Have I |Do I |Am I |Is my |I've been |I noticed |I |There were |I had a )", "", label)
        label = label[:45] + "…" if len(label) > 45 else label
        if inverted:
            label = f"{label} ⟳"   # mark inverted items

        rows.append(dict(
            code=code,
            label=label,
            norm_score=round(display_score, 1),
            weight=round(eff_w, 2),
            contribution=round(display_score * eff_w, 1),
            group=q["group"],
            inverted=inverted,
        ))

    df = pd.DataFrame(rows)
    total_w = df["weight"].sum()
    df["weighted_pct"] = (df["weight"] / total_w * 100).round(1) if total_w else 0
    df["multiplier"] = round(multiplier, 3)
    df["score_after_multiplier"] = (df["norm_score"] * multiplier).clip(upper=100).round(1)
    return df.sort_values("contribution", ascending=False)

# ──────────────────────────────────────────────────────────
# BASELINE BANDS — LOAD / SAVE
# ──────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_baseline_config() -> dict:
    ws = safe_worksheet(BASELINE_TAB)
    config = {
        "bands": {d: v.copy() for d, v in DEFAULT_BASELINE_BANDS.items()},
        "movement_threshold": DEFAULT_MOVEMENT_THRESHOLD,
        "personal_baseline_window": 90,
    }
    if ws is None:
        return config
    try:
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return config
        df = pd.DataFrame(values[1:], columns=values[0])
        if {"domain", "band", "value"}.issubset(df.columns):
            for _, row in df.iterrows():
                d = str(row["domain"]).strip()
                b = str(row["band"]).strip()
                v = pd.to_numeric(row["value"], errors="coerce")
                if d in config["bands"] and b in config["bands"][d] and pd.notna(v):
                    config["bands"][d][b] = float(v)
        if {"key", "value"}.issubset(df.columns):
            for _, row in df.iterrows():
                k = str(row.get("key", "")).strip()
                v = pd.to_numeric(row.get("value"), errors="coerce")
                if k == "movement_threshold" and pd.notna(v):
                    config["movement_threshold"] = float(v)
                if k == "personal_baseline_window" and pd.notna(v):
                    config["personal_baseline_window"] = int(v)
    except Exception:
        pass
    return config

def save_baseline_config(config: dict) -> tuple[bool, str]:
    ws = safe_worksheet(BASELINE_TAB)
    if ws is None:
        return False, f"Worksheet '{BASELINE_TAB}' not found. Create it manually then try again."
    rows = [["domain", "band", "value", "key"]]
    for domain, bands_inner in config["bands"].items():
        for band, value in bands_inner.items():
            rows.append([domain, band, value, ""])
    rows += [["", "", "", ""],
             ["", "", config["movement_threshold"], "movement_threshold"],
             ["", "", config["personal_baseline_window"], "personal_baseline_window"]]
    ws.clear()
    ws.update("A1", rows)
    load_baseline_config.clear()
    return True, "Baseline config saved."

# ──────────────────────────────────────────────────────────
# PERSONAL BASELINE
# ──────────────────────────────────────────────────────────
def compute_personal_baseline(
    daily: pd.DataFrame,
    bands: dict[str, dict[str, float]],
    window_days: int = 90,
    episodes: pd.DataFrame | None = None,
) -> dict[str, dict]:
    """
    Personal baseline is computed from well days using snapshot-derived scores only.
    Snapshot submissions are the most accurate point-in-time readings; reviews are
    subject to recall bias and excluded from the baseline calculation.
    Days with no snapshots (review-only days) are also excluded.
    """
    empty = dict(mean=None, sd=None, n=0, lower=None, upper=None, reliable=False)
    if daily.empty:
        return {d: empty.copy() for d in DOMAINS}

    # Only use days that have at least one snapshot submission
    working = daily.copy()
    if "has_snapshot" in working.columns:
        working = working[working["has_snapshot"] == True]

    mask = pd.Series(True, index=working.index)
    for domain in DOMAINS:
        col = f"{domain} Score %"
        if col in working.columns:
            ceiling = bands.get(domain, {}).get("well", 20.0)
            mask &= working[col].fillna(999) <= ceiling

    # Exclude labelled episode periods
    if episodes is not None and not episodes.empty:
        ep_mask = pd.Series(False, index=working.index)
        for _, ep in episodes.iterrows():
            try:
                ep_start = pd.Timestamp(ep["start_date"]).date()
                ep_end   = pd.Timestamp(ep["end_date"]).date()
                ep_mask |= (working["date"] >= ep_start) & (working["date"] <= ep_end)
            except Exception:
                pass
        mask &= ~ep_mask

    well_days = working[mask].sort_values("date").tail(window_days)
    result: dict[str, dict] = {}
    for domain in DOMAINS:
        col = f"{domain} Score %"
        if col not in well_days.columns or well_days.empty:
            result[domain] = empty.copy()
            continue
        scores = well_days[col].dropna()
        n = len(scores)
        if n == 0:
            result[domain] = empty.copy()
            continue
        mean = float(scores.mean())
        sd   = float(scores.std()) if n > 1 else 0.0
        result[domain] = dict(
            mean=round(mean, 1), sd=round(sd, 2), n=n,
            lower=round(mean - sd, 1), upper=round(mean + sd, 1),
            reliable=n >= PERSONAL_BASELINE_MIN_DAYS,
        )
    return result

# ──────────────────────────────────────────────────────────
# BAND CLASSIFICATION
# ──────────────────────────────────────────────────────────
def classify_score(score: float, domain: str, bands: dict) -> str:
    if score is None or (isinstance(score, float) and np.isnan(score)):
        return "unknown"
    b = bands.get(domain, DEFAULT_BASELINE_BANDS.get(domain, {}))
    if score <= b.get("well",    20): return "well"
    if score <= b.get("watch",   40): return "watch"
    if score <= b.get("caution", 60): return "caution"
    if score <= b.get("warning", 75): return "warning"
    return "critical"

# ──────────────────────────────────────────────────────────
# NOTES / JOURNAL HELPERS
# ──────────────────────────────────────────────────────────
_STOP_WORDS = {
    "i", "a", "an", "the", "and", "or", "but", "of", "to", "in", "is", "it",
    "my", "me", "was", "been", "have", "has", "had", "that", "this", "with",
    "for", "on", "are", "be", "at", "not", "felt", "feel", "feeling", "just",
    "been", "like", "so", "bit", "very", "quite", "pretty", "really", "some",
    "more", "less", "bit", "day", "today", "yesterday", "week", "night",
}

def extract_keywords(text: str, top_n: int = 8) -> list[str]:
    if not text or not isinstance(text, str):
        return []
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    filtered = [w for w in words if w not in _STOP_WORDS]
    return [w for w, _ in Counter(filtered).most_common(top_n)]

def build_notes_df(wide: pd.DataFrame, daily_scored: pd.DataFrame, bands: dict) -> pd.DataFrame:
    """
    Extract all non-empty text notes, join with the day's band status.
    """
    if wide.empty or "experience_description" not in wide.columns:
        return pd.DataFrame()

    notes = wide[wide["experience_description"].notna() &
                 (wide["experience_description"].astype(str).str.strip() != "")].copy()
    notes = notes[["submitted_at", "submitted_date", "experience_description"]].copy()
    notes["date"] = notes["submitted_date"]

    # Join domain scores from daily (first-of-day)
    if not daily_scored.empty:
        score_cols = [f"{d} Score %" for d in DOMAINS]
        day_scores = daily_scored[["date"] + [c for c in score_cols if c in daily_scored.columns]].copy()
        notes = notes.merge(day_scores, on="date", how="left")

    # Classify by overall band (worst domain that day)
    def _worst_band(row):
        bands_on_day = [classify_score(row.get(f"{d} Score %", 0), d, bands) for d in DOMAINS]
        order = ["critical", "warning", "caution", "watch", "well", "unknown"]
        for b in order:
            if b in bands_on_day:
                return b
        return "unknown"

    notes["worst_band"] = notes.apply(_worst_band, axis=1)
    notes["keywords"] = notes["experience_description"].apply(extract_keywords)
    notes = notes.sort_values("submitted_at", ascending=False).reset_index(drop=True)
    return notes

def keyword_frequency_chart(notes_df: pd.DataFrame, top_n: int = 20) -> go.Figure:
    all_kw = [kw for kws in notes_df["keywords"] for kw in kws]
    if not all_kw:
        return go.Figure()
    counts = Counter(all_kw).most_common(top_n)
    words, freqs = zip(*counts)
    fig = go.Figure(go.Bar(
        x=freqs, y=words, orientation="h",
        marker_color="#1C7EF2",
        hovertemplate="%{y}: %{x} mentions<extra></extra>",
    ))
    fig.update_layout(
        height=max(300, top_n * 22),
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(autorange="reversed"),
        xaxis=dict(title="Frequency"),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig

# ──────────────────────────────────────────────────────────
# PLOTLY CHARTS
# ──────────────────────────────────────────────────────────
def _add_vline_date(fig: go.Figure, x: str, label: str,
                    line_color: str = "rgba(0,150,100,0.6)",
                    line_dash: str = "dash",
                    line_width: float = 1.5,
                    font_color: str = "rgba(0,150,100,1)",
                    font_size: int = 8) -> go.Figure:
    """
    Add a vertical line + annotation on a date-string x-axis.
    Uses add_shape + add_annotation instead of add_vline, which
    fails when it tries to compute a numeric midpoint of date strings.
    """
    fig.add_shape(
        type="line",
        xref="x", yref="paper",
        x0=x, x1=x, y0=0, y1=1,
        line=dict(color=line_color, width=line_width, dash=line_dash),
    )
    fig.add_annotation(
        x=x, yref="paper", y=1.0,
        text=label,
        showarrow=False,
        font=dict(size=font_size, color=font_color),
        xanchor="left", yanchor="bottom",
        bgcolor="rgba(255,255,255,0.7)",
    )
    return fig

def make_band_chart(
    daily: pd.DataFrame,
    domain: str,
    bands: dict,
    personal: dict | None = None,
    movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD,
    show_rolling: bool = True,
    episodes: pd.DataFrame | None = None,
    med_notes: pd.DataFrame | None = None,
    height: int = 320,
) -> go.Figure:
    col = f"{domain} Score %"
    if col not in daily.columns or daily.empty:
        return go.Figure()

    dates  = daily["date"].astype(str).tolist()
    scores = daily[col].tolist()
    b = bands.get(domain, DEFAULT_BASELINE_BANDS.get(domain, {}))
    well_c = b.get("well", 20); watch_c = b.get("watch", 40)
    caution_c = b.get("caution", 60); warning_c = b.get("warning", 75)

    fig = go.Figure()

    for label, y0, y1, colour in [
        ("Well",     0,          well_c,    BAND_COLOURS["well"]),
        ("Watch",    well_c,     watch_c,   BAND_COLOURS["watch"]),
        ("Caution",  watch_c,    caution_c, BAND_COLOURS["caution"]),
        ("Warning",  caution_c,  warning_c, BAND_COLOURS["warning"]),
        ("Critical", warning_c,  100,       BAND_COLOURS["critical"]),
    ]:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=colour, line_width=0,
                      annotation_text=label, annotation_position="right",
                      annotation_font_size=10,
                      annotation_font_color=BAND_COLOUR_HEX.get(label.lower(), "#888"))

    for label, ceil in [("well", well_c), ("watch", watch_c),
                         ("caution", caution_c), ("warning", warning_c)]:
        fig.add_hline(y=ceil, line_dash="dot",
                      line_color=BAND_LINE_COLOURS[label], line_width=1)

    if personal:
        pb = personal.get(domain, {})
        if pb.get("reliable") and pb.get("mean") is not None:
            fig.add_hline(y=pb["mean"], line_dash="solid",
                          line_color="rgba(90,130,230,0.8)", line_width=1.5,
                          annotation_text=f"Your baseline ({pb['n']}d)",
                          annotation_position="left", annotation_font_size=10,
                          annotation_font_color="rgba(90,130,230,1)")
            if pb.get("lower") is not None:
                fig.add_hrect(y0=pb["lower"], y1=pb["upper"],
                              fillcolor="rgba(90,130,230,0.08)",
                              line=dict(color="rgba(90,130,230,0.3)", width=1, dash="dot"),
                              annotation_text="+/-1 SD", annotation_position="left",
                              annotation_font_size=9)

    # 7-day rolling average
    if show_rolling:
        avg_col = f"{col} 7d Avg"
        if avg_col in daily.columns:
            fig.add_trace(go.Scatter(
                x=dates, y=daily[avg_col].tolist(), mode="lines",
                name="7d avg", line=dict(color="rgba(100,100,100,0.5)", width=1.5, dash="dash"),
                hovertemplate="7d avg: %{y:.1f}%<extra></extra>",
            ))

    fig.add_trace(go.Scatter(
        x=dates, y=scores, mode="lines+markers", name=domain,
        line=dict(color=DOMAIN_COLOURS.get(domain, "#1C7EF2"), width=2),
        marker=dict(size=5, color=DOMAIN_COLOURS.get(domain, "#1C7EF2")),
        hovertemplate="%{x}<br>Score: %{y:.1f}%<extra></extra>",
    ))

    delta_col = f"{col} Delta"
    deltas = daily[delta_col].tolist() if delta_col in daily.columns else [0.0] * len(scores)
    alert_x, alert_y = [], []
    for i, (s, d) in enumerate(zip(scores, deltas)):
        if d is not None and not (isinstance(d, float) and np.isnan(d)):
            if abs(d) >= movement_threshold:
                if s is not None and not (isinstance(s, float) and np.isnan(s)) and s <= well_c:
                    alert_x.append(dates[i]); alert_y.append(s)
    if alert_x:
        fig.add_trace(go.Scatter(
            x=alert_x, y=alert_y, mode="markers", name="Movement",
            marker=dict(symbol="triangle-up", size=12, color="#FF9500",
                        line=dict(color="white", width=1)),
            hovertemplate="%{x}<br>%{y:.1f}% — notable movement<extra></extra>",
        ))

    # Episode overlays
    if episodes is not None and not episodes.empty:
        fig = add_episode_overlays(fig, episodes)

    # Medication change markers
    if med_notes is not None and not med_notes.empty:
        for _, m in med_notes.iterrows():
            note_text = str(m.get("medication_notes",""))[:40]
            fig = _add_vline_date(fig, x=str(m["date"]), label=f"💊 {note_text}")

    fig.update_layout(
        height=height, margin=dict(l=10, r=90, t=30, b=10),
        yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
        xaxis=dict(title=None), showlegend=False,
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(size=12),
        title=dict(text=domain, font=dict(size=14, color="#1C1C1E"), x=0),
    )
    return fig

def make_overview_chart(daily: pd.DataFrame, bands: dict, height: int = 380) -> go.Figure:
    if daily.empty:
        return go.Figure()
    fig = go.Figure()
    dates = daily["date"].astype(str).tolist()
    for d in DOMAINS:
        col = f"{d} Score %"
        if col not in daily.columns:
            continue
        fig.add_trace(go.Scatter(
            x=dates, y=daily[col].tolist(), mode="lines", name=d,
            line=dict(color=DOMAIN_COLOURS[d], width=2),
            hovertemplate=f"{d}: %{{y:.1f}}%<extra></extra>",
        ))
    for d in DOMAINS:
        b = bands.get(d, DEFAULT_BASELINE_BANDS.get(d, {}))
        fig.add_hline(y=b.get("well", 20), line_dash="dot",
                      line_color="rgba(52,199,89,0.4)", line_width=1)
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
        xaxis=dict(title=None),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig

def make_component_bar(components: pd.DataFrame, domain: str, height: int = 360) -> go.Figure:
    """Horizontal bar chart of normalised item scores for one domain in the latest snapshot."""
    if components.empty:
        return go.Figure()
    colour = DOMAIN_COLOURS.get(domain, "#1C7EF2")
    fig = go.Figure(go.Bar(
        x=components["norm_score"],
        y=components["label"],
        orientation="h",
        marker_color=[
            f"rgba({int(colour[1:3],16)},{int(colour[3:5],16)},{int(colour[5:7],16)},{0.3 + 0.7 * s/100})"
            for s in components["norm_score"]
        ],
        customdata=components[["weight", "weighted_pct"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Score: %{x:.0f}%<br>"
            "Weight: %{customdata[0]:.2f} (%{customdata[1]:.0f}% of domain)<extra></extra>"
        ),
    ))
    fig.add_vline(x=50, line_dash="dot", line_color="rgba(0,0,0,0.2)", line_width=1)
    fig.update_layout(
        height=height, margin=dict(l=10, r=20, t=10, b=10),
        xaxis=dict(range=[0, 100], title="Normalised score (0–100)", ticksuffix="%"),
        yaxis=dict(autorange="reversed", title=None),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(size=11),
    )
    return fig

def _hex_to_rgba(hex_colour: str, alpha: float = 0.15) -> str:
    """Convert a #RRGGBB hex string to an rgba(...) string."""
    h = hex_colour.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def make_component_radar(components_by_domain: dict[str, pd.DataFrame], height: int = 420) -> go.Figure:
    """Radar chart overlaying all domains using their top items."""
    fig = go.Figure()
    for domain, comp in components_by_domain.items():
        if comp.empty:
            continue
        top = comp.head(6)
        categories = top["label"].tolist()
        values = top["norm_score"].tolist()
        categories += [categories[0]]  # close the polygon
        values     += [values[0]]
        colour = DOMAIN_COLOURS.get(domain, "#888888")
        fig.add_trace(go.Scatterpolar(
            r=values, theta=categories, fill="toself", name=domain,
            line=dict(color=colour, width=2),
            fillcolor=_hex_to_rgba(colour, 0.15),
            opacity=0.9,
        ))
    fig.update_layout(
        height=height,
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=40, b=60),
        paper_bgcolor="white",
        font=dict(size=11),
    )
    return fig

def make_snapshot_timeline(snapshots: pd.DataFrame, bands: dict, height: int = 280) -> go.Figure:
    """Stacked area / line chart of all snapshots per day coloured by overall score."""
    if snapshots.empty:
        return go.Figure()
    fig = go.Figure()
    for d in DOMAINS:
        col = f"{d} Score %"
        if col not in snapshots.columns:
            continue
        times = snapshots["submitted_at"].astype(str).tolist()
        fig.add_trace(go.Scatter(
            x=times, y=snapshots[col].tolist(), mode="lines+markers", name=d,
            line=dict(color=DOMAIN_COLOURS[d], width=1.5),
            marker=dict(size=4),
            hovertemplate=f"{d}: %{{y:.1f}}%<extra></extra>",
        ))
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
        xaxis=dict(title=None),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig

# ──────────────────────────────────────────────────────────
# WARNINGS  (with Mixed-aware deduplication)
# ──────────────────────────────────────────────────────────
def build_warnings(daily: pd.DataFrame, snapshots: pd.DataFrame, bands: dict,
                   movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD) -> pd.DataFrame:
    """
    Build warnings with domain deduplication:

    Mixed takes precedence over individual Depression and Mania alerts.
    If Mixed is in caution/warning/critical, Depression and Mania alerts
    are suppressed as primary warnings — they are retained as 'suppressed'
    rows with a note so they can be shown as context rather than top-level alerts.
    Psychosis is always independent and never suppressed.
    Movement alerts are never suppressed.
    """
    rows: list[dict] = []

    def _check_row(row: pd.Series, source: str) -> None:
        scores = {d: float(row.get(f"{d} Score %", 0) or 0) for d in DOMAINS}
        deltas = {d: float(row.get(f"{d} Score % Delta", 0) or 0) for d in DOMAINS}
        domain_bands = {d: classify_score(scores[d], d, bands) for d in DOMAINS}

        mixed_elevated = domain_bands["Mixed"] in ("caution", "warning", "critical")

        for domain in DOMAINS:
            score = scores[domain]
            delta = deltas[domain]
            band  = domain_bands[domain]

            # Determine whether this domain should be suppressed as a
            # standalone warning because Mixed already captures it
            suppress_as_primary = (
                mixed_elevated
                and domain in ("Depression", "Mania")
                and band in ("caution", "warning", "critical")
            )

            if band in ("warning", "critical"):
                rows.append(dict(
                    source=source, domain=domain, severity="High",
                    score_pct=round(score, 1), delta=round(delta, 1), band=band,
                    suppressed=suppress_as_primary,
                    message=f"{domain} score {score:.1f}% — {band} band",
                ))
            elif band == "caution":
                rows.append(dict(
                    source=source, domain=domain, severity="Medium",
                    score_pct=round(score, 1), delta=round(delta, 1), band=band,
                    suppressed=suppress_as_primary,
                    message=f"{domain} score {score:.1f}% — caution band",
                ))

            # Movement alerts — never suppressed
            if band == "well" and abs(delta) >= movement_threshold:
                rows.append(dict(
                    source=source, domain=domain, severity="Movement",
                    score_pct=round(score, 1), delta=round(delta, 1), band=band,
                    suppressed=False,
                    message=f"{domain} moved {delta:+.1f}pp (still in well band)",
                ))

    if not daily.empty:
        _check_row(daily.sort_values("date").iloc[-1], "Daily")
    if not snapshots.empty:
        _check_row(snapshots.sort_values("submitted_at").iloc[-1], "Snapshot")

    if not rows:
        return pd.DataFrame(columns=["source","domain","severity","score_pct","delta","band","suppressed","message"])

    sev_order = {"High": 0, "Medium": 1, "Movement": 2}
    df = pd.DataFrame(rows)
    df["_o"] = df["severity"].map(sev_order).fillna(9)
    return df.sort_values(["suppressed", "_o"]).drop(columns=["_o"]).reset_index(drop=True)

# ──────────────────────────────────────────────────────────
# WEIGHTS PERSISTENCE
# ──────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_weights() -> dict[str, float]:
    ws = safe_worksheet(SETTINGS_TAB)
    if ws is None:
        return DEFAULT_WEIGHTS.copy()
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return DEFAULT_WEIGHTS.copy()
    df = pd.DataFrame(values[1:], columns=values[0])
    if not {"question_code", "weight"}.issubset(df.columns):
        return DEFAULT_WEIGHTS.copy()
    out = DEFAULT_WEIGHTS.copy()
    for _, row in df.iterrows():
        code = str(row["question_code"]).strip()
        parsed = pd.to_numeric(row.get("weight"), errors="coerce")
        if code in out and pd.notna(parsed):
            out[code] = float(parsed)
    return out

def save_weights(weights: dict[str, float]) -> tuple[bool, str]:
    ws = safe_worksheet(SETTINGS_TAB)
    if ws is None:
        return False, f"Worksheet '{SETTINGS_TAB}' not found. Create it manually then try again."
    rows = [["question_code", "weight"]] + [[k, v] for k, v in weights.items()]
    ws.clear()
    ws.update("A1", rows)
    load_weights.clear()
    return True, "Weights saved."

# ──────────────────────────────────────────────────────────
# ANALYSIS HELPERS
# ──────────────────────────────────────────────────────────
def _rolling_trend(series: pd.Series, window: int = 7) -> str:
    clean = series.dropna()
    if len(clean) < 3:
        return "insufficient data"
    slope = np.polyfit(range(len(clean[-window:])), clean[-window:].values, 1)[0]
    if slope > 1.5:  return "rising"
    if slope < -1.5: return "falling"
    return "stable"

def _episode_risk_score(daily: pd.DataFrame) -> dict[str, float]:
    if daily.empty or len(daily) < 2:
        return {d: 0.0 for d in DOMAINS}
    recent = daily.sort_values("date").tail(7)
    w = np.arange(1, len(recent) + 1, dtype=float)
    w /= w.sum()
    return {d: float(np.dot(recent[f"{d} Score %"].fillna(0).values, w)) for d in DOMAINS}

def _consecutive_days_in_band(daily: pd.DataFrame, domain: str,
                               bands: dict, target_bands: list[str]) -> int:
    """Count consecutive most-recent days where domain was in any of the target bands."""
    if daily.empty:
        return 0
    col = f"{domain} Score %"
    if col not in daily.columns:
        return 0
    sorted_df = daily.sort_values("date", ascending=False)
    count = 0
    for score in sorted_df[col]:
        if classify_score(score, domain, bands) in target_bands:
            count += 1
        else:
            break
    return count

def _peak_symptom_items(daily: pd.DataFrame, domain: str, top_n: int = 5) -> pd.DataFrame:
    by_code = _catalog_by_code()
    codes = [q["code"] for q in QUESTION_CATALOG
             if domain in q["domains"] and q["code"] in daily.columns]
    if not codes or daily.empty:
        return pd.DataFrame()
    means = {c: daily[c].mean() for c in codes if pd.api.types.is_numeric_dtype(daily[c])}
    return (
        pd.Series(means, name="mean_raw").reset_index()
        .rename(columns={"index": "code"})
        .assign(question=lambda df: df["code"].map(lambda c: by_code.get(c, {}).get("text", c)))
        .sort_values("mean_raw", ascending=False).head(top_n)
    )

def _cross_domain_correlation(daily: pd.DataFrame) -> pd.DataFrame:
    cols  = [f"{d} Score %" for d in DOMAINS]
    avail = [c for c in cols if c in daily.columns]
    if len(avail) < 2 or len(daily) < 4:
        return pd.DataFrame()
    return daily[avail].corr().round(2)

def _flag_impact(daily: pd.DataFrame) -> pd.DataFrame:
    flag_codes = [q["code"] for q in QUESTION_CATALOG if q["group"] == "flags"]
    avail = [c for c in flag_codes if c in daily.columns]
    if not avail or daily.empty:
        return pd.DataFrame()
    rows = []
    for flag in avail:
        flagged     = daily[daily[flag] == True]
        not_flagged = daily[daily[flag] == False]
        for domain in DOMAINS:
            col = f"{domain} Score %"
            if col not in daily.columns:
                continue
            rows.append(dict(
                flag=flag, domain=domain,
                mean_when_flagged=flagged[col].mean() if not flagged.empty else np.nan,
                mean_when_not_flagged=not_flagged[col].mean() if not not_flagged.empty else np.nan,
            ))
    df = pd.DataFrame(rows).dropna()
    df["impact"] = df["mean_when_flagged"] - df["mean_when_not_flagged"]
    return df.sort_values("impact", ascending=False).reset_index(drop=True)

# ──────────────────────────────────────────────────────────
# EPISODE LOG
# ──────────────────────────────────────────────────────────
EPISODE_TYPES  = ["Depressive", "Hypomanic", "Manic", "Mixed", "Psychotic", "Other"]
EPISODE_COLOURS = {
    "Depressive": _hex_to_rgba("#FF3B30", 0.15),
    "Hypomanic":  _hex_to_rgba("#FF9500", 0.12),
    "Manic":      _hex_to_rgba("#FF9500", 0.20),
    "Mixed":      _hex_to_rgba("#1C7EF2", 0.15),
    "Psychotic":  _hex_to_rgba("#AF52DE", 0.15),
    "Other":      _hex_to_rgba("#8E8E93", 0.12),
}
EPISODE_LINE_COLOURS = {
    "Depressive": "#FF3B30", "Hypomanic": "#FF9500", "Manic": "#FF9500",
    "Mixed": "#1C7EF2", "Psychotic": "#AF52DE", "Other": "#8E8E93",
}

@st.cache_data(ttl=30)
def load_episodes() -> pd.DataFrame:
    """Load episode log from Google Sheet. Returns DataFrame with columns:
    episode_id, episode_type, start_date, end_date, notes."""
    ws = safe_worksheet(EPISODE_TAB)
    if ws is None:
        return pd.DataFrame(columns=["episode_id","episode_type","start_date","end_date","notes"])
    try:
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame(columns=["episode_id","episode_type","start_date","end_date","notes"])
        df = pd.DataFrame(values[1:], columns=values[0])
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date
        df["end_date"]   = pd.to_datetime(df["end_date"],   errors="coerce").dt.date
        return df.dropna(subset=["start_date","end_date"]).reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["episode_id","episode_type","start_date","end_date","notes"])

def _save_episodes(episodes: pd.DataFrame) -> tuple[bool, str]:
    ws = safe_worksheet(EPISODE_TAB)
    if ws is None:
        return False, (
            f"Worksheet '{EPISODE_TAB}' not found. "
            "Create a tab with that exact name in your Google Sheet, then try again."
        )
    rows = [["episode_id","episode_type","start_date","end_date","notes"]]
    for _, row in episodes.iterrows():
        rows.append([
            str(row.get("episode_id","")),
            str(row.get("episode_type","")),
            str(row.get("start_date","")),
            str(row.get("end_date","")),
            str(row.get("notes","")),
        ])
    ws.clear()
    ws.update("A1", rows)
    load_episodes.clear()
    return True, "Episode log saved."

def add_episode(episode_type: str, start_date, end_date, notes: str) -> tuple[bool, str]:
    import datetime, hashlib
    episodes = load_episodes()
    episode_id = hashlib.md5(
        f"{episode_type}{start_date}{end_date}{notes}".encode()
    ).hexdigest()[:8]
    new_row = pd.DataFrame([{
        "episode_id": episode_id,
        "episode_type": episode_type,
        "start_date": start_date,
        "end_date": end_date,
        "notes": notes,
    }])
    updated = pd.concat([episodes, new_row], ignore_index=True)
    return _save_episodes(updated)

def delete_episode(episode_id: str) -> tuple[bool, str]:
    episodes = load_episodes()
    updated = episodes[episodes["episode_id"] != episode_id].reset_index(drop=True)
    return _save_episodes(updated)

def add_episode_overlays(fig: go.Figure, episodes: pd.DataFrame,
                         x_is_date: bool = True) -> go.Figure:
    """Add shaded episode regions and start/end markers to any Plotly figure."""
    if episodes.empty:
        return fig
    for _, ep in episodes.iterrows():
        ep_type = str(ep.get("episode_type", "Other"))
        x0 = str(ep["start_date"])
        x1 = str(ep["end_date"])
        colour = EPISODE_COLOURS.get(ep_type, EPISODE_COLOURS["Other"])
        line_c = EPISODE_LINE_COLOURS.get(ep_type, "#8E8E93")
        notes  = str(ep.get("notes",""))
        label  = ep_type + (f": {notes[:30]}…" if len(notes) > 30 else (f": {notes}" if notes else ""))
        fig.add_vrect(
            x0=x0, x1=x1,
            fillcolor=colour, line_width=1,
            line_color=line_c,
            annotation_text=label,
            annotation_position="top left",
            annotation_font_size=9,
            annotation_font_color=line_c,
        )
    return fig

# ──────────────────────────────────────────────────────────
# MEDICATION NOTES
# ──────────────────────────────────────────────────────────
def build_med_notes_df(wide: pd.DataFrame, daily_scored: pd.DataFrame) -> pd.DataFrame:
    """Extract non-empty medication change notes, joined with daily scores."""
    if wide.empty or "medication_notes" not in wide.columns:
        return pd.DataFrame()
    med = wide[
        wide["medication_notes"].notna() &
        (wide["medication_notes"].astype(str).str.strip() != "")
    ].copy()
    if med.empty:
        return pd.DataFrame()
    med["date"] = med["submitted_date"]
    med = med[["submitted_at","date","medication_notes"]].copy()
    if not daily_scored.empty:
        score_cols = [f"{d} Score %" for d in DOMAINS]
        day_scores = daily_scored[["date"] + [c for c in score_cols if c in daily_scored.columns]].copy()
        med = med.merge(day_scores, on="date", how="left")
    return med.sort_values("submitted_at", ascending=False).reset_index(drop=True)

# ──────────────────────────────────────────────────────────
# CLINICIAN EXPORT
# ──────────────────────────────────────────────────────────
def generate_clinician_report(
    daily: pd.DataFrame,
    bands: dict,
    personal_bl: dict,
    episodes: pd.DataFrame,
    notes: pd.DataFrame,
    med_notes: pd.DataFrame,
    weights: dict,
    wide: pd.DataFrame,
    comments: pd.DataFrame = None,
    window_days: int = 30,
) -> str:
    """Generate a structured plain-text / markdown clinician summary."""
    import datetime
    today = datetime.date.today()
    window_start = today - datetime.timedelta(days=window_days)

    lines: list[str] = []
    lines.append("# Bipolar Dashboard — Clinician Summary")
    lines.append(f"**Generated:** {today.strftime('%d %B %Y')}  ")
    lines.append(f"**Period:** Last {window_days} days ({window_start.strftime('%d %b')} – {today.strftime('%d %b %Y')})")
    lines.append("")

    # ── Current status ──────────────────────────────────────
    lines.append("## Current Status")
    if not daily.empty:
        latest = daily.sort_values("date").iloc[-1]
        mult   = float(latest.get("meta_multiplier", 1.0) or 1.0)
        lines.append(f"**Latest entry:** {latest['date']}  ")
        lines.append(f"**Submissions that day:** {int(latest.get('n_total',1))} "
                     f"({int(latest.get('n_snapshots',0))} snapshot, {int(latest.get('n_reviews',0))} review)")
        lines.append(f"**Meta force multiplier:** ×{mult:.2f}" +
                     (" ⚡ active" if mult > 1.05 else " (baseline)"))
        lines.append("")

        # For the latest date, show snapshot aggregate vs review scores separately
        latest_date = latest["date"]
        day_wide = wide[wide["submitted_date"] == latest_date] if not wide.empty else pd.DataFrame()
        snap_rows   = day_wide[day_wide["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT] if not day_wide.empty else pd.DataFrame()
        review_rows = day_wide[day_wide["submission_type_derived"] == SUBMISSION_TYPE_REVIEW]   if not day_wide.empty else pd.DataFrame()

        lines.append("| Domain | Aggregate | Snapshot avg | Review avg | Band | vs Baseline |")
        lines.append("|--------|-----------|-------------|------------|------|-------------|")
        for d in DOMAINS:
            score = float(latest.get(f"{d} Score %", 0) or 0)
            band  = classify_score(score, d, bands)
            pb    = personal_bl.get(d, {})
            vs_bl = (f"{score - pb['mean']:+.1f}pp"
                     if pb.get("reliable") and pb.get("mean") is not None else "—")
            # Snapshot average for this domain
            snap_avg = "—"
            rev_avg  = "—"
            if not snap_rows.empty:
                # Score each snapshot row and average
                snap_scored = build_scored_table(snap_rows.assign(
                    is_first_of_day=True, submission_order_in_day=1
                ), weights, daily_only=False)
                if not snap_scored.empty and f"{d} Score %" in snap_scored.columns:
                    snap_avg = f"{snap_scored[f'{d} Score %'].mean():.1f}%"
            if not review_rows.empty:
                rev_scored = build_scored_table(review_rows.assign(
                    is_first_of_day=True, submission_order_in_day=1
                ), weights, daily_only=False)
                if not rev_scored.empty and f"{d} Score %" in rev_scored.columns:
                    rev_avg = f"{rev_scored[f'{d} Score %'].mean():.1f}%"
            lines.append(f"| {d} | {score:.1f}% | {snap_avg} | {rev_avg} | {band.upper()} | {vs_bl} |")
    else:
        lines.append("*No daily data available.*")
    lines.append("")

    # ── Recent trends ───────────────────────────────────────
    lines.append("## Domain Trends (last 30 days)")
    period = daily[daily["date"] >= window_start] if not daily.empty else daily
    if not period.empty:
        lines.append("| Domain | Mean % | Peak % | Days in Well | Days in Watch+ | Days in Warning+ |")
        lines.append("|--------|--------|--------|-------------|----------------|-----------------|")
        for d in DOMAINS:
            col = f"{d} Score %"
            if col not in period.columns:
                continue
            scores    = period[col].dropna()
            mean_s    = scores.mean()
            peak_s    = scores.max()
            n_well    = int((scores.apply(lambda s: classify_score(s, d, bands) == "well")).sum())
            n_watch   = int((scores.apply(lambda s: classify_score(s, d, bands) in ["watch","caution","warning","critical"])).sum())
            n_warning = int((scores.apply(lambda s: classify_score(s, d, bands) in ["warning","critical"])).sum())
            lines.append(f"| {d} | {mean_s:.1f}% | {peak_s:.1f}% | {n_well} | {n_watch} | {n_warning} |")
    else:
        lines.append("*No data in this period.*")
    lines.append("")

    # ── Personal baseline ───────────────────────────────────
    lines.append("## Personal Baseline")
    lines.append("*(Computed from days where all domains were in the Well band)*")
    lines.append("")
    for d in DOMAINS:
        pb = personal_bl.get(d, {})
        if pb.get("reliable"):
            lines.append(f"- **{d}:** mean {pb['mean']}%, ±1 SD {pb['lower']}–{pb['upper']}% "
                         f"(based on {pb['n']} well days)")
        else:
            lines.append(f"- **{d}:** baseline not yet reliable ({pb.get('n',0)} well days recorded)")
    lines.append("")

    # ── Episodes ────────────────────────────────────────────
    lines.append("## Labelled Episodes")
    if not episodes.empty:
        recent_ep = episodes[
            pd.to_datetime(episodes["end_date"]) >= pd.Timestamp(window_start)
        ]
        if not recent_ep.empty:
            for _, ep in recent_ep.sort_values("start_date", ascending=False).iterrows():
                lines.append(
                    f"- **{ep['episode_type']}** — "
                    f"{ep['start_date']} to {ep['end_date']}"
                    + (f": {ep['notes']}" if ep.get("notes") else "")
                )
        else:
            lines.append("*No episodes ending in this period.*")
    else:
        lines.append("*No episodes labelled yet.*")
    lines.append("")

    # ── Medication notes ────────────────────────────────────
    lines.append("## Medication Notes")
    if not med_notes.empty:
        recent_med = med_notes[med_notes["date"] >= window_start] if not med_notes.empty else med_notes
        if not recent_med.empty:
            for _, m in recent_med.sort_values("submitted_at", ascending=False).iterrows():
                lines.append(f"- **{m['date']}:** {m['medication_notes']}")
        else:
            lines.append("*No medication notes in this period.*")
    else:
        lines.append("*No medication notes recorded.*")
    lines.append("")

    # ── Journal highlights ──────────────────────────────────
    lines.append("## Journal Highlights")
    lines.append("*(Entries from days in Caution band or above)*")
    if not notes.empty:
        elevated = notes[notes["worst_band"].isin(["caution","warning","critical"])]
        recent_notes = elevated[elevated["date"] >= window_start] if not elevated.empty else elevated
        if not recent_notes.empty:
            for _, n in recent_notes.sort_values("submitted_at", ascending=False).head(10).iterrows():
                band = n.get("worst_band","")
                text = str(n.get("experience_description",""))[:300]
                lines.append(f"- **{n['date']}** [{band.upper()}]: {text}" +
                             ("…" if len(str(n.get("experience_description",""))) > 300 else ""))
                # Append any comments for this entry
                if comments is not None and not comments.empty:
                    sid = str(n.get("submission_id",""))
                    entry_comments = get_comments_for_submission(sid, comments)
                    for c in entry_comments:
                        c_time = str(c.get("commented_at",""))[:16]
                        c_text = str(c.get("comment_text",""))
                        lines.append(f"  - 💬 *Note ({c_time}):* {c_text}")
        else:
            lines.append("*No elevated-band journal entries in this period.*")
    else:
        lines.append("*No journal entries.*")
    lines.append("")

    # ── Footer ──────────────────────────────────────────────
    lines.append("---")
    lines.append("*This summary was generated automatically from self-reported daily monitoring data. "
                 "It is intended to support clinical conversation, not to replace clinical judgement.*")

    return "\n".join(lines)

# ──────────────────────────────────────────────────────────
# PSYCHOSIS INSIGHT DIVERGENCE DETECTOR
# ──────────────────────────────────────────────────────────
# Primary psychosis symptom items — these capture the experiences themselves
PSY_PRIMARY_CODES = [
    "psy_heard_saw",        # hallucinations
    "psy_suspicious",       # paranoia / persecutory thinking
    "psy_trust_perceptions",# derealisation / derealization
    "psy_distress",         # distress caused by experiences
]

# Insight items — these capture awareness that something is wrong
# In our model these are inverted in the Psychosis domain, but here we
# read them at face value: high = good insight, low = poor insight
PSY_INSIGHT_CODES = [
    "meta_something_wrong",  # "do I think something may be wrong?"
    "meta_concerned",        # "am I concerned about my current state?"
    "psy_confidence_reality",# "how confident have I been in the reality of these experiences?"
    # Note: psy_confidence_reality is already in the psychosis domain at face value
    # (higher confidence in abnormal experiences = worse), so we re-read it inverted
    # here as an insight proxy: lower confidence in those experiences = better insight
]

def _mean_normalised(row: pd.Series, codes: list[str], invert: bool = False) -> float | None:
    """
    Mean normalised score (0–100) for a set of scale_1_5 items in a row.
    Returns None if no items are present.
    invert=True flips the score (100 - score) before averaging.
    """
    by_code = _catalog_by_code()
    scores = []
    for code in codes:
        if code not in row.index:
            continue
        raw = row[code]
        v = pd.to_numeric(raw, errors="coerce")
        if pd.isna(v):
            continue
        norm = float(min(max((v - 1.0) / 4.0 * 100.0, 0.0), 100.0))
        scores.append(100.0 - norm if invert else norm)
    return float(np.mean(scores)) if scores else None


def detect_psychosis_insight_divergence(
    daily: pd.DataFrame,
    window: int = 7,
    drop_threshold: float = 15.0,
    divergence_threshold: float = 12.0,
) -> dict:
    """
    Analyse the last `window` days of daily data to detect whether a fall
    in psychosis scores reflects genuine improvement or possible loss of insight.

    Returns a dict with:
      status:       "improvement" | "ambiguous" | "loss_of_insight" | "stable" | "insufficient_data"
      primary_delta:  change in mean primary symptom score over window (negative = falling)
      insight_delta:  change in mean insight score over window (negative = falling = worse insight)
      finding:        plain-English description
      severity:       "ok" | "caution" | "warning"
      days_analysed:  int
    """
    result = dict(
        status="insufficient_data",
        primary_delta=None,
        insight_delta=None,
        finding="Not enough data to assess psychosis insight divergence.",
        severity="ok",
        days_analysed=0,
    )

    if daily.empty or len(daily) < 3:
        return result

    recent = daily.sort_values("date").tail(window).copy()
    n = len(recent)
    result["days_analysed"] = n

    # Compute per-row scores for primary symptoms and insight
    # psy_confidence_reality: high score (confident in abnormal experiences) = bad,
    # so we invert it to use as an insight proxy (low confidence = good insight = high score here)
    primary_scores = recent.apply(
        lambda r: _mean_normalised(r, PSY_PRIMARY_CODES, invert=False), axis=1
    ).dropna()

    insight_scores = recent.apply(
        lambda r: _mean_normalised(
            r,
            # meta_something_wrong and meta_concerned: high = good insight (higher_worse scale,
            # so high score means they think something IS wrong — that's good insight)
            # psy_confidence_reality: high = bad insight, so invert it
            ["meta_something_wrong", "meta_concerned"],
            invert=False,
        ),
        axis=1,
    ).dropna()

    confidence_scores = recent.apply(
        lambda r: _mean_normalised(r, ["psy_confidence_reality"], invert=True),
        # inverted: high confidence in abnormal experiences → low insight score
        axis=1,
    ).dropna()

    if len(primary_scores) < 2 or len(insight_scores) < 2:
        return result

    # Compute trend as (last third mean) - (first third mean)
    def _trend(s: pd.Series) -> float:
        third = max(1, len(s) // 3)
        return float(s.tail(third).mean() - s.head(third).mean())

    primary_delta = _trend(primary_scores)
    insight_delta = _trend(insight_scores)   # negative = insight worsening
    confidence_delta = _trend(confidence_scores) if len(confidence_scores) >= 2 else 0.0

    result["primary_delta"] = round(primary_delta, 1)
    result["insight_delta"] = round(insight_delta, 1)

    primary_falling  = primary_delta  < -drop_threshold
    insight_falling  = insight_delta  < -divergence_threshold
    insight_stable   = abs(insight_delta) < divergence_threshold
    insight_rising   = insight_delta  >  divergence_threshold
    confidence_poor  = confidence_delta < -divergence_threshold  # less critical insight

    if not primary_falling:
        # Psychosis not falling — standard monitoring
        result["status"]   = "stable"
        result["finding"]  = "Psychosis scores are not falling. No divergence to assess."
        result["severity"] = "ok"
        return result

    # Primary symptoms ARE falling — now assess what insight is doing
    if primary_falling and (insight_stable or insight_rising):
        # Good sign: symptoms falling, insight holding or improving
        result["status"]  = "improvement"
        result["finding"] = (
            f"Psychosis scores have fallen (~{abs(primary_delta):.0f}pp over {n} days) "
            f"and insight indicators are {'holding steady' if insight_stable else 'improving'}. "
            f"This pattern is consistent with genuine improvement."
        )
        result["severity"] = "ok"

    elif primary_falling and insight_falling and not confidence_poor:
        # Ambiguous: symptoms and insight both falling, but confidence not dramatically shifted
        result["status"]  = "ambiguous"
        result["finding"] = (
            f"Psychosis scores have fallen (~{abs(primary_delta):.0f}pp over {n} days), "
            f"but insight indicators have also declined (~{abs(insight_delta):.0f}pp). "
            f"It is unclear whether this reflects genuine improvement or reduced awareness "
            f"of ongoing experiences. Worth discussing with your clinician."
        )
        result["severity"] = "caution"

    elif primary_falling and insight_falling and confidence_poor:
        # Most concerning: symptoms falling, insight falling, and confidence in
        # the reality of experiences increasing — classic loss-of-insight picture
        result["status"]  = "loss_of_insight"
        result["finding"] = (
            f"Psychosis scores have fallen (~{abs(primary_delta):.0f}pp over {n} days), "
            f"but insight indicators have also declined significantly (~{abs(insight_delta):.0f}pp) "
            f"and confidence in the reality of experiences appears to be increasing. "
            f"This pattern may reflect loss of insight rather than genuine improvement — "
            f"experiences may feel more real and less alarming, not because they are resolving. "
            f"This warrants prompt clinical review."
        )
        result["severity"] = "warning"

    else:
        result["status"]  = "ambiguous"
        result["finding"] = (
            f"Psychosis scores have fallen (~{abs(primary_delta):.0f}pp over {n} days). "
            f"The insight picture is mixed. Monitor closely."
        )
        result["severity"] = "caution"

    return result


def _generate_insights(daily, risk, trends, bands, personal, movement_threshold) -> list[dict]:
    insights: list[dict] = []

    # Active multiplier — surface prominently when non-trivial
    if not daily.empty and "meta_multiplier" in daily.columns:
        latest_mult = float(daily.sort_values("date").iloc[-1].get("meta_multiplier", 1.0) or 1.0)
        if latest_mult >= 1.20:
            insights.append(dict(level="warning", domain="Meta",
                text=f"**Meta force multiplier is ×{latest_mult:.2f}** — meta questions signal "
                     f"strong intensification or a sense of approaching episode. "
                     f"All domain scores are amplified by this factor."))
        elif latest_mult >= 1.10:
            insights.append(dict(level="caution", domain="Meta",
                text=f"**Meta force multiplier is ×{latest_mult:.2f}** — mild amplification "
                     f"active (intensifying state or feeling unlike yourself)."))

    # Psychosis insight divergence
    psy_divergence = detect_psychosis_insight_divergence(daily)
    if psy_divergence["status"] not in ("stable", "insufficient_data", "improvement"):
        insights.append(dict(
            level=psy_divergence["severity"],
            domain="Psychosis",
            text=f"**Psychosis score interpretation:** {psy_divergence['finding']}",
        ))
    elif psy_divergence["status"] == "improvement":
        # Surface positive finding too — reassurance is useful information
        insights.append(dict(
            level="ok",
            domain="Psychosis",
            text=f"✓ **Psychosis scores falling with insight intact** — {psy_divergence['finding']}",
        ))

    for domain in DOMAINS:
        r    = risk.get(domain, 0)
        t    = trends.get(domain, "stable")
        band = classify_score(r, domain, bands)
        streak = _consecutive_days_in_band(daily, domain, bands,
                                           ["caution", "warning", "critical"])
        if band in ("warning", "critical"):
            insights.append(dict(level="warning", domain=domain,
                text=f"**{domain}** momentum score is {r:.0f}% — in the **{band}** band."))
        elif band == "caution":
            insights.append(dict(level="caution", domain=domain,
                text=f"**{domain}** momentum score {r:.0f}% is in the **caution** band."))
        if streak >= 3:
            insights.append(dict(level="caution", domain=domain,
                text=f"**{domain}** has been in elevated bands for **{streak} consecutive days**."))
        if t == "rising" and band != "well":
            insights.append(dict(level="caution", domain=domain,
                text=f"**{domain}** has been trending upward over the last 7 days."))
        pb = personal.get(domain, {})
        if pb.get("reliable") and pb.get("upper") is not None:
            if r > pb["upper"] and band == "well":
                insights.append(dict(level="caution", domain=domain,
                    text=f"**{domain}** score ({r:.0f}%) is above your personal baseline "
                         f"upper bound ({pb['upper']}%) — above your normal range even "
                         f"within the standard well band."))
    if not daily.empty and "dep_self_harm_ideation" in daily.columns:
        peak = daily.tail(7)["dep_self_harm_ideation"].max()
        if pd.notna(peak) and peak > SELF_HARM_FLAG_THRESHOLD:
            insights.append(dict(level="critical", domain="Depression",
                text=f"Self-harm ideation reached **{peak:.0f}/5** in the last 7 days. "
                     f"Please review with your clinician regardless of overall score."))
    if not daily.empty and "func_sleep_hours" in daily.columns:
        mean_sleep = daily.tail(7)["func_sleep_hours"].mean()
        if pd.notna(mean_sleep) and mean_sleep < 5.5:
            insights.append(dict(level="caution", domain="General",
                text=f"Mean sleep over the last 7 days is **{mean_sleep:.1f} hours** — below threshold."))
    if not daily.empty:
        for domain in DOMAINS:
            delta_col = f"{domain} Score % Delta"
            score_col = f"{domain} Score %"
            if delta_col not in daily.columns:
                continue
            latest = daily.sort_values("date").iloc[-1]
            delta  = latest.get(delta_col, 0) or 0
            score  = latest.get(score_col, 0) or 0
            band   = classify_score(score, domain, bands)
            if band == "well" and abs(delta) >= movement_threshold:
                insights.append(dict(level="caution", domain=domain,
                    text=f"**{domain}** moved **{delta:+.1f}pp** since yesterday (still in well band)."))
    if not insights:
        insights.append(dict(level="ok", domain="General",
            text="No alerts. All domain scores are within expected ranges."))
    return insights

# ──────────────────────────────────────────────────────────
# SETTINGS UI
# ──────────────────────────────────────────────────────────
def render_weights_editor(weights: dict[str, float]) -> dict[str, float]:
    st.markdown("### Scoring weights")
    st.caption(
        "Note: sleep weights are additionally scaled by domain-specific multipliers "
        "(Depression: ×0.35/×0.45 for hours/quality; Mania & Mixed: ×1.0). "
        "This reflects sleep's role as a driver in mania/mixed but a symptom in depression."
    )
    if not safe_worksheet(SETTINGS_TAB):
        st.warning(f"Worksheet '{SETTINGS_TAB}' not found — weights are in-memory only.")
    cat = catalog_df()
    updated = weights.copy()
    for group in ["depression","mania","mixed","psychosis","functioning","flags","observations"]:
        rows = cat[cat["group"] == group]
        if rows.empty:
            continue
        with st.expander(group.title(), expanded=False):
            for _, row in rows.iterrows():
                code = row["code"]
                if code not in updated:
                    continue
                updated[code] = st.number_input(
                    code, min_value=0.0, max_value=10.0, step=0.25,
                    value=float(updated.get(code, 0.0)), key=f"w_{code}",
                )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save weights", type="primary"):
            ok, msg = save_weights(updated)
            (st.success if ok else st.error)(msg)
    with c2:
        if st.button("Reset to defaults"):
            ok, msg = save_weights(DEFAULT_WEIGHTS.copy())
            (st.success if ok else st.error)("Reset." if ok else msg)
    return updated

def render_baseline_editor(config: dict) -> dict:
    st.markdown("### Baseline band thresholds")
    st.caption("Upper bound of each band (0–100). Bands must be ascending: Well < Watch < Caution < Warning.")
    if not safe_worksheet(BASELINE_TAB):
        st.warning(f"Worksheet '{BASELINE_TAB}' not found — changes are in-memory only.")
    updated = {
        "bands": {d: v.copy() for d, v in config["bands"].items()},
        "movement_threshold": config["movement_threshold"],
        "personal_baseline_window": config["personal_baseline_window"],
    }
    for domain in DOMAINS:
        with st.expander(domain, expanded=True):
            b = updated["bands"][domain]
            cols = st.columns(4)
            b["well"]    = cols[0].number_input("Well",    0.0, 100.0, float(b["well"]),    0.5, key=f"bl_{domain}_well")
            b["watch"]   = cols[1].number_input("Watch",   0.0, 100.0, float(b["watch"]),   0.5, key=f"bl_{domain}_watch")
            b["caution"] = cols[2].number_input("Caution", 0.0, 100.0, float(b["caution"]), 0.5, key=f"bl_{domain}_caution")
            b["warning"] = cols[3].number_input("Warning", 0.0, 100.0, float(b["warning"]), 0.5, key=f"bl_{domain}_warning")
            if [b["well"], b["watch"], b["caution"], b["warning"]] != sorted([b["well"], b["watch"], b["caution"], b["warning"]]):
                st.warning("Ceilings must be in ascending order.")
    st.divider()
    updated["movement_threshold"] = st.number_input(
        "Movement alert threshold (pp)", 1.0, 50.0, float(updated["movement_threshold"]), 0.5, key="bl_movement")
    updated["personal_baseline_window"] = st.number_input(
        "Personal baseline window (well days)", 14, 365, int(updated["personal_baseline_window"]), 1, key="bl_window")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save baseline config", type="primary"):
            ok, msg = save_baseline_config(updated)
            (st.success if ok else st.error)(msg)
    with c2:
        if st.button("Reset baseline to defaults"):
            default_cfg = {"bands": {d: v.copy() for d, v in DEFAULT_BASELINE_BANDS.items()},
                           "movement_threshold": DEFAULT_MOVEMENT_THRESHOLD,
                           "personal_baseline_window": 90}
            ok, msg = save_baseline_config(default_cfg)
            (st.success if ok else st.error)("Reset." if ok else msg)
    return updated

# ──────────────────────────────────────────────────────────
# DATA LOAD
# ──────────────────────────────────────────────────────────
try:
    wb = _workbook()
    st.caption(f"Connected to **{wb.title}** | worksheet: *{NEW_FORM_TAB}*")
except Exception as exc:
    st.error("Google Sheets connection failed.")
    st.exception(exc)
    st.stop()

weights      = load_weights()
bl_config    = load_baseline_config()
bands        = bl_config["bands"]
mv_threshold = bl_config["movement_threshold"]
pb_window    = bl_config["personal_baseline_window"]

raw_df       = load_sheet(NEW_FORM_TAB)
indexed_df   = add_submission_indexing(raw_df)
wide_df      = clean_and_widen(indexed_df)
snapshots_df = build_scored_table(wide_df, weights, daily_only=False)
daily_df     = build_daily_aggregate(wide_df, weights)
warnings_df  = build_warnings(daily_df, snapshots_df, bands, mv_threshold)
episodes_df  = load_episodes()
personal_bl  = compute_personal_baseline(daily_df, bands, pb_window, episodes=episodes_df)
notes_df     = build_notes_df(wide_df, daily_df, bands)
med_notes_df = build_med_notes_df(wide_df, daily_df)
comments_df  = load_comments()

# ──────────────────────────────────────────────────────────
# GLOBAL FILTERS (sidebar)
# ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Filters")
    st.caption("Applied to all charts and tables.")

    # Refresh control
    import datetime as _dt
    if "last_refreshed" not in st.session_state:
        st.session_state["last_refreshed"] = _dt.datetime.now()
    elapsed = int((_dt.datetime.now() - st.session_state["last_refreshed"]).total_seconds())
    st.caption(f"Data last refreshed {elapsed}s ago")
    if st.button("🔄 Refresh data", use_container_width=True):
        load_sheet.clear()
        load_episodes.clear()
        load_weights.clear()
        load_baseline_config.clear()
        load_comments.clear()
        st.session_state["last_refreshed"] = _dt.datetime.now()
        st.rerun()
    st.divider()

    if not daily_df.empty:
        min_date = daily_df["date"].min()
        max_date = daily_df["date"].max()
        import datetime
        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date, max_value=max_date,
            key="filter_dates",
        )
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            filter_start, filter_end = date_range
        else:
            filter_start, filter_end = min_date, max_date
    else:
        filter_start, filter_end = None, None

    selected_domains = st.multiselect(
        "Domains to show",
        options=DOMAINS,
        default=DOMAINS,
        key="filter_domains",
    )
    show_rolling = st.toggle("Show 7-day rolling average", value=True, key="filter_rolling")
    st.divider()
    st.markdown("#### Chart height")
    chart_height = st.slider("px", 200, 600, 320, 20, key="filter_height")

# Apply date filter to daily_df and snapshots_df
def _apply_date_filter(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    if df.empty or filter_start is None:
        return df
    return df[(df[date_col] >= filter_start) & (df[date_col] <= filter_end)].copy()

daily_filtered     = _apply_date_filter(daily_df)
snapshots_filtered = _apply_date_filter(snapshots_df, "submitted_date")
notes_filtered     = _apply_date_filter(notes_df, "date") if not notes_df.empty else notes_df

# ──────────────────────────────────────────────────────────
# SUMMARY METRICS ROW
# ──────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total entries",   len(raw_df))
m2.metric("Days tracked",    len(daily_df))
m3.metric("Snapshots",       int(wide_df["submission_type_derived"].eq(SUBMISSION_TYPE_SNAPSHOT).sum()) if "submission_type_derived" in wide_df.columns else len(snapshots_df))
m4.metric("Active warnings", int(len(warnings_df[
    (warnings_df["severity"] == "High") &
    (~warnings_df["suppressed"] if "suppressed" in warnings_df.columns else True)
])) if not warnings_df.empty else 0)
if not daily_df.empty:
    lo = float(daily_df["Overall Score %"].iloc[-1])
    pr = float(daily_df["Overall Score %"].iloc[-2]) if len(daily_df) > 1 else lo
    m5.metric("Latest overall score", f"{lo:.1f}%", delta=f"{lo - pr:+.1f}%")
else:
    m5.metric("Latest overall score", "—")

# DOMAIN STATUS ROW
if not daily_df.empty:
    latest = daily_df.sort_values("date").iloc[-1]
    latest_multiplier = float(latest.get("meta_multiplier", 1.0) or 1.0)
    multiplier_note = (
        f"  \n⚡ *Meta multiplier: ×{latest_multiplier:.2f}*"
        if latest_multiplier > 1.05 else ""
    )
    status_cols = st.columns(len(DOMAINS))
    for i, domain in enumerate(DOMAINS):
        score     = float(latest.get(f"{domain} Score %", 0) or 0)
        raw_score = float(latest.get(f"{domain} Score % (raw)", score) or score)
        band      = classify_score(score, domain, bands)
        delta     = float(latest.get(f"{domain} Score % Delta", 0) or 0)
        pb        = personal_bl.get(domain, {})
        pb_note   = ""
        if pb.get("reliable") and pb.get("mean") is not None:
            diff    = score - pb["mean"]
            pb_note = f"\n*vs baseline: {diff:+.1f}pp*"
        streak      = _consecutive_days_in_band(daily_df, domain, bands, ["caution","warning","critical"])
        streak_note = f"\n*{streak}d elevated streak*" if streak >= 2 else ""
        raw_note    = f"\n*raw: {raw_score:.1f}%*" if latest_multiplier > 1.05 else ""
        status_cols[i].markdown(
            f"**{domain}**  \n"
            f"{BAND_EMOJI[band]} **{band.upper()}** — {score:.1f}%  \n"
            f"Δ {delta:+.1f}pp{raw_note}{pb_note}{streak_note}"
        )
    if latest_multiplier > 1.05:
        st.caption(
            f"⚡ **Meta force multiplier active: ×{latest_multiplier:.2f}** — "
            f"domain scores are amplified because meta questions signal "
            f"intensification, approaching episode, or feeling unlike yourself. "
            f"Raw (pre-multiplier) scores shown in italics above."
        )

st.divider()

# ──────────────────────────────────────────────────────────
# TABS
# ──────────────────────────────────────────────────────────
(tab_overview, tab_snapshots_tab, tab_analysis,
 tab_baseline, tab_journal, tab_episodes, tab_export,
 tab_questions, tab_daily, tab_data, tab_settings) = st.tabs([
    "Overview", "Snapshots", "Analysis", "Baselines",
    "Journal", "Episodes", "Clinician Export",
    "Questions", "Daily Model", "Data Layer", "Settings"
])

# ── OVERVIEW ──────────────────────────────────────────────
with tab_overview:
    st.markdown("### Alerts")
    if warnings_df.empty:
        st.success("No active alerts.")
    else:
        sev_icon = {"High": "🔴", "Medium": "🟡", "Movement": "🟠"}

        primary   = warnings_df[~warnings_df["suppressed"]] if "suppressed" in warnings_df.columns else warnings_df
        suppressed = warnings_df[warnings_df["suppressed"]]  if "suppressed" in warnings_df.columns else pd.DataFrame()

        if primary.empty:
            st.success("No active primary alerts.")
        else:
            for _, w in primary.iterrows():
                st.markdown(f"{sev_icon.get(w['severity'], 'ℹ️')} **{w['domain']}** ({w['source']}) — {w['message']}")

        # Show suppressed Dep/Mania as context under a mixed warning
        if not suppressed.empty:
            mixed_active = (
                not primary[primary["domain"] == "Mixed"].empty
                if not primary.empty else False
            )
            if mixed_active:
                suppressed_names = suppressed["domain"].unique().tolist()
                context_parts = []
                for d in suppressed_names:
                    rows_d = suppressed[suppressed["domain"] == d]
                    if not rows_d.empty:
                        score = rows_d.iloc[0]["score_pct"]
                        band  = rows_d.iloc[0]["band"]
                        context_parts.append(f"{d}: {score:.1f}% ({band})")
                if context_parts:
                    st.caption(
                        f"ℹ️ Also elevated as expected Mixed components — "
                        + ", ".join(context_parts)
                        + ". Shown here for context; Mixed is the primary alert."
                    )

    if not daily_filtered.empty:
        filtered_domains = [d for d in selected_domains if d in DOMAINS]

        st.markdown("### All domains over time")
        st.caption("Dotted green lines = Well band ceiling. Dashed grey = 7-day rolling average.")
        fig_all = go.Figure()
        dates = daily_filtered["date"].astype(str).tolist()
        for d in filtered_domains:
            col = f"{d} Score %"
            if col not in daily_filtered.columns:
                continue
            fig_all.add_trace(go.Scatter(
                x=dates, y=daily_filtered[col].tolist(), mode="lines", name=d,
                line=dict(color=DOMAIN_COLOURS[d], width=2),
                hovertemplate=f"{d}: %{{y:.1f}}%<extra></extra>",
            ))
            if show_rolling:
                avg_col = f"{col} 7d Avg"
                if avg_col in daily_filtered.columns:
                    fig_all.add_trace(go.Scatter(
                        x=dates, y=daily_filtered[avg_col].tolist(), mode="lines",
                        name=f"{d} 7d avg", showlegend=False,
                        line=dict(color=DOMAIN_COLOURS[d], width=1, dash="dash"),
                        opacity=0.4,
                        hovertemplate=f"{d} 7d avg: %{{y:.1f}}%<extra></extra>",
                    ))
        for d in filtered_domains:
            b = bands.get(d, DEFAULT_BASELINE_BANDS.get(d, {}))
            fig_all.add_hline(y=b.get("well", 20), line_dash="dot",
                              line_color="rgba(52,199,89,0.35)", line_width=1)

        # Episode overlays on the all-domains chart
        fig_all = add_episode_overlays(fig_all, episodes_df)

        # Medication markers on the all-domains chart
        if not med_notes_df.empty:
            med_in_range = med_notes_df[
                (med_notes_df["date"] >= filter_start) &
                (med_notes_df["date"] <= filter_end)
            ] if filter_start else med_notes_df
            for _, m in med_in_range.iterrows():
                note_text = str(m.get("medication_notes",""))[:35]
                fig_all = _add_vline_date(fig_all, x=str(m["date"]), label=f"💊 {note_text}")

        fig_all.update_layout(
            height=chart_height, margin=dict(l=10, r=10, t=10, b=10),
            yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
            xaxis=dict(title=None),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig_all, use_container_width=True)

        # Medication change markers on the overview chart
        if not med_notes_df.empty:
            med_in_range = med_notes_df[med_notes_df["date"] >= filter_start] if filter_start else med_notes_df
            if not med_in_range.empty:
                st.caption("💊 Vertical dashed lines on the chart above mark days with medication notes.")

        st.markdown("### Per-domain charts")
        c1, c2 = st.columns(2)
        for i, domain in enumerate(filtered_domains):
            with (c1 if i % 2 == 0 else c2):
                st.plotly_chart(
                    make_band_chart(daily_filtered, domain, bands,
                                    personal=personal_bl,
                                    movement_threshold=mv_threshold,
                                    show_rolling=show_rolling,
                                    episodes=episodes_df,
                                    med_notes=med_notes_df,
                                    height=chart_height),
                    use_container_width=True,
                )

# ── SNAPSHOTS ─────────────────────────────────────────────
with tab_snapshots_tab:
    st.markdown("## Snapshots")
    st.caption(
        "All submissions within each day, not just the first. "
        "Use these to understand intraday variation and what's driving each domain score."
    )

    if snapshots_filtered.empty:
        st.info("No snapshot data in the selected date range.")
    else:
        # Timeline of all snapshots
        st.markdown("### All snapshots over time")
        filtered_domains = [d for d in selected_domains if d in DOMAINS]
        st.plotly_chart(make_snapshot_timeline(snapshots_filtered, bands, height=chart_height),
                        use_container_width=True)

        st.divider()

        # Pick a snapshot to drill into
        st.markdown("### Component breakdown — pick a submission")
        st.caption("Select a submission to see exactly what's contributing to each domain score.")

        snap_options = snapshots_filtered.sort_values("submitted_at", ascending=False)
        snap_labels  = snap_options["submitted_at"].astype(str).tolist()

        if snap_labels:
            selected_snap_label = st.selectbox("Submission", snap_labels, index=0, key="snap_picker")
            snap_row = snap_options[snap_options["submitted_at"].astype(str) == selected_snap_label].iloc[0]

            # Domain score summary for selected snapshot
            score_cols_s = st.columns(len(DOMAINS))
            for i, domain in enumerate(DOMAINS):
                score = float(snap_row.get(f"{domain} Score %", 0) or 0)
                band  = classify_score(score, domain, bands)
                score_cols_s[i].metric(domain, f"{score:.1f}%", delta=f"{BAND_EMOJI[band]} {band}", delta_color="off")

            st.divider()
            st.markdown("### What's driving each domain?")
            st.caption(
                "Bars show the normalised score (0–100%) for each contributing item. "
                "Darker = higher symptom load. Hover for weight information."
            )

            comp_by_domain: dict[str, pd.DataFrame] = {}
            for domain in selected_domains:
                comp = get_snapshot_components(snap_row, domain, weights)
                comp_by_domain[domain] = comp

            # Radar overview
            st.markdown("#### Symptom radar — top items per domain")
            st.plotly_chart(make_component_radar(comp_by_domain, height=420), use_container_width=True)

            # Bar charts per domain
            st.markdown("#### Per-domain item breakdown")
            d_cols = st.columns(2)
            for i, domain in enumerate(selected_domains):
                comp = comp_by_domain.get(domain, pd.DataFrame())
                with d_cols[i % 2]:
                    st.markdown(f"**{domain}**")
                    if comp.empty:
                        st.info("No data.")
                    else:
                        st.plotly_chart(make_component_bar(comp, domain, height=max(260, len(comp) * 28)),
                                        use_container_width=True)

            st.divider()

            # Submissions per day chart
            st.markdown("### Submissions per day")
            subs_per_day = (
                snapshots_filtered.groupby("submitted_date")
                .size().reset_index(name="count")
            )
            fig_subs = px.bar(subs_per_day, x="submitted_date", y="count",
                              color_discrete_sequence=["#1C7EF2"])
            fig_subs.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10),
                                   xaxis_title=None, yaxis_title="Submissions",
                                   plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_subs, use_container_width=True)

            st.divider()
            st.markdown("### Raw snapshot table")
            display_cols = ["submitted_at"] + [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]
            st.dataframe(snapshots_filtered[[c for c in display_cols if c in snapshots_filtered.columns]],
                         use_container_width=True)

# ── ANALYSIS ──────────────────────────────────────────────
with tab_analysis:
    st.markdown("## Data Analysis")
    if daily_filtered.empty:
        st.info("No data in the selected date range.")
    else:
        risk   = _episode_risk_score(daily_filtered)
        trends = {d: _rolling_trend(daily_filtered[f"{d} Score %"]) for d in DOMAINS}

        st.markdown("### Insights")
        insights = _generate_insights(daily_filtered, risk, trends, bands, personal_bl, mv_threshold)
        lv_icon  = {"critical": "🚨", "warning": "⚠️", "caution": "💛", "ok": "✅"}
        for ins in insights:
            st.markdown(f"{lv_icon.get(ins['level'], 'ℹ️')} {ins['text']}")

        st.divider()
        st.markdown("### Momentum-weighted episode risk (last 7 days)")
        rc = st.columns(len(DOMAINS))
        for i, domain in enumerate(DOMAINS):
            r    = risk[domain]
            band = classify_score(r, domain, bands)
            rc[i].metric(domain, f"{r:.1f}%", delta=f"{BAND_EMOJI[band]} {band}", delta_color="off")

        st.divider()
        st.markdown("### 7-day trend vs baseline")
        pb_rows = []
        for d in DOMAINS:
            pb = personal_bl.get(d, {})
            trend_display = {"rising": "rising ↑", "falling": "falling ↓", "stable": "stable →"}.get(trends[d], trends[d])
            pb_rows.append({
                "Domain": d,
                "7d Trend": trend_display,
                "7d Mean %": round(daily_filtered[f"{d} Score %"].tail(7).mean(), 1),
                "7d Peak %": round(daily_filtered[f"{d} Score %"].tail(7).max(), 1),
                "Personal Baseline": f"{pb['mean']}%" if pb.get("reliable") else "not yet reliable",
                "Baseline ±1 SD":    f"{pb['lower']}–{pb['upper']}%" if pb.get("reliable") else "—",
                "Well Ceiling":      f"{bands.get(d, {}).get('well', '?')}%",
            })
        st.dataframe(pd.DataFrame(pb_rows), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Psychosis insight analysis")
        st.caption(
            "A falling Psychosis score can mean two very different things: "
            "genuine improvement, or loss of insight where experiences no longer "
            "feel unusual or alarming. This section attempts to distinguish between them "
            "by comparing primary symptom trends against insight indicator trends."
        )

        psy_div = detect_psychosis_insight_divergence(daily_filtered)

        sev_colours = {
            "ok":      ("#34C759", "🟢"),
            "caution": ("#FF9500", "🟠"),
            "warning": ("#FF3B30", "🔴"),
        }
        col_colour, col_emoji = sev_colours.get(psy_div["severity"], ("#8E8E93", "⚪"))
        col_emoji_str = col_emoji

        st.markdown(f"{col_emoji_str} **{psy_div['status'].replace('_', ' ').title()}**")
        st.markdown(psy_div["finding"])

        if psy_div["status"] not in ("insufficient_data", "stable"):
            pd_cols = st.columns(3)
            pd_cols[0].metric(
                "Primary symptom trend",
                f"{psy_div['primary_delta']:+.1f}pp" if psy_div["primary_delta"] is not None else "—",
                help="Change in mean primary psychosis symptom score over the window. Negative = falling."
            )
            pd_cols[1].metric(
                "Insight indicator trend",
                f"{psy_div['insight_delta']:+.1f}pp" if psy_div["insight_delta"] is not None else "—",
                help="Change in mean insight score over the window. Negative = insight worsening."
            )
            pd_cols[2].metric(
                "Days analysed",
                psy_div["days_analysed"],
            )

            # Chart: primary symptom score vs insight score over the window
            if not daily_filtered.empty:
                recent_w = daily_filtered.sort_values("date").tail(psy_div["days_analysed"]).copy()
                insight_series = recent_w.apply(
                    lambda r: _mean_normalised(r, ["meta_something_wrong", "meta_concerned"], invert=False),
                    axis=1,
                )
                primary_series = recent_w.apply(
                    lambda r: _mean_normalised(r, PSY_PRIMARY_CODES, invert=False),
                    axis=1,
                )
                dates_w = recent_w["date"].astype(str).tolist()

                fig_psy = go.Figure()
                fig_psy.add_trace(go.Scatter(
                    x=dates_w, y=primary_series.tolist(),
                    mode="lines+markers", name="Primary symptoms",
                    line=dict(color=DOMAIN_COLOURS["Psychosis"], width=2),
                    hovertemplate="Primary: %{y:.1f}%<extra></extra>",
                ))
                fig_psy.add_trace(go.Scatter(
                    x=dates_w, y=insight_series.tolist(),
                    mode="lines+markers", name="Insight indicators",
                    line=dict(color="#34C759", width=2, dash="dash"),
                    hovertemplate="Insight: %{y:.1f}%<extra></extra>",
                ))
                fig_psy.update_layout(
                    height=280,
                    margin=dict(l=10, r=10, t=30, b=10),
                    yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
                    xaxis=dict(title=None),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    plot_bgcolor="white", paper_bgcolor="white",
                    title=dict(
                        text="Primary symptoms vs insight indicators",
                        font=dict(size=13, color="#1C1C1E"), x=0,
                    ),
                )
                st.plotly_chart(fig_psy, use_container_width=True)
                st.caption(
                    "**Primary symptoms** (purple): mean of hallucinations, paranoia, "
                    "trust in perceptions, distress.  \n"
                    "**Insight indicators** (green dashed): mean of 'something may be wrong' "
                    "and 'concerned about my state'.  \n"
                    "When both fall together, review is needed. "
                    "When primary falls but insight holds, improvement is more likely genuine."
                )

        st.divider()
        st.markdown("### Cross-domain correlation")
        corr = _cross_domain_correlation(daily_filtered)
        if not corr.empty:
            st.caption("Pearson r across all filtered daily entries. Near 1 = co-move; near 0 = independent.")
            st.dataframe(corr.style.background_gradient(cmap="RdYlGn_r", vmin=-1, vmax=1),
                         use_container_width=True)
        else:
            st.info("Need at least 4 days of data.")

        st.divider()
        st.markdown("### Top contributing items (all-time mean)")
        for domain in DOMAINS:
            with st.expander(domain):
                df_peak = _peak_symptom_items(daily_filtered, domain)
                if df_peak.empty:
                    st.write("No data.")
                else:
                    df_peak = df_peak.rename(columns={"mean_raw": "Mean (1–5)", "question": "Question"})
                    st.dataframe(df_peak[["Question", "Mean (1–5)"]], use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Flag impact on domain scores")
        imp = _flag_impact(daily_filtered)
        if imp.empty:
            st.info("Not enough flag data.")
        else:
            st.caption("Impact = mean domain score on flagged days minus non-flagged days (pp).")
            top = imp[imp["impact"].abs() > 2].assign(
                impact=lambda df: df["impact"].round(1),
                mean_when_flagged=lambda df: df["mean_when_flagged"].round(1),
                mean_when_not_flagged=lambda df: df["mean_when_not_flagged"].round(1),
            )
            st.dataframe(top if not top.empty else pd.DataFrame({"Note": ["No flags with impact > 2pp"]}),
                         use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Submission type summary")
        if "submission_type_derived" in wide_df.columns:
            type_summary = wide_df.copy()
            if filter_start:
                type_summary = type_summary[
                    (type_summary["submitted_date"] >= filter_start) &
                    (type_summary["submitted_date"] <= filter_end)
                ]
            n_snap = int((type_summary["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT).sum())
            n_rev  = int((type_summary["submission_type_derived"] == SUBMISSION_TYPE_REVIEW).sum())
            ts1, ts2, ts3, ts4 = st.columns(4)
            ts1.metric("Snapshots", n_snap)
            ts2.metric("Reviews", n_rev)
            if not daily_filtered.empty:
                days_no_review = int((daily_filtered.get("n_reviews", pd.Series([0]*len(daily_filtered))) == 0).sum()) if "n_reviews" in daily_filtered.columns else 0
                days_no_snap   = int((daily_filtered.get("n_snapshots", pd.Series([0]*len(daily_filtered))) == 0).sum()) if "n_snapshots" in daily_filtered.columns else 0
                ts3.metric("Days with no review", days_no_review)
                ts4.metric("Days with no snapshot", days_no_snap)
                if days_no_review > 0:
                    st.caption(
                        f"⚠ {days_no_review} day(s) in this period have no day review. "
                        f"The daily aggregate for those days is based on snapshots only, "
                        f"which is actually preferable for accuracy."
                    )

        st.divider()
        if "func_sleep_hours" in daily_filtered.columns:
            st.markdown("### Sleep analysis")
            sleep = daily_filtered[["date","func_sleep_hours","func_sleep_quality"]].dropna(subset=["func_sleep_hours"])
            if not sleep.empty:
                s1, s2, s3 = st.columns(3)
                s1.metric("Mean sleep (hrs)", f"{sleep['func_sleep_hours'].mean():.1f}")
                s2.metric("Nights < 6 hrs",   int((sleep["func_sleep_hours"] < 6).sum()))
                s3.metric("Nights > 9 hrs",   int((sleep["func_sleep_hours"] > 9).sum()))
                st.line_chart(sleep.set_index("date")[["func_sleep_hours"]])

# ── JOURNAL ───────────────────────────────────────────────
with tab_journal:
    st.markdown("## Journal")
    st.caption(
        "All written responses to 'How would I describe my experiences?', "
        "colour-coded by the worst band reached that day. "
        "Your personal baseline is shown in the band context where available."
    )

    if notes_filtered.empty:
        st.info("No journal entries in the selected date range.")
    else:
        # Search and filter controls
        j1, j2, j3 = st.columns([3, 2, 2])
        search_term = j1.text_input("Search entries", placeholder="keyword...", key="journal_search")
        band_filter = j2.multiselect(
            "Filter by day's band",
            options=["well", "watch", "caution", "warning", "critical"],
            default=["well", "watch", "caution", "warning", "critical"],
            key="journal_band_filter",
        )
        sort_order = j3.radio("Sort", ["Newest first", "Oldest first"], horizontal=True, key="journal_sort")

        filtered_notes = notes_filtered[notes_filtered["worst_band"].isin(band_filter)].copy()
        if search_term:
            mask = filtered_notes["experience_description"].str.contains(
                search_term, case=False, na=False)
            filtered_notes = filtered_notes[mask]
        if sort_order == "Oldest first":
            filtered_notes = filtered_notes.sort_values("submitted_at")

        st.caption(f"Showing {len(filtered_notes)} of {len(notes_filtered)} entries")

        # Keyword frequency chart
        if not filtered_notes.empty:
            with st.expander("Keyword frequency across shown entries", expanded=False):
                st.plotly_chart(keyword_frequency_chart(filtered_notes), use_container_width=True)

        st.divider()

        # Entry cards
        for row_idx, (_, entry) in enumerate(filtered_notes.iterrows()):
            band       = entry.get("worst_band", "unknown")
            hex_colour = BAND_COLOUR_HEX.get(band, "#8E8E93")
            emoji      = BAND_EMOJI.get(band, "⚪")
            date_str   = str(entry.get("date", ""))
            text       = str(entry.get("experience_description", ""))
            keywords   = entry.get("keywords", [])

            # Submission type badge — look up from wide_df for this date
            day_subs = wide_df[wide_df["submitted_date"] == entry.get("date")] if not wide_df.empty else pd.DataFrame()
            has_review   = not day_subs.empty and (day_subs["submission_type_derived"] == SUBMISSION_TYPE_REVIEW).any()
            has_snapshot = not day_subs.empty and (day_subs["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT).any()
            type_badge = ""
            if has_review and has_snapshot:
                type_badge = "📋 Review + 📸 Snapshot"
            elif has_review:
                type_badge = "📋 Day review"
            elif has_snapshot:
                type_badge = "📸 Snapshot"

            # Domain context line
            domain_context = []
            for d in DOMAINS:
                sc = entry.get(f"{d} Score %")
                if sc is not None and not (isinstance(sc, float) and np.isnan(sc)):
                    b = classify_score(sc, d, bands)
                    domain_context.append(f"{d}: {sc:.0f}% ({b})")
            context_str = " · ".join(domain_context) if domain_context else ""

            # Highlight search term
            display_text = text
            if search_term:
                display_text = re.sub(
                    f"({re.escape(search_term)})",
                    r"**\1**",
                    display_text,
                    flags=re.IGNORECASE,
                )

            # Keyword tags
            kw_tags = " ".join(f"`{kw}`" for kw in keywords[:6]) if keywords else ""

            st.markdown(
                f"""<div style="
                    border-left: 4px solid {hex_colour};
                    padding: 12px 16px;
                    margin-bottom: 12px;
                    border-radius: 4px;
                    background: {hex_colour}18;
                ">
                <strong>{emoji} {date_str}</strong>
                &nbsp;&nbsp;<span style="color:#666;font-size:0.85em">{context_str}</span>
                &nbsp;&nbsp;<span style="font-size:0.8em;color:#999">{type_badge}</span>
                </div>""",
                unsafe_allow_html=True,
            )
            st.markdown(display_text)
            if kw_tags:
                st.markdown(f"*Keywords: {kw_tags}*")

            # ── Comments for this entry ──────────────────────
            submission_id = str(entry.get("submission_id", ""))
            entry_comments = get_comments_for_submission(submission_id, comments_df)

            if entry_comments:
                for c in entry_comments:
                    c_time = str(c.get("commented_at", ""))[:16]
                    c_text = str(c.get("comment_text", ""))
                    st.markdown(
                        f"""<div style="
                            margin-left: 16px;
                            margin-top: 6px;
                            padding: 8px 12px;
                            border-left: 3px solid rgba(100,100,100,0.3);
                            background: rgba(100,100,100,0.05);
                            border-radius: 3px;
                            font-size: 0.9em;
                            color: #444;
                        ">
                        💬 <em>{c_time}</em> — {c_text}
                        </div>""",
                        unsafe_allow_html=True,
                    )

            # Add comment input — key includes row index to guarantee uniqueness
            comment_key = f"comment_input_{submission_id}_{row_idx}"
            new_comment = st.text_input(
                "Add a note to this entry",
                placeholder="Type a note and press Enter…",
                key=comment_key,
                label_visibility="collapsed",
            )
            save_key = f"comment_save_{submission_id}_{row_idx}"
            if st.button("Save note", key=save_key, type="secondary"):
                if new_comment.strip():
                    ok, msg = save_comment(submission_id, new_comment.strip())
                    if ok:
                        st.success("Note saved.")
                        comments_df = load_comments()
                    else:
                        st.error(msg)
                else:
                    st.warning("Note is empty.")

            st.divider()

    # Medication notes section
    st.markdown("## Medication Notes")
    st.caption("Days where medication changes were reported via the form.")
    med_filtered = _apply_date_filter(med_notes_df, "date") if not med_notes_df.empty else med_notes_df
    if med_filtered.empty:
        st.info("No medication notes in the selected date range.")
    else:
        for _, m in med_filtered.iterrows():
            date_str  = str(m.get("date",""))
            note_text = str(m.get("medication_notes",""))
            # Show domain scores for context
            domain_ctx = []
            for d in DOMAINS:
                sc = m.get(f"{d} Score %")
                if sc is not None and not (isinstance(sc, float) and np.isnan(sc)):
                    b = classify_score(sc, d, bands)
                    domain_ctx.append(f"{d}: {sc:.0f}% ({b})")
            ctx_str = " · ".join(domain_ctx) if domain_ctx else ""
            st.markdown(
                f"""<div style="
                    border-left: 4px solid rgba(0,150,100,0.8);
                    padding: 10px 16px;
                    margin-bottom: 10px;
                    border-radius: 4px;
                    background: rgba(0,150,100,0.06);
                ">
                <strong>💊 {date_str}</strong>
                &nbsp;&nbsp;<span style="color:#666;font-size:0.85em">{ctx_str}</span>
                </div>""",
                unsafe_allow_html=True,
            )
            st.markdown(note_text)
            st.divider()

# ── EPISODES ──────────────────────────────────────────────
with tab_episodes:
    st.markdown("## Episode Labelling")
    st.caption(
        "Label historical periods as episodes. These appear as shaded regions on all "
        "domain charts and are used to exclude episode periods from the personal baseline. "
        "Requires a Google Sheet tab named **Episode Log** with columns: "
        "`episode_id, episode_type, start_date, end_date, notes`."
    )

    ws_exists = safe_worksheet(EPISODE_TAB) is not None
    if not ws_exists:
        st.warning(
            f"Worksheet '{EPISODE_TAB}' not found. Create a tab with that exact name "
            "in your Google Sheet, then episode saving will work."
        )

    # Add new episode form
    st.markdown("### Add episode")
    with st.form("add_episode_form"):
        fc1, fc2, fc3 = st.columns([2, 2, 3])
        ep_type  = fc1.selectbox("Episode type", EPISODE_TYPES, key="ep_type")
        ep_start = fc2.date_input("Start date", key="ep_start")
        ep_end   = fc3.date_input("End date",   key="ep_end")
        ep_notes = st.text_input("Notes (optional)", placeholder="e.g. hospitalisation, triggered by sleep deprivation…", key="ep_notes")
        submitted = st.form_submit_button("Add episode", type="primary")
        if submitted:
            if ep_end < ep_start:
                st.error("End date must be on or after start date.")
            else:
                ok, msg = add_episode(ep_type, ep_start, ep_end, ep_notes)
                if ok:
                    st.success(f"Episode added. {msg}")
                    st.rerun()
                else:
                    st.error(msg)

    st.divider()

    # Existing episodes
    st.markdown("### Labelled episodes")
    episodes_df = load_episodes()  # refresh after potential add
    if episodes_df.empty:
        st.info("No episodes labelled yet.")
    else:
        ep_colour_map = {"Depressive":"🔴","Hypomanic":"🟠","Manic":"🟡",
                         "Mixed":"🔵","Psychotic":"🟣","Other":"⚪"}
        for _, ep in episodes_df.sort_values("start_date", ascending=False).iterrows():
            icon = ep_colour_map.get(ep["episode_type"], "⚪")
            duration = (pd.Timestamp(ep["end_date"]) - pd.Timestamp(ep["start_date"])).days + 1
            with st.container():
                ec1, ec2 = st.columns([5, 1])
                with ec1:
                    st.markdown(
                        f"{icon} **{ep['episode_type']}** — "
                        f"{ep['start_date']} to {ep['end_date']} "
                        f"({duration} day{'s' if duration != 1 else ''})"
                        + (f"  \n*{ep['notes']}*" if ep.get("notes") else "")
                    )
                with ec2:
                    if st.button("Delete", key=f"del_{ep['episode_id']}"):
                        ok, msg = delete_episode(ep["episode_id"])
                        if ok:
                            st.rerun()
                        else:
                            st.error(msg)
            st.divider()

    # Episode context chart — domain scores around each episode
    if not episodes_df.empty and not daily_df.empty:
        st.markdown("### Domain scores around each episode")
        st.caption("Shows scores in the 14 days before, during, and after each labelled episode.")
        for _, ep in episodes_df.sort_values("start_date", ascending=False).iterrows():
            start = pd.Timestamp(ep["start_date"])
            end   = pd.Timestamp(ep["end_date"])
            window_start_ep = (start - pd.Timedelta(days=14)).date()
            window_end_ep   = (end   + pd.Timedelta(days=14)).date()
            ep_window = daily_df[
                (daily_df["date"] >= window_start_ep) &
                (daily_df["date"] <= window_end_ep)
            ].copy()
            if ep_window.empty:
                continue
            with st.expander(f"{ep['episode_type']} — {ep['start_date']} to {ep['end_date']}", expanded=False):
                fig_ep = make_overview_chart(ep_window, bands, height=280)
                # Add the episode shading
                single_ep = episodes_df[episodes_df["episode_id"] == ep["episode_id"]]
                fig_ep = add_episode_overlays(fig_ep, single_ep)
                st.plotly_chart(fig_ep, use_container_width=True)

# ── CLINICIAN EXPORT ──────────────────────────────────────
with tab_export:
    st.markdown("## Clinician Export")
    st.caption(
        "A structured summary covering the last 30 days, designed to support "
        "clinical appointments. Copy the text below or save it manually."
    )

    exp_col1, exp_col2 = st.columns([2, 1])
    with exp_col1:
        export_window = st.slider("Days to cover", 7, 90, 30, 7, key="export_window")
    with exp_col2:
        st.markdown("&nbsp;")  # spacer

    report = generate_clinician_report(
        daily=daily_df,
        bands=bands,
        personal_bl=personal_bl,
        episodes=episodes_df,
        notes=notes_df,
        med_notes=med_notes_df,
        weights=weights,
        wide=wide_df,
        comments=comments_df,
        window_days=export_window,
    )

    # Rendered preview
    with st.expander("Preview (rendered)", expanded=True):
        st.markdown(report)

    # Raw copyable text
    st.markdown("### Copy-ready text")
    st.text_area(
        "Select all and copy (Ctrl+A, Ctrl+C)",
        value=report,
        height=400,
        key="export_text",
    )

# ── BASELINES ─────────────────────────────────────────────
with tab_baseline:
    st.markdown("## Baselines")

    st.markdown("### Your personal baseline")
    ep_exclusion_note = ""
    if not episodes_df.empty:
        n_ep_days = sum(
            (pd.Timestamp(ep["end_date"]) - pd.Timestamp(ep["start_date"])).days + 1
            for _, ep in episodes_df.iterrows()
        )
        ep_exclusion_note = f" Episode periods are excluded ({n_ep_days} labelled episode days removed)."
    st.caption(
        f"Derived from days where **all** domains were in the Well band **and at least one snapshot was submitted**. "
        f"Snapshots are used because they reflect point-in-time state more accurately than retrospective reviews. "
        f"Uses the most recent **{pb_window}** such days. "
        f"Requires **{PERSONAL_BASELINE_MIN_DAYS}+** days to be reliable.{ep_exclusion_note}"
    )
    pb_cols = st.columns(len(DOMAINS))
    for i, domain in enumerate(DOMAINS):
        pb = personal_bl.get(domain, {})
        with pb_cols[i]:
            st.markdown(f"**{domain}**")
            if pb.get("reliable"):
                st.metric("Baseline mean", f"{pb['mean']}%")
                well_ceil = bands.get(domain, {}).get("well", 20)
                note = (f"Note: upper SD ({pb['upper']}%) exceeds Well ceiling ({well_ceil}%) — "
                        f"your normal sits toward the upper end of the well band.")
                st.caption(
                    f"±1 SD: {pb['lower']}–{pb['upper']}%  \n"
                    f"Based on {pb['n']} well days" +
                    (f"  \n{note}" if pb["upper"] > well_ceil else "")
                )
            else:
                n = pb.get("n", 0)
                st.info(f"Not yet reliable  \n{n} well days so far  \n{max(0, PERSONAL_BASELINE_MIN_DAYS - n)} more needed")

    st.divider()
    st.markdown("### Score history with overlays")
    st.caption("Green/yellow/orange/red/purple bands = Well/Watch/Caution/Warning/Critical. "
               "Blue line = personal baseline mean. Blue shading = ±1 SD. Orange triangle = movement alert.")
    if not daily_filtered.empty:
        for domain in selected_domains:
            st.plotly_chart(
                make_band_chart(daily_filtered, domain, bands, personal=personal_bl,
                                movement_threshold=mv_threshold, show_rolling=show_rolling,
                                episodes=episodes_df, med_notes=med_notes_df,
                                height=300),
                use_container_width=True,
            )
    else:
        st.info("No data in selected range.")

    st.divider()
    st.markdown("### Current band thresholds")
    ref_rows = []
    for domain in DOMAINS:
        b = bands.get(domain, {})
        ref_rows.append({
            "Domain": domain,
            "Well": f"0–{b.get('well','?')}%",
            "Watch": f"{b.get('well','?')}–{b.get('watch','?')}%",
            "Caution": f"{b.get('watch','?')}–{b.get('caution','?')}%",
            "Warning": f"{b.get('caution','?')}–{b.get('warning','?')}%",
            "Critical": f"{b.get('warning','?')}–100%",
        })
    st.dataframe(pd.DataFrame(ref_rows), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Edit thresholds")
    bl_config    = render_baseline_editor(bl_config)
    bands        = bl_config["bands"]
    mv_threshold = bl_config["movement_threshold"]
    pb_window    = bl_config["personal_baseline_window"]

# ── QUESTIONS ─────────────────────────────────────────────
with tab_questions:
    st.markdown("## Form Questions")
    st.caption(
        "All questions from the monitoring form, organised by group. "
        "Click **📈 Chart** on any question to see how your answers have changed over time."
    )

    # ── helper: build a per-question answer chart ──────────
    def _question_chart(code: str, meta: dict, daily: pd.DataFrame,
                        wide: pd.DataFrame, episodes: pd.DataFrame) -> go.Figure:
        """
        Return a Plotly figure showing raw answer values over time for one question.
        - scale_1_5 / numeric  → line chart on daily (first-of-day) values
        - boolean_yes_no       → stacked bar: Yes / No count per day
        - text                 → not charted (handled separately)
        """
        rtype = meta.get("rtype", "")

        if rtype == "text":
            return go.Figure()

        if rtype == "boolean_yes_no":
            if code not in wide.columns:
                return go.Figure()
            bool_data = wide[["submitted_date", code]].copy()
            bool_data[code] = bool_data[code].astype(bool)
            counts = (
                bool_data.groupby(["submitted_date", code])
                .size().reset_index(name="count")
            )
            yes_c = counts[counts[code] == True].set_index("submitted_date")["count"]
            no_c  = counts[counts[code] == False].set_index("submitted_date")["count"]
            all_dates = sorted(bool_data["submitted_date"].unique())
            yes_vals = [int(yes_c.get(d, 0)) for d in all_dates]
            no_vals  = [int(no_c.get(d, 0))  for d in all_dates]
            date_strs = [str(d) for d in all_dates]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=date_strs, y=yes_vals, name="Yes",
                marker_color="rgba(255,59,48,0.7)",
                hovertemplate="%{x}<br>Yes: %{y}<extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=date_strs, y=no_vals, name="No",
                marker_color="rgba(142,142,147,0.4)",
                hovertemplate="%{x}<br>No: %{y}<extra></extra>",
            ))
            fig.update_layout(
                barmode="stack", height=260,
                margin=dict(l=10, r=10, t=10, b=10),
                yaxis=dict(title="Submissions", dtick=1),
                xaxis=dict(title=None),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                plot_bgcolor="white", paper_bgcolor="white",
            )
            fig = add_episode_overlays(fig, episodes)
            return fig

        # scale_1_5 or numeric — use daily (first of day) values
        if code not in daily.columns:
            return go.Figure()

        plot_daily = daily[["date", code]].dropna(subset=[code]).copy()
        if plot_daily.empty:
            return go.Figure()

        date_strs = plot_daily["date"].astype(str).tolist()
        values    = plot_daily[code].tolist()

        # Rolling average
        rolling = plot_daily[code].rolling(7, min_periods=1).mean().tolist()

        # y-axis range
        if rtype == "scale_1_5":
            y_range = [0.5, 5.5]
            y_title = "Rating (1–5)"
            tick_vals = [1, 2, 3, 4, 5]
            tick_text = ["1\nNot at all", "2", "3\nModerate", "4", "5\nExtreme"]
        else:
            y_range = None
            y_title = "Value"
            tick_vals = None
            tick_text = None

        fig = go.Figure()

        # Episode shading behind everything
        fig = add_episode_overlays(fig, episodes)

        # 7-day rolling average
        fig.add_trace(go.Scatter(
            x=date_strs, y=rolling, mode="lines",
            name="7d avg",
            line=dict(color="rgba(100,100,100,0.4)", width=1.5, dash="dash"),
            hovertemplate="7d avg: %{y:.2f}<extra></extra>",
        ))

        # Raw values
        domain_list = meta.get("domains", [])
        colour = DOMAIN_COLOURS.get(domain_list[0], "#1C7EF2") if domain_list else "#1C7EF2"
        fig.add_trace(go.Scatter(
            x=date_strs, y=values, mode="lines+markers",
            name="Daily value",
            line=dict(color=colour, width=2),
            marker=dict(size=5, color=colour),
            hovertemplate="%{x}<br>Value: %{y}<extra></extra>",
        ))

        yaxis_cfg = dict(title=y_title)
        if y_range:
            yaxis_cfg["range"] = y_range
        if tick_vals:
            yaxis_cfg["tickvals"] = tick_vals
            yaxis_cfg["ticktext"] = tick_text

        fig.update_layout(
            height=260,
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis=yaxis_cfg,
            xaxis=dict(title=None),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="white", paper_bgcolor="white",
        )
        return fig

    # ── group display config ────────────────────────────────
    GROUP_LABELS = {
        "depression":   "🔵 Depression",
        "mania":        "🟠 Mania",
        "mixed":        "🔀 Mixed",
        "psychosis":    "🟣 Psychosis",
        "functioning":  "⚙️ Functioning",
        "meta":         "🧠 Meta / Self-observation",
        "flags":        "🚩 Flags",
        "observations": "👁 Observations",
        "notes":        "📝 Notes",
    }
    GROUP_ORDER = [
        "depression", "mania", "mixed", "psychosis",
        "functioning", "meta", "flags", "observations", "notes",
    ]

    ROLE_BADGES = {
        "force_multiplier":           "⚡ Force multiplier",
        "insight_inverse_psychosis":  "🔄 Insight-inverse (Psychosis)",
        "contributor":                "➕ Domain contributor",
    }
    RTYPE_LABELS = {
        "scale_1_5":      "Scale 1–5",
        "boolean_yes_no": "Yes / No",
        "numeric":        "Number",
        "text":           "Free text",
    }

    by_code = _catalog_by_code()
    cat     = catalog_df()

    # Track which question is charted via session state
    if "q_chart_code" not in st.session_state:
        st.session_state["q_chart_code"] = None

    # Search box
    q_search = st.text_input(
        "Search questions", placeholder="e.g. sleep, mood, agitation…",
        key="q_search"
    )

    st.divider()

    for group in GROUP_ORDER:
        group_qs = cat[cat["group"] == group].sort_values("order")
        if group_qs.empty:
            continue
        if q_search:
            group_qs = group_qs[
                group_qs["text"].str.contains(q_search, case=False, na=False) |
                group_qs["code"].str.contains(q_search, case=False, na=False)
            ]
            if group_qs.empty:
                continue

        label = GROUP_LABELS.get(group, group.title())
        with st.expander(f"{label}  ({len(group_qs)} questions)", expanded=not bool(q_search)):
            for _, q_row in group_qs.iterrows():
                code  = q_row["code"]
                text  = q_row["text"]
                rtype = q_row.get("rtype","")
                role  = q_row.get("meta_role", None)
                domains = q_row.get("domains", [])
                if isinstance(domains, str):
                    # catalog_df serialises lists as strings sometimes
                    import ast
                    try:
                        domains = ast.literal_eval(domains)
                    except Exception:
                        domains = []

                # ── Question header row ──────────────────────
                hc1, hc2 = st.columns([5, 1])
                with hc1:
                    st.markdown(f"**{text}**")
                    # Metadata badges in one line
                    badges = []
                    badges.append(f"`{RTYPE_LABELS.get(rtype, rtype)}`")
                    if domains:
                        for d in domains:
                            colour_hex = BAND_COLOUR_HEX.get(
                                classify_score(50, d, bands), "#888"
                            )
                            badges.append(f"`{d}`")
                    if role:
                        badges.append(f"`{ROLE_BADGES.get(role, role)}`")
                    # Weight info
                    base_w = DEFAULT_WEIGHTS.get(code)
                    if base_w is not None:
                        badges.append(f"weight `{base_w}`")
                    st.caption("  ".join(badges))

                with hc2:
                    btn_label = "📉 Hide" if st.session_state["q_chart_code"] == code else "📈 Chart"
                    if rtype == "text":
                        st.caption("*Free text*")
                    else:
                        if st.button(btn_label, key=f"qbtn_{code}", use_container_width=True):
                            if st.session_state["q_chart_code"] == code:
                                st.session_state["q_chart_code"] = None
                            else:
                                st.session_state["q_chart_code"] = code

                # ── Chart (shown inline when this question is active) ──
                if st.session_state["q_chart_code"] == code:
                    meta_entry = by_code.get(code, {})
                    fig = _question_chart(code, meta_entry, daily_filtered, wide_df, episodes_df)
                    if fig.data or fig.layout.shapes:
                        # Summary stats
                        if code in daily_filtered.columns and rtype != "text":
                            vals = pd.to_numeric(daily_filtered[code], errors="coerce").dropna()
                            if not vals.empty and rtype == "boolean_yes_no":
                                pct_yes = int(vals.astype(bool).mean() * 100)
                                sc1, sc2 = st.columns(2)
                                sc1.metric("Days answered Yes", f"{vals.astype(bool).sum()} / {len(vals)}")
                                sc2.metric("% Yes", f"{pct_yes}%")
                            elif not vals.empty:
                                sc1, sc2, sc3, sc4 = st.columns(4)
                                sc1.metric("Mean", f"{vals.mean():.2f}")
                                sc2.metric("Peak", f"{vals.max():.0f}")
                                sc3.metric("Days recorded", len(vals))
                                # % of days answered at 4 or 5
                                if rtype == "scale_1_5":
                                    pct_high = int((vals >= 4).mean() * 100)
                                    sc4.metric("% days rated 4–5", f"{pct_high}%")
                        st.plotly_chart(fig, use_container_width=True, key=f"qfig_{code}")

                        # For boolean: show dates when it was Yes
                        if rtype == "boolean_yes_no" and code in wide_df.columns:
                            yes_dates = wide_df[wide_df[code] == True]["submitted_date"].unique()
                            if len(yes_dates):
                                with st.expander(f"All dates answered Yes ({len(yes_dates)})", expanded=False):
                                    st.write(", ".join(str(d) for d in sorted(yes_dates)))
                    else:
                        if rtype == "text":
                            st.info("Free text — see the Journal tab for entries.")
                        else:
                            st.info("No data recorded for this question yet.")

                st.divider()

# ── DAILY MODEL ───────────────────────────────────────────
with tab_daily:
    st.markdown("### Daily model — first submission per day")
    st.dataframe(daily_filtered, use_container_width=True)
    if not daily_filtered.empty:
        delta_cols = [c for c in daily_filtered.columns if c.endswith(" Delta") and "Score" in c]
        if delta_cols:
            st.markdown("### Day-on-day deltas")
            st.dataframe(daily_filtered[["date"] + delta_cols], use_container_width=True)

# ── DATA LAYER ────────────────────────────────────────────
with tab_data:
    st.markdown("### Question catalog")
    display_cols = ["code","text","group","rtype","polarity","domains","score_in_snapshot","score_in_daily","order"]
    cat_display = catalog_df()
    # Add meta_role column if present
    if "meta_role" in cat_display.columns:
        display_cols = ["code","text","group","meta_role","rtype","polarity","domains","order"]
    st.dataframe(cat_display[[c for c in display_cols if c in cat_display.columns]], use_container_width=True)

    st.divider()
    st.markdown("### Meta question system")
    st.caption(
        "Meta questions operate at two levels: **force multipliers** amplify all domain "
        "scores after calculation; **contributors** feed directly into domain scores; "
        "**insight-inverse** items contribute normally to Depression/Mania/Mixed but are "
        "**inverted in Psychosis** (low concern/insight = higher psychosis risk)."
    )

    meta_ref = []
    for q in QUESTION_CATALOG:
        role = q.get("meta_role")
        if not role:
            continue
        if role == "force_multiplier":
            description = f"Force multiplier — amplifies all domain scores ×1.0–×{META_MULTIPLIER_MAX}. Not a domain contributor."
        elif role == "insight_inverse_psychosis":
            description = "Insight item — contributes normally to Dep/Mania/Mixed. INVERTED in Psychosis (low insight = higher risk)."
        elif role == "contributor":
            description = f"Direct contributor to: {', '.join(q.get('domains', []))}"
        else:
            description = role
        meta_ref.append({
            "Code": q["code"],
            "Question (short)": q["text"][:60] + ("…" if len(q["text"]) > 60 else ""),
            "Role": role,
            "Domains": ", ".join(q.get("domains", [])) or "—",
            "Description": description,
        })
    st.dataframe(pd.DataFrame(meta_ref), use_container_width=True, hide_index=True)

    st.caption(
        f"**Multiplier formula:** composite of {', '.join(FORCE_MULTIPLIER_CODES)} "
        f"→ mean normalised score (0–100) → mapped to ×1.0–×{META_MULTIPLIER_MAX}. "
        f"A score of 50/100 on all three items → multiplier of "
        f"×{1.0 + 0.5 * (META_MULTIPLIER_MAX - 1.0):.2f}. "
        f"All domain scores capped at 100 after multiplication."
    )

    st.divider()
    st.markdown("### Sleep weight multipliers by domain")
    mlt_rows = []
    for domain in DOMAINS:
        mlt = DOMAIN_WEIGHT_MULTIPLIERS.get(domain, {})
        mlt_rows.append({
            "Domain": domain,
            "func_sleep_hours multiplier":   mlt.get("func_sleep_hours", 1.0),
            "func_sleep_quality multiplier": mlt.get("func_sleep_quality", 1.0),
            "Effective sleep_hours weight":  round(_effective_weight("func_sleep_hours", domain, weights), 3),
            "Effective sleep_quality weight":round(_effective_weight("func_sleep_quality", domain, weights), 3),
        })
    st.dataframe(pd.DataFrame(mlt_rows), use_container_width=True, hide_index=True)

    with st.expander("Wide submission table"):
        st.dataframe(wide_df, use_container_width=True)
    with st.expander("Raw worksheet"):
        st.dataframe(raw_df, use_container_width=True)
        st.caption(f"Columns: {list(raw_df.columns)}")

# ── SETTINGS ─────────────────────────────────────────────
with tab_settings:
    weights = render_weights_editor(weights)
