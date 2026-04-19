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

    if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
        st.text_input("Enter password", type="password", on_change=password_entered, key="password")
        if "authenticated" in st.session_state:
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
DOMAIN_NAMES = ["Depression", "Mania", "Psychosis", "Mixed"]
DAILY_ROLLING_WINDOW_DAYS = 5

COLUMN_ALIASES = {
    "Signals and indicators [Avoided normal responsiblities]":
        "Signals and indicators [Avoided normal responsibilities]",
    "Certainty and  belief in unusual ideas or things others don't believe":
        "Certainty and belief in unusual ideas or things others don't believe",
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

SIG_NOT_MYSELF     = 'Signals and indicators [Felt "not like myself"]'
SIG_MOOD_SHIFT     = "Signals and indicators [Noticed a sudden mood shift]"
SIG_LESS_SLEEP     = "Signals and indicators [Needed less sleep than usual without feeling tired]"
SIG_MORE_ACTIVITY  = "Signals and indicators [Started more activities than usual]"
SIG_WITHDRAW       = "Signals and indicators [Withdrew socially or emotionally from others]"
SIG_AVOID_RESP     = "Signals and indicators [Avoided normal responsibilities]"
SIG_HEARD_SAW      = "Signals and indicators [Heard or saw something others didn't]"
SIG_WATCHED        = "Signals and indicators [Felt watched, followed, targeted]"
SIG_SPECIAL_MEANING= "Signals and indicators [Felt something had special meaning for me]"
SIG_TROUBLE_TRUST  = "Signals and indicators [Trouble trusting perceptions and thoughts]"
SIG_MISSED_MEDS    = "Signals and indicators [Missed meds]"
SIG_ROUTINE        = "Signals and indicators [Significant disruption to routine]"
SIG_STRESS_PSYCH   = "Signals and indicators [Major stressor or trigger (psychological)]"
SIG_STRESS_PHYS    = "Signals and indicators [Major stressor or trigger (physiological)]"
SIG_UP_NOW         = "Signals and indicators [Feel like I'm experiencing an up]"
SIG_DOWN_NOW       = "Signals and indicators [Feel like I'm experiencing a down]"
SIG_MIXED_NOW      = "Signals and indicators [Feel like I'm experiencing a mixed]"
SIG_UP_COMING      = "Signals and indicators [Feel like I'm going to experience an up]"
SIG_DOWN_COMING    = "Signals and indicators [Feel like I'm going to experience a down]"
SIG_MIXED_COMING   = "Signals and indicators [Feel like I'm going to experience a mixed]"

DEFAULT_DAILY_SETTINGS = {
    "dep_low_mood_weight": 4.0, "dep_low_sleep_quality_weight": 1.0,
    "dep_low_energy_weight": 1.0, "dep_low_mental_speed_weight": 1.0,
    "dep_low_motivation_weight": 2.0, "dep_flag_weight": 1.0,
    "mania_high_mood_weight": 1.0, "mania_low_sleep_quality_weight": 2.0,
    "mania_high_energy_weight": 1.5, "mania_high_mental_speed_weight": 1.5,
    "mania_high_impulsivity_weight": 1.5, "mania_high_irritability_weight": 2.0,
    "mania_high_agitation_weight": 2.0, "mania_flag_weight": 2.0,
    "psych_unusual_weight": 1.0, "psych_suspicious_weight": 1.0,
    "psych_certainty_weight": 3.0, "psych_flag_weight": 1.0,
    "mixed_dep_weight": 0.4, "mixed_mania_weight": 0.4,
    "mixed_psych_weight": 0.2, "mixed_low_sleep_quality_weight": 0.5,
    "medium_threshold_pct": 33.0, "high_threshold_pct": 66.0,
    "trend_threshold_pct": 8.0, "baseline_window_days": 14,
    "anomaly_z_threshold": 1.5, "high_anomaly_z_threshold": 2.5,
    "persistence_days": 3,
}

DEFAULT_SNAPSHOT_SETTINGS = {
    "dep_very_low_mood": 4.0, "dep_somewhat_low_mood": 2.0,
    "dep_withdrawal": 1.0, "dep_self_care": 1.0, "dep_slowed_down": 1.0,
    "mania_very_high_mood": 2.0, "mania_somewhat_high_mood": 1.0,
    "mania_agitation": 2.0, "mania_racing": 1.5, "mania_driven": 2.0,
    "psych_hearing_seeing": 1.0, "psych_paranoia": 1.0, "psych_beliefs": 1.0,
    "mixed_dep_weight": 0.4, "mixed_mania_weight": 0.4, "mixed_psych_weight": 0.2,
    "medium_threshold_pct": 33.0, "high_threshold_pct": 66.0, "trend_threshold_pct": 8.0,
}

REASON_LABELS = {
    "Depression - Low Mood Score": "Lower mood",
    "Depression - Low Sleep Quality": "Poor sleep quality",
    "Depression - Low Energy": "Lower energy",
    "Depression - Low Mental Speed": "Slower mental speed",
    "Depression - Low Motivation": "Lower motivation",
    "Depression - Flags": "Depression flag",
    "Mania - High Mood Score": "Higher mood",
    "Mania - Low Sleep Quality": "Poor sleep / reduced restorative sleep",
    "Mania - High Energy": "Higher energy",
    "Mania - High Mental Speed": "Faster mental speed",
    "Mania - High Impulsivity": "Higher impulsivity",
    "Mania - High Irritability": "Higher irritability",
    "Mania - High Agitation": "Higher agitation",
    "Mania - Flags": "Mania-related flags",
    "Psychosis - Unusual perceptions": "Unusual perceptions",
    "Psychosis - Suspiciousness": "Suspiciousness",
    "Psychosis - Certainty": "Strong certainty in unusual beliefs",
    "Psychosis - Flags": "Psychosis-related flags",
}


# =========================================================
# MODEL CONFIG
# =========================================================
DAILY_DOMAIN_CONFIG = {
    "Depression": {
        "components": [
            ("Low Mood Score",    COL_MOOD,         True,  "dep_low_mood_weight"),
            ("Low Sleep Quality", COL_SLEEP_QUALITY, True,  "dep_low_sleep_quality_weight"),
            ("Low Energy",        COL_ENERGY,        True,  "dep_low_energy_weight"),
            ("Low Mental Speed",  COL_MENTAL_SPEED,  True,  "dep_low_mental_speed_weight"),
            ("Low Motivation",    COL_MOTIVATION,    True,  "dep_low_motivation_weight"),
        ],
        "flags": [],
        "flag_weight_key": "dep_flag_weight",
        "custom_flag_logic": "depression",
    },
    "Mania": {
        "components": [
            ("High Mood Score",   COL_MOOD,         False, "mania_high_mood_weight"),
            ("Low Sleep Quality", COL_SLEEP_QUALITY, True,  "mania_low_sleep_quality_weight"),
            ("High Energy",       COL_ENERGY,        False, "mania_high_energy_weight"),
            ("High Mental Speed", COL_MENTAL_SPEED,  False, "mania_high_mental_speed_weight"),
            ("High Impulsivity",  COL_IMPULSIVITY,   False, "mania_high_impulsivity_weight"),
            ("High Irritability", COL_IRRITABILITY,  False, "mania_high_irritability_weight"),
            ("High Agitation",    COL_AGITATION,     False, "mania_high_agitation_weight"),
        ],
        "flags": [SIG_LESS_SLEEP, SIG_MORE_ACTIVITY, SIG_UP_NOW, SIG_UP_COMING],
        "flag_weight_key": "mania_flag_weight",
    },
    "Psychosis": {
        "components": [
            ("Unusual perceptions", COL_UNUSUAL,   False, "psych_unusual_weight"),
            ("Suspiciousness",      COL_SUSPICIOUS, False, "psych_suspicious_weight"),
            ("Certainty",           COL_CERTAINTY,  False, "psych_certainty_weight"),
        ],
        "flags": [SIG_HEARD_SAW, SIG_WATCHED, SIG_SPECIAL_MEANING, SIG_TROUBLE_TRUST],
        "flag_weight_key": "psych_flag_weight",
    },
}

SNAPSHOT_DOMAIN_CONFIG = {
    "Depression": {"components": [
        ("Symptoms: [Very low or depressed mood]",    "dep_very_low_mood"),
        ("Symptoms: [Somewhat low or depressed mood]","dep_somewhat_low_mood"),
        ("Symptoms: [Social or emotional withdrawal]","dep_withdrawal"),
        ("Symptoms: [Feeling slowed down]",           "dep_slowed_down"),
        ("Symptoms: [Difficulty with self-care]",     "dep_self_care"),
    ]},
    "Mania": {"components": [
        ("Symptoms: [Very high or elevated mood]",    "mania_very_high_mood"),
        ("Symptoms: [Somewhat high or elevated mood]","mania_somewhat_high_mood"),
        ("Symptoms: [Agitation or restlessness]",     "mania_agitation"),
        ("Symptoms: [Racing thoughts]",               "mania_racing"),
        ("Symptoms: [Driven to activity]",            "mania_driven"),
    ]},
    "Psychosis": {"components": [
        ("Symptoms: [Hearing or seeing things that aren't there]","psych_hearing_seeing"),
        ("Symptoms: [Paranoia or suspicion]",                     "psych_paranoia"),
        ("Symptoms: [Firm belief in things others would not agree with]","psych_beliefs"),
    ]},
}

DAILY_SETTINGS_UI = {
    "Depression weights": [
        ("dep_low_mood_weight",          "Low mood",          0.0, 5.0, 0.1),
        ("dep_low_sleep_quality_weight", "Low sleep quality", 0.0, 5.0, 0.1),
        ("dep_low_energy_weight",        "Low energy",        0.0, 5.0, 0.1),
        ("dep_low_mental_speed_weight",  "Low mental speed",  0.0, 5.0, 0.1),
        ("dep_low_motivation_weight",    "Low motivation",    0.0, 5.0, 0.1),
        ("dep_flag_weight",              "Depression flag",   0.0, 5.0, 0.1),
    ],
    "Mania weights": [
        ("mania_high_mood_weight",        "High mood",                 0.0, 5.0, 0.1),
        ("mania_low_sleep_quality_weight","Low sleep quality (mania)", 0.0, 5.0, 0.1),
        ("mania_high_energy_weight",      "High energy",               0.0, 5.0, 0.1),
        ("mania_high_mental_speed_weight","High mental speed",         0.0, 5.0, 0.1),
        ("mania_high_impulsivity_weight", "High impulsivity",          0.0, 5.0, 0.1),
        ("mania_high_irritability_weight","High irritability",         0.0, 5.0, 0.1),
        ("mania_high_agitation_weight",   "High agitation",            0.0, 5.0, 0.1),
        ("mania_flag_weight",             "Mania flags",               0.0, 5.0, 0.1),
    ],
    "Psychosis weights": [
        ("psych_unusual_weight",   "Unusual perceptions", 0.0, 5.0, 0.1),
        ("psych_suspicious_weight","Suspiciousness",      0.0, 5.0, 0.1),
        ("psych_certainty_weight", "Certainty",           0.0, 5.0, 0.1),
        ("psych_flag_weight",      "Psychosis flags",     0.0, 5.0, 0.1),
    ],
    "Mixed weights": [
        ("mixed_dep_weight",              "Mixed: depression",       0.0, 3.0, 0.05),
        ("mixed_mania_weight",            "Mixed: mania",            0.0, 3.0, 0.05),
        ("mixed_psych_weight",            "Mixed: psychosis",        0.0, 3.0, 0.05),
        ("mixed_low_sleep_quality_weight","Mixed: low sleep quality",0.0, 3.0, 0.05),
    ],
    "Thresholds": [
        ("medium_threshold_pct","Medium threshold (%)",  0.0, 100.0, 1.0),
        ("high_threshold_pct",  "High threshold (%)",    0.0, 100.0, 1.0),
        ("trend_threshold_pct", "Trend threshold (pp)",  0.0, 100.0, 1.0),
    ],
    "Baseline & alert tuning": [
        ("baseline_window_days",    "Baseline window (days)",    3,   60,  1),
        ("anomaly_z_threshold",     "Unusual z-threshold",       0.5, 5.0, 0.1),
        ("high_anomaly_z_threshold","High unusual z-threshold",  0.5, 6.0, 0.1),
        ("persistence_days",        "Persistence days",          2,   14,  1),
    ],
}

SNAPSHOT_SETTINGS_UI = {
    "Depression weights": [
        ("dep_very_low_mood",   "Very low mood",   0.0, 5.0, 0.1),
        ("dep_somewhat_low_mood","Somewhat low mood",0.0,5.0, 0.1),
        ("dep_withdrawal",      "Withdrawal",      0.0, 5.0, 0.1),
        ("dep_slowed_down",     "Slowed down",     0.0, 5.0, 0.1),
        ("dep_self_care",       "Self-care",       0.0, 5.0, 0.1),
    ],
    "Mania weights": [
        ("mania_very_high_mood",   "Very high mood",    0.0, 5.0, 0.1),
        ("mania_somewhat_high_mood","Somewhat high mood",0.0,5.0, 0.1),
        ("mania_agitation",        "Agitation",         0.0, 5.0, 0.1),
        ("mania_racing",           "Racing thoughts",   0.0, 5.0, 0.1),
        ("mania_driven",           "Driven to activity",0.0, 5.0, 0.1),
    ],
    "Psychosis weights": [
        ("psych_hearing_seeing","Hearing / seeing things",0.0, 5.0, 0.1),
        ("psych_paranoia",      "Paranoia",               0.0, 5.0, 0.1),
        ("psych_beliefs",       "Firm unusual beliefs",   0.0, 5.0, 0.1),
    ],
    "Mixed weights": [
        ("mixed_dep_weight",  "Mixed: depression",0.0, 3.0, 0.05),
        ("mixed_mania_weight","Mixed: mania",     0.0, 3.0, 0.05),
        ("mixed_psych_weight","Mixed: psychosis", 0.0, 3.0, 0.05),
    ],
    "Thresholds": [
        ("medium_threshold_pct","Medium threshold (%)", 0.0, 100.0, 1.0),
        ("high_threshold_pct",  "High threshold (%)",   0.0, 100.0, 1.0),
        ("trend_threshold_pct", "Trend threshold (pp)",  0.0, 100.0, 1.0),
    ],
}

DAILY_CHARTS = [
    {"title": "Daily state scores (%)",
     "cols": ["Depression Score %","Mania Score %","Psychosis Score %","Mixed Score %"],
     "key": "daily_state_scores", "type": "line"},
    {"title": "5-day averages (%)",
     "cols": ["5-Day Average (Depression %)","5-Day Average (Mania %)","5-Day Average (Psychosis %)","5-Day Average (Mixed %)"],
     "key": "daily_5day_avg", "type": "line"},
    {"title": "Deviation from 5-day averages (percentage points)",
     "cols": ["Depression Deviation %","Mania Deviation %","Psychosis Deviation %","Mixed Deviation %"],
     "key": "daily_deviation", "type": "line"},
    {"title": "Personal baseline vs current scores",
     "cols": ["Depression Score %","Depression Baseline %","Mania Score %","Mania Baseline %",
              "Psychosis Score %","Psychosis Baseline %","Mixed Score %","Mixed Baseline %"],
     "key": "daily_baseline_vs_current", "type": "line"},
    {"title": "Distance from personal baseline (percentage points)",
     "cols": ["Depression Baseline Difference %","Mania Baseline Difference %",
              "Psychosis Baseline Difference %","Mixed Baseline Difference %"],
     "key": "daily_baseline_diff", "type": "line"},
    {"title": "Unusual-for-me score (z-score)",
     "cols": ["Depression Baseline Z","Mania Baseline Z","Psychosis Baseline Z","Mixed Baseline Z"],
     "key": "daily_baseline_z", "type": "line"},
    {"title": "Flag breakdown by category",
     "cols": ["Concerning Situation Flags","Depression Flags","Mania Flags","Mixed Flags","Psychosis Flags"],
     "key": "daily_flags", "type": "bar"},
    {"title": "Depression drivers",
     "cols": ["Depression - Low Mood Score","Depression - Low Sleep Quality","Depression - Low Energy",
              "Depression - Low Mental Speed","Depression - Low Motivation","Depression - Flags"],
     "key": "daily_depression_drivers", "type": "line"},
    {"title": "Mania drivers",
     "cols": ["Mania - High Mood Score","Mania - Low Sleep Quality","Mania - High Energy",
              "Mania - High Mental Speed","Mania - High Impulsivity","Mania - High Irritability",
              "Mania - High Agitation","Mania - Flags"],
     "key": "daily_mania_drivers", "type": "line"},
    {"title": "Psychosis drivers",
     "cols": ["Psychosis - Unusual perceptions","Psychosis - Suspiciousness",
              "Psychosis - Certainty","Psychosis - Flags"],
     "key": "daily_psychosis_drivers", "type": "line"},
]

SNAPSHOT_CHARTS = [
    {"title": "Snapshot model scores (%)",
     "cols": ["Depression Score %","Mania Score %","Psychosis Score %","Mixed Score %"],
     "key": "snapshot_model_scores", "type": "line"},
    {"title": "Snapshot scores vs 10-response averages (%)",
     "cols": ["Depression Score %","10-Response Average (Depression %)","Mania Score %",
              "10-Response Average (Mania %)","Psychosis Score %","10-Response Average (Psychosis %)",
              "Mixed Score %","10-Response Average (Mixed %)"],
     "key": "snapshot_scores_vs_avg", "type": "line"},
    {"title": "Deviation from 10-response averages (percentage points)",
     "cols": ["Deviation From 10-Response Average (Depression %)","Deviation From 10-Response Average (Mania %)",
              "Deviation From 10-Response Average (Psychosis %)","Deviation From 10-Response Average (Mixed %)"],
     "key": "snapshot_deviation", "type": "line"},
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
def normalize_columns(df):
    return df.rename(columns=COLUMN_ALIASES) if not df.empty else df


def convert_numeric(df):
    if df.empty:
        return df
    for col in df.columns:
        if col in ("Timestamp", "Date", "Date (int)"):
            continue
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().any():
            df[col] = converted
    return df


def bool_from_response(val):
    return str(val).strip().lower() in ("yes", "true", "1", "y", "checked")


def score_response_0_2(val):
    return {"yes": 2, "somewhat": 1}.get(str(val).strip().lower(), 0)


def score_response_pct(val):
    return score_response_0_2(val) / 2 * 100.0


def prettify_signal_name(name):
    return name.replace("Signals and indicators [", "").replace("Symptoms: [", "").replace("]", "")


def drop_blank_tail_rows(df, required_cols):
    present = [c for c in required_cols if c in df.columns]
    return df.dropna(subset=present or None, how="all").copy()


def to_float(value, default=0.0):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(str(value).strip())
    except Exception:
        return default


def to_int(value, default=0):
    return int(round(to_float(value, default)))


def normalize_0_10_to_pct(series, inverse=False):
    s = pd.to_numeric(series if isinstance(series, pd.Series) else pd.Series(series), errors="coerce")
    return ((10 - s).clip(0, 10) / 10.0 * 100.0) if inverse else (s.clip(0, 10) / 10.0 * 100.0)


def normalize_flag_count_to_pct(series, max_flags):
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    return pd.Series(0.0, index=s.index) if max_flags <= 0 else (s.clip(0, max_flags) / max_flags * 100.0)


def weighted_average_percent(df, col_weight_pairs, from_response=False):
    num = pd.Series(0.0, index=df.index)
    denom = 0.0
    for col, weight in col_weight_pairs:
        if col in df.columns and weight > 0:
            vals = df[col].apply(score_response_pct) if from_response else pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            num += vals * weight
            denom += weight
    return num / denom if denom else pd.Series(0.0, index=df.index)


def confidence_from_count(count, trend, level):
    score = (2 if count >= 5 else 1 if count >= 3 else 0) + (1 if trend != "Stable" else 0) + (1 if level in ("Medium", "High") else 0)
    return "High" if score >= 4 else "Medium" if score >= 2 else "Low"


def level_from_percent(score_pct, medium_pct, high_pct):
    s = to_float(score_pct)
    return "High" if s >= high_pct else "Medium" if s >= medium_pct else "Low"


def trend_from_deviation_pct(dev_pct, threshold_pct):
    d = to_float(dev_pct)
    return "Rising" if d > threshold_pct else "Falling" if d < -threshold_pct else "Stable"


def alert_rank(severity):
    return {"Monitor": 1, "Pay attention today": 2, "High concern": 3}.get(severity, 0)


def tone_color_tag(tone):
    return {"error": "red", "warning": "orange", "info": "blue", "success": "green"}.get(tone, "gray")


def split_two(items):
    mid = (len(items) + 1) // 2
    return items[:mid], items[mid:]


def find_possible_columns(df, patterns):
    lowered = {c.lower(): c for c in df.columns}
    return [original for col_lower, original in lowered.items() if any(p in col_lower for p in patterns)]


def build_sleeping_pills_flag_series(daily):
    if COL_SLEEPING_PILLS not in daily.columns:
        return pd.Series(0, index=daily.index, dtype=int)
    vals = daily[COL_SLEEPING_PILLS]
    if pd.api.types.is_numeric_dtype(vals):
        return (pd.to_numeric(vals, errors="coerce").fillna(0) > 0).astype(int)
    return vals.apply(bool_from_response).astype(int)


# =========================================================
# DEPRESSION FLAG LOGIC
# =========================================================
def build_daily_depression_flag_series(daily):
    mood = pd.to_numeric(daily.get(COL_MOOD, pd.Series(pd.NA, index=daily.index)), errors="coerce")
    ms   = pd.to_numeric(daily.get(COL_MENTAL_SPEED, pd.Series(pd.NA, index=daily.index)), errors="coerce")
    mot  = pd.to_numeric(daily.get(COL_MOTIVATION, pd.Series(pd.NA, index=daily.index)), errors="coerce")
    return ((mood <= 3) | ((ms < 4) & (mot < 4))).fillna(False).astype(int)


def build_snapshot_depression_flag_series(df):
    result = pd.Series(False, index=df.index)
    for col in ["Symptoms: [Very low or depressed mood]", "Symptoms: [Somewhat low or depressed mood]"]:
        if col in df.columns:
            result |= df[col].astype(str).str.strip().str.lower().isin(("yes", "somewhat"))
    for col in find_possible_columns(df, ["experiencing a down","going to experience a down",
                                          "in a depression","going into a depression"]):
        result |= df[col].astype(str).str.strip().str.lower().isin(("yes", "somewhat"))
    return result.astype(int)


# =========================================================
# UI HELPERS
# =========================================================
def _render_two_col_list(items, color):
    if not items:
        st.markdown(f":{color}[- None]" if color != "gray" else ":gray[- None]")
        return
    left, right = split_two(items)
    c1, c2 = st.columns(2)
    for col, chunk in ((c1, left), (c2, right)):
        with col:
            for item in chunk:
                st.markdown(f":{color}[- {item}]")


def render_status_card(title, score_pct, level, trend, confidence):
    lc = {"High": "red", "Medium": "orange", "Low": "green"}.get(level, "gray")
    cc = {"High": "green", "Medium": "orange", "Low": "gray"}.get(confidence, "gray")
    tc = {"Rising": "orange", "Falling": "blue", "Stable": "green"}.get(trend, "gray")
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(f"**Current:** :{lc}[{level}] ({score_pct:.1f}%)")
        st.markdown(f"**Trend:** :{tc}[{trend}]")
        st.markdown(f"**Confidence:** :{cc}[{confidence}]")


def render_daily_card(title, data):
    lc = {"High": "red", "Medium": "orange", "Low": "green"}.get(data["level"], "gray")
    cc = {"High": "green", "Medium": "orange", "Low": "gray"}.get(data["confidence"], "gray")
    tc = {"Rising": "orange", "Falling": "blue", "Stable": "green"}.get(data["trend"], "gray")
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(f"**Current state:** :{lc}[{data['level']}] ({data['score_pct']:.1f}%)")
        st.markdown(f"**Recent direction:** :{tc}[{data['trend']}]")
        st.markdown(f"**Confidence:** :{cc}[{data['confidence']}]")
        if data.get("baseline_note"):
            st.markdown(f"**Compared with usual:** {data['baseline_note']}")
        if data.get("baseline_z_text"):
            with st.expander("Baseline detail"):
                st.write(data["baseline_z_text"])
        st.markdown("**Main drivers:**")
        _render_two_col_list(data.get("reasons") or ["No strong drivers"], lc)


def render_two_column_flag_box(title, items, tone="info"):
    color = tone_color_tag(tone)
    with st.container(border=True):
        st.markdown(f"#### :{color}[{title}]")
        _render_two_col_list(items, color)


def render_alert_card(alert):
    tone = {"High concern": "error", "Pay attention today": "warning", "Monitor": "info"}.get(alert["severity"], "info")
    color = tone_color_tag(tone)
    with st.container(border=True):
        st.markdown(f"#### :{color}[{alert['title']}]")
        st.markdown(f"**Status:** :{color}[{alert['severity']}]")
        st.markdown(f"**Summary:** {alert['summary']}")
        if alert.get("details"):
            st.markdown("**Details:**")
            _render_two_col_list(alert["details"], color)


def render_summary_cards(summary, detailed=False):
    if not summary:
        st.info("No summary available.")
        return
    for col, name in zip(st.columns(len(summary)), summary):
        with col:
            if detailed:
                render_daily_card(name, summary[name])
            else:
                render_status_card(name, summary[name]["score_pct"], summary[name]["level"],
                                   summary[name]["trend"], summary[name]["confidence"])


def render_settings_form(session_key, settings_ui, columns_per_row=3):
    for section, items in settings_ui.items():
        st.markdown(f"#### {section}")
        for i in range(0, len(items), columns_per_row):
            row = items[i:i + columns_per_row]
            for col, (key, label, mn, mx, step) in zip(st.columns(len(row)), row):
                with col:
                    cur = st.session_state[session_key][key]
                    is_int = isinstance(step, int) or (isinstance(cur, int) and float(step).is_integer())
                    st.session_state[session_key][key] = st.number_input(
                        label,
                        min_value=int(mn) if is_int else float(mn),
                        max_value=int(mx) if is_int else float(mx),
                        value=int(cur) if is_int else float(cur),
                        step=int(step) if is_int else float(step),
                        key=f"{session_key}_{key}",
                    )


def filter_df_by_date(df, date_col, key_prefix):
    if df.empty or date_col not in df.columns:
        return df
    working = df[df[date_col].notna()].copy()
    if working.empty:
        return working
    dates = pd.to_datetime(working[date_col])
    mn, mx = dates.min().date(), dates.max().date()
    r = st.date_input("Date range", value=(mn, mx), min_value=mn, max_value=mx, key=f"{key_prefix}_date_range")
    start, end = (r[0], r[1]) if isinstance(r, tuple) and len(r) == 2 else (mn, mx)
    return working[(dates.dt.date >= start) & (dates.dt.date <= end)].copy()


def render_filtered_chart(df, date_col, label_col, title, default_cols, key_prefix, chart_type="line"):
    st.markdown(f"### {title}")
    if df.empty:
        st.info("No data available.")
        return
    filtered = filter_df_by_date(df, date_col, key_prefix)
    available = [c for c in default_cols if c in filtered.columns]
    selected = st.multiselect("Series", available, default=available, key=f"{key_prefix}_series")
    if filtered.empty:
        st.info("No data in selected date range.")
        return
    if not selected:
        st.info("Pick at least one series.")
        return
    chart_df = filtered[[label_col] + selected].set_index(label_col)
    (st.bar_chart if chart_type == "bar" else st.line_chart)(chart_df)


def render_chart_group(df, date_col, label_col, chart_defs):
    for chart in chart_defs:
        render_filtered_chart(df, date_col, label_col, chart["title"],
                              chart["cols"], chart["key"], chart["type"])


def render_dataframe_picker(title, df, default_cols, key):
    st.markdown(f"### {title}")
    if df.empty:
        st.info("No data available.")
        return
    selected = st.multiselect(f"Choose {title} columns", df.columns.tolist(),
                              default=default_cols or df.columns.tolist()[:12], key=key)
    if selected:
        st.dataframe(df[selected], use_container_width=True)


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
def load_sheet(tab_name):
    data = get_workbook().worksheet(tab_name).get_all_values()
    if not data:
        return pd.DataFrame()

    headers = [str(h).strip() if h else "" for h in data[0]]
    seen, unique_headers = {}, []
    for i, h in enumerate(headers):
        base = h or f"Unnamed_{i+1}"
        seen[base] = seen.get(base, 0)
        unique_headers.append(f"{base}_{seen[base]}" if seen[base] else base)
        seen[base] += 1 if seen[base] else 1

    df = pd.DataFrame(data[1:], columns=unique_headers).loc[:, lambda d: ~d.columns.duplicated()]
    df = normalize_columns(df)
    for dt_col in ("Timestamp", "Date", "Date (int)"):
        if dt_col in df.columns:
            df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce", dayfirst=True)
    return df


# =========================================================
# PREP FUNCTIONS
# =========================================================
def prepare_form_raw(df):
    if df.empty:
        return df
    working = convert_numeric(df.copy())
    working = drop_blank_tail_rows(working, ["Timestamp", COL_MOOD, COL_SLEEP_QUALITY, COL_ENERGY])
    if "Timestamp" in working.columns:
        working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
        working["Date"] = working["Timestamp"].dt.date
    return working.sort_values("Timestamp").reset_index(drop=True)


def prepare_quick_form_raw(df):
    if df.empty:
        return df
    working = drop_blank_tail_rows(df.copy(), ["Timestamp"])
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    working = working.sort_values("Timestamp").reset_index(drop=True)
    for col in (c for c in working.columns if c != "Timestamp"):
        working[f"{col} Numeric"] = working[col].apply(score_response_0_2)
        working[f"{col} Percent"] = working[col].apply(score_response_pct)
        working[f"{col} Trend"]   = working[f"{col} Percent"].diff()
    return working


# =========================================================
# MODEL HELPERS
# =========================================================
def build_domain_scores(daily, domain_name, config, settings):
    sleep_pills_pct = build_sleeping_pills_flag_series(daily) * 100.0
    component_pairs = []

    for label, source_col, inverse, weight_key in config["components"]:
        out_col = f"{domain_name} - {label}"
        source  = daily[source_col] if source_col in daily.columns else pd.Series(0, index=daily.index)
        daily[out_col] = normalize_0_10_to_pct(source, inverse=inverse)
        if label == "Low Sleep Quality":
            daily[out_col] = pd.concat([daily[out_col], sleep_pills_pct], axis=1).max(axis=1)
        component_pairs.append((out_col, float(settings[weight_key])))

    flag_score_col = f"{domain_name} - Flags"
    flags_col      = f"{domain_name} Flags"

    if config.get("custom_flag_logic") == "depression":
        daily[flags_col]     = build_daily_depression_flag_series(daily)
        daily[flag_score_col]= normalize_flag_count_to_pct(daily[flags_col], max_flags=1)
    else:
        flag_cols = [c for c in config["flags"] if c in daily.columns]
        daily[flags_col]     = daily[flag_cols].sum(axis=1) if flag_cols else 0
        daily[flag_score_col]= normalize_flag_count_to_pct(daily[flags_col], max_flags=len(flag_cols)) if flag_cols else 0.0

    component_pairs.append((flag_score_col, float(settings[config["flag_weight_key"]])))

    score_col = f"{domain_name} Score %"
    avg_col   = f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average ({domain_name} %)"
    dev_col   = f"{domain_name} Deviation %"

    daily[score_col] = weighted_average_percent(daily, component_pairs)
    daily[avg_col]   = daily[score_col].rolling(window=DAILY_ROLLING_WINDOW_DAYS, min_periods=1).mean()
    daily[dev_col]   = daily[score_col] - daily[avg_col]
    return daily


def add_personal_baselines(df, settings, domains):
    if df.empty:
        return df
    window = max(int(settings.get("baseline_window_days", 14)), 3)
    for name in domains:
        score_col = f"{name} Score %"
        prev      = df[score_col].shift(1)
        baseline  = prev.rolling(window=window, min_periods=3).mean()
        std       = prev.rolling(window=window, min_periods=3).std()
        df[f"{name} Baseline %"]           = baseline
        df[f"{name} Baseline Std %"]       = std
        df[f"{name} Baseline Difference %"]= df[score_col] - baseline
        safe_std  = std.where(std.notna() & (std > 0), 1.0)
        z = (df[score_col] - baseline) / safe_std
        df[f"{name} Baseline Z"] = z.where(baseline.notna(), 0.0).fillna(0.0)
    return df


def build_domain_summary(df, settings, domains, include_reasons=True):
    if df.empty:
        return {}

    latest = df.iloc[-1]
    last5  = df.tail(5)
    medium_pct     = float(settings["medium_threshold_pct"])
    high_pct       = float(settings["high_threshold_pct"])
    trend_thr      = float(settings["trend_threshold_pct"])
    anomaly_thr    = float(settings.get("anomaly_z_threshold", 1.5))
    high_anom_thr  = float(settings.get("high_anomaly_z_threshold", 2.5))
    summary = {}

    for name in domains:
        score_pct = to_float(latest.get(f"{name} Score %", 0.0))
        dev_pct   = to_float(latest.get(f"{name} Deviation %", 0.0))
        z_val     = to_float(latest.get(f"{name} Baseline Z", 0.0))
        diff_val  = to_float(latest.get(f"{name} Baseline Difference %", 0.0))
        level     = level_from_percent(score_pct, medium_pct, high_pct)
        trend     = trend_from_deviation_pct(dev_pct, trend_thr)
        confidence= confidence_from_count(len(last5), trend, level)

        direction = "higher" if diff_val >= 0 else "lower"
        if abs(z_val) >= high_anom_thr:
            baseline_note   = f"much {direction} than your recent baseline ({diff_val:+.1f} points)"
            baseline_z_text = f"z={z_val:+.2f}"
        elif abs(z_val) >= anomaly_thr:
            baseline_note   = f"noticeably {direction} than your recent baseline ({diff_val:+.1f} points)"
            baseline_z_text = f"z={z_val:+.2f}"
        elif pd.notna(latest.get(f"{name} Baseline %", pd.NA)):
            baseline_note   = f"close to your recent baseline ({diff_val:+.1f} points)"
            baseline_z_text = f"z={z_val:+.2f}"
        else:
            baseline_note = baseline_z_text = ""

        item = dict(score_pct=score_pct, level=level, trend=trend, confidence=confidence,
                    baseline_z=z_val, baseline_diff_pct=diff_val,
                    baseline_note=baseline_note, baseline_z_text=baseline_z_text)

        if include_reasons:
            component_cols = [c for c in df.columns if c.startswith(f"{name} - ")]
            item["reasons"] = [
                REASON_LABELS.get(col, col.replace(f"{name} - ", ""))
                for col, _ in sorted(
                    [(c, to_float(latest.get(c, 0.0))) for c in component_cols],
                    key=lambda x: x[1], reverse=True
                )
                if to_float(latest.get(col, 0.0)) > 0
            ][:4]

        if name == "Depression" and to_int(latest.get("Depression Flags", 0)) == 0:
            item.update(level="Low", trend="Stable", confidence="Low",
                        reasons=[], baseline_note="", baseline_z_text="")

        summary[name] = item
    return summary


# =========================================================
# DAILY MODEL
# =========================================================
def build_daily_model_from_form(form_df, settings):
    if form_df.empty or "Timestamp" not in form_df.columns:
        return pd.DataFrame(), None

    working = convert_numeric(form_df.copy())
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    working["Date"] = working["Timestamp"].dt.date

    signal_columns = [c for c in working.columns if c.startswith("Signals and indicators [")]
    for col in signal_columns:
        working[col] = working[col].apply(bool_from_response).astype(int)

    numeric_cols = [c for c in [COL_MOOD, COL_SLEEP_HOURS, COL_SLEEP_QUALITY, COL_ENERGY,
                                 COL_MENTAL_SPEED, COL_IMPULSIVITY, COL_MOTIVATION,
                                 COL_IRRITABILITY, COL_AGITATION, COL_UNUSUAL,
                                 COL_SUSPICIOUS, COL_CERTAINTY] if c in working.columns]

    daily_scores = working.groupby("Date", as_index=False)[numeric_cols].mean() if numeric_cols \
        else pd.DataFrame({"Date": working["Date"].dropna().unique()})
    daily_flags  = working.groupby("Date", as_index=False)[signal_columns].sum() if signal_columns \
        else pd.DataFrame({"Date": working["Date"].dropna().unique()})

    if COL_SLEEPING_PILLS in working.columns:
        sleep_med_df = working.groupby("Date", as_index=False)[COL_SLEEPING_PILLS].agg(
            lambda s: int(any(bool_from_response(v) for v in s))
        )
    else:
        sleep_med_df = pd.DataFrame({"Date": working["Date"].dropna().unique()})

    daily = (daily_scores.merge(daily_flags, on="Date", how="outer")
                         .merge(sleep_med_df, on="Date", how="outer")
                         .sort_values("Date").reset_index(drop=True))
    daily["DateLabel"] = pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")
    if COL_SLEEPING_PILLS in daily.columns:
        daily[COL_SLEEPING_PILLS] = daily[COL_SLEEPING_PILLS].fillna(0).astype(int)

    for domain_name, config in DAILY_DOMAIN_CONFIG.items():
        daily = build_domain_scores(daily, domain_name, config, settings)

    daily["Sleeping Pills Flag"] = build_sleeping_pills_flag_series(daily)

    mixed_keys = ["mixed_dep_weight", "mixed_mania_weight", "mixed_psych_weight", "mixed_low_sleep_quality_weight"]
    mw = {k: float(settings[k]) for k in mixed_keys}
    mixed_total = sum(mw.values()) or 1.0

    daily["Mixed Score %"] = (
        daily["Depression Score %"] * mw["mixed_dep_weight"]
        + daily["Mania Score %"]    * mw["mixed_mania_weight"]
        + daily["Psychosis Score %"]* mw["mixed_psych_weight"]
        + daily.get("Depression - Low Sleep Quality", pd.Series(0, index=daily.index)) * mw["mixed_low_sleep_quality_weight"]
    ) / mixed_total

    daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"] = \
        daily["Mixed Score %"].rolling(DAILY_ROLLING_WINDOW_DAYS, min_periods=1).mean()
    daily["Mixed Deviation %"] = daily["Mixed Score %"] - daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"]

    for flag_col, out_col, cols in [
        (None, "Mixed Flags",              [SIG_MIXED_NOW, SIG_MIXED_COMING, SIG_WITHDRAW, SIG_LESS_SLEEP, SIG_MORE_ACTIVITY]),
        (None, "Concerning Situation Flags",[SIG_NOT_MYSELF, SIG_MISSED_MEDS, SIG_ROUTINE, SIG_STRESS_PSYCH, SIG_STRESS_PHYS]),
        (None, "Self-Reported Depression", [SIG_DOWN_NOW, SIG_DOWN_COMING]),
        (None, "Self-Reported Mania",      [SIG_UP_NOW, SIG_UP_COMING]),
        (None, "Self-Reported Mixed",      [SIG_MIXED_NOW, SIG_MIXED_COMING]),
    ]:
        present = [c for c in cols if c in daily.columns]
        daily[out_col] = daily[present].sum(axis=1) if present else 0

    daily = add_personal_baselines(daily, settings, DOMAIN_NAMES)
    return daily, build_domain_summary(daily, settings, DOMAIN_NAMES, include_reasons=True)


# =========================================================
# SNAPSHOT MODEL
# =========================================================
def build_snapshot_model_from_quick_form(quick_form_df, settings):
    if quick_form_df.empty or "Timestamp" not in quick_form_df.columns:
        return None, pd.DataFrame()

    working = drop_blank_tail_rows(quick_form_df.copy(), ["Timestamp"])
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    working = working.sort_values("Timestamp").reset_index(drop=True)

    for domain_name, config in SNAPSHOT_DOMAIN_CONFIG.items():
        pairs = [(col, float(settings[wk])) for col, wk in config["components"]]
        working[f"{domain_name} Score %"] = weighted_average_percent(working, pairs, from_response=True)

    working["Depression Flags"] = build_snapshot_depression_flag_series(working)

    mixed_weights = [float(settings[k]) for k in ("mixed_dep_weight","mixed_mania_weight","mixed_psych_weight")]
    mixed_total = sum(mixed_weights) or 1.0
    working["Mixed Score %"] = (
        working["Depression Score %"] * mixed_weights[0]
        + working["Mania Score %"]    * mixed_weights[1]
        + working["Psychosis Score %"]* mixed_weights[2]
    ) / mixed_total

    for name in DOMAIN_NAMES:
        avg = working[f"{name} Score %"].rolling(10, min_periods=1).mean()
        working[f"10-Response Average ({name} %)"] = avg
        working[f"Deviation From 10-Response Average ({name} %)"] = working[f"{name} Score %"] - avg

    working["FilterDate"] = working["Timestamp"].dt.date
    working["TimeLabel"]  = working["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")

    summary = {}
    if not working.empty:
        latest = working.iloc[-1]
        medium_pct = float(settings["medium_threshold_pct"])
        high_pct   = float(settings["high_threshold_pct"])
        trend_thr  = float(settings["trend_threshold_pct"])
        for name in DOMAIN_NAMES:
            score_pct = to_float(latest.get(f"{name} Score %", 0.0))
            dev_pct   = to_float(latest.get(f"Deviation From 10-Response Average ({name} %)", 0.0))
            level     = level_from_percent(score_pct, medium_pct, high_pct)
            trend     = trend_from_deviation_pct(dev_pct, trend_thr)
            confidence= confidence_from_count(len(working.tail(5)), trend, level)
            if name == "Depression" and to_int(latest.get("Depression Flags", 0)) == 0:
                level, trend, confidence = "Low", "Stable", "Low"
            summary[name] = dict(score_pct=score_pct, level=level, trend=trend, confidence=confidence)

    return summary, working


# =========================================================
# ALERT ENGINE / TODAY SUMMARY
# =========================================================
def get_domain_persistence(df, domain, medium_threshold, days):
    if df.empty or len(df) < days:
        return 0
    return int((df[f"{domain} Score %"].tail(days) >= medium_threshold).all())


def build_alerts(daily_model_data, daily_summary, snapshot_summary, settings, snapshot_model_data=None):
    if daily_model_data.empty or not daily_summary:
        return []

    latest         = daily_model_data.iloc[-1]
    medium_pct     = float(settings["medium_threshold_pct"])
    anomaly_thr    = float(settings.get("anomaly_z_threshold", 1.5))
    high_anom_thr  = float(settings.get("high_anomaly_z_threshold", 2.5))
    persistence_days = int(settings.get("persistence_days", 3))

    daily_dep_flag_on    = to_int(latest.get("Depression Flags", 0)) > 0
    snapshot_dep_flag_on = (not (snapshot_model_data is None or snapshot_model_data.empty)
                            and to_int(snapshot_model_data.iloc[-1].get("Depression Flags", 0)) > 0)

    alerts = []
    for name in DOMAIN_NAMES:
        item = daily_summary[name]
        if name == "Depression" and not daily_dep_flag_on:
            continue

        z_val   = to_float(item.get("baseline_z", 0.0))
        diff_val= to_float(item.get("baseline_diff_pct", 0.0))
        details = []

        if item["level"] in ("Medium", "High"):
            details.append(f"{name} score is {item['level'].lower()} at {item['score_pct']:.1f}%.")
        if item["trend"] in ("Rising", "Falling"):
            details.append(f"Recent direction is {item['trend'].lower()}.")
        if abs(z_val) >= anomaly_thr:
            direction = "above" if diff_val >= 0 else "below"
            details.append(f"This is {abs(diff_val):.1f} points {direction} your personal baseline (z={z_val:+.2f}).")
        if get_domain_persistence(daily_model_data, name, medium_pct, persistence_days):
            details.append(f"This pattern has stayed at or above medium for the last {persistence_days} days.")

        snapshot_agrees = False
        if snapshot_summary and name in snapshot_summary:
            snap_level = snapshot_summary[name]["level"]
            if snap_level in ("Medium", "High") and (name != "Depression" or snapshot_dep_flag_on):
                snapshot_agrees = True
                details.append(f"Snapshot model also shows {name.lower()} as {snap_level.lower()}.")

        persists = get_domain_persistence(daily_model_data, name, medium_pct, persistence_days)
        if item["level"] == "High":
            severity = "High concern"
        elif item["level"] == "Medium" and item["trend"] == "Rising":
            severity = "Pay attention today"
        elif abs(z_val) >= high_anom_thr:
            severity = "Pay attention today"
        elif snapshot_agrees and item["level"] in ("Medium", "High"):
            severity = "Pay attention today"
        elif persists:
            severity = "Pay attention today"
        elif abs(z_val) >= anomaly_thr and item["score_pct"] >= medium_pct * 0.8:
            severity = "Monitor"
        else:
            continue

        summary_text = f"{name} looks {item['level'].lower()} with a {item['trend'].lower()} recent direction."
        if abs(z_val) >= anomaly_thr:
            summary_text += " It is also unusual relative to your recent baseline."
        alerts.append(dict(severity=severity, domain=name, title=f"{name} pattern",
                           summary=summary_text, details=details))

    concerning = to_int(latest.get("Concerning Situation Flags", 0))
    if concerning > 0:
        alerts.append(dict(
            severity="High concern" if concerning > 2 else "Pay attention today",
            domain="General", title="Concerning situation flags",
            summary=f"{concerning} concerning situation flag(s) were recorded in the latest daily data.",
            details=["These can matter even if the main domain scores are not high.",
                     "Consider checking routine disruption, missed meds, or major stressor signals."],
        ))

    active_med_plus = [d for d in DOMAIN_NAMES if d != "Depression" and daily_summary[d]["level"] in ("Medium","High")]
    active_high     = [d for d in DOMAIN_NAMES if d != "Depression" and daily_summary[d]["level"] == "High"]
    if daily_dep_flag_on and daily_summary["Depression"]["level"] in ("Medium","High"):
        active_med_plus.append("Depression")
        if daily_summary["Depression"]["level"] == "High":
            active_high.append("Depression")

    if len(active_high) >= 2 or len(active_med_plus) >= 3:
        alerts.append(dict(
            severity="High concern", domain="General", title="Multiple elevated patterns",
            summary="More than one domain is elevated at the same time.",
            details=[f"Elevated domains: {', '.join(active_med_plus)}.",
                     "This may be worth paying extra attention to because the picture is not confined to a single area."],
        ))

    return sorted(alerts, key=lambda a: (-alert_rank(a["severity"]), a["title"]))


def build_today_summary(daily_summary, alerts, daily_model_data):
    if not daily_summary or daily_model_data.empty:
        return "No daily interpretation is available yet."

    primary_name, primary = max(
        daily_summary.items(),
        key=lambda kv: ({"High":3,"Medium":2,"Low":1}.get(kv[1]["level"],0),
                        kv[1]["score_pct"], abs(kv[1].get("baseline_z",0.0)))
    )
    top_alert = alerts[0] if alerts else None
    parts = [f"Main pattern today: {primary_name.lower()} looks {primary['level'].lower()}"]
    if primary["trend"] != "Stable":
        parts[0] += f" and is {primary['trend'].lower()}"
    parts[0] += f" ({primary['score_pct']:.1f}%)."
    if primary.get("baseline_note"):
        parts.append(f"Compared with your usual pattern, it is {primary['baseline_note']}.")
    if primary.get("reasons"):
        parts.append(f"Main drivers: {', '.join(primary['reasons'][:3])}.")
    if top_alert:
        parts.append(f"Overall status: {top_alert['severity']}.")
    return " ".join(parts)


# =========================================================
# WARNING HELPERS
# =========================================================
def get_latest_form_warning_items(form_df):
    if form_df.empty or "Timestamp" not in form_df.columns:
        return [], []

    latest = form_df.sort_values("Timestamp").iloc[-1]
    signal_columns = [c for c in form_df.columns if c.startswith("Signals and indicators [")]
    flagged = [prettify_signal_name(c) for c in signal_columns if bool_from_response(latest.get(c, ""))]

    thresholds = [
        (COL_MOOD,         "Mood score is low",               lambda v: v <= 4),
        (COL_SLEEP_HOURS,  "Sleep hours are low",             lambda v: v <= 5),
        (COL_SLEEP_QUALITY,"Sleep quality is poor",           lambda v: v <= 4),
        (COL_MOTIVATION,   "Motivation is low",               lambda v: v <= 4),
        (COL_ENERGY,       "Energy is elevated",              lambda v: v >= 6),
        (COL_MENTAL_SPEED, "Mental speed is elevated",        lambda v: v >= 6),
        (COL_IMPULSIVITY,  "Impulsivity is elevated",         lambda v: v >= 6),
        (COL_IRRITABILITY, "Irritability is elevated",        lambda v: v >= 6),
        (COL_AGITATION,    "Agitation is elevated",           lambda v: v >= 6),
        (COL_UNUSUAL,      "Unusual perceptions are elevated",lambda v: v >= 6),
        (COL_SUSPICIOUS,   "Suspiciousness is elevated",      lambda v: v >= 6),
        (COL_CERTAINTY,    "Belief certainty is elevated",    lambda v: v >= 6),
    ]
    concerning = []
    for col, label, check in thresholds:
        if col in latest.index:
            val = pd.to_numeric(latest[col], errors="coerce")
            if pd.notna(val) and check(val):
                concerning.append(f"{label} ({val:.1f})")
    if COL_SLEEPING_PILLS in latest.index and bool_from_response(latest.get(COL_SLEEPING_PILLS, "")):
        concerning.append("Took sleeping medication (treat as bad sleep flag)")
    return flagged, concerning


def get_latest_quick_form_warning_items(quick_form_df):
    if quick_form_df.empty or "Timestamp" not in quick_form_df.columns:
        return [], []

    latest = quick_form_df.sort_values("Timestamp").iloc[-1]
    signals = []
    for col in (c for c in quick_form_df.columns
                if c != "Timestamp" and not c.endswith((" Numeric"," Percent"," Trend"))):
        val = str(latest.get(col, "")).strip().lower()
        if val in ("yes", "somewhat"):
            signals.append(f"{prettify_signal_name(col)} — {'Yes' if val == 'yes' else 'Somewhat'}")

    yes_count  = sum(1 for s in signals if s.endswith("Yes"))
    some_count = sum(1 for s in signals if s.endswith("Somewhat"))
    concerning = []
    if yes_count  >= 3: concerning.append(f"Several snapshot symptoms are marked Yes ({yes_count})")
    if some_count >= 3: concerning.append(f"Several snapshot symptoms are marked Somewhat ({some_count})")
    return signals, concerning


def get_model_concerning_findings(daily_summary, snapshot_summary, daily_model_df, snapshot_model_df):
    daily_findings, snapshot_findings = [], []

    daily_dep_flag    = not daily_model_df.empty and to_int(daily_model_df.iloc[-1].get("Depression Flags", 0)) > 0
    snapshot_dep_flag = not snapshot_model_df.empty and to_int(snapshot_model_df.iloc[-1].get("Depression Flags", 0)) > 0

    if daily_summary and not daily_model_df.empty:
        for name in DOMAIN_NAMES:
            if name == "Depression" and not daily_dep_flag:
                continue
            item = daily_summary[name]
            if item["level"] in ("Medium", "High"):
                daily_findings.append(f"Daily {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}")
            if abs(to_float(item.get("baseline_z", 0.0))) >= 1.5:
                daily_findings.append(f"Daily {name.lower()} is unusual relative to your recent baseline")
        concerning = to_float(daily_model_df.iloc[-1].get("Concerning Situation Flags", 0))
        if concerning > 0:
            daily_findings.append(f"Concerning situation flags: {int(concerning)}")

    if snapshot_summary:
        for name in DOMAIN_NAMES:
            if name == "Depression" and not snapshot_dep_flag:
                continue
            item = snapshot_summary[name]
            if item["level"] in ("Medium", "High"):
                snapshot_findings.append(f"Snapshot {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}")
    if snapshot_dep_flag:
        snapshot_findings.append("Snapshot depression flag is present")

    return daily_findings, snapshot_findings


# =========================================================
# PAGE RENDERERS
# =========================================================
def _render_metrics_row(metrics: list[tuple[str, str]]):
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.metric(label, value)


def render_dashboard_page(form_data, quick_form_data, daily_model_data, daily_model_summary,
                          snapshot_model_summary, latest_form_signals, latest_form_findings,
                          latest_snapshot_signals, latest_snapshot_findings,
                          daily_model_findings, snapshot_model_findings, alerts, today_summary):
    st.subheader("Dashboard")
    st.caption("Daily Model is calculated from Form Responses. Snapshot Model is calculated from Quick Form Responses.")

    st.markdown("### Today's interpretation")
    top_severity = alerts[0]["severity"] if alerts else "Monitor"
    tone = "error" if top_severity == "High concern" else "warning" if top_severity == "Pay attention today" else "info"
    render_two_column_flag_box("Today at a glance", [today_summary], tone=tone)

    st.markdown("### Current alerts")
    if alerts:
        for col, alert in zip(st.columns(min(3, len(alerts))), alerts[:3]):
            with col:
                render_alert_card(alert)
    else:
        st.info("No active alerts are being generated from the current rules.")

    st.markdown("### Current state")
    st.markdown("#### Daily Model")
    render_summary_cards(daily_model_summary, detailed=True)
    st.markdown("#### Snapshot Model")
    render_summary_cards(snapshot_model_summary, detailed=False)

    st.markdown("### Key warnings")
    warn_left, warn_right = st.columns(2)
    with warn_left:
        render_two_column_flag_box("Daily questionnaire / model",
                                   latest_form_findings + daily_model_findings + latest_form_signals,
                                   tone="error" if (latest_form_findings or daily_model_findings) else "warning")
    with warn_right:
        render_two_column_flag_box("Snapshot questionnaire / model",
                                   latest_snapshot_findings + snapshot_model_findings + latest_snapshot_signals,
                                   tone="error" if (latest_snapshot_findings or snapshot_model_findings) else "warning")

    st.markdown("### Recent trends")
    if not daily_model_data.empty:
        trend_df  = daily_model_data.copy()
        max_date  = pd.to_datetime(trend_df["Date"]).max().date()
        min_date  = pd.to_datetime(trend_df["Date"]).min().date()
        window    = st.selectbox("Trend window", ["Last 7 days","Last 14 days","Last 30 days","All data"],
                                 index=1, key="dashboard_trend_window")
        offsets   = {"Last 7 days": 6, "Last 14 days": 13, "Last 30 days": 29}
        start     = (max_date - pd.Timedelta(days=offsets[window])) if window in offsets else min_date
        trend_df  = trend_df[pd.to_datetime(trend_df["Date"]).dt.date.between(start, max_date)].copy()
        st.line_chart(trend_df[["DateLabel","Depression Score %","Mania Score %",
                                 "Psychosis Score %","Mixed Score %"]].set_index("DateLabel"))
    else:
        st.info("No daily trend data available.")

    st.markdown("### Personal baseline")
    if not daily_model_data.empty:
        ld = daily_model_data.iloc[-1]
        _render_metrics_row([
            ("Depression vs baseline", f"{to_float(ld.get('Depression Baseline Difference %', 0.0)):+.1f} pp"),
            ("Mania vs baseline",      f"{to_float(ld.get('Mania Baseline Difference %', 0.0)):+.1f} pp"),
            ("Psychosis vs baseline",  f"{to_float(ld.get('Psychosis Baseline Difference %', 0.0)):+.1f} pp"),
            ("Mixed vs baseline",      f"{to_float(ld.get('Mixed Baseline Difference %', 0.0)):+.1f} pp"),
        ])
    else:
        st.info("No personal baseline data available.")

    st.markdown("### Flags overview")
    if not daily_model_data.empty:
        ld = daily_model_data.iloc[-1]
        _render_metrics_row([
            ("Concerning flags", str(to_int(ld.get("Concerning Situation Flags", 0)))),
            ("Depression flags", str(to_int(ld.get("Depression Flags", 0)))),
            ("Mania flags",      str(to_int(ld.get("Mania Flags", 0)))),
            ("Psychosis flags",  str(to_int(ld.get("Psychosis Flags", 0)))),
        ])
    else:
        st.info("No flag overview available.")

    st.markdown("### Recent activity")
    latest_form_time     = form_data["Timestamp"].max() if not form_data.empty and "Timestamp" in form_data.columns else None
    latest_snapshot_time = quick_form_data["Timestamp"].max() if not quick_form_data.empty and "Timestamp" in quick_form_data.columns else None
    days_tracked         = len(daily_model_data) if not daily_model_data.empty else 0
    snapshot_last_7      = 0
    if latest_snapshot_time is not None and not quick_form_data.empty and "Timestamp" in quick_form_data.columns:
        snap_ts      = pd.to_datetime(quick_form_data["Timestamp"], errors="coerce").dropna()
        snapshot_last_7 = int((snap_ts >= latest_snapshot_time - pd.Timedelta(days=7)).sum())
    _render_metrics_row([
        ("Latest form entry",          latest_form_time.strftime("%Y-%m-%d %H:%M") if latest_form_time else "N/A"),
        ("Latest snapshot entry",      latest_snapshot_time.strftime("%Y-%m-%d %H:%M") if latest_snapshot_time else "N/A"),
        ("Days tracked",               str(days_tracked)),
        ("Snapshot entries (last 7d)", str(snapshot_last_7)),
    ])


def render_warnings_page(daily_model_summary, snapshot_model_summary, latest_form_signals,
                         latest_form_findings, latest_snapshot_signals, latest_snapshot_findings,
                         daily_model_findings, snapshot_model_findings, alerts, today_summary):
    st.subheader("Warnings")
    render_two_column_flag_box("Today at a glance", [today_summary], tone="info")

    st.markdown("### Alert engine output")
    if alerts:
        for alert in alerts:
            render_alert_card(alert)
    else:
        st.info("No alerts are currently being generated.")

    st.markdown("### Current State — Daily Model")
    render_summary_cards(daily_model_summary, detailed=True)
    st.markdown("### Current State — Snapshot Model")
    render_summary_cards(snapshot_model_summary, detailed=False)

    st.markdown("### Warning Signals and Concerning Findings")
    left, right = st.columns(2)
    with left:
        render_two_column_flag_box("Daily questionnaire — warning signals", latest_form_signals, tone="warning")
        render_two_column_flag_box("Daily questionnaire — concerning findings",
                                   latest_form_findings + daily_model_findings, tone="error")
    with right:
        render_two_column_flag_box("Snapshot questionnaire — warning signals", latest_snapshot_signals, tone="warning")
        render_two_column_flag_box("Snapshot questionnaire — concerning findings",
                                   latest_snapshot_findings + snapshot_model_findings, tone="error")


def render_daily_model_page(form_data):
    st.subheader("Daily Model")
    st.caption("Calculated from Form Responses with configurable parameters. Scores are shown as percentages.")
    with st.expander("Daily model settings"):
        render_settings_form("daily_settings", DAILY_SETTINGS_UI, columns_per_row=3)

    daily_model_data, daily_model_summary = build_daily_model_from_form(
        form_data, st.session_state["daily_settings"])
    if daily_model_data.empty:
        st.info("No daily model data available.")
        return

    render_summary_cards(daily_model_summary, detailed=True)
    render_chart_group(daily_model_data, "Date", "DateLabel", DAILY_CHARTS)

    default_cols = [c for c in [
        "Date","Depression Score %","5-Day Average (Depression %)","Depression Baseline %",
        "Depression Baseline Difference %","Depression Baseline Z",
        "Mania Score %","5-Day Average (Mania %)","Mania Baseline %",
        "Mania Baseline Difference %","Mania Baseline Z",
        "Psychosis Score %","5-Day Average (Psychosis %)","Psychosis Baseline %",
        "Psychosis Baseline Difference %","Psychosis Baseline Z",
        "Mixed Score %","5-Day Average (Mixed %)","Mixed Baseline %",
        "Mixed Baseline Difference %","Mixed Baseline Z",
        "Concerning Situation Flags","Sleeping Pills Flag",
        "Depression Flags","Mania Flags","Mixed Flags","Psychosis Flags",
    ] if c in daily_model_data.columns]
    render_dataframe_picker("Daily model data", daily_model_data, default_cols, "daily_model_columns")


def render_snapshot_model_page(quick_form_data):
    st.subheader("Snapshot Model")
    st.caption("Calculated from Quick Form Responses. Symptom scoring converts No/Somewhat/Yes from 0/1/2 into 0/50/100%.")
    with st.expander("Snapshot model settings"):
        render_settings_form("snapshot_settings", SNAPSHOT_SETTINGS_UI, columns_per_row=3)

    snapshot_model_summary, snapshot_model_data = build_snapshot_model_from_quick_form(
        quick_form_data, st.session_state["snapshot_settings"])
    if snapshot_model_summary is None or snapshot_model_data.empty:
        st.info("No snapshot model data available.")
        return

    render_summary_cards(snapshot_model_summary, detailed=False)
    render_chart_group(snapshot_model_data, "FilterDate", "TimeLabel", SNAPSHOT_CHARTS)

    preview_cols = [c for c in [
        "Timestamp","Depression Score %","Depression Flags","Mania Score %",
        "Psychosis Score %","Mixed Score %",
        "10-Response Average (Depression %)","10-Response Average (Mania %)",
        "10-Response Average (Psychosis %)","10-Response Average (Mixed %)",
        "Deviation From 10-Response Average (Depression %)","Deviation From 10-Response Average (Mania %)",
        "Deviation From 10-Response Average (Psychosis %)","Deviation From 10-Response Average (Mixed %)",
    ] if c in snapshot_model_data.columns]
    render_dataframe_picker("Snapshot model data", snapshot_model_data, preview_cols, "snapshot_model_columns")


def render_form_data_page(form_data):
    st.subheader("Form Data")
    st.caption("Imported directly from Form Responses.")
    default_cols = [c for c in [
        "Timestamp","Date","Mood Score","Sleep (hours)","Sleep quality","Energy","Mental speed",
        "Impulsivity","Motivation","Irritability","Agitation","Unusual perceptions","Suspiciousness",
        "Certainty and belief in unusual ideas or things others don't believe","Took sleeping medication?",
    ] if c in form_data.columns]
    render_dataframe_picker("Form Data", form_data, default_cols, "form_data_columns")


def render_snapshot_data_page(quick_form_data):
    st.subheader("Snapshot Data")
    st.caption("Imported directly from Quick Form Responses.")
    default_cols = [c for c in [
        "Timestamp",
        "Symptoms: [Very low or depressed mood]","Symptoms: [Very low or depressed mood] Percent",
        "Symptoms: [Somewhat low or depressed mood]","Symptoms: [Somewhat low or depressed mood] Percent",
        "Symptoms: [Very high or elevated mood]","Symptoms: [Very high or elevated mood] Percent",
        "Symptoms: [Paranoia or suspicion]","Symptoms: [Paranoia or suspicion] Percent",
        "Depression Flags",
    ] if c in quick_form_data.columns]
    render_dataframe_picker("Snapshot Data", quick_form_data, default_cols, "snapshot_data_columns")


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

form_df       = load_sheet(FORM_TAB)
quick_form_df = load_sheet(QUICK_FORM_TAB)
form_data     = prepare_form_raw(form_df)
quick_form_data = prepare_quick_form_raw(quick_form_df)

daily_model_data, daily_model_summary = build_daily_model_from_form(
    form_data, st.session_state["daily_settings"])
snapshot_model_summary, snapshot_model_data = build_snapshot_model_from_quick_form(
    quick_form_data, st.session_state["snapshot_settings"])

latest_form_signals,     latest_form_findings     = get_latest_form_warning_items(form_data)
latest_snapshot_signals, latest_snapshot_findings = get_latest_quick_form_warning_items(quick_form_data)
daily_model_findings, snapshot_model_findings     = get_model_concerning_findings(
    daily_model_summary, snapshot_model_summary, daily_model_data, snapshot_model_data)

alerts       = build_alerts(daily_model_data, daily_model_summary, snapshot_model_summary,
                            st.session_state["daily_settings"], snapshot_model_data)
today_summary= build_today_summary(daily_model_summary, alerts, daily_model_data)

tabs = st.tabs(["Dashboard","Warnings","Daily Model","Snapshot Model","Form Data","Snapshot Data"])

with tabs[0]:
    render_dashboard_page(form_data, quick_form_data, daily_model_data, daily_model_summary,
                          snapshot_model_summary, latest_form_signals, latest_form_findings,
                          latest_snapshot_signals, latest_snapshot_findings,
                          daily_model_findings, snapshot_model_findings, alerts, today_summary)
with tabs[1]:
    render_warnings_page(daily_model_summary, snapshot_model_summary, latest_form_signals,
                         latest_form_findings, latest_snapshot_signals, latest_snapshot_findings,
                         daily_model_findings, snapshot_model_findings, alerts, today_summary)
with tabs[2]:
    render_daily_model_page(form_data)
with tabs[3]:
    render_snapshot_model_page(quick_form_data)
with tabs[4]:
    render_form_data_page(form_data)
with tabs[5]:
    render_snapshot_data_page(quick_form_data)
