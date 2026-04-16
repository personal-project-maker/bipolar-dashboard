# =========================================================
# WELLBEING DASHBOARD
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
SNAPSHOT_TAB = "Quick Form Responses"


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
}


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

MANIA_SIGNAL_COLUMNS = [
    SIG_LESS_SLEEP,
    SIG_MORE_ACTIVITY,
    SIG_UP_NOW,
    SIG_UP_COMING,
]

DEPRESSION_SIGNAL_COLUMNS = [
    SIG_WITHDRAW,
    SIG_AVOID_RESPONSIBILITIES,
    SIG_DOWN_NOW,
    SIG_DOWN_COMING,
]

PSYCHOSIS_SIGNAL_COLUMNS = [
    SIG_HEARD_SAW,
    SIG_WATCHED,
    SIG_SPECIAL_MEANING,
    SIG_TROUBLE_TRUSTING,
]


# =========================
# Default Settings
# =========================
DEFAULT_DAILY_SETTINGS = {
    "mania_energy_weight": 4.0,
    "mania_speed_weight": 4.0,
    "mania_impulsivity_weight": 4.0,
    "mania_sleep_weight": 5.0,
    "mania_signal_weight": 6.0,
    "depression_mood_weight": 5.0,
    "depression_energy_weight": 3.0,
    "depression_motivation_weight": 4.0,
    "depression_signal_weight": 6.0,
    "psychosis_unusual_weight": 5.0,
    "psychosis_suspicious_weight": 5.0,
    "psychosis_certainty_weight": 4.0,
    "psychosis_signal_weight": 6.0,
    "mixed_mania_weight": 0.35,
    "mixed_depression_weight": 0.35,
    "mixed_psychosis_weight": 0.30,
    "daily_medium_threshold": 40.0,
    "daily_high_threshold": 70.0,
    "daily_trend_threshold": 5.0,
}

DEFAULT_SNAPSHOT_SETTINGS = {
    "snapshot_medium_pct": 0.33,
    "snapshot_high_pct": 0.66,
    "snapshot_trend_threshold": 1.0,
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

    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", dayfirst=True)

    return df


# =========================
# Generic Helpers
# =========================
def convert_numeric(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    working = df.copy()

    for col in working.columns:
        if col in ["Timestamp", "Date"]:
            continue

        converted = pd.to_numeric(working[col], errors="coerce")
        if converted.notna().any():
            working[col] = converted

    return working


def score_response(val):
    text = str(val).strip().lower()
    if text == "yes":
        return 2
    if text == "somewhat":
        return 1
    if text == "no":
        return 0
    return 0


def bool_from_response(val):
    text = str(val).strip().lower()
    return text in ["yes", "true", "1", "y", "checked"]


def safe_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0)
    return pd.Series(0, index=df.index, dtype=float)


def safe_signal_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0)
    return pd.Series(0, index=df.index, dtype=float)


def clamp_0_100(series: pd.Series) -> pd.Series:
    return series.clip(lower=0, upper=100)


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


def render_status_card(title: str, score: float, max_score: float, level: str, trend: str, confidence: str):
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
        ">
            <div style="font-size: 22px; font-weight: 700; margin-bottom: 6px;">{title}</div>
            <div style="font-size: 16px; margin-bottom: 6px;">
                <strong>Current:</strong> {level} ({score:.0f}/{max_score:.0f})
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
        ">
            <div style="font-size: 22px; font-weight: 700; margin-bottom: 6px;">{title}</div>
            <div style="font-size: 16px; margin-bottom: 6px;"><strong>Current state:</strong> {data['level']} ({data['score']:.0f}/100)</div>
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
# Form Data (DATE-based)
# =========================
def prepare_form(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = convert_numeric(df.copy())

    if "Timestamp" not in df.columns:
        return df

    df["Date"] = pd.to_datetime(df["Timestamp"], errors="coerce").dt.date

    signal_columns = [c for c in df.columns if c.startswith("Signals and indicators [")]
    for col in signal_columns:
        df[col] = df[col].apply(bool_from_response).astype(int)

    numeric_cols = [
        c for c in df.select_dtypes(include="number").columns
        if c != "Timestamp"
    ]

    if not numeric_cols:
        return df

    daily = (
        df.groupby("Date", as_index=False)[numeric_cols]
        .mean()
        .sort_values("Date")
        .reset_index(drop=True)
    )

    rolling_base_cols = [c for c in numeric_cols if c not in signal_columns]
    rolling = (
        daily[rolling_base_cols]
        .rolling(window=3, min_periods=1)
        .mean()
        .add_suffix(" 3 Day Rolling Avg")
    )

    daily = pd.concat([daily[["Date"]], rolling], axis=1)
    df = df.merge(daily, on="Date", how="left")

    return df


# =========================
# Snapshot Data (DATETIME-based)
# =========================
def prepare_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    if "Timestamp" in df.columns:
        df = df.sort_values("Timestamp").reset_index(drop=True)

    symptom_columns = [c for c in df.columns if c != "Timestamp"]

    for col in symptom_columns:
        df[col] = df[col].apply(score_response)

    numeric_cols = [
        c for c in df.select_dtypes(include="number").columns
        if c != "Timestamp"
    ]

    for col in numeric_cols:
        df[f"{col} Trend"] = df[col].diff()

    return df


# =========================
# Snapshot Model
# =========================
def snapshot_level(score: float, max_score: float, settings: dict) -> str:
    if max_score <= 0:
        return "Low"
    pct = score / max_score
    if pct >= settings["snapshot_high_pct"]:
        return "High"
    if pct >= settings["snapshot_medium_pct"]:
        return "Medium"
    return "Low"


def snapshot_trend(series: pd.Series, settings: dict) -> str:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2:
        return "Stable"

    baseline = s.iloc[:-1]
    if baseline.empty:
        return "Stable"

    diff = s.iloc[-1] - baseline.mean()

    if diff > settings["snapshot_trend_threshold"]:
        return "Rising"
    if diff < -settings["snapshot_trend_threshold"]:
        return "Falling"
    return "Stable"


def build_snapshot_model(df: pd.DataFrame, settings: dict):
    if df.empty or "Timestamp" not in df.columns:
        return None, pd.DataFrame()

    working = df.copy()
    working = working.sort_values("Timestamp").reset_index(drop=True)

    depression_cols = [
        "Symptoms: [Very low or depressed mood]",
        "Symptoms: [Somewhat low or depressed mood]",
        "Symptoms: [Social or emotional withdrawal]",
        "Symptoms: [Feeling slowed down]",
        "Symptoms: [Difficulty with self-care]",
    ]

    mania_cols = [
        "Symptoms: [Very high or elevated mood]",
        "Symptoms: [Somewhat high or elevated mood]",
        "Symptoms: [Agitation or restlessness]",
        "Symptoms: [Racing thoughts]",
        "Symptoms: [Driven to activity]",
    ]

    psychosis_cols = [
        "Symptoms: [Hearing or seeing things that aren't there]",
        "Symptoms: [Paranoia or suspicion]",
        "Symptoms: [Firm belief in things others would not agree with]",
    ]

    all_model_cols = depression_cols + mania_cols + psychosis_cols

    for col in all_model_cols:
        if col not in working.columns:
            working[col] = "No"

    for col in all_model_cols:
        working[col] = working[col].apply(score_response)

    working["Depression Score"] = working[depression_cols].sum(axis=1)
    working["Mania Score"] = working[mania_cols].sum(axis=1)
    working["Psychosis Score"] = working[psychosis_cols].sum(axis=1)

    working["Depression Level"] = working["Depression Score"].apply(lambda x: snapshot_level(x, 10, settings))
    working["Mania Level"] = working["Mania Score"].apply(lambda x: snapshot_level(x, 10, settings))
    working["Psychosis Level"] = working["Psychosis Score"].apply(lambda x: snapshot_level(x, 6, settings))

    last5 = working.tail(5).copy()
    latest = last5.iloc[-1]

    dep_trend = snapshot_trend(last5["Depression Score"], settings)
    mania_trend = snapshot_trend(last5["Mania Score"], settings)
    psych_trend = snapshot_trend(last5["Psychosis Score"], settings)

    dep_conf = confidence_from_count(len(last5), dep_trend, latest["Depression Level"])
    mania_conf = confidence_from_count(len(last5), mania_trend, latest["Mania Level"])
    psych_conf = confidence_from_count(len(last5), psych_trend, latest["Psychosis Level"])

    dep_level = latest["Depression Level"]
    mania_level = latest["Mania Level"]
    psych_level = latest["Psychosis Level"]

    mixed_state = dep_level in ["Medium", "High"] and mania_level in ["Medium", "High"]

    if mixed_state:
        if dep_trend == "Rising" and mania_trend == "Rising":
            mixed_trend = "Rising"
        elif dep_trend == "Falling" and mania_trend == "Falling":
            mixed_trend = "Falling"
        else:
            mixed_trend = "Stable"
    else:
        mixed_trend = "Not Active"

    summary = {
        "Depression": {
            "score": float(latest["Depression Score"]),
            "max_score": 10.0,
            "level": dep_level,
            "trend": dep_trend,
            "confidence": dep_conf,
        },
        "Mania": {
            "score": float(latest["Mania Score"]),
            "max_score": 10.0,
            "level": mania_level,
            "trend": mania_trend,
            "confidence": mania_conf,
        },
        "Psychosis": {
            "score": float(latest["Psychosis Score"]),
            "max_score": 6.0,
            "level": psych_level,
            "trend": psych_trend,
            "confidence": psych_conf,
        },
        "Mixed": {
            "active": mixed_state,
            "trend": mixed_trend,
            "confidence": "Medium" if mixed_state else "Low",
        },
    }

    working["Depression Trend Value"] = working["Depression Score"].diff()
    working["Mania Trend Value"] = working["Mania Score"].diff()
    working["Psychosis Trend Value"] = working["Psychosis Score"].diff()
    working["TimeLabel"] = working["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")

    return summary, working


# =========================
# Daily Model (DATE-based)
# =========================
def build_daily_model(form_df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    if form_df.empty or "Timestamp" not in form_df.columns:
        return pd.DataFrame()

    working = form_df.copy()
    working = convert_numeric(working)
    working["Date"] = pd.to_datetime(working["Timestamp"], errors="coerce").dt.date

    signal_columns = [c for c in working.columns if c.startswith("Signals and indicators [")]
    for col in signal_columns:
        working[col] = working[col].apply(bool_from_response).astype(int)

    score_columns = [
        COL_MOOD,
        COL_SLEEP_HOURS,
        COL_SLEEP_QUALITY,
        COL_ENERGY,
        COL_MENTAL_SPEED,
        COL_IMPULSIVITY,
        COL_MOTIVATION,
        COL_UNUSUAL,
        COL_SUSPICIOUS,
        COL_CERTAINTY,
    ]
    available_score_columns = [c for c in score_columns if c in working.columns]

    daily_scores = (
        working.groupby("Date", as_index=False)[available_score_columns].mean()
        if available_score_columns else pd.DataFrame({"Date": working["Date"].dropna().unique()})
    )

    daily_signals = (
        working.groupby("Date", as_index=False)[signal_columns].sum()
        if signal_columns else pd.DataFrame({"Date": working["Date"].dropna().unique()})
    )

    daily = daily_scores.merge(daily_signals, on="Date", how="outer").sort_values("Date").reset_index(drop=True)

    daily["Mania - Energy"] = safe_series(daily, COL_ENERGY) * settings["mania_energy_weight"]
    daily["Mania - Mental speed"] = safe_series(daily, COL_MENTAL_SPEED) * settings["mania_speed_weight"]
    daily["Mania - Impulsivity"] = safe_series(daily, COL_IMPULSIVITY) * settings["mania_impulsivity_weight"]
    daily["Mania - Less sleep"] = (10 - safe_series(daily, COL_SLEEP_HOURS)).clip(lower=0) * settings["mania_sleep_weight"]
    daily["Mania - Up signals"] = (
        safe_signal_series(daily, SIG_LESS_SLEEP)
        + safe_signal_series(daily, SIG_MORE_ACTIVITY)
        + safe_signal_series(daily, SIG_UP_NOW)
        + safe_signal_series(daily, SIG_UP_COMING)
    ) * settings["mania_signal_weight"]

    daily["Mania Score"] = clamp_0_100(
        daily["Mania - Energy"]
        + daily["Mania - Mental speed"]
        + daily["Mania - Impulsivity"]
        + daily["Mania - Less sleep"]
        + daily["Mania - Up signals"]
    )

    daily["Depression - Low mood"] = (10 - safe_series(daily, COL_MOOD)).clip(lower=0) * settings["depression_mood_weight"]
    daily["Depression - Low energy"] = (10 - safe_series(daily, COL_ENERGY)).clip(lower=0) * settings["depression_energy_weight"]
    daily["Depression - Low motivation"] = (10 - safe_series(daily, COL_MOTIVATION)).clip(lower=0) * settings["depression_motivation_weight"]
    daily["Depression - Withdrawal"] = (
        safe_signal_series(daily, SIG_WITHDRAW)
        + safe_signal_series(daily, SIG_AVOID_RESPONSIBILITIES)
        + safe_signal_series(daily, SIG_DOWN_NOW)
        + safe_signal_series(daily, SIG_DOWN_COMING)
    ) * settings["depression_signal_weight"]

    daily["Depression Score"] = clamp_0_100(
        daily["Depression - Low mood"]
        + daily["Depression - Low energy"]
        + daily["Depression - Low motivation"]
        + daily["Depression - Withdrawal"]
    )

    daily["Psychosis - Unusual perceptions"] = safe_series(daily, COL_UNUSUAL) * settings["psychosis_unusual_weight"]
    daily["Psychosis - Suspiciousness"] = safe_series(daily, COL_SUSPICIOUS) * settings["psychosis_suspicious_weight"]
    daily["Psychosis - Certainty"] = safe_series(daily, COL_CERTAINTY) * settings["psychosis_certainty_weight"]
    daily["Psychosis - Signals"] = (
        safe_signal_series(daily, SIG_HEARD_SAW)
        + safe_signal_series(daily, SIG_WATCHED)
        + safe_signal_series(daily, SIG_SPECIAL_MEANING)
        + safe_signal_series(daily, SIG_TROUBLE_TRUSTING)
    ) * settings["psychosis_signal_weight"]

    daily["Psychosis Score"] = clamp_0_100(
        daily["Psychosis - Unusual perceptions"]
        + daily["Psychosis - Suspiciousness"]
        + daily["Psychosis - Certainty"]
        + daily["Psychosis - Signals"]
    )

    mixed_weight_total = (
        settings["mixed_mania_weight"]
        + settings["mixed_depression_weight"]
        + settings["mixed_psychosis_weight"]
    )
    if mixed_weight_total == 0:
        mixed_weight_total = 1.0

    daily["Mixed - Mania"] = daily["Mania Score"] * settings["mixed_mania_weight"]
    daily["Mixed - Depression"] = daily["Depression Score"] * settings["mixed_depression_weight"]
    daily["Mixed - Psychosis"] = daily["Psychosis Score"] * settings["mixed_psychosis_weight"]
    daily["Mixed Score"] = clamp_0_100(
        (daily["Mixed - Mania"] + daily["Mixed - Depression"] + daily["Mixed - Psychosis"]) / mixed_weight_total
    )

    if signal_columns:
        daily["Total Signals"] = daily[signal_columns].sum(axis=1)
    else:
        daily["Total Signals"] = 0

    mania_available = [c for c in MANIA_SIGNAL_COLUMNS if c in daily.columns]
    depression_available = [c for c in DEPRESSION_SIGNAL_COLUMNS if c in daily.columns]
    psychosis_available = [c for c in PSYCHOSIS_SIGNAL_COLUMNS if c in daily.columns]

    daily["Mania Signals"] = daily[mania_available].sum(axis=1) if mania_available else 0
    daily["Depression Signals"] = daily[depression_available].sum(axis=1) if depression_available else 0
    daily["Psychosis Signals"] = daily[psychosis_available].sum(axis=1) if psychosis_available else 0

    daily["DateLabel"] = pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")

    return daily


def build_daily_summary_cards(daily_df: pd.DataFrame, settings: dict):
    if daily_df.empty:
        return None

    df = daily_df.copy()
    last5 = df.tail(5)
    latest = last5.iloc[-1]

    def daily_level(score):
        if score >= settings["daily_high_threshold"]:
            return "High"
        if score >= settings["daily_medium_threshold"]:
            return "Medium"
        return "Low"

    def daily_trend(series):
        s = pd.to_numeric(series, errors="coerce").dropna()
        if len(s) < 2:
            return "Stable"
        diff = s.iloc[-1] - s.iloc[:-1].mean()
        if diff > settings["daily_trend_threshold"]:
            return "Rising"
        if diff < -settings["daily_trend_threshold"]:
            return "Falling"
        return "Stable"

    def top_reasons(row, cols, prefix_to_remove):
        pairs = [(c, float(row.get(c, 0) or 0)) for c in cols if c in row.index]
        pairs = sorted(pairs, key=lambda x: x[1], reverse=True)
        cleaned = []
        for c, v in pairs:
            if v > 0:
                cleaned.append(c.replace(prefix_to_remove, ""))
        return cleaned[:3]

    depression_level = daily_level(float(latest["Depression Score"]))
    mania_level = daily_level(float(latest["Mania Score"]))
    psychosis_level = daily_level(float(latest["Psychosis Score"]))

    depression_trend = daily_trend(last5["Depression Score"])
    mania_trend = daily_trend(last5["Mania Score"])
    psychosis_trend = daily_trend(last5["Psychosis Score"])

    summary = {
        "Depression": {
            "score": float(latest["Depression Score"]),
            "level": depression_level,
            "trend": depression_trend,
            "confidence": confidence_from_count(len(last5), depression_trend, depression_level),
            "reasons": top_reasons(
                latest,
                [
                    "Depression - Low mood",
                    "Depression - Low energy",
                    "Depression - Low motivation",
                    "Depression - Withdrawal",
                ],
                "Depression - ",
            ),
        },
        "Mania": {
            "score": float(latest["Mania Score"]),
            "level": mania_level,
            "trend": mania_trend,
            "confidence": confidence_from_count(len(last5), mania_trend, mania_level),
            "reasons": top_reasons(
                latest,
                [
                    "Mania - Energy",
                    "Mania - Mental speed",
                    "Mania - Impulsivity",
                    "Mania - Less sleep",
                    "Mania - Up signals",
                ],
                "Mania - ",
            ),
        },
        "Psychosis": {
            "score": float(latest["Psychosis Score"]),
            "level": psychosis_level,
            "trend": psychosis_trend,
            "confidence": confidence_from_count(len(last5), psychosis_trend, psychosis_level),
            "reasons": top_reasons(
                latest,
                [
                    "Psychosis - Unusual perceptions",
                    "Psychosis - Suspiciousness",
                    "Psychosis - Certainty",
                    "Psychosis - Signals",
                ],
                "Psychosis - ",
            ),
        },
    }

    return summary


# =========================
# Warning Helpers
# =========================
def prettify_signal_name(name: str) -> str:
    cleaned = name.replace("Signals and indicators [", "").replace("]", "")
    return cleaned


def get_latest_form_warning_items(form_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if form_df.empty or "Timestamp" not in form_df.columns:
        return [], []

    working = form_df.copy()
    working = working.sort_values("Timestamp").reset_index(drop=True)
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
        if col in latest.index and pd.notna(latest[col]):
            val = pd.to_numeric(latest[col], errors="coerce")
            if col in [COL_MOOD, COL_MOTIVATION] and val <= 4:
                concerning.append(f"{label} ({val:.1f})")
            elif col == COL_SLEEP_HOURS and val <= 5:
                concerning.append(f"{label} ({val:.1f})")
            elif col == COL_SLEEP_QUALITY and val <= 4:
                concerning.append(f"{label} ({val:.1f})")
            elif col in [COL_ENERGY, COL_MENTAL_SPEED, COL_IMPULSIVITY, COL_UNUSUAL, COL_SUSPICIOUS, COL_CERTAINTY] and val >= 6:
                concerning.append(f"{label} ({val:.1f})")

    return flagged, concerning


def get_latest_snapshot_warning_items(snapshot_raw_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if snapshot_raw_df.empty or "Timestamp" not in snapshot_raw_df.columns:
        return [], []

    working = snapshot_raw_df.copy()
    working = working.sort_values("Timestamp").reset_index(drop=True)
    latest = working.iloc[-1]

    signals = []
    concerning = []

    for col in working.columns:
        if col == "Timestamp":
            continue

        val = str(latest.get(col, "")).strip().lower()
        label = col.replace("Symptoms: [", "").replace("]", "")

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
) -> tuple[list[str], list[str]]:
    daily_findings = []
    snapshot_findings = []

    if daily_summary:
        for name in ["Depression", "Mania", "Psychosis"]:
            item = daily_summary[name]
            if item["level"] in ["Medium", "High"]:
                daily_findings.append(
                    f"Daily {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}"
                )
            if item["reasons"]:
                daily_findings.append(
                    f"Daily {name.lower()} is being driven by: {', '.join(item['reasons'])}"
                )

    if snapshot_summary:
        for name in ["Depression", "Mania", "Psychosis"]:
            item = snapshot_summary[name]
            if item["level"] in ["Medium", "High"]:
                snapshot_findings.append(
                    f"Snapshot {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}"
                )

        if snapshot_summary["Mixed"]["active"]:
            snapshot_findings.append(
                f"Snapshot mixed state is active and {snapshot_summary['Mixed']['trend'].lower()}"
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
snapshot_df_raw = load_sheet(SNAPSHOT_TAB)


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
    st.write("Blank section ready for redesign.")


# =========================
# Warnings
# =========================
with tab_warnings:
    st.subheader("Warnings")

    # Build from current settings
    current_daily_model_data = build_daily_model(form_df, st.session_state["daily_settings"])
    current_daily_model_summary = build_daily_summary_cards(
        current_daily_model_data,
        st.session_state["daily_settings"],
    )
    current_snapshot_model_summary, current_snapshot_model_data = build_snapshot_model(
        snapshot_df_raw,
        st.session_state["snapshot_settings"],
    )

    latest_form_signals, latest_form_findings = get_latest_form_warning_items(form_df)
    latest_snapshot_signals, latest_snapshot_findings = get_latest_snapshot_warning_items(snapshot_df_raw)
    daily_model_findings, snapshot_model_findings = get_model_concerning_findings(
        current_daily_model_summary,
        current_snapshot_model_summary,
    )

    st.markdown("### Current State — Daily Model")
    if current_daily_model_summary:
        c1, c2, c3 = st.columns(3)
        with c1:
            render_daily_card("Depression", current_daily_model_summary["Depression"])
        with c2:
            render_daily_card("Mania", current_daily_model_summary["Mania"])
        with c3:
            render_daily_card("Psychosis", current_daily_model_summary["Psychosis"])
    else:
        st.info("No Daily Model summary available.")

    st.markdown("### Current State — Snapshot Model")
    if current_snapshot_model_summary:
        c1, c2, c3 = st.columns(3)
        with c1:
            render_status_card(
                "Depression",
                current_snapshot_model_summary["Depression"]["score"],
                current_snapshot_model_summary["Depression"]["max_score"],
                current_snapshot_model_summary["Depression"]["level"],
                current_snapshot_model_summary["Depression"]["trend"],
                current_snapshot_model_summary["Depression"]["confidence"],
            )
        with c2:
            render_status_card(
                "Mania",
                current_snapshot_model_summary["Mania"]["score"],
                current_snapshot_model_summary["Mania"]["max_score"],
                current_snapshot_model_summary["Mania"]["level"],
                current_snapshot_model_summary["Mania"]["trend"],
                current_snapshot_model_summary["Mania"]["confidence"],
            )
        with c3:
            render_status_card(
                "Psychosis",
                current_snapshot_model_summary["Psychosis"]["score"],
                current_snapshot_model_summary["Psychosis"]["max_score"],
                current_snapshot_model_summary["Psychosis"]["level"],
                current_snapshot_model_summary["Psychosis"]["trend"],
                current_snapshot_model_summary["Psychosis"]["confidence"],
            )
        if current_snapshot_model_summary["Mixed"]["active"]:
            st.error(
                f"Mixed state active — Trend: {current_snapshot_model_summary['Mixed']['trend']} | "
                f"Confidence: {current_snapshot_model_summary['Mixed']['confidence']}"
            )
    else:
        st.info("No Snapshot Model summary available.")

    st.markdown("### Warning Signals and Concerning Findings")
    left, right = st.columns(2)

    with left:
        render_signal_box(
            "Daily questionnaire — warning signals",
            latest_form_signals,
            tone="warning",
        )
        render_signal_box(
            "Daily questionnaire — concerning findings",
            latest_form_findings + daily_model_findings,
            tone="error",
        )

    with right:
        render_signal_box(
            "Snapshot questionnaire — warning signals",
            latest_snapshot_signals,
            tone="warning",
        )
        render_signal_box(
            "Snapshot questionnaire — concerning findings",
            latest_snapshot_findings + snapshot_model_findings,
            tone="error",
        )


# =========================
# Daily Model
# =========================
with tab_daily_model:
    st.subheader("Daily Model")

    with st.expander("Daily Model settings"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.session_state["daily_settings"]["mania_energy_weight"] = st.number_input(
                "Mania: energy weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["mania_energy_weight"]),
                step=0.5,
                key="daily_mania_energy_weight",
            )
            st.session_state["daily_settings"]["mania_speed_weight"] = st.number_input(
                "Mania: mental speed weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["mania_speed_weight"]),
                step=0.5,
                key="daily_mania_speed_weight",
            )
            st.session_state["daily_settings"]["mania_impulsivity_weight"] = st.number_input(
                "Mania: impulsivity weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["mania_impulsivity_weight"]),
                step=0.5,
                key="daily_mania_impulsivity_weight",
            )
            st.session_state["daily_settings"]["mania_sleep_weight"] = st.number_input(
                "Mania: low sleep weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["mania_sleep_weight"]),
                step=0.5,
                key="daily_mania_sleep_weight",
            )
            st.session_state["daily_settings"]["mania_signal_weight"] = st.number_input(
                "Mania: signal weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["mania_signal_weight"]),
                step=0.5,
                key="daily_mania_signal_weight",
            )

        with col2:
            st.session_state["daily_settings"]["depression_mood_weight"] = st.number_input(
                "Depression: low mood weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["depression_mood_weight"]),
                step=0.5,
                key="daily_depression_mood_weight",
            )
            st.session_state["daily_settings"]["depression_energy_weight"] = st.number_input(
                "Depression: low energy weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["depression_energy_weight"]),
                step=0.5,
                key="daily_depression_energy_weight",
            )
            st.session_state["daily_settings"]["depression_motivation_weight"] = st.number_input(
                "Depression: low motivation weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["depression_motivation_weight"]),
                step=0.5,
                key="daily_depression_motivation_weight",
            )
            st.session_state["daily_settings"]["depression_signal_weight"] = st.number_input(
                "Depression: signal weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["depression_signal_weight"]),
                step=0.5,
                key="daily_depression_signal_weight",
            )
            st.session_state["daily_settings"]["psychosis_unusual_weight"] = st.number_input(
                "Psychosis: unusual perceptions weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["psychosis_unusual_weight"]),
                step=0.5,
                key="daily_psychosis_unusual_weight",
            )
            st.session_state["daily_settings"]["psychosis_suspicious_weight"] = st.number_input(
                "Psychosis: suspiciousness weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["psychosis_suspicious_weight"]),
                step=0.5,
                key="daily_psychosis_suspicious_weight",
            )

        with col3:
            st.session_state["daily_settings"]["psychosis_certainty_weight"] = st.number_input(
                "Psychosis: certainty weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["psychosis_certainty_weight"]),
                step=0.5,
                key="daily_psychosis_certainty_weight",
            )
            st.session_state["daily_settings"]["psychosis_signal_weight"] = st.number_input(
                "Psychosis: signal weight",
                min_value=0.0,
                max_value=20.0,
                value=float(st.session_state["daily_settings"]["psychosis_signal_weight"]),
                step=0.5,
                key="daily_psychosis_signal_weight",
            )
            st.session_state["daily_settings"]["mixed_mania_weight"] = st.number_input(
                "Mixed: mania component weight",
                min_value=0.0,
                max_value=2.0,
                value=float(st.session_state["daily_settings"]["mixed_mania_weight"]),
                step=0.05,
                key="daily_mixed_mania_weight",
            )
            st.session_state["daily_settings"]["mixed_depression_weight"] = st.number_input(
                "Mixed: depression component weight",
                min_value=0.0,
                max_value=2.0,
                value=float(st.session_state["daily_settings"]["mixed_depression_weight"]),
                step=0.05,
                key="daily_mixed_depression_weight",
            )
            st.session_state["daily_settings"]["mixed_psychosis_weight"] = st.number_input(
                "Mixed: psychosis component weight",
                min_value=0.0,
                max_value=2.0,
                value=float(st.session_state["daily_settings"]["mixed_psychosis_weight"]),
                step=0.05,
                key="daily_mixed_psychosis_weight",
            )
            st.session_state["daily_settings"]["daily_medium_threshold"] = st.number_input(
                "Card threshold: medium",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state["daily_settings"]["daily_medium_threshold"]),
                step=1.0,
                key="daily_medium_threshold",
            )
            st.session_state["daily_settings"]["daily_high_threshold"] = st.number_input(
                "Card threshold: high",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state["daily_settings"]["daily_high_threshold"]),
                step=1.0,
                key="daily_high_threshold",
            )
            st.session_state["daily_settings"]["daily_trend_threshold"] = st.number_input(
                "Trend threshold",
                min_value=0.0,
                max_value=50.0,
                value=float(st.session_state["daily_settings"]["daily_trend_threshold"]),
                step=1.0,
                key="daily_trend_threshold",
            )

    daily_model_data = build_daily_model(form_df, st.session_state["daily_settings"])
    daily_model_summary = build_daily_summary_cards(
        daily_model_data,
        st.session_state["daily_settings"],
    )

    if daily_model_data.empty:
        st.info("No daily model data available.")
    else:
       if daily_model_summary:
        c1, c2, c3 = st.columns(3)
    with c1:
        render_daily_card("Depression", daily_model_summary["Depression"])
    with c2:
        render_daily_card("Mania", daily_model_summary["Mania"])
    with c3:
        render_daily_card("Psychosis", daily_model_summary["Psychosis"])

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Daily state scores",
            default_cols=["Mania Score", "Depression Score", "Psychosis Score", "Mixed Score"],
            key_prefix="daily_state_scores",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Mania contributions",
            default_cols=[
                "Mania - Energy",
                "Mania - Mental speed",
                "Mania - Impulsivity",
                "Mania - Less sleep",
                "Mania - Up signals",
            ],
            key_prefix="daily_mania_contrib",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Depression contributions",
            default_cols=[
                "Depression - Low mood",
                "Depression - Low energy",
                "Depression - Low motivation",
                "Depression - Withdrawal",
            ],
            key_prefix="daily_depression_contrib",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Psychosis contributions",
            default_cols=[
                "Psychosis - Unusual perceptions",
                "Psychosis - Suspiciousness",
                "Psychosis - Certainty",
                "Psychosis - Signals",
            ],
            key_prefix="daily_psychosis_contrib",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Mixed contributions",
            default_cols=[
                "Mixed - Mania",
                "Mixed - Depression",
                "Mixed - Psychosis",
            ],
            key_prefix="daily_mixed_contrib",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Everything",
            default_cols=[
                "Mania Score",
                "Depression Score",
                "Psychosis Score",
                "Mixed Score",
                "Mania - Energy",
                "Mania - Mental speed",
                "Mania - Impulsivity",
                "Mania - Less sleep",
                "Mania - Up signals",
                "Depression - Low mood",
                "Depression - Low energy",
                "Depression - Low motivation",
                "Depression - Withdrawal",
                "Psychosis - Unusual perceptions",
                "Psychosis - Suspiciousness",
                "Psychosis - Certainty",
                "Psychosis - Signals",
                "Mixed - Mania",
                "Mixed - Depression",
                "Mixed - Psychosis",
            ],
            key_prefix="daily_everything",
            chart_type="line",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Signals and indicators",
            default_cols=["Total Signals"],
            key_prefix="daily_signal_total",
            chart_type="bar",
        )

        render_filtered_chart(
            daily_model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Signals by category",
            default_cols=[
                "Mania Signals",
                "Depression Signals",
                "Psychosis Signals",
            ],
            key_prefix="daily_signal_breakdown",
            chart_type="bar",
        )

        st.markdown("### Daily model data")
        default_daily_cols = [
            c for c in [
                "Date",
                "Mania Score",
                "Depression Score",
                "Psychosis Score",
                "Mixed Score",
                "Total Signals",
                "Mania Signals",
                "Depression Signals",
                "Psychosis Signals",
            ]
            if c in daily_model_data.columns
        ]

        selected_daily_cols = st.multiselect(
            "Choose Daily Model columns",
            daily_model_data.columns.tolist(),
            default=default_daily_cols if default_daily_cols else daily_model_data.columns.tolist()[:10],
            key="daily_model_columns",
        )

        if selected_daily_cols:
            st.dataframe(daily_model_data[selected_daily_cols], use_container_width=True)
        else:
            st.info("Pick at least one Daily Model column to display.")


# =========================
# Snapshot Model
# =========================
with tab_snapshot_model:
    st.subheader("Snapshot Model")

    with st.expander("Snapshot Model settings"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.session_state["snapshot_settings"]["snapshot_medium_pct"] = st.number_input(
                "Medium threshold (fraction of max score)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state["snapshot_settings"]["snapshot_medium_pct"]),
                step=0.01,
                key="snapshot_medium_pct",
            )

        with col2:
            st.session_state["snapshot_settings"]["snapshot_high_pct"] = st.number_input(
                "High threshold (fraction of max score)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state["snapshot_settings"]["snapshot_high_pct"]),
                step=0.01,
                key="snapshot_high_pct",
            )

        with col3:
            st.session_state["snapshot_settings"]["snapshot_trend_threshold"] = st.number_input(
                "Trend threshold",
                min_value=0.0,
                max_value=10.0,
                value=float(st.session_state["snapshot_settings"]["snapshot_trend_threshold"]),
                step=0.25,
                key="snapshot_trend_threshold",
            )

    snapshot_model_summary, snapshot_model_data = build_snapshot_model(
        snapshot_df_raw,
        st.session_state["snapshot_settings"],
    )

    if snapshot_model_summary is None:
        st.info("No snapshot model data available.")
    else:
        c1, c2, c3 = st.columns(3)

        with c1:
            render_status_card(
                "Depression",
                snapshot_model_summary["Depression"]["score"],
                snapshot_model_summary["Depression"]["max_score"],
                snapshot_model_summary["Depression"]["level"],
                snapshot_model_summary["Depression"]["trend"],
                snapshot_model_summary["Depression"]["confidence"],
            )

        with c2:
            render_status_card(
                "Mania",
                snapshot_model_summary["Mania"]["score"],
                snapshot_model_summary["Mania"]["max_score"],
                snapshot_model_summary["Mania"]["level"],
                snapshot_model_summary["Mania"]["trend"],
                snapshot_model_summary["Mania"]["confidence"],
            )

        with c3:
            render_status_card(
                "Psychosis",
                snapshot_model_summary["Psychosis"]["score"],
                snapshot_model_summary["Psychosis"]["max_score"],
                snapshot_model_summary["Psychosis"]["level"],
                snapshot_model_summary["Psychosis"]["trend"],
                snapshot_model_summary["Psychosis"]["confidence"],
            )

        st.markdown("### Mixed State")

        if snapshot_model_summary["Mixed"]["active"]:
            st.error(
                f"Mixed state active — Depression and Mania are both elevated. "
                f"Trend: {snapshot_model_summary['Mixed']['trend']} | "
                f"Confidence: {snapshot_model_summary['Mixed']['confidence']}"
            )
        else:
            st.success("Mixed state not currently active.")

        render_filtered_chart(
            snapshot_model_data.assign(FilterDate=snapshot_model_data["Timestamp"].dt.date),
            date_col="FilterDate",
            label_col="TimeLabel",
            title="Snapshot model scores",
            default_cols=["Depression Score", "Mania Score", "Psychosis Score"],
            key_prefix="snapshot_model_scores",
            chart_type="line",
        )

        st.markdown("### Last 5 Entries Used")
        preview_cols = [
            c for c in [
                "Timestamp",
                "Depression Score",
                "Depression Level",
                "Mania Score",
                "Mania Level",
                "Psychosis Score",
                "Psychosis Level",
                "Depression Trend Value",
                "Mania Trend Value",
                "Psychosis Trend Value",
            ]
            if c in snapshot_model_data.columns
        ]
        st.dataframe(snapshot_model_data.tail(5)[preview_cols], use_container_width=True)


# =========================
# Form Data
# =========================
with tab_form_data:
    st.subheader("Form Data")
    st.caption("Imported from Form Responses. Rolling averages are date-based.")

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
                "Mood Score 3 Day Rolling Avg",
                "Sleep (hours) 3 Day Rolling Avg",
                "Energy 3 Day Rolling Avg",
                "Motivation 3 Day Rolling Avg",
            ]
            if c in form_data.columns
        ]

        selected_form_cols = st.multiselect(
            "Choose Form Data columns",
            form_data.columns.tolist(),
            default=default_form_cols if default_form_cols else form_data.columns.tolist()[:8],
            key="form_data_columns",
        )

        if selected_form_cols:
            st.dataframe(form_data[selected_form_cols], use_container_width=True)
        else:
            st.info("Pick at least one column to display.")


# =========================
# Snapshot Data
# =========================
with tab_snapshot_data:
    st.subheader("Snapshot Data")
    st.caption("Imported from Quick Form Responses. Trends are datetime-based.")

    if snapshot_data.empty:
        st.info("No snapshot data available.")
    else:
        default_snapshot_cols = [
            c for c in [
                "Timestamp",
                "Symptoms: [Very low or depressed mood]",
                "Symptoms: [Somewhat low or depressed mood]",
                "Symptoms: [Very high or elevated mood]",
                "Symptoms: [Agitation or restlessness]",
                "Symptoms: [Paranoia or suspicion]",
                "Symptoms: [Very low or depressed mood] Trend",
                "Symptoms: [Very high or elevated mood] Trend",
                "Symptoms: [Paranoia or suspicion] Trend",
            ]
            if c in snapshot_data.columns
        ]

        selected_snapshot_cols = st.multiselect(
            "Choose Snapshot Data columns",
            snapshot_data.columns.tolist(),
            default=default_snapshot_cols if default_snapshot_cols else snapshot_data.columns.tolist()[:8],
            key="snapshot_data_columns",
        )

        if selected_snapshot_cols:
            st.dataframe(snapshot_data[selected_snapshot_cols], use_container_width=True)
        else:
            st.info("Pick at least one column to display.")
