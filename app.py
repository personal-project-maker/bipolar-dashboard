"""
Bipolar Dashboard — revised full script.

Major changes in this version:
  • Safer clinical wording: "recent symptom momentum" instead of diagnostic/risk claims
  • Reliability labels and valid-N counts for analytical outputs
  • Continuous-date daily table for deltas, rolling averages, streaks and sleep lead/lag
  • Dedicated Today panel
  • Top-level self-harm safety notice
  • Data Quality panel
  • Sleep lead/lag analysis with sample size and non-causal wording
  • More conservative psychosis insight-divergence logic
  • Clinician export disclaimer
  • Simplified tab structure: Today, Trends, Sleep, Episodes, Journal, Export, Data Quality, Settings

Important:
  This dashboard is a personal self-monitoring aid. It is not a diagnostic tool and does not replace
  clinical judgement, emergency care, or a crisis plan.
"""

import datetime as dt
import hashlib
import re
from collections import Counter
from typing import Any

import gspread
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


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
# GOOGLE SHEETS CONFIG
# ──────────────────────────────────────────────────────────
SHEET_NAME = "Bipolar Dashboard"
NEW_FORM_TAB = "Updated Bipolar Form"
SETTINGS_TAB = "Scoring Settings"
BASELINE_TAB = "Baseline Settings"
EPISODE_TAB = "Episode Log"
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


try:
    wb = _workbook()
    st.caption(f"Connected to **{wb.title}** | worksheet: *{NEW_FORM_TAB}*")
except Exception as exc:
    st.error("Google Sheets connection failed.")
    st.exception(exc)
    st.stop()


# ──────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────
DOMAINS = ["Depression", "Mania", "Psychosis", "Mixed"]

DEFAULT_BASELINE_BANDS: dict[str, dict[str, float]] = {
    "Depression": {"well": 20.0, "watch": 40.0, "caution": 60.0, "warning": 75.0},
    "Mania": {"well": 20.0, "watch": 40.0, "caution": 60.0, "warning": 75.0},
    "Mixed": {"well": 18.0, "watch": 35.0, "caution": 55.0, "warning": 70.0},
    "Psychosis": {"well": 12.0, "watch": 28.0, "caution": 50.0, "warning": 68.0},
}

DEFAULT_MOVEMENT_THRESHOLD = 10.0
PERSONAL_BASELINE_MIN_DAYS = 14
SELF_HARM_FLAG_THRESHOLD = 2

REVIEW_WEIGHT = 0.5
SNAPSHOT_WEIGHT = 1.0
SUBMISSION_TYPE_REVIEW = "review"
SUBMISSION_TYPE_SNAPSHOT = "snapshot"

META_MULTIPLIER_MAX = 1.35

BAND_EMOJI = {
    "well": "🟢",
    "watch": "🟡",
    "caution": "🟠",
    "warning": "🔴",
    "critical": "🟣",
    "unknown": "⚪",
}

BAND_COLOUR_HEX = {
    "well": "#34C759",
    "watch": "#FFCC00",
    "caution": "#FF9500",
    "warning": "#FF3B30",
    "critical": "#AF52DE",
    "unknown": "#8E8E93",
}

BAND_COLOURS = {
    "well": "rgba(52,199,89,0.12)",
    "watch": "rgba(255,204,0,0.12)",
    "caution": "rgba(255,149,0,0.12)",
    "warning": "rgba(255,59,48,0.12)",
    "critical": "rgba(175,82,222,0.12)",
}

BAND_LINE_COLOURS = {
    "well": "rgba(52,199,89,0.5)",
    "watch": "rgba(255,204,0,0.5)",
    "caution": "rgba(255,149,0,0.5)",
    "warning": "rgba(255,59,48,0.5)",
}

DOMAIN_COLOURS = {
    "Depression": "#FF3B30",
    "Mania": "#FF9500",
    "Psychosis": "#AF52DE",
    "Mixed": "#1C7EF2",
}


# ──────────────────────────────────────────────────────────
# QUESTION CATALOG
# ──────────────────────────────────────────────────────────
QUESTION_CATALOG: list[dict[str, Any]] = [
    dict(code="dep_low_mood", text="Have I felt a low mood?", group="depression", rtype="scale_1_5", polarity="higher_worse", domains=["Depression"], order=10),
    dict(code="dep_slowed_low_energy", text="Have I felt slowed down or low on energy?", group="depression", rtype="scale_1_5", polarity="higher_worse", domains=["Depression"], order=20),
    dict(code="dep_low_motivation", text="Have I felt low on motivation or had difficulty initiating tasks?", group="depression", rtype="scale_1_5", polarity="higher_worse", domains=["Depression"], order=30),
    dict(code="dep_anhedonia", text="Have I felt a lack of interest or pleasure in activities?", group="depression", rtype="scale_1_5", polarity="higher_worse", domains=["Depression"], order=40),
    dict(code="dep_withdrawal", text="Have I been socially or emotionally withdrawn?", group="depression", rtype="scale_1_5", polarity="higher_worse", domains=["Depression"], order=50),
    dict(code="dep_self_harm_ideation", text="Have I had ideation around self-harming or suicidal behaviours?", group="depression", rtype="scale_1_5", polarity="higher_worse", domains=["Depression"], order=60),

    dict(code="man_elevated_mood", text="Have I felt an elevated mood?", group="mania", rtype="scale_1_5", polarity="higher_worse", domains=["Mania"], order=70),
    dict(code="man_sped_up_high_energy", text="Have I felt sped up or high on energy?", group="mania", rtype="scale_1_5", polarity="higher_worse", domains=["Mania", "Mixed"], order=80),
    dict(code="man_racing_thoughts", text="Have I had racing thoughts or speech?", group="mania", rtype="scale_1_5", polarity="higher_worse", domains=["Mania"], order=90),
    dict(code="man_goal_drive", text="Have I had an increased drive towards goal-directed activity?", group="mania", rtype="scale_1_5", polarity="higher_worse", domains=["Mania"], order=100),
    dict(code="man_impulsivity", text="Have I felt impulsivity or an urge to take risky actions?", group="mania", rtype="scale_1_5", polarity="higher_worse", domains=["Mania"], order=110),
    dict(code="man_agitation", text="Have I felt agitated or restless?", group="mania", rtype="scale_1_5", polarity="higher_worse", domains=["Mania", "Mixed"], order=120),
    dict(code="man_irritability", text="Have I been more irritable and reactive than normal?", group="mania", rtype="scale_1_5", polarity="higher_worse", domains=["Mania", "Mixed"], order=130),
    dict(code="man_cant_settle", text="Have I been unable to settle or switch off?", group="mania", rtype="scale_1_5", polarity="higher_worse", domains=["Mania"], order=140),

    dict(code="mix_high_energy_low_mood", text="Have I had a high energy combined with low mood?", group="mixed", rtype="scale_1_5", polarity="higher_worse", domains=["Mixed"], order=150),
    dict(code="mix_rapid_emotional_shifts", text="Have I experienced rapid emotional shifts?", group="mixed", rtype="scale_1_5", polarity="higher_worse", domains=["Mixed"], order=160),

    dict(code="psy_heard_saw", text="Have I heard or seen things others didn't?", group="psychosis", rtype="scale_1_5", polarity="higher_worse", domains=["Psychosis"], order=170),
    dict(code="psy_suspicious", text="Have I felt watched, followed, targeted or suspicious?", group="psychosis", rtype="scale_1_5", polarity="higher_worse", domains=["Psychosis"], order=180),
    dict(code="psy_trust_perceptions", text="Have I had trouble trusting my perceptions and thoughts?", group="psychosis", rtype="scale_1_5", polarity="higher_worse", domains=["Psychosis"], order=190),
    dict(code="psy_confidence_reality", text="How confident have I been in the reality of these experiences?", group="psychosis", rtype="scale_1_5", polarity="higher_worse", domains=["Psychosis"], order=200),
    dict(code="psy_distress", text="How distressed have I been by these beliefs and experiences?", group="psychosis", rtype="scale_1_5", polarity="higher_worse", domains=["Psychosis"], order=210),

    dict(code="func_work", text="How effectively have I been functioning at work?", group="functioning", rtype="scale_1_5", polarity="higher_better", domains=["Depression", "Mania"], order=220),
    dict(code="func_daily", text="How well have I been functioning in my daily life?", group="functioning", rtype="scale_1_5", polarity="higher_better", domains=["Depression", "Mania"], order=230),
    dict(code="func_sleep_hours", text="How many hours did I sleep last night?", group="functioning", rtype="numeric", polarity="custom_sleep", domains=["Depression", "Mania", "Mixed"], order=450, score_in_snapshot=False),
    dict(code="func_sleep_quality", text="How poor was my sleep quality last night", group="functioning", rtype="scale_1_5", polarity="higher_worse", domains=["Depression", "Mania", "Mixed"], order=460, score_in_snapshot=False),

    dict(code="meta_unlike_self", text="Do I feel unlike my usual self?", group="meta", rtype="scale_1_5", polarity="higher_worse", domains=[], order=240, meta_role="force_multiplier"),
    dict(code="meta_intensifying", text="Is my state intensifying (in any direction)?", group="meta", rtype="scale_1_5", polarity="higher_worse", domains=[], order=300, meta_role="force_multiplier"),
    dict(code="meta_towards_episode", text="Do I feel like I'm moving towards an episode?", group="meta", rtype="scale_1_5", polarity="higher_worse", domains=[], order=310, meta_role="force_multiplier"),

    dict(code="meta_something_wrong", text="Do I think something may be wrong or changing?", group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Depression", "Mania", "Mixed", "Psychosis"], order=250, meta_role="insight_inverse_psychosis"),
    dict(code="meta_concerned", text="Am I concerned about my current state?", group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Depression", "Mania", "Mixed", "Psychosis"], order=260, meta_role="insight_inverse_psychosis"),

    dict(code="meta_disorganised_thoughts", text="Do my thoughts feel disorganised or hard to follow?", group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Psychosis", "Mixed"], order=270, meta_role="contributor"),
    dict(code="meta_attention_unstable", text="Is my attention unstable or jumping?", group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Mania", "Mixed"], order=280, meta_role="contributor"),
    dict(code="meta_driven_without_thinking", text="Do I feel driven to act without thinking?", group="meta", rtype="scale_1_5", polarity="higher_worse", domains=["Mania", "Mixed"], order=290, meta_role="contributor"),

    dict(code="flag_not_myself", text="I've been feeling \"not like myself\"", group="flags", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression", "Mania", "Psychosis"], order=320),
    dict(code="flag_mood_shift", text="I noticed a sudden mood shift", group="flags", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression", "Mania", "Psychosis", "Mixed"], order=330),
    dict(code="flag_missed_medication", text="I missed medication", group="flags", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression", "Mania", "Psychosis"], order=340),
    dict(code="flag_sleep_medication", text="I took sleeping or anti-anxiety medication", group="flags", rtype="boolean_yes_no", polarity="higher_worse", domains=[], order=350),
    dict(code="flag_routine_disruption", text="There were significant disruptions to my routine", group="flags", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression", "Mania", "Psychosis", "Mixed"], order=360),
    dict(code="flag_physiological_stress", text="I had a major physiological stress", group="flags", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression", "Mania", "Psychosis"], order=370),
    dict(code="flag_psychological_stress", text="I had a major psychological stress", group="flags", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression", "Mania", "Psychosis"], order=380),

    dict(code="obs_up_now", text="Observations [I feel like I'm experiencing an up]", group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Mania"], order=390),
    dict(code="obs_down_now", text="Observations [I feel like I'm experiencing a down]", group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression"], order=400),
    dict(code="obs_mixed_now", text="Observations [I feel like I'm experiencing a mixed]", group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Psychosis", "Mixed"], order=410),
    dict(code="obs_up_coming", text="Observations [I feel like I'm going to experience an up]", group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Mania"], order=420),
    dict(code="obs_down_coming", text="Observations [I feel like I'm going to experience a down]", group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression"], order=430),
    dict(code="obs_mixed_coming", text="Observations [I feel like I'm going to experience a mixed]", group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Psychosis", "Mixed"], order=440),

    dict(code="experience_description", text="How would I describe my experiences?", group="notes", rtype="text", polarity="not_applicable", domains=[], order=470),
    dict(code="medication_notes", text="Have there been any medication changes? If so, what?", group="notes", rtype="text", polarity="not_applicable", domains=[], order=480),
    dict(code="submission_type", text="What kind of entry is this?", group="notes", rtype="text", polarity="not_applicable", domains=[], order=5),
]

for q in QUESTION_CATALOG:
    q.setdefault("score_in_snapshot", True)
    q.setdefault("score_in_daily", True)


DOMAIN_WEIGHT_MULTIPLIERS: dict[str, dict[str, float]] = {
    "Depression": {"func_sleep_hours": 0.35, "func_sleep_quality": 0.45},
    "Mania": {"func_sleep_hours": 1.0, "func_sleep_quality": 1.0},
    "Mixed": {"func_sleep_hours": 1.0, "func_sleep_quality": 1.0},
    "Psychosis": {},
}

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
    "meta_something_wrong": 1.25, "meta_concerned": 1.0,
    "meta_disorganised_thoughts": 1.75,
    "meta_attention_unstable": 1.25,
    "meta_driven_without_thinking": 1.5,
}

FORCE_MULTIPLIER_CODES = [q["code"] for q in QUESTION_CATALOG if q.get("meta_role") == "force_multiplier"]
INSIGHT_INVERSE_CODES = [q["code"] for q in QUESTION_CATALOG if q.get("meta_role") == "insight_inverse_psychosis"]


# ──────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────
@st.cache_data
def catalog_df() -> pd.DataFrame:
    return pd.DataFrame(QUESTION_CATALOG).sort_values("order").reset_index(drop=True)


def _catalog_by_text() -> dict[str, dict]:
    return {q["text"]: q for q in QUESTION_CATALOG}


def _catalog_by_code() -> dict[str, dict]:
    return {q["code"]: q for q in QUESTION_CATALOG}


def _effective_weight(code: str, domain: str, base_weights: dict[str, float]) -> float:
    return base_weights.get(code, 0.0) * DOMAIN_WEIGHT_MULTIPLIERS.get(domain, {}).get(code, 1.0)


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "y", "checked"}


def reliability_label(n: int) -> str:
    if n < 7:
        return "very low"
    if n < 14:
        return "low"
    if n < 30:
        return "moderate"
    return "higher"


def classify_score(score: float, domain: str, bands: dict) -> str:
    if score is None or pd.isna(score):
        return "unknown"
    b = bands.get(domain, DEFAULT_BASELINE_BANDS.get(domain, {}))
    if score <= b.get("well", 20):
        return "well"
    if score <= b.get("watch", 40):
        return "watch"
    if score <= b.get("caution", 60):
        return "caution"
    if score <= b.get("warning", 75):
        return "warning"
    return "critical"


def _hex_to_rgba(hex_colour: str, alpha: float = 0.15) -> str:
    h = hex_colour.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ──────────────────────────────────────────────────────────
# CONFIG LOAD / SAVE
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
    rows += [
        ["", "", "", ""],
        ["", "", config["movement_threshold"], "movement_threshold"],
        ["", "", config["personal_baseline_window"], "personal_baseline_window"],
    ]
    ws.clear()
    ws.update("A1", rows)
    load_baseline_config.clear()
    return True, "Baseline config saved."


# ──────────────────────────────────────────────────────────
# COMMENTS
# ──────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_comments() -> pd.DataFrame:
    ws = safe_worksheet(COMMENTS_TAB)
    cols = ["submission_id", "commented_at", "comment_text"]
    if ws is None:
        return pd.DataFrame(columns=cols)
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(values[1:], columns=values[0])
    if "comment_text" in df.columns:
        df = df[df["comment_text"].astype(str).str.strip() != ""].copy()
    return df.reset_index(drop=True)


def save_comment(submission_id: str, comment_text: str) -> tuple[bool, str]:
    ws = safe_worksheet(COMMENTS_TAB)
    if ws is None:
        return False, f"Worksheet '{COMMENTS_TAB}' not found."
    existing = ws.get_all_values()
    if not existing:
        ws.append_row(["submission_id", "commented_at", "comment_text"])
    ws.append_row([submission_id, dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), comment_text.strip()])
    load_comments.clear()
    return True, "Comment saved."


def get_comments_for_submission(submission_id: str, comments_df: pd.DataFrame) -> list[dict]:
    if not submission_id or comments_df.empty or "submission_id" not in comments_df.columns:
        return []
    rows = comments_df[comments_df["submission_id"].astype(str).str.strip() == submission_id.strip()]
    return rows.sort_values("commented_at").to_dict("records") if not rows.empty else []


# ──────────────────────────────────────────────────────────
# RAW DATA PROCESSING
# ──────────────────────────────────────────────────────────
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


def _classify_submission_type(row: pd.Series) -> str:
    st_val = str(row.get("submission_type", "") or "").strip().lower()
    if "review" in st_val:
        return SUBMISSION_TYPE_REVIEW
    if "snapshot" in st_val:
        return SUBMISSION_TYPE_SNAPSHOT
    sleep = row.get("func_sleep_hours")
    if sleep is not None and pd.notna(pd.to_numeric(sleep, errors="coerce")):
        return SUBMISSION_TYPE_REVIEW
    return SUBMISSION_TYPE_SNAPSHOT


def clean_and_widen(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    by_text = _catalog_by_text()
    w = df.copy()
    base_cols = ["submission_id", "submitted_at", "submitted_date", "submission_order_in_day", "is_first_of_day"]
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
        bins = [(0, 3, 100), (3, 4, 85), (4, 5, 70), (5, 6, 50), (6, 9, 20), (9, 10, 40), (10, np.inf, 60)]
        out = pd.Series(np.nan, index=s.index)
        for lo, hi, score in bins:
            out = out.mask((s >= lo) & (s < hi), score)
        return out.fillna(0.0)

    if rtype == "scale_1_5":
        base = ((s - 1).clip(0, 4) / 4.0) * 100.0
        return (100.0 - base if polarity == "higher_better" else base).fillna(0.0)

    return s.fillna(0.0)


def _normalise_meta_item(raw_value: Any) -> float:
    v = pd.to_numeric(raw_value, errors="coerce")
    if pd.isna(v):
        return 0.0
    return float(min(max((v - 1.0) / 4.0 * 100.0, 0.0), 100.0))


def compute_meta_multiplier(row: pd.Series) -> float:
    scores = [_normalise_meta_item(row[code]) for code in FORCE_MULTIPLIER_CODES if code in row.index]
    if not scores:
        return 1.0
    avg = float(np.mean(scores))
    return 1.0 + (avg / 100.0) * (META_MULTIPLIER_MAX - 1.0)


def _domain_score(frame: pd.DataFrame, domain: str, weights: dict[str, float], snapshot: bool = False) -> pd.Series:
    codes = [
        q["code"]
        for q in QUESTION_CATALOG
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
        meta = _catalog_by_code()[c]
        ew = _effective_weight(c, domain, weights)
        col_vals = frame[c].fillna(0.0)
        if domain == "Psychosis" and c in INSIGHT_INVERSE_CODES:
            col_vals = 100.0 - col_vals
        num += col_vals * ew
        den += ew
    return num / den if den else pd.Series(0.0, index=frame.index)


def build_scored_table(wide: pd.DataFrame, weights: dict[str, float], daily_only: bool = False) -> pd.DataFrame:
    if wide.empty:
        return pd.DataFrame()

    src = wide[wide["is_first_of_day"]].copy() if daily_only else wide.copy()
    by_code = _catalog_by_code()

    for code, meta in by_code.items():
        if code in src.columns and meta["rtype"] != "text":
            src[f"_n_{code}"] = _normalise(src[code], meta)

    norm_frame = src.copy()
    for code in by_code:
        if f"_n_{code}" in norm_frame.columns:
            norm_frame[code] = norm_frame[f"_n_{code}"]

    for domain in DOMAINS:
        src[f"{domain} Score % (raw)"] = _domain_score(norm_frame, domain, weights, snapshot=not daily_only)

    src["meta_multiplier"] = src.apply(compute_meta_multiplier, axis=1)

    for domain in DOMAINS:
        src[f"{domain} Score %"] = (src[f"{domain} Score % (raw)"] * src["meta_multiplier"]).clip(upper=100.0)

    src["Overall Score %"] = src[[f"{d} Score %" for d in DOMAINS]].mean(axis=1)
    src = src.drop(columns=[c for c in src.columns if c.startswith("_n_")])

    if daily_only:
        src = src.rename(columns={"submitted_date": "date"})
        for col in [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]:
            src[f"{col} Delta"] = src[col].diff()
            src[f"{col} 7d Avg"] = src[col].rolling(7, min_periods=1).mean()

    return src.reset_index(drop=True)


def build_daily_weighted_submission_summary(wide: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """
    Produces one row per recorded day.

    Important modelling note:
    Domain scores are weighted averages of per-submission domain scores.
    They are not recomputed from a single synthetic daily answer set.
    """
    if wide.empty:
        return pd.DataFrame()

    by_code = _catalog_by_code()
    scored_all = build_scored_table(wide, weights, daily_only=False)

    type_map = wide.set_index("submission_id")["submission_type_derived"].to_dict()
    scored_all["submission_type_derived"] = scored_all["submission_id"].map(type_map).fillna(SUBMISSION_TYPE_SNAPSHOT)

    date_map = wide.set_index("submission_id")["submitted_date"].to_dict()
    scored_all["submitted_date"] = scored_all["submission_id"].map(date_map)

    scored_all["_sw"] = scored_all["submission_type_derived"].map({
        SUBMISSION_TYPE_SNAPSHOT: SNAPSHOT_WEIGHT,
        SUBMISSION_TYPE_REVIEW: REVIEW_WEIGHT,
    }).fillna(SNAPSHOT_WEIGHT)

    agg_rows = []
    for date, group in scored_all.groupby("submitted_date"):
        row = {"date": date}
        row["n_snapshots"] = int((group["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT).sum())
        row["n_reviews"] = int((group["submission_type_derived"] == SUBMISSION_TYPE_REVIEW).sum())
        row["n_total"] = int(len(group))
        row["has_snapshot"] = row["n_snapshots"] > 0
        row["has_review"] = row["n_reviews"] > 0
        row["submitted_at"] = group["submitted_at"].max()

        weights_arr = group["_sw"].values.astype(float)

        for domain in DOMAINS:
            col = f"{domain} Score %"
            raw_col = f"{domain} Score % (raw)"
            if col in group.columns:
                row[col] = float(np.average(group[col].fillna(0), weights=weights_arr))
            if raw_col in group.columns:
                row[raw_col] = float(np.average(group[raw_col].fillna(0), weights=weights_arr))

        row["Overall Score %"] = float(np.mean([row.get(f"{d} Score %", 0) for d in DOMAINS]))

        if "meta_multiplier" in group.columns:
            row["meta_multiplier"] = float(np.average(group["meta_multiplier"].fillna(1.0), weights=weights_arr))

        day_wide = wide[wide["submitted_date"] == date].copy()

        for code, meta in by_code.items():
            if code not in day_wide.columns:
                continue

            raw_vals = day_wide[[code, "submission_type_derived", "submitted_at"]].copy()

            if meta["rtype"] == "boolean_yes_no":
                row[code] = bool(raw_vals[code].fillna(False).any())

            elif code in ("func_sleep_hours", "func_sleep_quality"):
                review_vals = pd.to_numeric(
                    raw_vals[raw_vals["submission_type_derived"] == SUBMISSION_TYPE_REVIEW][code],
                    errors="coerce",
                ).dropna()
                if not review_vals.empty:
                    row[code] = float(review_vals.mean())
                else:
                    all_vals = pd.to_numeric(raw_vals[code], errors="coerce").dropna()
                    row[code] = float(all_vals.mean()) if not all_vals.empty else np.nan

            elif meta["rtype"] in ("scale_1_5", "numeric"):
                rv = raw_vals[[code, "submission_type_derived"]].copy()
                rv["_w"] = rv["submission_type_derived"].map({
                    SUBMISSION_TYPE_SNAPSHOT: SNAPSHOT_WEIGHT,
                    SUBMISSION_TYPE_REVIEW: REVIEW_WEIGHT,
                }).fillna(SNAPSHOT_WEIGHT)
                rv[code] = pd.to_numeric(rv[code], errors="coerce")
                rv = rv.dropna(subset=[code])
                if not rv.empty:
                    row[code] = float(np.average(rv[code], weights=rv["_w"]))

            elif meta["rtype"] == "text":
                review_text = raw_vals[raw_vals["submission_type_derived"] == SUBMISSION_TYPE_REVIEW][code]
                review_text = review_text[review_text.notna() & (review_text.astype(str).str.strip() != "")]
                if not review_text.empty:
                    row[code] = str(review_text.iloc[-1])
                else:
                    snap_text = raw_vals[raw_vals["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT][code]
                    snap_text = snap_text[snap_text.notna() & (snap_text.astype(str).str.strip() != "")]
                    row[code] = str(snap_text.iloc[-1]) if not snap_text.empty else ""

        agg_rows.append(row)

    daily = pd.DataFrame(agg_rows).sort_values("date").reset_index(drop=True)
    for col in [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]:
        if col in daily.columns:
            daily[f"{col} Delta"] = daily[col].diff()
            daily[f"{col} 7d Avg"] = daily[col].rolling(7, min_periods=1).mean()
    return daily


def make_daily_continuous(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Adds calendar days that were missed, preserving NaN for score columns.
    Use for time-based calculations where gaps matter.
    """
    if daily.empty:
        return daily

    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    full_index = pd.date_range(df.index.min(), df.index.max(), freq="D")
    df = df.reindex(full_index)

    df["date"] = df.index.date
    df["has_entry"] = df["Overall Score %"].notna()

    for count_col in ["n_snapshots", "n_reviews", "n_total"]:
        if count_col in df.columns:
            df[count_col] = df[count_col].fillna(0).astype(int)

    for bool_col in ["has_snapshot", "has_review"]:
        if bool_col in df.columns:
            df[bool_col] = df[bool_col].fillna(False).astype(bool)

    for col in [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]:
        if col in df.columns:
            df[f"{col} Delta"] = df[col].diff()
            df[f"{col} 7d Avg"] = df[col].rolling(7, min_periods=1).mean()

    return df.reset_index(drop=True)


# ──────────────────────────────────────────────────────────
# EPISODES
# ──────────────────────────────────────────────────────────
EPISODE_TYPES = ["Depressive", "Hypomanic", "Manic", "Mixed", "Psychotic", "Other"]

EPISODE_COLOURS = {
    "Depressive": _hex_to_rgba("#FF3B30", 0.15),
    "Hypomanic": _hex_to_rgba("#FF9500", 0.12),
    "Manic": _hex_to_rgba("#FF9500", 0.20),
    "Mixed": _hex_to_rgba("#1C7EF2", 0.15),
    "Psychotic": _hex_to_rgba("#AF52DE", 0.15),
    "Other": _hex_to_rgba("#8E8E93", 0.12),
}

EPISODE_LINE_COLOURS = {
    "Depressive": "#FF3B30",
    "Hypomanic": "#FF9500",
    "Manic": "#FF9500",
    "Mixed": "#1C7EF2",
    "Psychotic": "#AF52DE",
    "Other": "#8E8E93",
}


@st.cache_data(ttl=30)
def load_episodes() -> pd.DataFrame:
    ws = safe_worksheet(EPISODE_TAB)
    cols = ["episode_id", "episode_type", "start_date", "end_date", "notes"]
    if ws is None:
        return pd.DataFrame(columns=cols)
    try:
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(values[1:], columns=values[0])
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.date
        return df.dropna(subset=["start_date", "end_date"]).reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=cols)


def _save_episodes(episodes: pd.DataFrame) -> tuple[bool, str]:
    ws = safe_worksheet(EPISODE_TAB)
    if ws is None:
        return False, f"Worksheet '{EPISODE_TAB}' not found."
    rows = [["episode_id", "episode_type", "start_date", "end_date", "notes"]]
    for _, row in episodes.iterrows():
        rows.append([
            str(row.get("episode_id", "")),
            str(row.get("episode_type", "")),
            str(row.get("start_date", "")),
            str(row.get("end_date", "")),
            str(row.get("notes", "")),
        ])
    ws.clear()
    ws.update("A1", rows)
    load_episodes.clear()
    return True, "Episode log saved."


def add_episode(episode_type: str, start_date, end_date, notes: str) -> tuple[bool, str]:
    episodes = load_episodes()
    episode_id = hashlib.md5(f"{episode_type}{start_date}{end_date}{notes}".encode()).hexdigest()[:8]
    new_row = pd.DataFrame([{
        "episode_id": episode_id,
        "episode_type": episode_type,
        "start_date": start_date,
        "end_date": end_date,
        "notes": notes,
    }])
    return _save_episodes(pd.concat([episodes, new_row], ignore_index=True))


def delete_episode(episode_id: str) -> tuple[bool, str]:
    episodes = load_episodes()
    return _save_episodes(episodes[episodes["episode_id"] != episode_id].reset_index(drop=True))


def add_episode_overlays(fig: go.Figure, episodes: pd.DataFrame) -> go.Figure:
    if episodes.empty:
        return fig
    for _, ep in episodes.iterrows():
        ep_type = str(ep.get("episode_type", "Other"))
        x0 = str(ep["start_date"])
        x1 = str(ep["end_date"])
        line_c = EPISODE_LINE_COLOURS.get(ep_type, "#8E8E93")
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor=EPISODE_COLOURS.get(ep_type, EPISODE_COLOURS["Other"]),
            line_width=1,
            line_color=line_c,
            annotation_text=ep_type,
            annotation_position="top left",
            annotation_font_size=9,
            annotation_font_color=line_c,
        )
    return fig


# ──────────────────────────────────────────────────────────
# BASELINE, NOTES, DATA QUALITY
# ──────────────────────────────────────────────────────────
def compute_personal_baseline(
    daily: pd.DataFrame,
    bands: dict[str, dict[str, float]],
    window_days: int = 90,
    episodes: pd.DataFrame | None = None,
) -> dict[str, dict]:
    empty = dict(mean=None, sd=None, n=0, lower=None, upper=None, reliable=False)
    if daily.empty:
        return {d: empty.copy() for d in DOMAINS}

    working = daily.copy()
    if "has_snapshot" in working.columns:
        working = working[working["has_snapshot"] == True]

    mask = pd.Series(True, index=working.index)
    for domain in DOMAINS:
        col = f"{domain} Score %"
        if col in working.columns:
            ceiling = bands.get(domain, {}).get("well", 20.0)
            mask &= working[col].fillna(999) <= ceiling

    if episodes is not None and not episodes.empty:
        ep_mask = pd.Series(False, index=working.index)
        for _, ep in episodes.iterrows():
            try:
                ep_start = pd.Timestamp(ep["start_date"]).date()
                ep_end = pd.Timestamp(ep["end_date"]).date()
                ep_mask |= (working["date"] >= ep_start) & (working["date"] <= ep_end)
            except Exception:
                pass
        mask &= ~ep_mask

    well_days = working[mask].sort_values("date").tail(window_days)
    result = {}
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
        sd = float(scores.std()) if n > 1 else 0.0
        result[domain] = dict(
            mean=round(mean, 1),
            sd=round(sd, 2),
            n=n,
            lower=round(mean - sd, 1),
            upper=round(mean + sd, 1),
            reliable=n >= PERSONAL_BASELINE_MIN_DAYS,
        )
    return result


_STOP_WORDS = {
    "i", "a", "an", "the", "and", "or", "but", "of", "to", "in", "is", "it",
    "my", "me", "was", "been", "have", "has", "had", "that", "this", "with",
    "for", "on", "are", "be", "at", "not", "felt", "feel", "feeling", "just",
    "like", "very", "quite", "pretty", "really", "some", "more", "less",
    "day", "today", "yesterday", "week", "night",
}


def extract_keywords(text: str, top_n: int = 8) -> list[str]:
    if not text or not isinstance(text, str):
        return []
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    filtered = [w for w in words if w not in _STOP_WORDS]
    return [w for w, _ in Counter(filtered).most_common(top_n)]


def build_notes_df(wide: pd.DataFrame, daily_scored: pd.DataFrame, bands: dict) -> pd.DataFrame:
    if wide.empty or "experience_description" not in wide.columns:
        return pd.DataFrame()
    notes = wide[
        wide["experience_description"].notna()
        & (wide["experience_description"].astype(str).str.strip() != "")
    ].copy()
    notes = notes[["submission_id", "submitted_at", "submitted_date", "experience_description"]].copy()
    notes["date"] = notes["submitted_date"]

    if not daily_scored.empty:
        score_cols = [f"{d} Score %" for d in DOMAINS]
        day_scores = daily_scored[["date"] + [c for c in score_cols if c in daily_scored.columns]].copy()
        notes = notes.merge(day_scores, on="date", how="left")

    def _worst_band(row):
        bands_on_day = [classify_score(row.get(f"{d} Score %", 0), d, bands) for d in DOMAINS]
        for b in ["critical", "warning", "caution", "watch", "well", "unknown"]:
            if b in bands_on_day:
                return b
        return "unknown"

    notes["worst_band"] = notes.apply(_worst_band, axis=1)
    notes["keywords"] = notes["experience_description"].apply(extract_keywords)
    return notes.sort_values("submitted_at", ascending=False).reset_index(drop=True)


def build_med_notes_df(wide: pd.DataFrame, daily_scored: pd.DataFrame) -> pd.DataFrame:
    if wide.empty or "medication_notes" not in wide.columns:
        return pd.DataFrame()
    med = wide[wide["medication_notes"].notna() & (wide["medication_notes"].astype(str).str.strip() != "")].copy()
    if med.empty:
        return pd.DataFrame()
    med["date"] = med["submitted_date"]
    med = med[["submitted_at", "date", "medication_notes"]].copy()
    if not daily_scored.empty:
        score_cols = [f"{d} Score %" for d in DOMAINS]
        med = med.merge(daily_scored[["date"] + [c for c in score_cols if c in daily_scored.columns]], on="date", how="left")
    return med.sort_values("submitted_at", ascending=False).reset_index(drop=True)


def build_data_quality_report(wide: pd.DataFrame, daily: pd.DataFrame, continuous: pd.DataFrame, comments: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def add(check: str, value: Any, note: str, level: str = "info"):
        rows.append({"Check": check, "Value": value, "Level": level, "Note": note})

    if wide.empty:
        add("Raw submissions", 0, "No submissions loaded.", "warning")
        return pd.DataFrame(rows)

    add("Raw submissions", len(wide), "Total cleaned submissions loaded.")
    add("Tracked calendar days", int(continuous["date"].nunique()) if not continuous.empty else 0, "Includes missed calendar days between first and latest entry.")
    add("Days with entries", int(daily["date"].nunique()) if not daily.empty else 0, "Recorded days only.")
    if not continuous.empty and "has_entry" in continuous.columns:
        missed = int((continuous["has_entry"] == False).sum())
        add("Missed days", missed, "Calendar days with no submission.", "warning" if missed else "ok")

    if not daily.empty:
        no_review = int((daily.get("n_reviews", pd.Series([0] * len(daily))) == 0).sum())
        no_snapshot = int((daily.get("n_snapshots", pd.Series([0] * len(daily))) == 0).sum())
        sleep_missing = int(daily["func_sleep_hours"].isna().sum()) if "func_sleep_hours" in daily.columns else 0
        add("Days with no review", no_review, "Daily aggregate uses snapshots only on these days.", "info")
        add("Days with no snapshot", no_snapshot, "Baseline excludes these days.", "warning" if no_snapshot else "ok")
        add("Days missing sleep hours", sleep_missing, "Affects sleep analysis.", "warning" if sleep_missing else "ok")

    dupes = int(wide["submission_id"].duplicated().sum()) if "submission_id" in wide.columns else 0
    add("Duplicate submission IDs", dupes, "Should normally be zero.", "warning" if dupes else "ok")

    if not comments.empty and "submission_id" in comments.columns and "submission_id" in wide.columns:
        valid_ids = set(wide["submission_id"].astype(str))
        orphan = int((~comments["submission_id"].astype(str).isin(valid_ids)).sum())
        add("Unlinked comments", orphan, "Comments whose submission_id no longer matches a submission.", "warning" if orphan else "ok")

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────
# ANALYSIS HELPERS
# ──────────────────────────────────────────────────────────
def _rolling_trend(series: pd.Series, window: int = 7) -> str:
    clean = series.dropna()
    if len(clean) < 3:
        return "insufficient data"
    tail = clean.tail(window)
    if len(tail) < 3:
        return "insufficient data"
    slope = np.polyfit(range(len(tail)), tail.values, 1)[0]
    if slope > 1.5:
        return "rising"
    if slope < -1.5:
        return "falling"
    return "stable"


def _recent_symptom_momentum(daily: pd.DataFrame) -> dict[str, float]:
    if daily.empty or len(daily.dropna(subset=["Overall Score %"])) < 2:
        return {d: 0.0 for d in DOMAINS}
    recent = daily.sort_values("date").tail(7)
    result = {}
    for d in DOMAINS:
        col = f"{d} Score %"
        clean = recent[[col]].dropna()
        if clean.empty:
            result[d] = 0.0
            continue
        w = np.arange(1, len(clean) + 1, dtype=float)
        w /= w.sum()
        result[d] = float(np.dot(clean[col].values, w))
    return result


def _consecutive_days_in_band(daily: pd.DataFrame, domain: str, bands: dict, target_bands: list[str]) -> int:
    if daily.empty:
        return 0
    col = f"{domain} Score %"
    if col not in daily.columns:
        return 0
    sorted_df = daily.sort_values("date", ascending=False)
    count = 0
    for score in sorted_df[col]:
        if pd.isna(score):
            break
        if classify_score(score, domain, bands) in target_bands:
            count += 1
        else:
            break
    return count


def _cross_domain_correlation(daily: pd.DataFrame) -> pd.DataFrame:
    cols = [f"{d} Score %" for d in DOMAINS]
    avail = [c for c in cols if c in daily.columns]
    if len(avail) < 2 or len(daily.dropna(subset=avail, how="all")) < 4:
        return pd.DataFrame()
    return daily[avail].corr().round(2)


def _flag_impact(daily: pd.DataFrame) -> pd.DataFrame:
    flag_codes = [q["code"] for q in QUESTION_CATALOG if q["group"] == "flags"]
    avail = [c for c in flag_codes if c in daily.columns]
    if not avail or daily.empty:
        return pd.DataFrame()

    rows = []
    for flag in avail:
        valid = daily[daily[flag].notna()] if flag in daily.columns else pd.DataFrame()
        flagged = valid[valid[flag] == True]
        not_flagged = valid[valid[flag] == False]
        for domain in DOMAINS:
            col = f"{domain} Score %"
            if col not in valid.columns:
                continue
            rows.append(dict(
                flag=flag,
                domain=domain,
                n_flagged=len(flagged[col].dropna()),
                n_not_flagged=len(not_flagged[col].dropna()),
                mean_when_flagged=flagged[col].mean() if not flagged.empty else np.nan,
                mean_when_not_flagged=not_flagged[col].mean() if not not_flagged.empty else np.nan,
            ))

    df = pd.DataFrame(rows).dropna()
    if df.empty:
        return df
    df["impact"] = df["mean_when_flagged"] - df["mean_when_not_flagged"]
    df["reliability"] = df.apply(lambda r: reliability_label(int(min(r["n_flagged"], r["n_not_flagged"]))), axis=1)
    return df.sort_values("impact", ascending=False).reset_index(drop=True)


PSY_PRIMARY_CODES = ["psy_heard_saw", "psy_suspicious", "psy_trust_perceptions", "psy_distress"]


def _mean_normalised(row: pd.Series, codes: list[str], invert: bool = False) -> float | None:
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
    bands: dict,
    window: int = 7,
    drop_threshold: float = 15.0,
    divergence_threshold: float = 12.0,
) -> dict:
    result = dict(
        status="insufficient_data",
        primary_delta=None,
        insight_delta=None,
        confidence_delta=None,
        finding="Not enough data to assess psychosis insight indicators.",
        severity="ok",
        days_analysed=0,
    )

    if daily.empty or len(daily.dropna(subset=["Psychosis Score %"])) < window:
        return result

    recent = daily.sort_values("date").tail(window).copy()
    result["days_analysed"] = len(recent)

    primary_scores = recent.apply(lambda r: _mean_normalised(r, PSY_PRIMARY_CODES, invert=False), axis=1).dropna()
    insight_scores = recent.apply(lambda r: _mean_normalised(r, ["meta_something_wrong", "meta_concerned"], invert=False), axis=1).dropna()
    confidence_scores = recent.apply(lambda r: _mean_normalised(r, ["psy_confidence_reality"], invert=True), axis=1).dropna()

    if len(primary_scores) < window or len(insight_scores) < window:
        return result

    def _trend(s: pd.Series) -> float:
        third = max(1, len(s) // 3)
        return float(s.tail(third).mean() - s.head(third).mean())

    primary_delta = _trend(primary_scores)
    insight_delta = _trend(insight_scores)
    confidence_delta = _trend(confidence_scores) if len(confidence_scores) >= 2 else 0.0

    result["primary_delta"] = round(primary_delta, 1)
    result["insight_delta"] = round(insight_delta, 1)
    result["confidence_delta"] = round(confidence_delta, 1)

    latest_psychosis = float(recent["Psychosis Score %"].dropna().iloc[-1])
    latest_band = classify_score(latest_psychosis, "Psychosis", bands)
    psychosis_still_elevated = latest_band in ("watch", "caution", "warning", "critical")

    primary_falling = primary_delta < -drop_threshold
    insight_falling = insight_delta < -divergence_threshold
    confidence_poor = confidence_delta < -divergence_threshold

    if not primary_falling:
        result.update(status="stable", finding="Psychosis indicators are not falling enough to assess insight divergence.", severity="ok")
        return result

    if primary_falling and not insight_falling:
        result.update(
            status="improvement_pattern",
            finding=f"Primary psychosis indicators have fallen by about {abs(primary_delta):.0f}pp and insight indicators have not declined. This pattern is more consistent with improvement, though it is still self-report data.",
            severity="ok",
        )
        return result

    if primary_falling and insight_falling and confidence_poor and psychosis_still_elevated:
        result.update(
            status="possible_insight_divergence",
            finding=f"Primary psychosis indicators have fallen by about {abs(primary_delta):.0f}pp, while insight indicators and confidence-related insight have also declined. Because Psychosis remains in the {latest_band} band, this may warrant clinical review.",
            severity="warning",
        )
        return result

    result.update(
        status="ambiguous",
        finding=f"Primary psychosis indicators have fallen by about {abs(primary_delta):.0f}pp, but insight indicators also declined. This is ambiguous and may be worth discussing clinically.",
        severity="caution",
    )
    return result


def compute_sleep_lead_lag(daily_continuous: pd.DataFrame, method: str = "pearson") -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """
    Non-causal lead/lag associations:
      previous-night sleep vs today score
      same-day sleep vs score
      yesterday score vs tonight sleep
    """
    required = {"date", "func_sleep_hours"}
    if daily_continuous.empty or not required.issubset(daily_continuous.columns):
        return None

    df = daily_continuous.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["sleep_previous_night"] = df["func_sleep_hours"].shift(1)

    rows = []
    for domain in DOMAINS:
        score_col = f"{domain} Score %"
        if score_col not in df.columns:
            continue

        pairs_prev = df[["sleep_previous_night", score_col]].dropna()
        pairs_same = df[["func_sleep_hours", score_col]].dropna()
        shifted = pd.DataFrame({
            "score_yesterday": df[score_col].shift(1),
            "sleep_tonight": df["func_sleep_hours"],
        }).dropna()

        prev_corr = pairs_prev["sleep_previous_night"].corr(pairs_prev[score_col], method=method) if len(pairs_prev) >= 3 else np.nan
        same_corr = pairs_same["func_sleep_hours"].corr(pairs_same[score_col], method=method) if len(pairs_same) >= 3 else np.nan
        lag_corr = shifted["score_yesterday"].corr(shifted["sleep_tonight"], method=method) if len(shifted) >= 3 else np.nan

        rows.append({
            "Domain": domain,
            "Previous-night sleep vs today score": round(prev_corr, 2) if pd.notna(prev_corr) else np.nan,
            "N previous-night": len(pairs_prev),
            "Same-day sleep vs score": round(same_corr, 2) if pd.notna(same_corr) else np.nan,
            "N same-day": len(pairs_same),
            "Yesterday score vs tonight sleep": round(lag_corr, 2) if pd.notna(lag_corr) else np.nan,
            "N lag": len(shifted),
            "Reliability": reliability_label(min(len(pairs_prev), len(pairs_same), len(shifted))),
        })

    return pd.DataFrame(rows), df


# ──────────────────────────────────────────────────────────
# PLOTLY CHARTS
# ──────────────────────────────────────────────────────────
def make_overview_chart(daily: pd.DataFrame, domains: list[str], bands: dict, show_rolling: bool, episodes: pd.DataFrame | None = None, height: int = 380) -> go.Figure:
    fig = go.Figure()
    if daily.empty:
        return fig
    dates = daily["date"].astype(str).tolist()

    for d in domains:
        col = f"{d} Score %"
        if col not in daily.columns:
            continue
        fig.add_trace(go.Scatter(
            x=dates,
            y=daily[col],
            mode="lines+markers",
            name=d,
            line=dict(color=DOMAIN_COLOURS[d], width=2),
            marker=dict(size=5),
            hovertemplate=f"{d}: %{{y:.1f}}%<extra></extra>",
        ))
        if show_rolling:
            avg_col = f"{col} 7d Avg"
            if avg_col in daily.columns:
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=daily[avg_col],
                    mode="lines",
                    name=f"{d} 7d avg",
                    showlegend=False,
                    line=dict(color=DOMAIN_COLOURS[d], width=1, dash="dash"),
                    opacity=0.4,
                    hovertemplate=f"{d} 7d avg: %{{y:.1f}}%<extra></extra>",
                ))

    for d in domains:
        b = bands.get(d, DEFAULT_BASELINE_BANDS.get(d, {}))
        fig.add_hline(y=b.get("well", 20), line_dash="dot", line_color="rgba(52,199,89,0.35)", line_width=1)

    if episodes is not None and not episodes.empty:
        fig = add_episode_overlays(fig, episodes)

    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
        xaxis=dict(title=None),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        paper_bgcolor="white",
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
    height: int = 320,
) -> go.Figure:
    fig = go.Figure()
    col = f"{domain} Score %"
    if daily.empty or col not in daily.columns:
        return fig

    dates = daily["date"].astype(str).tolist()
    b = bands.get(domain, DEFAULT_BASELINE_BANDS.get(domain, {}))
    well_c, watch_c, caution_c, warning_c = b.get("well", 20), b.get("watch", 40), b.get("caution", 60), b.get("warning", 75)

    for label, y0, y1, colour in [
        ("Well", 0, well_c, BAND_COLOURS["well"]),
        ("Watch", well_c, watch_c, BAND_COLOURS["watch"]),
        ("Caution", watch_c, caution_c, BAND_COLOURS["caution"]),
        ("Warning", caution_c, warning_c, BAND_COLOURS["warning"]),
        ("Critical", warning_c, 100, BAND_COLOURS["critical"]),
    ]:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=colour, line_width=0, annotation_text=label, annotation_position="right", annotation_font_size=10)

    for label, ceil in [("well", well_c), ("watch", watch_c), ("caution", caution_c), ("warning", warning_c)]:
        fig.add_hline(y=ceil, line_dash="dot", line_color=BAND_LINE_COLOURS[label], line_width=1)

    if personal:
        pb = personal.get(domain, {})
        if pb.get("reliable") and pb.get("mean") is not None:
            fig.add_hline(
                y=pb["mean"],
                line_dash="solid",
                line_color="rgba(90,130,230,0.8)",
                line_width=1.5,
                annotation_text=f"Personal baseline ({pb['n']}d)",
                annotation_position="left",
            )
            fig.add_hrect(
                y0=pb["lower"],
                y1=pb["upper"],
                fillcolor="rgba(90,130,230,0.08)",
                line=dict(color="rgba(90,130,230,0.3)", width=1, dash="dot"),
            )

    if show_rolling and f"{col} 7d Avg" in daily.columns:
        fig.add_trace(go.Scatter(
            x=dates,
            y=daily[f"{col} 7d Avg"],
            mode="lines",
            name="7d avg",
            line=dict(color="rgba(100,100,100,0.5)", width=1.5, dash="dash"),
        ))

    fig.add_trace(go.Scatter(
        x=dates,
        y=daily[col],
        mode="lines+markers",
        name=domain,
        line=dict(color=DOMAIN_COLOURS.get(domain, "#1C7EF2"), width=2),
        marker=dict(size=5),
        hovertemplate="%{x}<br>Score: %{y:.1f}%<extra></extra>",
    ))

    delta_col = f"{col} Delta"
    if delta_col in daily.columns:
        alert = daily[(daily[delta_col].abs() >= movement_threshold) & (daily[col] <= well_c)]
        if not alert.empty:
            fig.add_trace(go.Scatter(
                x=alert["date"].astype(str),
                y=alert[col],
                mode="markers",
                name="Movement",
                marker=dict(symbol="triangle-up", size=12, color="#FF9500", line=dict(color="white", width=1)),
            ))

    if episodes is not None and not episodes.empty:
        fig = add_episode_overlays(fig, episodes)

    fig.update_layout(
        height=height,
        margin=dict(l=10, r=90, t=30, b=10),
        yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
        xaxis=dict(title=None),
        showlegend=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
        title=dict(text=domain, font=dict(size=14), x=0),
    )
    return fig


def make_sleep_lead_chart(continuous_df: pd.DataFrame, selected_domains: list[str]) -> go.Figure:
    fig = go.Figure()
    if continuous_df.empty:
        return fig

    def zscore(s: pd.Series) -> pd.Series:
        s = pd.to_numeric(s, errors="coerce")
        sd = s.std()
        if pd.isna(sd) or sd == 0:
            return s * np.nan
        return (s - s.mean()) / sd

    dates = continuous_df["date"].astype(str)

    if "func_sleep_hours" in continuous_df.columns:
        fig.add_trace(go.Scatter(
            x=dates,
            y=zscore(continuous_df["func_sleep_hours"].shift(1)),
            name="Sleep previous night, z-score",
            line=dict(color="#8E8E93", dash="dot"),
        ))

    for d in selected_domains:
        col = f"{d} Score %"
        if col in continuous_df.columns:
            fig.add_trace(go.Scatter(
                x=dates,
                y=zscore(continuous_df[col]),
                name=f"{d} score, z-score",
                line=dict(color=DOMAIN_COLOURS.get(d, "#1C7EF2"), width=2),
            ))

    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Standardised value",
        xaxis_title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


# ──────────────────────────────────────────────────────────
# LOAD DATA
# ──────────────────────────────────────────────────────────
weights = load_weights()
bl_config = load_baseline_config()
bands = bl_config["bands"]
mv_threshold = bl_config["movement_threshold"]
pb_window = bl_config["personal_baseline_window"]

raw_df = load_sheet(NEW_FORM_TAB)
indexed_df = add_submission_indexing(raw_df)
wide_df = clean_and_widen(indexed_df)
snapshots_df = build_scored_table(wide_df, weights, daily_only=False)
daily_df = build_daily_weighted_submission_summary(wide_df, weights)
continuous_daily_df = make_daily_continuous(daily_df)

episodes_df = load_episodes()
personal_bl = compute_personal_baseline(daily_df, bands, pb_window, episodes=episodes_df)
notes_df = build_notes_df(wide_df, daily_df, bands)
med_notes_df = build_med_notes_df(wide_df, daily_df)
comments_df = load_comments()
quality_df = build_data_quality_report(wide_df, daily_df, continuous_daily_df, comments_df)


# ──────────────────────────────────────────────────────────
# SIDEBAR FILTERS
# ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Filters")

    if "last_refreshed" not in st.session_state:
        st.session_state["last_refreshed"] = dt.datetime.now()
    elapsed = int((dt.datetime.now() - st.session_state["last_refreshed"]).total_seconds())
    st.caption(f"Data last refreshed {elapsed}s ago")

    if st.button("🔄 Refresh data", use_container_width=True):
        load_sheet.clear()
        load_episodes.clear()
        load_weights.clear()
        load_baseline_config.clear()
        load_comments.clear()
        st.session_state["last_refreshed"] = dt.datetime.now()
        st.rerun()

    st.divider()

    if not daily_df.empty:
        min_date = daily_df["date"].min()
        max_date = daily_df["date"].max()
        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="filter_dates",
        )
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            filter_start, filter_end = date_range
        else:
            filter_start, filter_end = min_date, max_date
    else:
        filter_start, filter_end = None, None

    selected_domains = st.multiselect("Domains to show", DOMAINS, default=DOMAINS)
    show_rolling = st.toggle("Show 7-day rolling average", value=True)
    chart_height = st.slider("Chart height", 220, 620, 340, 20)


def _apply_date_filter(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    if df.empty or filter_start is None:
        return df
    return df[(df[date_col] >= filter_start) & (df[date_col] <= filter_end)].copy()


daily_filtered = _apply_date_filter(daily_df)
continuous_filtered = _apply_date_filter(continuous_daily_df)
snapshots_filtered = _apply_date_filter(snapshots_df, "submitted_date")
notes_filtered = _apply_date_filter(notes_df, "date") if not notes_df.empty else notes_df


# ──────────────────────────────────────────────────────────
# TOP-LEVEL SAFETY NOTICE
# ──────────────────────────────────────────────────────────
if not daily_df.empty and "dep_self_harm_ideation" in daily_df.columns:
    latest_self_harm = daily_df.sort_values("date").iloc[-1].get("dep_self_harm_ideation")
    if pd.notna(latest_self_harm) and latest_self_harm >= SELF_HARM_FLAG_THRESHOLD:
        st.error(
            "Self-harm ideation was reported recently. If there is any immediate risk, contact emergency services, "
            "your local crisis line, your crisis team, or a trusted person now. This dashboard cannot assess immediate safety."
        )


# ──────────────────────────────────────────────────────────
# TOP SUMMARY METRICS
# ──────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total entries", len(raw_df))
m2.metric("Days with entries", len(daily_df))
m3.metric("Calendar days tracked", len(continuous_daily_df))
m4.metric("Reliability", reliability_label(len(daily_df)))
if not daily_df.empty:
    latest_overall = float(daily_df["Overall Score %"].dropna().iloc[-1])
    prev_overall = float(daily_df["Overall Score %"].dropna().iloc[-2]) if len(daily_df["Overall Score %"].dropna()) > 1 else latest_overall
    m5.metric("Latest overall score", f"{latest_overall:.1f}%", delta=f"{latest_overall - prev_overall:+.1f}pp")
else:
    m5.metric("Latest overall score", "—")

st.divider()


# ──────────────────────────────────────────────────────────
# TABS
# ──────────────────────────────────────────────────────────
tab_today, tab_trends, tab_sleep, tab_episodes, tab_journal, tab_export, tab_quality, tab_settings = st.tabs([
    "Today",
    "Trends",
    "Sleep",
    "Episodes",
    "Journal",
    "Clinician Export",
    "Data Quality",
    "Settings",
])


# ── TODAY ────────────────────────────────────────────────
with tab_today:
    st.markdown("## Today / Current State")
    st.caption("Scores are custom self-monitoring indicators, not diagnostic scale scores.")

    if daily_df.empty:
        st.info("No data available.")
    else:
        latest = daily_df.sort_values("date").iloc[-1]
        latest_date = latest["date"]
        latest_mult = float(latest.get("meta_multiplier", 1.0) or 1.0)

        st.markdown(f"### Latest recorded day: {latest_date}")
        st.caption(
            f"Submissions: {int(latest.get('n_total', 1))} "
            f"({int(latest.get('n_snapshots', 0))} snapshot, {int(latest.get('n_reviews', 0))} review). "
            f"Reliability: {reliability_label(len(daily_df))} ({len(daily_df)} recorded days)."
        )

        if latest_mult > 1.05:
            st.warning(
                f"Meta amplification active: ×{latest_mult:.2f}. "
                "Scores are amplified because meta questions indicate intensification, feeling unlike usual self, or moving toward an episode."
            )

        cols = st.columns(len(DOMAINS))
        for i, domain in enumerate(DOMAINS):
            score = float(latest.get(f"{domain} Score %", 0) or 0)
            raw_score = float(latest.get(f"{domain} Score % (raw)", score) or score)
            band = classify_score(score, domain, bands)
            delta = float(latest.get(f"{domain} Score % Delta", 0) or 0)
            pb = personal_bl.get(domain, {})
            with cols[i]:
                st.metric(
                    domain,
                    f"{score:.1f}%",
                    delta=f"{delta:+.1f}pp",
                    help=f"Band: {band}. Raw pre-multiplier score: {raw_score:.1f}%.",
                )
                st.markdown(f"{BAND_EMOJI[band]} **{band.upper()}**")
                if pb.get("reliable") and pb.get("mean") is not None:
                    st.caption(f"vs baseline: {score - pb['mean']:+.1f}pp")
                else:
                    st.caption(f"baseline not reliable yet ({pb.get('n', 0)} well days)")

        st.divider()
        st.markdown("### Current-state summary")

        momentum = _recent_symptom_momentum(daily_df)
        highest_domain = max(DOMAINS, key=lambda d: latest.get(f"{d} Score %", 0) or 0)
        biggest_change = max(DOMAINS, key=lambda d: abs(latest.get(f"{d} Score % Delta", 0) or 0))

        summary_rows = [
            {"Item": "Highest current domain", "Value": f"{highest_domain}: {latest.get(f'{highest_domain} Score %', 0):.1f}%"},
            {"Item": "Biggest day-on-day movement", "Value": f"{biggest_change}: {latest.get(f'{biggest_change} Score % Delta', 0):+.1f}pp"},
            {"Item": "Highest 7-day momentum", "Value": f"{max(DOMAINS, key=lambda d: momentum[d])}: {momentum[max(DOMAINS, key=lambda d: momentum[d])]:.1f}%"},
        ]

        if "func_sleep_hours" in latest.index and pd.notna(latest.get("func_sleep_hours")):
            sleep_mean = daily_df.tail(7)["func_sleep_hours"].mean()
            summary_rows.append({"Item": "Sleep last night", "Value": f"{latest.get('func_sleep_hours'):.1f}h vs 7-day mean {sleep_mean:.1f}h"})

        if not med_notes_df.empty:
            latest_med = med_notes_df.sort_values("submitted_at", ascending=False).iloc[0]
            summary_rows.append({"Item": "Latest medication note", "Value": f"{latest_med['date']}: {str(latest_med['medication_notes'])[:120]}"})

        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Recent domain chart")
        st.plotly_chart(
            make_overview_chart(daily_df.tail(30), selected_domains, bands, show_rolling, episodes_df, height=chart_height),
            use_container_width=True,
        )


# ── TRENDS ───────────────────────────────────────────────
with tab_trends:
    st.markdown("## Trends")
    if daily_filtered.empty:
        st.info("No data in selected date range.")
    else:
        st.caption(
            f"Analysis reliability: {reliability_label(len(daily_filtered))} "
            f"({len(daily_filtered)} recorded days in selected range)."
        )

        st.markdown("### All selected domains")
        st.plotly_chart(
            make_overview_chart(daily_filtered, selected_domains, bands, show_rolling, episodes_df, height=chart_height),
            use_container_width=True,
        )

        st.markdown("### Per-domain bands and baseline")
        c1, c2 = st.columns(2)
        for i, domain in enumerate(selected_domains):
            with (c1 if i % 2 == 0 else c2):
                st.plotly_chart(
                    make_band_chart(
                        daily_filtered,
                        domain,
                        bands,
                        personal=personal_bl,
                        movement_threshold=mv_threshold,
                        show_rolling=show_rolling,
                        episodes=episodes_df,
                        height=chart_height,
                    ),
                    use_container_width=True,
                )

        st.divider()
        st.markdown("### Recent symptom momentum")
        st.caption("Weighted average of the last 7 recorded days, with more recent days weighted more heavily.")
        momentum = _recent_symptom_momentum(daily_filtered)
        mc = st.columns(len(DOMAINS))
        for i, domain in enumerate(DOMAINS):
            r = momentum[domain]
            band = classify_score(r, domain, bands)
            mc[i].metric(domain, f"{r:.1f}%", delta=f"{BAND_EMOJI[band]} {band}", delta_color="off")

        st.divider()
        st.markdown("### 7-day trend vs personal baseline")
        rows = []
        for d in DOMAINS:
            pb = personal_bl.get(d, {})
            trend = _rolling_trend(daily_filtered[f"{d} Score %"]) if f"{d} Score %" in daily_filtered.columns else "insufficient data"
            rows.append({
                "Domain": d,
                "7d trend": {"rising": "rising ↑", "falling": "falling ↓", "stable": "stable →"}.get(trend, trend),
                "7d mean": round(daily_filtered[f"{d} Score %"].tail(7).mean(), 1),
                "7d peak": round(daily_filtered[f"{d} Score %"].tail(7).max(), 1),
                "Personal baseline": f"{pb['mean']}%" if pb.get("reliable") else f"not reliable ({pb.get('n', 0)}d)",
                "Baseline ±1 SD": f"{pb['lower']}–{pb['upper']}%" if pb.get("reliable") else "—",
                "Well ceiling": f"{bands.get(d, {}).get('well', '?')}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Psychosis insight indicators")
        st.caption("This is a conservative self-report pattern check, not a clinical determination.")
        psy = detect_psychosis_insight_divergence(daily_filtered, bands)
        icon = {"ok": "🟢", "caution": "🟠", "warning": "🔴"}.get(psy["severity"], "⚪")
        st.markdown(f"{icon} **{psy['status'].replace('_', ' ').title()}**")
        st.write(psy["finding"])
        st.caption(f"Days analysed: {psy['days_analysed']} · Reliability: {reliability_label(psy['days_analysed'])}")

        if psy["primary_delta"] is not None:
            p1, p2, p3 = st.columns(3)
            p1.metric("Primary indicator change", f"{psy['primary_delta']:+.1f}pp")
            p2.metric("Insight indicator change", f"{psy['insight_delta']:+.1f}pp")
            p3.metric("Confidence-insight change", f"{psy['confidence_delta']:+.1f}pp")

        st.divider()
        st.markdown("### Cross-domain correlation")
        corr = _cross_domain_correlation(daily_filtered)
        if corr.empty:
            st.info("Need at least 4 recorded days.")
        else:
            st.caption("Pearson r across filtered daily entries. Correlation is association, not causation.")
            st.dataframe(corr.style.background_gradient(cmap="RdYlGn_r", vmin=-1, vmax=1), use_container_width=True)

        st.divider()
        st.markdown("### Flag impact")
        impact = _flag_impact(daily_filtered)
        if impact.empty:
            st.info("Not enough flag data.")
        else:
            show = impact.assign(
                impact=lambda df: df["impact"].round(1),
                mean_when_flagged=lambda df: df["mean_when_flagged"].round(1),
                mean_when_not_flagged=lambda df: df["mean_when_not_flagged"].round(1),
            )
            st.caption("Impact = mean domain score on flagged days minus non-flagged days. Interpret cautiously when N is low.")
            st.dataframe(show, use_container_width=True, hide_index=True)


# ── SLEEP ────────────────────────────────────────────────
with tab_sleep:
    st.markdown("## Sleep")
    st.caption("Sleep associations are exploratory and non-causal.")

    if daily_filtered.empty or "func_sleep_hours" not in daily_filtered.columns:
        st.info("No sleep data available.")
    else:
        sleep = daily_filtered[["date", "func_sleep_hours"] + (["func_sleep_quality"] if "func_sleep_quality" in daily_filtered.columns else [])].copy()
        sleep_valid = sleep.dropna(subset=["func_sleep_hours"])

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Mean sleep", f"{sleep_valid['func_sleep_hours'].mean():.1f}h" if not sleep_valid.empty else "—")
        s2.metric("Nights < 6h", int((sleep_valid["func_sleep_hours"] < 6).sum()) if not sleep_valid.empty else 0)
        s3.metric("Nights > 9h", int((sleep_valid["func_sleep_hours"] > 9).sum()) if not sleep_valid.empty else 0)
        s4.metric("Reliability", reliability_label(len(sleep_valid)))

        if not sleep_valid.empty:
            fig_sleep = go.Figure()
            fig_sleep.add_trace(go.Scatter(
                x=sleep_valid["date"].astype(str),
                y=sleep_valid["func_sleep_hours"],
                mode="lines+markers",
                name="Sleep hours",
                line=dict(color="#8E8E93", width=2),
            ))
            fig_sleep.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=10, b=10),
                yaxis_title="Hours",
                xaxis_title=None,
                plot_bgcolor="white",
                paper_bgcolor="white",
            )
            st.plotly_chart(fig_sleep, use_container_width=True)

        st.divider()
        st.markdown("### Sleep and mood lead/lag associations")
        method = st.radio("Correlation method", ["pearson", "spearman"], horizontal=True)
        res = compute_sleep_lead_lag(continuous_filtered, method=method)
        if res is None:
            st.info("Insufficient sleep data.")
        else:
            corr_df, corr_data = res
            st.caption(
                "Negative values mean lower sleep tends to align with higher score, depending on the column. "
                "Use N and reliability before interpreting."
            )
            st.dataframe(
                corr_df.style.background_gradient(
                    subset=[
                        "Previous-night sleep vs today score",
                        "Same-day sleep vs score",
                        "Yesterday score vs tonight sleep",
                    ],
                    cmap="RdYlGn",
                    vmin=-1,
                    vmax=1,
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("### Previous-night sleep vs today scores")
            st.plotly_chart(make_sleep_lead_chart(corr_data, selected_domains), use_container_width=True)


# ── EPISODES ─────────────────────────────────────────────
with tab_episodes:
    st.markdown("## Episodes")
    st.caption("Episode labels are used for chart overlays and to exclude labelled episode periods from personal baseline.")

    if safe_worksheet(EPISODE_TAB) is None:
        st.warning(f"Worksheet '{EPISODE_TAB}' not found. Create it with columns: episode_id, episode_type, start_date, end_date, notes.")

    with st.form("add_episode_form"):
        c1, c2, c3 = st.columns([2, 2, 2])
        ep_type = c1.selectbox("Episode type", EPISODE_TYPES)
        ep_start = c2.date_input("Start date")
        ep_end = c3.date_input("End date")
        ep_notes = st.text_input("Notes")
        submitted = st.form_submit_button("Add episode", type="primary")
        if submitted:
            if ep_end < ep_start:
                st.error("End date must be on or after start date.")
            else:
                ok, msg = add_episode(ep_type, ep_start, ep_end, ep_notes)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

    st.divider()
    if episodes_df.empty:
        st.info("No episodes labelled yet.")
    else:
        for _, ep in episodes_df.sort_values("start_date", ascending=False).iterrows():
            c1, c2 = st.columns([5, 1])
            duration = (pd.Timestamp(ep["end_date"]) - pd.Timestamp(ep["start_date"])).days + 1
            c1.markdown(f"**{ep['episode_type']}** — {ep['start_date']} to {ep['end_date']} ({duration} days)  \n{ep.get('notes', '')}")
            if c2.button("Delete", key=f"del_{ep['episode_id']}"):
                ok, msg = delete_episode(ep["episode_id"])
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

        st.divider()
        st.markdown("### Scores around episodes")
        for _, ep in episodes_df.sort_values("start_date", ascending=False).iterrows():
            start = pd.Timestamp(ep["start_date"])
            end = pd.Timestamp(ep["end_date"])
            window_start = (start - pd.Timedelta(days=14)).date()
            window_end = (end + pd.Timedelta(days=14)).date()
            ep_window = daily_df[(daily_df["date"] >= window_start) & (daily_df["date"] <= window_end)].copy()
            if ep_window.empty:
                continue
            with st.expander(f"{ep['episode_type']} — {ep['start_date']} to {ep['end_date']}"):
                single_ep = episodes_df[episodes_df["episode_id"] == ep["episode_id"]]
                st.plotly_chart(make_overview_chart(ep_window, DOMAINS, bands, True, single_ep, height=300), use_container_width=True)


# ── JOURNAL ──────────────────────────────────────────────
with tab_journal:
    st.markdown("## Journal")
    if notes_filtered.empty:
        st.info("No journal entries in the selected date range.")
    else:
        j1, j2, j3 = st.columns([3, 2, 2])
        search_term = j1.text_input("Search entries", placeholder="keyword...")
        band_filter = j2.multiselect(
            "Band",
            ["well", "watch", "caution", "warning", "critical"],
            default=["well", "watch", "caution", "warning", "critical"],
        )
        sort_order = j3.radio("Sort", ["Newest first", "Oldest first"], horizontal=True)

        shown = notes_filtered[notes_filtered["worst_band"].isin(band_filter)].copy()
        if search_term:
            shown = shown[shown["experience_description"].str.contains(search_term, case=False, na=False)]
        if sort_order == "Oldest first":
            shown = shown.sort_values("submitted_at")

        st.caption(f"Showing {len(shown)} of {len(notes_filtered)} entries.")

        if not shown.empty:
            with st.expander("Keyword frequency"):
                all_kw = [kw for kws in shown["keywords"] for kw in kws]
                counts = Counter(all_kw).most_common(20)
                if counts:
                    words, freqs = zip(*counts)
                    fig_kw = go.Figure(go.Bar(x=freqs, y=words, orientation="h", marker_color="#1C7EF2"))
                    fig_kw.update_layout(
                        height=max(300, len(words) * 24),
                        margin=dict(l=10, r=10, t=10, b=10),
                        yaxis=dict(autorange="reversed"),
                        xaxis=dict(title="Mentions"),
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                    )
                    st.plotly_chart(fig_kw, use_container_width=True)
                else:
                    st.info("No keywords extracted.")

        st.divider()
        for row_idx, (_, entry) in enumerate(shown.iterrows()):
            band = entry.get("worst_band", "unknown")
            hex_colour = BAND_COLOUR_HEX.get(band, "#8E8E93")
            emoji = BAND_EMOJI.get(band, "⚪")
            date_str = str(entry.get("date", ""))
            text = str(entry.get("experience_description", ""))
            keywords = entry.get("keywords", [])

            domain_context = []
            for d in DOMAINS:
                sc = entry.get(f"{d} Score %")
                if sc is not None and not pd.isna(sc):
                    b = classify_score(sc, d, bands)
                    domain_context.append(f"{d}: {sc:.0f}% ({b})")

            st.markdown(
                f"""<div style="
                    border-left: 4px solid {hex_colour};
                    padding: 12px 16px;
                    margin-bottom: 12px;
                    border-radius: 4px;
                    background: {hex_colour}18;
                ">
                <strong>{emoji} {date_str}</strong>
                &nbsp;&nbsp;<span style="color:#666;font-size:0.85em">{' · '.join(domain_context)}</span>
                </div>""",
                unsafe_allow_html=True,
            )

            display_text = text
            if search_term:
                display_text = re.sub(f"({re.escape(search_term)})", r"**\1**", display_text, flags=re.IGNORECASE)
            st.markdown(display_text)

            if keywords:
                st.markdown("*Keywords: " + " ".join(f"`{kw}`" for kw in keywords[:6]) + "*")

            submission_id = str(entry.get("submission_id", ""))
            entry_comments = get_comments_for_submission(submission_id, comments_df)
            for c in entry_comments:
                c_time = str(c.get("commented_at", ""))[:16]
                c_text = str(c.get("comment_text", ""))
                st.markdown(f"> 💬 *{c_time}* — {c_text}")

            comment_key = f"comment_input_{submission_id}_{row_idx}"
            new_comment = st.text_input("Add a note", key=comment_key, label_visibility="collapsed", placeholder="Type a note…")
            if st.button("Save note", key=f"save_{submission_id}_{row_idx}"):
                if new_comment.strip():
                    ok, msg = save_comment(submission_id, new_comment.strip())
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
                else:
                    st.warning("Note is empty.")

            st.divider()

    st.markdown("## Medication Notes")
    med_filtered = _apply_date_filter(med_notes_df, "date") if not med_notes_df.empty else med_notes_df
    if med_filtered.empty:
        st.info("No medication notes in selected range.")
    else:
        for _, m in med_filtered.iterrows():
            st.markdown(f"**💊 {m['date']}**")
            st.write(str(m["medication_notes"]))
            st.divider()


# ── EXPORT ───────────────────────────────────────────────
def generate_clinician_report(window_days: int = 30) -> str:
    today = dt.date.today()
    window_start = today - dt.timedelta(days=window_days)
    period = daily_df[daily_df["date"] >= window_start] if not daily_df.empty else daily_df

    lines = [
        "# Bipolar Dashboard — Clinician Summary",
        f"**Generated:** {today.strftime('%d %B %Y')}",
        f"**Period:** Last {window_days} days ({window_start.strftime('%d %b')} – {today.strftime('%d %b %Y')})",
        "",
        "**Important note:** This is self-reported monitoring data. Scores are custom weighted indicators, not validated diagnostic scales. This summary is intended to support clinical conversation, not replace clinical judgement.",
        "",
        "## Current Status",
    ]

    if daily_df.empty:
        lines.append("*No daily data available.*")
    else:
        latest = daily_df.sort_values("date").iloc[-1]
        lines.append(f"**Latest entry:** {latest['date']}")
        lines.append(f"**Submissions that day:** {int(latest.get('n_total', 1))} ({int(latest.get('n_snapshots', 0))} snapshot, {int(latest.get('n_reviews', 0))} review)")
        lines.append(f"**Meta multiplier:** ×{float(latest.get('meta_multiplier', 1.0) or 1.0):.2f}")
        lines.append("")
        lines.append("| Domain | Score | Band | vs baseline |")
        lines.append("|--------|-------|------|-------------|")
        for d in DOMAINS:
            score = float(latest.get(f"{d} Score %", 0) or 0)
            band = classify_score(score, d, bands)
            pb = personal_bl.get(d, {})
            vs = f"{score - pb['mean']:+.1f}pp" if pb.get("reliable") and pb.get("mean") is not None else "—"
            lines.append(f"| {d} | {score:.1f}% | {band.upper()} | {vs} |")

    lines += ["", f"## Domain Trends ({window_days} days)"]
    if period.empty:
        lines.append("*No data in this period.*")
    else:
        lines.append("| Domain | Mean | Peak | Days warning+ |")
        lines.append("|--------|------|------|---------------|")
        for d in DOMAINS:
            col = f"{d} Score %"
            scores = period[col].dropna()
            warning_days = int(scores.apply(lambda s: classify_score(s, d, bands) in ["warning", "critical"]).sum())
            lines.append(f"| {d} | {scores.mean():.1f}% | {scores.max():.1f}% | {warning_days} |")

    lines += ["", "## Personal Baseline"]
    for d in DOMAINS:
        pb = personal_bl.get(d, {})
        if pb.get("reliable"):
            lines.append(f"- **{d}:** mean {pb['mean']}%, ±1 SD {pb['lower']}–{pb['upper']}% ({pb['n']} well days)")
        else:
            lines.append(f"- **{d}:** not yet reliable ({pb.get('n', 0)} well days)")

    lines += ["", "## Labelled Episodes"]
    if episodes_df.empty:
        lines.append("*No episodes labelled.*")
    else:
        recent_ep = episodes_df[pd.to_datetime(episodes_df["end_date"]) >= pd.Timestamp(window_start)]
        if recent_ep.empty:
            lines.append("*No episodes ending in this period.*")
        else:
            for _, ep in recent_ep.sort_values("start_date", ascending=False).iterrows():
                lines.append(f"- **{ep['episode_type']}** — {ep['start_date']} to {ep['end_date']}" + (f": {ep['notes']}" if ep.get("notes") else ""))

    lines += ["", "## Medication Notes"]
    if med_notes_df.empty:
        lines.append("*No medication notes recorded.*")
    else:
        recent_med = med_notes_df[med_notes_df["date"] >= window_start]
        if recent_med.empty:
            lines.append("*No medication notes in this period.*")
        else:
            for _, m in recent_med.iterrows():
                lines.append(f"- **{m['date']}:** {m['medication_notes']}")

    lines += ["", "## Journal Highlights", "*(Entries from Caution band or above)*"]
    if notes_df.empty:
        lines.append("*No journal entries.*")
    else:
        recent_notes = notes_df[(notes_df["date"] >= window_start) & (notes_df["worst_band"].isin(["caution", "warning", "critical"]))]
        if recent_notes.empty:
            lines.append("*No elevated-band journal entries in this period.*")
        else:
            for _, n in recent_notes.sort_values("submitted_at", ascending=False).head(10).iterrows():
                text = str(n["experience_description"])
                lines.append(f"- **{n['date']}** [{n['worst_band'].upper()}]: {text[:300]}" + ("…" if len(text) > 300 else ""))

    lines += [
        "",
        "---",
        "*Automatically generated from self-reported monitoring data.*",
    ]
    return "\n".join(lines)


with tab_export:
    st.markdown("## Clinician Export")
    export_window = st.slider("Days to cover", 7, 90, 30, 7)
    report = generate_clinician_report(export_window)

    with st.expander("Preview", expanded=True):
        st.markdown(report)

    st.markdown("### Copy-ready text")
    st.text_area("Select all and copy", value=report, height=420)


# ── DATA QUALITY ─────────────────────────────────────────
with tab_quality:
    st.markdown("## Data Quality")
    st.caption("These checks make the dashboard easier to interpret and debug.")
    if quality_df.empty:
        st.info("No quality checks available.")
    else:
        st.dataframe(quality_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Daily model note")
    st.info(
        "Daily domain scores are weighted averages of per-submission scores. "
        "Snapshots are weighted 1.0 and retrospective reviews 0.5. "
        "Continuous-date rows are used for temporal calculations but missed days keep score values as NaN."
    )

    with st.expander("Daily table"):
        st.dataframe(daily_df, use_container_width=True)

    with st.expander("Continuous daily table"):
        st.dataframe(continuous_daily_df, use_container_width=True)

    with st.expander("Wide submissions"):
        st.dataframe(wide_df, use_container_width=True)

    with st.expander("Raw worksheet"):
        st.dataframe(raw_df, use_container_width=True)


# ── SETTINGS ─────────────────────────────────────────────
with tab_settings:
    st.markdown("## Settings")
    st.caption("Changes are saved to the Google Sheet settings tabs if those tabs exist.")

    st.markdown("### Baseline thresholds")
    updated_config = {
        "bands": {d: v.copy() for d, v in bands.items()},
        "movement_threshold": mv_threshold,
        "personal_baseline_window": pb_window,
    }

    for domain in DOMAINS:
        with st.expander(domain, expanded=False):
            b = updated_config["bands"][domain]
            cols = st.columns(4)
            b["well"] = cols[0].number_input("Well", 0.0, 100.0, float(b["well"]), 0.5, key=f"bl_{domain}_well")
            b["watch"] = cols[1].number_input("Watch", 0.0, 100.0, float(b["watch"]), 0.5, key=f"bl_{domain}_watch")
            b["caution"] = cols[2].number_input("Caution", 0.0, 100.0, float(b["caution"]), 0.5, key=f"bl_{domain}_caution")
            b["warning"] = cols[3].number_input("Warning", 0.0, 100.0, float(b["warning"]), 0.5, key=f"bl_{domain}_warning")
            if [b["well"], b["watch"], b["caution"], b["warning"]] != sorted([b["well"], b["watch"], b["caution"], b["warning"]]):
                st.warning("Ceilings must be ascending.")

    updated_config["movement_threshold"] = st.number_input("Movement alert threshold (pp)", 1.0, 50.0, float(mv_threshold), 0.5)
    updated_config["personal_baseline_window"] = st.number_input("Personal baseline window (well days)", 14, 365, int(pb_window), 1)

    if st.button("Save baseline config", type="primary"):
        ok, msg = save_baseline_config(updated_config)
        (st.success if ok else st.error)(msg)

    st.divider()
    st.markdown("### Scoring weights")
    st.caption(
        "Sleep weights are additionally scaled by domain: Depression hours ×0.35 and quality ×0.45; Mania/Mixed ×1.0."
    )

    updated_weights = weights.copy()
    cat = catalog_df()

    for group in ["depression", "mania", "mixed", "psychosis", "functioning", "meta", "flags", "observations"]:
        rows = cat[cat["group"] == group]
        if rows.empty:
            continue
        with st.expander(group.title(), expanded=False):
            for _, row in rows.iterrows():
                code = row["code"]
                if code not in updated_weights:
                    continue
                updated_weights[code] = st.number_input(
                    code,
                    min_value=0.0,
                    max_value=10.0,
                    step=0.25,
                    value=float(updated_weights.get(code, 0.0)),
                    key=f"w_{code}",
                )

    c1, c2 = st.columns(2)
    if c1.button("Save weights", type="primary"):
        ok, msg = save_weights(updated_weights)
        (st.success if ok else st.error)(msg)

    if c2.button("Reset weights to defaults"):
        ok, msg = save_weights(DEFAULT_WEIGHTS.copy())
        (st.success if ok else st.error)("Reset." if ok else msg)

    st.divider()
    st.markdown("### Question catalog")
    display_cols = ["code", "text", "group", "meta_role", "rtype", "polarity", "domains", "order"]
    cat_display = catalog_df()
    st.dataframe(cat_display[[c for c in display_cols if c in cat_display.columns]], use_container_width=True)
