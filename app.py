import math
import streamlit as st
import pandas as pd
import gspread

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(page_title="Wellbeing Dashboard", layout="wide")

# =========================================================
# AUTHENTICATION
# =========================================================
def check_password():
    def password_entered():
        st.session_state["authenticated"] = (
            st.session_state["password"] == st.secrets["auth"]["password"]
        )

    if "authenticated" not in st.session_state:
        st.text_input("Enter password", type="password", on_change=password_entered, key="password")
        return False

    if not st.session_state["authenticated"]:
        st.text_input("Enter password", type="password", on_change=password_entered, key="password")
        st.error("Wrong password")
        return False

    return True

if not check_password():
    st.stop()

# =========================================================
# CONSTANTS
# =========================================================
SHEET_NAME = "Bipolar Dashboard"

FORM_TAB = "Form Responses"
QUICK_FORM_TAB = "Quick Form Responses"
NEW_DAILY_TAB = "Updated Daily Bipolar Form"

DOMAIN_NAMES = ["Depression", "Mania", "Psychosis", "Mixed"]
DAILY_ROLLING_WINDOW_DAYS = 5

COLUMN_ALIASES = {
    "Signals and indicators [Avoided normal responsiblities]": "Signals and indicators [Avoided normal responsibilities]",
    "Certainty and  belief in unusual ideas or things others don't believe": "Certainty and belief in unusual ideas or things others don't believe",
    "Weekly Check-In  Flags": "Weekly Check-In Flags",
    "Column 1": "Date",
    "Positive motivation": "Motivation",
}

COL_MOOD = "Mood Score"
COL_SLEEP_HOURS = "Sleep (hours)"
COL_SLEEP_QUALITY = "Sleep quality"
COL_ENERGY = "Energy"
COL_MENTAL_SPEED = "Mental speed"
COL_IMPULSIVITY = "Impulsivity"
COL_MOTIVATION = "Motivation"
COL_IRRITABILITY = "Irritability"
COL_AGITATION = "Agitation"
COL_SLEEPING_PILLS = "Took sleeping medication?"
COL_UNUSUAL = "Unusual perceptions"
COL_SUSPICIOUS = "Suspiciousness"
COL_CERTAINTY = "Certainty and belief in unusual ideas or things others don't believe"

SIG_NOT_MYSELF = 'Signals and indicators [Felt "not like myself"]'
SIG_MOOD_SHIFT = "Signals and indicators [Noticed a sudden mood shift]"
SIG_LESS_SLEEP = "Signals and indicators [Needed less sleep than usual without feeling tired]"
SIG_MORE_ACTIVITY = "Signals and indicators [Started more activities than usual]"
SIG_WITHDRAW = "Signals and indicators [Withdrew socially or emotionally from others]"
SIG_AVOID_RESPONSIBILITIES = "Signals and indicators [Avoided normal responsibilities]"
SIG_HEARD_SAW = "Signals and indicators [Heard or saw something others didn't]"
SIG_WATCHED = "Signals and indicators [Felt watched, followed, targeted]"
SIG_SPECIAL_MEANING = "Signals and indicators [Felt something had special meaning for me]"
SIG_TROUBLE_TRUSTING = "Signals and indicators [Trouble trusting perceptions and thoughts]"
SIG_MISSED_MEDS = "Signals and indicators [Missed meds]"
SIG_ROUTINE = "Signals and indicators [Significant disruption to routine]"
SIG_STRESS_PSYCH = "Signals and indicators [Major stressor or trigger (psychological)]"
SIG_STRESS_PHYS = "Signals and indicators [Major stressor or trigger (physiological)]"
SIG_UP_NOW = "Signals and indicators [Feel like I'm experiencing an up]"
SIG_DOWN_NOW = "Signals and indicators [Feel like I'm experiencing a down]"
SIG_MIXED_NOW = "Signals and indicators [Feel like I'm experiencing a mixed]"
SIG_UP_COMING = "Signals and indicators [Feel like I'm going to experience an up]"
SIG_DOWN_COMING = "Signals and indicators [Feel like I'm going to experience a down]"
SIG_MIXED_COMING = "Signals and indicators [Feel like I'm going to experience a mixed]"

DEFAULT_DAILY_SETTINGS = {
    "dep_low_mood_weight": 4.0, "dep_low_sleep_quality_weight": 1.0, "dep_low_energy_weight": 1.0,
    "dep_low_mental_speed_weight": 1.0, "dep_low_motivation_weight": 2.0, "dep_flag_weight": 1.0,
    "mania_high_mood_weight": 1.0, "mania_low_sleep_quality_weight": 2.0, "mania_high_energy_weight": 1.5,
    "mania_high_mental_speed_weight": 1.5, "mania_high_impulsivity_weight": 1.5, "mania_high_irritability_weight": 2.0,
    "mania_high_agitation_weight": 2.0, "mania_flag_weight": 2.0, "psych_unusual_weight": 1.0,
    "psych_suspicious_weight": 1.0, "psych_certainty_weight": 3.0, "psych_flag_weight": 1.0,
    "mixed_dep_weight": 0.4, "mixed_mania_weight": 0.4, "mixed_psych_weight": 0.2, "mixed_low_sleep_quality_weight": 0.5,
    "medium_threshold_pct": 33.0, "high_threshold_pct": 66.0, "trend_threshold_pct": 8.0,
    "baseline_window_days": 14, "anomaly_z_threshold": 1.5, "high_anomaly_z_threshold": 2.5, "persistence_days": 3,
}

DEFAULT_SNAPSHOT_SETTINGS = {
    "dep_very_low_mood": 4.0, "dep_somewhat_low_mood": 2.0, "dep_withdrawal": 1.0, "dep_self_care": 1.0,
    "dep_slowed_down": 1.0, "mania_very_high_mood": 2.0, "mania_somewhat_high_mood": 1.0, "mania_agitation": 2.0,
    "mania_racing": 1.5, "mania_driven": 2.0, "psych_hearing_seeing": 1.0, "psych_paranoia": 1.0,
    "psych_beliefs": 1.0, "mixed_dep_weight": 0.4, "mixed_mania_weight": 0.4, "mixed_psych_weight": 0.2,
    "medium_threshold_pct": 33.0, "high_threshold_pct": 66.0, "trend_threshold_pct": 8.0,
}

REASON_LABELS = {
    "Depression - Low Mood Score": "Lower mood", "Depression - Low Sleep Quality": "Poor sleep quality",
    "Depression - Low Energy": "Lower energy", "Depression - Low Mental Speed": "Slower mental speed",
    "Depression - Low Motivation": "Lower motivation", "Depression - Flags": "Depression flag",
    "Mania - High Mood Score": "Higher mood", "Mania - Low Sleep Quality": "Poor sleep / reduced restorative sleep",
    "Mania - High Energy": "Higher energy", "Mania - High Mental Speed": "Faster mental speed",
    "Mania - High Impulsivity": "Higher impulsivity", "Mania - High Irritability": "Higher irritability",
    "Mania - High Agitation": "Higher agitation", "Mania - Flags": "Mania-related flags",
    "Psychosis - Unusual perceptions": "Unusual perceptions", "Psychosis - Suspiciousness": "Suspiciousness",
    "Psychosis - Certainty": "Strong certainty in unusual beliefs", "Psychosis - Flags": "Psychosis-related flags",
}

# =========================================================
# MODEL CONFIG
# =========================================================
DAILY_DOMAIN_CONFIG = {
    "Depression": {
        "components": [
            ("Low Mood Score", COL_MOOD, True, "dep_low_mood_weight"),
            ("Low Sleep Quality", COL_SLEEP_QUALITY, True, "dep_low_sleep_quality_weight"),
            ("Low Energy", COL_ENERGY, True, "dep_low_energy_weight"),
            ("Low Mental Speed", COL_MENTAL_SPEED, True, "dep_low_mental_speed_weight"),
            ("Low Motivation", COL_MOTIVATION, True, "dep_low_motivation_weight"),
        ],
        "flags": [],
        "flag_weight_key": "dep_flag_weight",
        "custom_flag_logic": "depression",
    },
    "Mania": {
        "components": [
            ("High Mood Score", COL_MOOD, False, "mania_high_mood_weight"),
            ("Low Sleep Quality", COL_SLEEP_QUALITY, True, "mania_low_sleep_quality_weight"),
            ("High Energy", COL_ENERGY, False, "mania_high_energy_weight"),
            ("High Mental Speed", COL_MENTAL_SPEED, False, "mania_high_mental_speed_weight"),
            ("High Impulsivity", COL_IMPULSIVITY, False, "mania_high_impulsivity_weight"),
            ("High Irritability", COL_IRRITABILITY, False, "mania_high_irritability_weight"),
            ("High Agitation", COL_AGITATION, False, "mania_high_agitation_weight"),
        ],
        "flags": [SIG_LESS_SLEEP, SIG_MORE_ACTIVITY, SIG_UP_NOW, SIG_UP_COMING],
        "flag_weight_key": "mania_flag_weight",
    },
    "Psychosis": {
        "components": [
            ("Unusual perceptions", COL_UNUSUAL, False, "psych_unusual_weight"),
            ("Suspiciousness", COL_SUSPICIOUS, False, "psych_suspicious_weight"),
            ("Certainty", COL_CERTAINTY, False, "psych_certainty_weight"),
        ],
        "flags": [SIG_HEARD_SAW, SIG_WATCHED, SIG_SPECIAL_MEANING, SIG_TROUBLE_TRUSTING],
        "flag_weight_key": "psych_flag_weight",
    },
}

SNAPSHOT_DOMAIN_CONFIG = {
    "Depression": {
        "components": [
            ("Symptoms: [Very low or depressed mood]", "dep_very_low_mood"),
            ("Symptoms: [Somewhat low or depressed mood]", "dep_somewhat_low_mood"),
            ("Symptoms: [Social or emotional withdrawal]", "dep_withdrawal"),
            ("Symptoms: [Feeling slowed down]", "dep_slowed_down"),
            ("Symptoms: [Difficulty with self-care]", "dep_self_care"),
        ]
    },
    "Mania": {
        "components": [
            ("Symptoms: [Very high or elevated mood]", "mania_very_high_mood"),
            ("Symptoms: [Somewhat high or elevated mood]", "mania_somewhat_high_mood"),
            ("Symptoms: [Agitation or restlessness]", "mania_agitation"),
            ("Symptoms: [Racing thoughts]", "mania_racing"),
            ("Symptoms: [Driven to activity]", "mania_driven"),
        ]
    },
    "Psychosis": {
        "components": [
            ("Symptoms: [Hearing or seeing things that aren't there]", "psych_hearing_seeing"),
            ("Symptoms: [Paranoia or suspicion]", "psych_paranoia"),
            ("Symptoms: [Firm belief in things others would not agree with]", "psych_beliefs"),
        ]
    },
}

DAILY_SETTINGS_UI = {
    "Depression weights": [
        ("dep_low_mood_weight", "Low mood", 0.0, 5.0, 0.1),
        ("dep_low_sleep_quality_weight", "Low sleep quality", 0.0, 5.0, 0.1),
        ("dep_low_energy_weight", "Low energy", 0.0, 5.0, 0.1),
        ("dep_low_mental_speed_weight", "Low mental speed", 0.0, 5.0, 0.1),
        ("dep_low_motivation_weight", "Low motivation", 0.0, 5.0, 0.1),
        ("dep_flag_weight", "Depression flag", 0.0, 5.0, 0.1),
    ],
    "Mania weights": [
        ("mania_high_mood_weight", "High mood", 0.0, 5.0, 0.1),
        ("mania_low_sleep_quality_weight", "Low sleep quality (mania)", 0.0, 5.0, 0.1),
        ("mania_high_energy_weight", "High energy", 0.0, 5.0, 0.1),
        ("mania_high_mental_speed_weight", "High mental speed", 0.0, 5.0, 0.1),
        ("mania_high_impulsivity_weight", "High impulsivity", 0.0, 5.0, 0.1),
        ("mania_high_irritability_weight", "High irritability", 0.0, 5.0, 0.1),
        ("mania_high_agitation_weight", "High agitation", 0.0, 5.0, 0.1),
        ("mania_flag_weight", "Mania flags", 0.0, 5.0, 0.1),
    ],
    "Psychosis weights": [
        ("psych_unusual_weight", "Unusual perceptions", 0.0, 5.0, 0.1),
        ("psych_suspicious_weight", "Suspiciousness", 0.0, 5.0, 0.1),
        ("psych_certainty_weight", "Certainty", 0.0, 5.0, 0.1),
        ("psych_flag_weight", "Psychosis flags", 0.0, 5.0, 0.1),
    ],
    "Mixed weights": [
        ("mixed_dep_weight", "Mixed: depression", 0.0, 3.0, 0.05),
        ("mixed_mania_weight", "Mixed: mania", 0.0, 3.0, 0.05),
        ("mixed_psych_weight", "Mixed: psychosis", 0.0, 3.0, 0.05),
        ("mixed_low_sleep_quality_weight", "Mixed: low sleep quality", 0.0, 3.0, 0.05),
    ],
    "Thresholds": [
        ("medium_threshold_pct", "Medium threshold (%)", 0.0, 100.0, 1.0),
        ("high_threshold_pct", "High threshold (%)", 0.0, 100.0, 1.0),
        ("trend_threshold_pct", "Trend threshold (pp)", 0.0, 100.0, 1.0),
    ],
    "Baseline & alert tuning": [
        ("baseline_window_days", "Baseline window (days)", 3, 60, 1),
        ("anomaly_z_threshold", "Unusual z-threshold", 0.5, 5.0, 0.1),
        ("high_anomaly_z_threshold", "High unusual z-threshold", 0.5, 6.0, 0.1),
        ("persistence_days", "Persistence days", 2, 14, 1),
    ],
}

SNAPSHOT_SETTINGS_UI = {
    "Depression weights": [
        ("dep_very_low_mood", "Very low mood", 0.0, 5.0, 0.1),
        ("dep_somewhat_low_mood", "Somewhat low mood", 0.0, 5.0, 0.1),
        ("dep_withdrawal", "Withdrawal", 0.0, 5.0, 0.1),
        ("dep_slowed_down", "Slowed down", 0.0, 5.0, 0.1),
        ("dep_self_care", "Self-care", 0.0, 5.0, 0.1),
    ],
    "Mania weights": [
        ("mania_very_high_mood", "Very high mood", 0.0, 5.0, 0.1),
        ("mania_somewhat_high_mood", "Somewhat high mood", 0.0, 5.0, 0.1),
        ("mania_agitation", "Agitation", 0.0, 5.0, 0.1),
        ("mania_racing", "Racing thoughts", 0.0, 5.0, 0.1),
        ("mania_driven", "Driven to activity", 0.0, 5.0, 0.1),
    ],
    "Psychosis weights": [
        ("psych_hearing_seeing", "Hearing / seeing things", 0.0, 5.0, 0.1),
        ("psych_paranoia", "Paranoia", 0.0, 5.0, 0.1),
        ("psych_beliefs", "Firm unusual beliefs", 0.0, 5.0, 0.1),
    ],
    "Mixed weights": [
        ("mixed_dep_weight", "Mixed: depression", 0.0, 3.0, 0.05),
        ("mixed_mania_weight", "Mixed: mania", 0.0, 3.0, 0.05),
        ("mixed_psych_weight", "Mixed: psychosis", 0.0, 3.0, 0.05),
    ],
    "Thresholds": [
        ("medium_threshold_pct", "Medium threshold (%)", 0.0, 100.0, 1.0),
        ("high_threshold_pct", "High threshold (%)", 0.0, 100.0, 1.0),
        ("trend_threshold_pct", "Trend threshold (pp)", 0.0, 100.0, 1.0),
    ],
}

DAILY_CHARTS = [
    {"title": "Daily state scores (%)", "cols": ["Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"], "key": "daily_state_scores", "type": "line"},
    {"title": "5-day averages (%)", "cols": ["5-Day Average (Depression %)", "5-Day Average (Mania %)", "5-Day Average (Psychosis %)", "5-Day Average (Mixed %)"], "key": "daily_5day_avg", "type": "line"},
    {"title": "Deviation from 5-day averages (percentage points)", "cols": ["Depression Deviation %", "Mania Deviation %", "Psychosis Deviation %", "Mixed Deviation %"], "key": "daily_deviation", "type": "line"},
    {"title": "Personal baseline vs current scores", "cols": ["Depression Score %", "Depression Baseline %", "Mania Score %", "Mania Baseline %", "Psychosis Score %", "Psychosis Baseline %", "Mixed Score %", "Mixed Baseline %"], "key": "daily_baseline_vs_current", "type": "line"},
    {"title": "Distance from personal baseline (percentage points)", "cols": ["Depression Baseline Difference %", "Mania Baseline Difference %", "Psychosis Baseline Difference %", "Mixed Baseline Difference %"], "key": "daily_baseline_diff", "type": "line"},
    {"title": "Unusual-for-me score (z-score)", "cols": ["Depression Baseline Z", "Mania Baseline Z", "Psychosis Baseline Z", "Mixed Baseline Z"], "key": "daily_baseline_z", "type": "line"},
    {"title": "Flag breakdown by category", "cols": ["Concerning Situation Flags", "Depression Flags", "Mania Flags", "Mixed Flags", "Psychosis Flags"], "key": "daily_flags", "type": "bar"},
    {"title": "Depression drivers", "cols": ["Depression - Low Mood Score", "Depression - Low Sleep Quality", "Depression - Low Energy", "Depression - Low Mental Speed", "Depression - Low Motivation", "Depression - Flags"], "key": "daily_depression_drivers", "type": "line"},
    {"title": "Mania drivers", "cols": ["Mania - High Mood Score", "Mania - Low Sleep Quality", "Mania - High Energy", "Mania - High Mental Speed", "Mania - High Impulsivity", "Mania - High Irritability", "Mania - High Agitation", "Mania - Flags"], "key": "daily_mania_drivers", "type": "line"},
    {"title": "Psychosis drivers", "cols": ["Psychosis - Unusual perceptions", "Psychosis - Suspiciousness", "Psychosis - Certainty", "Psychosis - Flags"], "key": "daily_psychosis_drivers", "type": "line"},
]

SNAPSHOT_CHARTS = [
    {"title": "Snapshot model scores (%)", "cols": ["Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"], "key": "snapshot_model_scores", "type": "line"},
    {"title": "Snapshot scores vs 10-response averages (%)", "cols": ["Depression Score %", "10-Response Average (Depression %)", "Mania Score %", "10-Response Average (Mania %)", "Psychosis Score %", "10-Response Average (Psychosis %)", "Mixed Score %", "10-Response Average (Mixed %)"], "key": "snapshot_scores_vs_avg", "type": "line"},
    {"title": "Deviation from 10-response averages (percentage points)", "cols": ["Deviation From 10-Response Average (Depression %)", "Deviation From 10-Response Average (Mania %)", "Deviation From 10-Response Average (Psychosis %)", "Deviation From 10-Response Average (Mixed %)"], "key": "snapshot_deviation", "type": "line"},
]

# =========================================================
# SESSION STATE
# =========================================================
if "daily_settings" not in st.session_state:
    st.session_state["daily_settings"] = DEFAULT_DAILY_SETTINGS.copy()

if "snapshot_settings" not in st.session_state:
    st.session_state["snapshot_settings"] = DEFAULT_SNAPSHOT_SETTINGS.copy()

# =========================================================
# HELPERS
# =========================================================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=COLUMN_ALIASES) if not df.empty else df

def convert_numeric(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    working = df.copy()
    for col in working.columns:
        if col not in ["Timestamp", "Date", "Date (int)"]:
            working[col] = pd.to_numeric(working[col], errors="coerce")
    return working

def bool_from_response(val):
    return str(val).strip().lower() in ["yes", "true", "1", "y", "checked"]

def score_response_0_2(val):
    text = str(val).strip().lower()
    return 2 if text == "yes" else 1 if text == "somewhat" else 0

def score_response_pct(val):
    return score_response_0_2(val) / 2 * 100.0

def prettify_signal_name(name: str) -> str:
    return name.replace("Signals and indicators [", "").replace("Symptoms: [", "").replace("]", "")

def drop_blank_tail_rows(df: pd.DataFrame, required_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    present = [c for c in required_cols if c in df.columns]
    return df.dropna(subset=present, how="all").copy() if present else df.dropna(how="all").copy()

def to_float(value, default=0.0) -> float:
    try:
        if pd.isna(value) or value is None or str(value).strip() == "": return default
        return float(value)
    except Exception:
        return default

def to_int(value, default=0) -> int:
    return int(round(to_float(value, default=default)))

def normalize_0_10_to_pct(series, inverse: bool = False) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    return ((10 - s).clip(lower=0, upper=10) / 10.0 * 100.0) if inverse else (s.clip(lower=0, upper=10) / 10.0 * 100.0)

def normalize_flag_count_to_pct(series: pd.Series, max_flags: int) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    return (s.clip(lower=0, upper=max_flags) / max_flags * 100.0) if max_flags > 0 else pd.Series(0.0, index=s.index)

def weighted_average_percent(df: pd.DataFrame, col_weight_pairs: list[tuple[str, float]]) -> pd.Series:
    numerator, denominator = pd.Series(0.0, index=df.index, dtype=float), 0.0
    for col, weight in col_weight_pairs:
        if col in df.columns and weight > 0:
            numerator += (pd.to_numeric(df[col], errors="coerce").fillna(0.0) * weight)
            denominator += weight
    return numerator / denominator if denominator > 0 else pd.Series(0.0, index=df.index, dtype=float)

def confidence_from_count(count: int, trend: str, level: str) -> str:
    score = (2 if count >= 5 else 1 if count >= 3 else 0) + (1 if trend != "Stable" else 0) + (1 if level in ["Medium", "High"] else 0)
    return "High" if score >= 4 else "Medium" if score >= 2 else "Low"

def level_from_percent(score_pct, medium_pct, high_pct) -> str:
    score = to_float(score_pct)
    return "High" if score >= high_pct else "Medium" if score >= medium_pct else "Low"

def trend_from_deviation_pct(dev_pct, threshold_pct) -> str:
    d = to_float(dev_pct)
    return "Rising" if d > threshold_pct else "Falling" if d < -threshold_pct else "Stable"

def alert_rank(severity: str) -> int:
    return {"Monitor": 1, "Pay attention today": 2, "High concern": 3}.get(severity, 0)

def tone_color_tag(tone: str) -> str:
    return {"error": "red", "warning": "orange", "info": "blue", "success": "green"}.get(tone, "gray")

def split_into_two_columns(items: list[str]) -> tuple[list[str], list[str]]:
    midpoint = math.ceil(len(items) / 2) if items else 0
    return items[:midpoint], items[midpoint:]

def find_possible_columns(df: pd.DataFrame, patterns: list[str]) -> list[str]:
    lowered = {c.lower(): c for c in df.columns}
    return [original for col_lower, original in lowered.items() if any(p in col_lower for p in patterns)]

def build_sleeping_pills_flag_series(daily: pd.DataFrame) -> pd.Series:
    if COL_SLEEPING_PILLS not in daily.columns: return pd.Series(0, index=daily.index, dtype=int)
    vals = daily[COL_SLEEPING_PILLS]
    return (pd.to_numeric(vals, errors="coerce").fillna(0) > 0).astype(int) if pd.api.types.is_numeric_dtype(vals) else vals.apply(bool_from_response).astype(int)

# =========================================================
# DEPRESSION FLAG LOGIC
# =========================================================
def build_daily_depression_flag_series(daily: pd.DataFrame) -> pd.Series:
    mood_low = pd.to_numeric(daily.get(COL_MOOD, pd.Series(pd.NA, index=daily.index)), errors="coerce") <= 3
    mental_speed_low = pd.to_numeric(daily.get(COL_MENTAL_SPEED, pd.Series(pd.NA, index=daily.index)), errors="coerce") < 4
    motivation_low = pd.to_numeric(daily.get(COL_MOTIVATION, pd.Series(pd.NA, index=daily.index)), errors="coerce") < 4
    return (mood_low | (mental_speed_low & motivation_low)).fillna(False).astype(int)

def build_snapshot_depression_flag_series(df: pd.DataFrame) -> pd.Series:
    result = pd.Series(False, index=df.index)
    cols_to_check = [c for c in ["Symptoms: [Very low or depressed mood]", "Symptoms: [Somewhat low or depressed mood]"] if c in df.columns]
    cols_to_check.extend(find_possible_columns(df, ["experiencing a down", "going to experience a down", "in a depression", "going into a depression", "depression now", "depression coming"]))
    for col in cols_to_check:
        result |= df[col].astype(str).str.strip().str.lower().isin(["yes", "somewhat"])
    return result.astype(int)

# =========================================================
# UI HELPERS - STREAMLIT NATIVE
# =========================================================
def render_status_card(title: str, score_pct: float, level: str, trend: str, confidence: str):
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(f"**Current:** :{'red' if level == 'High' else 'orange' if level == 'Medium' else 'green'}[{level}] ({score_pct:.1f}%)")
        st.markdown(f"**Trend:** :{'orange' if trend == 'Rising' else 'blue' if trend == 'Falling' else 'green'}[{trend}]")
        st.markdown(f"**Confidence:** :{'green' if confidence == 'High' else 'orange' if confidence == 'Medium' else 'gray'}[{confidence}]")

def render_daily_card(title: str, data: dict):
    with st.container(border=True):
        st.markdown(f"#### {title}")
        render_status_card_details(data)
        if data.get("baseline_note"): st.markdown(f"**Compared with usual:** {data['baseline_note']}")
        if data.get("baseline_z_text"):
            with st.expander("Baseline detail"): st.write(data["baseline_z_text"])
        st.markdown("**Main drivers:**")
        if data.get("reasons"):
            r1, r2 = split_into_two_columns(data["reasons"])
            c1, c2 = st.columns(2)
            with c1: [st.write(f"- {r}") for r in r1]
            with c2: [st.write(f"- {r}") for r in r2]
        else:
            st.write("- No strong drivers")

def render_status_card_details(data):
    st.markdown(f"**Current state:** :{'red' if data['level'] == 'High' else 'orange' if data['level'] == 'Medium' else 'green'}[{data['level']}] ({data['score_pct']:.1f}%)")
    st.markdown(f"**Recent direction:** :{'orange' if data['trend'] == 'Rising' else 'blue' if data['trend'] == 'Falling' else 'green'}[{data['trend']}]")
    st.markdown(f"**Confidence:** :{'green' if data['confidence'] == 'High' else 'orange' if data['confidence'] == 'Medium' else 'gray'}[{data['confidence']}]")

def render_two_column_flag_box(title: str, items: list[str], tone: str = "info"):
    with st.container(border=True):
        color = tone_color_tag(tone)
        st.markdown(f"#### :{color}[{title}]")
        if not items:
            st.markdown(":gray[- None]")
            return
        left, right = split_into_two_columns(items)
        c1, c2 = st.columns(2)
        with c1: [st.markdown(f":{color}[- {item}]") for item in left]
        with c2: [st.markdown(f":{color}[- {item}]") for item in right]

def render_alert_card(alert: dict):
    color = tone_color_tag({"High concern": "error", "Pay attention today": "warning", "Monitor": "info"}.get(alert["severity"], "info"))
    with st.container(border=True):
        st.markdown(f"#### :{color}[{alert['title']}]\n**Status:** :{color}[{alert['severity']}]\n**Summary:** {alert['summary']}")
        if alert.get("details"):
            st.markdown("**Details:**")
            d1, d2 = split_into_two_columns(alert["details"])
            c1, c2 = st.columns(2)
            with c1: [st.markdown(f":{color}[- {d}]") for d in d1]
            with c2: [st.markdown(f":{color}[- {d}]") for d in d2]

def render_summary_cards(summary: dict, detailed: bool = False):
    if not summary:
        st.info("No summary available.")
        return
    for col, (name, data) in zip(st.columns(len(summary)), summary.items()):
        with col:
            render_daily_card(name, data) if detailed else render_status_card(name, data["score_pct"], data["level"], data["trend"], data["confidence"])

def render_settings_form(session_key: str, settings_ui: dict, columns_per_row: int = 3):
    for section, items in settings_ui.items():
        st.markdown(f"#### {section}")
        for i in range(0, len(items), columns_per_row):
            for col, (key, label, min_v, max_v, step) in zip(st.columns(len(items[i:i + columns_per_row])), items[i:i + columns_per_row]):
                with col:
                    current_val = st.session_state[session_key][key]
                    is_int = isinstance(step, int) or (isinstance(current_val, int) and float(step).is_integer())
                    st.session_state[session_key][key] = st.number_input(label, min_value=int(min_v) if is_int else float(min_v), max_value=int(max_v) if is_int else float(max_v), value=int(current_val) if is_int else float(current_val), step=int(step) if is_int else float(step), key=f"{session_key}_{key}")

def filter_df_by_date(df: pd.DataFrame, date_col: str, key_prefix: str):
    if df.empty or date_col not in df.columns: return df
    working = df[df[date_col].notna()].copy()
    if working.empty: return working
    min_date, max_date = pd.to_datetime(working[date_col]).min().date(), pd.to_datetime(working[date_col]).max().date()
    start_end = st.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date, key=f"{key_prefix}_date_range")
    start_date, end_date = start_end if isinstance(start_end, tuple) and len(start_end) == 2 else (min_date, max_date)
    return working[(pd.to_datetime(working[date_col]).dt.date >= start_date) & (pd.to_datetime(working[date_col]).dt.date <= end_date)].copy()

def render_filtered_chart(df: pd.DataFrame, date_col: str, label_col: str, title: str, default_cols: list[str], key_prefix: str, chart_type: str = "line"):
    st.markdown(f"### {title}")
    if df.empty: return st.info("No data available.")
    filtered = filter_df_by_date(df, date_col, key_prefix)
    selected_cols = st.multiselect("Series", options=[c for c in default_cols if c in filtered.columns], default=[c for c in default_cols if c in filtered.columns], key=f"{key_prefix}_series")
    if filtered.empty or not selected_cols: return st.info("No data in selected date range." if filtered.empty else "Pick at least one series.")
    chart_df = filtered[[label_col] + selected_cols].set_index(label_col)
    st.bar_chart(chart_df) if chart_type == "bar" else st.line_chart(chart_df)

def render_chart_group(df, date_col, label_col, chart_defs):
    for chart in chart_defs:
        render_filtered_chart(df=df, date_col=date_col, label_col=label_col, title=chart["title"], default_cols=chart["cols"], key_prefix=chart["key"], chart_type=chart["type"])

def render_dataframe_picker(title: str, df: pd.DataFrame, default_cols: list[str], key: str):
    st.markdown(f"### {title}")
    if df.empty: return st.info("No data available.")
    selected_cols = st.multiselect(f"Choose {title} columns", df.columns.tolist(), default=default_cols or df.columns.tolist()[:12], key=key)
    if selected_cols: st.dataframe(df[selected_cols], use_container_width=True)

# =========================================================
# GOOGLE SHEETS
# =========================================================
@st.cache_resource
def get_gspread_client():
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))

@st.cache_resource
def get_workbook():
    return get_gspread_client().open(SHEET_NAME)

@st.cache_data(ttl=60)
def load_sheet(tab_name: str) -> pd.DataFrame:
    try:
        data = get_workbook().worksheet(tab_name).get_all_values()
    except Exception:
        return pd.DataFrame()
    if not data: return pd.DataFrame()
    headers = [str(h).strip() if h else f"Unnamed_{i+1}" for i, h in enumerate(data[0])]
    seen = {}
    unique_headers = []
    for header in headers:
        if header in seen:
            seen[header] += 1
            unique_headers.append(f"{header}_{seen[header]}")
        else:
            seen[header] = 0
            unique_headers.append(header)
            
    df = pd.DataFrame(data[1:], columns=unique_headers).loc[:, lambda d: ~d.columns.duplicated()]
    df = normalize_columns(df)
    for dt_col in ["Timestamp", "Date", "Date (int)"]:
        if dt_col in df.columns: df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce", dayfirst=True)
    return df

# =========================================================
# PREP FUNCTIONS
# =========================================================
def prepare_form_raw(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    working = drop_blank_tail_rows(convert_numeric(df.copy()), ["Timestamp", COL_MOOD, COL_SLEEP_QUALITY, COL_ENERGY])
    if "Timestamp" in working.columns:
        working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
        working["Date"] = working["Timestamp"].dt.date
    return working.sort_values("Timestamp").reset_index(drop=True)

def prepare_quick_form_raw(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    working = drop_blank_tail_rows(df.copy(), ["Timestamp"])
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    working = working.sort_values("Timestamp").reset_index(drop=True)
    for col in [c for c in working.columns if c != "Timestamp"]:
        working[f"{col} Numeric"] = working[col].apply(score_response_0_2)
        working[f"{col} Percent"] = working[col].apply(score_response_pct)
        working[f"{col} Trend"] = working[f"{col} Percent"].diff()
    return working

def prepare_new_daily_sheet(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return pd.DataFrame()
    working = df.copy()
    
    rename_map = {
        'I\'ve been feeling "not like myself"': SIG_NOT_MYSELF, 'I noticed a sudden mood shift': SIG_MOOD_SHIFT,
        'I missed medication': SIG_MISSED_MEDS, 'I took sleeping or anti-anxiety medication': COL_SLEEPING_PILLS,
        'There were significant disruptions to my routine': SIG_ROUTINE, 'I had a major physiological stress': SIG_STRESS_PHYS,
        'I had a major psychological stress': SIG_STRESS_PSYCH, "Observations [I feel like I'm experiencing an up]": SIG_UP_NOW,
        "Observations [I feel like I'm experiencing a down]": SIG_DOWN_NOW, "Observations [I feel like I'm experiencing a mixed]": SIG_MIXED_NOW,
        "Observations [I feel like I'm going to experience an up]": SIG_UP_COMING, "Observations [I feel like I'm going to experience a down]": SIG_DOWN_COMING,
        "Observations [I feel like I'm going to experience a mixed]": SIG_MIXED_COMING, "How many hours of sleep did I get?": COL_SLEEP_HOURS,
    }
    working.rename(columns=rename_map, inplace=True)
    
    scale_cols = ["Have I felt a low mood?", "Have I felt an elevated mood?", "Have I felt slowed down or low on energy?", "Have I felt sped up or high on energy?", "Have I had racing thoughts or speech?", "Have I felt low on motivation or had difficulty initiating tasks?", "What was my sleep quality?", "Have I been more irritable and reactive than normal?", "Have I felt agitated or restless?", "Have I heard or seen things others didn't?", "Have I felt watched, followed, targeted or suspicious?", "How confident have I been in the reality of these experiences?"]
    for col in scale_cols:
        if col in working.columns: working[col] = pd.to_numeric(working[col], errors='coerce').fillna(1)
        
    def s(col): return working.get(col)
    
    if "Have I felt a low mood?" in working.columns and "Have I felt an elevated mood?" in working.columns:
        working[COL_MOOD] = 5.0 - ((s("Have I felt a low mood?") - 1) * 1.25) + ((s("Have I felt an elevated mood?") - 1) * 1.25)
    if "Have I felt slowed down or low on energy?" in working.columns and "Have I felt sped up or high on energy?" in working.columns:
        working[COL_ENERGY] = 5.0 - ((s("Have I felt slowed down or low on energy?") - 1) * 1.25) + ((s("Have I felt sped up or high on energy?") - 1) * 1.25)
    if "Have I felt slowed down or low on energy?" in working.columns and "Have I had racing thoughts or speech?" in working.columns:
        working[COL_MENTAL_SPEED] = 5.0 - ((s("Have I felt slowed down or low on energy?") - 1) * 1.25) + ((s("Have I had racing thoughts or speech?") - 1) * 1.25)
    if "Have I felt low on motivation or had difficulty initiating tasks?" in working.columns:
        working[COL_MOTIVATION] = 10.0 - ((s("Have I felt low on motivation or had difficulty initiating tasks?") - 1) * 2.5)
        
    scale_1_to_5 = lambda c: (s(c) - 1) * 2.5
    if "What was my sleep quality?" in working.columns: working[COL_SLEEP_QUALITY] = scale_1_to_5("What was my sleep quality?")
    if "Have I been more irritable and reactive than normal?" in working.columns: working[COL_IRRITABILITY] = scale_1_to_5("Have I been more irritable and reactive than normal?")
    if "Have I felt agitated or restless?" in working.columns: working[COL_AGITATION] = scale_1_to_5("Have I felt agitated or restless?")
    if "Have I heard or seen things others didn't?" in working.columns: working[COL_UNUSUAL] = scale_1_to_5("Have I heard or seen things others didn't?")
    if "Have I felt watched, followed, targeted or suspicious?" in working.columns: working[COL_SUSPICIOUS] = scale_1_to_5("Have I felt watched, followed, targeted or suspicious?")
    if "How confident have I been in the reality of these experiences?" in working.columns: working[COL_CERTAINTY] = scale_1_to_5("How confident have I been in the reality of these experiences?")

    if "Timestamp" in working.columns:
        working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
        working["Date"] = working["Timestamp"].dt.date
    return working

# =========================================================
# MODEL HELPERS
# =========================================================
def build_domain_scores(daily: pd.DataFrame, domain_name: str, config: dict, settings: dict):
    component_pairs = []
    sleep_pills_pct = build_sleeping_pills_flag_series(daily) * 100.0 if COL_SLEEPING_PILLS in daily.columns else pd.Series(0.0, index=daily.index)

    for label, source_col, inverse, weight_key in config["components"]:
        out_col = f"{domain_name} - {label}"
        daily[out_col] = normalize_0_10_to_pct(daily.get(source_col, pd.Series(0, index=daily.index)), inverse=inverse)
        if label == "Low Sleep Quality": daily[out_col] = pd.concat([daily[out_col], sleep_pills_pct], axis=1).max(axis=1)
        component_pairs.append((out_col, float(settings[weight_key])))

    flag_score_col, flags_col = f"{domain_name} - Flags", f"{domain_name} Flags"
    if config.get("custom_flag_logic") == "depression":
        daily[flags_col] = build_daily_depression_flag_series(daily)
        daily[flag_score_col] = normalize_flag_count_to_pct(daily[flags_col], max_flags=1)
    else:
        flag_cols = [c for c in config["flags"] if c in daily.columns]
        daily[flags_col] = daily[flag_cols].sum(axis=1) if flag_cols else 0
        daily[flag_score_col] = normalize_flag_count_to_pct(daily[flags_col], max_flags=len(flag_cols)) if flag_cols else 0.0

    component_pairs.append((flag_score_col, float(settings[config["flag_weight_key"]])))
    score_col, avg_col, dev_col = f"{domain_name} Score %", f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average ({domain_name} %)", f"{domain_name} Deviation %"
    daily[score_col] = weighted_average_percent(daily, component_pairs)
    daily[avg_col] = daily[score_col].rolling(window=DAILY_ROLLING_WINDOW_DAYS, min_periods=1).mean()
    daily[dev_col] = daily[score_col] - daily[avg_col]
    return daily

def add_personal_baselines(df: pd.DataFrame, settings: dict, domains: list[str]) -> pd.DataFrame:
    if df.empty: return df
    working = df.copy()
    window = max(3, int(settings.get("baseline_window_days", 14)))
    for name in domains:
        score_col, baseline_col, baseline_diff_col, baseline_std_col, baseline_z_col = f"{name} Score %", f"{name} Baseline %", f"{name} Baseline Difference %", f"{name} Baseline Std %", f"{name} Baseline Z"
        prev_scores = working[score_col].shift(1)
        baseline = prev_scores.rolling(window=window, min_periods=3).mean()
        baseline_std = prev_scores.rolling(window=window, min_periods=3).std()
        working[baseline_col], working[baseline_std_col], working[baseline_diff_col] = baseline, baseline_std, working[score_col] - baseline
        safe_std = baseline_std.where((baseline_std.notna()) & (baseline_std > 0), 1.0)
        z = (working[score_col] - working[baseline_col]) / safe_std
        working[baseline_z_col] = z.where(working[baseline_col].notna(), 0.0).fillna(0.0)
    return working

def build_domain_summary(df: pd.DataFrame, settings: dict, domains: list[str], include_reasons: bool = True) -> dict:
    if df.empty: return {}
    latest, last5 = df.iloc[-1], df.tail(5)
    med_pct, high_pct, trend_pct, anomaly_thr, high_anomaly_thr = float(settings["medium_threshold_pct"]), float(settings["high_threshold_pct"]), float(settings["trend_threshold_pct"]), float(settings.get("anomaly_z_threshold", 1.5)), float(settings.get("high_anomaly_z_threshold", 2.5))
    summary = {}
    for name in domains:
        score_pct, dev_pct = to_float(latest.get(f"{name} Score %", 0.0)), to_float(latest.get(f"{name} Deviation %", 0.0))
        level, trend = level_from_percent(score_pct, med_pct, high_pct), trend_from_deviation_pct(dev_pct, trend_pct)
        z_val, diff_val = to_float(latest.get(f"{name} Baseline Z", 0.0)), to_float(latest.get(f"{name} Baseline Difference %", 0.0))
        
        baseline_note, baseline_z_text = "", ""
        if abs(z_val) >= anomaly_thr:
            prefix = "much " if abs(z_val) >= high_anomaly_thr else "noticeably "
            baseline_note = f"{prefix}{'higher' if diff_val >= 0 else 'lower'} than your recent baseline ({diff_val:+.1f} points)"
            baseline_z_text = f"z={z_val:+.2f}"
        elif pd.notna(latest.get(f"{name} Baseline %", pd.NA)):
            baseline_note, baseline_z_text = f"close to your recent baseline ({diff_val:+.1f} points)", f"z={z_val:+.2f}"

        item = {"score_pct": score_pct, "level": level, "trend": trend, "confidence": confidence_from_count(len(last5), trend, level), "baseline_z": z_val, "baseline_diff_pct": diff_val, "baseline_note": baseline_note, "baseline_z_text": baseline_z_text}
        
        if include_reasons:
            raw_reasons = sorted([(c, to_float(latest.get(c, 0.0))) for c in df.columns if c.startswith(f"{name} - ")], key=lambda x: x[1], reverse=True)
            item["reasons"] = [REASON_LABELS.get(col, col.replace(f"{name} - ", "")) for col, value in raw_reasons if value > 0][:4]

        if name == "Depression" and to_int(latest.get("Depression Flags", 0)) == 0:
            item.update({"level": "Low", "trend": "Stable", "confidence": "Low", "reasons": [], "baseline_note": "", "baseline_z_text": ""})
        summary[name] = item
    return summary

# =========================================================
# DAILY MODEL
# =========================================================
def build_daily_model_from_form(form_df: pd.DataFrame, settings: dict):
    if form_df.empty or "Timestamp" not in form_df.columns: return pd.DataFrame(), None
    working = convert_numeric(form_df.copy())
    working["Timestamp"], working["Date"] = pd.to_datetime(working["Timestamp"], errors="coerce"), pd.to_datetime(working["Timestamp"], errors="coerce").dt.date
    
    sig_cols = [c for c in working.columns if c.startswith("Signals and indicators [")]
    for col in sig_cols: working[col] = working[col].apply(bool_from_response).astype(int)
    num_cols = [c for c in [COL_MOOD, COL_SLEEP_HOURS, COL_SLEEP_QUALITY, COL_ENERGY, COL_MENTAL_SPEED, COL_IMPULSIVITY, COL_MOTIVATION, COL_IRRITABILITY, COL_AGITATION, COL_UNUSUAL, COL_SUSPICIOUS, COL_CERTAINTY] if c in working.columns]

    daily_scores = working.groupby("Date", as_index=False)[num_cols].mean() if num_cols else pd.DataFrame({"Date": working["Date"].dropna().unique()})
    daily_flags = working.groupby("Date", as_index=False)[sig_cols].sum() if sig_cols else pd.DataFrame({"Date": working["Date"].dropna().unique()})
    sleep_med_df = working.groupby("Date", as_index=False)[COL_SLEEPING_PILLS].agg(lambda s: int(any(bool_from_response(v) for v in s))) if COL_SLEEPING_PILLS in working.columns else pd.DataFrame({"Date": working["Date"].dropna().unique()})

    daily = daily_scores.merge(daily_flags, on="Date", how="outer").merge(sleep_med_df, on="Date", how="outer").sort_values("Date").reset_index(drop=True)
    daily["DateLabel"] = pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")
    if COL_SLEEPING_PILLS in daily.columns: daily[COL_SLEEPING_PILLS] = daily[COL_SLEEPING_PILLS].fillna(0).astype(int)
    for domain_name, config in DAILY_DOMAIN_CONFIG.items(): daily = build_domain_scores(daily, domain_name, config, settings)
    
    daily["Sleeping Pills Flag"] = build_sleeping_pills_flag_series(daily)
    mixed_weight_total = max(1.0, float(settings["mixed_dep_weight"]) + float(settings["mixed_mania_weight"]) + float(settings["mixed_psych_weight"]) + float(settings["mixed_low_sleep_quality_weight"]))
    daily["Mixed Score %"] = (daily["Depression Score %"] * float(settings["mixed_dep_weight"]) + daily["Mania Score %"] * float(settings["mixed_mania_weight"]) + daily["Psychosis Score %"] * float(settings["mixed_psych_weight"]) + daily.get("Depression - Low Sleep Quality", pd.Series(0, index=daily.index)) * float(settings["mixed_low_sleep_quality_weight"])) / mixed_weight_total
    daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"] = daily["Mixed Score %"].rolling(window=DAILY_ROLLING_WINDOW_DAYS, min_periods=1).mean()
    daily["Mixed Deviation %"] = daily["Mixed Score %"] - daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"]

    daily["Mixed Flags"] = daily[[c for c in [SIG_MIXED_NOW, SIG_MIXED_COMING, SIG_WITHDRAW, SIG_LESS_SLEEP, SIG_MORE_ACTIVITY] if c in daily.columns]].sum(axis=1) if any(c in daily.columns for c in [SIG_MIXED_NOW, SIG_MIXED_COMING, SIG_WITHDRAW, SIG_LESS_SLEEP, SIG_MORE_ACTIVITY]) else 0
    daily["Concerning Situation Flags"] = daily[[c for c in [SIG_NOT_MYSELF, SIG_MISSED_MEDS, SIG_ROUTINE, SIG_STRESS_PSYCH, SIG_STRESS_PHYS] if c in daily.columns]].sum(axis=1) if any(c in daily.columns for c in [SIG_NOT_MYSELF, SIG_MISSED_MEDS, SIG_ROUTINE, SIG_STRESS_PSYCH, SIG_STRESS_PHYS]) else 0
    daily["Self-Reported Depression"] = daily[[c for c in [SIG_DOWN_NOW, SIG_DOWN_COMING] if c in daily.columns]].sum(axis=1) if any(c in daily.columns for c in [SIG_DOWN_NOW, SIG_DOWN_COMING]) else 0
    daily["Self-Reported Mania"] = daily[[c for c in [SIG_UP_NOW, SIG_UP_COMING] if c in daily.columns]].sum(axis=1) if any(c in daily.columns for c in [SIG_UP_NOW, SIG_UP_COMING]) else 0
    daily["Self-Reported Mixed"] = daily[[c for c in [SIG_MIXED_NOW, SIG_MIXED_COMING] if c in daily.columns]].sum(axis=1) if any(c in daily.columns for c in [SIG_MIXED_NOW, SIG_MIXED_COMING]) else 0

    return add_personal_baselines(daily, settings, DOMAIN_NAMES), build_domain_summary(add_personal_baselines(daily, settings, DOMAIN_NAMES), settings, DOMAIN_NAMES)

# =========================================================
# SNAPSHOT MODEL
# =========================================================
def build_snapshot_model_from_quick_form(quick_form_df: pd.DataFrame, settings: dict):
    if quick_form_df.empty or "Timestamp" not in quick_form_df.columns: return None, pd.DataFrame()
    working = drop_blank_tail_rows(quick_form_df.copy(), ["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    
    for domain_name, config in SNAPSHOT_DOMAIN_CONFIG.items():
        working[f"{domain_name} Score %"] = weighted_average_percent_from_responses(working, [(col, float(settings[weight_key])) for col, weight_key in config["components"]])

    working["Depression Flags"] = build_snapshot_depression_flag_series(working)
    mixed_weight = max(1.0, float(settings["mixed_dep_weight"]) + float(settings["mixed_mania_weight"]) + float(settings["mixed_psych_weight"]))
    working["Mixed Score %"] = (working["Depression Score %"] * float(settings["mixed_dep_weight"]) + working["Mania Score %"] * float(settings["mixed_mania_weight"]) + working["Psychosis Score %"] * float(settings["mixed_psych_weight"])) / mixed_weight

    for name in DOMAIN_NAMES:
        score_col, avg_col, dev_col = f"{name} Score %", f"10-Response Average ({name} %)", f"Deviation From 10-Response Average ({name} %)"
        working[avg_col], working[dev_col] = working[score_col].rolling(10, 1).mean(), working[score_col] - working[score_col].rolling(10, 1).mean()

    working["FilterDate"], working["TimeLabel"] = working["Timestamp"].dt.date, working["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")

    summary = {}
    if not working.empty:
        latest, last5 = working.iloc[-1], working.tail(5)
        med_pct, high_pct, trend_pct = float(settings["medium_threshold_pct"]), float(settings["high_threshold_pct"]), float(settings["trend_threshold_pct"])
        for name in DOMAIN_NAMES:
            score, dev = to_float(latest.get(f"{name} Score %")), to_float(latest.get(f"Deviation From 10-Response Average ({name} %)", 0.0))
            level, trend = level_from_percent(score, med_pct, high_pct), trend_from_deviation_pct(dev, trend_pct)
            conf = confidence_from_count(len(last5), trend, level)
            if name == "Depression" and to_int(latest.get("Depression Flags", 0)) == 0: level, trend, conf = "Low", "Stable", "Low"
            summary[name] = {"score_pct": score, "level": level, "trend": trend, "confidence": conf}
    return summary, working

def weighted_average_percent_from_responses(df: pd.DataFrame, col_weight_pairs: list[tuple[str, float]]) -> pd.Series:
    num, den = pd.Series(0.0, index=df.index), 0.0
    for col, weight in col_weight_pairs:
        if col in df.columns and weight > 0:
            num += (df[col].apply(score_response_pct) * weight)
            den += weight
    return num / den if den > 0 else pd.Series(0.0, index=df.index)

# =========================================================
# ALERT ENGINE / TODAY SUMMARY
# =========================================================
def get_domain_persistence(df: pd.DataFrame, domain: str, medium_threshold: float, days: int) -> int:
    return int((df[f"{domain} Score %"].tail(days) >= medium_threshold).all()) if not df.empty and len(df) >= days else 0

def build_alerts(daily_model_data: pd.DataFrame, daily_summary: dict | None, snapshot_summary: dict | None, settings: dict, snapshot_model_data: pd.DataFrame | None = None):
    alerts = []
    if daily_model_data.empty or not daily_summary: return alerts
    latest, med_pct, anomaly_thr, high_anomaly_thr, pers_days = daily_model_data.iloc[-1], float(settings["medium_threshold_pct"]), float(settings.get("anomaly_z_threshold", 1.5)), float(settings.get("high_anomaly_z_threshold", 2.5)), int(settings.get("persistence_days", 3))
    
    daily_dep_flag = to_int(latest.get("Depression Flags", 0)) > 0
    snap_dep_flag = to_int(snapshot_model_data.iloc[-1].get("Depression Flags", 0)) > 0 if snapshot_model_data is not None and not snapshot_model_data.empty else False

    for name in DOMAIN_NAMES:
        if name == "Depression" and not daily_dep_flag: continue
        item, details = daily_summary[name], []
        if item["level"] in ["Medium", "High"]: details.append(f"{name} score is {item['level'].lower()} at {item['score_pct']:.1f}%.")
        if item["trend"] in ["Rising", "Falling"]: details.append(f"Recent direction is {item['trend'].lower()}.")
        
        z_val, diff_val = to_float(item.get("baseline_z")), to_float(item.get("baseline_diff_pct"))
        if abs(z_val) >= anomaly_thr: details.append(f"This is {abs(diff_val):.1f} points {'above' if diff_val >= 0 else 'below'} your personal baseline (z={z_val:+.2f}).")
        if get_domain_persistence(daily_model_data, name, med_pct, pers_days): details.append(f"This pattern has stayed at or above medium for the last {pers_days} days.")
        
        snap_agrees = snapshot_summary and name in snapshot_summary and snapshot_summary[name]["level"] in ["Medium", "High"] and (name != "Depression" or snap_dep_flag)
        if snap_agrees: details.append(f"Snapshot model also shows {name.lower()} as {snapshot_summary[name]['level'].lower()}.")

        severity = "High concern" if item["level"] == "High" else "Pay attention today" if (item["level"] == "Medium" and item["trend"] == "Rising") or abs(z_val) >= high_anomaly_thr or (snap_agrees and item["level"] in ["Medium", "High"]) or get_domain_persistence(daily_model_data, name, med_pct, pers_days) else "Monitor" if abs(z_val) >= anomaly_thr and item["score_pct"] >= (med_pct * 0.8) else None
        if severity: alerts.append({"severity": severity, "domain": name, "title": f"{name} pattern", "summary": f"{name} looks {item['level'].lower()} with a {item['trend'].lower()} recent direction." + (" It is also unusual relative to your recent baseline." if abs(z_val) >= anomaly_thr else ""), "details": details})

    conc_flags = to_int(latest.get("Concerning Situation Flags", 0))
    if conc_flags > 0: alerts.append({"severity": "Pay attention today" if conc_flags <= 2 else "High concern", "domain": "General", "title": "Concerning situation flags", "summary": f"{conc_flags} concerning situation flag(s) were recorded.", "details": ["These can matter even if main scores are not high.", "Check routine disruption, missed meds, or stressors."]})

    active_high, active_med = [d for d in DOMAIN_NAMES if d != "Depression" and daily_summary[d]["level"] == "High"], [d for d in DOMAIN_NAMES if d != "Depression" and daily_summary[d]["level"] in ["Medium", "High"]]
    if daily_dep_flag and daily_summary["Depression"]["level"] in ["Medium", "High"]:
        active_med.append("Depression")
        if daily_summary["Depression"]["level"] == "High": active_high.append("Depression")
    if len(active_high) >= 2 or len(active_med) >= 3: alerts.append({"severity": "High concern", "domain": "General", "title": "Multiple elevated patterns", "summary": "More than one domain is elevated.", "details": [f"Elevated domains: {', '.join(active_med)}.", "May be worth extra attention."]})
    return sorted(alerts, key=lambda a: (-alert_rank(a["severity"]), a["title"]))

def build_today_summary(daily_summary: dict | None, alerts: list[dict], daily_model_data: pd.DataFrame):
    if not daily_summary or daily_model_data.empty: return "No daily interpretation is available yet."
    primary_name, primary = sorted(daily_summary.items(), key=lambda kv: ({"High": 3, "Medium": 2, "Low": 1}.get(kv[1]["level"], 0), kv[1]["score_pct"], abs(kv[1].get("baseline_z", 0.0))), reverse=True)[0]
    summary = f"Main pattern today: {primary_name.lower()} looks {primary['level'].lower()}{f' and is {primary['trend'].lower()}' if primary['trend'] != 'Stable' else ''} ({primary['score_pct']:.1f}%)."
    if primary.get("baseline_note"): summary += f" Compared with your usual pattern, it is {primary['baseline_note']}."
    if primary.get("reasons"): summary += f" Main drivers: {', '.join(primary['reasons'][:3])}."
    if alerts: summary += f" Overall status: {alerts[0]['severity']}."
    return summary

# =========================================================
# WARNING HELPERS
# =========================================================
def get_latest_form_warning_items(form_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if form_df.empty or "Timestamp" not in form_df.columns: return [], []
    latest = form_df.sort_values("Timestamp").iloc[-1]
    flagged = [prettify_signal_name(col) for col in form_df.columns if col.startswith("Signals and indicators [") and bool_from_response(latest.get(col, ""))]
    
    concerning = []
    checks = [(COL_MOOD, "Mood score is low", lambda v: v <= 4), (COL_SLEEP_HOURS, "Sleep hours are low", lambda v: v <= 5), (COL_SLEEP_QUALITY, "Sleep quality is poor", lambda v: v <= 4), (COL_MOTIVATION, "Motivation is low", lambda v: v <= 4), (COL_ENERGY, "Energy is elevated", lambda v: v >= 6), (COL_MENTAL_SPEED, "Mental speed is elevated", lambda v: v >= 6), (COL_IMPULSIVITY, "Impulsivity is elevated", lambda v: v >= 6), (COL_IRRITABILITY, "Irritability is elevated", lambda v: v >= 6), (COL_AGITATION, "Agitation is elevated", lambda v: v >= 6), (COL_UNUSUAL, "Unusual perceptions are elevated", lambda v: v >= 6), (COL_SUSPICIOUS, "Suspiciousness is elevated", lambda v: v >= 6), (COL_CERTAINTY, "Belief certainty is elevated", lambda v: v >= 6)]
    for col, label, cond in checks:
        if col in latest.index and pd.notna(val := pd.to_numeric(latest[col], errors="coerce")) and cond(val): concerning.append(f"{label} ({val:.1f})")
    if COL_SLEEPING_PILLS in latest.index and bool_from_response(latest.get(COL_SLEEPING_PILLS, "")): concerning.append("Took sleeping medication (treat as bad sleep flag)")
    return flagged, concerning

def get_latest_quick_form_warning_items(quick_form_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if quick_form_df.empty or "Timestamp" not in quick_form_df.columns: return [], []
    latest = quick_form_df.sort_values("Timestamp").iloc[-1]
    signals = [f"{prettify_signal_name(col)} — {'Yes' if str(latest.get(col, '')).strip().lower() == 'yes' else 'Somewhat'}" for col in quick_form_df.columns if col != "Timestamp" and not any(col.endswith(s) for s in [" Numeric", " Percent", " Trend"]) and str(latest.get(col, '')).strip().lower() in ["yes", "somewhat"]]
    
    y_cnt, s_cnt = sum(1 for i in signals if i.endswith("Yes")), sum(1 for i in signals if i.endswith("Somewhat"))
    concerning = [msg for cnt, msg in [(y_cnt, f"Several snapshot symptoms are marked Yes ({y_cnt})"), (s_cnt, f"Several snapshot symptoms are marked Somewhat ({s_cnt})")] if cnt >= 3]
    return signals, concerning

def get_model_concerning_findings(daily_summary, snapshot_summary, daily_model_df, snapshot_model_df):
    daily_find, snap_find = [], []
    d_flag = to_int(daily_model_df.iloc[-1].get("Depression Flags", 0)) > 0 if not daily_model_df.empty else False
    s_flag = to_int(snapshot_model_df.iloc[-1].get("Depression Flags", 0)) > 0 if not snapshot_model_df.empty else False

    if daily_summary and not daily_model_df.empty:
        for name in DOMAIN_NAMES:
            if name == "Depression" and not d_flag: continue
            if daily_summary[name]["level"] in ["Medium", "High"]: daily_find.append(f"Daily {name.lower()} is {daily_summary[name]['level'].lower()} and {daily_summary[name]['trend'].lower()}")
            if abs(to_float(daily_summary[name].get("baseline_z"))) >= 1.5: daily_find.append(f"Daily {name.lower()} is unusual relative to your recent baseline")
        if (c_flags := to_float(daily_model_df.iloc[-1].get("Concerning Situation Flags", 0))) > 0: daily_find.append(f"Concerning situation flags: {int(c_flags)}")

    if snapshot_summary:
        for name in DOMAIN_NAMES:
            if name == "Depression" and not s_flag: continue
            if snapshot_summary[name]["level"] in ["Medium", "High"]: snap_find.append(f"Snapshot {name.lower()} is {snapshot_summary[name]['level'].lower()} and {snapshot_summary[name]['trend'].lower()}")
    if s_flag: snap_find.append("Snapshot depression flag is present")
    return daily_find, snap_find

# =========================================================
# PAGE RENDERERS
# =========================================================
def render_dashboard_page(form_data, quick_form_data, daily_model_data, daily_model_summary, snapshot_model_summary, latest_form_signals, latest_form_findings, latest_snapshot_signals, latest_snapshot_findings, daily_model_findings, snapshot_model_findings, alerts, today_summary):
    st.subheader("Dashboard")
    st.caption("Daily Model is calculated from Form Responses with adjustable settings. Snapshot Model is calculated from Quick Form Responses with adjustable settings.")
    top_alert = alerts[0]["severity"] if alerts else "Monitor"
    render_two_column_flag_box("Today at a glance", [today_summary], tone="error" if top_alert == "High concern" else "warning" if top_alert == "Pay attention today" else "info")
    
    st.markdown("### Current alerts")
    if alerts:
        cols = st.columns(min(3, len(alerts)))
        for idx, alert in enumerate(alerts[:3]):
            with cols[idx]: render_alert_card(alert)
    else: st.info("No active alerts are being generated from the current rules.")

    st.markdown("### Current state\n#### Daily Model")
    render_summary_cards(daily_model_summary, detailed=True)
    st.markdown("#### Snapshot Model")
    render_summary_cards(snapshot_model_summary, detailed=False)

    st.markdown("### Key warnings")
    warn_left, warn_right = st.columns(2)
    with warn_left: render_two_column_flag_box("Daily questionnaire / model", latest_form_findings + daily_model_findings + latest_form_signals, tone="error" if (latest_form_findings or daily_model_findings) else "warning")
    with warn_right: render_two_column_flag_box("Snapshot questionnaire / model", latest_snapshot_findings + snapshot_model_findings + latest_snapshot_signals, tone="error" if (latest_snapshot_findings or snapshot_model_findings) else "warning")

    st.markdown("### Recent trends")
    if not daily_model_data.empty:
        trend_df = daily_model_data.copy()
        min_d, max_d = pd.to_datetime(trend_df["Date"]).min().date(), pd.to_datetime(trend_df["Date"]).max().date()
        quick_range = st.selectbox("Trend window", ["Last 7 days", "Last 14 days", "Last 30 days", "All data"], index=1, key="dashboard_trend_window")
        start_date = max_d - pd.Timedelta(days={"Last 7 days": 6, "Last 14 days": 13, "Last 30 days": 29}.get(quick_range, (max_d - min_d).days))
        st.line_chart(trend_df[(pd.to_datetime(trend_df["Date"]).dt.date >= start_date) & (pd.to_datetime(trend_df["Date"]).dt.date <= max_d)][["DateLabel", "Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"]].set_index("DateLabel"))
    else: st.info("No daily trend data available.")

    st.markdown("### Personal baseline")
    if not daily_model_data.empty:
        ld = daily_model_data.iloc[-1]
        for col, label, key in zip(st.columns(4), ["Depression", "Mania", "Psychosis", "Mixed"], [f"{n} Baseline Difference %" for n in ["Depression", "Mania", "Psychosis", "Mixed"]]):
            with col: st.metric(f"{label} vs baseline", f"{to_float(ld.get(key, 0.0)):+.1f} pp")
    else: st.info("No personal baseline data available.")

    st.markdown("### Flags overview")
    if not daily_model_data.empty:
        ld = daily_model_data.iloc[-1]
        for col, title, key in zip(st.columns(4), ["Concerning flags", "Depression flags", "Mania flags", "Psychosis flags"], ["Concerning Situation Flags", "Depression Flags", "Mania Flags", "Psychosis Flags"]):
            with col: st.metric(title, to_int(ld.get(key, 0)))
    else: st.info("No flag overview available.")

    st.markdown("### Recent activity")
    for col, title, val in zip(st.columns(4), ["Latest form entry", "Latest snapshot entry", "Days tracked", "Snapshot entries (last 7d)"], [
        form_data["Timestamp"].max().strftime("%Y-%m-%d %H:%M") if not form_data.empty and "Timestamp" in form_data.columns else "N/A",
        quick_form_data["Timestamp"].max().strftime("%Y-%m-%d %H:%M") if not quick_form_data.empty and "Timestamp" in quick_form_data.columns else "N/A",
        len(daily_model_data),
        int((pd.to_datetime(quick_form_data["Timestamp"], errors="coerce").dropna() >= (quick_form_data["Timestamp"].max() - pd.Timedelta(days=7))).sum()) if not quick_form_data.empty and "Timestamp" in quick_form_data.columns else 0
    ]):
        with col: st.metric(title, val)

def render_warnings_page(daily_model_summary, snapshot_model_summary, latest_form_signals, latest_form_findings, latest_snapshot_signals, latest_snapshot_findings, daily_model_findings, snapshot_model_findings, alerts, today_summary):
    st.subheader("Warnings")
    render_two_column_flag_box("Today at a glance", [today_summary], tone="info")
    st.markdown("### Alert engine output")
    [render_alert_card(a) for a in alerts] if alerts else st.info("No alerts are currently being generated.")
    st.markdown("### Current State — Daily Model")
    render_summary_cards(daily_model_summary, detailed=True)
    st.markdown("### Current State — Snapshot Model")
    render_summary_cards(snapshot_model_summary, detailed=False)
    left, right = st.columns(2)
    with left:
        render_two_column_flag_box("Daily questionnaire — warning signals", latest_form_signals, tone="warning")
        render_two_column_flag_box("Daily questionnaire — concerning findings", latest_form_findings + daily_model_findings, tone="error")
    with right:
        render_two_column_flag_box("Snapshot questionnaire — warning signals", latest_snapshot_signals, tone="warning")
        render_two_column_flag_box("Snapshot questionnaire — concerning findings", latest_snapshot_findings + snapshot_model_findings, tone="error")

def render_daily_model_page(form_data):
    st.subheader("Daily Model")
    st.caption("Calculated from Form Responses with configurable parameters. Scores are shown as percentages.")
    with st.expander("Daily model settings"): render_settings_form("daily_settings", DAILY_SETTINGS_UI)
    daily_model_data, daily_model_summary = build_daily_model_from_form(form_data, st.session_state["daily_settings"])
    if daily_model_data.empty: return st.info("No daily model data available.")
    render_summary_cards(daily_model_summary, detailed=True)
    render_chart_group(daily_model_data, "Date", "DateLabel", DAILY_CHARTS)
    render_dataframe_picker("Daily model data", daily_model_data, [c for c in ["Date", "Depression Score %", "5-Day Average (Depression %)", "Depression Baseline %", "Depression Baseline Difference %", "Depression Baseline Z", "Mania Score %", "5-Day Average (Mania %)", "Mania Baseline %", "Mania Baseline Difference %", "Mania Baseline Z", "Psychosis Score %", "5-Day Average (Psychosis %)", "Psychosis Baseline %", "Psychosis Baseline Difference %", "Psychosis Baseline Z", "Mixed Score %", "5-Day Average (Mixed %)", "Mixed Baseline %", "Mixed Baseline Difference %", "Mixed Baseline Z", "Concerning Situation Flags", "Sleeping Pills Flag", "Depression Flags", "Mania Flags", "Mixed Flags", "Psychosis Flags"] if c in daily_model_data.columns], "daily_model_columns")

def render_snapshot_model_page(quick_form_data):
    st.subheader("Snapshot Model")
    st.caption("Calculated from Quick Form Responses. Symptom scoring converts No/Somewhat/Yes from 0/1/2 into 0/50/100%.")
    with st.expander("Snapshot model settings"): render_settings_form("snapshot_settings", SNAPSHOT_SETTINGS_UI)
    snapshot_model_summary, snapshot_model_data = build_snapshot_model_from_quick_form(quick_form_data, st.session_state["snapshot_settings"])
    if snapshot_model_summary is None or snapshot_model_data.empty: return st.info("No snapshot model data available.")
    render_summary_cards(snapshot_model_summary, detailed=False)
    render_chart_group(snapshot_model_data, "FilterDate", "TimeLabel", SNAPSHOT_CHARTS)
    render_dataframe_picker("Snapshot model data", snapshot_model_data, [c for c in ["Timestamp", "Depression Score %", "Depression Flags", "Mania Score %", "Psychosis Score %", "Mixed Score %", "10-Response Average (Depression %)", "10-Response Average (Mania %)", "10-Response Average (Psychosis %)", "10-Response Average (Mixed %)", "Deviation From 10-Response Average (Depression %)", "Deviation From 10-Response Average (Mania %)", "Deviation From 10-Response Average (Psychosis %)", "Deviation From 10-Response Average (Mixed %)"] if c in snapshot_model_data.columns], "snapshot_model_columns")

def render_form_data_page(form_data):
    st.subheader("Form Data")
    st.caption("Imported directly from Form Responses.")
    render_dataframe_picker("Form Data", form_data, [c for c in ["Timestamp", "Date", "Mood Score", "Sleep (hours)", "Sleep quality", "Energy", "Mental speed", "Impulsivity", "Motivation", "Irritability", "Agitation", "Unusual perceptions", "Suspiciousness", "Certainty and belief in unusual ideas or things others don't believe", "Took sleeping medication?"] if c in form_data.columns], "form_data_columns")

def render_snapshot_data_page(quick_form_data):
    st.subheader("Snapshot Data")
    st.caption("Imported directly from Quick Form Responses. Raw symptom flags are also converted to percentages.")
    render_dataframe_picker("Snapshot Data", quick_form_data, [c for c in ["Timestamp", "Symptoms: [Very low or depressed mood]", "Symptoms: [Very low or depressed mood] Percent", "Symptoms: [Somewhat low or depressed mood]", "Symptoms: [Somewhat low or depressed mood] Percent", "Symptoms: [Very high or elevated mood]", "Symptoms: [Very high or elevated mood] Percent", "Symptoms: [Paranoia or suspicion]", "Symptoms: [Paranoia or suspicion] Percent", "Depression Flags"] if c in quick_form_data.columns], "snapshot_data_columns")

# =========================================================
# APP
# =========================================================
st.title("Wellbeing Dashboard")

try:
    get_workbook()
    st.success("Google Sheets connected successfully.")
except Exception as e:
    st.error("Google Sheets connection failed.")
    st.exception(e)
    st.stop()

# 1. Load Data
form_df = load_sheet(FORM_TAB)
quick_form_df = load_sheet(QUICK_FORM_TAB)
new_daily_df = load_sheet(NEW_DAILY_TAB)

# 2. Prepare Data
form_data_original = prepare_form_raw(form_df)
new_daily_data = prepare_new_daily_sheet(new_daily_df)
quick_form_data = prepare_quick_form_raw(quick_form_df)

# 3. Combine Old and New Daily Data
if not new_daily_data.empty and not form_data_original.empty:
    form_data = pd.concat([form_data_original, new_daily_data], ignore_index=True)
elif not new_daily_data.empty:
    form_data = new_daily_data
else:
    form_data = form_data_original

if not form_data.empty:
    form_data = form_data.sort_values("Timestamp").reset_index(drop=True)

# 4. Build Models
daily_model_data, daily_model_summary = build_daily_model_from_form(form_data, st.session_state["daily_settings"])
snapshot_model_summary, snapshot_model_data = build_snapshot_model_from_quick_form(quick_form_data, st.session_state["snapshot_settings"])

# 5. Extract Insights
latest_form_signals, latest_form_findings = get_latest_form_warning_items(form_data)
latest_snapshot_signals, latest_snapshot_findings = get_latest_quick_form_warning_items(quick_form_data)
daily_model_findings, snapshot_model_findings = get_model_concerning_findings(daily_model_summary, snapshot_model_summary, daily_model_data, snapshot_model_data)

alerts = build_alerts(daily_model_data=daily_model_data, daily_summary=daily_model_summary, snapshot_summary=snapshot_model_summary, settings=st.session_state["daily_settings"], snapshot_model_data=snapshot_model_data)
today_summary = build_today_summary(daily_summary=daily_model_summary, alerts=alerts, daily_model_data=daily_model_data)

# 6. Render UI Tabs
tabs = st.tabs(["Dashboard", "Warnings", "Daily Model", "Snapshot Model", "Form Data", "Snapshot Data"])

with tabs[0]: render_dashboard_page(form_data, quick_form_data, daily_model_data, daily_model_summary, snapshot_model_summary, latest_form_signals, latest_form_findings, latest_snapshot_signals, latest_snapshot_findings, daily_model_findings, snapshot_model_findings, alerts, today_summary)
with tabs[1]: render_warnings_page(daily_model_summary, snapshot_model_summary, latest_form_signals, latest_form_findings, latest_snapshot_signals, latest_snapshot_findings, daily_model_findings, snapshot_model_findings, alerts, today_summary)
with tabs[2]: render_daily_model_page(form_data)
with tabs[3]: render_snapshot_model_page(quick_form_data)
with tabs[4]: render_form_data_page(form_data)
with tabs[5]: render_snapshot_data_page(quick_form_data)
