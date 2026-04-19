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
        st.text_input(
            "Enter password",
            type="password",
            on_change=password_entered,
            key="password",
        )
        return False

    if not st.session_state["authenticated"]:
        st.text_input(
            "Enter password",
            type="password",
            on_change=password_entered,
            key="password",
        )
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
UPDATED_DAILY_TAB = "Updated Daily Bipolar Form"

DOMAIN_NAMES = ["Depression", "Mania", "Psychosis", "Mixed"]
DAILY_ROLLING_WINDOW_DAYS = 5

COLUMN_ALIASES = {
    "Signals and indicators [Avoided normal responsiblities]":
        "Signals and indicators [Avoided normal responsibilities]",
    "Certainty and  belief in unusual ideas or things others don't believe":
        "Certainty and belief in unusual ideas or things others don't believe",
    "Weekly Check-In  Flags":
        "Weekly Check-In Flags",
    "Column 1": "Date",
    "Positive motivation": "Motivation",

    # Updated Daily Bipolar Form mappings
    "How many hours of sleep did I get?": "Updated Daily [Sleep hours]",
    "What was my sleep quality?": "Updated Daily [Sleep quality]",
    "How effectively have I been functioning at work?": "Updated Daily [Work functioning]",
    "How well have I been functioning in my daily life?": "Updated Daily [Daily functioning]",

    "Have I felt a low mood?": "Updated Daily [Low mood]",
    "Have I felt slowed down or low on energy?": "Updated Daily [Low energy]",
    "Have I felt low on motivation or had difficulty initiating tasks?": "Updated Daily [Low motivation]",
    "Have I felt a lack of interest or pleasure in activities?": "Updated Daily [Low interest]",
    "Have I been socially or emotionally withdrawn?": "Updated Daily [Withdrawal]",
    "Have I had ideation around self-harming or suicidal behaviours?": "Updated Daily [Self-harm ideation]",

    "Have I felt an elevated mood?": "Updated Daily [Elevated mood]",
    "Have I felt sped up or high on energy?": "Updated Daily [High energy]",
    "Have I felt agitated or restless?": "Updated Daily [Agitation]",
    "Have I had racing thoughts or speech?": "Updated Daily [Racing thoughts]",
    "Have I been more irritable and reactive than normal?": "Updated Daily [Irritability]",
    "Have I had an increased drive towards goal-directed activity or a sense that I must be 'doing things' at all times?":
        "Updated Daily [Goal-directed activity]",

    "Have I heard or seen things others didn't?": "Updated Daily [Heard or saw things]",
    "Have I felt watched, followed, targeted or suspicious?": "Updated Daily [Suspiciousness]",
    "Have I had trouble trusting my perceptions and thoughts?": "Updated Daily [Trouble trusting perceptions]",
    "How confident have I been in the reality of these experiences?": "Updated Daily [Belief certainty]",
    "How distressed have I been by these beliefs and experiences?": "Updated Daily [Psychosis distress]",
    "How would I describe my experiences?": "Updated Daily [Experience description]",

    "I've been feeling \"not like myself\"": 'Signals and indicators [Felt "not like myself"]',
    "I noticed a sudden mood shift": "Signals and indicators [Noticed a sudden mood shift]",
    "I missed medication": "Signals and indicators [Missed meds]",
    "I took sleeping or anti-anxiety medication": "Took sleeping medication?",
    "There were significant disruptions to my routine": "Signals and indicators [Significant disruption to routine]",
    "I had a major physiological stress": "Signals and indicators [Major stressor or trigger (physiological)]",
    "I had a major psychological stress": "Signals and indicators [Major stressor or trigger (psychological)]",

    "Observations [I feel like I'm experiencing an up]": "Signals and indicators [Feel like I'm experiencing an up]",
    "Observations [I feel like I'm experiencing a down]": "Signals and indicators [Feel like I'm experiencing a down]",
    "Observations [I feel like I'm experiencing a mixed]": "Signals and indicators [Feel like I'm experiencing a mixed]",
    "Observations [I feel like I'm going to experience an up]": "Signals and indicators [Feel like I'm going to experience an up]",
    "Observations [I feel like I'm going to experience a down]": "Signals and indicators [Feel like I'm going to experience a down]",
    "Observations [I feel like I'm going to experience a mixed]": "Signals and indicators [Feel like I'm going to experience a mixed]",
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
    "dep_low_mood_weight": 4.0,
    "dep_low_sleep_quality_weight": 1.0,
    "dep_low_energy_weight": 1.0,
    "dep_low_mental_speed_weight": 1.0,
    "dep_low_motivation_weight": 2.0,
    "dep_flag_weight": 1.0,

    "mania_high_mood_weight": 1.0,
    "mania_low_sleep_quality_weight": 2.0,
    "mania_high_energy_weight": 1.5,
    "mania_high_mental_speed_weight": 1.5,
    "mania_high_impulsivity_weight": 1.5,
    "mania_high_irritability_weight": 2.0,
    "mania_high_agitation_weight": 2.0,
    "mania_flag_weight": 2.0,

    "psych_unusual_weight": 1.0,
    "psych_suspicious_weight": 1.0,
    "psych_certainty_weight": 3.0,
    "psych_flag_weight": 1.0,

    "updated_daily_weight": 0.7,
    "legacy_daily_weight": 0.3,

    "mixed_dep_weight": 0.4,
    "mixed_mania_weight": 0.4,
    "mixed_psych_weight": 0.2,
    "mixed_low_sleep_quality_weight": 0.5,
    "medium_threshold_pct": 33.0,
    "high_threshold_pct": 66.0,
    "trend_threshold_pct": 8.0,
    "baseline_window_days": 14,
    "anomaly_z_threshold": 1.5,
    "high_anomaly_z_threshold": 2.5,
    "persistence_days": 3,
}

DEFAULT_SNAPSHOT_SETTINGS = {
    "dep_very_low_mood": 4.0,
    "dep_somewhat_low_mood": 2.0,
    "dep_withdrawal": 1.0,
    "dep_self_care": 1.0,
    "dep_slowed_down": 1.0,
    "mania_very_high_mood": 2.0,
    "mania_somewhat_high_mood": 1.0,
    "mania_agitation": 2.0,
    "mania_racing": 1.5,
    "mania_driven": 2.0,
    "psych_hearing_seeing": 1.0,
    "psych_paranoia": 1.0,
    "psych_beliefs": 1.0,
    "mixed_dep_weight": 0.4,
    "mixed_mania_weight": 0.4,
    "mixed_psych_weight": 0.2,
    "medium_threshold_pct": 33.0,
    "high_threshold_pct": 66.0,
    "trend_threshold_pct": 8.0,
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

    "Updated Depression - Low Mood": "Lower mood",
    "Updated Depression - Low Energy": "Lower energy",
    "Updated Depression - Low Motivation": "Lower motivation",
    "Updated Depression - Low Interest": "Lower interest / pleasure",
    "Updated Depression - Withdrawal": "Withdrawal",
    "Updated Depression - Self-Harm": "Self-harm / suicidal ideation",
    "Updated Work Functioning Impact %": "Reduced work functioning",
    "Updated Daily Functioning Impact %": "Reduced daily functioning",
    "Updated Sleep Quality %": "Poor sleep quality",

    "Updated Mania - Elevated Mood": "Elevated mood",
    "Updated Mania - High Energy": "Higher energy",
    "Updated Mania - Agitation": "Agitation / restlessness",
    "Updated Mania - Racing Thoughts": "Racing thoughts / speech",
    "Updated Mania - Irritability": "Higher irritability",
    "Updated Mania - Goal Activity": "Driven activity",

    "Updated Psychosis - Perceptions": "Unusual perceptions",
    "Updated Psychosis - Suspiciousness": "Suspiciousness",
    "Updated Psychosis - Trust Difficulty": "Trouble trusting perceptions",
    "Updated Psychosis - Certainty": "Belief certainty",
    "Updated Psychosis - Distress": "Distress from experiences",
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
    "Daily source blending": [
        ("updated_daily_weight", "Updated daily form weight", 0.0, 1.0, 0.05),
        ("legacy_daily_weight", "Legacy form weight", 0.0, 1.0, 0.05),
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
    {
        "title": "Daily state scores (%)",
        "cols": [
            "Depression Score %",
            "Mania Score %",
            "Psychosis Score %",
            "Mixed Score %",
            "Updated Depression Score %",
            "Updated Mania Score %",
            "Updated Psychosis Score %",
        ],
        "key": "daily_state_scores",
        "type": "line",
    },
    {
        "title": "5-day averages (%)",
        "cols": [
            "5-Day Average (Depression %)",
            "5-Day Average (Mania %)",
            "5-Day Average (Psychosis %)",
            "5-Day Average (Mixed %)",
        ],
        "key": "daily_5day_avg",
        "type": "line",
    },
    {
        "title": "Deviation from 5-day averages (percentage points)",
        "cols": [
            "Depression Deviation %",
            "Mania Deviation %",
            "Psychosis Deviation %",
            "Mixed Deviation %",
        ],
        "key": "daily_deviation",
        "type": "line",
    },
    {
        "title": "Personal baseline vs current scores",
        "cols": [
            "Depression Score %",
            "Depression Baseline %",
            "Mania Score %",
            "Mania Baseline %",
            "Psychosis Score %",
            "Psychosis Baseline %",
            "Mixed Score %",
            "Mixed Baseline %",
        ],
        "key": "daily_baseline_vs_current",
        "type": "line",
    },
    {
        "title": "Distance from personal baseline (percentage points)",
        "cols": [
            "Depression Baseline Difference %",
            "Mania Baseline Difference %",
            "Psychosis Baseline Difference %",
            "Mixed Baseline Difference %",
        ],
        "key": "daily_baseline_diff",
        "type": "line",
    },
    {
        "title": "Unusual-for-me score (z-score)",
        "cols": [
            "Depression Baseline Z",
            "Mania Baseline Z",
            "Psychosis Baseline Z",
            "Mixed Baseline Z",
        ],
        "key": "daily_baseline_z",
        "type": "line",
    },
    {
        "title": "Flag breakdown by category",
        "cols": [
            "Concerning Situation Flags",
            "Depression Flags",
            "Mania Flags",
            "Mixed Flags",
            "Psychosis Flags",
        ],
        "key": "daily_flags",
        "type": "bar",
    },
    {
        "title": "Depression drivers",
        "cols": [
            "Depression - Low Mood Score",
            "Depression - Low Sleep Quality",
            "Depression - Low Energy",
            "Depression - Low Mental Speed",
            "Depression - Low Motivation",
            "Depression - Flags",
            "Updated Depression - Low Mood",
            "Updated Depression - Low Energy",
            "Updated Depression - Low Motivation",
            "Updated Depression - Low Interest",
            "Updated Depression - Withdrawal",
            "Updated Depression - Self-Harm",
            "Updated Work Functioning Impact %",
            "Updated Daily Functioning Impact %",
            "Updated Sleep Quality %",
        ],
        "key": "daily_depression_drivers",
        "type": "line",
    },
    {
        "title": "Mania drivers",
        "cols": [
            "Mania - High Mood Score",
            "Mania - Low Sleep Quality",
            "Mania - High Energy",
            "Mania - High Mental Speed",
            "Mania - High Impulsivity",
            "Mania - High Irritability",
            "Mania - High Agitation",
            "Mania - Flags",
            "Updated Mania - Elevated Mood",
            "Updated Mania - High Energy",
            "Updated Mania - Agitation",
            "Updated Mania - Racing Thoughts",
            "Updated Mania - Irritability",
            "Updated Mania - Goal Activity",
            "Updated Sleep Quality %",
        ],
        "key": "daily_mania_drivers",
        "type": "line",
    },
    {
        "title": "Psychosis drivers",
        "cols": [
            "Psychosis - Unusual perceptions",
            "Psychosis - Suspiciousness",
            "Psychosis - Certainty",
            "Psychosis - Flags",
            "Updated Psychosis - Perceptions",
            "Updated Psychosis - Suspiciousness",
            "Updated Psychosis - Trust Difficulty",
            "Updated Psychosis - Certainty",
            "Updated Psychosis - Distress",
        ],
        "key": "daily_psychosis_drivers",
        "type": "line",
    },
]

SNAPSHOT_CHARTS = [
    {
        "title": "Snapshot model scores (%)",
        "cols": ["Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"],
        "key": "snapshot_model_scores",
        "type": "line",
    },
    {
        "title": "Snapshot scores vs 10-response averages (%)",
        "cols": [
            "Depression Score %",
            "10-Response Average (Depression %)",
            "Mania Score %",
            "10-Response Average (Mania %)",
            "Psychosis Score %",
            "10-Response Average (Psychosis %)",
            "Mixed Score %",
            "10-Response Average (Mixed %)",
        ],
        "key": "snapshot_scores_vs_avg",
        "type": "line",
    },
    {
        "title": "Deviation from 10-response averages (percentage points)",
        "cols": [
            "Deviation From 10-Response Average (Depression %)",
            "Deviation From 10-Response Average (Mania %)",
            "Deviation From 10-Response Average (Psychosis %)",
            "Deviation From 10-Response Average (Mixed %)",
        ],
        "key": "snapshot_deviation",
        "type": "line",
    },
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
    if df.empty:
        return df
    return df.rename(columns=COLUMN_ALIASES)


def convert_numeric(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    working = df.copy()
    for col in working.columns:
        if col in ["Timestamp", "Date", "Date (int)", "Updated Daily [Experience description]"]:
            continue
        converted = pd.to_numeric(working[col], errors="coerce")
        if converted.notna().any():
            working[col] = converted
    return working


def bool_from_response(val):
    text = str(val).strip().lower()
    return text in ["yes", "true", "1", "y", "checked"]


def score_response_0_2(val):
    text = str(val).strip().lower()
    if text == "yes":
        return 2
    if text == "somewhat":
        return 1
    if text == "no":
        return 0
    return 0


def score_response_pct(val):
    return score_response_0_2(val) / 2 * 100.0


def prettify_signal_name(name: str) -> str:
    return (
        name.replace("Signals and indicators [", "")
        .replace("Symptoms: [", "")
        .replace("Updated Daily [", "")
        .replace("]", "")
    )


def drop_blank_tail_rows(df: pd.DataFrame, required_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df

    present = [c for c in required_cols if c in df.columns]
    if not present:
        return df.dropna(how="all").copy()

    return df.dropna(subset=present, how="all").copy()


def to_float(value, default=0.0) -> float:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    if value is None:
        return default

    text = str(value).strip()
    if text == "":
        return default

    try:
        return float(text)
    except Exception:
        return default


def to_int(value, default=0) -> int:
    return int(round(to_float(value, default=default)))


def normalize_0_10_to_pct(series, inverse: bool = False) -> pd.Series:
    if not isinstance(series, pd.Series):
        series = pd.Series(series)

    s = pd.to_numeric(series, errors="coerce")
    if inverse:
        return ((10 - s).clip(lower=0, upper=10) / 10.0) * 100.0
    return (s.clip(lower=0, upper=10) / 10.0) * 100.0


def normalize_1_5_to_pct(series, inverse: bool = False) -> pd.Series:
    if not isinstance(series, pd.Series):
        series = pd.Series(series)

    s = pd.to_numeric(series, errors="coerce")
    # 1-5 scale: 1 = lowest intensity/best, 5 = highest intensity/worst
    if inverse:
        return ((5 - (s - 1).clip(lower=0, upper=4)) / 4.0) * 100.0
    return (((s - 1).clip(lower=0, upper=4)) / 4.0) * 100.0


def normalize_flag_count_to_pct(series: pd.Series, max_flags: int) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    if max_flags <= 0:
        return pd.Series(0.0, index=s.index)
    return (s.clip(lower=0, upper=max_flags) / max_flags) * 100.0


def weighted_average_percent(df: pd.DataFrame, col_weight_pairs: list[tuple[str, float]]) -> pd.Series:
    numerator = pd.Series(0.0, index=df.index, dtype=float)
    denominator = 0.0

    for col, weight in col_weight_pairs:
        if col in df.columns and weight > 0:
            numerator = numerator + (pd.to_numeric(df[col], errors="coerce").fillna(0.0) * weight)
            denominator += weight

    if denominator == 0:
        return pd.Series(0.0, index=df.index, dtype=float)

    return numerator / denominator


def weighted_average_percent_from_responses(df: pd.DataFrame, col_weight_pairs: list[tuple[str, float]]) -> pd.Series:
    numerator = pd.Series(0.0, index=df.index, dtype=float)
    denominator = 0.0

    for col, weight in col_weight_pairs:
        if col in df.columns and weight > 0:
            numerator = numerator + (df[col].apply(score_response_pct) * weight)
            denominator += weight

    if denominator == 0:
        return pd.Series(0.0, index=df.index, dtype=float)

    return numerator / denominator


def weighted_blend_series(primary: pd.Series | None, secondary: pd.Series | None, primary_weight: float, secondary_weight: float) -> pd.Series:
    if primary is None and secondary is None:
        return pd.Series(dtype=float)

    pieces = []
    weights = []

    if primary is not None:
        pieces.append(pd.to_numeric(primary, errors="coerce"))
        weights.append(max(0.0, float(primary_weight)))

    if secondary is not None:
        pieces.append(pd.to_numeric(secondary, errors="coerce"))
        weights.append(max(0.0, float(secondary_weight)))

    if not pieces:
        return pd.Series(dtype=float)

    if sum(weights) == 0:
        return pd.concat(pieces, axis=1).mean(axis=1)

    out = pd.Series(0.0, index=pieces[0].index, dtype=float)
    denom = pd.Series(0.0, index=pieces[0].index, dtype=float)

    for s, w in zip(pieces, weights):
        valid = s.notna()
        out.loc[valid] = out.loc[valid] + (s.loc[valid] * w)
        denom.loc[valid] = denom.loc[valid] + w

    denom = denom.replace(0, pd.NA)
    return (out / denom).fillna(0.0)


def confidence_from_count(count: int, trend: str, level: str) -> str:
    score = 0
    if count >= 5:
        score += 2
    elif count >= 3:
        score += 1

    if trend != "Stable":
        score += 1

    if level in ["Medium", "High"]:
        score += 1

    if score >= 4:
        return "High"
    if score >= 2:
        return "Medium"
    return "Low"


def level_from_percent(score_pct, medium_pct, high_pct) -> str:
    score = to_float(score_pct, 0.0)
    if score >= high_pct:
        return "High"
    if score >= medium_pct:
        return "Medium"
    return "Low"


def trend_from_deviation_pct(dev_pct, threshold_pct) -> str:
    d = to_float(dev_pct, 0.0)
    if d > threshold_pct:
        return "Rising"
    if d < -threshold_pct:
        return "Falling"
    return "Stable"


def alert_rank(severity: str) -> int:
    return {
        "Monitor": 1,
        "Pay attention today": 2,
        "High concern": 3,
    }.get(severity, 0)


def tone_color_tag(tone: str) -> str:
    return {
        "error": "red",
        "warning": "orange",
        "info": "blue",
        "success": "green",
    }.get(tone, "gray")


def split_into_two_columns(items: list[str]) -> tuple[list[str], list[str]]:
    if not items:
        return [], []
    midpoint = math.ceil(len(items) / 2)
    return items[:midpoint], items[midpoint:]


def find_possible_columns(df: pd.DataFrame, patterns: list[str]) -> list[str]:
    lowered = {c.lower(): c for c in df.columns}
    matches = []
    for col_lower, original in lowered.items():
        if any(p in col_lower for p in patterns):
            matches.append(original)
    return matches


def build_sleeping_pills_flag_series(daily: pd.DataFrame) -> pd.Series:
    if COL_SLEEPING_PILLS not in daily.columns:
        return pd.Series(0, index=daily.index, dtype=int)

    vals = daily[COL_SLEEPING_PILLS]

    if pd.api.types.is_numeric_dtype(vals):
        return (pd.to_numeric(vals, errors="coerce").fillna(0) > 0).astype(int)

    return vals.apply(bool_from_response).astype(int)


# =========================================================
# DEPRESSION FLAG LOGIC
# =========================================================
def build_daily_depression_flag_series(daily: pd.DataFrame) -> pd.Series:
    mood_low = pd.to_numeric(daily.get(COL_MOOD, pd.Series(pd.NA, index=daily.index)), errors="coerce") <= 3
    mental_speed_low = pd.to_numeric(daily.get(COL_MENTAL_SPEED, pd.Series(pd.NA, index=daily.index)), errors="coerce") < 4
    motivation_low = pd.to_numeric(daily.get(COL_MOTIVATION, pd.Series(pd.NA, index=daily.index)), errors="coerce") < 4

    legacy_dep_flag = mood_low | (mental_speed_low & motivation_low)

    updated_low_mood = pd.to_numeric(
        daily.get("Updated Daily [Low mood]", pd.Series(pd.NA, index=daily.index)),
        errors="coerce",
    ) >= 3
    updated_low_energy = pd.to_numeric(
        daily.get("Updated Daily [Low energy]", pd.Series(pd.NA, index=daily.index)),
        errors="coerce",
    ) >= 3
    updated_low_motivation = pd.to_numeric(
        daily.get("Updated Daily [Low motivation]", pd.Series(pd.NA, index=daily.index)),
        errors="coerce",
    ) >= 3
    updated_low_interest = pd.to_numeric(
        daily.get("Updated Daily [Low interest]", pd.Series(pd.NA, index=daily.index)),
        errors="coerce",
    ) >= 3
    updated_withdrawal = pd.to_numeric(
        daily.get("Updated Daily [Withdrawal]", pd.Series(pd.NA, index=daily.index)),
        errors="coerce",
    ) >= 3
    updated_self_harm = pd.to_numeric(
        daily.get("Updated Daily [Self-harm ideation]", pd.Series(pd.NA, index=daily.index)),
        errors="coerce",
    ) >= 2
    self_report_down = pd.to_numeric(
        daily.get(SIG_DOWN_NOW, pd.Series(0, index=daily.index)),
        errors="coerce",
    ).fillna(0) > 0

    updated_dep_flag = (
        updated_self_harm
        | self_report_down
        | updated_low_mood
        | ((updated_low_energy | updated_low_motivation | updated_low_interest | updated_withdrawal) & updated_low_mood)
    )

    dep_flag = legacy_dep_flag | updated_dep_flag
    return dep_flag.fillna(False).astype(int)


def build_snapshot_depression_flag_series(df: pd.DataFrame) -> pd.Series:
    result = pd.Series(False, index=df.index)

    fixed_cols = [
        "Symptoms: [Very low or depressed mood]",
        "Symptoms: [Somewhat low or depressed mood]",
    ]
    existing_fixed = [c for c in fixed_cols if c in df.columns]
    for col in existing_fixed:
        result = result | (df[col].astype(str).str.strip().str.lower().isin(["yes", "somewhat"]))

    possible_dep_cols = find_possible_columns(
        df,
        [
            "experiencing a down",
            "going to experience a down",
            "in a depression",
            "going into a depression",
            "depression now",
            "depression coming",
        ],
    )
    for col in possible_dep_cols:
        result = result | (df[col].astype(str).str.strip().str.lower().isin(["yes", "somewhat"]))

    return result.astype(int)


# =========================================================
# UI HELPERS - STREAMLIT NATIVE
# =========================================================
def render_status_card(title: str, score_pct: float, level: str, trend: str, confidence: str):
    with st.container(border=True):
        st.markdown(f"#### {title}")

        level_color = {"High": "red", "Medium": "orange", "Low": "green"}.get(level, "gray")
        conf_color = {"High": "green", "Medium": "orange", "Low": "gray"}.get(confidence, "gray")
        trend_color = {"Rising": "orange", "Falling": "blue", "Stable": "green"}.get(trend, "gray")

        st.markdown(f"**Current:** :{level_color}[{level}] ({score_pct:.1f}%)")
        st.markdown(f"**Trend:** :{trend_color}[{trend}]")
        st.markdown(f"**Confidence:** :{conf_color}[{confidence}]")


def render_daily_card(title: str, data: dict):
    with st.container(border=True):
        st.markdown(f"#### {title}")

        level_color = {"High": "red", "Medium": "orange", "Low": "green"}.get(data["level"], "gray")
        conf_color = {"High": "green", "Medium": "orange", "Low": "gray"}.get(data["confidence"], "gray")
        trend_color = {"Rising": "orange", "Falling": "blue", "Stable": "green"}.get(data["trend"], "gray")

        st.markdown(f"**Current state:** :{level_color}[{data['level']}] ({data['score_pct']:.1f}%)")
        st.markdown(f"**Recent direction:** :{trend_color}[{data['trend']}]")
        st.markdown(f"**Confidence:** :{conf_color}[{data['confidence']}]")

        if data.get("baseline_note"):
            st.markdown(f"**Compared with usual:** {data['baseline_note']}")

        if data.get("baseline_z_text"):
            with st.expander("Baseline detail"):
                st.write(data["baseline_z_text"])

        reasons = data.get("reasons", [])
        st.markdown("**Main drivers:**")
        if reasons:
            r1, r2 = split_into_two_columns(reasons)
            c1, c2 = st.columns(2)
            with c1:
                for reason in r1:
                    st.write(f"- {reason}")
            with c2:
                for reason in r2:
                    st.write(f"- {reason}")
        else:
            st.write("- No strong drivers")


def render_two_column_flag_box(title: str, items: list[str], tone: str = "info"):
    with st.container(border=True):
        color = tone_color_tag(tone)
        st.markdown(f"#### :{color}[{title}]")

        if not items:
            st.markdown(":gray[- None]")
            return

        left_items, right_items = split_into_two_columns(items)
        c1, c2 = st.columns(2)

        with c1:
            for item in left_items:
                st.markdown(f":{color}[- {item}]")

        with c2:
            for item in right_items:
                st.markdown(f":{color}[- {item}]")


def render_alert_card(alert: dict):
    tone = {
        "High concern": "error",
        "Pay attention today": "warning",
        "Monitor": "info",
    }.get(alert["severity"], "info")
    color = tone_color_tag(tone)

    with st.container(border=True):
        st.markdown(f"#### :{color}[{alert['title']}]")
        st.markdown(f"**Status:** :{color}[{alert['severity']}]")
        st.markdown(f"**Summary:** {alert['summary']}")

        details = alert.get("details", [])
        if details:
            st.markdown("**Details:**")
            d1, d2 = split_into_two_columns(details)
            c1, c2 = st.columns(2)
            with c1:
                for d in d1:
                    st.markdown(f":{color}[- {d}]")
            with c2:
                for d in d2:
                    st.markdown(f":{color}[- {d}]")


def render_summary_cards(summary: dict, detailed: bool = False):
    if not summary:
        st.info("No summary available.")
        return

    cols = st.columns(len(summary))
    for col, name in zip(cols, summary.keys()):
        with col:
            if detailed:
                render_daily_card(name, summary[name])
            else:
                render_status_card(
                    name,
                    summary[name]["score_pct"],
                    summary[name]["level"],
                    summary[name]["trend"],
                    summary[name]["confidence"],
                )


def render_settings_form(session_key: str, settings_ui: dict, columns_per_row: int = 3):
    for section, items in settings_ui.items():
        st.markdown(f"#### {section}")
        for i in range(0, len(items), columns_per_row):
            row_items = items[i:i + columns_per_row]
            cols = st.columns(len(row_items))
            for col, (key, label, min_v, max_v, step) in zip(cols, row_items):
                with col:
                    current_val = st.session_state[session_key][key]
                    if isinstance(step, int) or (isinstance(current_val, int) and float(step).is_integer()):
                        st.session_state[session_key][key] = st.number_input(
                            label,
                            min_value=int(min_v),
                            max_value=int(max_v),
                            value=int(current_val),
                            step=int(step),
                            key=f"{session_key}_{key}",
                        )
                    else:
                        st.session_state[session_key][key] = st.number_input(
                            label,
                            min_value=float(min_v),
                            max_value=float(max_v),
                            value=float(current_val),
                            step=float(step),
                            key=f"{session_key}_{key}",
                        )


def filter_df_by_date(df: pd.DataFrame, date_col: str, key_prefix: str):
    if df.empty or date_col not in df.columns:
        return df

    working = df.copy()
    working = working[working[date_col].notna()].copy()

    if working.empty:
        return working

    min_date = pd.to_datetime(working[date_col]).min().date()
    max_date = pd.to_datetime(working[date_col]).max().date()

    start_end = st.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key=f"{key_prefix}_date_range",
    )

    if isinstance(start_end, tuple) and len(start_end) == 2:
        start_date, end_date = start_end
    else:
        start_date, end_date = min_date, max_date

    mask = (
        pd.to_datetime(working[date_col]).dt.date >= start_date
    ) & (
        pd.to_datetime(working[date_col]).dt.date <= end_date
    )

    return working.loc[mask].copy()


def render_filtered_chart(
    df: pd.DataFrame,
    date_col: str,
    label_col: str,
    title: str,
    default_cols: list[str],
    key_prefix: str,
    chart_type: str = "line",
):
    st.markdown(f"### {title}")

    if df.empty:
        st.info("No data available.")
        return

    filtered = filter_df_by_date(df, date_col, key_prefix)
    available_cols = [c for c in default_cols if c in filtered.columns]

    selected_cols = st.multiselect(
        "Series",
        options=available_cols,
        default=available_cols,
        key=f"{key_prefix}_series",
    )

    if filtered.empty:
        st.info("No data in selected date range.")
        return

    if not selected_cols:
        st.info("Pick at least one series.")
        return

    chart_df = filtered[[label_col] + selected_cols].set_index(label_col)

    if chart_type == "bar":
        st.bar_chart(chart_df)
    else:
        st.line_chart(chart_df)


def render_chart_group(df, date_col, label_col, chart_defs):
    for chart in chart_defs:
        render_filtered_chart(
            df=df,
            date_col=date_col,
            label_col=label_col,
            title=chart["title"],
            default_cols=[c for c in chart["cols"] if c in df.columns],
            key_prefix=chart["key"],
            chart_type=chart["type"],
        )


def render_dataframe_picker(title: str, df: pd.DataFrame, default_cols: list[str], key: str):
    st.markdown(f"### {title}")

    if df.empty:
        st.info("No data available.")
        return

    selected_cols = st.multiselect(
        f"Choose {title} columns",
        df.columns.tolist(),
        default=default_cols if default_cols else df.columns.tolist()[:12],
        key=key,
    )

    if selected_cols:
        st.dataframe(df[selected_cols], use_container_width=True)


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
    ws = get_workbook().worksheet(tab_name)
    data = ws.get_all_values()

    if not data:
        return pd.DataFrame()

    headers = [str(h).strip() if h is not None else "" for h in data[0]]
    rows = data[1:]

    seen = {}
    unique_headers = []

    for i, header in enumerate(headers):
        base = header if header else f"Unnamed_{i+1}"
        if base in seen:
            seen[base] += 1
            unique_headers.append(f"{base}_{seen[base]}")
        else:
            seen[base] = 0
            unique_headers.append(base)

    df = pd.DataFrame(rows, columns=unique_headers)
    df = df.loc[:, ~df.columns.duplicated()]
    df = normalize_columns(df)

    for dt_col in ["Timestamp", "Date", "Date (int)"]:
        if dt_col in df.columns:
            df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce", dayfirst=True)

    return df


# =========================================================
# PREP FUNCTIONS
# =========================================================
def prepare_form_raw(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    working = convert_numeric(df.copy())
    working = drop_blank_tail_rows(working, ["Timestamp", COL_MOOD, COL_SLEEP_QUALITY, COL_ENERGY])

    if "Timestamp" in working.columns:
        working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
        working["Date"] = working["Timestamp"].dt.date

    return working.sort_values("Timestamp").reset_index(drop=True)


def prepare_quick_form_raw(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    working = df.copy()
    working = drop_blank_tail_rows(working, ["Timestamp"])
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    working = working.sort_values("Timestamp").reset_index(drop=True)

    symptom_cols = [c for c in working.columns if c != "Timestamp"]
    for col in symptom_cols:
        working[f"{col} Numeric"] = working[col].apply(score_response_0_2)
        working[f"{col} Percent"] = working[col].apply(score_response_pct)
        working[f"{col} Trend"] = working[f"{col} Percent"].diff()

    return working


def prepare_updated_daily_raw(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    working = normalize_columns(df.copy())
    working = convert_numeric(working)
    working = drop_blank_tail_rows(working, ["Timestamp"])
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce", dayfirst=True)
    working["Date"] = working["Timestamp"].dt.date

    bool_like_cols = [
        c for c in working.columns
        if c.startswith("Signals and indicators [") or c == "Took sleeping medication?"
    ]
    for col in bool_like_cols:
        if col in working.columns:
            if pd.api.types.is_numeric_dtype(working[col]):
                working[col] = (pd.to_numeric(working[col], errors="coerce").fillna(0) > 0).astype(int)
            else:
                working[col] = working[col].apply(bool_from_response).astype(int)

    return working.sort_values("Timestamp").reset_index(drop=True)


# =========================================================
# MODEL HELPERS
# =========================================================
def build_updated_daily_features(updated_df: pd.DataFrame) -> pd.DataFrame:
    if updated_df.empty or "Date" not in updated_df.columns:
        return pd.DataFrame()

    working = updated_df.copy()

    mapping = {
        "Updated Daily [Low mood]": ("Updated Depression - Low Mood", False),
        "Updated Daily [Low energy]": ("Updated Depression - Low Energy", False),
        "Updated Daily [Low motivation]": ("Updated Depression - Low Motivation", False),
        "Updated Daily [Low interest]": ("Updated Depression - Low Interest", False),
        "Updated Daily [Withdrawal]": ("Updated Depression - Withdrawal", False),
        "Updated Daily [Self-harm ideation]": ("Updated Depression - Self-Harm", False),

        "Updated Daily [Elevated mood]": ("Updated Mania - Elevated Mood", False),
        "Updated Daily [High energy]": ("Updated Mania - High Energy", False),
        "Updated Daily [Agitation]": ("Updated Mania - Agitation", False),
        "Updated Daily [Racing thoughts]": ("Updated Mania - Racing Thoughts", False),
        "Updated Daily [Irritability]": ("Updated Mania - Irritability", False),
        "Updated Daily [Goal-directed activity]": ("Updated Mania - Goal Activity", False),

        "Updated Daily [Heard or saw things]": ("Updated Psychosis - Perceptions", False),
        "Updated Daily [Suspiciousness]": ("Updated Psychosis - Suspiciousness", False),
        "Updated Daily [Trouble trusting perceptions]": ("Updated Psychosis - Trust Difficulty", False),
        "Updated Daily [Belief certainty]": ("Updated Psychosis - Certainty", False),
        "Updated Daily [Psychosis distress]": ("Updated Psychosis - Distress", False),

        "Updated Daily [Sleep quality]": ("Updated Sleep Quality %", True),
        "Updated Daily [Work functioning]": ("Updated Work Functioning Impact %", True),
        "Updated Daily [Daily functioning]": ("Updated Daily Functioning Impact %", True),
    }

    for source_col, (out_col, inverse) in mapping.items():
        if source_col in working.columns:
            working[out_col] = normalize_1_5_to_pct(working[source_col], inverse=inverse)

    passthrough_numeric = [c for c in ["Updated Daily [Sleep hours]"] if c in working.columns]
    score_cols = [c for c in working.columns if c.startswith("Updated ")]
    signal_cols = [c for c in working.columns if c.startswith("Signals and indicators [")]
    bool_cols = [c for c in ["Took sleeping medication?"] if c in working.columns]

    parts = []

    if score_cols or passthrough_numeric:
        parts.append(
            working.groupby("Date", as_index=False)[score_cols + passthrough_numeric].mean()
        )

    if signal_cols:
        parts.append(
            working.groupby("Date", as_index=False)[signal_cols].max()
        )

    if bool_cols:
        parts.append(
            working.groupby("Date", as_index=False)[bool_cols].max()
        )

    if not parts:
        return pd.DataFrame()

    out = parts[0]
    for part in parts[1:]:
        out = out.merge(part, on="Date", how="outer")

    return out.sort_values("Date").reset_index(drop=True)


def build_domain_scores(daily: pd.DataFrame, domain_name: str, config: dict, settings: dict):
    component_pairs = []

    sleep_pills_pct = pd.Series(0.0, index=daily.index)
    if COL_SLEEPING_PILLS in daily.columns:
        sleep_pills_pct = build_sleeping_pills_flag_series(daily) * 100.0

    for label, source_col, inverse, weight_key in config["components"]:
        out_col = f"{domain_name} - {label}"
        source_series = daily[source_col] if source_col in daily.columns else pd.Series(0, index=daily.index)
        daily[out_col] = normalize_0_10_to_pct(source_series, inverse=inverse)

        if label == "Low Sleep Quality":
            daily[out_col] = pd.concat(
                [daily[out_col], sleep_pills_pct],
                axis=1
            ).max(axis=1)

        component_pairs.append((out_col, float(settings[weight_key])))

    flag_score_col = f"{domain_name} - Flags"
    flags_col = f"{domain_name} Flags"

    if config.get("custom_flag_logic") == "depression":
        daily[flags_col] = build_daily_depression_flag_series(daily)
        daily[flag_score_col] = normalize_flag_count_to_pct(daily[flags_col], max_flags=1)
    else:
        flag_cols = [c for c in config["flags"] if c in daily.columns]
        if flag_cols:
            daily[flags_col] = daily[flag_cols].sum(axis=1)
            daily[flag_score_col] = normalize_flag_count_to_pct(
                daily[flags_col],
                max_flags=len(flag_cols),
            )
        else:
            daily[flags_col] = 0
            daily[flag_score_col] = 0.0

    component_pairs.append((flag_score_col, float(settings[config["flag_weight_key"]])))

    score_col = f"{domain_name} Score %"
    avg_col = f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average ({domain_name} %)"
    dev_col = f"{domain_name} Deviation %"

    daily[score_col] = weighted_average_percent(daily, component_pairs)
    daily[avg_col] = daily[score_col].rolling(window=DAILY_ROLLING_WINDOW_DAYS, min_periods=1).mean()
    daily[dev_col] = daily[score_col] - daily[avg_col]

    return daily


def add_personal_baselines(df: pd.DataFrame, settings: dict, domains: list[str]) -> pd.DataFrame:
    if df.empty:
        return df

    working = df.copy()
    window = int(settings.get("baseline_window_days", 14))
    if window < 3:
        window = 3

    for name in domains:
        score_col = f"{name} Score %"
        baseline_col = f"{name} Baseline %"
        baseline_diff_col = f"{name} Baseline Difference %"
        baseline_std_col = f"{name} Baseline Std %"
        baseline_z_col = f"{name} Baseline Z"

        prev_scores = working[score_col].shift(1)
        baseline = prev_scores.rolling(window=window, min_periods=3).mean()
        baseline_std = prev_scores.rolling(window=window, min_periods=3).std()

        working[baseline_col] = baseline
        working[baseline_std_col] = baseline_std
        working[baseline_diff_col] = working[score_col] - working[baseline_col]

        safe_std = baseline_std.where((baseline_std.notna()) & (baseline_std > 0), 1.0)
        z = (working[score_col] - working[baseline_col]) / safe_std
        z = z.where(working[baseline_col].notna(), 0.0)
        working[baseline_z_col] = z.fillna(0.0)

    return working


def build_domain_summary(df: pd.DataFrame, settings: dict, domains: list[str], include_reasons: bool = True) -> dict:
    if df.empty:
        return {}

    latest = df.iloc[-1]
    last5 = df.tail(5)

    medium_pct = float(settings["medium_threshold_pct"])
    high_pct = float(settings["high_threshold_pct"])
    trend_threshold_pct = float(settings["trend_threshold_pct"])
    anomaly_thr = float(settings.get("anomaly_z_threshold", 1.5))
    high_anomaly_thr = float(settings.get("high_anomaly_z_threshold", 2.5))

    summary = {}

    for name in domains:
        score_col = f"{name} Score %"
        dev_col = f"{name} Deviation %"
        z_col = f"{name} Baseline Z"
        baseline_diff_col = f"{name} Baseline Difference %"

        score_pct = to_float(latest.get(score_col, 0.0), 0.0)
        dev_pct = to_float(latest.get(dev_col, 0.0), 0.0)
        level = level_from_percent(score_pct, medium_pct, high_pct)
        trend = trend_from_deviation_pct(dev_pct, trend_threshold_pct)
        confidence = confidence_from_count(len(last5), trend, level)

        z_val = to_float(latest.get(z_col, 0.0), 0.0)
        diff_val = to_float(latest.get(baseline_diff_col, 0.0), 0.0)

        baseline_note = ""
        baseline_z_text = ""
        if abs(z_val) >= high_anomaly_thr:
            direction = "higher" if diff_val >= 0 else "lower"
            baseline_note = f"much {direction} than your recent baseline ({diff_val:+.1f} points)"
            baseline_z_text = f"z={z_val:+.2f}"
        elif abs(z_val) >= anomaly_thr:
            direction = "higher" if diff_val >= 0 else "lower"
            baseline_note = f"noticeably {direction} than your recent baseline ({diff_val:+.1f} points)"
            baseline_z_text = f"z={z_val:+.2f}"
        elif pd.notna(latest.get(f"{name} Baseline %", pd.NA)):
            baseline_note = f"close to your recent baseline ({diff_val:+.1f} points)"
            baseline_z_text = f"z={z_val:+.2f}"

        item = {
            "score_pct": score_pct,
            "level": level,
            "trend": trend,
            "confidence": confidence,
            "baseline_z": z_val,
            "baseline_diff_pct": diff_val,
            "baseline_note": baseline_note,
            "baseline_z_text": baseline_z_text,
        }

        if include_reasons:
            component_cols = [c for c in df.columns if c.startswith(f"{name} - ")]
            updated_component_cols = [c for c in df.columns if c.startswith(f"Updated {name} -")]
            if name == "Depression":
                extra_cols = [c for c in ["Updated Work Functioning Impact %", "Updated Daily Functioning Impact %", "Updated Sleep Quality %"] if c in df.columns]
            elif name == "Mania":
                extra_cols = [c for c in ["Updated Sleep Quality %"] if c in df.columns]
            else:
                extra_cols = []

            reason_cols = component_cols + updated_component_cols + extra_cols

            raw_reasons = sorted(
                [(c, to_float(latest.get(c, 0.0))) for c in reason_cols],
                key=lambda x: x[1],
                reverse=True,
            )
            item["reasons"] = [
                REASON_LABELS.get(col, col.replace(f"{name} - ", "").replace(f"Updated {name} - ", ""))
                for col, value in raw_reasons
                if value > 0
            ][:5]

        if name == "Depression":
            dep_flag_on = to_int(latest.get("Depression Flags", 0)) > 0
            if not dep_flag_on:
                item["level"] = "Low"
                item["trend"] = "Stable"
                item["confidence"] = "Low"
                item["reasons"] = []
                item["baseline_note"] = ""
                item["baseline_z_text"] = ""

        summary[name] = item

    return summary


# =========================================================
# DAILY MODEL
# =========================================================
def build_daily_model_from_form(
    form_df: pd.DataFrame,
    settings: dict,
    updated_daily_df: pd.DataFrame | None = None,
):
    if (
        (form_df.empty or "Timestamp" not in form_df.columns)
        and (updated_daily_df is None or updated_daily_df.empty)
    ):
        return pd.DataFrame(), None

    # Legacy daily source
    if form_df.empty or "Timestamp" not in form_df.columns:
        daily_scores = pd.DataFrame(columns=["Date"])
        daily_flags = pd.DataFrame(columns=["Date"])
        sleep_med_df = pd.DataFrame(columns=["Date"])
    else:
        working = form_df.copy()
        working = convert_numeric(working)
        working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
        working["Date"] = working["Timestamp"].dt.date

        signal_columns = [c for c in working.columns if c.startswith("Signals and indicators [")]
        for col in signal_columns:
            working[col] = working[col].apply(bool_from_response).astype(int)

        numeric_cols = [
            c for c in [
                COL_MOOD, COL_SLEEP_HOURS, COL_SLEEP_QUALITY, COL_ENERGY,
                COL_MENTAL_SPEED, COL_IMPULSIVITY, COL_MOTIVATION,
                COL_IRRITABILITY, COL_AGITATION,
                COL_UNUSUAL, COL_SUSPICIOUS, COL_CERTAINTY
            ]
            if c in working.columns
        ]

        daily_scores = (
            working.groupby("Date", as_index=False)[numeric_cols].mean()
            if numeric_cols else pd.DataFrame({"Date": working["Date"].dropna().unique()})
        )

        daily_flags = (
            working.groupby("Date", as_index=False)[signal_columns].sum()
            if signal_columns else pd.DataFrame({"Date": working["Date"].dropna().unique()})
        )

        sleep_med_df = pd.DataFrame({"Date": working["Date"].dropna().unique()})
        if COL_SLEEPING_PILLS in working.columns:
            sleep_med_df = (
                working.groupby("Date", as_index=False)[COL_SLEEPING_PILLS]
                .agg(lambda s: int(any(bool_from_response(v) for v in s)))
            )

    daily = (
        daily_scores.merge(daily_flags, on="Date", how="outer")
        .merge(sleep_med_df, on="Date", how="outer")
        .sort_values("Date")
        .reset_index(drop=True)
    )

    # Updated daily source
    if updated_daily_df is not None and not updated_daily_df.empty:
        updated_features = build_updated_daily_features(updated_daily_df)
        if not updated_features.empty:
            daily = daily.merge(updated_features, on="Date", how="outer")

    if daily.empty:
        return pd.DataFrame(), None

    daily = daily.sort_values("Date").reset_index(drop=True)
    daily["DateLabel"] = pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")

    if COL_SLEEPING_PILLS in daily.columns:
        daily[COL_SLEEPING_PILLS] = pd.to_numeric(daily[COL_SLEEPING_PILLS], errors="coerce").fillna(0).astype(int)

    # Build legacy model scores first
    for domain_name, config in DAILY_DOMAIN_CONFIG.items():
        daily = build_domain_scores(daily, domain_name, config, settings)

    daily["Sleeping Pills Flag"] = build_sleeping_pills_flag_series(daily)

    # Updated daily domain scores
    dep_updated_cols = [
        c for c in [
            "Updated Depression - Low Mood",
            "Updated Depression - Low Energy",
            "Updated Depression - Low Motivation",
            "Updated Depression - Low Interest",
            "Updated Depression - Withdrawal",
            "Updated Depression - Self-Harm",
            "Updated Work Functioning Impact %",
            "Updated Daily Functioning Impact %",
            "Updated Sleep Quality %",
        ] if c in daily.columns
    ]
    if dep_updated_cols:
        daily["Updated Depression Score %"] = daily[dep_updated_cols].mean(axis=1)

    mania_updated_cols = [
        c for c in [
            "Updated Mania - Elevated Mood",
            "Updated Mania - High Energy",
            "Updated Mania - Agitation",
            "Updated Mania - Racing Thoughts",
            "Updated Mania - Irritability",
            "Updated Mania - Goal Activity",
            "Updated Sleep Quality %",
        ] if c in daily.columns
    ]
    if mania_updated_cols:
        daily["Updated Mania Score %"] = daily[mania_updated_cols].mean(axis=1)

    psych_updated_cols = [
        c for c in [
            "Updated Psychosis - Perceptions",
            "Updated Psychosis - Suspiciousness",
            "Updated Psychosis - Trust Difficulty",
            "Updated Psychosis - Certainty",
            "Updated Psychosis - Distress",
        ] if c in daily.columns
    ]
    if psych_updated_cols:
        daily["Updated Psychosis Score %"] = daily[psych_updated_cols].mean(axis=1)

    # Blend legacy + updated model scores
    legacy_weight = float(settings.get("legacy_daily_weight", 0.3))
    updated_weight = float(settings.get("updated_daily_weight", 0.7))

    if "Updated Depression Score %" in daily.columns:
        daily["Depression Score %"] = weighted_blend_series(
            daily["Depression Score %"],
            daily["Updated Depression Score %"],
            legacy_weight,
            updated_weight,
        )

    if "Updated Mania Score %" in daily.columns:
        daily["Mania Score %"] = weighted_blend_series(
            daily["Mania Score %"],
            daily["Updated Mania Score %"],
            legacy_weight,
            updated_weight,
        )

    if "Updated Psychosis Score %" in daily.columns:
        daily["Psychosis Score %"] = weighted_blend_series(
            daily["Psychosis Score %"],
            daily["Updated Psychosis Score %"],
            legacy_weight,
            updated_weight,
        )

    # Recompute rolling averages/deviations after blending
    for name in ["Depression", "Mania", "Psychosis"]:
        score_col = f"{name} Score %"
        avg_col = f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average ({name} %)"
        dev_col = f"{name} Deviation %"
        daily[avg_col] = daily[score_col].rolling(window=DAILY_ROLLING_WINDOW_DAYS, min_periods=1).mean()
        daily[dev_col] = daily[score_col] - daily[avg_col]

    mixed_weight_total = (
        float(settings["mixed_dep_weight"])
        + float(settings["mixed_mania_weight"])
        + float(settings["mixed_psych_weight"])
        + float(settings["mixed_low_sleep_quality_weight"])
    )
    if mixed_weight_total == 0:
        mixed_weight_total = 1.0

    mixed_sleep_quality_series = daily.get(
        "Updated Sleep Quality %",
        daily.get("Depression - Low Sleep Quality", pd.Series(0, index=daily.index))
    )

    daily["Mixed Score %"] = (
        daily["Depression Score %"] * float(settings["mixed_dep_weight"])
        + daily["Mania Score %"] * float(settings["mixed_mania_weight"])
        + daily["Psychosis Score %"] * float(settings["mixed_psych_weight"])
        + mixed_sleep_quality_series * float(settings["mixed_low_sleep_quality_weight"])
    ) / mixed_weight_total

    daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"] = daily["Mixed Score %"].rolling(
        window=DAILY_ROLLING_WINDOW_DAYS, min_periods=1
    ).mean()
    daily["Mixed Deviation %"] = daily["Mixed Score %"] - daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"]

    mixed_flag_components = [
        c for c in [SIG_MIXED_NOW, SIG_MIXED_COMING, SIG_WITHDRAW, SIG_LESS_SLEEP, SIG_MORE_ACTIVITY]
        if c in daily.columns
    ]
    daily["Mixed Flags"] = daily[mixed_flag_components].sum(axis=1) if mixed_flag_components else 0

    concerning_cols = [c for c in [SIG_NOT_MYSELF, SIG_MISSED_MEDS, SIG_ROUTINE, SIG_STRESS_PSYCH, SIG_STRESS_PHYS] if c in daily.columns]
    daily["Concerning Situation Flags"] = daily[concerning_cols].sum(axis=1) if concerning_cols else 0

    dep_self_cols = [c for c in [SIG_DOWN_NOW, SIG_DOWN_COMING] if c in daily.columns]
    man_self_cols = [c for c in [SIG_UP_NOW, SIG_UP_COMING] if c in daily.columns]
    mix_self_cols = [c for c in [SIG_MIXED_NOW, SIG_MIXED_COMING] if c in daily.columns]

    daily["Self-Reported Depression"] = daily[dep_self_cols].sum(axis=1) if dep_self_cols else 0
    daily["Self-Reported Mania"] = daily[man_self_cols].sum(axis=1) if man_self_cols else 0
    daily["Self-Reported Mixed"] = daily[mix_self_cols].sum(axis=1) if mix_self_cols else 0

    daily = add_personal_baselines(daily, settings, DOMAIN_NAMES)
    summary = build_domain_summary(daily, settings, DOMAIN_NAMES, include_reasons=True)

    return daily, summary


# =========================================================
# SNAPSHOT MODEL
# =========================================================
def build_snapshot_model_from_quick_form(quick_form_df: pd.DataFrame, settings: dict):
    if quick_form_df.empty or "Timestamp" not in quick_form_df.columns:
        return None, pd.DataFrame()

    working = quick_form_df.copy()
    working = drop_blank_tail_rows(working, ["Timestamp"])
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    working = working.sort_values("Timestamp").reset_index(drop=True)

    for domain_name, config in SNAPSHOT_DOMAIN_CONFIG.items():
        weights = [(col, float(settings[weight_key])) for col, weight_key in config["components"]]
        working[f"{domain_name} Score %"] = weighted_average_percent_from_responses(working, weights)

    working["Depression Flags"] = build_snapshot_depression_flag_series(working)

    mixed_total_weight = (
        float(settings["mixed_dep_weight"])
        + float(settings["mixed_mania_weight"])
        + float(settings["mixed_psych_weight"])
    )
    if mixed_total_weight == 0:
        mixed_total_weight = 1.0

    working["Mixed Score %"] = (
        working["Depression Score %"] * float(settings["mixed_dep_weight"])
        + working["Mania Score %"] * float(settings["mixed_mania_weight"])
        + working["Psychosis Score %"] * float(settings["mixed_psych_weight"])
    ) / mixed_total_weight

    for name in DOMAIN_NAMES:
        score_col = f"{name} Score %"
        avg_col = f"10-Response Average ({name} %)"
        dev_col = f"Deviation From 10-Response Average ({name} %)"
        working[avg_col] = working[score_col].rolling(window=10, min_periods=1).mean()
        working[dev_col] = working[score_col] - working[avg_col]

    working["FilterDate"] = working["Timestamp"].dt.date
    working["TimeLabel"] = working["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")

    summary = {}
    if not working.empty:
        latest = working.iloc[-1]
        last5 = working.tail(5)

        medium_pct = float(settings["medium_threshold_pct"])
        high_pct = float(settings["high_threshold_pct"])
        trend_threshold_pct = float(settings["trend_threshold_pct"])

        for name in DOMAIN_NAMES:
            score_pct = to_float(latest.get(f"{name} Score %", 0.0), 0.0)
            dev_pct = to_float(latest.get(f"Deviation From 10-Response Average ({name} %)", 0.0), 0.0)
            level = level_from_percent(score_pct, medium_pct, high_pct)
            trend = trend_from_deviation_pct(dev_pct, trend_threshold_pct)
            confidence = confidence_from_count(len(last5), trend, level)

            if name == "Depression" and to_int(latest.get("Depression Flags", 0)) == 0:
                level = "Low"
                trend = "Stable"
                confidence = "Low"

            summary[name] = {
                "score_pct": score_pct,
                "level": level,
                "trend": trend,
                "confidence": confidence,
            }

    return summary, working


# =========================================================
# ALERT ENGINE / TODAY SUMMARY
# =========================================================
def get_domain_persistence(df: pd.DataFrame, domain: str, medium_threshold: float, days: int) -> int:
    if df.empty or len(df) < days:
        return 0

    score_col = f"{domain} Score %"
    recent = df[score_col].tail(days)
    return int((recent >= medium_threshold).all())


def build_alerts(
    daily_model_data: pd.DataFrame,
    daily_summary: dict | None,
    snapshot_summary: dict | None,
    settings: dict,
    snapshot_model_data: pd.DataFrame | None = None,
):
    alerts = []

    if daily_model_data.empty or not daily_summary:
        return alerts

    latest = daily_model_data.iloc[-1]
    medium_pct = float(settings["medium_threshold_pct"])
    anomaly_thr = float(settings.get("anomaly_z_threshold", 1.5))
    high_anomaly_thr = float(settings.get("high_anomaly_z_threshold", 2.5))
    persistence_days = int(settings.get("persistence_days", 3))

    daily_dep_flag_on = to_int(latest.get("Depression Flags", 0)) > 0
    snapshot_dep_flag_on = False
    if snapshot_model_data is not None and not snapshot_model_data.empty:
        snapshot_dep_flag_on = to_int(snapshot_model_data.iloc[-1].get("Depression Flags", 0)) > 0

    for name in DOMAIN_NAMES:
        item = daily_summary[name]

        if name == "Depression" and not daily_dep_flag_on:
            continue

        details = []

        if item["level"] in ["Medium", "High"]:
            details.append(f"{name} score is {item['level'].lower()} at {item['score_pct']:.1f}%.")

        if item["trend"] in ["Rising", "Falling"]:
            details.append(f"Recent direction is {item['trend'].lower()}.")

        z_val = to_float(item.get("baseline_z", 0.0), 0.0)
        diff_val = to_float(item.get("baseline_diff_pct", 0.0), 0.0)
        if abs(z_val) >= anomaly_thr:
            direction = "above" if diff_val >= 0 else "below"
            details.append(f"This is {abs(diff_val):.1f} points {direction} your personal baseline (z={z_val:+.2f}).")

        if get_domain_persistence(daily_model_data, name, medium_pct, persistence_days):
            details.append(f"This pattern has stayed at or above medium for the last {persistence_days} days.")

        snapshot_agrees = False
        if snapshot_summary and name in snapshot_summary:
            snap_level = snapshot_summary[name]["level"]
            if snap_level in ["Medium", "High"]:
                if name != "Depression" or snapshot_dep_flag_on:
                    snapshot_agrees = True
                    details.append(f"Snapshot model also shows {name.lower()} as {snap_level.lower()}.")

        severity = None
        if item["level"] == "High":
            severity = "High concern"
        elif item["level"] == "Medium" and item["trend"] == "Rising":
            severity = "Pay attention today"
        elif abs(z_val) >= high_anomaly_thr:
            severity = "Pay attention today"
        elif snapshot_agrees and item["level"] in ["Medium", "High"]:
            severity = "Pay attention today"
        elif get_domain_persistence(daily_model_data, name, medium_pct, persistence_days):
            severity = "Pay attention today"
        elif abs(z_val) >= anomaly_thr and item["score_pct"] >= (medium_pct * 0.8):
            severity = "Monitor"

        if severity:
            title = f"{name} pattern"
            summary = f"{name} looks {item['level'].lower()} with a {item['trend'].lower()} recent direction."
            if abs(z_val) >= anomaly_thr:
                summary += " It is also unusual relative to your recent baseline."

            alerts.append({
                "severity": severity,
                "domain": name,
                "title": title,
                "summary": summary,
                "details": details,
            })

    concerning_flags = to_int(latest.get("Concerning Situation Flags", 0))
    if concerning_flags > 0:
        severity = "Pay attention today" if concerning_flags <= 2 else "High concern"
        alerts.append({
            "severity": severity,
            "domain": "General",
            "title": "Concerning situation flags",
            "summary": f"{concerning_flags} concerning situation flag(s) were recorded in the latest daily data.",
            "details": [
                "These can matter even if the main domain scores are not high.",
                "Consider checking routine disruption, missed meds, or major stressor signals.",
            ],
        })

    active_high_domains = [
        d for d in DOMAIN_NAMES
        if d != "Depression" and daily_summary[d]["level"] == "High"
    ]
    active_med_plus = [
        d for d in DOMAIN_NAMES
        if d != "Depression" and daily_summary[d]["level"] in ["Medium", "High"]
    ]

    if daily_dep_flag_on and daily_summary["Depression"]["level"] in ["Medium", "High"]:
        active_med_plus.append("Depression")
        if daily_summary["Depression"]["level"] == "High":
            active_high_domains.append("Depression")

    if len(active_high_domains) >= 2 or len(active_med_plus) >= 3:
        alerts.append({
            "severity": "High concern",
            "domain": "General",
            "title": "Multiple elevated patterns",
            "summary": "More than one domain is elevated at the same time.",
            "details": [
                f"Elevated domains: {', '.join(active_med_plus)}.",
                "This may be worth paying extra attention to because the picture is not confined to a single area.",
            ],
        })

    alerts = sorted(alerts, key=lambda a: (-alert_rank(a["severity"]), a["title"]))
    return alerts


def build_today_summary(daily_summary: dict | None, alerts: list[dict], daily_model_data: pd.DataFrame):
    if not daily_summary or daily_model_data.empty:
        return "No daily interpretation is available yet."

    ranked = sorted(
        daily_summary.items(),
        key=lambda kv: (
            {"High": 3, "Medium": 2, "Low": 1}.get(kv[1]["level"], 0),
            kv[1]["score_pct"],
            abs(kv[1].get("baseline_z", 0.0)),
        ),
        reverse=True,
    )
    primary_name, primary = ranked[0]

    top_alert = alerts[0] if alerts else None

    summary = f"Main pattern today: {primary_name.lower()} looks {primary['level'].lower()}"

    if primary["trend"] != "Stable":
        summary += f" and is {primary['trend'].lower()}"

    summary += f" ({primary['score_pct']:.1f}%)."

    if primary.get("baseline_note"):
        summary += f" Compared with your usual pattern, it is {primary['baseline_note']}."

    reasons = primary.get("reasons", [])
    if reasons:
        summary += f" Main drivers: {', '.join(reasons[:3])}."

    if top_alert:
        summary += f" Overall status: {top_alert['severity']}."

    return summary


# =========================================================
# WARNING HELPERS
# =========================================================
def get_latest_form_warning_items(form_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if form_df.empty or "Timestamp" not in form_df.columns:
        return [], []

    working = form_df.copy().sort_values("Timestamp").reset_index(drop=True)
    latest = working.iloc[-1]

    signal_columns = [c for c in working.columns if c.startswith("Signals and indicators [")]
    flagged = []

    for col in signal_columns:
        if bool_from_response(latest.get(col, "")):
            flagged.append(prettify_signal_name(col))

    concerning = []

    for col, label in [
        (COL_MOOD, "Mood score is low"),
        (COL_SLEEP_HOURS, "Sleep hours are low"),
        (COL_SLEEP_QUALITY, "Sleep quality is poor"),
        (COL_MOTIVATION, "Motivation is low"),
        (COL_ENERGY, "Energy is elevated"),
        (COL_MENTAL_SPEED, "Mental speed is elevated"),
        (COL_IMPULSIVITY, "Impulsivity is elevated"),
        (COL_IRRITABILITY, "Irritability is elevated"),
        (COL_AGITATION, "Agitation is elevated"),
        (COL_UNUSUAL, "Unusual perceptions are elevated"),
        (COL_SUSPICIOUS, "Suspiciousness is elevated"),
        (COL_CERTAINTY, "Belief certainty is elevated"),
    ]:
        if col in latest.index:
            val = pd.to_numeric(latest[col], errors="coerce")
            if pd.isna(val):
                continue
            if col in [COL_MOOD, COL_MOTIVATION] and val <= 4:
                concerning.append(f"{label} ({val:.1f})")
            elif col == COL_SLEEP_HOURS and val <= 5:
                concerning.append(f"{label} ({val:.1f})")
            elif col == COL_SLEEP_QUALITY and val <= 4:
                concerning.append(f"{label} ({val:.1f})")
            elif col in [
                COL_ENERGY, COL_MENTAL_SPEED, COL_IMPULSIVITY,
                COL_IRRITABILITY, COL_AGITATION,
                COL_UNUSUAL, COL_SUSPICIOUS, COL_CERTAINTY
            ] and val >= 6:
                concerning.append(f"{label} ({val:.1f})")

    if COL_SLEEPING_PILLS in latest.index and bool_from_response(latest.get(COL_SLEEPING_PILLS, "")):
        concerning.append("Took sleeping medication (treat as bad sleep flag)")

    return flagged, concerning


def get_latest_updated_daily_warning_items(updated_daily_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if updated_daily_df.empty or "Timestamp" not in updated_daily_df.columns:
        return [], []

    working = updated_daily_df.copy().sort_values("Timestamp").reset_index(drop=True)
    latest = working.iloc[-1]

    signals = []
    concerning = []

    signal_columns = [c for c in working.columns if c.startswith("Signals and indicators [")]
    for col in signal_columns:
        val = latest.get(col, 0)
        try:
            is_on = bool(int(val))
        except Exception:
            is_on = bool_from_response(val)
        if is_on:
            signals.append(prettify_signal_name(col))

    score_checks = [
        ("Updated Daily [Low mood]", "Low mood"),
        ("Updated Daily [Low energy]", "Low energy"),
        ("Updated Daily [Low motivation]", "Low motivation"),
        ("Updated Daily [Low interest]", "Low interest / pleasure"),
        ("Updated Daily [Withdrawal]", "Withdrawal"),
        ("Updated Daily [Self-harm ideation]", "Self-harm / suicidal ideation"),
        ("Updated Daily [Elevated mood]", "Elevated mood"),
        ("Updated Daily [High energy]", "High energy"),
        ("Updated Daily [Agitation]", "Agitation"),
        ("Updated Daily [Racing thoughts]", "Racing thoughts / speech"),
        ("Updated Daily [Irritability]", "Irritability"),
        ("Updated Daily [Goal-directed activity]", "Driven activity"),
        ("Updated Daily [Heard or saw things]", "Unusual perceptions"),
        ("Updated Daily [Suspiciousness]", "Suspiciousness"),
        ("Updated Daily [Trouble trusting perceptions]", "Trouble trusting perceptions"),
        ("Updated Daily [Belief certainty]", "Belief certainty"),
        ("Updated Daily [Psychosis distress]", "Distress from beliefs / experiences"),
    ]

    for col, label in score_checks:
        if col in latest.index:
            val = pd.to_numeric(latest[col], errors="coerce")
            if pd.isna(val):
                continue
            if val >= 4:
                concerning.append(f"{label} is high ({val:.1f}/5)")
            elif val >= 3:
                signals.append(f"{label} is elevated ({val:.1f}/5)")

    for col, label in [
        ("Updated Daily [Sleep hours]", "Sleep hours are low"),
        ("Updated Daily [Sleep quality]", "Sleep quality is poor"),
        ("Updated Daily [Work functioning]", "Work functioning is reduced"),
        ("Updated Daily [Daily functioning]", "Daily functioning is reduced"),
    ]:
        if col in latest.index:
            val = pd.to_numeric(latest[col], errors="coerce")
            if pd.isna(val):
                continue
            if col == "Updated Daily [Sleep hours]" and val <= 5:
                concerning.append(f"{label} ({val:.1f})")
            elif col in ["Updated Daily [Sleep quality]", "Updated Daily [Work functioning]", "Updated Daily [Daily functioning]"] and val <= 2:
                concerning.append(f"{label} ({val:.1f}/5)")
            elif col in ["Updated Daily [Sleep quality]", "Updated Daily [Work functioning]", "Updated Daily [Daily functioning]"] and val == 3:
                signals.append(f"{label} is somewhat reduced ({val:.1f}/5)")

    if COL_SLEEPING_PILLS in latest.index:
        val = latest.get(COL_SLEEPING_PILLS, 0)
        try:
            is_on = bool(int(val))
        except Exception:
            is_on = bool_from_response(val)
        if is_on:
            concerning.append("Took sleeping or anti-anxiety medication")

    return signals, concerning


def get_latest_quick_form_warning_items(quick_form_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if quick_form_df.empty or "Timestamp" not in quick_form_df.columns:
        return [], []

    working = quick_form_df.copy().sort_values("Timestamp").reset_index(drop=True)
    latest = working.iloc[-1]

    signals = []
    concerning = []

    for col in working.columns:
        if col == "Timestamp":
            continue
        if col.endswith(" Numeric") or col.endswith(" Percent") or col.endswith(" Trend"):
            continue

        val = str(latest.get(col, "")).strip().lower()
        label = prettify_signal_name(col)

        if val == "yes":
            signals.append(f"{label} — Yes")
        elif val == "somewhat":
            signals.append(f"{label} — Somewhat")

    yes_count = sum(1 for item in signals if item.endswith("Yes"))
    some_count = sum(1 for item in signals if item.endswith("Somewhat"))

    if yes_count >= 3:
        concerning.append(f"Several snapshot symptoms are marked Yes ({yes_count})")
    if some_count >= 3:
        concerning.append(f"Several snapshot symptoms are marked Somewhat ({some_count})")

    return signals, concerning


def get_model_concerning_findings(
    daily_summary: dict | None,
    snapshot_summary: dict | None,
    daily_model_df: pd.DataFrame,
    snapshot_model_df: pd.DataFrame,
) -> tuple[list[str], list[str]]:
    daily_findings = []
    snapshot_findings = []

    daily_dep_flag_on = False
    if not daily_model_df.empty:
        daily_dep_flag_on = to_int(daily_model_df.iloc[-1].get("Depression Flags", 0)) > 0

    snapshot_dep_flag_on = False
    if not snapshot_model_df.empty:
        snapshot_dep_flag_on = to_int(snapshot_model_df.iloc[-1].get("Depression Flags", 0)) > 0

    if daily_summary and not daily_model_df.empty:
        for name in DOMAIN_NAMES:
            if name == "Depression" and not daily_dep_flag_on:
                continue

            item = daily_summary[name]
            if item["level"] in ["Medium", "High"]:
                daily_findings.append(f"Daily {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}")

            if abs(to_float(item.get("baseline_z", 0.0), 0.0)) >= 1.5:
                daily_findings.append(f"Daily {name.lower()} is unusual relative to your recent baseline")

        latest = daily_model_df.iloc[-1]
        concerning_flags = to_float(latest.get("Concerning Situation Flags", 0), 0.0)
        if concerning_flags > 0:
            daily_findings.append(f"Concerning situation flags: {int(concerning_flags)}")

    if snapshot_summary:
        for name in DOMAIN_NAMES:
            if name == "Depression" and not snapshot_dep_flag_on:
                continue

            item = snapshot_summary[name]
            if item["level"] in ["Medium", "High"]:
                snapshot_findings.append(f"Snapshot {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}")

    if snapshot_dep_flag_on:
        snapshot_findings.append("Snapshot depression flag is present")

    return daily_findings, snapshot_findings


# =========================================================
# PAGE RENDERERS
# =========================================================
def render_dashboard_page(
    form_data,
    updated_daily_data,
    quick_form_data,
    daily_model_data,
    daily_model_summary,
    snapshot_model_summary,
    latest_form_signals,
    latest_form_findings,
    latest_updated_daily_signals,
    latest_updated_daily_findings,
    latest_snapshot_signals,
    latest_snapshot_findings,
    daily_model_findings,
    snapshot_model_findings,
    alerts,
    today_summary,
):
    st.subheader("Dashboard")
    st.caption("Daily Model is calculated from Form Responses plus Updated Daily Bipolar Form with adjustable settings. Snapshot Model is calculated from Quick Form Responses with adjustable settings.")

    st.markdown("### Today's interpretation")
    top_alert = alerts[0]["severity"] if alerts else "Monitor"
    tone = "error" if top_alert == "High concern" else ("warning" if top_alert == "Pay attention today" else "info")
    render_two_column_flag_box("Today at a glance", [today_summary], tone=tone)

    st.markdown("### Current alerts")
    if alerts:
        cols = st.columns(min(3, len(alerts)))
        for idx, alert in enumerate(alerts[:3]):
            with cols[idx]:
                render_alert_card(alert)
    else:
        st.info("No active alerts are being generated from the current rules.")

    st.markdown("### Current state")
    st.markdown("#### Daily Model")
    render_summary_cards(daily_model_summary, detailed=True)

    st.markdown("#### Snapshot Model")
    render_summary_cards(snapshot_model_summary, detailed=False)

    st.markdown("### Key warnings")
    warn_left, warn_mid, warn_right = st.columns(3)

    with warn_left:
        render_two_column_flag_box(
            "Legacy daily form",
            latest_form_findings + latest_form_signals,
            tone="error" if latest_form_findings else "warning",
        )

    with warn_mid:
        render_two_column_flag_box(
            "Updated daily form / model",
            latest_updated_daily_findings + daily_model_findings + latest_updated_daily_signals,
            tone="error" if (latest_updated_daily_findings or daily_model_findings) else "warning",
        )

    with warn_right:
        render_two_column_flag_box(
            "Snapshot questionnaire / model",
            latest_snapshot_findings + snapshot_model_findings + latest_snapshot_signals,
            tone="error" if (latest_snapshot_findings or snapshot_model_findings) else "warning",
        )

    st.markdown("### Recent trends")
    if not daily_model_data.empty:
        trend_df = daily_model_data.copy()

        min_date = pd.to_datetime(trend_df["Date"]).min().date()
        max_date = pd.to_datetime(trend_df["Date"]).max().date()

        quick_range = st.selectbox(
            "Trend window",
            ["Last 7 days", "Last 14 days", "Last 30 days", "All data"],
            index=1,
            key="dashboard_trend_window",
        )

        if quick_range == "Last 7 days":
            start_date = max_date - pd.Timedelta(days=6)
        elif quick_range == "Last 14 days":
            start_date = max_date - pd.Timedelta(days=13)
        elif quick_range == "Last 30 days":
            start_date = max_date - pd.Timedelta(days=29)
        else:
            start_date = min_date

        trend_df = trend_df[
            (pd.to_datetime(trend_df["Date"]).dt.date >= start_date) &
            (pd.to_datetime(trend_df["Date"]).dt.date <= max_date)
        ].copy()

        chart_cols = [c for c in [
            "Depression Score %",
            "Mania Score %",
            "Psychosis Score %",
            "Mixed Score %",
            "Updated Depression Score %",
            "Updated Mania Score %",
            "Updated Psychosis Score %",
        ] if c in trend_df.columns]

        st.line_chart(
            trend_df[["DateLabel"] + chart_cols].set_index("DateLabel")
        )
    else:
        st.info("No daily trend data available.")

    st.markdown("### Personal baseline")
    if not daily_model_data.empty:
        latest_daily = daily_model_data.iloc[-1]
        b1, b2, b3, b4 = st.columns(4)

        with b1:
            st.metric(
                "Depression vs baseline",
                f"{to_float(latest_daily.get('Depression Baseline Difference %', 0.0)):+.1f} pp"
            )
        with b2:
            st.metric(
                "Mania vs baseline",
                f"{to_float(latest_daily.get('Mania Baseline Difference %', 0.0)):+.1f} pp"
            )
        with b3:
            st.metric(
                "Psychosis vs baseline",
                f"{to_float(latest_daily.get('Psychosis Baseline Difference %', 0.0)):+.1f} pp"
            )
        with b4:
            st.metric(
                "Mixed vs baseline",
                f"{to_float(latest_daily.get('Mixed Baseline Difference %', 0.0)):+.1f} pp"
            )
    else:
        st.info("No personal baseline data available.")

    st.markdown("### Flags overview")
    if not daily_model_data.empty:
        latest_daily = daily_model_data.iloc[-1]
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Concerning flags", to_int(latest_daily.get("Concerning Situation Flags", 0)))
        with m2:
            st.metric("Depression flags", to_int(latest_daily.get("Depression Flags", 0)))
        with m3:
            st.metric("Mania flags", to_int(latest_daily.get("Mania Flags", 0)))
        with m4:
            st.metric("Psychosis flags", to_int(latest_daily.get("Psychosis Flags", 0)))
    else:
        st.info("No flag overview available.")

    st.markdown("### Recent activity")
    a1, a2, a3, a4 = st.columns(4)

    latest_form_time = form_data["Timestamp"].max() if not form_data.empty and "Timestamp" in form_data.columns else None
    latest_updated_time = updated_daily_data["Timestamp"].max() if not updated_daily_data.empty and "Timestamp" in updated_daily_data.columns else None
    latest_snapshot_time = quick_form_data["Timestamp"].max() if not quick_form_data.empty and "Timestamp" in quick_form_data.columns else None
    days_tracked = len(daily_model_data) if not daily_model_data.empty else 0

    with a1:
        st.metric("Latest legacy form", latest_form_time.strftime("%Y-%m-%d %H:%M") if latest_form_time is not None else "N/A")
    with a2:
        st.metric("Latest updated daily", latest_updated_time.strftime("%Y-%m-%d %H:%M") if latest_updated_time is not None else "N/A")
    with a3:
        st.metric("Latest snapshot", latest_snapshot_time.strftime("%Y-%m-%d %H:%M") if latest_snapshot_time is not None else "N/A")
    with a4:
        st.metric("Days tracked", days_tracked)


def render_warnings_page(
    daily_model_summary,
    snapshot_model_summary,
    latest_form_signals,
    latest_form_findings,
    latest_updated_daily_signals,
    latest_updated_daily_findings,
    latest_snapshot_signals,
    latest_snapshot_findings,
    daily_model_findings,
    snapshot_model_findings,
    alerts,
    today_summary,
):
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
    left, mid, right = st.columns(3)

    with left:
        render_two_column_flag_box("Legacy daily form — warning signals", latest_form_signals, tone="warning")
        render_two_column_flag_box("Legacy daily form — concerning findings", latest_form_findings, tone="error")

    with mid:
        render_two_column_flag_box("Updated daily form — warning signals", latest_updated_daily_signals, tone="warning")
        render_two_column_flag_box("Updated daily form / model — concerning findings", latest_updated_daily_findings + daily_model_findings, tone="error")

    with right:
        render_two_column_flag_box("Snapshot questionnaire — warning signals", latest_snapshot_signals, tone="warning")
        render_two_column_flag_box("Snapshot questionnaire / model — concerning findings", latest_snapshot_findings + snapshot_model_findings, tone="error")


def render_daily_model_page(form_data, updated_daily_data):
    st.subheader("Daily Model")
    st.caption("Calculated from Form Responses plus Updated Daily Bipolar Form with configurable parameters. Scores are shown as percentages.")

    with st.expander("Daily model settings"):
        render_settings_form("daily_settings", DAILY_SETTINGS_UI, columns_per_row=3)

    daily_model_data, daily_model_summary = build_daily_model_from_form(
        form_data,
        st.session_state["daily_settings"],
        updated_daily_data,
    )

    if daily_model_data.empty:
        st.info("No daily model data available.")
        return

    render_summary_cards(daily_model_summary, detailed=True)
    render_chart_group(daily_model_data, "Date", "DateLabel", DAILY_CHARTS)

    default_daily_cols = [
        c for c in [
            "Date",
            "Depression Score %",
            "Updated Depression Score %",
            "5-Day Average (Depression %)",
            "Depression Baseline %",
            "Depression Baseline Difference %",
            "Depression Baseline Z",
            "Mania Score %",
            "Updated Mania Score %",
            "5-Day Average (Mania %)",
            "Mania Baseline %",
            "Mania Baseline Difference %",
            "Mania Baseline Z",
            "Psychosis Score %",
            "Updated Psychosis Score %",
            "5-Day Average (Psychosis %)",
            "Psychosis Baseline %",
            "Psychosis Baseline Difference %",
            "Psychosis Baseline Z",
            "Mixed Score %",
            "5-Day Average (Mixed %)",
            "Mixed Baseline %",
            "Mixed Baseline Difference %",
            "Mixed Baseline Z",
            "Updated Sleep Quality %",
            "Updated Work Functioning Impact %",
            "Updated Daily Functioning Impact %",
            "Concerning Situation Flags",
            "Sleeping Pills Flag",
            "Depression Flags",
            "Mania Flags",
            "Mixed Flags",
            "Psychosis Flags",
        ]
        if c in daily_model_data.columns
    ]

    render_dataframe_picker(
        "Daily model data",
        daily_model_data,
        default_daily_cols,
        "daily_model_columns",
    )


def render_snapshot_model_page(quick_form_data):
    st.subheader("Snapshot Model")
    st.caption("Calculated from Quick Form Responses. Symptom scoring converts No/Somewhat/Yes from 0/1/2 into 0/50/100%.")

    with st.expander("Snapshot model settings"):
        render_settings_form("snapshot_settings", SNAPSHOT_SETTINGS_UI, columns_per_row=3)

    snapshot_model_summary, snapshot_model_data = build_snapshot_model_from_quick_form(
        quick_form_data,
        st.session_state["snapshot_settings"],
    )

    if snapshot_model_summary is None or snapshot_model_data.empty:
        st.info("No snapshot model data available.")
        return

    render_summary_cards(snapshot_model_summary, detailed=False)
    render_chart_group(snapshot_model_data, "FilterDate", "TimeLabel", SNAPSHOT_CHARTS)

    preview_cols = [
        c for c in [
            "Timestamp",
            "Depression Score %",
            "Depression Flags",
            "Mania Score %",
            "Psychosis Score %",
            "Mixed Score %",
            "10-Response Average (Depression %)",
            "10-Response Average (Mania %)",
            "10-Response Average (Psychosis %)",
            "10-Response Average (Mixed %)",
            "Deviation From 10-Response Average (Depression %)",
            "Deviation From 10-Response Average (Mania %)",
            "Deviation From 10-Response Average (Psychosis %)",
            "Deviation From 10-Response Average (Mixed %)",
        ]
        if c in snapshot_model_data.columns
    ]

    render_dataframe_picker(
        "Snapshot model data",
        snapshot_model_data,
        preview_cols,
        "snapshot_model_columns",
    )


def render_form_data_page(form_data):
    st.subheader("Form Data")
    st.caption("Imported directly from Form Responses.")

    default_form_cols = [
        c for c in [
            "Timestamp",
            "Date",
            "Mood Score",
            "Sleep (hours)",
            "Sleep quality",
            "Energy",
            "Mental speed",
            "Impulsivity",
            "Motivation",
            "Irritability",
            "Agitation",
            "Unusual perceptions",
            "Suspiciousness",
            "Certainty and belief in unusual ideas or things others don't believe",
            "Took sleeping medication?",
        ]
        if c in form_data.columns
    ]

    render_dataframe_picker("Form Data", form_data, default_form_cols, "form_data_columns")


def render_updated_daily_data_page(updated_daily_data):
    st.subheader("Updated Daily Data")
    st.caption("Imported directly from Updated Daily Bipolar Form. 1–5 symptom/function scales are blended into the daily model.")

    default_cols = [
        c for c in [
            "Timestamp",
            "Date",
            "Updated Daily [Sleep hours]",
            "Updated Daily [Sleep quality]",
            "Updated Daily [Work functioning]",
            "Updated Daily [Daily functioning]",
            "Updated Daily [Low mood]",
            "Updated Daily [Low energy]",
            "Updated Daily [Low motivation]",
            "Updated Daily [Low interest]",
            "Updated Daily [Withdrawal]",
            "Updated Daily [Self-harm ideation]",
            "Updated Daily [Elevated mood]",
            "Updated Daily [High energy]",
            "Updated Daily [Agitation]",
            "Updated Daily [Racing thoughts]",
            "Updated Daily [Irritability]",
            "Updated Daily [Goal-directed activity]",
            "Updated Daily [Heard or saw things]",
            "Updated Daily [Suspiciousness]",
            "Updated Daily [Trouble trusting perceptions]",
            "Updated Daily [Belief certainty]",
            "Updated Daily [Psychosis distress]",
            "Took sleeping medication?",
            SIG_UP_NOW,
            SIG_DOWN_NOW,
            SIG_MIXED_NOW,
        ]
        if c in updated_daily_data.columns
    ]

    render_dataframe_picker("Updated Daily Data", updated_daily_data, default_cols, "updated_daily_data_columns")


def render_snapshot_data_page(quick_form_data):
    st.subheader("Snapshot Data")
    st.caption("Imported directly from Quick Form Responses. Raw symptom flags are also converted to percentages.")

    default_snapshot_cols = [
        c for c in [
            "Timestamp",
            "Symptoms: [Very low or depressed mood]",
            "Symptoms: [Very low or depressed mood] Percent",
            "Symptoms: [Somewhat low or depressed mood]",
            "Symptoms: [Somewhat low or depressed mood] Percent",
            "Symptoms: [Very high or elevated mood]",
            "Symptoms: [Very high or elevated mood] Percent",
            "Symptoms: [Paranoia or suspicion]",
            "Symptoms: [Paranoia or suspicion] Percent",
            "Depression Flags",
        ]
        if c in quick_form_data.columns
    ]

    render_dataframe_picker("Snapshot Data", quick_form_data, default_snapshot_cols, "snapshot_data_columns")


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

form_df = load_sheet(FORM_TAB)
quick_form_df = load_sheet(QUICK_FORM_TAB)
updated_daily_df = load_sheet(UPDATED_DAILY_TAB)

form_data = prepare_form_raw(form_df)
quick_form_data = prepare_quick_form_raw(quick_form_df)
updated_daily_data = prepare_updated_daily_raw(updated_daily_df)

daily_model_data, daily_model_summary = build_daily_model_from_form(
    form_data,
    st.session_state["daily_settings"],
    updated_daily_data,
)

snapshot_model_summary, snapshot_model_data = build_snapshot_model_from_quick_form(
    quick_form_data,
    st.session_state["snapshot_settings"],
)

latest_form_signals, latest_form_findings = get_latest_form_warning_items(form_data)
latest_updated_daily_signals, latest_updated_daily_findings = get_latest_updated_daily_warning_items(updated_daily_data)
latest_snapshot_signals, latest_snapshot_findings = get_latest_quick_form_warning_items(quick_form_data)

daily_model_findings, snapshot_model_findings = get_model_concerning_findings(
    daily_model_summary,
    snapshot_model_summary,
    daily_model_data,
    snapshot_model_data,
)

alerts = build_alerts(
    daily_model_data=daily_model_data,
    daily_summary=daily_model_summary,
    snapshot_summary=snapshot_model_summary,
    settings=st.session_state["daily_settings"],
    snapshot_model_data=snapshot_model_data,
)

today_summary = build_today_summary(
    daily_summary=daily_model_summary,
    alerts=alerts,
    daily_model_data=daily_model_data,
)

tabs = st.tabs([
    "Dashboard",
    "Warnings",
    "Daily Model",
    "Snapshot Model",
    "Form Data",
    "Updated Daily Data",
    "Snapshot Data",
])

with tabs[0]:
    render_dashboard_page(
        form_data=form_data,
        updated_daily_data=updated_daily_data,
        quick_form_data=quick_form_data,
        daily_model_data=daily_model_data,
        daily_model_summary=daily_model_summary,
        snapshot_model_summary=snapshot_model_summary,
        latest_form_signals=latest_form_signals,
        latest_form_findings=latest_form_findings,
        latest_updated_daily_signals=latest_updated_daily_signals,
        latest_updated_daily_findings=latest_updated_daily_findings,
        latest_snapshot_signals=latest_snapshot_signals,
        latest_snapshot_findings=latest_snapshot_findings,
        daily_model_findings=daily_model_findings,
        snapshot_model_findings=snapshot_model_findings,
        alerts=alerts,
        today_summary=today_summary,
    )

with tabs[1]:
    render_warnings_page(
        daily_model_summary=daily_model_summary,
        snapshot_model_summary=snapshot_model_summary,
        latest_form_signals=latest_form_signals,
        latest_form_findings=latest_form_findings,
        latest_updated_daily_signals=latest_updated_daily_signals,
        latest_updated_daily_findings=latest_updated_daily_findings,
        latest_snapshot_signals=latest_snapshot_signals,
        latest_snapshot_findings=latest_snapshot_findings,
        daily_model_findings=daily_model_findings,
        snapshot_model_findings=snapshot_model_findings,
        alerts=alerts,
        today_summary=today_summary,
    )

with tabs[2]:
    render_daily_model_page(form_data, updated_daily_data)

with tabs[3]:
    render_snapshot_model_page(quick_form_data)

with tabs[4]:
    render_form_data_page(form_data)

with tabs[5]:
    render_updated_daily_data_page(updated_daily_data)

with tabs[6]:
    render_snapshot_data_page(quick_form_data)
