# =========================================================
# WELLBEING DASHBOARD
# Reads from:
# - Form Responses
# - Quick Form Responses
# - Model (used for reference / flag breakdown support)
# - Quick Model (reference only)
# =========================================================

import streamlit as st
import pandas as pd
import gspread


# =========================
# Authentication
# =========================
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
    elif not st.session_state["authenticated"]:
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


# =========================
# Page Config
# =========================
st.set_page_config(page_title="Wellbeing Dashboard", layout="wide")


# =========================
# Sheets Config
# =========================
SHEET_NAME = "Bipolar Dashboard"

FORM_TAB = "Form Responses"
QUICK_FORM_TAB = "Quick Form Responses"
MODEL_TAB = "Model"
QUICK_MODEL_TAB = "Quick Model"


# =========================
# Column Normalization
# =========================
COLUMN_ALIASES = {
    "Signals and indicators [Avoided normal responsiblities]":
        "Signals and indicators [Avoided normal responsibilities]",
    "Certainty and  belief in unusual ideas or things others don't believe":
        "Certainty and belief in unusual ideas or things others don't believe",
    "Weekly Check-In  Flags":
        "Weekly Check-In Flags",
    "Column 1": "Date",
}

RISK_VALUE_MAP = {"LOW": 0, "MED": 1, "HIGH": 2}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.rename(columns=COLUMN_ALIASES)


# =========================
# Core Columns
# =========================
COL_MOOD = "Mood Score"
COL_SLEEP_HOURS = "Sleep (hours)"
COL_SLEEP_QUALITY = "Sleep quality"
COL_ENERGY = "Energy"
COL_MENTAL_SPEED = "Mental speed"
COL_IMPULSIVITY = "Impulsivity"
COL_MOTIVATION = "Motivation"
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

# Model tab column groups
MODEL_SCORE_COLS = {
    "Depression": "Depression Score",
    "Mania": "Mania Score",
    "Psychosis": "Psychosis Score",
    "Mixed": "Mixed Score",
}

MODEL_AVG_COLS = {
    "Depression": "3-Day Average (Depression)",
    "Mania": "3-Day Average (Mania)",
    "Psychosis": "3-Day Average (Psychosis)",
    "Mixed": "3-Day Average (Mixed)",
}

MODEL_FLAG_COLS = {
    "Depression": "Depression Flags",
    "Mania": "Mania Flags",
    "Psychosis": "Psychosis Flags",
    "Mixed": "Mixed Flags",
}

# Snapshot raw symptom groups
SNAPSHOT_DEPRESSION_COLS = [
    "Symptoms: [Very low or depressed mood]",
    "Symptoms: [Somewhat low or depressed mood]",
    "Symptoms: [Social or emotional withdrawal]",
    "Symptoms: [Feeling slowed down]",
    "Symptoms: [Difficulty with self-care]",
]

SNAPSHOT_MANIA_COLS = [
    "Symptoms: [Very high or elevated mood]",
    "Symptoms: [Somewhat high or elevated mood]",
    "Symptoms: [Agitation or restlessness]",
    "Symptoms: [Racing thoughts]",
    "Symptoms: [Driven to activity]",
]

SNAPSHOT_PSYCHOSIS_COLS = [
    "Symptoms: [Hearing or seeing things that aren't there]",
    "Symptoms: [Paranoia or suspicion]",
    "Symptoms: [Firm belief in things others would not agree with]",
]


# =========================
# Default Settings
# =========================
DEFAULT_DAILY_SETTINGS = {
    # depression drivers
    "dep_low_mood_weight": 4.0,
    "dep_low_sleep_quality_weight": 1.0,
    "dep_low_energy_weight": 1.0,
    "dep_low_mental_speed_weight": 1.0,
    "dep_low_motivation_weight": 1.0,
    "dep_flag_weight": 1.0,

    # mania drivers
    "mania_high_mood_weight": 4.0,
    "mania_low_sleep_quality_weight": 1.0,
    "mania_high_energy_weight": 1.0,
    "mania_high_mental_speed_weight": 1.0,
    "mania_high_motivation_weight": 1.0,
    "mania_flag_weight": 1.0,

    # psychosis drivers
    "psych_unusual_weight": 1.0,
    "psych_suspicious_weight": 1.0,
    "psych_certainty_weight": 3.0,
    "psych_flag_weight": 1.0,

    # mixed
    "mixed_dep_weight": 0.4,
    "mixed_mania_weight": 0.4,
    "mixed_psych_weight": 0.2,
    "mixed_low_sleep_quality_weight": 0.5,

    # thresholds
    "medium_threshold_pct": 33.0,
    "high_threshold_pct": 66.0,
    "trend_threshold_pct": 8.0,
}

DEFAULT_SNAPSHOT_SETTINGS = {
    "dep_very_low_mood": 4.0,
    "dep_somewhat_low_mood": 2.0,
    "dep_withdrawal": 1.0,
    "dep_slowed_down": 1.0,
    "dep_self_care": 1.0,

    "mania_very_high_mood": 4.0,
    "mania_somewhat_high_mood": 2.0,
    "mania_agitation": 1.0,
    "mania_racing": 1.0,
    "mania_driven": 1.0,

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


# =========================
# Session State Init
# =========================
if "daily_settings" not in st.session_state:
    st.session_state["daily_settings"] = DEFAULT_DAILY_SETTINGS.copy()

if "snapshot_settings" not in st.session_state:
    st.session_state["snapshot_settings"] = DEFAULT_SNAPSHOT_SETTINGS.copy()


# =========================
# Google Sheets Access
# =========================
@st.cache_resource
def get_gspread_client():
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))


@st.cache_resource
def get_workbook():
    return get_gspread_client().open(SHEET_NAME)


# =========================
# Load Sheet
# =========================
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


# =========================
# Helpers
# =========================
def convert_numeric(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    working = df.copy()

    for col in working.columns:
        if col in ["Timestamp", "Date", "Date (int)"]:
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


def normalize_0_10_to_pct(series: pd.Series, inverse: bool = False) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if inverse:
        return ((10 - s).clip(lower=0, upper=10) / 10.0) * 100.0
    return (s.clip(lower=0, upper=10) / 10.0) * 100.0


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


def status_color(level: str) -> str:
    if level == "High":
        return "#d32f2f"
    if level == "Medium":
        return "#f9a825"
    return "#2e7d32"


def confidence_color(confidence: str) -> str:
    if confidence == "High":
        return "#2e7d32"
    if confidence == "Medium":
        return "#f9a825"
    return "#757575"


def render_status_card(title: str, score_pct: float, level: str, trend: str, confidence: str):
    color = status_color(level)
    conf_color = confidence_color(confidence)

    st.markdown(
        f"""
        <div style="
            border: 1px solid #ddd;
            border-left: 8px solid {color};
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            background-color: #fafafa;
            min-height: 170px;
        ">
            <div style="font-size: 22px; font-weight: 700; margin-bottom: 6px;">{title}</div>
            <div style="font-size: 16px; margin-bottom: 6px;">
                <strong>Current:</strong> {level} ({score_pct:.1f}%)
            </div>
            <div style="font-size: 16px; margin-bottom: 6px;">
                <strong>Trend:</strong> {trend}
            </div>
            <div style="font-size: 16px;">
                <strong>Confidence:</strong>
                <span style="
                    display: inline-block;
                    padding: 2px 8px;
                    border-radius: 999px;
                    background-color: {conf_color};
                    color: white;
                    font-weight: 600;
                ">
                    {confidence}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_daily_card(title: str, data: dict):
    color = status_color(data["level"])
    conf_color = confidence_color(data["confidence"])
    reasons_html = "<br>".join([f"• {r}" for r in data["reasons"]]) if data["reasons"] else "No strong drivers"

    st.markdown(
        f"""
        <div style="
            border: 1px solid #ddd;
            border-left: 8px solid {color};
            border-radius: 12px;
            padding: 16px;
            background-color: #fafafa;
            margin-bottom: 12px;
            min-height: 220px;
        ">
            <div style="font-size: 22px; font-weight: 700; margin-bottom: 6px;">{title}</div>
            <div style="font-size: 16px; margin-bottom: 6px;">
                <strong>Current state:</strong> {data['level']} ({data['score_pct']:.1f}%)
            </div>
            <div style="font-size: 16px; margin-bottom: 6px;"><strong>Trend:</strong> {data['trend']}</div>
            <div style="font-size: 16px; margin-bottom: 8px;">
                <strong>Confidence:</strong>
                <span style="
                    background-color:{conf_color};
                    color:white;
                    padding:2px 8px;
                    border-radius:999px;
                    font-weight:600;
                ">
                    {data['confidence']}
                </span>
            </div>
            <div style="font-size: 16px;">
                <strong>Reasons:</strong><br>
                {reasons_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_signal_box(title: str, items: list[str], tone: str = "info"):
    if tone == "error":
        bg = "#fdecea"
        border = "#d32f2f"
    elif tone == "warning":
        bg = "#fff8e1"
        border = "#f9a825"
    else:
        bg = "#eef6ff"
        border = "#1976d2"

    content = "<br>".join([f"• {i}" for i in items]) if items else "• None"

    st.markdown(
        f"""
        <div style="
            border: 1px solid {border};
            border-left: 8px solid {border};
            border-radius: 12px;
            padding: 14px;
            background-color: {bg};
            margin-bottom: 12px;
        ">
            <div style="font-size: 18px; font-weight: 700; margin-bottom: 6px;">{title}</div>
            <div style="font-size: 15px;">{content}</div>
        </div>
        """,
        unsafe_allow_html=True,
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


# =========================
# Prep Functions
# =========================
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


def prepare_model_reference(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    working = convert_numeric(df.copy())
    working = drop_blank_tail_rows(
        working,
        ["Timestamp", "Date", "Depression Score", "Mania Score", "Psychosis Score", "Mixed Score"],
    )

    if "Timestamp" in working.columns:
        working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")

    if "Date" in working.columns:
        working["Date"] = pd.to_datetime(working["Date"], errors="coerce")
    elif "Timestamp" in working.columns:
        working["Date"] = pd.to_datetime(working["Timestamp"], errors="coerce").dt.floor("D")

    working = working.sort_values("Date").reset_index(drop=True)
    working["DateLabel"] = pd.to_datetime(working["Date"]).dt.strftime("%Y-%m-%d")

    for name, col in MODEL_SCORE_COLS.items():
        if col in working.columns:
            working[f"{name} Score % (Sheet)"] = pd.to_numeric(working[col], errors="coerce") * 100.0

    for name, col in MODEL_AVG_COLS.items():
        if col in working.columns:
            working[f"{name} Avg % (Sheet)"] = pd.to_numeric(working[col], errors="coerce") * 100.0

    return working


def prepare_quick_model_reference(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    working = convert_numeric(df.copy())
    working = drop_blank_tail_rows(
        working,
        ["Timestamp", "Depression Score", "Mania Score", "Psychosis Score", "Mixed Score"],
    )

    if "Timestamp" in working.columns:
        working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")

    working = working.sort_values("Timestamp").reset_index(drop=True)
    working["FilterDate"] = working["Timestamp"].dt.date
    working["TimeLabel"] = working["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    return working


# =========================
# Daily Model (configurable, from Form Responses)
# =========================
def build_daily_model_from_form(form_df: pd.DataFrame, settings: dict):
    if form_df.empty or "Timestamp" not in form_df.columns:
        return pd.DataFrame(), None

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

    daily = daily_scores.merge(daily_flags, on="Date", how="outer").sort_values("Date").reset_index(drop=True)
    daily["DateLabel"] = pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")

    # raw contributors mapped to percentages
    daily["Depression - Low Mood Score"] = normalize_0_10_to_pct(daily.get(COL_MOOD, 0), inverse=True)
    daily["Depression - Low Sleep Quality"] = normalize_0_10_to_pct(daily.get(COL_SLEEP_QUALITY, 0), inverse=True)
    daily["Depression - Low Energy"] = normalize_0_10_to_pct(daily.get(COL_ENERGY, 0), inverse=True)
    daily["Depression - Low Mental Speed"] = normalize_0_10_to_pct(daily.get(COL_MENTAL_SPEED, 0), inverse=True)
    daily["Depression - Low Motivation"] = normalize_0_10_to_pct(daily.get(COL_MOTIVATION, 0), inverse=True)

    depression_flag_components = [
        c for c in [SIG_WITHDRAW, SIG_AVOID_RESPONSIBILITIES, SIG_DOWN_NOW, SIG_DOWN_COMING]
        if c in daily.columns
    ]
    if depression_flag_components:
        daily["Depression - Flags"] = normalize_flag_count_to_pct(
            daily[depression_flag_components].sum(axis=1), max_flags=len(depression_flag_components)
        )
    else:
        daily["Depression - Flags"] = 0.0

    daily["Mania - High Mood Score"] = normalize_0_10_to_pct(daily.get(COL_MOOD, 0), inverse=False)
    daily["Mania - Low Sleep Quality"] = normalize_0_10_to_pct(daily.get(COL_SLEEP_QUALITY, 0), inverse=True)
    daily["Mania - High Energy"] = normalize_0_10_to_pct(daily.get(COL_ENERGY, 0), inverse=False)
    daily["Mania - High Mental Speed"] = normalize_0_10_to_pct(daily.get(COL_MENTAL_SPEED, 0), inverse=False)
    daily["Mania - High Motivation"] = normalize_0_10_to_pct(daily.get(COL_MOTIVATION, 0), inverse=False)

    mania_flag_components = [
        c for c in [SIG_LESS_SLEEP, SIG_MORE_ACTIVITY, SIG_UP_NOW, SIG_UP_COMING]
        if c in daily.columns
    ]
    if mania_flag_components:
        daily["Mania - Flags"] = normalize_flag_count_to_pct(
            daily[mania_flag_components].sum(axis=1), max_flags=len(mania_flag_components)
        )
    else:
        daily["Mania - Flags"] = 0.0

    daily["Psychosis - Unusual perceptions"] = normalize_0_10_to_pct(daily.get(COL_UNUSUAL, 0), inverse=False)
    daily["Psychosis - Suspiciousness"] = normalize_0_10_to_pct(daily.get(COL_SUSPICIOUS, 0), inverse=False)
    daily["Psychosis - Certainty"] = normalize_0_10_to_pct(daily.get(COL_CERTAINTY, 0), inverse=False)

    psych_flag_components = [
        c for c in [SIG_HEARD_SAW, SIG_WATCHED, SIG_SPECIAL_MEANING, SIG_TROUBLE_TRUSTING]
        if c in daily.columns
    ]
    if psych_flag_components:
        daily["Psychosis - Flags"] = normalize_flag_count_to_pct(
            daily[psych_flag_components].sum(axis=1), max_flags=len(psych_flag_components)
        )
    else:
        daily["Psychosis - Flags"] = 0.0

    # weighted scores
    daily["Depression Score %"] = weighted_average_percent(
        daily,
        [
            ("Depression - Low Mood Score", float(settings["dep_low_mood_weight"])),
            ("Depression - Low Sleep Quality", float(settings["dep_low_sleep_quality_weight"])),
            ("Depression - Low Energy", float(settings["dep_low_energy_weight"])),
            ("Depression - Low Mental Speed", float(settings["dep_low_mental_speed_weight"])),
            ("Depression - Low Motivation", float(settings["dep_low_motivation_weight"])),
            ("Depression - Flags", float(settings["dep_flag_weight"])),
        ],
    )

    daily["Mania Score %"] = weighted_average_percent(
        daily,
        [
            ("Mania - High Mood Score", float(settings["mania_high_mood_weight"])),
            ("Mania - Low Sleep Quality", float(settings["mania_low_sleep_quality_weight"])),
            ("Mania - High Energy", float(settings["mania_high_energy_weight"])),
            ("Mania - High Mental Speed", float(settings["mania_high_mental_speed_weight"])),
            ("Mania - High Motivation", float(settings["mania_high_motivation_weight"])),
            ("Mania - Flags", float(settings["mania_flag_weight"])),
        ],
    )

    daily["Psychosis Score %"] = weighted_average_percent(
        daily,
        [
            ("Psychosis - Unusual perceptions", float(settings["psych_unusual_weight"])),
            ("Psychosis - Suspiciousness", float(settings["psych_suspicious_weight"])),
            ("Psychosis - Certainty", float(settings["psych_certainty_weight"])),
            ("Psychosis - Flags", float(settings["psych_flag_weight"])),
        ],
    )

    mixed_weight_total = (
        float(settings["mixed_dep_weight"])
        + float(settings["mixed_mania_weight"])
        + float(settings["mixed_psych_weight"])
        + float(settings["mixed_low_sleep_quality_weight"])
    )
    if mixed_weight_total == 0:
        mixed_weight_total = 1.0

    daily["Mixed Score %"] = (
        daily["Depression Score %"] * float(settings["mixed_dep_weight"])
        + daily["Mania Score %"] * float(settings["mixed_mania_weight"])
        + daily["Psychosis Score %"] * float(settings["mixed_psych_weight"])
        + daily["Depression - Low Sleep Quality"] * float(settings["mixed_low_sleep_quality_weight"])
    ) / mixed_weight_total

    # averages and deviations
    for name in ["Depression", "Mania", "Psychosis", "Mixed"]:
        score_col = f"{name} Score %"
        avg_col = f"3-Day Average ({name} %)"
        dev_col = f"{name} Deviation %"
        daily[avg_col] = daily[score_col].rolling(window=3, min_periods=1).mean()
        daily[dev_col] = daily[score_col] - daily[avg_col]

    # flag breakdown for charts / metrics
    daily["Depression Flags"] = daily[depression_flag_components].sum(axis=1) if depression_flag_components else 0
    daily["Mania Flags"] = daily[mania_flag_components].sum(axis=1) if mania_flag_components else 0
    daily["Psychosis Flags"] = daily[psych_flag_components].sum(axis=1) if psych_flag_components else 0

    mixed_flag_components = [
        c for c in [SIG_MIXED_NOW, SIG_MIXED_COMING, SIG_WITHDRAW, SIG_LESS_SLEEP, SIG_MORE_ACTIVITY]
        if c in daily.columns
    ]
    daily["Mixed Flags"] = daily[mixed_flag_components].sum(axis=1) if mixed_flag_components else 0

    daily["Concerning Situation Flags"] = daily[
        [c for c in [SIG_NOT_MYSELF, SIG_MISSED_MEDS, SIG_ROUTINE, SIG_STRESS_PSYCH, SIG_STRESS_PHYS] if c in daily.columns]
    ].sum(axis=1) if any(c in daily.columns for c in [SIG_NOT_MYSELF, SIG_MISSED_MEDS, SIG_ROUTINE, SIG_STRESS_PSYCH, SIG_STRESS_PHYS]) else 0

    # self-report flags
    daily["Self-Reported Depression"] = daily[[c for c in [SIG_DOWN_NOW, SIG_DOWN_COMING] if c in daily.columns]].sum(axis=1) if any(c in daily.columns for c in [SIG_DOWN_NOW, SIG_DOWN_COMING]) else 0
    daily["Self-Reported Mania"] = daily[[c for c in [SIG_UP_NOW, SIG_UP_COMING] if c in daily.columns]].sum(axis=1) if any(c in daily.columns for c in [SIG_UP_NOW, SIG_UP_COMING]) else 0
    daily["Self-Reported Mixed"] = daily[[c for c in [SIG_MIXED_NOW, SIG_MIXED_COMING] if c in daily.columns]].sum(axis=1) if any(c in daily.columns for c in [SIG_MIXED_NOW, SIG_MIXED_COMING]) else 0

    # summary
    latest = daily.iloc[-1]
    last5 = daily.tail(5)

    medium_pct = float(settings["medium_threshold_pct"])
    high_pct = float(settings["high_threshold_pct"])
    trend_threshold_pct = float(settings["trend_threshold_pct"])

    summary = {}
    reason_map = {
        "Depression": [
            "Depression - Low Mood Score",
            "Depression - Low Sleep Quality",
            "Depression - Low Energy",
            "Depression - Low Mental Speed",
            "Depression - Low Motivation",
            "Depression - Flags",
        ],
        "Mania": [
            "Mania - High Mood Score",
            "Mania - Low Sleep Quality",
            "Mania - High Energy",
            "Mania - High Mental Speed",
            "Mania - High Motivation",
            "Mania - Flags",
        ],
        "Psychosis": [
            "Psychosis - Unusual perceptions",
            "Psychosis - Suspiciousness",
            "Psychosis - Certainty",
            "Psychosis - Flags",
        ],
        "Mixed": [
            "Depression Score %",
            "Mania Score %",
            "Psychosis Score %",
            "Depression - Low Sleep Quality",
        ],
    }

    for name in ["Depression", "Mania", "Psychosis", "Mixed"]:
        score_pct = to_float(latest[f"{name} Score %"], 0.0)
        dev_pct = to_float(latest[f"{name} Deviation %"], 0.0)
        level = level_from_percent(score_pct, medium_pct, high_pct)
        trend = trend_from_deviation_pct(dev_pct, trend_threshold_pct)
        confidence = confidence_from_count(len(last5), trend, level)

        pairs = []
        for c in reason_map[name]:
            if c in latest.index:
                pairs.append((c, to_float(latest[c], 0.0)))
        pairs = sorted(pairs, key=lambda x: x[1], reverse=True)
        reasons = [c.replace("Depression - ", "").replace("Mania - ", "").replace("Psychosis - ", "") for c, v in pairs if v > 0][:3]

        summary[name] = {
            "score_pct": score_pct,
            "level": level,
            "trend": trend,
            "confidence": confidence,
            "reasons": reasons,
        }

    return daily, summary


# =========================
# Snapshot Model (configurable)
# =========================
def build_snapshot_model_from_quick_form(quick_form_df: pd.DataFrame, settings: dict):
    if quick_form_df.empty or "Timestamp" not in quick_form_df.columns:
        return None, pd.DataFrame()

    working = quick_form_df.copy()
    working = drop_blank_tail_rows(working, ["Timestamp"])
    working["Timestamp"] = pd.to_datetime(working["Timestamp"], errors="coerce")
    working = working.sort_values("Timestamp").reset_index(drop=True)

    depression_weights = [
        ("Symptoms: [Very low or depressed mood]", float(settings["dep_very_low_mood"])),
        ("Symptoms: [Somewhat low or depressed mood]", float(settings["dep_somewhat_low_mood"])),
        ("Symptoms: [Social or emotional withdrawal]", float(settings["dep_withdrawal"])),
        ("Symptoms: [Feeling slowed down]", float(settings["dep_slowed_down"])),
        ("Symptoms: [Difficulty with self-care]", float(settings["dep_self_care"])),
    ]

    mania_weights = [
        ("Symptoms: [Very high or elevated mood]", float(settings["mania_very_high_mood"])),
        ("Symptoms: [Somewhat high or elevated mood]", float(settings["mania_somewhat_high_mood"])),
        ("Symptoms: [Agitation or restlessness]", float(settings["mania_agitation"])),
        ("Symptoms: [Racing thoughts]", float(settings["mania_racing"])),
        ("Symptoms: [Driven to activity]", float(settings["mania_driven"])),
    ]

    psychosis_weights = [
        ("Symptoms: [Hearing or seeing things that aren't there]", float(settings["psych_hearing_seeing"])),
        ("Symptoms: [Paranoia or suspicion]", float(settings["psych_paranoia"])),
        ("Symptoms: [Firm belief in things others would not agree with]", float(settings["psych_beliefs"])),
    ]

    working["Depression Score %"] = weighted_average_percent_from_responses(working, depression_weights)
    working["Mania Score %"] = weighted_average_percent_from_responses(working, mania_weights)
    working["Psychosis Score %"] = weighted_average_percent_from_responses(working, psychosis_weights)

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

    for name in ["Depression", "Mania", "Psychosis", "Mixed"]:
        score_col = f"{name} Score %"
        avg_col = f"3-Response Average ({name} %)"
        dev_col = f"Deviation From 3-Response Average ({name} %)"
        working[avg_col] = working[score_col].rolling(window=3, min_periods=1).mean()
        working[dev_col] = working[score_col] - working[avg_col]

    working["FilterDate"] = working["Timestamp"].dt.date
    working["TimeLabel"] = working["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")

    latest = working.iloc[-1]
    last5 = working.tail(5)

    medium_pct = float(settings["medium_threshold_pct"])
    high_pct = float(settings["high_threshold_pct"])
    trend_threshold_pct = float(settings["trend_threshold_pct"])

    summary = {}
    for name in ["Depression", "Mania", "Psychosis", "Mixed"]:
        score_pct = to_float(latest.get(f"{name} Score %", 0.0), 0.0)
        dev_pct = to_float(latest.get(f"Deviation From 3-Response Average ({name} %)", 0.0), 0.0)
        level = level_from_percent(score_pct, medium_pct, high_pct)
        trend = trend_from_deviation_pct(dev_pct, trend_threshold_pct)
        confidence = confidence_from_count(len(last5), trend, level)

        summary[name] = {
            "score_pct": score_pct,
            "level": level,
            "trend": trend,
            "confidence": confidence,
        }

    return summary, working


# =========================
# Warning Helpers
# =========================
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
        (COL_ENERGY, "Energy is elevated"),
        (COL_MENTAL_SPEED, "Mental speed is elevated"),
        (COL_IMPULSIVITY, "Impulsivity is elevated"),
        (COL_MOTIVATION, "Motivation is low"),
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
            elif col in [COL_ENERGY, COL_MENTAL_SPEED, COL_IMPULSIVITY, COL_UNUSUAL, COL_SUSPICIOUS, COL_CERTAINTY] and val >= 6:
                concerning.append(f"{label} ({val:.1f})")

    return flagged, concerning


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
) -> tuple[list[str], list[str]]:
    daily_findings = []
    snapshot_findings = []

    if daily_summary and not daily_model_df.empty:
        for name in ["Depression", "Mania", "Psychosis", "Mixed"]:
            item = daily_summary[name]
            if item["level"] in ["Medium", "High"]:
                daily_findings.append(
                    f"Daily {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}"
                )

        latest = daily_model_df.iloc[-1]
        concerning_flags = to_float(latest.get("Concerning Situation Flags", 0), 0.0)
        if concerning_flags > 0:
            daily_findings.append(f"Concerning situation flags: {int(concerning_flags)}")

    if snapshot_summary:
        for name in ["Depression", "Mania", "Psychosis", "Mixed"]:
            item = snapshot_summary[name]
            if item["level"] in ["Medium", "High"]:
                snapshot_findings.append(
                    f"Snapshot {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}"
                )

    return daily_findings, snapshot_findings


# =========================
# Load Data
# =========================
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
model_sheet_df = load_sheet(MODEL_TAB)
quick_model_sheet_df = load_sheet(QUICK_MODEL_TAB)

form_data = prepare_form_raw(form_df)
quick_form_data = prepare_quick_form_raw(quick_form_df)
model_sheet_data = prepare_model_reference(model_sheet_df)
quick_model_sheet_data = prepare_quick_model_reference(quick_model_sheet_df)

daily_model_data, daily_model_summary = build_daily_model_from_form(
    form_data,
    st.session_state["daily_settings"],
)

snapshot_model_summary, snapshot_model_data = build_snapshot_model_from_quick_form(
    quick_form_df,
    st.session_state["snapshot_settings"],
)

latest_form_signals, latest_form_findings = get_latest_form_warning_items(form_data)
latest_snapshot_signals, latest_snapshot_findings = get_latest_quick_form_warning_items(quick_form_data)
daily_model_findings, snapshot_model_findings = get_model_concerning_findings(
    daily_model_summary,
    snapshot_model_summary,
    daily_model_data,
)


# =========================
# Tabs
# =========================
tab_dashboard, tab_warnings, tab_daily_model, tab_snapshot_model, tab_form_data, tab_snapshot_data = st.tabs([
    "Dashboard",
    "Warnings",
    "Daily Model",
    "Snapshot Model",
    "Form Data",
    "Snapshot Data",
])


# =========================
# Dashboard
# =========================
with tab_dashboard:
    st.subheader("Dashboard")
    st.caption("Daily Model is calculated from Form Responses with adjustable settings. Snapshot Model is calculated from Quick Form Responses with adjustable settings.")

    st.markdown("### Current state")

    st.markdown("#### Daily Model")
    if daily_model_summary:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_daily_card("Depression", daily_model_summary["Depression"])
        with c2:
            render_daily_card("Mania", daily_model_summary["Mania"])
        with c3:
            render_daily_card("Psychosis", daily_model_summary["Psychosis"])
        with c4:
            render_daily_card("Mixed", daily_model_summary["Mixed"])
    else:
        st.info("No daily model summary available.")

    st.markdown("#### Snapshot Model")
    if snapshot_model_summary:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_status_card(
                "Depression",
                snapshot_model_summary["Depression"]["score_pct"],
                snapshot_model_summary["Depression"]["level"],
                snapshot_model_summary["Depression"]["trend"],
                snapshot_model_summary["Depression"]["confidence"],
            )
        with c2:
            render_status_card(
                "Mania",
                snapshot_model_summary["Mania"]["score_pct"],
                snapshot_model_summary["Mania"]["level"],
                snapshot_model_summary["Mania"]["trend"],
                snapshot_model_summary["Mania"]["confidence"],
            )
        with c3:
            render_status_card(
                "Psychosis",
                snapshot_model_summary["Psychosis"]["score_pct"],
                snapshot_model_summary["Psychosis"]["level"],
                snapshot_model_summary["Psychosis"]["trend"],
                snapshot_model_summary["Psychosis"]["confidence"],
            )
        with c4:
            render_status_card(
                "Mixed",
                snapshot_model_summary["Mixed"]["score_pct"],
                snapshot_model_summary["Mixed"]["level"],
                snapshot_model_summary["Mixed"]["trend"],
                snapshot_model_summary["Mixed"]["confidence"],
            )
    else:
        st.info("No snapshot model summary available.")

    st.markdown("### Key warnings")

    warn_left, warn_right = st.columns(2)
    with warn_left:
        render_signal_box(
            "Daily questionnaire / model",
            latest_form_findings + daily_model_findings + latest_form_signals,
            tone="error" if (latest_form_findings or daily_model_findings) else "warning",
        )

    with warn_right:
        render_signal_box(
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

        st.line_chart(
            trend_df[["DateLabel", "Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"]]
            .set_index("DateLabel")
        )
    else:
        st.info("No daily trend data available.")

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
    latest_snapshot_time = quick_form_data["Timestamp"].max() if not quick_form_data.empty and "Timestamp" in quick_form_data.columns else None
    days_tracked = len(daily_model_data) if not daily_model_data.empty else 0

    snapshot_last_7 = 0
    if latest_snapshot_time is not None and not quick_form_data.empty and "Timestamp" in quick_form_data.columns:
        snap_ts = pd.to_datetime(quick_form_data["Timestamp"], errors="coerce").dropna()
        snapshot_last_7 = int((snap_ts >= (latest_snapshot_time - pd.Timedelta(days=7))).sum())

    with a1:
        st.metric("Latest form entry", latest_form_time.strftime("%Y-%m-%d %H:%M") if latest_form_time is not None else "N/A")
    with a2:
        st.metric("Latest snapshot entry", latest_snapshot_time.strftime("%Y-%m-%d %H:%M") if latest_snapshot_time is not None else "N/A")
    with a3:
        st.metric("Days tracked", days_tracked)
    with a4:
        st.metric("Snapshot entries (last 7d)", snapshot_last_7)


# =========================
# Warnings
# =========================
with tab_warnings:
    st.subheader("Warnings")

    st.markdown("### Current State — Daily Model")
    if daily_model_summary:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_daily_card("Depression", daily_model_summary["Depression"])
        with c2:
            render_daily_card("Mania", daily_model_summary["Mania"])
        with c3:
            render_daily_card("Psychosis", daily_model_summary["Psychosis"])
        with c4:
            render_daily_card("Mixed", daily_model_summary["Mixed"])

    st.markdown("### Current State — Snapshot Model")
    if snapshot_model_summary:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_status_card("Depression", snapshot_model_summary["Depression"]["score_pct"], snapshot_model_summary["Depression"]["level"], snapshot_model_summary["Depression"]["trend"], snapshot_model_summary["Depression"]["confidence"])
        with c2:
            render_status_card("Mania", snapshot_model_summary["Mania"]["score_pct"], snapshot_model_summary["Mania"]["level"], snapshot_model_summary["Mania"]["trend"], snapshot_model_summary["Mania"]["confidence"])
        with c3:
            render_status_card("Psychosis", snapshot_model_summary["Psychosis"]["score_pct"], snapshot_model_summary["Psychosis"]["level"], snapshot_model_summary["Psychosis"]["trend"], snapshot_model_summary["Psychosis"]["confidence"])
        with c4:
            render_status_card("Mixed", snapshot_model_summary["Mixed"]["score_pct"], snapshot_model_summary["Mixed"]["level"], snapshot_model_summary["Mixed"]["trend"], snapshot_model_summary["Mixed"]["confidence"])

    st.markdown("### Warning Signals and Concerning Findings")
    left, right = st.columns(2)
    with left:
        render_signal_box("Daily questionnaire — warning signals", latest_form_signals, tone="warning")
        render_signal_box("Daily questionnaire — concerning findings", latest_form_findings + daily_model_findings, tone="error")
    with right:
        render_signal_box("Snapshot questionnaire — warning signals", latest_snapshot_signals, tone="warning")
        render_signal_box("Snapshot questionnaire — concerning findings", latest_snapshot_findings + snapshot_model_findings, tone="error")


# =========================
# Daily Model
# =========================
with tab_daily_model:
    st.subheader("Daily Model")
    st.caption("Calculated from Form Responses with configurable parameters. Scores are shown as percentages.")

    with st.expander("Daily model settings"):
        st.markdown("#### Depression weights")
        d1, d2, d3, d4, d5, d6 = st.columns(6)
        with d1:
            st.session_state["daily_settings"]["dep_low_mood_weight"] = st.number_input("Low mood", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["dep_low_mood_weight"]), step=0.1)
        with d2:
            st.session_state["daily_settings"]["dep_low_sleep_quality_weight"] = st.number_input("Low sleep quality", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["dep_low_sleep_quality_weight"]), step=0.1)
        with d3:
            st.session_state["daily_settings"]["dep_low_energy_weight"] = st.number_input("Low energy", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["dep_low_energy_weight"]), step=0.1)
        with d4:
            st.session_state["daily_settings"]["dep_low_mental_speed_weight"] = st.number_input("Low mental speed", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["dep_low_mental_speed_weight"]), step=0.1)
        with d5:
            st.session_state["daily_settings"]["dep_low_motivation_weight"] = st.number_input("Low motivation", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["dep_low_motivation_weight"]), step=0.1)
        with d6:
            st.session_state["daily_settings"]["dep_flag_weight"] = st.number_input("Depression flags", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["dep_flag_weight"]), step=0.1)

        st.markdown("#### Mania weights")
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        with m1:
            st.session_state["daily_settings"]["mania_high_mood_weight"] = st.number_input("High mood", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["mania_high_mood_weight"]), step=0.1)
        with m2:
            st.session_state["daily_settings"]["mania_low_sleep_quality_weight"] = st.number_input("Low sleep quality (mania)", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["mania_low_sleep_quality_weight"]), step=0.1)
        with m3:
            st.session_state["daily_settings"]["mania_high_energy_weight"] = st.number_input("High energy", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["mania_high_energy_weight"]), step=0.1)
        with m4:
            st.session_state["daily_settings"]["mania_high_mental_speed_weight"] = st.number_input("High mental speed", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["mania_high_mental_speed_weight"]), step=0.1)
        with m5:
            st.session_state["daily_settings"]["mania_high_motivation_weight"] = st.number_input("High motivation", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["mania_high_motivation_weight"]), step=0.1)
        with m6:
            st.session_state["daily_settings"]["mania_flag_weight"] = st.number_input("Mania flags", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["mania_flag_weight"]), step=0.1)

        st.markdown("#### Psychosis weights")
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            st.session_state["daily_settings"]["psych_unusual_weight"] = st.number_input("Unusual perceptions", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["psych_unusual_weight"]), step=0.1)
        with p2:
            st.session_state["daily_settings"]["psych_suspicious_weight"] = st.number_input("Suspiciousness", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["psych_suspicious_weight"]), step=0.1)
        with p3:
            st.session_state["daily_settings"]["psych_certainty_weight"] = st.number_input("Certainty", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["psych_certainty_weight"]), step=0.1)
        with p4:
            st.session_state["daily_settings"]["psych_flag_weight"] = st.number_input("Psychosis flags", min_value=0.0, max_value=5.0, value=float(st.session_state["daily_settings"]["psych_flag_weight"]), step=0.1)

        st.markdown("#### Mixed weights")
        mx1, mx2, mx3, mx4 = st.columns(4)
        with mx1:
            st.session_state["daily_settings"]["mixed_dep_weight"] = st.number_input("Mixed: depression", min_value=0.0, max_value=3.0, value=float(st.session_state["daily_settings"]["mixed_dep_weight"]), step=0.05)
        with mx2:
            st.session_state["daily_settings"]["mixed_mania_weight"] = st.number_input("Mixed: mania", min_value=0.0, max_value=3.0, value=float(st.session_state["daily_settings"]["mixed_mania_weight"]), step=0.05)
        with mx3:
            st.session_state["daily_settings"]["mixed_psych_weight"] = st.number_input("Mixed: psychosis", min_value=0.0, max_value=3.0, value=float(st.session_state["daily_settings"]["mixed_psych_weight"]), step=0.05)
        with mx4:
            st.session_state["daily_settings"]["mixed_low_sleep_quality_weight"] = st.number_input("Mixed: low sleep quality", min_value=0.0, max_value=3.0, value=float(st.session_state["daily_settings"]["mixed_low_sleep_quality_weight"]), step=0.05)

        st.markdown("#### Thresholds")
        t1, t2, t3 = st.columns(3)
        with t1:
            st.session_state["daily_settings"]["medium_threshold_pct"] = st.number_input("Medium threshold (%)", min_value=0.0, max_value=100.0, value=float(st.session_state["daily_settings"]["medium_threshold_pct"]), step=1.0)
        with t2:
            st.session_state["daily_settings"]["high_threshold_pct"] = st.number_input("High threshold (%)", min_value=0.0, max_value=100.0, value=float(st.session_state["daily_settings"]["high_threshold_pct"]), step=1.0)
        with t3:
            st.session_state["daily_settings"]["trend_threshold_pct"] = st.number_input("Trend threshold (pp)", min_value=0.0, max_value=100.0, value=float(st.session_state["daily_settings"]["trend_threshold_pct"]), step=1.0)

    daily_model_data, daily_model_summary = build_daily_model_from_form(
        form_data,
        st.session_state["daily_settings"],
    )

    if daily_model_data.empty:
        st.info("No daily model data available.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_daily_card("Depression", daily_model_summary["Depression"])
        with c2:
            render_daily_card("Mania", daily_model_summary["Mania"])
        with c3:
            render_daily_card("Psychosis", daily_model_summary["Psychosis"])
        with c4:
            render_daily_card("Mixed", daily_model_summary["Mixed"])

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Daily state scores (%)",
            default_cols=["Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"],
            key_prefix="daily_state_scores",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="3-day averages (%)",
            default_cols=[
                "3-Day Average (Depression %)",
                "3-Day Average (Mania %)",
                "3-Day Average (Psychosis %)",
                "3-Day Average (Mixed %)",
            ],
            key_prefix="daily_3day_avg",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Deviation from 3-day averages (percentage points)",
            default_cols=[
                "Depression Deviation %",
                "Mania Deviation %",
                "Psychosis Deviation %",
                "Mixed Deviation %",
            ],
            key_prefix="daily_deviation",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Flag breakdown by category",
            default_cols=[
                "Concerning Situation Flags",
                "Depression Flags",
                "Mania Flags",
                "Mixed Flags",
                "Psychosis Flags",
            ],
            key_prefix="daily_flags",
            chart_type="bar",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Depression drivers",
            default_cols=[
                "Depression - Low Mood Score",
                "Depression - Low Sleep Quality",
                "Depression - Low Energy",
                "Depression - Low Mental Speed",
                "Depression - Low Motivation",
                "Depression - Flags",
            ],
            key_prefix="daily_depression_drivers",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Mania drivers",
            default_cols=[
                "Mania - High Mood Score",
                "Mania - Low Sleep Quality",
                "Mania - High Energy",
                "Mania - High Mental Speed",
                "Mania - High Motivation",
                "Mania - Flags",
            ],
            key_prefix="daily_mania_drivers",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Psychosis drivers",
            default_cols=[
                "Psychosis - Unusual perceptions",
                "Psychosis - Suspiciousness",
                "Psychosis - Certainty",
                "Psychosis - Flags",
            ],
            key_prefix="daily_psychosis_drivers",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Mixed-relevant drivers",
            default_cols=[
                "Depression Score %",
                "Mania Score %",
                "Psychosis Score %",
                "Mixed Score %",
            ],
            key_prefix="daily_mixed_drivers",
            chart_type="line",
        )

        st.markdown("### Daily model data")
        default_daily_cols = [
            c for c in [
                "Date",
                "Depression Score %",
                "Mania Score %",
                "Psychosis Score %",
                "Mixed Score %",
                "3-Day Average (Depression %)",
                "3-Day Average (Mania %)",
                "3-Day Average (Psychosis %)",
                "3-Day Average (Mixed %)",
                "Concerning Situation Flags",
                "Depression Flags",
                "Mania Flags",
                "Mixed Flags",
                "Psychosis Flags",
            ]
            if c in daily_model_data.columns
        ]

        selected_daily_cols = st.multiselect(
            "Choose Daily Model columns",
            daily_model_data.columns.tolist(),
            default=default_daily_cols if default_daily_cols else daily_model_data.columns.tolist()[:12],
            key="daily_model_columns",
        )

        if selected_daily_cols:
            st.dataframe(daily_model_data[selected_daily_cols], use_container_width=True)


# =========================
# Snapshot Model
# =========================
with tab_snapshot_model:
    st.subheader("Snapshot Model")
    st.caption("Calculated from Quick Form Responses. Symptom scoring converts No/Somewhat/Yes from 0/1/2 into 0/50/100%.")

    with st.expander("Snapshot model settings"):
        st.markdown("#### Depression weights")
        d1, d2, d3, d4, d5 = st.columns(5)
        with d1:
            st.session_state["snapshot_settings"]["dep_very_low_mood"] = st.number_input("Very low mood", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["dep_very_low_mood"]), step=0.1, key="snap_dep_1")
        with d2:
            st.session_state["snapshot_settings"]["dep_somewhat_low_mood"] = st.number_input("Somewhat low mood", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["dep_somewhat_low_mood"]), step=0.1, key="snap_dep_2")
        with d3:
            st.session_state["snapshot_settings"]["dep_withdrawal"] = st.number_input("Withdrawal", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["dep_withdrawal"]), step=0.1, key="snap_dep_3")
        with d4:
            st.session_state["snapshot_settings"]["dep_slowed_down"] = st.number_input("Slowed down", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["dep_slowed_down"]), step=0.1, key="snap_dep_4")
        with d5:
            st.session_state["snapshot_settings"]["dep_self_care"] = st.number_input("Self-care", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["dep_self_care"]), step=0.1, key="snap_dep_5")

        st.markdown("#### Mania weights")
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.session_state["snapshot_settings"]["mania_very_high_mood"] = st.number_input("Very high mood", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["mania_very_high_mood"]), step=0.1, key="snap_man_1")
        with m2:
            st.session_state["snapshot_settings"]["mania_somewhat_high_mood"] = st.number_input("Somewhat high mood", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["mania_somewhat_high_mood"]), step=0.1, key="snap_man_2")
        with m3:
            st.session_state["snapshot_settings"]["mania_agitation"] = st.number_input("Agitation", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["mania_agitation"]), step=0.1, key="snap_man_3")
        with m4:
            st.session_state["snapshot_settings"]["mania_racing"] = st.number_input("Racing thoughts", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["mania_racing"]), step=0.1, key="snap_man_4")
        with m5:
            st.session_state["snapshot_settings"]["mania_driven"] = st.number_input("Driven to activity", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["mania_driven"]), step=0.1, key="snap_man_5")

        st.markdown("#### Psychosis weights")
        p1, p2, p3 = st.columns(3)
        with p1:
            st.session_state["snapshot_settings"]["psych_hearing_seeing"] = st.number_input("Hearing / seeing things", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["psych_hearing_seeing"]), step=0.1, key="snap_psy_1")
        with p2:
            st.session_state["snapshot_settings"]["psych_paranoia"] = st.number_input("Paranoia", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["psych_paranoia"]), step=0.1, key="snap_psy_2")
        with p3:
            st.session_state["snapshot_settings"]["psych_beliefs"] = st.number_input("Firm unusual beliefs", min_value=0.0, max_value=5.0, value=float(st.session_state["snapshot_settings"]["psych_beliefs"]), step=0.1, key="snap_psy_3")

        st.markdown("#### Mixed weights")
        mx1, mx2, mx3 = st.columns(3)
        with mx1:
            st.session_state["snapshot_settings"]["mixed_dep_weight"] = st.number_input("Mixed: depression", min_value=0.0, max_value=3.0, value=float(st.session_state["snapshot_settings"]["mixed_dep_weight"]), step=0.05, key="snap_mix_1")
        with mx2:
            st.session_state["snapshot_settings"]["mixed_mania_weight"] = st.number_input("Mixed: mania", min_value=0.0, max_value=3.0, value=float(st.session_state["snapshot_settings"]["mixed_mania_weight"]), step=0.05, key="snap_mix_2")
        with mx3:
            st.session_state["snapshot_settings"]["mixed_psych_weight"] = st.number_input("Mixed: psychosis", min_value=0.0, max_value=3.0, value=float(st.session_state["snapshot_settings"]["mixed_psych_weight"]), step=0.05, key="snap_mix_3")

        st.markdown("#### Thresholds")
        t1, t2, t3 = st.columns(3)
        with t1:
            st.session_state["snapshot_settings"]["medium_threshold_pct"] = st.number_input("Medium threshold (%)", min_value=0.0, max_value=100.0, value=float(st.session_state["snapshot_settings"]["medium_threshold_pct"]), step=1.0, key="snap_thr_1")
        with t2:
            st.session_state["snapshot_settings"]["high_threshold_pct"] = st.number_input("High threshold (%)", min_value=0.0, max_value=100.0, value=float(st.session_state["snapshot_settings"]["high_threshold_pct"]), step=1.0, key="snap_thr_2")
        with t3:
            st.session_state["snapshot_settings"]["trend_threshold_pct"] = st.number_input("Trend threshold (pp)", min_value=0.0, max_value=100.0, value=float(st.session_state["snapshot_settings"]["trend_threshold_pct"]), step=1.0, key="snap_thr_3")

    snapshot_model_summary, snapshot_model_data = build_snapshot_model_from_quick_form(
        quick_form_df,
        st.session_state["snapshot_settings"],
    )

    if snapshot_model_summary is None or snapshot_model_data.empty:
        st.info("No snapshot model data available.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_status_card("Depression", snapshot_model_summary["Depression"]["score_pct"], snapshot_model_summary["Depression"]["level"], snapshot_model_summary["Depression"]["trend"], snapshot_model_summary["Depression"]["confidence"])
        with c2:
            render_status_card("Mania", snapshot_model_summary["Mania"]["score_pct"], snapshot_model_summary["Mania"]["level"], snapshot_model_summary["Mania"]["trend"], snapshot_model_summary["Mania"]["confidence"])
        with c3:
            render_status_card("Psychosis", snapshot_model_summary["Psychosis"]["score_pct"], snapshot_model_summary["Psychosis"]["level"], snapshot_model_summary["Psychosis"]["trend"], snapshot_model_summary["Psychosis"]["confidence"])
        with c4:
            render_status_card("Mixed", snapshot_model_summary["Mixed"]["score_pct"], snapshot_model_summary["Mixed"]["level"], snapshot_model_summary["Mixed"]["trend"], snapshot_model_summary["Mixed"]["confidence"])

        render_filtered_chart(
            snapshot_model_data,
            date_col="FilterDate",
            label_col="TimeLabel",
            title="Snapshot model scores (%)",
            default_cols=["Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"],
            key_prefix="snapshot_model_scores",
            chart_type="line",
        )

        render_filtered_chart(
            snapshot_model_data,
            date_col="FilterDate",
            label_col="TimeLabel",
            title="Snapshot scores vs 3-response averages (%)",
            default_cols=[
                "Depression Score %",
                "3-Response Average (Depression %)",
                "Mania Score %",
                "3-Response Average (Mania %)",
                "Psychosis Score %",
                "3-Response Average (Psychosis %)",
                "Mixed Score %",
                "3-Response Average (Mixed %)",
            ],
            key_prefix="snapshot_scores_vs_avg",
            chart_type="line",
        )

        render_filtered_chart(
            snapshot_model_data,
            date_col="FilterDate",
            label_col="TimeLabel",
            title="Deviation from 3-response averages (percentage points)",
            default_cols=[
                "Deviation From 3-Response Average (Depression %)",
                "Deviation From 3-Response Average (Mania %)",
                "Deviation From 3-Response Average (Psychosis %)",
                "Deviation From 3-Response Average (Mixed %)",
            ],
            key_prefix="snapshot_deviation",
            chart_type="line",
        )

        st.markdown("### Snapshot model data")
        preview_cols = [
            c for c in [
                "Timestamp",
                "Depression Score %",
                "Mania Score %",
                "Psychosis Score %",
                "Mixed Score %",
                "3-Response Average (Depression %)",
                "3-Response Average (Mania %)",
                "3-Response Average (Psychosis %)",
                "3-Response Average (Mixed %)",
                "Deviation From 3-Response Average (Depression %)",
                "Deviation From 3-Response Average (Mania %)",
                "Deviation From 3-Response Average (Psychosis %)",
                "Deviation From 3-Response Average (Mixed %)",
            ]
            if c in snapshot_model_data.columns
        ]
        st.dataframe(snapshot_model_data[preview_cols], use_container_width=True)


# =========================
# Form Data
# =========================
with tab_form_data:
    st.subheader("Form Data")
    st.caption("Imported directly from Form Responses.")

    if form_data.empty:
        st.info("No form data available.")
    else:
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
                "Unusual perceptions",
                "Suspiciousness",
                "Certainty and belief in unusual ideas or things others don't believe",
            ]
            if c in form_data.columns
        ]

        selected_form_cols = st.multiselect(
            "Choose Form Data columns",
            form_data.columns.tolist(),
            default=default_form_cols if default_form_cols else form_data.columns.tolist()[:10],
            key="form_data_columns",
        )

        if selected_form_cols:
            st.dataframe(form_data[selected_form_cols], use_container_width=True)


# =========================
# Snapshot Data
# =========================
with tab_snapshot_data:
    st.subheader("Snapshot Data")
    st.caption("Imported directly from Quick Form Responses. Raw symptom flags are also converted to percentages.")

    if quick_form_data.empty:
        st.info("No snapshot data available.")
    else:
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
            ]
            if c in quick_form_data.columns
        ]

        selected_snapshot_cols = st.multiselect(
            "Choose Snapshot Data columns",
            quick_form_data.columns.tolist(),
            default=default_snapshot_cols if default_snapshot_cols else quick_form_data.columns.tolist()[:10],
            key="snapshot_data_columns",
        )

        if selected_snapshot_cols:
            st.dataframe(quick_form_data[selected_snapshot_cols], use_container_width=True)
