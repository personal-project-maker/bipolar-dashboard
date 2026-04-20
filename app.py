"""
Wellbeing Dashboard — with baseline scoring, personal baseline, and overlay charts.

Baseline system:
  • BASELINE_BANDS: domain-specific well / watch / caution / warning / critical thresholds
  • Personal baseline: rolling mean ± SD computed from days where ALL domains are in the
    well band (configurable window, default 90 days), stored in session_state and
    optionally persisted to a Google Sheet tab
  • Overlay charts (Plotly): coloured band overlays so scores are always read relative
    to what is normal for this person
  • Movement alerts: day-on-day delta flags even when absolute score is within well band
  • Baseline status row: per-domain badge showing current position in the band system
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import gspread
from typing import Any

# ──────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────
st.set_page_config(page_title="Wellbeing Dashboard", layout="wide")
st.title("Wellbeing Dashboard")

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
# BASELINE BAND DEFINITIONS
# ──────────────────────────────────────────────────────────
# Thresholds are upper bounds of each band (0-100 score).
# E.g. for Depression, scores 0-20 = Well, 21-40 = Watch, etc.
# These are defaults; the user can override them in Settings.

DEFAULT_BASELINE_BANDS: dict[str, dict[str, float]] = {
    "Depression": {"well": 20.0, "watch": 40.0, "caution": 60.0, "warning": 75.0},
    "Mania":      {"well": 20.0, "watch": 40.0, "caution": 60.0, "warning": 75.0},
    "Mixed":      {"well": 18.0, "watch": 35.0, "caution": 55.0, "warning": 70.0},
    "Psychosis":  {"well": 12.0, "watch": 28.0, "caution": 50.0, "warning": 68.0},
}

# Normal day-on-day variation: delta above this triggers a movement alert
# even if the absolute score is still in the well band.
DEFAULT_MOVEMENT_THRESHOLD: float = 10.0

# Self-harm item: any raw score > this (on 1-5 scale) triggers a standalone alert.
SELF_HARM_FLAG_THRESHOLD: int = 1

# Minimum number of "well" days needed before personal baseline is reliable.
PERSONAL_BASELINE_MIN_DAYS: int = 14

# Band display colours (Plotly-compatible RGBA strings)
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

# ──────────────────────────────────────────────────────────
# QUESTION CATALOG
# ──────────────────────────────────────────────────────────
QUESTION_CATALOG: list[dict[str, Any]] = [
    # DEPRESSION
    dict(code="dep_low_mood",           text="Have I felt a low mood?",                                               group="depression", rtype="scale_1_5",      polarity="higher_worse",  domains=["Depression"],                         order=10),
    dict(code="dep_slowed_low_energy",  text="Have I felt slowed down or low on energy?",                            group="depression", rtype="scale_1_5",      polarity="higher_worse",  domains=["Depression"],                         order=20),
    dict(code="dep_low_motivation",     text="Have I felt low on motivation or had difficulty initiating tasks?",     group="depression", rtype="scale_1_5",      polarity="higher_worse",  domains=["Depression"],                         order=30),
    dict(code="dep_anhedonia",          text="Have I felt a lack of interest or pleasure in activities?",             group="depression", rtype="scale_1_5",      polarity="higher_worse",  domains=["Depression"],                         order=40),
    dict(code="dep_withdrawal",         text="Have I been socially or emotionally withdrawn?",                        group="depression", rtype="scale_1_5",      polarity="higher_worse",  domains=["Depression"],                         order=50),
    dict(code="dep_self_harm_ideation", text="Have I had ideation around self-harming or suicidal behaviours?",       group="depression", rtype="scale_1_5",      polarity="higher_worse",  domains=["Depression"],                         order=60),
    # MANIA
    dict(code="man_elevated_mood",      text="Have I felt an elevated mood?",                                         group="mania",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mania"],                              order=70),
    dict(code="man_sped_up_high_energy",text="Have I felt sped up or high on energy?",                               group="mania",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mania","Mixed"],                      order=80),
    dict(code="man_racing_thoughts",    text="Have I had racing thoughts or speech?",                                 group="mania",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mania"],                              order=90),
    dict(code="man_goal_drive",         text="Have I had an increased drive towards goal-directed activity?",          group="mania",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mania"],                              order=100),
    dict(code="man_impulsivity",        text="Have I felt impulsivity or an urge to take risky actions?",             group="mania",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mania"],                              order=110),
    dict(code="man_agitation",          text="Have I felt agitated or restless?",                                     group="mania",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mania","Mixed"],                      order=120),
    dict(code="man_irritability",       text="Have I been more irritable and reactive than normal?",                  group="mania",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mania","Mixed"],                      order=130),
    dict(code="man_cant_settle",        text="Have I been unable to settle or switch off?",                           group="mania",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mania"],                              order=140),
    # MIXED
    dict(code="mix_high_energy_low_mood",   text="Have I had a high energy combined with low mood?",                 group="mixed",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mixed"],                              order=150),
    dict(code="mix_rapid_emotional_shifts", text="Have I experienced rapid emotional shifts?",                        group="mixed",      rtype="scale_1_5",      polarity="higher_worse",  domains=["Mixed"],                              order=160),
    # PSYCHOSIS
    dict(code="psy_heard_saw",          text="Have I heard or seen things others didn't?",                            group="psychosis",  rtype="scale_1_5",      polarity="higher_worse",  domains=["Psychosis"],                          order=170),
    dict(code="psy_suspicious",         text="Have I felt watched, followed, targeted or suspicious?",                group="psychosis",  rtype="scale_1_5",      polarity="higher_worse",  domains=["Psychosis"],                          order=180),
    dict(code="psy_trust_perceptions",  text="Have I had trouble trusting my perceptions and thoughts?",              group="psychosis",  rtype="scale_1_5",      polarity="higher_worse",  domains=["Psychosis"],                          order=190),
    dict(code="psy_confidence_reality", text="How confident have I been in the reality of these experiences?",        group="psychosis",  rtype="scale_1_5",      polarity="higher_worse",  domains=["Psychosis"],                          order=200),
    dict(code="psy_distress",           text="How distressed have I been by these beliefs and experiences?",          group="psychosis",  rtype="scale_1_5",      polarity="higher_worse",  domains=["Psychosis"],                          order=210),
    # FUNCTIONING
    dict(code="func_work",              text="How effectively have I been functioning at work?",                      group="functioning",rtype="scale_1_5",      polarity="higher_better", domains=["Depression","Mania"],                  order=220),
    dict(code="func_daily",             text="How well have I been functioning in my daily life?",                    group="functioning",rtype="scale_1_5",      polarity="higher_better", domains=["Depression","Mania"],                  order=230),
    dict(code="func_sleep_hours",       text="How many hours did I sleep last night?",                                group="functioning",rtype="numeric",        polarity="custom_sleep",  domains=["Depression","Mania","Mixed"],          order=450, score_in_snapshot=False),
    dict(code="func_sleep_quality",     text="How poor was my sleep quality last night",                              group="functioning",rtype="scale_1_5",      polarity="higher_worse",  domains=["Depression","Mania","Mixed"],          order=460, score_in_snapshot=False),
    # META
    dict(code="meta_unlike_self",             text="Do I feel unlike my usual self?",                                 group="meta",       rtype="scale_1_5",      polarity="higher_worse",  domains=[],                                     order=240),
    dict(code="meta_something_wrong",         text="Do I think something may be wrong or changing?",                 group="meta",       rtype="scale_1_5",      polarity="higher_worse",  domains=[],                                     order=250),
    dict(code="meta_concerned",               text="Am I concerned about my current state?",                          group="meta",       rtype="scale_1_5",      polarity="higher_worse",  domains=[],                                     order=260),
    dict(code="meta_disorganised_thoughts",   text="Do my thoughts feel disorganised or hard to follow?",             group="meta",       rtype="scale_1_5",      polarity="higher_worse",  domains=[],                                     order=270),
    dict(code="meta_attention_unstable",      text="Is my attention unstable or jumping?",                            group="meta",       rtype="scale_1_5",      polarity="higher_worse",  domains=[],                                     order=280),
    dict(code="meta_driven_without_thinking", text="Do I feel driven to act without thinking?",                       group="meta",       rtype="scale_1_5",      polarity="higher_worse",  domains=[],                                     order=290),
    dict(code="meta_intensifying",            text="Is my state intensifying (in any direction)?",                    group="meta",       rtype="scale_1_5",      polarity="higher_worse",  domains=[],                                     order=300),
    dict(code="meta_towards_episode",         text="Do I feel like I'm moving towards an episode?",                   group="meta",       rtype="scale_1_5",      polarity="higher_worse",  domains=[],                                     order=310),
    # FLAGS
    dict(code="flag_not_myself",          text="I've been feeling \"not like myself\"",                               group="flags",      rtype="boolean_yes_no", polarity="higher_worse",  domains=["Depression","Mania","Psychosis"],      order=320),
    dict(code="flag_mood_shift",          text="I noticed a sudden mood shift",                                       group="flags",      rtype="boolean_yes_no", polarity="higher_worse",  domains=["Depression","Mania","Psychosis","Mixed"], order=330),
    dict(code="flag_missed_medication",   text="I missed medication",                                                 group="flags",      rtype="boolean_yes_no", polarity="higher_worse",  domains=["Depression","Mania","Psychosis"],      order=340),
    dict(code="flag_sleep_medication",    text="I took sleeping or anti-anxiety medication",                          group="flags",      rtype="boolean_yes_no", polarity="higher_worse",  domains=[],                                     order=350),
    dict(code="flag_routine_disruption",  text="There were significant disruptions to my routine",                   group="flags",      rtype="boolean_yes_no", polarity="higher_worse",  domains=["Depression","Mania","Psychosis","Mixed"], order=360),
    dict(code="flag_physiological_stress",text="I had a major physiological stress",                                 group="flags",      rtype="boolean_yes_no", polarity="higher_worse",  domains=["Depression","Mania","Psychosis"],      order=370),
    dict(code="flag_psychological_stress",text="I had a major psychological stress",                                 group="flags",      rtype="boolean_yes_no", polarity="higher_worse",  domains=["Depression","Mania","Psychosis"],      order=380),
    # OBSERVATIONS
    dict(code="obs_up_now",      text="Observations [I feel like I'm experiencing an up]",           group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Mania"],             order=390),
    dict(code="obs_down_now",    text="Observations [I feel like I'm experiencing a down]",          group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression"],        order=400),
    dict(code="obs_mixed_now",   text="Observations [I feel like I'm experiencing a mixed]",         group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Psychosis","Mixed"], order=410),
    dict(code="obs_up_coming",   text="Observations [I feel like I'm going to experience an up]",    group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Mania"],             order=420),
    dict(code="obs_down_coming", text="Observations [I feel like I'm going to experience a down]",   group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression"],        order=430),
    dict(code="obs_mixed_coming",text="Observations [I feel like I'm going to experience a mixed]",  group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Psychosis","Mixed"], order=440),
    # NOTES
    dict(code="experience_description", text="How would I describe my experiences?", group="notes", rtype="text", polarity="not_applicable", domains=[], order=470),
]

for _q in QUESTION_CATALOG:
    _q.setdefault("score_in_snapshot", True)
    _q.setdefault("score_in_daily", True)

DOMAINS = ["Depression", "Mania", "Psychosis", "Mixed"]

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
        and weights.get(q["code"], 0) > 0
        and (not snapshot or q.get("score_in_snapshot", True))
    ]
    if not codes:
        return pd.Series(0.0, index=frame.index)
    num = sum(frame[c].fillna(0.0) * weights.get(c, 0.0) for c in codes)
    den = sum(weights.get(c, 0.0) for c in codes)
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
    by_code = _catalog_by_code()
    for code, meta in by_code.items():
        if code in src.columns and meta["rtype"] != "text":
            src[f"_n_{code}"] = _normalise(src[code], meta)
    norm_frame = src.copy()
    for code in by_code:
        if f"_n_{code}" in norm_frame.columns:
            norm_frame[code] = norm_frame[f"_n_{code}"]
    for domain in DOMAINS:
        src[f"{domain} Score %"] = _domain_score(norm_frame, domain, weights, snapshot=not daily_only)
    src["Overall Score %"] = src[[f"{d} Score %" for d in DOMAINS]].mean(axis=1)
    src = src.drop(columns=[c for c in src.columns if c.startswith("_n_")])
    if daily_only:
        src = src.rename(columns={"submitted_date": "date"})
        for col in [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]:
            src[f"{col} Delta"] = src[col].diff()
    return src.reset_index(drop=True)

# ──────────────────────────────────────────────────────────
# BASELINE BANDS — LOAD / SAVE
# ──────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_baseline_config() -> dict:
    """
    Returns dict with keys:
      bands: {domain: {well, watch, caution, warning}}
      movement_threshold: float
      personal_baseline_window: int  (days)
    """
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
    for domain, bands in config["bands"].items():
        for band, value in bands.items():
            rows.append([domain, band, value, ""])
    rows.append(["", "", "", ""])
    rows.append(["", "", config["movement_threshold"], "movement_threshold"])
    rows.append(["", "", config["personal_baseline_window"], "personal_baseline_window"])
    ws.clear()
    ws.update("A1", rows)
    load_baseline_config.clear()
    return True, "Baseline config saved."

# ──────────────────────────────────────────────────────────
# PERSONAL BASELINE COMPUTATION
# ──────────────────────────────────────────────────────────
def compute_personal_baseline(
    daily: pd.DataFrame,
    bands: dict[str, dict[str, float]],
    window_days: int = 90,
) -> dict[str, dict]:
    """
    Identify days where ALL domains fall within the 'well' band,
    then compute mean +/- 1 SD per domain over the most recent `window_days`
    such days. Returns:
      {domain: {mean, sd, n, lower (mean-sd), upper (mean+sd), reliable}}
    """
    result: dict[str, dict] = {}
    empty = dict(mean=None, sd=None, n=0, lower=None, upper=None, reliable=False)

    if daily.empty:
        return {d: empty.copy() for d in DOMAINS}

    # A "well day" is one where every domain score is at or below its well ceiling
    mask = pd.Series(True, index=daily.index)
    for domain in DOMAINS:
        col = f"{domain} Score %"
        if col in daily.columns:
            ceiling = bands.get(domain, {}).get("well", 20.0)
            mask &= daily[col].fillna(999) <= ceiling

    well_days = daily[mask].sort_values("date").tail(window_days)

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
            mean=round(mean, 1),
            sd=round(sd, 2),
            n=n,
            lower=round(mean - sd, 1),
            upper=round(mean + sd, 1),
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

BAND_EMOJI = {
    "well": "🟢", "watch": "🟡", "caution": "🟠",
    "warning": "🔴", "critical": "🟣", "unknown": "⚪",
}
BAND_COLOUR_HEX = {
    "well": "#34C759", "watch": "#FFCC00", "caution": "#FF9500",
    "warning": "#FF3B30", "critical": "#AF52DE", "unknown": "#8E8E93",
}

# ──────────────────────────────────────────────────────────
# PLOTLY CHARTS
# ──────────────────────────────────────────────────────────
def make_band_chart(
    daily: pd.DataFrame,
    domain: str,
    bands: dict,
    personal: dict | None = None,
    movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD,
    height: int = 320,
) -> go.Figure:
    """
    Plotly line chart for one domain with:
      - Coloured band overlays (well / watch / caution / warning / critical)
      - Personal baseline mean line + +/-1 SD shaded envelope (if reliable)
      - Movement alert markers (large day-on-day delta even within the well band)
    """
    col = f"{domain} Score %"
    if col not in daily.columns or daily.empty:
        return go.Figure()

    dates  = daily["date"].astype(str).tolist()
    scores = daily[col].tolist()
    b = bands.get(domain, DEFAULT_BASELINE_BANDS.get(domain, {}))
    well_c    = b.get("well",    20)
    watch_c   = b.get("watch",   40)
    caution_c = b.get("caution", 60)
    warning_c = b.get("warning", 75)

    fig = go.Figure()

    # Band fill rectangles
    for label, y0, y1, colour in [
        ("Well",     0,          well_c,    BAND_COLOURS["well"]),
        ("Watch",    well_c,     watch_c,   BAND_COLOURS["watch"]),
        ("Caution",  watch_c,    caution_c, BAND_COLOURS["caution"]),
        ("Warning",  caution_c,  warning_c, BAND_COLOURS["warning"]),
        ("Critical", warning_c,  100,       BAND_COLOURS["critical"]),
    ]:
        fig.add_hrect(
            y0=y0, y1=y1, fillcolor=colour, line_width=0,
            annotation_text=label, annotation_position="right",
            annotation_font_size=10,
            annotation_font_color=BAND_COLOUR_HEX.get(label.lower(), "#888"),
        )

    # Band threshold lines
    for label, ceil in [("well", well_c), ("watch", watch_c),
                         ("caution", caution_c), ("warning", warning_c)]:
        fig.add_hline(y=ceil, line_dash="dot",
                      line_color=BAND_LINE_COLOURS[label], line_width=1)

    # Personal baseline envelope
    if personal:
        pb = personal.get(domain, {})
        if pb.get("reliable") and pb.get("mean") is not None:
            fig.add_hline(
                y=pb["mean"],
                line_dash="solid", line_color="rgba(90,130,230,0.8)", line_width=1.5,
                annotation_text=f"Your baseline ({pb['n']}d)",
                annotation_position="left",
                annotation_font_size=10,
                annotation_font_color="rgba(90,130,230,1)",
            )
            if pb.get("lower") is not None:
                fig.add_hrect(
                    y0=pb["lower"], y1=pb["upper"],
                    fillcolor="rgba(90,130,230,0.08)",
                    line=dict(color="rgba(90,130,230,0.3)", width=1, dash="dot"),
                    annotation_text="+/-1 SD", annotation_position="left",
                    annotation_font_size=9,
                )

    # Main score line
    delta_col = f"{col} Delta"
    deltas = daily[delta_col].tolist() if delta_col in daily.columns else [0.0] * len(scores)

    fig.add_trace(go.Scatter(
        x=dates, y=scores, mode="lines+markers",
        name=domain,
        line=dict(color="#1C7EF2", width=2),
        marker=dict(size=5, color="#1C7EF2"),
        hovertemplate="%{x}<br>Score: %{y:.1f}%<extra></extra>",
    ))

    # Movement alert markers: large delta but score still within well band
    alert_x, alert_y = [], []
    for i, (s, d) in enumerate(zip(scores, deltas)):
        if d is not None and not (isinstance(d, float) and np.isnan(d)):
            if abs(d) >= movement_threshold:
                if s is not None and not (isinstance(s, float) and np.isnan(s)) and s <= well_c:
                    alert_x.append(dates[i])
                    alert_y.append(s)

    if alert_x:
        fig.add_trace(go.Scatter(
            x=alert_x, y=alert_y, mode="markers",
            name="Movement alert",
            marker=dict(symbol="triangle-up", size=12, color="#FF9500",
                        line=dict(color="white", width=1)),
            hovertemplate="%{x}<br>%{y:.1f}% — notable movement<extra></extra>",
        ))

    fig.update_layout(
        height=height,
        margin=dict(l=10, r=90, t=30, b=10),
        yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
        xaxis=dict(title=None),
        showlegend=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(size=12),
        title=dict(text=domain, font=dict(size=14, color="#1C1C1E"), x=0),
    )
    return fig

def make_overview_chart(daily: pd.DataFrame, bands: dict, height: int = 380) -> go.Figure:
    """Multi-domain line chart with well-ceiling reference lines."""
    if daily.empty:
        return go.Figure()
    fig = go.Figure()
    colours = {"Depression": "#FF3B30", "Mania": "#FF9500",
               "Psychosis":  "#AF52DE", "Mixed": "#1C7EF2"}
    dates = daily["date"].astype(str).tolist()
    for d in DOMAINS:
        col = f"{d} Score %"
        if col not in daily.columns:
            continue
        fig.add_trace(go.Scatter(
            x=dates, y=daily[col].tolist(), mode="lines", name=d,
            line=dict(color=colours[d], width=2),
            hovertemplate=f"{d}: %{{y:.1f}}%<extra></extra>",
        ))
    # Well ceiling reference lines
    for d in DOMAINS:
        b = bands.get(d, DEFAULT_BASELINE_BANDS.get(d, {}))
        fig.add_hline(y=b.get("well", 20), line_dash="dot",
                      line_color="rgba(52,199,89,0.4)", line_width=1)
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(range=[0, 100], title="Score %", ticksuffix="%"),
        xaxis=dict(title=None),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    return fig

# ──────────────────────────────────────────────────────────
# WARNINGS  (now baseline-aware)
# ──────────────────────────────────────────────────────────
def build_warnings(
    daily: pd.DataFrame,
    snapshots: pd.DataFrame,
    bands: dict,
    movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD,
) -> pd.DataFrame:
    rows: list[dict] = []

    def _check_row(row: pd.Series, source: str) -> None:
        for domain in DOMAINS:
            score = float(row.get(f"{domain} Score %", 0) or 0)
            delta = float(row.get(f"{domain} Score % Delta", 0) or 0)
            band  = classify_score(score, domain, bands)
            if band in ("warning", "critical"):
                rows.append(dict(source=source, domain=domain, severity="High",
                    score_pct=round(score, 1), delta=round(delta, 1), band=band,
                    message=f"{domain} score {score:.1f}% — {band} band"))
            elif band == "caution":
                rows.append(dict(source=source, domain=domain, severity="Medium",
                    score_pct=round(score, 1), delta=round(delta, 1), band=band,
                    message=f"{domain} score {score:.1f}% — caution band"))
            if band == "well" and abs(delta) >= movement_threshold:
                rows.append(dict(source=source, domain=domain, severity="Movement",
                    score_pct=round(score, 1), delta=round(delta, 1), band=band,
                    message=f"{domain} moved {delta:+.1f}pp (still in well band)"))

    if not daily.empty:
        _check_row(daily.sort_values("date").iloc[-1], "Daily")
    if not snapshots.empty:
        _check_row(snapshots.sort_values("submitted_at").iloc[-1], "Snapshot")

    if not rows:
        return pd.DataFrame(columns=["source","domain","severity","score_pct","delta","band","message"])
    order = {"High": 0, "Medium": 1, "Movement": 2}
    df = pd.DataFrame(rows)
    df["_o"] = df["severity"].map(order).fillna(9)
    return df.sort_values("_o").drop(columns=["_o"]).reset_index(drop=True)

# ──────────────────────────────────────────────────────────
# WEIGHTS — PERSISTENCE
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

def _generate_insights(
    daily: pd.DataFrame,
    risk: dict[str, float],
    trends: dict[str, str],
    bands: dict,
    personal: dict,
    movement_threshold: float,
) -> list[dict]:
    insights: list[dict] = []

    for domain in DOMAINS:
        r    = risk.get(domain, 0)
        t    = trends.get(domain, "stable")
        band = classify_score(r, domain, bands)

        if band in ("warning", "critical"):
            insights.append(dict(level="warning", domain=domain,
                text=f"**{domain}** momentum score is {r:.0f}% — in the **{band}** band."))
        elif band == "caution":
            insights.append(dict(level="caution", domain=domain,
                text=f"**{domain}** momentum score {r:.0f}% is in the **caution** band."))

        if t == "rising" and band != "well":
            insights.append(dict(level="caution", domain=domain,
                text=f"**{domain}** has been trending upward over the last 7 days."))

        # Above personal baseline upper bound — alert even if within standard well band
        pb = personal.get(domain, {})
        if pb.get("reliable") and pb.get("upper") is not None:
            if r > pb["upper"] and band == "well":
                insights.append(dict(level="caution", domain=domain,
                    text=f"**{domain}** momentum score ({r:.0f}%) is above your personal "
                         f"baseline upper bound ({pb['upper']}%). This is above your normal "
                         f"range even though it falls within the standard well band."))

    # Self-harm standalone flag
    if not daily.empty and "dep_self_harm_ideation" in daily.columns:
        peak = daily.tail(7)["dep_self_harm_ideation"].max()
        if pd.notna(peak) and peak > SELF_HARM_FLAG_THRESHOLD:
            insights.append(dict(level="critical", domain="Depression",
                text=f"Self-harm ideation reached **{peak:.0f}/5** in the last 7 days. "
                     f"Please review with your clinician regardless of overall score."))

    # Sleep
    if not daily.empty and "func_sleep_hours" in daily.columns:
        mean_sleep = daily.tail(7)["func_sleep_hours"].mean()
        if pd.notna(mean_sleep) and mean_sleep < 5.5:
            insights.append(dict(level="caution", domain="General",
                text=f"Mean sleep over the last 7 days is **{mean_sleep:.1f} hours** — below threshold."))

    # Movement alerts
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
                    text=f"**{domain}** moved **{delta:+.1f}pp** since yesterday. Score is still "
                         f"in the well band ({score:.1f}%), but this is a notable shift."))

    if not insights:
        insights.append(dict(level="ok", domain="General",
            text="No alerts. All domain scores are within expected ranges."))

    return insights

# ──────────────────────────────────────────────────────────
# SETTINGS UI
# ──────────────────────────────────────────────────────────
def render_weights_editor(weights: dict[str, float]) -> dict[str, float]:
    st.markdown("### Scoring weights")
    if not safe_worksheet(SETTINGS_TAB):
        st.warning(f"Worksheet '{SETTINGS_TAB}' not found — weights are in-memory only.")
    cat     = catalog_df()
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
    st.caption(
        "Each value is the **upper bound** of that band (0–100 scale). "
        "Anything above the Warning ceiling is Critical. "
        "Bands must be in ascending order: Well < Watch < Caution < Warning."
    )
    if not safe_worksheet(BASELINE_TAB):
        st.warning(f"Worksheet '{BASELINE_TAB}' not found — changes are in-memory only.")

    updated = {
        "bands": {d: v.copy() for d, v in config["bands"].items()},
        "movement_threshold": config["movement_threshold"],
        "personal_baseline_window": config["personal_baseline_window"],
    }

    for domain in DOMAINS:
        with st.expander(f"{domain}", expanded=True):
            b = updated["bands"][domain]
            cols = st.columns(4)
            b["well"]    = cols[0].number_input("Well ceiling",    0.0, 100.0, float(b["well"]),    0.5, key=f"bl_{domain}_well")
            b["watch"]   = cols[1].number_input("Watch ceiling",   0.0, 100.0, float(b["watch"]),   0.5, key=f"bl_{domain}_watch")
            b["caution"] = cols[2].number_input("Caution ceiling", 0.0, 100.0, float(b["caution"]), 0.5, key=f"bl_{domain}_caution")
            b["warning"] = cols[3].number_input("Warning ceiling", 0.0, 100.0, float(b["warning"]), 0.5, key=f"bl_{domain}_warning")
            vals = [b["well"], b["watch"], b["caution"], b["warning"]]
            if vals != sorted(vals):
                st.warning("Band ceilings must be in ascending order.")

    st.divider()
    st.markdown("### Movement alert threshold")
    st.caption(
        "A day-on-day change at or above this value (percentage points) will trigger "
        "a movement alert, even if the score is still within the well band."
    )
    updated["movement_threshold"] = st.number_input(
        "Movement threshold (pp)", 1.0, 50.0,
        float(updated["movement_threshold"]), 0.5, key="bl_movement",
    )

    st.divider()
    st.markdown("### Personal baseline window")
    st.caption(
        f"Number of most-recent **well days** to include when computing your personal "
        f"baseline mean and SD. Baseline is marked reliable once "
        f"{PERSONAL_BASELINE_MIN_DAYS} or more qualifying days exist."
    )
    updated["personal_baseline_window"] = st.number_input(
        "Window (days)", 14, 365,
        int(updated["personal_baseline_window"]), 1, key="bl_window",
    )

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save baseline config", type="primary"):
            ok, msg = save_baseline_config(updated)
            (st.success if ok else st.error)(msg)
    with c2:
        if st.button("Reset baseline to defaults"):
            default_cfg = {
                "bands": {d: v.copy() for d, v in DEFAULT_BASELINE_BANDS.items()},
                "movement_threshold": DEFAULT_MOVEMENT_THRESHOLD,
                "personal_baseline_window": 90,
            }
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
daily_df     = build_scored_table(wide_df, weights, daily_only=True)
snapshots_df = build_scored_table(wide_df, weights, daily_only=False)
warnings_df  = build_warnings(daily_df, snapshots_df, bands, mv_threshold)
personal_bl  = compute_personal_baseline(daily_df, bands, pb_window)

# ──────────────────────────────────────────────────────────
# SUMMARY METRICS ROW
# ──────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total entries",   len(raw_df))
m2.metric("Days tracked",    len(daily_df))
m3.metric("Snapshot rows",   len(snapshots_df))
m4.metric("Active warnings", int(len(warnings_df[warnings_df["severity"] == "High"])) if not warnings_df.empty else 0)
if not daily_df.empty:
    lo = float(daily_df["Overall Score %"].iloc[-1])
    pr = float(daily_df["Overall Score %"].iloc[-2]) if len(daily_df) > 1 else lo
    m5.metric("Latest overall score", f"{lo:.1f}%", delta=f"{lo - pr:+.1f}%")
else:
    m5.metric("Latest overall score", "—")

# ──────────────────────────────────────────────────────────
# DOMAIN BAND STATUS ROW
# ──────────────────────────────────────────────────────────
if not daily_df.empty:
    latest = daily_df.sort_values("date").iloc[-1]
    status_cols = st.columns(len(DOMAINS))
    for i, domain in enumerate(DOMAINS):
        score = float(latest.get(f"{domain} Score %", 0) or 0)
        band  = classify_score(score, domain, bands)
        delta = float(latest.get(f"{domain} Score % Delta", 0) or 0)
        pb    = personal_bl.get(domain, {})
        pb_note = ""
        if pb.get("reliable") and pb.get("mean") is not None:
            diff = score - pb["mean"]
            pb_note = f"\n*vs your baseline: {diff:+.1f}pp*"
        status_cols[i].markdown(
            f"**{domain}**  \n"
            f"{BAND_EMOJI[band]} **{band.upper()}** — {score:.1f}%  \n"
            f"Δ {delta:+.1f}pp{pb_note}"
        )

st.divider()

# ──────────────────────────────────────────────────────────
# TABS
# ──────────────────────────────────────────────────────────
tab_overview, tab_analysis, tab_baseline, tab_daily, tab_snapshots, tab_data, tab_settings = st.tabs([
    "Overview", "Analysis", "Baselines", "Daily Model", "Snapshots", "Data Layer", "Settings"
])

# ── OVERVIEW ──────────────────────────────────────────────
with tab_overview:
    st.markdown("### Alerts")
    if warnings_df.empty:
        st.success("No active alerts.")
    else:
        sev_icon = {"High": "🔴", "Medium": "🟡", "Movement": "🟠"}
        for _, w in warnings_df.iterrows():
            st.markdown(f"{sev_icon.get(w['severity'], 'ℹ️')} **{w['domain']}** ({w['source']}) — {w['message']}")

    if not daily_df.empty:
        st.markdown("### All domains over time")
        st.caption("Dotted green lines mark the Well band ceiling for each domain.")
        st.plotly_chart(make_overview_chart(daily_df, bands), use_container_width=True)

        st.markdown("### Per-domain detail with band overlays")
        c1, c2 = st.columns(2)
        for i, domain in enumerate(DOMAINS):
            with (c1 if i % 2 == 0 else c2):
                st.plotly_chart(
                    make_band_chart(daily_df, domain, bands,
                                    personal=personal_bl,
                                    movement_threshold=mv_threshold),
                    use_container_width=True,
                )

# ── ANALYSIS ──────────────────────────────────────────────
with tab_analysis:
    st.markdown("## Data Analysis")
    if daily_df.empty:
        st.info("No data yet.")
    else:
        risk   = _episode_risk_score(daily_df)
        trends = {d: _rolling_trend(daily_df[f"{d} Score %"]) for d in DOMAINS}

        st.markdown("### Insights")
        insights  = _generate_insights(daily_df, risk, trends, bands, personal_bl, mv_threshold)
        lv_icon   = {"critical": "🚨", "warning": "⚠️", "caution": "💛", "ok": "✅"}
        for ins in insights:
            st.markdown(f"{lv_icon.get(ins['level'], 'ℹ️')} {ins['text']}")

        st.divider()
        st.markdown("### Momentum-weighted episode risk (last 7 days)")
        st.caption("Weighted toward the most recent days. Band shown in parentheses.")
        rc = st.columns(len(DOMAINS))
        for i, domain in enumerate(DOMAINS):
            r    = risk[domain]
            band = classify_score(r, domain, bands)
            rc[i].metric(domain, f"{r:.1f}%",
                         delta=f"{BAND_EMOJI[band]} {band}", delta_color="off")

        st.divider()
        st.markdown("### 7-day trend vs baseline")
        pb_rows = []
        for d in DOMAINS:
            pb = personal_bl.get(d, {})
            trend_raw = trends[d]
            trend_display = {"rising": "rising ↑", "falling": "falling ↓", "stable": "stable →"}.get(trend_raw, trend_raw)
            pb_rows.append({
                "Domain": d,
                "7d Trend": trend_display,
                "7d Mean %": round(daily_df[f"{d} Score %"].tail(7).mean(), 1),
                "7d Peak %": round(daily_df[f"{d} Score %"].tail(7).max(), 1),
                "Personal Baseline": f"{pb['mean']}%" if pb.get("reliable") else "not yet reliable",
                "Baseline +/-1 SD":  f"{pb['lower']}–{pb['upper']}%" if pb.get("reliable") else "—",
                "Well Ceiling": f"{bands.get(d, {}).get('well', '?')}%",
            })
        st.dataframe(pd.DataFrame(pb_rows), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Cross-domain correlation")
        corr = _cross_domain_correlation(daily_df)
        if not corr.empty:
            st.caption("Pearson r across all daily entries. Near 1 = co-move; near 0 = independent.")
            st.dataframe(corr.style.background_gradient(cmap="RdYlGn_r", vmin=-1, vmax=1),
                         use_container_width=True)
        else:
            st.info("Need at least 4 days of data for correlation.")

        st.divider()
        st.markdown("### Top contributing symptom items (all-time mean)")
        for domain in DOMAINS:
            with st.expander(domain):
                df_peak = _peak_symptom_items(daily_df, domain)
                if df_peak.empty:
                    st.write("No data.")
                else:
                    df_peak = df_peak.rename(columns={"mean_raw": "Mean rating (1-5)", "question": "Question"})
                    st.dataframe(df_peak[["Question", "Mean rating (1-5)"]], use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Flag impact on domain scores")
        imp = _flag_impact(daily_df)
        if imp.empty:
            st.info("Not enough flag data.")
        else:
            st.caption("Impact = mean domain score on days a flag was triggered minus days it was not.")
            top = imp[imp["impact"].abs() > 2].assign(
                impact=lambda df: df["impact"].round(1),
                mean_when_flagged=lambda df: df["mean_when_flagged"].round(1),
                mean_when_not_flagged=lambda df: df["mean_when_not_flagged"].round(1),
            )
            st.dataframe(top if not top.empty else pd.DataFrame({"Note": ["No flags with impact > 2pp"]}),
                         use_container_width=True, hide_index=True)

        st.divider()
        if "func_sleep_hours" in daily_df.columns:
            st.markdown("### Sleep analysis")
            sleep = daily_df[["date","func_sleep_hours","func_sleep_quality"]].dropna(subset=["func_sleep_hours"])
            if not sleep.empty:
                s1, s2, s3 = st.columns(3)
                s1.metric("Mean sleep (hrs)", f"{sleep['func_sleep_hours'].mean():.1f}")
                s2.metric("Nights < 6 hrs",   int((sleep["func_sleep_hours"] < 6).sum()))
                s3.metric("Nights > 9 hrs",   int((sleep["func_sleep_hours"] > 9).sum()))
                st.line_chart(sleep.set_index("date")[["func_sleep_hours"]])

# ── BASELINES ─────────────────────────────────────────────
with tab_baseline:
    st.markdown("## Baselines")

    # Personal baseline status cards
    st.markdown("### Your personal baseline")
    st.caption(
        f"Derived from days where **all** domains fell within their Well band. "
        f"Uses the most recent **{pb_window}** such days. "
        f"Requires at least **{PERSONAL_BASELINE_MIN_DAYS}** qualifying days to be reliable."
    )
    pb_cols = st.columns(len(DOMAINS))
    for i, domain in enumerate(DOMAINS):
        pb = personal_bl.get(domain, {})
        with pb_cols[i]:
            st.markdown(f"**{domain}**")
            if pb.get("reliable"):
                st.metric("Baseline mean", f"{pb['mean']}%")
                well_ceil = bands.get(domain, {}).get("well", 20)
                if pb["upper"] > well_ceil:
                    st.caption(
                        f"+/-1 SD: {pb['lower']}–{pb['upper']}%  \n"
                        f"Based on {pb['n']} well days  \n"
                        f"Note: your upper SD bound ({pb['upper']}%) exceeds the "
                        f"Well ceiling ({well_ceil}%), suggesting your 'normal' "
                        f"sits toward the upper end of the well band."
                    )
                else:
                    st.caption(f"+/-1 SD: {pb['lower']}–{pb['upper']}%  \nBased on {pb['n']} well days")
            else:
                n      = pb.get("n", 0)
                needed = max(0, PERSONAL_BASELINE_MIN_DAYS - n)
                st.info(f"Not yet reliable  \n{n} well days so far  \n{needed} more needed")

    st.divider()

    # Charts with overlays
    st.markdown("### Score history with band and baseline overlays")
    st.caption(
        "**Coloured bands**: green = Well, yellow = Watch, orange = Caution, red = Warning, purple = Critical.  \n"
        "**Blue line**: your personal baseline mean.  "
        "**Blue shading**: +/-1 SD (your normal variation on well days).  \n"
        "**Orange triangle**: movement alert — a notable shift even while in the well band."
    )
    if not daily_df.empty:
        for domain in DOMAINS:
            st.plotly_chart(
                make_band_chart(daily_df, domain, bands,
                                personal=personal_bl,
                                movement_threshold=mv_threshold,
                                height=300),
                use_container_width=True,
            )
    else:
        st.info("No data yet.")

    st.divider()

    # Band reference table
    st.markdown("### Current band thresholds")
    ref_rows = []
    for domain in DOMAINS:
        b = bands.get(domain, {})
        ref_rows.append({
            "Domain": domain,
            "Well":     f"0 – {b.get('well', '?')}%",
            "Watch":    f"{b.get('well', '?')} – {b.get('watch', '?')}%",
            "Caution":  f"{b.get('watch', '?')} – {b.get('caution', '?')}%",
            "Warning":  f"{b.get('caution', '?')} – {b.get('warning', '?')}%",
            "Critical": f"{b.get('warning', '?')} – 100%",
        })
    st.dataframe(pd.DataFrame(ref_rows), use_container_width=True, hide_index=True)

    st.divider()

    # Editor
    st.markdown("### Edit thresholds")
    bl_config    = render_baseline_editor(bl_config)
    bands        = bl_config["bands"]
    mv_threshold = bl_config["movement_threshold"]
    pb_window    = bl_config["personal_baseline_window"]

# ── DAILY MODEL ───────────────────────────────────────────
with tab_daily:
    st.markdown("### Daily model — first submission per day")
    st.dataframe(daily_df, use_container_width=True)
    if not daily_df.empty:
        delta_cols = [c for c in daily_df.columns if c.endswith(" Delta") and "Score" in c]
        if delta_cols:
            st.markdown("### Day-on-day deltas")
            st.dataframe(daily_df[["date"] + delta_cols], use_container_width=True)

# ── SNAPSHOTS ─────────────────────────────────────────────
with tab_snapshots:
    st.markdown("### Snapshot model — all submissions")
    st.dataframe(snapshots_df, use_container_width=True)
    if not snapshots_df.empty:
        score_cols = [f"{d} Score %" for d in DOMAINS]
        st.line_chart(snapshots_df.set_index("submitted_at")[score_cols])

# ── DATA LAYER ────────────────────────────────────────────
with tab_data:
    st.markdown("### Question catalog")
    display_cols = ["code","text","group","rtype","polarity","domains",
                    "score_in_snapshot","score_in_daily","order"]
    st.dataframe(catalog_df()[display_cols], use_container_width=True)
    with st.expander("Wide submission table"):
        st.dataframe(wide_df, use_container_width=True)
    with st.expander("Raw worksheet"):
        st.dataframe(raw_df, use_container_width=True)
        st.caption(f"Columns: {list(raw_df.columns)}")

# ── SETTINGS ─────────────────────────────────────────────
with tab_settings:
    weights = render_weights_editor(weights)
