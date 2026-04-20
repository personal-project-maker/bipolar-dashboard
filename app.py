"""
Wellbeing Dashboard — streamlined + data analysis layer.

Changes vs original:
  • Auth, GSheets, and caching helpers consolidated at top
  • QUESTION_CATALOG is the single source of truth; no parallel DOMAIN_MAP duplication
  • Scoring pipeline is a single pass (component → domain → overall)
  • Normalisation logic unified into one function
  • Data-analysis tab: trend detection, cross-domain correlation, episode-risk
    scoring, and plain-English insight cards
  • Warnings logic tightened and deduplicated
"""

import streamlit as st
import pandas as pd
import numpy as np
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
SHEET_NAME    = "Bipolar Dashboard"
NEW_FORM_TAB  = "Updated Bipolar Form"
SETTINGS_TAB  = "Scoring Settings"


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
# QUESTION CATALOG
# ──────────────────────────────────────────────────────────
# Each entry is the single source of truth for a question.
# domain_membership lists which scoring domains it feeds.
QUESTION_CATALOG: list[dict[str, Any]] = [
    # ── DEPRESSION ────────────────────────────────────────
    dict(code="dep_low_mood",          text="Have I felt a low mood?",                                                group="depression", rtype="scale_1_5",      polarity="higher_worse", domains=["Depression"],                    order=10),
    dict(code="dep_slowed_low_energy", text="Have I felt slowed down or low on energy?",                             group="depression", rtype="scale_1_5",      polarity="higher_worse", domains=["Depression"],                    order=20),
    dict(code="dep_low_motivation",    text="Have I felt low on motivation or had difficulty initiating tasks?",      group="depression", rtype="scale_1_5",      polarity="higher_worse", domains=["Depression"],                    order=30),
    dict(code="dep_anhedonia",         text="Have I felt a lack of interest or pleasure in activities?",              group="depression", rtype="scale_1_5",      polarity="higher_worse", domains=["Depression"],                    order=40),
    dict(code="dep_withdrawal",        text="Have I been socially or emotionally withdrawn?",                         group="depression", rtype="scale_1_5",      polarity="higher_worse", domains=["Depression"],                    order=50),
    dict(code="dep_self_harm_ideation",text="Have I had ideation around self-harming or suicidal behaviours?",        group="depression", rtype="scale_1_5",      polarity="higher_worse", domains=["Depression"],                    order=60),
    # ── MANIA ─────────────────────────────────────────────
    dict(code="man_elevated_mood",     text="Have I felt an elevated mood?",                                          group="mania",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mania"],                         order=70),
    dict(code="man_sped_up_high_energy",text="Have I felt sped up or high on energy?",                               group="mania",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mania","Mixed"],                 order=80),
    dict(code="man_racing_thoughts",   text="Have I had racing thoughts or speech?",                                  group="mania",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mania"],                         order=90),
    dict(code="man_goal_drive",        text="Have I had an increased drive towards goal-directed activity?",           group="mania",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mania"],                         order=100),
    dict(code="man_impulsivity",       text="Have I felt impulsivity or an urge to take risky actions?",              group="mania",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mania"],                         order=110),
    dict(code="man_agitation",         text="Have I felt agitated or restless?",                                      group="mania",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mania","Mixed"],                 order=120),
    dict(code="man_irritability",      text="Have I been more irritable and reactive than normal?",                   group="mania",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mania","Mixed"],                 order=130),
    dict(code="man_cant_settle",       text="Have I been unable to settle or switch off?",                            group="mania",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mania"],                         order=140),
    # ── MIXED ─────────────────────────────────────────────
    dict(code="mix_high_energy_low_mood",   text="Have I had a high energy combined with low mood?",                  group="mixed",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mixed"],                         order=150),
    dict(code="mix_rapid_emotional_shifts", text="Have I experienced rapid emotional shifts?",                        group="mixed",      rtype="scale_1_5",      polarity="higher_worse", domains=["Mixed"],                         order=160),
    # ── PSYCHOSIS ─────────────────────────────────────────
    dict(code="psy_heard_saw",          text="Have I heard or seen things others didn't?",                            group="psychosis",  rtype="scale_1_5",      polarity="higher_worse", domains=["Psychosis"],                     order=170),
    dict(code="psy_suspicious",         text="Have I felt watched, followed, targeted or suspicious?",                group="psychosis",  rtype="scale_1_5",      polarity="higher_worse", domains=["Psychosis"],                     order=180),
    dict(code="psy_trust_perceptions",  text="Have I had trouble trusting my perceptions and thoughts?",              group="psychosis",  rtype="scale_1_5",      polarity="higher_worse", domains=["Psychosis"],                     order=190),
    dict(code="psy_confidence_reality", text="How confident have I been in the reality of these experiences?",        group="psychosis",  rtype="scale_1_5",      polarity="higher_worse", domains=["Psychosis"],                     order=200),
    dict(code="psy_distress",           text="How distressed have I been by these beliefs and experiences?",          group="psychosis",  rtype="scale_1_5",      polarity="higher_worse", domains=["Psychosis"],                     order=210),
    # ── FUNCTIONING ───────────────────────────────────────
    dict(code="func_work",              text="How effectively have I been functioning at work?",                      group="functioning",rtype="scale_1_5",      polarity="higher_better",domains=["Depression","Mania"],             order=220),
    dict(code="func_daily",             text="How well have I been functioning in my daily life?",                    group="functioning",rtype="scale_1_5",      polarity="higher_better",domains=["Depression","Mania"],             order=230),
    dict(code="func_sleep_hours",       text="How many hours did I sleep last night?",                                group="functioning",rtype="numeric",        polarity="custom_sleep", domains=["Depression","Mania","Mixed"],    order=450, score_in_snapshot=False),
    dict(code="func_sleep_quality",     text="How poor was my sleep quality last night",                              group="functioning",rtype="scale_1_5",      polarity="higher_worse", domains=["Depression","Mania","Mixed"],    order=460, score_in_snapshot=False),
    # ── META ──────────────────────────────────────────────
    dict(code="meta_unlike_self",            text="Do I feel unlike my usual self?",                                  group="meta",       rtype="scale_1_5",      polarity="higher_worse", domains=[],                                order=240),
    dict(code="meta_something_wrong",        text="Do I think something may be wrong or changing?",                  group="meta",       rtype="scale_1_5",      polarity="higher_worse", domains=[],                                order=250),
    dict(code="meta_concerned",              text="Am I concerned about my current state?",                           group="meta",       rtype="scale_1_5",      polarity="higher_worse", domains=[],                                order=260),
    dict(code="meta_disorganised_thoughts",  text="Do my thoughts feel disorganised or hard to follow?",              group="meta",       rtype="scale_1_5",      polarity="higher_worse", domains=[],                                order=270),
    dict(code="meta_attention_unstable",     text="Is my attention unstable or jumping?",                             group="meta",       rtype="scale_1_5",      polarity="higher_worse", domains=[],                                order=280),
    dict(code="meta_driven_without_thinking",text="Do I feel driven to act without thinking?",                        group="meta",       rtype="scale_1_5",      polarity="higher_worse", domains=[],                                order=290),
    dict(code="meta_intensifying",           text="Is my state intensifying (in any direction)?",                     group="meta",       rtype="scale_1_5",      polarity="higher_worse", domains=[],                                order=300),
    dict(code="meta_towards_episode",        text="Do I feel like I'm moving towards an episode?",                    group="meta",       rtype="scale_1_5",      polarity="higher_worse", domains=[],                                order=310),
    # ── FLAGS ─────────────────────────────────────────────
    dict(code="flag_not_myself",          text='I\'ve been feeling "not like myself"',                                group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis"], order=320),
    dict(code="flag_mood_shift",          text="I noticed a sudden mood shift",                                       group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis","Mixed"], order=330),
    dict(code="flag_missed_medication",   text="I missed medication",                                                 group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis"], order=340),
    dict(code="flag_sleep_medication",    text="I took sleeping or anti-anxiety medication",                          group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=[],                                order=350),
    dict(code="flag_routine_disruption",  text="There were significant disruptions to my routine",                   group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis","Mixed"], order=360),
    dict(code="flag_physiological_stress",text="I had a major physiological stress",                                 group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis"], order=370),
    dict(code="flag_psychological_stress",text="I had a major psychological stress",                                 group="flags",      rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression","Mania","Psychosis"], order=380),
    # ── OBSERVATIONS ──────────────────────────────────────
    dict(code="obs_up_now",      text="Observations [I feel like I'm experiencing an up]",           group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Mania"],      order=390),
    dict(code="obs_down_now",    text="Observations [I feel like I'm experiencing a down]",          group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression"], order=400),
    dict(code="obs_mixed_now",   text="Observations [I feel like I'm experiencing a mixed]",         group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Psychosis","Mixed"], order=410),
    dict(code="obs_up_coming",   text="Observations [I feel like I'm going to experience an up]",    group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Mania"],      order=420),
    dict(code="obs_down_coming", text="Observations [I feel like I'm going to experience a down]",   group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Depression"], order=430),
    dict(code="obs_mixed_coming",text="Observations [I feel like I'm going to experience a mixed]",  group="observations", rtype="boolean_yes_no", polarity="higher_worse", domains=["Psychosis","Mixed"], order=440),
    # ── NOTES ─────────────────────────────────────────────
    dict(code="experience_description", text="How would I describe my experiences?",                 group="notes",        rtype="text",           polarity="not_applicable", domains=[],            order=470),
]

# Fill in default optional keys
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
    return (
        pd.DataFrame(QUESTION_CATALOG)
        .sort_values("order")
        .reset_index(drop=True)
    )


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
    """Parse raw sheet → wide table keyed by question_code."""
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
        code = meta["code"]
        raw = w[text]
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
    """Convert raw answer → 0–100 risk score (higher = more symptomatic)."""
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
    """Weighted mean of normalised component scores for one domain."""
    by_code = _catalog_by_code()
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
    """Return scored wide table with domain and overall scores."""
    if wide.empty:
        return pd.DataFrame()

    # Optionally filter to first submission per day
    src = wide[wide["is_first_of_day"]].copy() if daily_only else wide.copy()

    # Add minutes-since-first-of-day for snapshot use
    if not daily_only:
        src["minutes_since_first"] = (
            src["submitted_at"]
            - src.groupby("submitted_date")["submitted_at"].transform("min")
        ).dt.total_seconds() / 60.0

    # Normalise all scoreable questions in-place
    by_code = _catalog_by_code()
    for code, meta in by_code.items():
        if code in src.columns and meta["rtype"] != "text":
            src[f"_n_{code}"] = _normalise(src[code], meta)

    # Swap normalised columns into a scoring frame
    norm_frame = src.copy()
    for code in by_code:
        if f"_n_{code}" in norm_frame.columns:
            norm_frame[code] = norm_frame[f"_n_{code}"]

    for domain in DOMAINS:
        src[f"{domain} Score %"] = _domain_score(
            norm_frame, domain, weights, snapshot=not daily_only
        )

    src["Overall Score %"] = src[[f"{d} Score %" for d in DOMAINS]].mean(axis=1)

    # Drop normalisation helpers
    src = src.drop(columns=[c for c in src.columns if c.startswith("_n_")])

    if daily_only:
        src = src.rename(columns={"submitted_date": "date"})
        for col in [f"{d} Score %" for d in DOMAINS] + ["Overall Score %"]:
            src[f"{col} Δ"] = src[col].diff()

    return src.reset_index(drop=True)


# ──────────────────────────────────────────────────────────
# WARNINGS
# ──────────────────────────────────────────────────────────
_WARN_THRESHOLDS = {
    "daily":    {"High": 70, "Medium": 45},
    "snapshot": {"High": 75, "Medium": 50},
}


def build_warnings(daily: pd.DataFrame, snapshots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []

    def _check(row: pd.Series, source: str, ts_col: str) -> None:
        thresholds = _WARN_THRESHOLDS["daily" if source == "Daily" else "snapshot"]
        for domain in DOMAINS:
            score = float(row.get(f"{domain} Score %", 0))
            delta = float(row.get(f"{domain} Score % Δ", 0) or 0)
            severity = next((s for s, t in thresholds.items() if score >= t), None)
            if severity:
                rows.append(dict(source=source, timestamp=row.get(ts_col),
                                 domain=domain, severity=severity,
                                 score_pct=round(score, 1), delta=round(delta, 1),
                                 message=f"{domain} {source.lower()} score {score:.1f}%"))

    if not daily.empty:
        _check(daily.sort_values("date").iloc[-1], "Daily", "submitted_at")
    if not snapshots.empty:
        _check(snapshots.sort_values("submitted_at").iloc[-1], "Snapshot", "submitted_at")

    if not rows:
        return pd.DataFrame(columns=["source","timestamp","domain","severity","score_pct","delta","message"])
    return (
        pd.DataFrame(rows)
        .sort_values(["severity","timestamp"], ascending=[False, False])
        .reset_index(drop=True)
    )


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
        return False, (
            f"Worksheet '{SETTINGS_TAB}' not found. Create it manually then try again."
        )
    rows = [["question_code", "weight"]] + [[k, v] for k, v in weights.items()]
    ws.clear()
    ws.update("A1", rows)
    load_weights.clear()
    return True, "Weights saved."


# ──────────────────────────────────────────────────────────
# DATA ANALYSIS HELPERS
# ──────────────────────────────────────────────────────────
def _rolling_trend(series: pd.Series, window: int = 7) -> str:
    """Return 'rising', 'falling', or 'stable' based on recent linear slope."""
    clean = series.dropna()
    if len(clean) < 3:
        return "insufficient data"
    slope = np.polyfit(range(len(clean[-window:])), clean[-window:].values, 1)[0]
    if slope > 1.5:
        return "rising ↑"
    if slope < -1.5:
        return "falling ↓"
    return "stable →"


def _episode_risk_score(daily: pd.DataFrame) -> dict[str, float]:
    """
    Composite episode risk 0–100 using the last 7 days of daily scores
    with momentum weighting (more recent days count more).
    """
    if daily.empty or len(daily) < 2:
        return {d: 0.0 for d in DOMAINS}
    recent = daily.sort_values("date").tail(7)
    weights_arr = np.arange(1, len(recent) + 1, dtype=float)
    weights_arr /= weights_arr.sum()
    return {
        d: float(np.dot(recent[f"{d} Score %"].fillna(0).values, weights_arr))
        for d in DOMAINS
    }


def _peak_symptom_items(daily: pd.DataFrame, domain: str, top_n: int = 5) -> pd.DataFrame:
    """Mean component scores for a domain over all days, sorted descending."""
    by_code = _catalog_by_code()
    codes = [
        q["code"] for q in QUESTION_CATALOG
        if domain in q["domains"] and q["code"] in daily.columns
    ]
    if not codes or daily.empty:
        return pd.DataFrame()
    means = {c: daily[c].mean() for c in codes if pd.api.types.is_numeric_dtype(daily[c])}
    out = (
        pd.Series(means, name="mean_raw")
        .reset_index()
        .rename(columns={"index": "code"})
        .assign(question=lambda df: df["code"].map(lambda c: by_code.get(c, {}).get("text", c)))
        .sort_values("mean_raw", ascending=False)
        .head(top_n)
    )
    return out


def _cross_domain_correlation(daily: pd.DataFrame) -> pd.DataFrame:
    cols = [f"{d} Score %" for d in DOMAINS]
    available = [c for c in cols if c in daily.columns]
    if len(available) < 2 or len(daily) < 4:
        return pd.DataFrame()
    return daily[available].corr().round(2)


def _flag_impact(daily: pd.DataFrame) -> pd.DataFrame:
    """Mean domain scores on days flags were vs were not triggered."""
    flag_codes = [q["code"] for q in QUESTION_CATALOG if q["group"] == "flags"]
    available_flags = [c for c in flag_codes if c in daily.columns]
    if not available_flags or daily.empty:
        return pd.DataFrame()

    rows = []
    for flag in available_flags:
        flagged = daily[daily[flag] == True]
        not_flagged = daily[daily[flag] == False]
        for domain in DOMAINS:
            col = f"{domain} Score %"
            if col not in daily.columns:
                continue
            rows.append(dict(
                flag=flag,
                domain=domain,
                mean_when_flagged=flagged[col].mean() if not flagged.empty else np.nan,
                mean_when_not_flagged=not_flagged[col].mean() if not not_flagged.empty else np.nan,
            ))

    df = pd.DataFrame(rows).dropna()
    df["impact"] = df["mean_when_flagged"] - df["mean_when_not_flagged"]
    return df.sort_values("impact", ascending=False).reset_index(drop=True)


def _generate_insights(daily: pd.DataFrame, risk: dict[str, float],
                        trends: dict[str, str]) -> list[dict]:
    """Plain-English insight cards."""
    insights: list[dict] = []

    for domain in DOMAINS:
        r = risk.get(domain, 0)
        t = trends.get(domain, "stable →")
        if r >= 60:
            insights.append(dict(level="warning", domain=domain,
                text=f"**{domain}** momentum score is {r:.0f}/100 — elevated risk territory."))
        if "rising" in t and r >= 40:
            insights.append(dict(level="caution", domain=domain,
                text=f"**{domain}** scores have been trending upward over the last 7 days."))

    if not daily.empty and "dep_self_harm_ideation" in daily.columns:
        peak = daily["dep_self_harm_ideation"].max()
        if pd.notna(peak) and peak >= 3:
            insights.append(dict(level="critical", domain="Depression",
                text=f"Self-harm ideation reached a rating of {peak:.0f}/5 at peak — review with clinician."))

    if not daily.empty and "func_sleep_hours" in daily.columns:
        recent_sleep = daily.tail(7)["func_sleep_hours"].mean()
        if pd.notna(recent_sleep) and recent_sleep < 5.5:
            insights.append(dict(level="caution", domain="General",
                text=f"Average sleep over the last 7 days is {recent_sleep:.1f} hours — below the recommended threshold."))

    if not insights:
        insights.append(dict(level="ok", domain="General",
            text="No significant alerts at this time. Scores are within baseline range."))

    return insights


# ──────────────────────────────────────────────────────────
# WEIGHTS EDITOR UI
# ──────────────────────────────────────────────────────────
def render_weights_editor(weights: dict[str, float]) -> dict[str, float]:
    st.markdown("### Scoring weights")
    ws_exists = safe_worksheet(SETTINGS_TAB) is not None
    if not ws_exists:
        st.warning(f"Worksheet '{SETTINGS_TAB}' not found — weights are in-memory only.")

    cat = catalog_df()
    updated = weights.copy()
    for group in ["depression", "mania", "mixed", "psychosis", "functioning", "flags", "observations"]:
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

    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button("Save weights", type="primary"):
            ok, msg = save_weights(updated)
            (st.success if ok else st.error)(msg)
    with col_reset:
        if st.button("Reset to defaults"):
            ok, msg = save_weights(DEFAULT_WEIGHTS.copy())
            (st.success if ok else st.error)("Weights reset." if ok else msg)

    return updated


# ──────────────────────────────────────────────────────────
# DATA LOAD
# ──────────────────────────────────────────────────────────
try:
    wb = _workbook()
    st.caption(f"Connected → **{wb.title}** · worksheet: *{NEW_FORM_TAB}*")
except Exception as exc:
    st.error("Google Sheets connection failed.")
    st.exception(exc)
    st.stop()

weights = load_weights()
raw_df        = load_sheet(NEW_FORM_TAB)
indexed_df    = add_submission_indexing(raw_df)
wide_df       = clean_and_widen(indexed_df)
daily_df      = build_scored_table(wide_df, weights, daily_only=True)
snapshots_df  = build_scored_table(wide_df, weights, daily_only=False)
warnings_df   = build_warnings(daily_df, snapshots_df)

# ──────────────────────────────────────────────────────────
# SUMMARY METRICS ROW
# ──────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total entries", len(raw_df))
m2.metric("Days tracked", len(daily_df))
m3.metric("Snapshot rows", len(snapshots_df))
m4.metric("Active warnings", len(warnings_df[warnings_df["severity"] == "High"]))
if not daily_df.empty:
    latest_overall = daily_df["Overall Score %"].iloc[-1]
    prev_overall   = daily_df["Overall Score %"].iloc[-2] if len(daily_df) > 1 else latest_overall
    m5.metric("Latest overall score", f"{latest_overall:.1f}%",
              delta=f"{latest_overall - prev_overall:+.1f}%")
else:
    m5.metric("Latest overall score", "—")

# ──────────────────────────────────────────────────────────
# TABS
# ──────────────────────────────────────────────────────────
tab_overview, tab_analysis, tab_daily, tab_snapshots, tab_data, tab_settings = st.tabs([
    "Overview", "Analysis", "Daily Model", "Snapshots", "Data Layer", "Settings"
])

# ── OVERVIEW ─────────────────────────────────────────────
with tab_overview:
    st.markdown("### Active warnings")
    if warnings_df.empty:
        st.success("No active warnings.")
    else:
        for _, w in warnings_df.iterrows():
            colour = "🔴" if w["severity"] == "High" else "🟡"
            st.markdown(f"{colour} **{w['domain']}** ({w['source']}) — {w['message']}")

    if not daily_df.empty:
        st.markdown("### Domain scores over time")
        score_cols = [f"{d} Score %" for d in DOMAINS]
        chart_data = daily_df.set_index("date")[score_cols]
        st.line_chart(chart_data)

        st.markdown("### Latest daily snapshot")
        latest = daily_df.sort_values("date").iloc[-1]
        cols = st.columns(len(DOMAINS))
        for i, domain in enumerate(DOMAINS):
            score = latest.get(f"{domain} Score %", 0)
            delta = latest.get(f"{domain} Score % Δ", 0) or 0
            cols[i].metric(domain, f"{score:.1f}%", delta=f"{delta:+.1f}%")

# ── ANALYSIS ─────────────────────────────────────────────
with tab_analysis:
    st.markdown("## Data Analysis")

    if daily_df.empty:
        st.info("No data yet — analysis will appear once submissions are recorded.")
    else:
        risk   = _episode_risk_score(daily_df)
        trends = {d: _rolling_trend(daily_df[f"{d} Score %"]) for d in DOMAINS}

        # ── Insight cards ──────────────────────────────
        st.markdown("### Insights")
        insights = _generate_insights(daily_df, risk, trends)
        level_icon = {"critical": "🚨", "warning": "⚠️", "caution": "💛", "ok": "✅"}
        for ins in insights:
            icon = level_icon.get(ins["level"], "ℹ️")
            st.markdown(f"{icon} {ins['text']}")

        st.divider()

        # ── Episode risk gauge ─────────────────────────
        st.markdown("### Momentum-weighted episode risk (last 7 days)")
        risk_cols = st.columns(len(DOMAINS))
        for i, domain in enumerate(DOMAINS):
            r = risk[domain]
            risk_cols[i].metric(domain, f"{r:.1f} / 100",
                delta=trends[domain],
                delta_color="off")

        st.divider()

        # ── Trend summary ─────────────────────────────
        st.markdown("### 7-day trend direction")
        trend_df = pd.DataFrame([
            {"Domain": d, "Trend": trends[d],
             "Mean Score %": round(daily_df[f"{d} Score %"].tail(7).mean(), 1),
             "Peak Score %": round(daily_df[f"{d} Score %"].tail(7).max(), 1)}
            for d in DOMAINS
        ])
        st.dataframe(trend_df, use_container_width=True, hide_index=True)

        st.divider()

        # ── Cross-domain correlation ───────────────────
        st.markdown("### Cross-domain correlation")
        corr = _cross_domain_correlation(daily_df)
        if not corr.empty:
            st.caption("Pearson correlation between domain scores across all daily entries. "
                        "Values near 1 suggest the domains co-move; near 0 suggests independence.")
            st.dataframe(corr.style.background_gradient(cmap="RdYlGn_r", vmin=-1, vmax=1),
                          use_container_width=True)
        else:
            st.info("Not enough data for correlation (need ≥ 4 days).")

        st.divider()

        # ── Peak symptom items per domain ─────────────
        st.markdown("### Top contributing symptom items (all-time mean)")
        for domain in DOMAINS:
            with st.expander(domain):
                peak_df = _peak_symptom_items(daily_df, domain)
                if peak_df.empty:
                    st.write("No data.")
                else:
                    peak_df = peak_df.rename(columns={"mean_raw": "Mean rating (1–5)",
                                                       "question": "Question"})
                    st.dataframe(peak_df[["Question", "Mean rating (1–5)"]],
                                  use_container_width=True, hide_index=True)

        st.divider()

        # ── Flag impact ────────────────────────────────
        st.markdown("### Flag impact on domain scores")
        impact_df = _flag_impact(daily_df)
        if impact_df.empty:
            st.info("Not enough flag data to compute impact.")
        else:
            st.caption("Difference in mean domain score on days a flag was triggered vs not triggered.")
            top_impact = (
                impact_df[impact_df["impact"].abs() > 2]
                .assign(impact=lambda df: df["impact"].round(1),
                        mean_when_flagged=lambda df: df["mean_when_flagged"].round(1),
                        mean_when_not_flagged=lambda df: df["mean_when_not_flagged"].round(1))
            )
            if top_impact.empty:
                st.write("No flags with material impact detected (threshold: > 2 percentage points).")
            else:
                st.dataframe(top_impact, use_container_width=True, hide_index=True)

        st.divider()

        # ── Sleep analysis ─────────────────────────────
        if "func_sleep_hours" in daily_df.columns:
            st.markdown("### Sleep analysis")
            sleep = daily_df[["date", "func_sleep_hours", "func_sleep_quality"]].copy()
            sleep = sleep.dropna(subset=["func_sleep_hours"])
            if not sleep.empty:
                sl_cols = st.columns(3)
                sl_cols[0].metric("Mean sleep (hours)", f"{sleep['func_sleep_hours'].mean():.1f}")
                sl_cols[1].metric("Nights < 6 hours",
                                   int((sleep["func_sleep_hours"] < 6).sum()))
                sl_cols[2].metric("Nights > 9 hours",
                                   int((sleep["func_sleep_hours"] > 9).sum()))
                st.line_chart(sleep.set_index("date")[["func_sleep_hours"]])

# ── DAILY MODEL ───────────────────────────────────────────
with tab_daily:
    st.markdown("### Daily model — first submission per day")
    st.dataframe(daily_df, use_container_width=True)
    if not daily_df.empty:
        delta_cols = [c for c in daily_df.columns if c.endswith(" Δ") and "Score" in c]
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
    display_cols = ["code", "text", "group", "rtype", "polarity", "domains",
                    "score_in_snapshot", "score_in_daily", "order"]
    st.dataframe(catalog_df()[display_cols], use_container_width=True)

    with st.expander("Wide submission table"):
        st.dataframe(wide_df, use_container_width=True)

    with st.expander("Raw worksheet"):
        st.dataframe(raw_df, use_container_width=True)
        st.caption(f"Columns: {list(raw_df.columns)}")

# ── SETTINGS ─────────────────────────────────────────────
with tab_settings:
    weights = render_weights_editor(weights)
