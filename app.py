"""
Bipolar Dashboard — streamlined build.

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

import datetime as dt
import hashlib
import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import gspread
import streamlit as st

# ── PAGE CONFIG ───────────────────────────────────────────
st.set_page_config(page_title="Bipolar Dashboard", layout="wide")
st.title("Bipolar Dashboard")

# ── AUTH ─────────────────────────────────────────────────
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

# ── GOOGLE SHEETS ─────────────────────────────────────────
SHEET_NAME   = "Bipolar Dashboard"
NEW_FORM_TAB = "Updated Bipolar Form"
SETTINGS_TAB = "Scoring Settings"
BASELINE_TAB = "Baseline Settings"
EPISODE_TAB  = "Episode Log"
COMMENTS_TAB = "Journal Comments"
MED_LOG_TAB  = "Medication Log"

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

# ── CONSTANTS ─────────────────────────────────────────────
DOMAINS = ["Depression", "Mania", "Psychosis", "Mixed"]

DEFAULT_BASELINE_BANDS: dict[str, dict[str, float]] = {
    "Depression": {"well": 20.0, "watch": 40.0, "caution": 60.0, "warning": 75.0},
    "Mania":      {"well": 20.0, "watch": 40.0, "caution": 60.0, "warning": 75.0},
    "Mixed":      {"well": 18.0, "watch": 35.0, "caution": 55.0, "warning": 70.0},
    "Psychosis":  {"well": 12.0, "watch": 28.0, "caution": 50.0, "warning": 68.0},
}

DEFAULT_MOVEMENT_THRESHOLD: float = 10.0
SELF_HARM_FLAG_THRESHOLD: int = 1
PERSONAL_BASELINE_MIN_DAYS: int = 14
META_MULTIPLIER_MAX: float = 1.35

SUBMISSION_TYPE_REVIEW   = "review"
SUBMISSION_TYPE_SNAPSHOT = "snapshot"
REVIEW_WEIGHT   = 0.5
SNAPSHOT_WEIGHT = 1.0

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

EPISODE_TYPES = ["Depressive", "Hypomanic", "Manic", "Mixed", "Psychotic", "Other"]
EPISODE_LINE_COLOURS = {
    "Depressive": "#FF3B30", "Hypomanic": "#FF9500", "Manic": "#FF9500",
    "Mixed": "#1C7EF2", "Psychotic": "#AF52DE", "Other": "#8E8E93",
}

MED_CHANGE_TYPES = ["Started", "Increased", "Decreased", "Stopped", "Dose adjusted", "Added PRN", "Other"]
MED_DOSE_UNITS   = ["mg", "mcg", "g", "ml", "units", "tablets"]
MED_FREQUENCIES  = ["Once daily", "Twice daily", "Three times daily", "Four times daily",
                    "As needed (PRN)", "Every other day", "Weekly", "Other"]

# ── HELPERS ───────────────────────────────────────────────
def _hex_to_rgba(hex_colour: str, alpha: float = 0.15) -> str:
    h = hex_colour.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "y", "checked"}

# ── QUESTION CATALOG ──────────────────────────────────────
# Helper to reduce repetition in catalog definitions
def _q(code, text, group, rtype, polarity, domains, order, **kw) -> dict:
    return dict(code=code, text=text, group=group, rtype=rtype, polarity=polarity,
                domains=domains, order=order, score_in_snapshot=True,
                score_in_daily=True, **kw)

def _scale(code, text, group, polarity, domains, order, **kw) -> dict:
    return _q(code, text, group, "scale_1_5", polarity, domains, order, **kw)

def _flag(code, text, domains, order) -> dict:
    return _q(code, text, "flags", "boolean_yes_no", "higher_worse", domains, order)

def _obs(code, text, domains, order) -> dict:
    return _q(code, text, "observations", "boolean_yes_no", "higher_worse", domains, order)

_DEP = ["Depression"]
_MAN = ["Mania"]
_PSY = ["Psychosis"]
_MIX = ["Mixed"]
_DM  = ["Depression", "Mania"]
_MP  = ["Psychosis", "Mixed"]
_MM  = ["Mania", "Mixed"]
_ALL = ["Depression", "Mania", "Psychosis", "Mixed"]
_DMM = ["Depression", "Mania", "Mixed", "Psychosis"]
_SLP = ["Depression", "Mania", "Mixed"]

QUESTION_CATALOG: list[dict] = [
    _q("submission_type", "What kind of entry is this?", "notes", "text", "not_applicable", [], 5),
    # Depression
    _scale("dep_low_mood",          "Have I felt a low mood?",                                              "depression", "higher_worse",  _DEP, 10),
    _scale("dep_slowed_low_energy", "Have I felt slowed down or low on energy?",                            "depression", "higher_worse",  _DEP, 20),
    _scale("dep_low_motivation",    "Have I felt low on motivation or had difficulty initiating tasks?",    "depression", "higher_worse",  _DEP, 30),
    _scale("dep_anhedonia",         "Have I felt a lack of interest or pleasure in activities?",            "depression", "higher_worse",  _DEP, 40),
    _scale("dep_withdrawal",        "Have I been socially or emotionally withdrawn?",                       "depression", "higher_worse",  _DEP, 50),
    _scale("dep_self_harm_ideation","Have I had ideation around self-harming or suicidal behaviours?",      "depression", "higher_worse",  _DEP, 60),
    # Mania
    _scale("man_elevated_mood",       "Have I felt an elevated mood?",                                      "mania", "higher_worse", _MAN,      70),
    _scale("man_sped_up_high_energy", "Have I felt sped up or high on energy?",                             "mania", "higher_worse", ["Mania","Mixed"], 80),
    _scale("man_racing_thoughts",     "Have I had racing thoughts or speech?",                               "mania", "higher_worse", _MAN,     90),
    _scale("man_goal_drive",          "Have I had an increased drive towards goal-directed activity?",       "mania", "higher_worse", _MAN,    100),
    _scale("man_impulsivity",         "Have I felt impulsivity or an urge to take risky actions?",          "mania", "higher_worse", _MAN,    110),
    _scale("man_agitation",           "Have I felt agitated or restless?",                                  "mania", "higher_worse", ["Mania","Mixed"], 120),
    _scale("man_irritability",        "Have I been more irritable and reactive than normal?",               "mania", "higher_worse", ["Mania","Mixed"], 130),
    _scale("man_cant_settle",         "Have I been unable to settle or switch off?",                        "mania", "higher_worse", _MAN,    140),
    # Mixed
    _scale("mix_high_energy_low_mood",   "Have I had a high energy combined with low mood?",               "mixed", "higher_worse", _MIX, 150),
    _scale("mix_rapid_emotional_shifts", "Have I experienced rapid emotional shifts?",                      "mixed", "higher_worse", _MIX, 160),
    # Psychosis
    _scale("psy_heard_saw",         "Have I heard or seen things others didn't?",                           "psychosis", "higher_worse", _PSY, 170),
    _scale("psy_suspicious",        "Have I felt watched, followed, targeted or suspicious?",               "psychosis", "higher_worse", _PSY, 180),
    _scale("psy_trust_perceptions", "Have I had trouble trusting my perceptions and thoughts?",             "psychosis", "higher_worse", _PSY, 190),
    _scale("psy_confidence_reality","How confident have I been in the reality of these experiences?",       "psychosis", "higher_worse", _PSY, 200),
    _scale("psy_distress",          "How distressed have I been by these beliefs and experiences?",         "psychosis", "higher_worse", _PSY, 210),
    # Functioning
    _scale("func_work",         "How effectively have I been functioning at work?",         "functioning", "higher_better", _DM, 220),
    _scale("func_daily",        "How well have I been functioning in my daily life?",       "functioning", "higher_better", _DM, 230),
    _q("func_sleep_hours",   "How many hours did I sleep last night?",         "functioning", "numeric",   "custom_sleep",  _SLP, 450, score_in_snapshot=False),
    _q("func_sleep_quality", "How poor was my sleep quality last night",       "functioning", "scale_1_5", "higher_worse",  _SLP, 460, score_in_snapshot=False),
    # Meta — force multipliers
    _scale("meta_unlike_self",       "Do I feel unlike my usual self?",                     "meta", "higher_worse", [], 240, meta_role="force_multiplier"),
    _scale("meta_intensifying",      "Is my state intensifying (in any direction)?",        "meta", "higher_worse", [], 300, meta_role="force_multiplier"),
    _scale("meta_towards_episode",   "Do I feel like I'm moving towards an episode?",       "meta", "higher_worse", [], 310, meta_role="force_multiplier"),
    # Meta — insight-inverse
    _scale("meta_something_wrong",   "Do I think something may be wrong or changing?",      "meta", "higher_worse", _DMM, 250, meta_role="insight_inverse_psychosis"),
    _scale("meta_concerned",         "Am I concerned about my current state?",              "meta", "higher_worse", _DMM, 260, meta_role="insight_inverse_psychosis"),
    # Meta — contributors
    _scale("meta_disorganised_thoughts",   "Do my thoughts feel disorganised or hard to follow?", "meta", "higher_worse", _MP, 270, meta_role="contributor"),
    _scale("meta_attention_unstable",      "Is my attention unstable or jumping?",                "meta", "higher_worse", _MM, 280, meta_role="contributor"),
    _scale("meta_driven_without_thinking", "Do I feel driven to act without thinking?",           "meta", "higher_worse", _MM, 290, meta_role="contributor"),
    # Flags
    _flag("flag_not_myself",          "I've been feeling \"not like myself\"",                      ["Depression","Mania","Psychosis"],          320),
    _flag("flag_mood_shift",          "I noticed a sudden mood shift",                              _DMM,                                        330),
    _flag("flag_missed_medication",   "I missed medication",                                        ["Depression","Mania","Psychosis"],          340),
    _flag("flag_sleep_medication",    "I took sleeping or anti-anxiety medication",                 [],                                          350),
    _flag("flag_routine_disruption",  "There were significant disruptions to my routine",           _DMM,                                        360),
    _flag("flag_physiological_stress","I had a major physiological stress",                         ["Depression","Mania","Psychosis"],          370),
    _flag("flag_psychological_stress","I had a major psychological stress",                         ["Depression","Mania","Psychosis"],          380),
    # Observations
    _obs("obs_up_now",      "Observations [I feel like I'm experiencing an up]",          _MAN, 390),
    _obs("obs_down_now",    "Observations [I feel like I'm experiencing a down]",         _DEP, 400),
    _obs("obs_mixed_now",   "Observations [I feel like I'm experiencing a mixed]",        _MP,  410),
    _obs("obs_up_coming",   "Observations [I feel like I'm going to experience an up]",   _MAN, 420),
    _obs("obs_down_coming", "Observations [I feel like I'm going to experience a down]",  _DEP, 430),
    _obs("obs_mixed_coming","Observations [I feel like I'm going to experience a mixed]", _MP,  440),
    # Notes
    _q("experience_description", "How would I describe my experiences?",                  "notes", "text", "not_applicable", [], 470),
    _q("medication_notes",       "Have there been any medication changes? If so, what?",  "notes", "text", "not_applicable", [], 480),
]

# ── CATALOG LOOKUPS (module-level, built once) ────────────
_CATALOG_BY_TEXT: dict[str, dict] = {q["text"]: q for q in QUESTION_CATALOG}
_CATALOG_BY_CODE: dict[str, dict] = {q["code"]: q for q in QUESTION_CATALOG}

@st.cache_data
def catalog_df() -> pd.DataFrame:
    return pd.DataFrame(QUESTION_CATALOG).sort_values("order").reset_index(drop=True)

# ── DOMAIN WEIGHT MULTIPLIERS ─────────────────────────────
DOMAIN_WEIGHT_MULTIPLIERS: dict[str, dict[str, float]] = {
    "Depression": {"func_sleep_hours": 0.35, "func_sleep_quality": 0.45},
    "Mania":      {"func_sleep_hours": 1.0,  "func_sleep_quality": 1.0},
    "Mixed":      {"func_sleep_hours": 1.0,  "func_sleep_quality": 1.0},
    "Psychosis":  {},
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
    "meta_disorganised_thoughts": 1.75, "meta_attention_unstable": 1.25,
    "meta_driven_without_thinking": 1.5,
}

FORCE_MULTIPLIER_CODES = [q["code"] for q in QUESTION_CATALOG if q.get("meta_role") == "force_multiplier"]
INSIGHT_INVERSE_CODES  = [q["code"] for q in QUESTION_CATALOG if q.get("meta_role") == "insight_inverse_psychosis"]

PSY_PRIMARY_CODES = ["psy_heard_saw", "psy_suspicious", "psy_trust_perceptions", "psy_distress"]
PSY_INSIGHT_CODES = ["meta_something_wrong", "meta_concerned", "psy_confidence_reality", "psy_trust_perceptions"]

def _effective_weight(code: str, domain: str, base_weights: dict[str, float]) -> float:
    return base_weights.get(code, 0.0) * DOMAIN_WEIGHT_MULTIPLIERS.get(domain, {}).get(code, 1.0)

# ── JOURNAL COMMENTS ──────────────────────────────────────
@st.cache_data(ttl=30)
def load_comments() -> pd.DataFrame:
    ws = safe_worksheet(COMMENTS_TAB)
    if ws is None:
        return pd.DataFrame(columns=["submission_id", "commented_at", "comment_text"])
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame(columns=["submission_id", "commented_at", "comment_text"])
    df = pd.DataFrame(values[1:], columns=[str(h).strip() for h in values[0]])
    return df[df["comment_text"].astype(str).str.strip() != ""].reset_index(drop=True)

def save_comment(submission_id: str, comment_text: str) -> tuple[bool, str]:
    ws = safe_worksheet(COMMENTS_TAB)
    if ws is None:
        return False, f"Worksheet '{COMMENTS_TAB}' not found."
    if not ws.get_all_values():
        ws.append_row(["submission_id", "commented_at", "comment_text"])
    ws.append_row([submission_id, dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), comment_text.strip()])
    load_comments.clear()
    return True, "Comment saved."

def get_comments_for_submission(submission_id: str, comments_df: pd.DataFrame) -> list[dict]:
    if not submission_id.strip() or comments_df.empty or "submission_id" not in comments_df.columns:
        return []
    rows = comments_df[comments_df["submission_id"].astype(str).str.strip() == submission_id.strip()]
    return rows.sort_values("commented_at").to_dict("records") if not rows.empty else []

# ── BASELINE CONFIG ───────────────────────────────────────
@st.cache_data(ttl=60)
def load_baseline_config() -> dict:
    config = {
        "bands": {d: v.copy() for d, v in DEFAULT_BASELINE_BANDS.items()},
        "movement_threshold": DEFAULT_MOVEMENT_THRESHOLD,
        "personal_baseline_window": 90,
    }
    ws = safe_worksheet(BASELINE_TAB)
    if ws is None:
        return config
    try:
        values = ws.get_all_values()
        if len(values) < 2:
            return config
        df = pd.DataFrame(values[1:], columns=values[0])
        if {"domain", "band", "value"}.issubset(df.columns):
            for _, row in df.iterrows():
                d, b = str(row["domain"]).strip(), str(row["band"]).strip()
                v = pd.to_numeric(row["value"], errors="coerce")
                if d in config["bands"] and b in config["bands"][d] and pd.notna(v):
                    config["bands"][d][b] = float(v)
        if {"key", "value"}.issubset(df.columns):
            for _, row in df.iterrows():
                k, v = str(row.get("key","")).strip(), pd.to_numeric(row.get("value"), errors="coerce")
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
        return False, f"Worksheet '{BASELINE_TAB}' not found."
    rows = [["domain", "band", "value", "key"]]
    for domain, bands_inner in config["bands"].items():
        for band, value in bands_inner.items():
            rows.append([domain, band, value, ""])
    rows += [["", "", "", ""],
             ["", "", config["movement_threshold"], "movement_threshold"],
             ["", "", config["personal_baseline_window"], "personal_baseline_window"]]
    ws.clear(); ws.update("A1", rows)
    load_baseline_config.clear()
    return True, "Baseline config saved."

# ── WEIGHTS PERSISTENCE ───────────────────────────────────
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
        v = pd.to_numeric(row.get("weight"), errors="coerce")
        if code in out and pd.notna(v):
            out[code] = float(v)
    return out

def save_weights(weights: dict[str, float]) -> tuple[bool, str]:
    ws = safe_worksheet(SETTINGS_TAB)
    if ws is None:
        return False, f"Worksheet '{SETTINGS_TAB}' not found."
    rows = [["question_code", "weight"]] + [[k, v] for k, v in weights.items()]
    ws.clear(); ws.update("A1", rows)
    load_weights.clear()
    return True, "Weights saved."

# ── RAW DATA PROCESSING ───────────────────────────────────
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
    if "review" in st_val:   return SUBMISSION_TYPE_REVIEW
    if "snapshot" in st_val: return SUBMISSION_TYPE_SNAPSHOT
    sleep = row.get("func_sleep_hours")
    if sleep is not None and not (isinstance(sleep, float) and np.isnan(sleep)):
        try:
            if pd.notna(pd.to_numeric(sleep, errors="coerce")):
                return SUBMISSION_TYPE_REVIEW
        except Exception:
            pass
    return SUBMISSION_TYPE_SNAPSHOT

def clean_and_widen(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    w = df.copy()
    base_cols = ["submission_id", "submitted_at", "submitted_date",
                 "submission_order_in_day", "is_first_of_day"]
    wide = w[base_cols].copy()
    for text, meta in _CATALOG_BY_TEXT.items():
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

# ── SCORING ───────────────────────────────────────────────
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

def _normalise_meta_item(raw_value: Any) -> float:
    v = pd.to_numeric(raw_value, errors="coerce")
    return 0.0 if pd.isna(v) else float(min(max((v - 1.0) / 4.0 * 100.0, 0.0), 100.0))

def compute_meta_multiplier(row: pd.Series) -> float:
    scores = [_normalise_meta_item(row[c]) for c in FORCE_MULTIPLIER_CODES if c in row.index]
    if not scores:
        return 1.0
    return 1.0 + (float(np.mean(scores)) / 100.0) * (META_MULTIPLIER_MAX - 1.0)

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

    # Normalise all scoreable questions into a working frame
    norm_frame = src.copy()
    for code, meta in _CATALOG_BY_CODE.items():
        if code in src.columns and meta["rtype"] != "text":
            norm_frame[code] = _normalise(src[code], meta)

    for domain in DOMAINS:
        src[f"{domain} Score % (raw)"] = _domain_score(norm_frame, domain, weights, snapshot=not daily_only)

    src["meta_multiplier"] = src.apply(compute_meta_multiplier, axis=1)
    for domain in DOMAINS:
        src[f"{domain} Score %"] = (src[f"{domain} Score % (raw)"] * src["meta_multiplier"]).clip(upper=100.0)
    src["Overall Score %"] = src[[f"{d} Score %" for d in DOMAINS]].mean(axis=1)

    if daily_only:
        src = src.rename(columns={"submitted_date": "date"})
        for col in [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]:
            src[f"{col} Delta"] = src[col].diff()
            src[f"{col} 7d Avg"] = src[col].rolling(7, min_periods=1).mean()

    return src.reset_index(drop=True)

# ── DAILY AGGREGATE ───────────────────────────────────────
def build_daily_aggregate(wide: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    if wide.empty:
        return pd.DataFrame()

    scored_all = build_scored_table(wide, weights, daily_only=False)

    if "submission_type_derived" in wide.columns:
        type_map = wide.set_index("submission_id")["submission_type_derived"].to_dict()
        scored_all["submission_type_derived"] = scored_all["submission_id"].map(type_map).fillna(SUBMISSION_TYPE_SNAPSHOT)
    else:
        scored_all["submission_type_derived"] = SUBMISSION_TYPE_SNAPSHOT

    if "submitted_date" not in scored_all.columns and "submitted_date" in wide.columns:
        date_map = wide.set_index("submission_id")["submitted_date"].to_dict()
        scored_all["submitted_date"] = scored_all["submission_id"].map(date_map)

    scored_all["_sw"] = scored_all["submission_type_derived"].map(
        {SUBMISSION_TYPE_SNAPSHOT: SNAPSHOT_WEIGHT, SUBMISSION_TYPE_REVIEW: REVIEW_WEIGHT}
    ).fillna(SNAPSHOT_WEIGHT)

    agg_rows: list[dict] = []
    for date, group in scored_all.groupby("submitted_date"):
        row: dict = {"date": date}
        row["n_snapshots"] = int((group["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT).sum())
        row["n_reviews"]   = int((group["submission_type_derived"] == SUBMISSION_TYPE_REVIEW).sum())
        row["n_total"]     = len(group)
        weights_arr = group["_sw"].values.astype(float)

        for domain in DOMAINS:
            for suffix in ("Score %", "Score % (raw)"):
                col = f"{domain} {suffix}"
                if col in group.columns:
                    row[col] = float(np.average(group[col].fillna(0), weights=weights_arr))
        row["Overall Score %"] = float(np.mean([row.get(f"{d} Score %", 0) for d in DOMAINS]))
        if "meta_multiplier" in group.columns:
            row["meta_multiplier"] = float(np.average(group["meta_multiplier"].fillna(1.0), weights=weights_arr))

        for code, meta in _CATALOG_BY_CODE.items():
            if code not in wide.columns:
                continue
            raw_vals = wide[wide["submitted_date"] == date][[code, "submission_type_derived"]].copy()
            if raw_vals.empty:
                continue
            if meta["rtype"] == "boolean_yes_no":
                row[code] = bool(raw_vals[code].any())
            elif code in ("func_sleep_hours", "func_sleep_quality"):
                review_vals = raw_vals[raw_vals["submission_type_derived"] == SUBMISSION_TYPE_REVIEW][code].dropna()
                all_vals    = raw_vals[code].dropna()
                row[code] = float(review_vals.mean()) if not review_vals.empty else (float(all_vals.mean()) if not all_vals.empty else np.nan)
            elif meta["rtype"] in ("scale_1_5", "numeric"):
                rv = raw_vals.copy()
                rv["_w"] = rv["submission_type_derived"].map(
                    {SUBMISSION_TYPE_SNAPSHOT: SNAPSHOT_WEIGHT, SUBMISSION_TYPE_REVIEW: REVIEW_WEIGHT}
                ).fillna(SNAPSHOT_WEIGHT)
                rv = rv.dropna(subset=[code])
                if not rv.empty:
                    row[code] = float(np.average(pd.to_numeric(rv[code], errors="coerce").fillna(0), weights=rv["_w"]))
            elif meta["rtype"] == "text":
                for stype in (SUBMISSION_TYPE_REVIEW, SUBMISSION_TYPE_SNAPSHOT):
                    t = raw_vals[raw_vals["submission_type_derived"] == stype][code]
                    t = t[t.notna() & (t.astype(str).str.strip() != "")]
                    if not t.empty:
                        row[code] = str(t.iloc[-1]); break
                else:
                    row[code] = ""

        row["submitted_at"] = group["submitted_at"].max()
        row["has_review"]   = row["n_reviews"] > 0
        row["has_snapshot"] = row["n_snapshots"] > 0
        agg_rows.append(row)

    if not agg_rows:
        return pd.DataFrame()
    daily = pd.DataFrame(agg_rows).sort_values("date").reset_index(drop=True)
    for col in [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]:
        if col in daily.columns:
            daily[f"{col} Delta"]  = daily[col].diff()
            daily[f"{col} 7d Avg"] = daily[col].rolling(7, min_periods=1).mean()
    return daily

# ── SNAPSHOT COMPONENTS ───────────────────────────────────
def get_snapshot_components(row: pd.Series, domain: str, weights: dict[str, float]) -> pd.DataFrame:
    items = [q for q in QUESTION_CATALOG
             if domain in q["domains"] and q["code"] in row.index
             and q.get("score_in_snapshot", True)
             and _effective_weight(q["code"], domain, weights) > 0]
    if not items:
        return pd.DataFrame()
    multiplier = compute_meta_multiplier(row)
    rows = []
    for q in items:
        code = q["code"]
        norm_score = float(_normalise(pd.Series([row.get(code)]), q).iloc[0])
        inverted = domain == "Psychosis" and code in INSIGHT_INVERSE_CODES
        display_score = 100.0 - norm_score if inverted else norm_score
        ew = _effective_weight(code, domain, weights)
        label = re.sub(r"^(Have I |Do I |Am I |Is my |I've been |I noticed |I |There were |I had a )", "", q["text"])
        label = (label[:45] + "…" if len(label) > 45 else label) + (" ⟳" if inverted else "")
        rows.append(dict(code=code, label=label, norm_score=round(display_score, 1),
                         weight=round(ew, 2), contribution=round(display_score * ew, 1),
                         group=q["group"], inverted=inverted))
    df = pd.DataFrame(rows)
    total_w = df["weight"].sum()
    df["weighted_pct"] = (df["weight"] / total_w * 100).round(1) if total_w else 0
    df["multiplier"] = round(multiplier, 3)
    df["score_after_multiplier"] = (df["norm_score"] * multiplier).clip(upper=100).round(1)
    return df.sort_values("contribution", ascending=False)

# ── BAND CLASSIFICATION ───────────────────────────────────
def classify_score(score: float, domain: str, bands: dict) -> str:
    if score is None or (isinstance(score, float) and np.isnan(score)):
        return "unknown"
    b = bands.get(domain, DEFAULT_BASELINE_BANDS.get(domain, {}))
    if score <= b.get("well",    20): return "well"
    if score <= b.get("watch",   40): return "watch"
    if score <= b.get("caution", 60): return "caution"
    if score <= b.get("warning", 75): return "warning"
    return "critical"

# ── PERSONAL BASELINE ─────────────────────────────────────
def compute_personal_baseline(daily: pd.DataFrame, bands: dict,
                               window_days: int = 90,
                               episodes: pd.DataFrame | None = None) -> dict[str, dict]:
    empty = dict(mean=None, sd=None, n=0, lower=None, upper=None, reliable=False)
    if daily.empty:
        return {d: empty.copy() for d in DOMAINS}
    working = daily[daily.get("has_snapshot", pd.Series(True, index=daily.index))].copy() if "has_snapshot" in daily.columns else daily.copy()
    mask = pd.Series(True, index=working.index)
    for domain in DOMAINS:
        col = f"{domain} Score %"
        if col in working.columns:
            mask &= working[col].fillna(999) <= bands.get(domain, {}).get("well", 20.0)
    if episodes is not None and not episodes.empty:
        ep_mask = pd.Series(False, index=working.index)
        for _, ep in episodes.iterrows():
            try:
                ep_mask |= (working["date"] >= pd.Timestamp(ep["start_date"]).date()) & \
                            (working["date"] <= pd.Timestamp(ep["end_date"]).date())
            except Exception:
                pass
        mask &= ~ep_mask
    well_days = working[mask].sort_values("date").tail(window_days)
    result: dict[str, dict] = {}
    for domain in DOMAINS:
        col = f"{domain} Score %"
        if col not in well_days.columns or well_days.empty:
            result[domain] = empty.copy(); continue
        scores = well_days[col].dropna()
        n = len(scores)
        if n == 0:
            result[domain] = empty.copy(); continue
        mean = float(scores.mean())
        sd   = float(scores.std()) if n > 1 else 0.0
        result[domain] = dict(mean=round(mean, 1), sd=round(sd, 2), n=n,
                               lower=round(mean - sd, 1), upper=round(mean + sd, 1),
                               reliable=n >= PERSONAL_BASELINE_MIN_DAYS)
    return result

# ── NOTES / JOURNAL ───────────────────────────────────────
_STOP_WORDS = {
    "i","a","an","the","and","or","but","of","to","in","is","it","my","me","was","been",
    "have","has","had","that","this","with","for","on","are","be","at","not","felt","feel",
    "feeling","just","like","so","bit","very","quite","pretty","really","some","more","less",
    "day","today","yesterday","week","night",
}

def extract_keywords(text: str, top_n: int = 8) -> list[str]:
    if not text or not isinstance(text, str):
        return []
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    return [w for w, _ in Counter(w for w in words if w not in _STOP_WORDS).most_common(top_n)]

def build_notes_df(wide: pd.DataFrame, daily_scored: pd.DataFrame, bands: dict) -> pd.DataFrame:
    if wide.empty or "experience_description" not in wide.columns:
        return pd.DataFrame()
    notes = wide[wide["experience_description"].notna() &
                 (wide["experience_description"].astype(str).str.strip() != "")].copy()
    notes = notes[["submission_id","submitted_at","submitted_date","experience_description"]].copy()
    notes["date"] = notes["submitted_date"]
    if not daily_scored.empty:
        score_cols = [f"{d} Score %" for d in DOMAINS]
        notes = notes.merge(daily_scored[["date"] + [c for c in score_cols if c in daily_scored.columns]], on="date", how="left")

    def _worst_band(row):
        order = ["critical","warning","caution","watch","well","unknown"]
        day_bands = [classify_score(row.get(f"{d} Score %", 0), d, bands) for d in DOMAINS]
        return next((b for b in order if b in day_bands), "unknown")

    notes["worst_band"] = notes.apply(_worst_band, axis=1)
    notes["keywords"]   = notes["experience_description"].apply(extract_keywords)
    return notes.sort_values("submitted_at", ascending=False).reset_index(drop=True)

def keyword_frequency_chart(notes_df: pd.DataFrame, top_n: int = 20) -> go.Figure:
    all_kw = [kw for kws in notes_df["keywords"] for kw in kws]
    if not all_kw:
        return go.Figure()
    counts = Counter(all_kw).most_common(top_n)
    words, freqs = zip(*counts)
    fig = go.Figure(go.Bar(x=freqs, y=words, orientation="h", marker_color="#1C7EF2",
                           hovertemplate="%{y}: %{x} mentions<extra></extra>"))
    fig.update_layout(height=max(300, top_n * 22), margin=dict(l=10,r=10,t=10,b=10),
                      yaxis=dict(autorange="reversed"), xaxis=dict(title="Frequency"),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig

def build_med_notes_df(wide: pd.DataFrame, daily_scored: pd.DataFrame) -> pd.DataFrame:
    if wide.empty or "medication_notes" not in wide.columns:
        return pd.DataFrame()
    med = wide[wide["medication_notes"].notna() &
               (wide["medication_notes"].astype(str).str.strip() != "")].copy()
    if med.empty:
        return pd.DataFrame()
    med["date"] = med["submitted_date"]
    med = med[["submitted_at","date","medication_notes"]].copy()
    if not daily_scored.empty:
        score_cols = [f"{d} Score %" for d in DOMAINS]
        med = med.merge(daily_scored[["date"] + [c for c in score_cols if c in daily_scored.columns]], on="date", how="left")
    return med.sort_values("submitted_at", ascending=False).reset_index(drop=True)

# ── EPISODE LOG ───────────────────────────────────────────
EPISODE_COLOURS = {ep: _hex_to_rgba(EPISODE_LINE_COLOURS[ep], 0.15 if ep != "Manic" else 0.20)
                   for ep in EPISODE_TYPES}

@st.cache_data(ttl=30)
def load_episodes() -> pd.DataFrame:
    ws = safe_worksheet(EPISODE_TAB)
    empty = pd.DataFrame(columns=["episode_id","episode_type","start_date","end_date","notes"])
    if ws is None:
        return empty
    try:
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return empty
        df = pd.DataFrame(values[1:], columns=values[0])
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date
        df["end_date"]   = pd.to_datetime(df["end_date"],   errors="coerce").dt.date
        return df.dropna(subset=["start_date","end_date"]).reset_index(drop=True)
    except Exception:
        return empty

def _save_episodes(episodes: pd.DataFrame) -> tuple[bool, str]:
    ws = safe_worksheet(EPISODE_TAB)
    if ws is None:
        return False, f"Worksheet '{EPISODE_TAB}' not found."
    rows = [["episode_id","episode_type","start_date","end_date","notes"]]
    rows += [[str(row.get(c,"")) for c in ["episode_id","episode_type","start_date","end_date","notes"]]
             for _, row in episodes.iterrows()]
    ws.clear(); ws.update("A1", rows)
    load_episodes.clear()
    return True, "Episode log saved."

def add_episode(episode_type: str, start_date, end_date, notes: str) -> tuple[bool, str]:
    episodes = load_episodes()
    episode_id = hashlib.md5(f"{episode_type}{start_date}{end_date}{notes}".encode()).hexdigest()[:8]
    new_row = pd.DataFrame([{"episode_id": episode_id, "episode_type": episode_type,
                              "start_date": start_date, "end_date": end_date, "notes": notes}])
    return _save_episodes(pd.concat([episodes, new_row], ignore_index=True))

def delete_episode(episode_id: str) -> tuple[bool, str]:
    return _save_episodes(load_episodes()[load_episodes()["episode_id"] != episode_id].reset_index(drop=True))

def add_episode_overlays(fig: go.Figure, episodes: pd.DataFrame) -> go.Figure:
    if episodes is None or episodes.empty:
        return fig
    for _, ep in episodes.iterrows():
        ep_type = str(ep.get("episode_type", "Other"))
        notes   = str(ep.get("notes",""))
        label   = ep_type + (f": {notes[:30]}…" if len(notes) > 30 else (f": {notes}" if notes else ""))
        fig.add_vrect(x0=str(ep["start_date"]), x1=str(ep["end_date"]),
                      fillcolor=EPISODE_COLOURS.get(ep_type, EPISODE_COLOURS["Other"]),
                      line_width=1, line_color=EPISODE_LINE_COLOURS.get(ep_type, "#8E8E93"),
                      annotation_text=label, annotation_position="top left",
                      annotation_font_size=9,
                      annotation_font_color=EPISODE_LINE_COLOURS.get(ep_type, "#8E8E93"))
    return fig

# ── MEDICATION LOG ────────────────────────────────────────
@st.cache_data(ttl=30)
def load_med_log() -> pd.DataFrame:
    ws = safe_worksheet(MED_LOG_TAB)
    cols = ["med_id","date","medication","dose","dose_unit","frequency","change_type","notes"]
    empty = pd.DataFrame(columns=cols)
    if ws is None:
        return empty
    try:
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return empty
        df = pd.DataFrame(values[1:], columns=values[0])
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df["dose"] = pd.to_numeric(df["dose"], errors="coerce")
        return df.dropna(subset=["date"]).sort_values("date", ascending=False).reset_index(drop=True)
    except Exception:
        return empty

def _save_med_log(df: pd.DataFrame) -> tuple[bool, str]:
    ws = safe_worksheet(MED_LOG_TAB)
    if ws is None:
        return False, f"Worksheet '{MED_LOG_TAB}' not found."
    cols = ["med_id","date","medication","dose","dose_unit","frequency","change_type","notes"]
    rows = [cols] + [[str(row.get(c,"")) for c in cols] for _, row in df.iterrows()]
    ws.clear(); ws.update("A1", rows)
    load_med_log.clear()
    return True, "Medication log saved."

def add_med_event(date, medication: str, dose: float, dose_unit: str,
                  frequency: str, change_type: str, notes: str) -> tuple[bool, str]:
    existing = load_med_log()
    med_id = hashlib.md5(f"{date}{medication}{dose}{change_type}".encode()).hexdigest()[:8]
    new_row = pd.DataFrame([{"med_id": med_id, "date": date, "medication": medication.strip(),
                              "dose": dose, "dose_unit": dose_unit, "frequency": frequency,
                              "change_type": change_type, "notes": notes.strip()}])
    ok, msg = _save_med_log(pd.concat([existing, new_row], ignore_index=True))
    if ok:
        load_med_log.clear()
    return ok, msg

def delete_med_event(med_id: str) -> tuple[bool, str]:
    return _save_med_log(load_med_log()[load_med_log()["med_id"] != med_id].reset_index(drop=True))

def get_current_medications(med_log: pd.DataFrame) -> pd.DataFrame:
    if med_log.empty:
        return pd.DataFrame()
    latest = med_log.sort_values("date", ascending=False).groupby("medication", as_index=False).first()
    return latest[latest["change_type"] != "Stopped"].sort_values("medication")

# ── CHART HELPERS ─────────────────────────────────────────
def _vline(fig: go.Figure, x: str, label: str,
           line_color: str = "rgba(0,150,100,0.6)", dash: str = "dash",
           width: float = 1.5, font_color: str = "rgba(0,150,100,1)", font_size: int = 8) -> go.Figure:
    fig.add_shape(type="line", xref="x", yref="paper", x0=x, x1=x, y0=0, y1=1,
                  line=dict(color=line_color, width=width, dash=dash))
    fig.add_annotation(x=x, yref="paper", y=1.0, text=label, showarrow=False,
                       font=dict(size=font_size, color=font_color),
                       xanchor="left", yanchor="bottom", bgcolor="rgba(255,255,255,0.7)")
    return fig

def _base_layout(height: int, **extra) -> dict:
    return dict(height=height, margin=dict(l=10, r=10, t=10, b=10),
                plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
                xaxis=dict(title=None), **extra)

def add_med_log_overlays(fig: go.Figure, med_log: pd.DataFrame) -> go.Figure:
    if med_log is None or med_log.empty:
        return fig
    for _, row in med_log.iterrows():
        dose_str = f"{row['dose']}{row['dose_unit']}" if pd.notna(row.get("dose")) else ""
        fig = _vline(fig, str(row["date"]),
                     f"💊 {row['medication']} {dose_str} ({row['change_type']})",
                     line_color="rgba(100,100,200,0.6)")
    return fig

def make_band_chart(daily: pd.DataFrame, domain: str, bands: dict,
                    personal: dict | None = None,
                    movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD,
                    show_rolling: bool = True,
                    episodes: pd.DataFrame | None = None,
                    med_notes: pd.DataFrame | None = None,
                    height: int = 320) -> go.Figure:
    col = f"{domain} Score %"
    if col not in daily.columns or daily.empty:
        return go.Figure()
    dates  = daily["date"].astype(str).tolist()
    scores = daily[col].tolist()
    b = bands.get(domain, DEFAULT_BASELINE_BANDS.get(domain, {}))
    well_c, watch_c = b.get("well", 20), b.get("watch", 40)
    caution_c, warning_c = b.get("caution", 60), b.get("warning", 75)
    fig = go.Figure()

    for label, y0, y1 in [("Well",0,well_c),("Watch",well_c,watch_c),
                           ("Caution",watch_c,caution_c),("Warning",caution_c,warning_c),("Critical",warning_c,100)]:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=BAND_COLOURS.get(label.lower(),"rgba(0,0,0,0.05)"),
                      line_width=0, annotation_text=label, annotation_position="right",
                      annotation_font_size=10,
                      annotation_font_color=BAND_COLOUR_HEX.get(label.lower(), "#888"))
    for label, ceil in [("well",well_c),("watch",watch_c),("caution",caution_c),("warning",warning_c)]:
        fig.add_hline(y=ceil, line_dash="dot", line_color=BAND_LINE_COLOURS[label], line_width=1)

    if personal:
        pb = personal.get(domain, {})
        if pb.get("reliable") and pb.get("mean") is not None:
            fig.add_hline(y=pb["mean"], line_dash="solid", line_color="rgba(90,130,230,0.8)",
                          line_width=1.5, annotation_text=f"Your baseline ({pb['n']}d)",
                          annotation_position="left", annotation_font_size=10,
                          annotation_font_color="rgba(90,130,230,1)")
            if pb.get("lower") is not None:
                fig.add_hrect(y0=pb["lower"], y1=pb["upper"],
                              fillcolor="rgba(90,130,230,0.08)",
                              line=dict(color="rgba(90,130,230,0.3)", width=1, dash="dot"),
                              annotation_text="+/-1 SD", annotation_position="left",
                              annotation_font_size=9)

    if show_rolling:
        avg_col = f"{col} 7d Avg"
        if avg_col in daily.columns:
            fig.add_trace(go.Scatter(x=dates, y=daily[avg_col].tolist(), mode="lines",
                                     name="7d avg", line=dict(color="rgba(100,100,100,0.5)", width=1.5, dash="dash"),
                                     hovertemplate="7d avg: %{y:.1f}%<extra></extra>"))

    colour = DOMAIN_COLOURS.get(domain, "#1C7EF2")
    fig.add_trace(go.Scatter(x=dates, y=scores, mode="lines+markers", name=domain,
                             line=dict(color=colour, width=2), marker=dict(size=5, color=colour),
                             hovertemplate="%{x}<br>Score: %{y:.1f}%<extra></extra>"))

    delta_col = f"{col} Delta"
    deltas = daily[delta_col].tolist() if delta_col in daily.columns else [0.0] * len(scores)
    alert_x = [dates[i] for i, (s, d) in enumerate(zip(scores, deltas))
                if d is not None and not (isinstance(d, float) and np.isnan(d))
                and abs(d) >= movement_threshold
                and s is not None and not (isinstance(s, float) and np.isnan(s))
                and s <= well_c]
    alert_y = [scores[dates.index(x)] for x in alert_x]
    if alert_x:
        fig.add_trace(go.Scatter(x=alert_x, y=alert_y, mode="markers", name="Movement",
                                 marker=dict(symbol="triangle-up", size=12, color="#FF9500",
                                             line=dict(color="white", width=1)),
                                 hovertemplate="%{x}<br>%{y:.1f}% — notable movement<extra></extra>"))

    fig = add_episode_overlays(fig, episodes)
    if med_notes is not None and not med_notes.empty:
        for _, m in med_notes.iterrows():
            fig = _vline(fig, str(m["date"]), f"💊 {str(m.get('medication_notes',''))[:40]}")

    fig.update_layout(height=height, margin=dict(l=10, r=90, t=30, b=10),
                      yaxis=dict(range=[0,100], title="Score %", ticksuffix="%"),
                      xaxis=dict(title=None), showlegend=False,
                      plot_bgcolor="white", paper_bgcolor="white",
                      title=dict(text=domain, font=dict(size=14, color="#1C1C1E"), x=0))
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
        fig.add_trace(go.Scatter(x=dates, y=daily[col].tolist(), mode="lines", name=d,
                                 line=dict(color=DOMAIN_COLOURS[d], width=2),
                                 hovertemplate=f"{d}: %{{y:.1f}}%<extra></extra>"))
    for d in DOMAINS:
        fig.add_hline(y=bands.get(d, DEFAULT_BASELINE_BANDS.get(d, {})).get("well", 20),
                      line_dash="dot", line_color="rgba(52,199,89,0.4)", line_width=1)
    fig.update_layout(height=height, margin=dict(l=10,r=10,t=10,b=10),
                      yaxis=dict(range=[0,100], title="Score %", ticksuffix="%"),
                      xaxis=dict(title=None),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig

def make_component_bar(components: pd.DataFrame, domain: str, height: int = 360) -> go.Figure:
    if components.empty:
        return go.Figure()
    colour = DOMAIN_COLOURS.get(domain, "#1C7EF2")
    r, g, b_ch = int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)
    fig = go.Figure(go.Bar(
        x=components["norm_score"], y=components["label"], orientation="h",
        marker_color=[f"rgba({r},{g},{b_ch},{0.3 + 0.7 * s/100})" for s in components["norm_score"]],
        customdata=components[["weight","weighted_pct"]].values,
        hovertemplate="<b>%{y}</b><br>Score: %{x:.0f}%<br>Weight: %{customdata[0]:.2f} (%{customdata[1]:.0f}% of domain)<extra></extra>",
    ))
    fig.add_vline(x=50, line_dash="dot", line_color="rgba(0,0,0,0.2)", line_width=1)
    fig.update_layout(height=height, margin=dict(l=10,r=20,t=10,b=10),
                      xaxis=dict(range=[0,100], title="Normalised score (0–100)", ticksuffix="%"),
                      yaxis=dict(autorange="reversed", title=None),
                      plot_bgcolor="white", paper_bgcolor="white", font=dict(size=11))
    return fig

def make_component_radar(components_by_domain: dict[str, pd.DataFrame], height: int = 420) -> go.Figure:
    fig = go.Figure()
    for domain, comp in components_by_domain.items():
        if comp.empty:
            continue
        top = comp.head(6)
        categories = top["label"].tolist() + [top["label"].iloc[0]]
        values     = top["norm_score"].tolist() + [top["norm_score"].iloc[0]]
        colour = DOMAIN_COLOURS.get(domain, "#888888")
        fig.add_trace(go.Scatterpolar(r=values, theta=categories, fill="toself", name=domain,
                                      line=dict(color=colour, width=2),
                                      fillcolor=_hex_to_rgba(colour, 0.15), opacity=0.9))
    fig.update_layout(height=height, polar=dict(radialaxis=dict(visible=True, range=[0,100])),
                      showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
                      margin=dict(l=40,r=40,t=40,b=60), paper_bgcolor="white", font=dict(size=11))
    return fig

def make_snapshot_timeline(snapshots: pd.DataFrame, bands: dict, height: int = 280) -> go.Figure:
    if snapshots.empty:
        return go.Figure()
    fig = go.Figure()
    for d in DOMAINS:
        col = f"{d} Score %"
        if col not in snapshots.columns:
            continue
        fig.add_trace(go.Scatter(x=snapshots["submitted_at"].astype(str).tolist(),
                                 y=snapshots[col].tolist(), mode="lines+markers", name=d,
                                 line=dict(color=DOMAIN_COLOURS[d], width=1.5), marker=dict(size=4),
                                 hovertemplate=f"{d}: %{{y:.1f}}%<extra></extra>"))
    fig.update_layout(height=height, margin=dict(l=10,r=10,t=10,b=10),
                      yaxis=dict(range=[0,100], title="Score %", ticksuffix="%"),
                      xaxis=dict(title=None),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig

# ── WARNINGS ──────────────────────────────────────────────
def build_warnings(daily: pd.DataFrame, snapshots: pd.DataFrame, bands: dict,
                   movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD) -> pd.DataFrame:
    rows: list[dict] = []

    def _check_row(row: pd.Series, source: str) -> None:
        scores = {d: float(row.get(f"{d} Score %", 0) or 0) for d in DOMAINS}
        deltas = {d: float(row.get(f"{d} Score % Delta", 0) or 0) for d in DOMAINS}
        domain_bands = {d: classify_score(scores[d], d, bands) for d in DOMAINS}
        mixed_elevated = domain_bands["Mixed"] in ("caution", "warning", "critical")

        for domain in DOMAINS:
            score, delta, band = scores[domain], deltas[domain], domain_bands[domain]
            suppress = mixed_elevated and domain in ("Depression","Mania") and band in ("caution","warning","critical")
            if band in ("warning","critical"):
                rows.append(dict(source=source, domain=domain, severity="High",
                                 score_pct=round(score,1), delta=round(delta,1), band=band,
                                 suppressed=suppress, message=f"{domain} score {score:.1f}% — {band} band"))
            elif band == "caution":
                rows.append(dict(source=source, domain=domain, severity="Medium",
                                 score_pct=round(score,1), delta=round(delta,1), band=band,
                                 suppressed=suppress, message=f"{domain} score {score:.1f}% — caution band"))
            if band == "well" and abs(delta) >= movement_threshold:
                rows.append(dict(source=source, domain=domain, severity="Movement",
                                 score_pct=round(score,1), delta=round(delta,1), band=band,
                                 suppressed=False, message=f"{domain} moved {delta:+.1f}pp (still in well band)"))

    if not daily.empty:
        _check_row(daily.sort_values("date").iloc[-1], "Daily")
    if not snapshots.empty:
        _check_row(snapshots.sort_values("submitted_at").iloc[-1], "Snapshot")

    if not rows:
        return pd.DataFrame(columns=["source","domain","severity","score_pct","delta","band","suppressed","message"])
    sev_order = {"High": 0, "Medium": 1, "Movement": 2}
    df = pd.DataFrame(rows)
    df["_o"] = df["severity"].map(sev_order).fillna(9)
    return df.sort_values(["suppressed","_o"]).drop(columns=["_o"]).reset_index(drop=True)

# ── ANALYSIS HELPERS ──────────────────────────────────────
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
    w = np.arange(1, len(recent) + 1, dtype=float); w /= w.sum()
    return {d: float(np.dot(recent[f"{d} Score %"].fillna(0).values, w)) for d in DOMAINS}

def _consecutive_days_in_band(daily: pd.DataFrame, domain: str, bands: dict, target_bands: list[str]) -> int:
    col = f"{domain} Score %"
    if daily.empty or col not in daily.columns:
        return 0
    count = 0
    for score in daily.sort_values("date", ascending=False)[col]:
        if classify_score(score, domain, bands) in target_bands:
            count += 1
        else:
            break
    return count

def _peak_symptom_items(daily: pd.DataFrame, domain: str, top_n: int = 5) -> pd.DataFrame:
    codes = [q["code"] for q in QUESTION_CATALOG if domain in q["domains"] and q["code"] in daily.columns]
    if not codes or daily.empty:
        return pd.DataFrame()
    means = {c: daily[c].mean() for c in codes if pd.api.types.is_numeric_dtype(daily[c])}
    return (pd.Series(means, name="mean_raw").reset_index().rename(columns={"index":"code"})
              .assign(question=lambda df: df["code"].map(lambda c: _CATALOG_BY_CODE.get(c, {}).get("text", c)))
              .sort_values("mean_raw", ascending=False).head(top_n))

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
        for domain in DOMAINS:
            col = f"{domain} Score %"
            if col not in daily.columns:
                continue
            rows.append(dict(flag=flag, domain=domain,
                             mean_when_flagged    =daily[daily[flag] == True][col].mean(),
                             mean_when_not_flagged=daily[daily[flag] == False][col].mean()))
    df = pd.DataFrame(rows).dropna()
    df["impact"] = df["mean_when_flagged"] - df["mean_when_not_flagged"]
    return df.sort_values("impact", ascending=False).reset_index(drop=True)

# ── PSYCHOSIS INSIGHT DIVERGENCE ──────────────────────────
def _mean_normalised(row: pd.Series, codes: list[str], invert: bool = False) -> float | None:
    scores = []
    for code in codes:
        if code not in row.index:
            continue
        v = pd.to_numeric(row[code], errors="coerce")
        if pd.isna(v):
            continue
        norm = float(min(max((v - 1.0) / 4.0 * 100.0, 0.0), 100.0))
        scores.append(100.0 - norm if invert else norm)
    return float(np.mean(scores)) if scores else None

def detect_psychosis_insight_divergence(daily: pd.DataFrame, window: int = 7,
                                         drop_threshold: float = 15.0,
                                         divergence_threshold: float = 12.0) -> dict:
    result = dict(status="insufficient_data", primary_delta=None, insight_delta=None,
                  finding="Not enough data to assess psychosis insight divergence.",
                  severity="ok", days_analysed=0)
    if daily.empty or len(daily) < 3:
        return result

    recent = daily.sort_values("date").tail(window).copy()
    result["days_analysed"] = n = len(recent)

    primary_scores = recent.apply(lambda r: _mean_normalised(r, PSY_PRIMARY_CODES), axis=1).dropna()

    def _composite_insight(row: pd.Series) -> float | None:
        meta = _mean_normalised(row, ["meta_something_wrong","meta_concerned"])
        psy  = _mean_normalised(row, ["psy_confidence_reality","psy_trust_perceptions"], invert=True)
        if meta is None and psy is None: return None
        if meta is None: return psy
        if psy  is None: return meta
        return (meta + psy) / 2.0

    insight_scores    = recent.apply(_composite_insight, axis=1).dropna()
    confidence_scores = recent.apply(
        lambda r: _mean_normalised(r, ["psy_confidence_reality","psy_trust_perceptions"], invert=True), axis=1
    ).dropna()

    if len(primary_scores) < 2 or len(insight_scores) < 2:
        return result

    def _trend(s: pd.Series) -> float:
        third = max(1, len(s) // 3)
        return float(s.tail(third).mean() - s.head(third).mean())

    primary_delta    = _trend(primary_scores)
    insight_delta    = _trend(insight_scores)
    confidence_delta = _trend(confidence_scores) if len(confidence_scores) >= 2 else 0.0
    result.update(primary_delta=round(primary_delta, 1), insight_delta=round(insight_delta, 1))

    if primary_delta >= -drop_threshold:
        return dict(**result, status="stable", finding="Psychosis scores are not falling. No divergence to assess.", severity="ok")

    insight_stable = abs(insight_delta) < divergence_threshold
    insight_rising = insight_delta > divergence_threshold
    confidence_poor = confidence_delta < -divergence_threshold

    if insight_stable or insight_rising:
        return dict(**result, status="improvement", severity="ok",
                    finding=f"Psychosis scores have fallen (~{abs(primary_delta):.0f}pp over {n} days) "
                            f"and the insight composite is {'holding steady' if insight_stable else 'improving'}. "
                            f"This pattern is consistent with genuine improvement.")
    if not confidence_poor:
        return dict(**result, status="ambiguous", severity="caution",
                    finding=f"Psychosis scores have fallen (~{abs(primary_delta):.0f}pp over {n} days), "
                            f"but the insight composite has also declined (~{abs(insight_delta):.0f}pp). "
                            f"It is unclear whether this reflects genuine improvement or reduced awareness. "
                            f"Worth discussing with your clinician.")
    return dict(**result, status="loss_of_insight", severity="warning",
                finding=f"Psychosis scores have fallen (~{abs(primary_delta):.0f}pp over {n} days), "
                        f"but insight indicators have declined significantly (~{abs(insight_delta):.0f}pp) "
                        f"and confidence in experiences appears to be increasing. This may reflect loss of "
                        f"insight rather than genuine improvement. This warrants prompt clinical review.")

# ── INSIGHTS GENERATOR ────────────────────────────────────
def _generate_insights(daily, risk, trends, bands, personal, movement_threshold) -> list[dict]:
    insights: list[dict] = []

    if not daily.empty and "meta_multiplier" in daily.columns:
        mult = float(daily.sort_values("date").iloc[-1].get("meta_multiplier", 1.0) or 1.0)
        if mult >= 1.20:
            insights.append(dict(level="warning", domain="Meta",
                text=f"**Meta force multiplier is ×{mult:.2f}** — meta questions signal strong intensification or approaching episode. All domain scores are amplified."))
        elif mult >= 1.10:
            insights.append(dict(level="caution", domain="Meta",
                text=f"**Meta force multiplier is ×{mult:.2f}** — mild amplification active."))

    psy_div = detect_psychosis_insight_divergence(daily)
    if psy_div["status"] == "improvement":
        insights.append(dict(level="ok", domain="Psychosis",
            text=f"✓ **Psychosis scores falling with insight intact** — {psy_div['finding']}"))
    elif psy_div["status"] not in ("stable", "insufficient_data"):
        insights.append(dict(level=psy_div["severity"], domain="Psychosis",
            text=f"**Psychosis score interpretation:** {psy_div['finding']}"))

    for domain in DOMAINS:
        r, t = risk.get(domain, 0), trends.get(domain, "stable")
        band  = classify_score(r, domain, bands)
        streak = _consecutive_days_in_band(daily, domain, bands, ["caution","warning","critical"])
        if band in ("warning","critical"):
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
        if pb.get("reliable") and pb.get("upper") is not None and r > pb["upper"] and band == "well":
            insights.append(dict(level="caution", domain=domain,
                text=f"**{domain}** score ({r:.0f}%) is above your personal baseline upper bound ({pb['upper']}%)."))

    if not daily.empty and "dep_self_harm_ideation" in daily.columns:
        peak = daily.tail(7)["dep_self_harm_ideation"].max()
        if pd.notna(peak) and peak > SELF_HARM_FLAG_THRESHOLD:
            insights.append(dict(level="critical", domain="Depression",
                text=f"Self-harm ideation reached **{peak:.0f}/5** in the last 7 days. Please review with your clinician."))

    if not daily.empty and "func_sleep_hours" in daily.columns:
        mean_sleep = daily.tail(7)["func_sleep_hours"].mean()
        if pd.notna(mean_sleep) and mean_sleep < 5.5:
            insights.append(dict(level="caution", domain="General",
                text=f"Mean sleep over the last 7 days is **{mean_sleep:.1f} hours** — below threshold."))

    if not daily.empty:
        for domain in DOMAINS:
            delta_col, score_col = f"{domain} Score % Delta", f"{domain} Score %"
            if delta_col not in daily.columns:
                continue
            latest = daily.sort_values("date").iloc[-1]
            delta, score = latest.get(delta_col, 0) or 0, latest.get(score_col, 0) or 0
            if classify_score(score, domain, bands) == "well" and abs(delta) >= movement_threshold:
                insights.append(dict(level="caution", domain=domain,
                    text=f"**{domain}** moved **{delta:+.1f}pp** since yesterday (still in well band)."))

    if not insights:
        insights.append(dict(level="ok", domain="General",
            text="No alerts. All domain scores are within expected ranges."))
    return insights

# ── CLINICIAN EXPORT ──────────────────────────────────────
def generate_clinician_report(daily, bands, personal_bl, episodes, notes, med_notes,
                               weights, wide, comments=None, med_log=None, window_days=30) -> str:
    today = dt.date.today()
    window_start = today - dt.timedelta(days=window_days)
    L: list[str] = []

    def h(s): L.append(s)
    def nl(): L.append("")

    h("# Bipolar Dashboard — Clinician Summary")
    h(f"**Generated:** {today.strftime('%d %B %Y')}  ")
    h(f"**Period:** Last {window_days} days ({window_start.strftime('%d %b')} – {today.strftime('%d %b %Y')})")
    nl()

    h("## Current Status")
    if not daily.empty:
        latest = daily.sort_values("date").iloc[-1]
        mult   = float(latest.get("meta_multiplier", 1.0) or 1.0)
        h(f"**Latest entry:** {latest['date']}  ")
        h(f"**Submissions that day:** {int(latest.get('n_total',1))} "
          f"({int(latest.get('n_snapshots',0))} snapshot, {int(latest.get('n_reviews',0))} review)")
        h(f"**Meta force multiplier:** ×{mult:.2f}" + (" ⚡ active" if mult > 1.05 else " (baseline)"))
        nl()

        latest_date = latest["date"]
        day_wide = wide[wide["submitted_date"] == latest_date] if not wide.empty else pd.DataFrame()
        snap_rows   = day_wide[day_wide["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT] if not day_wide.empty else pd.DataFrame()
        review_rows = day_wide[day_wide["submission_type_derived"] == SUBMISSION_TYPE_REVIEW]   if not day_wide.empty else pd.DataFrame()

        h("| Domain | Aggregate | Snapshot avg | Review avg | Band | vs Baseline |")
        h("|--------|-----------|-------------|------------|------|-------------|")
        for d in DOMAINS:
            score = float(latest.get(f"{d} Score %", 0) or 0)
            band  = classify_score(score, d, bands)
            pb    = personal_bl.get(d, {})
            vs_bl = f"{score - pb['mean']:+.1f}pp" if pb.get("reliable") and pb.get("mean") is not None else "—"

            def _avg(rows):
                if rows.empty:
                    return "—"
                sc = build_scored_table(rows.assign(is_first_of_day=True, submission_order_in_day=1), weights)
                return f"{sc[f'{d} Score %'].mean():.1f}%" if not sc.empty and f"{d} Score %" in sc.columns else "—"

            h(f"| {d} | {score:.1f}% | {_avg(snap_rows)} | {_avg(review_rows)} | {band.upper()} | {vs_bl} |")
    else:
        h("*No daily data available.*")
    nl()

    h("## Domain Trends (last 30 days)")
    period = daily[daily["date"] >= window_start] if not daily.empty else daily
    if not period.empty:
        h("| Domain | Mean % | Peak % | Days in Well | Days in Watch+ | Days in Warning+ |")
        h("|--------|--------|--------|-------------|----------------|-----------------|")
        for d in DOMAINS:
            col = f"{d} Score %"
            if col not in period.columns:
                continue
            scores = period[col].dropna()
            def _cnt(fn): return int(scores.apply(fn).sum())
            h(f"| {d} | {scores.mean():.1f}% | {scores.max():.1f}% "
              f"| {_cnt(lambda s: classify_score(s,d,bands)=='well')} "
              f"| {_cnt(lambda s: classify_score(s,d,bands) in ['watch','caution','warning','critical'])} "
              f"| {_cnt(lambda s: classify_score(s,d,bands) in ['warning','critical'])} |")
    else:
        h("*No data in this period.*")
    nl()

    h("## Personal Baseline")
    h("*(Computed from days where all domains were in the Well band)*"); nl()
    for d in DOMAINS:
        pb = personal_bl.get(d, {})
        if pb.get("reliable"):
            h(f"- **{d}:** mean {pb['mean']}%, ±1 SD {pb['lower']}–{pb['upper']}% (based on {pb['n']} well days)")
        else:
            h(f"- **{d}:** baseline not yet reliable ({pb.get('n',0)} well days recorded)")
    nl()

    h("## Labelled Episodes")
    if not episodes.empty:
        recent_ep = episodes[pd.to_datetime(episodes["end_date"]) >= pd.Timestamp(window_start)]
        if not recent_ep.empty:
            for _, ep in recent_ep.sort_values("start_date", ascending=False).iterrows():
                h(f"- **{ep['episode_type']}** — {ep['start_date']} to {ep['end_date']}"
                  + (f": {ep['notes']}" if ep.get("notes") else ""))
        else:
            h("*No episodes ending in this period.*")
    else:
        h("*No episodes labelled yet.*")
    nl()

    h("## Medications")
    current_meds = get_current_medications(med_log if med_log is not None and not med_log.empty else pd.DataFrame())
    if not current_meds.empty:
        h("### Currently active")
        for _, m in current_meds.iterrows():
            dose_str = f"{m['dose']:.0f}{m['dose_unit']}" if pd.notna(m.get("dose")) else ""
            h(f"- **{m['medication']}** {dose_str}{f', {m[\"frequency\"]}' if m.get('frequency') else ''} "
              f"(last change: {m['change_type']} on {m['date']})")
        nl()
    if med_log is not None and not med_log.empty:
        recent_log = med_log[med_log["date"] >= window_start]
        if not recent_log.empty:
            h("### Changes in this period")
            for _, m in recent_log.sort_values("date", ascending=False).iterrows():
                dose_str = f"{m['dose']:.0f}{m['dose_unit']}" if pd.notna(m.get("dose")) else ""
                h(f"- **{m['date']}** {m['change_type']}: {m['medication']} {dose_str}"
                  + (f" — {m['notes']}" if m.get("notes") else ""))
            nl()
    if not med_notes.empty:
        recent_med = med_notes[med_notes["date"] >= window_start]
        if not recent_med.empty:
            h("### Form notes (supplementary)")
            for _, m in recent_med.sort_values("submitted_at", ascending=False).iterrows():
                h(f"- **{m['date']}:** {m['medication_notes']}")
            nl()
    if current_meds.empty and (med_log is None or med_log.empty) and med_notes.empty:
        h("*No medication information recorded.*")
    nl()

    h("## Journal Highlights")
    h("*(Entries from days in Caution band or above)*")
    if not notes.empty:
        elevated = notes[notes["worst_band"].isin(["caution","warning","critical"])]
        recent_notes = elevated[elevated["date"] >= window_start] if not elevated.empty else elevated
        if not recent_notes.empty:
            for _, n in recent_notes.sort_values("submitted_at", ascending=False).head(10).iterrows():
                text = str(n.get("experience_description",""))
                h(f"- **{n['date']}** [{n.get('worst_band','').upper()}]: {text[:300]}"
                  + ("…" if len(text) > 300 else ""))
                if comments is not None and not comments.empty:
                    for c in get_comments_for_submission(str(n.get("submission_id","")), comments):
                        h(f"  - 💬 *Note ({str(c.get('commented_at',''))[:16]}):* {c.get('comment_text','')}")
        else:
            h("*No elevated-band journal entries in this period.*")
    else:
        h("*No journal entries.*")
    nl()

    h("---")
    h("*This summary was generated automatically from self-reported daily monitoring data. "
      "It is intended to support clinical conversation, not to replace clinical judgement.*")
    return "\n".join(L)

# ── SETTINGS RENDERERS ────────────────────────────────────
def render_weights_editor(weights: dict[str, float]) -> dict[str, float]:
    st.markdown("### Scoring weights")
    st.caption("Sleep weights are additionally scaled by domain-specific multipliers "
               "(Depression: ×0.35/×0.45; Mania & Mixed: ×1.0).")
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
                updated[code] = st.number_input(code, min_value=0.0, max_value=10.0, step=0.25,
                                                value=float(updated.get(code, 0.0)), key=f"w_{code}")
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
    st.caption("Upper bound of each band (0–100). Must be ascending: Well < Watch < Caution < Warning.")
    if not safe_worksheet(BASELINE_TAB):
        st.warning(f"Worksheet '{BASELINE_TAB}' not found — changes are in-memory only.")
    updated = {"bands": {d: v.copy() for d, v in config["bands"].items()},
               "movement_threshold": config["movement_threshold"],
               "personal_baseline_window": config["personal_baseline_window"]}
    for domain in DOMAINS:
        with st.expander(domain, expanded=True):
            b, cols = updated["bands"][domain], st.columns(4)
            for i, (key, label) in enumerate([("well","Well"),("watch","Watch"),("caution","Caution"),("warning","Warning")]):
                b[key] = cols[i].number_input(label, 0.0, 100.0, float(b[key]), 0.5, key=f"bl_{domain}_{key}")
            if sorted([b["well"],b["watch"],b["caution"],b["warning"]]) != [b["well"],b["watch"],b["caution"],b["warning"]]:
                st.warning("Ceilings must be in ascending order.")
    st.divider()
    updated["movement_threshold"] = st.number_input("Movement alert threshold (pp)", 1.0, 50.0,
                                                    float(updated["movement_threshold"]), 0.5, key="bl_movement")
    updated["personal_baseline_window"] = st.number_input("Personal baseline window (well days)", 14, 365,
                                                           int(updated["personal_baseline_window"]), 1, key="bl_window")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save baseline config", type="primary"):
            ok, msg = save_baseline_config(updated)
            (st.success if ok else st.error)(msg)
    with c2:
        if st.button("Reset baseline to defaults"):
            default_cfg = {"bands": {d: v.copy() for d, v in DEFAULT_BASELINE_BANDS.items()},
                           "movement_threshold": DEFAULT_MOVEMENT_THRESHOLD, "personal_baseline_window": 90}
            ok, msg = save_baseline_config(default_cfg)
            (st.success if ok else st.error)("Reset." if ok else msg)
    return updated

# ── DATA LOAD ─────────────────────────────────────────────
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
med_log_df   = load_med_log()
comments_df  = load_comments()

# ── GLOBAL FILTERS (sidebar) ──────────────────────────────
with st.sidebar:
    st.markdown("## Filters")
    if "last_refreshed" not in st.session_state:
        st.session_state["last_refreshed"] = dt.datetime.now()
    elapsed = int((dt.datetime.now() - st.session_state["last_refreshed"]).total_seconds())
    st.caption(f"Data last refreshed {elapsed}s ago")
    if st.button("🔄 Refresh data", use_container_width=True):
        for fn in [load_sheet, load_episodes, load_weights, load_baseline_config, load_comments, load_med_log]:
            fn.clear()
        st.session_state["last_refreshed"] = dt.datetime.now()
        st.rerun()
    st.divider()

    if not daily_df.empty:
        min_date, max_date = daily_df["date"].min(), daily_df["date"].max()
        date_range = st.date_input("Date range", value=(min_date, max_date),
                                   min_value=min_date, max_value=max_date, key="filter_dates")
        filter_start, filter_end = (date_range if isinstance(date_range, (list,tuple)) and len(date_range)==2
                                    else (min_date, max_date))
    else:
        filter_start = filter_end = None

    selected_domains = st.multiselect("Domains to show", options=DOMAINS, default=DOMAINS, key="filter_domains")
    show_rolling = st.toggle("Show 7-day rolling average", value=True, key="filter_rolling")
    st.divider()
    st.markdown("#### Chart height")
    chart_height = st.slider("px", 200, 600, 320, 20, key="filter_height")

def _apply_date_filter(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    if df.empty or filter_start is None:
        return df
    return df[(df[date_col] >= filter_start) & (df[date_col] <= filter_end)].copy()

daily_filtered     = _apply_date_filter(daily_df)
snapshots_filtered = _apply_date_filter(snapshots_df, "submitted_date")
notes_filtered     = _apply_date_filter(notes_df, "date") if not notes_df.empty else notes_df

# ── SUMMARY METRICS ───────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total entries",   len(raw_df))
m2.metric("Days tracked",    len(daily_df))
m3.metric("Snapshots",       int(wide_df["submission_type_derived"].eq(SUBMISSION_TYPE_SNAPSHOT).sum())
          if "submission_type_derived" in wide_df.columns else len(snapshots_df))
m4.metric("Active warnings", int(len(warnings_df[
    (warnings_df["severity"] == "High") & (~warnings_df["suppressed"])
])) if not warnings_df.empty and "suppressed" in warnings_df.columns else 0)
if not daily_df.empty:
    lo = float(daily_df["Overall Score %"].iloc[-1])
    pr = float(daily_df["Overall Score %"].iloc[-2]) if len(daily_df) > 1 else lo
    m5.metric("Latest overall score", f"{lo:.1f}%", delta=f"{lo - pr:+.1f}%")
else:
    m5.metric("Latest overall score", "—")

if not daily_df.empty:
    latest = daily_df.sort_values("date").iloc[-1]
    latest_multiplier = float(latest.get("meta_multiplier", 1.0) or 1.0)
    status_cols = st.columns(len(DOMAINS))
    for i, domain in enumerate(DOMAINS):
        score     = float(latest.get(f"{domain} Score %", 0) or 0)
        raw_score = float(latest.get(f"{domain} Score % (raw)", score) or score)
        band      = classify_score(score, domain, bands)
        delta     = float(latest.get(f"{domain} Score % Delta", 0) or 0)
        pb        = personal_bl.get(domain, {})
        streak    = _consecutive_days_in_band(daily_df, domain, bands, ["caution","warning","critical"])
        pb_note   = f"\n*vs baseline: {score - pb['mean']:+.1f}pp*" if pb.get("reliable") and pb.get("mean") else ""
        raw_note  = f"\n*raw: {raw_score:.1f}%*" if latest_multiplier > 1.05 else ""
        status_cols[i].markdown(
            f"**{domain}**  \n"
            f"{BAND_EMOJI[band]} **{band.upper()}** — {score:.1f}%  \n"
            f"Δ {delta:+.1f}pp{raw_note}{pb_note}"
            + (f"\n*{streak}d elevated streak*" if streak >= 2 else "")
        )
    if latest_multiplier > 1.05:
        st.caption(f"⚡ **Meta force multiplier active: ×{latest_multiplier:.2f}** — "
                   f"domain scores are amplified. Raw (pre-multiplier) scores shown in italics above.")

st.divider()

# ── TABS ──────────────────────────────────────────────────
(tab_overview, tab_snapshots_tab, tab_analysis, tab_baseline, tab_journal,
 tab_episodes, tab_medications, tab_export, tab_questions, tab_daily,
 tab_data, tab_settings) = st.tabs([
    "Overview", "Snapshots", "Analysis", "Baselines",
    "Journal", "Episodes", "Medications", "Clinician Export",
    "Questions", "Daily Model", "Data Layer", "Settings"
])

# ── OVERVIEW ──────────────────────────────────────────────
with tab_overview:
    st.markdown("### Alerts")
    if warnings_df.empty:
        st.success("No active alerts.")
    else:
        sev_icon = {"High": "🔴", "Medium": "🟡", "Movement": "🟠"}
        primary    = warnings_df[~warnings_df["suppressed"]] if "suppressed" in warnings_df.columns else warnings_df
        suppressed = warnings_df[warnings_df["suppressed"]]  if "suppressed" in warnings_df.columns else pd.DataFrame()
        if primary.empty:
            st.success("No active primary alerts.")
        else:
            for _, w in primary.iterrows():
                st.markdown(f"{sev_icon.get(w['severity'],'ℹ️')} **{w['domain']}** ({w['source']}) — {w['message']}")
        if not suppressed.empty and not primary[primary["domain"]=="Mixed"].empty:
            parts = [f"{d}: {suppressed[suppressed['domain']==d].iloc[0]['score_pct']:.1f}% ({suppressed[suppressed['domain']==d].iloc[0]['band']})"
                     for d in suppressed["domain"].unique() if not suppressed[suppressed["domain"]==d].empty]
            if parts:
                st.caption(f"ℹ️ Also elevated as expected Mixed components — {', '.join(parts)}. Shown for context; Mixed is the primary alert.")

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
            fig_all.add_trace(go.Scatter(x=dates, y=daily_filtered[col].tolist(), mode="lines", name=d,
                                         line=dict(color=DOMAIN_COLOURS[d], width=2),
                                         hovertemplate=f"{d}: %{{y:.1f}}%<extra></extra>"))
            if show_rolling:
                avg_col = f"{col} 7d Avg"
                if avg_col in daily_filtered.columns:
                    fig_all.add_trace(go.Scatter(x=dates, y=daily_filtered[avg_col].tolist(), mode="lines",
                                                 name=f"{d} 7d avg", showlegend=False, opacity=0.4,
                                                 line=dict(color=DOMAIN_COLOURS[d], width=1, dash="dash"),
                                                 hovertemplate=f"{d} 7d avg: %{{y:.1f}}%<extra></extra>"))
        for d in filtered_domains:
            fig_all.add_hline(y=bands.get(d, DEFAULT_BASELINE_BANDS.get(d, {})).get("well", 20),
                              line_dash="dot", line_color="rgba(52,199,89,0.35)", line_width=1)
        fig_all = add_episode_overlays(fig_all, episodes_df)
        if not med_notes_df.empty:
            med_in_range = _apply_date_filter(med_notes_df)
            for _, m in med_in_range.iterrows():
                fig_all = _vline(fig_all, str(m["date"]), f"💊 {str(m.get('medication_notes',''))[:35]}")
        if not med_log_df.empty:
            fig_all = add_med_log_overlays(fig_all, _apply_date_filter(med_log_df))
        fig_all.update_layout(**_base_layout(chart_height),
                               legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_all, use_container_width=True)

        if not med_notes_df.empty and filter_start and not med_notes_df[med_notes_df["date"] >= filter_start].empty:
            st.caption("💊 Vertical dashed lines on the chart above mark days with medication notes.")

        st.markdown("### Per-domain charts")
        c1, c2 = st.columns(2)
        for i, domain in enumerate(filtered_domains):
            with (c1 if i % 2 == 0 else c2):
                st.plotly_chart(make_band_chart(daily_filtered, domain, bands, personal=personal_bl,
                                                movement_threshold=mv_threshold, show_rolling=show_rolling,
                                                episodes=episodes_df, med_notes=med_notes_df, height=chart_height),
                                use_container_width=True)

# ── SNAPSHOTS ─────────────────────────────────────────────
with tab_snapshots_tab:
    st.markdown("## Snapshots")
    st.caption("All submissions within each day. Use to understand intraday variation.")
    if snapshots_filtered.empty:
        st.info("No snapshot data in the selected date range.")
    else:
        st.markdown("### All snapshots over time")
        st.plotly_chart(make_snapshot_timeline(snapshots_filtered, bands, height=chart_height), use_container_width=True)
        st.divider()

        st.markdown("### Component breakdown — pick a submission")
        snap_options = snapshots_filtered.sort_values("submitted_at", ascending=False)
        snap_labels  = snap_options["submitted_at"].astype(str).tolist()
        if snap_labels:
            selected_snap_label = st.selectbox("Submission", snap_labels, index=0, key="snap_picker")
            snap_row = snap_options[snap_options["submitted_at"].astype(str) == selected_snap_label].iloc[0]

            score_cols_s = st.columns(len(DOMAINS))
            for i, domain in enumerate(DOMAINS):
                score = float(snap_row.get(f"{domain} Score %", 0) or 0)
                band  = classify_score(score, domain, bands)
                score_cols_s[i].metric(domain, f"{score:.1f}%", delta=f"{BAND_EMOJI[band]} {band}", delta_color="off")

            st.divider()
            st.markdown("### What's driving each domain?")
            comp_by_domain = {domain: get_snapshot_components(snap_row, domain, weights) for domain in selected_domains}

            st.markdown("#### Symptom radar — top items per domain")
            st.plotly_chart(make_component_radar(comp_by_domain, height=420), use_container_width=True)

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
            st.markdown("### Submissions per day")
            subs_per_day = snapshots_filtered.groupby("submitted_date").size().reset_index(name="count")
            fig_subs = px.bar(subs_per_day, x="submitted_date", y="count", color_discrete_sequence=["#1C7EF2"])
            fig_subs.update_layout(height=220, margin=dict(l=10,r=10,t=10,b=10),
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
        lv_icon = {"critical":"🚨","warning":"⚠️","caution":"💛","ok":"✅"}
        for ins in _generate_insights(daily_filtered, risk, trends, bands, personal_bl, mv_threshold):
            st.markdown(f"{lv_icon.get(ins['level'],'ℹ️')} {ins['text']}")

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
            pb_rows.append({"Domain": d,
                "7d Trend":  {"rising":"rising ↑","falling":"falling ↓","stable":"stable →"}.get(trends[d], trends[d]),
                "7d Mean %": round(daily_filtered[f"{d} Score %"].tail(7).mean(), 1),
                "7d Peak %": round(daily_filtered[f"{d} Score %"].tail(7).max(), 1),
                "Personal Baseline": f"{pb['mean']}%" if pb.get("reliable") else "not yet reliable",
                "Baseline ±1 SD":    f"{pb['lower']}–{pb['upper']}%" if pb.get("reliable") else "—",
                "Well Ceiling":      f"{bands.get(d,{}).get('well','?')}%",
            })
        st.dataframe(pd.DataFrame(pb_rows), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Psychosis insight analysis")
        st.caption("A falling Psychosis score can mean genuine improvement or loss of insight. "
                   "This section attempts to distinguish between them.")
        psy_div = detect_psychosis_insight_divergence(daily_filtered)
        sev_emoji = {"ok":"🟢","caution":"🟠","warning":"🔴"}.get(psy_div["severity"],"⚪")
        st.markdown(f"{sev_emoji} **{psy_div['status'].replace('_',' ').title()}**")
        st.markdown(psy_div["finding"])

        if psy_div["status"] not in ("insufficient_data","stable"):
            pd_cols = st.columns(3)
            pd_cols[0].metric("Primary symptom trend",
                              f"{psy_div['primary_delta']:+.1f}pp" if psy_div["primary_delta"] is not None else "—")
            pd_cols[1].metric("Insight indicator trend",
                              f"{psy_div['insight_delta']:+.1f}pp" if psy_div["insight_delta"] is not None else "—")
            pd_cols[2].metric("Days analysed", psy_div["days_analysed"])

            if not daily_filtered.empty:
                recent_w = daily_filtered.sort_values("date").tail(psy_div["days_analysed"]).copy()
                dates_w  = recent_w["date"].astype(str).tolist()
                insight_s = recent_w.apply(lambda r: _mean_normalised(r, ["meta_something_wrong","meta_concerned"]), axis=1)
                primary_s = recent_w.apply(lambda r: _mean_normalised(r, PSY_PRIMARY_CODES), axis=1)
                fig_psy = go.Figure()
                fig_psy.add_trace(go.Scatter(x=dates_w, y=primary_s.tolist(), mode="lines+markers",
                                             name="Primary symptoms", line=dict(color=DOMAIN_COLOURS["Psychosis"], width=2),
                                             hovertemplate="Primary: %{y:.1f}%<extra></extra>"))
                fig_psy.add_trace(go.Scatter(x=dates_w, y=insight_s.tolist(), mode="lines+markers",
                                             name="Insight indicators", line=dict(color="#34C759", width=2, dash="dash"),
                                             hovertemplate="Insight: %{y:.1f}%<extra></extra>"))
                fig_psy.update_layout(height=280, margin=dict(l=10,r=10,t=30,b=10),
                                      yaxis=dict(range=[0,100], title="Score %", ticksuffix="%"),
                                      xaxis=dict(title=None),
                                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                      plot_bgcolor="white", paper_bgcolor="white",
                                      title=dict(text="Primary symptoms vs insight indicators", font=dict(size=13, color="#1C1C1E"), x=0))
                st.plotly_chart(fig_psy, use_container_width=True)

        st.divider()
        st.markdown("### Cross-domain correlation")
        corr = _cross_domain_correlation(daily_filtered)
        if not corr.empty:
            st.caption("Pearson r across all filtered daily entries.")
            st.dataframe(corr.style.background_gradient(cmap="RdYlGn_r", vmin=-1, vmax=1), use_container_width=True)
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
                    st.dataframe(df_peak.rename(columns={"mean_raw":"Mean (1–5)","question":"Question"})[["Question","Mean (1–5)"]],
                                 use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Flag impact on domain scores")
        imp = _flag_impact(daily_filtered)
        if imp.empty:
            st.info("Not enough flag data.")
        else:
            top = imp[imp["impact"].abs() > 2].round(1)
            st.dataframe(top if not top.empty else pd.DataFrame({"Note":["No flags with impact > 2pp"]}),
                         use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Submission type summary")
        if "submission_type_derived" in wide_df.columns:
            type_summary = wide_df.copy()
            if filter_start:
                type_summary = type_summary[(type_summary["submitted_date"] >= filter_start) &
                                             (type_summary["submitted_date"] <= filter_end)]
            ts1, ts2, ts3, ts4 = st.columns(4)
            ts1.metric("Snapshots", int((type_summary["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT).sum()))
            ts2.metric("Reviews",   int((type_summary["submission_type_derived"] == SUBMISSION_TYPE_REVIEW).sum()))
            if not daily_filtered.empty and "n_reviews" in daily_filtered.columns:
                ts3.metric("Days with no review",   int((daily_filtered["n_reviews"] == 0).sum()))
                ts4.metric("Days with no snapshot", int((daily_filtered["n_snapshots"] == 0).sum()) if "n_snapshots" in daily_filtered.columns else "—")

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
    st.caption("All written entries, colour-coded by worst band reached that day.")
    if notes_filtered.empty:
        st.info("No journal entries in the selected date range.")
    else:
        j1, j2, j3 = st.columns([3,2,2])
        search_term = j1.text_input("Search entries", placeholder="keyword...", key="journal_search")
        band_filter = j2.multiselect("Filter by day's band",
            options=["well","watch","caution","warning","critical"],
            default=["well","watch","caution","warning","critical"], key="journal_band_filter")
        sort_order  = j3.radio("Sort", ["Newest first","Oldest first"], horizontal=True, key="journal_sort")

        filtered_notes = notes_filtered[notes_filtered["worst_band"].isin(band_filter)].copy()
        if search_term:
            filtered_notes = filtered_notes[
                filtered_notes["experience_description"].str.contains(search_term, case=False, na=False)]
        if sort_order == "Oldest first":
            filtered_notes = filtered_notes.sort_values("submitted_at")
        st.caption(f"Showing {len(filtered_notes)} of {len(notes_filtered)} entries")

        if not filtered_notes.empty:
            with st.expander("Keyword frequency across shown entries", expanded=False):
                st.plotly_chart(keyword_frequency_chart(filtered_notes), use_container_width=True)
        st.divider()

        for row_idx, (_, entry) in enumerate(filtered_notes.iterrows()):
            band      = entry.get("worst_band","unknown")
            hex_c     = BAND_COLOUR_HEX.get(band, "#8E8E93")
            date_str  = str(entry.get("date",""))
            text      = str(entry.get("experience_description",""))
            keywords  = entry.get("keywords",[])

            day_subs    = wide_df[wide_df["submitted_date"] == entry.get("date")] if not wide_df.empty else pd.DataFrame()
            has_review  = not day_subs.empty and (day_subs["submission_type_derived"] == SUBMISSION_TYPE_REVIEW).any()
            has_snapshot= not day_subs.empty and (day_subs["submission_type_derived"] == SUBMISSION_TYPE_SNAPSHOT).any()
            type_badge  = ("📋 Review + 📸 Snapshot" if has_review and has_snapshot
                           else ("📋 Day review" if has_review else ("📸 Snapshot" if has_snapshot else "")))

            ctx = " · ".join(f"{d}: {entry.get(f'{d} Score %',0):.0f}% ({classify_score(entry.get(f'{d} Score %',0),d,bands)})"
                             for d in DOMAINS if entry.get(f"{d} Score %") is not None)
            display_text = re.sub(f"({re.escape(search_term)})", r"**\1**", text, flags=re.IGNORECASE) if search_term else text

            st.markdown(
                f"""<div style="border-left:4px solid {hex_c};padding:12px 16px;margin-bottom:12px;border-radius:4px;background:{hex_c}18">
                <strong>{BAND_EMOJI.get(band,'⚪')} {date_str}</strong>
                &nbsp;&nbsp;<span style="color:#666;font-size:0.85em">{ctx}</span>
                &nbsp;&nbsp;<span style="font-size:0.8em;color:#999">{type_badge}</span></div>""",
                unsafe_allow_html=True)
            st.markdown(display_text)
            if keywords:
                st.markdown(f"*Keywords: {' '.join(f'`{kw}`' for kw in keywords[:6])}*")

            submission_id  = str(entry.get("submission_id",""))
            entry_comments = get_comments_for_submission(submission_id, comments_df)
            for c in entry_comments:
                st.markdown(
                    f"""<div style="margin-left:16px;margin-top:6px;padding:8px 12px;border-left:3px solid rgba(100,100,100,0.3);
                    background:rgba(100,100,100,0.05);border-radius:3px;font-size:0.9em;color:#444">
                    💬 <em>{str(c.get('commented_at',''))[:16]}</em> — {c.get('comment_text','')}</div>""",
                    unsafe_allow_html=True)

            new_comment = st.text_input("Add a note", placeholder="Type a note and press Enter…",
                                        key=f"comment_input_{submission_id}_{row_idx}",
                                        label_visibility="collapsed")
            if st.button("Save note", key=f"comment_save_{submission_id}_{row_idx}", type="secondary"):
                if new_comment.strip():
                    ok, msg = save_comment(submission_id, new_comment.strip())
                    if ok:
                        st.success("Note saved."); comments_df = load_comments()
                    else:
                        st.error(msg)
                else:
                    st.warning("Note is empty.")
            st.divider()

    st.markdown("## Medication Notes")
    med_filtered = _apply_date_filter(med_notes_df) if not med_notes_df.empty else med_notes_df
    if med_filtered.empty:
        st.info("No medication notes in the selected date range.")
    else:
        for _, m in med_filtered.iterrows():
            ctx = " · ".join(f"{d}: {m.get(f'{d} Score %',0):.0f}% ({classify_score(m.get(f'{d} Score %',0),d,bands)})"
                             for d in DOMAINS if m.get(f"{d} Score %") is not None)
            st.markdown(
                f"""<div style="border-left:4px solid rgba(0,150,100,0.8);padding:10px 16px;margin-bottom:10px;
                border-radius:4px;background:rgba(0,150,100,0.06)">
                <strong>💊 {m.get('date','')}</strong>&nbsp;&nbsp;<span style="color:#666;font-size:0.85em">{ctx}</span></div>""",
                unsafe_allow_html=True)
            st.markdown(str(m.get("medication_notes","")))
            st.divider()

# ── EPISODES ──────────────────────────────────────────────
with tab_episodes:
    st.markdown("## Episode Labelling")
    st.caption("Label historical periods as episodes. These appear as shaded regions on all domain charts "
               "and exclude episode periods from the personal baseline. Requires a **Episode Log** sheet tab.")
    if not safe_worksheet(EPISODE_TAB):
        st.warning(f"Worksheet '{EPISODE_TAB}' not found.")

    st.markdown("### Add episode")
    with st.form("add_episode_form"):
        fc1, fc2, fc3 = st.columns([2,2,3])
        ep_type  = fc1.selectbox("Episode type", EPISODE_TYPES, key="ep_type")
        ep_start = fc2.date_input("Start date", key="ep_start")
        ep_end   = fc3.date_input("End date",   key="ep_end")
        ep_notes = st.text_input("Notes (optional)", key="ep_notes")
        if st.form_submit_button("Add episode", type="primary"):
            if ep_end < ep_start:
                st.error("End date must be on or after start date.")
            else:
                ok, msg = add_episode(ep_type, ep_start, ep_end, ep_notes)
                if ok:
                    st.success(f"Episode added. {msg}"); st.rerun()
                else:
                    st.error(msg)

    st.divider()
    st.markdown("### Labelled episodes")
    episodes_df = load_episodes()
    ep_emoji = {"Depressive":"🔴","Hypomanic":"🟠","Manic":"🟡","Mixed":"🔵","Psychotic":"🟣","Other":"⚪"}
    if episodes_df.empty:
        st.info("No episodes labelled yet.")
    else:
        for _, ep in episodes_df.sort_values("start_date", ascending=False).iterrows():
            duration = (pd.Timestamp(ep["end_date"]) - pd.Timestamp(ep["start_date"])).days + 1
            ec1, ec2 = st.columns([5,1])
            ec1.markdown(
                f"{ep_emoji.get(ep['episode_type'],'⚪')} **{ep['episode_type']}** — "
                f"{ep['start_date']} to {ep['end_date']} ({duration} day{'s' if duration!=1 else ''})"
                + (f"  \n*{ep['notes']}*" if ep.get("notes") else ""))
            if ec2.button("Delete", key=f"del_{ep['episode_id']}"):
                ok, msg = delete_episode(ep["episode_id"])
                if ok: st.rerun()
                else:  st.error(msg)
            st.divider()

        st.markdown("### Domain scores around each episode")
        for _, ep in episodes_df.sort_values("start_date", ascending=False).iterrows():
            start = pd.Timestamp(ep["start_date"])
            end   = pd.Timestamp(ep["end_date"])
            ep_window = daily_df[
                (daily_df["date"] >= (start - pd.Timedelta(days=14)).date()) &
                (daily_df["date"] <= (end   + pd.Timedelta(days=14)).date())
            ]
            if ep_window.empty:
                continue
            with st.expander(f"{ep['episode_type']} — {ep['start_date']} to {ep['end_date']}", expanded=False):
                fig_ep = make_overview_chart(ep_window, bands, height=280)
                st.plotly_chart(add_episode_overlays(fig_ep, episodes_df[episodes_df["episode_id"]==ep["episode_id"]]),
                                use_container_width=True)

# ── MEDICATIONS ───────────────────────────────────────────
with tab_medications:
    st.markdown("## Medication Log")
    st.caption("Log medication change events. Changes appear as markers on domain score charts.")
    if not safe_worksheet(MED_LOG_TAB):
        st.warning(f"Worksheet '{MED_LOG_TAB}' not found.")

    st.markdown("### Currently active medications")
    current_meds = get_current_medications(med_log_df)
    if current_meds.empty:
        st.info("No medications logged yet.")
    else:
        for _, m in current_meds.iterrows():
            dose_str = f"{m['dose']:.0f}{m['dose_unit']}" if pd.notna(m.get("dose")) else ""
            st.markdown(f"**{m['medication']}** {dose_str}{f' — {m[\"frequency\"]}' if m.get('frequency') else ''}  \n"
                        f"*Last change: {m['change_type']} on {m['date']}*"
                        + (f"  \n*{m['notes']}*" if m.get("notes") else ""))

    st.divider()
    st.markdown("### Log a medication change")
    with st.form("med_log_form", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        med_date    = f1.date_input("Date", value=dt.date.today(), key="mf_date")
        med_name    = f2.text_input("Medication name", placeholder="e.g. Quetiapine", key="mf_name")
        change_type = f3.selectbox("Change type", MED_CHANGE_TYPES, key="mf_change")
        f4, f5, f6  = st.columns(3)
        med_dose    = f4.number_input("New dose", min_value=0.0, step=25.0, key="mf_dose")
        dose_unit   = f5.selectbox("Unit", MED_DOSE_UNITS, key="mf_unit")
        frequency   = f6.selectbox("Frequency", MED_FREQUENCIES, key="mf_freq")
        med_notes_field = st.text_input("Notes (optional)", key="mf_notes")
        if st.form_submit_button("Save medication change", type="primary"):
            if not med_name.strip():
                st.error("Medication name is required.")
            else:
                ok, msg = add_med_event(med_date, med_name, med_dose, dose_unit, frequency, change_type, med_notes_field)
                if ok:
                    st.success(f"Logged: {change_type} {med_name} {med_dose}{dose_unit} on {med_date}.")
                    med_log_df = load_med_log()
                else:
                    st.error(msg)

    st.divider()
    st.markdown("### Full change history")
    if med_log_df.empty:
        st.info("No events logged yet.")
    else:
        for _, m in med_log_df.iterrows():
            dose_str = f"{m['dose']:.0f}{m['dose_unit']}" if pd.notna(m.get("dose")) else ""
            c1, c2 = st.columns([5,1])
            c1.markdown(f"**{m['date']}** · {m['change_type']}: **{m['medication']}** "
                        f"{dose_str} {m.get('frequency','')}" + (f" — {m['notes']}" if m.get("notes") else ""))
            if c2.button("Delete", key=f"del_med_{m['med_id']}", type="secondary"):
                ok, msg = delete_med_event(str(m["med_id"]))
                if ok:
                    st.success("Entry deleted."); med_log_df = load_med_log()
                else:
                    st.error(msg)

    st.divider()
    st.markdown("### Domain scores with medication change markers")
    if not daily_filtered.empty and not med_log_df.empty:
        fig_med = go.Figure()
        for d in selected_domains:
            col = f"{d} Score %"
            if col not in daily_filtered.columns:
                continue
            fig_med.add_trace(go.Scatter(x=daily_filtered["date"].astype(str).tolist(),
                                         y=daily_filtered[col].tolist(), mode="lines", name=d,
                                         line=dict(color=DOMAIN_COLOURS.get(d,"#888"), width=2),
                                         hovertemplate=f"{d}: %{{y:.1f}}%<extra></extra>"))
        fig_med = add_med_log_overlays(fig_med, _apply_date_filter(med_log_df))
        fig_med.update_layout(**_base_layout(chart_height),
                               legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_med, use_container_width=True)
        st.caption("Blue dashed lines = medication change events.")
    elif daily_filtered.empty:
        st.info("No daily data in the selected date range.")
    else:
        st.info("No medication events logged yet.")

# ── CLINICIAN EXPORT ──────────────────────────────────────
with tab_export:
    st.markdown("## Clinician Export")
    st.caption("Structured summary for clinical appointments.")
    export_window = st.slider("Days to cover", 7, 90, 30, 7, key="export_window")
    report = generate_clinician_report(daily=daily_df, bands=bands, personal_bl=personal_bl,
                                        episodes=episodes_df, notes=notes_df, med_notes=med_notes_df,
                                        weights=weights, wide=wide_df, comments=comments_df,
                                        med_log=med_log_df, window_days=export_window)
    with st.expander("Preview (rendered)", expanded=True):
        st.markdown(report)
    st.markdown("### Copy-ready text")
    st.text_area("Select all and copy (Ctrl+A, Ctrl+C)", value=report, height=400, key="export_text")

# ── BASELINES ─────────────────────────────────────────────
with tab_baseline:
    st.markdown("## Baselines")
    st.markdown("### Your personal baseline")
    n_ep_days = sum((pd.Timestamp(ep["end_date"]) - pd.Timestamp(ep["start_date"])).days + 1
                    for _, ep in episodes_df.iterrows()) if not episodes_df.empty else 0
    st.caption(
        f"Derived from days where **all** domains were in the Well band **and at least one snapshot was submitted**. "
        f"Uses the most recent **{pb_window}** such days. Requires **{PERSONAL_BASELINE_MIN_DAYS}+** days to be reliable."
        + (f" Episode periods excluded ({n_ep_days} labelled episode days removed)." if n_ep_days else ""))

    pb_cols = st.columns(len(DOMAINS))
    for i, domain in enumerate(DOMAINS):
        pb = personal_bl.get(domain, {})
        with pb_cols[i]:
            st.markdown(f"**{domain}**")
            if pb.get("reliable"):
                st.metric("Baseline mean", f"{pb['mean']}%")
                well_ceil = bands.get(domain, {}).get("well", 20)
                note = f"Note: upper SD ({pb['upper']}%) exceeds Well ceiling ({well_ceil}%)." if pb["upper"] > well_ceil else ""
                st.caption(f"±1 SD: {pb['lower']}–{pb['upper']}%  \nBased on {pb['n']} well days" + (f"  \n{note}" if note else ""))
            else:
                st.info(f"Not yet reliable  \n{pb.get('n',0)} well days so far  \n{max(0,PERSONAL_BASELINE_MIN_DAYS-pb.get('n',0))} more needed")

    st.divider()
    st.markdown("### Score history with overlays")
    if not daily_filtered.empty:
        for domain in selected_domains:
            st.plotly_chart(make_band_chart(daily_filtered, domain, bands, personal=personal_bl,
                                            movement_threshold=mv_threshold, show_rolling=show_rolling,
                                            episodes=episodes_df, med_notes=med_notes_df, height=300),
                            use_container_width=True)
    else:
        st.info("No data in selected range.")

    st.divider()
    st.markdown("### Current band thresholds")
    st.dataframe(pd.DataFrame([{"Domain": d,
        "Well": f"0–{bands.get(d,{}).get('well','?')}%",
        "Watch": f"{bands.get(d,{}).get('well','?')}–{bands.get(d,{}).get('watch','?')}%",
        "Caution": f"{bands.get(d,{}).get('watch','?')}–{bands.get(d,{}).get('caution','?')}%",
        "Warning": f"{bands.get(d,{}).get('caution','?')}–{bands.get(d,{}).get('warning','?')}%",
        "Critical": f"{bands.get(d,{}).get('warning','?')}–100%",
    } for d in DOMAINS]), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Edit thresholds")
    bl_config    = render_baseline_editor(bl_config)
    bands        = bl_config["bands"]
    mv_threshold = bl_config["movement_threshold"]
    pb_window    = bl_config["personal_baseline_window"]

# ── QUESTIONS ─────────────────────────────────────────────
with tab_questions:
    st.markdown("## Form Questions")
    st.caption("All questions from the monitoring form. Click **📈 Chart** to see answer trends.")

    def _question_chart(code: str, meta: dict, daily: pd.DataFrame,
                        wide: pd.DataFrame, episodes: pd.DataFrame) -> go.Figure:
        rtype = meta.get("rtype","")
        if rtype == "text":
            return go.Figure()
        if rtype == "boolean_yes_no":
            if code not in wide.columns:
                return go.Figure()
            bool_data = wide[["submitted_date", code]].copy()
            bool_data[code] = bool_data[code].astype(bool)
            counts = bool_data.groupby(["submitted_date", code]).size().reset_index(name="count")
            yes_c = counts[counts[code]==True].set_index("submitted_date")["count"]
            no_c  = counts[counts[code]==False].set_index("submitted_date")["count"]
            all_dates = sorted(bool_data["submitted_date"].unique())
            date_strs = [str(d) for d in all_dates]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=date_strs, y=[int(yes_c.get(d,0)) for d in all_dates],
                                 name="Yes", marker_color="rgba(255,59,48,0.7)",
                                 hovertemplate="%{x}<br>Yes: %{y}<extra></extra>"))
            fig.add_trace(go.Bar(x=date_strs, y=[int(no_c.get(d,0)) for d in all_dates],
                                 name="No", marker_color="rgba(142,142,147,0.4)",
                                 hovertemplate="%{x}<br>No: %{y}<extra></extra>"))
            fig.update_layout(barmode="stack", height=260, margin=dict(l=10,r=10,t=10,b=10),
                              yaxis=dict(title="Submissions",dtick=1), xaxis=dict(title=None),
                              legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
                              plot_bgcolor="white", paper_bgcolor="white")
            return add_episode_overlays(fig, episodes)

        if code not in daily.columns:
            return go.Figure()
        plot_daily = daily[["date",code]].dropna(subset=[code]).copy()
        if plot_daily.empty:
            return go.Figure()
        date_strs = plot_daily["date"].astype(str).tolist()
        values    = plot_daily[code].tolist()
        rolling   = plot_daily[code].rolling(7, min_periods=1).mean().tolist()
        domain_list = meta.get("domains",[])
        colour = DOMAIN_COLOURS.get(domain_list[0],"#1C7EF2") if domain_list else "#1C7EF2"
        y_range = [0.5,5.5] if rtype == "scale_1_5" else None
        fig = add_episode_overlays(go.Figure(), episodes)
        fig.add_trace(go.Scatter(x=date_strs, y=rolling, mode="lines", name="7d avg",
                                 line=dict(color="rgba(100,100,100,0.4)",width=1.5,dash="dash"),
                                 hovertemplate="7d avg: %{y:.2f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=date_strs, y=values, mode="lines+markers", name="Daily value",
                                 line=dict(color=colour,width=2), marker=dict(size=5,color=colour),
                                 hovertemplate="%{x}<br>Value: %{y}<extra></extra>"))
        yaxis_cfg = dict(title="Rating (1–5)" if rtype=="scale_1_5" else "Value")
        if y_range:
            yaxis_cfg["range"] = y_range
            yaxis_cfg["tickvals"] = [1,2,3,4,5]
        fig.update_layout(height=260, margin=dict(l=10,r=10,t=10,b=10), yaxis=yaxis_cfg,
                          xaxis=dict(title=None), showlegend=True,
                          legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
                          plot_bgcolor="white", paper_bgcolor="white")
        return fig

    GROUP_LABELS = {
        "depression":"🔵 Depression","mania":"🟠 Mania","mixed":"🔀 Mixed","psychosis":"🟣 Psychosis",
        "functioning":"⚙️ Functioning","meta":"🧠 Meta / Self-observation",
        "flags":"🚩 Flags","observations":"👁 Observations","notes":"📝 Notes",
    }
    GROUP_ORDER = ["depression","mania","mixed","psychosis","functioning","meta","flags","observations","notes"]
    ROLE_BADGES = {
        "force_multiplier":          "⚡ Force multiplier",
        "insight_inverse_psychosis": "🔄 Insight-inverse (Psychosis)",
        "contributor":               "➕ Domain contributor",
    }
    RTYPE_LABELS = {"scale_1_5":"Scale 1–5","boolean_yes_no":"Yes / No","numeric":"Number","text":"Free text"}

    if "q_chart_code" not in st.session_state:
        st.session_state["q_chart_code"] = None
    q_search = st.text_input("Search questions", placeholder="e.g. sleep, mood…", key="q_search")
    st.divider()
    cat = catalog_df()

    for group in GROUP_ORDER:
        group_qs = cat[cat["group"] == group].sort_values("order")
        if group_qs.empty:
            continue
        if q_search:
            group_qs = group_qs[group_qs["text"].str.contains(q_search,case=False,na=False) |
                                 group_qs["code"].str.contains(q_search,case=False,na=False)]
            if group_qs.empty:
                continue

        with st.expander(f"{GROUP_LABELS.get(group,group.title())}  ({len(group_qs)} questions)", expanded=not bool(q_search)):
            for _, q_row in group_qs.iterrows():
                code, rtype = q_row["code"], q_row.get("rtype","")
                domains = q_row.get("domains",[])
                if isinstance(domains, str):
                    import ast
                    try: domains = ast.literal_eval(domains)
                    except Exception: domains = []
                hc1, hc2 = st.columns([5,1])
                with hc1:
                    st.markdown(f"**{q_row['text']}**")
                    badges = [f"`{RTYPE_LABELS.get(rtype,rtype)}`"] + \
                             [f"`{d}`" for d in domains] + \
                             ([f"`{ROLE_BADGES.get(q_row.get('meta_role'),q_row.get('meta_role'))}`"] if q_row.get("meta_role") else []) + \
                             ([f"weight `{DEFAULT_WEIGHTS[code]}`"] if code in DEFAULT_WEIGHTS else [])
                    st.caption("  ".join(badges))
                with hc2:
                    btn_label = "📉 Hide" if st.session_state["q_chart_code"] == code else "📈 Chart"
                    if rtype == "text":
                        st.caption("*Free text*")
                    elif st.button(btn_label, key=f"qbtn_{code}", use_container_width=True):
                        st.session_state["q_chart_code"] = None if st.session_state["q_chart_code"] == code else code

                if st.session_state["q_chart_code"] == code:
                    fig = _question_chart(code, _CATALOG_BY_CODE.get(code,{}), daily_filtered, wide_df, episodes_df)
                    if fig.data or fig.layout.shapes:
                        if code in daily_filtered.columns and rtype != "text":
                            vals = pd.to_numeric(daily_filtered[code], errors="coerce").dropna()
                            if not vals.empty:
                                if rtype == "boolean_yes_no":
                                    sc1, sc2 = st.columns(2)
                                    sc1.metric("Days answered Yes", f"{vals.astype(bool).sum()} / {len(vals)}")
                                    sc2.metric("% Yes", f"{int(vals.astype(bool).mean()*100)}%")
                                else:
                                    sc1, sc2, sc3, sc4 = st.columns(4)
                                    sc1.metric("Mean", f"{vals.mean():.2f}")
                                    sc2.metric("Peak", f"{vals.max():.0f}")
                                    sc3.metric("Days recorded", len(vals))
                                    if rtype == "scale_1_5":
                                        sc4.metric("% days rated 4–5", f"{int((vals>=4).mean()*100)}%")
                        st.plotly_chart(fig, use_container_width=True, key=f"qfig_{code}")
                        if rtype == "boolean_yes_no" and code in wide_df.columns:
                            yes_dates = wide_df[wide_df[code]==True]["submitted_date"].unique()
                            if len(yes_dates):
                                with st.expander(f"All dates answered Yes ({len(yes_dates)})", expanded=False):
                                    st.write(", ".join(str(d) for d in sorted(yes_dates)))
                    else:
                        st.info("Free text — see the Journal tab." if rtype=="text" else "No data recorded yet.")
                st.divider()

# ── DAILY MODEL ───────────────────────────────────────────
with tab_daily:
    st.markdown("### Daily model")
    st.dataframe(daily_filtered, use_container_width=True)
    delta_cols = [c for c in daily_filtered.columns if c.endswith(" Delta") and "Score" in c]
    if delta_cols:
        st.markdown("### Day-on-day deltas")
        st.dataframe(daily_filtered[["date"] + delta_cols], use_container_width=True)

# ── DATA LAYER ────────────────────────────────────────────
with tab_data:
    st.markdown("### Question catalog")
    display_cols = ["code","text","group","meta_role","rtype","polarity","domains","order"]
    cat_display = catalog_df()
    st.dataframe(cat_display[[c for c in display_cols if c in cat_display.columns]], use_container_width=True)

    st.divider()
    st.markdown("### Meta question system")
    meta_ref = []
    for q in QUESTION_CATALOG:
        role = q.get("meta_role")
        if not role:
            continue
        desc = {
            "force_multiplier": f"Force multiplier — amplifies all domain scores ×1.0–×{META_MULTIPLIER_MAX}.",
            "insight_inverse_psychosis": "Insight item — inverted in Psychosis (low insight = higher risk).",
            "contributor": f"Direct contributor to: {', '.join(q.get('domains',[]))}",
        }.get(role, role)
        meta_ref.append({"Code": q["code"], "Question": q["text"][:60]+("…" if len(q["text"])>60 else ""),
                         "Role": role, "Domains": ", ".join(q.get("domains",[])) or "—", "Description": desc})
    st.dataframe(pd.DataFrame(meta_ref), use_container_width=True, hide_index=True)
    st.caption(f"Multiplier: mean of {FORCE_MULTIPLIER_CODES} → 0–100 → ×1.0–×{META_MULTIPLIER_MAX}. All scores capped at 100.")

    st.divider()
    st.markdown("### Sleep weight multipliers by domain")
    st.dataframe(pd.DataFrame([{"Domain": d,
        "sleep_hours ×":   DOMAIN_WEIGHT_MULTIPLIERS.get(d,{}).get("func_sleep_hours",1.0),
        "sleep_quality ×": DOMAIN_WEIGHT_MULTIPLIERS.get(d,{}).get("func_sleep_quality",1.0),
        "Eff. sleep_hours w":   round(_effective_weight("func_sleep_hours",d,weights),3),
        "Eff. sleep_quality w": round(_effective_weight("func_sleep_quality",d,weights),3),
    } for d in DOMAINS]), use_container_width=True, hide_index=True)

    with st.expander("Wide submission table"):
        st.dataframe(wide_df, use_container_width=True)
    with st.expander("Raw worksheet"):
        st.dataframe(raw_df, use_container_width=True)
        st.caption(f"Columns: {list(raw_df.columns)}")

# ── SETTINGS ──────────────────────────────────────────────
with tab_settings:
    weights = render_weights_editor(weights)
