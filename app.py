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

# Per your instruction: mixed should combine mania + depression + psychosis
MIXED_SIGNAL_COLUMNS = (
    MANIA_SIGNAL_COLUMNS
    + DEPRESSION_SIGNAL_COLUMNS
    + PSYCHOSIS_SIGNAL_COLUMNS
)


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


def level_from_score(score: float, max_score: float) -> str:
    if max_score <= 0:
        return "Low"
    pct = score / max_score
    if pct >= 0.66:
        return "High"
    if pct >= 0.33:
        return "Medium"
    return "Low"


def trend_from_series(series: pd.Series) -> str:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2:
        return "Stable"

    baseline = s.iloc[:-1]
    if baseline.empty:
        return "Stable"

    diff = s.iloc[-1] - baseline.mean()

    if diff > 1:
        return "Rising"
    if diff < -1:
        return "Falling"
    return "Stable"


def confidence_from_entries(last_n: pd.DataFrame, trend: str, level: str) -> str:
    count = len(last_n)
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


# =========================
# Form Data (DATE-based)
# =========================
def prepare_form(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = convert_numeric(df.copy())

    if "Timestamp" not in df.columns:
        return df

    # Form responses must use DATE only
    df["Date"] = pd.to_datetime(df["Timestamp"], errors="coerce").dt.date

    # Convert signal columns to numeric 0/1
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

    rolling = (
        daily[[c for c in numeric_cols if c not in signal_columns]]
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
def build_snapshot_model(df: pd.DataFrame):
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

    working["Depression Level"] = working["Depression Score"].apply(lambda x: level_from_score(x, 10))
    working["Mania Level"] = working["Mania Score"].apply(lambda x: level_from_score(x, 10))
    working["Psychosis Level"] = working["Psychosis Score"].apply(lambda x: level_from_score(x, 6))

    last5 = working.tail(5).copy()
    latest = last5.iloc[-1]

    dep_trend = trend_from_series(last5["Depression Score"])
    mania_trend = trend_from_series(last5["Mania Score"])
    psych_trend = trend_from_series(last5["Psychosis Score"])

    dep_conf = confidence_from_entries(last5, dep_trend, latest["Depression Level"])
    mania_conf = confidence_from_entries(last5, mania_trend, latest["Mania Level"])
    psych_conf = confidence_from_entries(last5, psych_trend, latest["Psychosis Level"])

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

    return summary, working


# =========================
# Daily Model (DATE-based)
# =========================
def build_daily_model(form_df: pd.DataFrame) -> pd.DataFrame:
    if form_df.empty or "Timestamp" not in form_df.columns:
        return pd.DataFrame()

    working = form_df.copy()
    working = convert_numeric(working)

    # DATE only for all daily graphs
    working["Date"] = pd.to_datetime(working["Timestamp"], errors="coerce").dt.date

    # Signals to 0/1
    signal_columns = [c for c in working.columns if c.startswith("Signals and indicators [")]
    for col in signal_columns:
        working[col] = working[col].apply(bool_from_response).astype(int)

    # Numeric scores
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

    # ---------- Mania contributions ----------
    daily["Mania - Energy"] = safe_series(daily, COL_ENERGY) * 4
    daily["Mania - Mental speed"] = safe_series(daily, COL_MENTAL_SPEED) * 4
    daily["Mania - Impulsivity"] = safe_series(daily, COL_IMPULSIVITY) * 4
    daily["Mania - Less sleep"] = (10 - safe_series(daily, COL_SLEEP_HOURS)).clip(lower=0) * 5
    daily["Mania - Up signals"] = (
        safe_signal_series(daily, SIG_LESS_SLEEP)
        + safe_signal_series(daily, SIG_MORE_ACTIVITY)
        + safe_signal_series(daily, SIG_UP_NOW)
        + safe_signal_series(daily, SIG_UP_COMING)
    ) * 6

    daily["Mania Score"] = clamp_0_100(
        daily["Mania - Energy"]
        + daily["Mania - Mental speed"]
        + daily["Mania - Impulsivity"]
        + daily["Mania - Less sleep"]
        + daily["Mania - Up signals"]
    )

    # ---------- Depression contributions ----------
    daily["Depression - Low mood"] = (10 - safe_series(daily, COL_MOOD)).clip(lower=0) * 5
    daily["Depression - Low energy"] = (10 - safe_series(daily, COL_ENERGY)).clip(lower=0) * 3
    daily["Depression - Low motivation"] = (10 - safe_series(daily, COL_MOTIVATION)).clip(lower=0) * 4
    daily["Depression - Withdrawal"] = (
        safe_signal_series(daily, SIG_WITHDRAW)
        + safe_signal_series(daily, SIG_AVOID_RESPONSIBILITIES)
        + safe_signal_series(daily, SIG_DOWN_NOW)
        + safe_signal_series(daily, SIG_DOWN_COMING)
    ) * 6

    daily["Depression Score"] = clamp_0_100(
        daily["Depression - Low mood"]
        + daily["Depression - Low energy"]
        + daily["Depression - Low motivation"]
        + daily["Depression - Withdrawal"]
    )

    # ---------- Psychosis contributions ----------
    daily["Psychosis - Unusual perceptions"] = safe_series(daily, COL_UNUSUAL) * 5
    daily["Psychosis - Suspiciousness"] = safe_series(daily, COL_SUSPICIOUS) * 5
    daily["Psychosis - Certainty"] = safe_series(daily, COL_CERTAINTY) * 4
    daily["Psychosis - Signals"] = (
        safe_signal_series(daily, SIG_HEARD_SAW)
        + safe_signal_series(daily, SIG_WATCHED)
        + safe_signal_series(daily, SIG_SPECIAL_MEANING)
        + safe_signal_series(daily, SIG_TROUBLE_TRUSTING)
    ) * 6

    daily["Psychosis Score"] = clamp_0_100(
        daily["Psychosis - Unusual perceptions"]
        + daily["Psychosis - Suspiciousness"]
        + daily["Psychosis - Certainty"]
        + daily["Psychosis - Signals"]
    )

    # ---------- Mixed contributions ----------
    # Per your instruction: combine mania + depression + psychosis
    daily["Mixed - Mania"] = daily["Mania Score"] * 0.35
    daily["Mixed - Depression"] = daily["Depression Score"] * 0.35
    daily["Mixed - Psychosis"] = daily["Psychosis Score"] * 0.30

    daily["Mixed Score"] = clamp_0_100(
        daily["Mixed - Mania"] + daily["Mixed - Depression"] + daily["Mixed - Psychosis"]
    )

    # ---------- Signal totals ----------
    if signal_columns:
        daily["Total Signals"] = daily[signal_columns].sum(axis=1)
    else:
        daily["Total Signals"] = 0

    mania_available = [c for c in MANIA_SIGNAL_COLUMNS if c in daily.columns]
    depression_available = [c for c in DEPRESSION_SIGNAL_COLUMNS if c in daily.columns]
    psychosis_available = [c for c in PSYCHOSIS_SIGNAL_COLUMNS if c in daily.columns]
    mixed_available = [c for c in MIXED_SIGNAL_COLUMNS if c in daily.columns]

    daily["Mania Signals"] = daily[mania_available].sum(axis=1) if mania_available else 0
    daily["Depression Signals"] = daily[depression_available].sum(axis=1) if depression_available else 0
    daily["Psychosis Signals"] = daily[psychosis_available].sum(axis=1) if psychosis_available else 0
    daily["Mixed Signals"] = daily[mixed_available].sum(axis=1) if mixed_available else 0

    daily["DateLabel"] = pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")

    return daily


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

form_data = prepare_form(form_df)
snapshot_data = prepare_snapshot(snapshot_df_raw)
snapshot_model_summary, snapshot_model_data = build_snapshot_model(snapshot_df_raw)
daily_model_data = build_daily_model(form_df)


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
    st.write("Blank section ready for redesign.")


# =========================
# Daily Model
# =========================
with tab_daily_model:
    st.subheader("Daily Model")
    st.caption("All Daily Model charts use DATE only, not timestamp.")

    if daily_model_data.empty:
        st.info("No daily model data available.")
    else:
        st.markdown("### Daily state scores")
        state_chart = daily_model_data[
            ["DateLabel", "Mania Score", "Depression Score", "Psychosis Score", "Mixed Score"]
        ].set_index("DateLabel")
        st.line_chart(state_chart)

        st.markdown("### Mania contributions")
        mania_chart = daily_model_data[
            [
                "DateLabel",
                "Mania - Energy",
                "Mania - Mental speed",
                "Mania - Impulsivity",
                "Mania - Less sleep",
                "Mania - Up signals",
            ]
        ].set_index("DateLabel")
        st.line_chart(mania_chart)

        st.markdown("### Depression contributions")
        depression_chart = daily_model_data[
            [
                "DateLabel",
                "Depression - Low mood",
                "Depression - Low energy",
                "Depression - Low motivation",
                "Depression - Withdrawal",
            ]
        ].set_index("DateLabel")
        st.line_chart(depression_chart)

        st.markdown("### Psychosis contributions")
        psychosis_chart = daily_model_data[
            [
                "DateLabel",
                "Psychosis - Unusual perceptions",
                "Psychosis - Suspiciousness",
                "Psychosis - Certainty",
                "Psychosis - Signals",
            ]
        ].set_index("DateLabel")
        st.line_chart(psychosis_chart)

        st.markdown("### Mixed contributions")
        mixed_chart = daily_model_data[
            [
                "DateLabel",
                "Mixed - Mania",
                "Mixed - Depression",
                "Mixed - Psychosis",
            ]
        ].set_index("DateLabel")
        st.line_chart(mixed_chart)

        st.markdown("### Everything")
        everything_cols = [
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
        ]
        everything_cols = [c for c in everything_cols if c in daily_model_data.columns]

        all_chart = daily_model_data[["DateLabel"] + everything_cols].set_index("DateLabel")
        st.line_chart(all_chart)

        st.markdown("### Signals and indicators")
        signal_total_chart = daily_model_data[
            ["DateLabel", "Total Signals"]
        ].set_index("DateLabel")
        st.bar_chart(signal_total_chart)

        st.markdown("### Signals by category")
        signal_breakdown_chart = daily_model_data[
            [
                "DateLabel",
                "Mania Signals",
                "Depression Signals",
                "Psychosis Signals",
                "Mixed Signals",
            ]
        ].set_index("DateLabel")
        st.bar_chart(signal_breakdown_chart)

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
                "Mixed Signals",
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
    st.caption("Built from Quick Form Responses and compared against the last 5 entries.")

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
    st.caption("Imported from Form Responses. Rolling averages are DATE-based, not datetime-based.")

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
    st.caption("Imported from Quick Form Responses. Trends are DATETIME-based.")

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
