# =========================================================
# WELLBEING DASHBOARD — SHEET-DRIVEN VERSION
# Reads directly from:
# - Form Responses
# - Quick Form Responses
# - Model
# - Quick Model
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

DAILY_FLAG_COLS = {
    "Depression": "Depression Flags",
    "Mania": "Mania Flags",
    "Psychosis": "Psychosis Flags",
    "Mixed": "Mixed Flags",
}

DAILY_SCORE_COLS = {
    "Depression": "Depression Score",
    "Mania": "Mania Score",
    "Psychosis": "Psychosis Score",
    "Mixed": "Mixed Score",
}

DAILY_AVG_COLS = {
    "Depression": "3-Day Average (Depression)",
    "Mania": "3-Day Average (Mania)",
    "Psychosis": "3-Day Average (Psychosis)",
    "Mixed": "3-Day Average (Mixed)",
}

QUICK_SCORE_COLS = {
    "Depression": "Depression Score",
    "Mania": "Mania Score",
    "Psychosis": "Psychosis Score",
    "Mixed": "Mixed Score",
}

QUICK_AVG_COLS = {
    "Depression": "3-Response Average (Depression)",
    "Mania": "3-Response Average (Mania)",
    "Psychosis": "3-Response Average (Psychosis)",
    "Mixed": "3-Response Average (Mixed)",
}

QUICK_DEV_COLS = {
    "Depression": "Deviation From 3-Response Average (Depression)",
    "Mania": "Deviation From 3-Response Average (Mania)",
    "Psychosis": "Deviation From 3-Response Average (Psychosis)",
    "Mixed": "Deviation From 3-Response Average (Mixed)",
}


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
# Generic Helpers
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


def score_response(val):
    text = str(val).strip().lower()
    if text == "yes":
        return 2
    if text == "somewhat":
        return 1
    if text == "no":
        return 0
    return 0


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


def safe_numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series([pd.NA] * len(df), index=df.index, dtype="float64")


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


def safe_cell(row: pd.Series, col: str, default=0.0):
    if col not in row.index:
        return default
    return row[col]


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


def level_from_flag_count(flag_count, score=None) -> str:
    f = to_float(flag_count, 0.0)

    if f >= 3:
        return "High"
    if f >= 1:
        return "Medium"

    if score is not None:
        s = to_float(score, None)
        if s is not None:
            if s >= 0.66:
                return "High"
            if s >= 0.33:
                return "Medium"

    return "Low"


def level_from_normalized_score(score) -> str:
    s = to_float(score, 0.0)
    if s >= 0.66:
        return "High"
    if s >= 0.33:
        return "Medium"
    return "Low"


def trend_from_deviation(dev, threshold=0.08) -> str:
    d = to_float(dev, 0.0)
    if d > threshold:
        return "Rising"
    if d < -threshold:
        return "Falling"
    return "Stable"


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
                <strong>Current:</strong> {level} ({score:.2f}/{max_score:.2f})
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
            <div style="font-size: 16px; margin-bottom: 6px;"><strong>Current state:</strong> {data['level']} ({data['score']:.2f})</div>
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
        numeric = working[col].apply(score_response)
        working[f"{col} Numeric"] = numeric
        working[f"{col} Trend"] = numeric.diff()

    return working


def prepare_model(df: pd.DataFrame) -> pd.DataFrame:
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

    for name, score_col in DAILY_SCORE_COLS.items():
        avg_col = DAILY_AVG_COLS[name]
        if score_col in working.columns and avg_col in working.columns:
            working[f"{name} Deviation"] = (
                pd.to_numeric(working[score_col], errors="coerce")
                - pd.to_numeric(working[avg_col], errors="coerce")
            )

    if "Overall Risk" in working.columns:
        working["Overall Risk Numeric"] = (
            working["Overall Risk"].astype(str).str.upper().map(RISK_VALUE_MAP).fillna(0)
        )

    return working


def prepare_quick_model(df: pd.DataFrame) -> pd.DataFrame:
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
# Summaries from Model Tabs
# =========================
def build_daily_summary_from_model(model_df: pd.DataFrame):
    if model_df.empty:
        return None

    latest = model_df.iloc[-1]

    def top_reasons(row, candidates):
        pairs = []
        for c in candidates:
            if c in row.index:
                v = to_float(row[c], default=0.0)
                pairs.append((c, v))
        pairs = sorted(pairs, key=lambda x: x[1], reverse=True)
        cleaned = []
        for c, v in pairs:
            if v > 0:
                cleaned.append(c)
        return cleaned[:3]

    score_reason_map = {
        "Depression": [
            "Low Mood Score",
            "Low Sleep Quality",
            "Low Energy",
            "Low Mental Speed",
            "Low Motivation",
        ],
        "Mania": [
            "High Mood Score",
            "High Sleep Quality",
            "High Energy",
            "High Mental Speed",
            "High Motivation",
        ],
        "Psychosis": [
            "Unusual perceptions",
            "Suspiciousness",
            "Certainty and belief in unusual ideas or things others don't believe",
            "Psychosis Flags",
        ],
    }

    summary = {}

    for name in ["Depression", "Mania", "Psychosis"]:
        score_col = DAILY_SCORE_COLS[name]
        flag_col = DAILY_FLAG_COLS[name]
        dev_col = f"{name} Deviation"

        score = to_float(safe_cell(latest, score_col, 0.0), default=0.0)
        flags = to_float(safe_cell(latest, flag_col, 0.0), default=0.0)
        deviation = to_float(safe_cell(latest, dev_col, 0.0), default=0.0)

        level = level_from_flag_count(flags, score)
        trend = trend_from_deviation(deviation, threshold=0.08)
        confidence = confidence_from_count(len(model_df.tail(5)), trend, level)
        reasons = top_reasons(latest, score_reason_map[name])

        summary[name] = {
            "score": score,
            "level": level,
            "trend": trend,
            "confidence": confidence,
            "reasons": reasons,
        }

    return summary


def build_quick_summary_from_model(quick_model_df: pd.DataFrame):
    if quick_model_df.empty:
        return None, pd.DataFrame()

    latest = quick_model_df.iloc[-1]
    last5 = quick_model_df.tail(5).copy()

    summary = {}

    for name in ["Depression", "Mania", "Psychosis"]:
        score_col = QUICK_SCORE_COLS[name]
        dev_col = QUICK_DEV_COLS[name]

        score = to_float(safe_cell(latest, score_col, 0.0), default=0.0)
        dev = to_float(safe_cell(latest, dev_col, 0.0), default=0.0)

        level = level_from_normalized_score(score)
        trend = trend_from_deviation(dev, threshold=0.10)
        confidence = confidence_from_count(len(last5), trend, level)

        summary[name] = {
            "score": score,
            "max_score": 1.0,
            "level": level,
            "trend": trend,
            "confidence": confidence,
        }

    mixed_score = to_float(safe_cell(latest, "Mixed Score", 0.0), default=0.0)
    mixed_dev = to_float(
        safe_cell(latest, "Deviation From 3-Response Average (Mixed)", 0.0),
        default=0.0,
    )

    mixed_active = mixed_score >= 0.33 or (
        summary["Depression"]["level"] in ["Medium", "High"]
        and summary["Mania"]["level"] in ["Medium", "High"]
    )

    summary["Mixed"] = {
        "active": mixed_active,
        "trend": trend_from_deviation(mixed_dev, threshold=0.10) if mixed_active else "Not Active",
        "confidence": "Medium" if mixed_active else "Low",
    }

    return summary, quick_model_df


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
        if col == "Timestamp" or col.endswith(" Numeric") or col.endswith(" Trend"):
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
    quick_summary: dict | None,
    model_df: pd.DataFrame,
    quick_model_df: pd.DataFrame,
) -> tuple[list[str], list[str]]:
    daily_findings = []
    quick_findings = []

    if daily_summary and not model_df.empty:
        latest = model_df.iloc[-1]

        for name in ["Depression", "Mania", "Psychosis"]:
            item = daily_summary[name]
            if item["level"] in ["Medium", "High"]:
                daily_findings.append(
                    f"Daily {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}"
                )

        if "Concerning Situation Flags" in latest.index:
            concerning_flags = to_float(latest["Concerning Situation Flags"], default=0.0)
            if concerning_flags > 0:
                daily_findings.append(f"Concerning situation flags: {int(concerning_flags)}")

        for col in ["Mania Warning", "Psychosis Warning", "Overall Risk"]:
            if col in latest.index and str(latest[col]).strip():
                daily_findings.append(f"{col}: {latest[col]}")

    if quick_summary and not quick_model_df.empty:
        for name in ["Depression", "Mania", "Psychosis"]:
            item = quick_summary[name]
            if item["level"] in ["Medium", "High"]:
                quick_findings.append(
                    f"Snapshot {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}"
                )

        if quick_summary["Mixed"]["active"]:
            quick_findings.append(
                f"Snapshot mixed state is active and {quick_summary['Mixed']['trend'].lower()}"
            )

    return daily_findings, quick_findings


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
model_df = load_sheet(MODEL_TAB)
quick_model_df = load_sheet(QUICK_MODEL_TAB)

form_data = prepare_form_raw(form_df)
quick_form_data = prepare_quick_form_raw(quick_form_df)
model_data = prepare_model(model_df)
quick_model_data = prepare_quick_model(quick_model_df)

daily_model_summary = build_daily_summary_from_model(model_data)
snapshot_model_summary, snapshot_model_data = build_quick_summary_from_model(quick_model_data)

latest_form_signals, latest_form_findings = get_latest_form_warning_items(form_data)
latest_snapshot_signals, latest_snapshot_findings = get_latest_quick_form_warning_items(quick_form_data)
daily_model_findings, snapshot_model_findings = get_model_concerning_findings(
    daily_model_summary,
    snapshot_model_summary,
    model_data,
    snapshot_model_data,
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
    st.caption("This dashboard reads directly from Form Responses, Quick Form Responses, Model, and Quick Model.")

    st.markdown("### Current state")

    left, right = st.columns(2)

    with left:
        st.markdown("#### Daily Model")
        if daily_model_summary:
            c1, c2, c3 = st.columns(3)
            with c1:
                render_daily_card("Depression", daily_model_summary["Depression"])
            with c2:
                render_daily_card("Mania", daily_model_summary["Mania"])
            with c3:
                render_daily_card("Psychosis", daily_model_summary["Psychosis"])
        else:
            st.info("No daily model summary available.")

    with right:
        st.markdown("#### Snapshot Model")
        if snapshot_model_summary:
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

            if snapshot_model_summary["Mixed"]["active"]:
                st.error(
                    f"Mixed state active — Trend: {snapshot_model_summary['Mixed']['trend']} | "
                    f"Confidence: {snapshot_model_summary['Mixed']['confidence']}"
                )
            else:
                st.success("Mixed state not currently active.")
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

    if not model_data.empty:
        trend_df = model_data.copy()

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

        trend_cols = [
            "Depression Score",
            "Mania Score",
            "Psychosis Score",
            "Mixed Score",
        ]

        available_trend_cols = [c for c in trend_cols if c in trend_df.columns]

        if available_trend_cols:
            st.line_chart(
                trend_df[["DateLabel"] + available_trend_cols].set_index("DateLabel")
            )
        else:
            st.info("No daily score columns available for trend chart.")
    else:
        st.info("No daily trend data available.")

    st.markdown("### Flags overview")

    if not model_data.empty:
        latest_daily = model_data.iloc[-1]

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
    days_tracked = len(model_data) if not model_data.empty else 0

    snapshot_last_7 = 0
    if latest_snapshot_time is not None and not quick_form_data.empty and "Timestamp" in quick_form_data.columns:
        snap_ts = pd.to_datetime(quick_form_data["Timestamp"], errors="coerce").dropna()
        snapshot_last_7 = int((snap_ts >= (latest_snapshot_time - pd.Timedelta(days=7))).sum())

    with a1:
        st.metric(
            "Latest form entry",
            latest_form_time.strftime("%Y-%m-%d %H:%M") if latest_form_time is not None else "N/A"
        )
    with a2:
        st.metric(
            "Latest snapshot entry",
            latest_snapshot_time.strftime("%Y-%m-%d %H:%M") if latest_snapshot_time is not None else "N/A"
        )
    with a3:
        st.metric("Days tracked (Model)", days_tracked)
    with a4:
        st.metric("Snapshot entries (last 7d)", snapshot_last_7)


# =========================
# Warnings
# =========================
with tab_warnings:
    st.subheader("Warnings")

    st.markdown("### Current State — Daily Model")
    if daily_model_summary:
        c1, c2, c3 = st.columns(3)
        with c1:
            render_daily_card("Depression", daily_model_summary["Depression"])
        with c2:
            render_daily_card("Mania", daily_model_summary["Mania"])
        with c3:
            render_daily_card("Psychosis", daily_model_summary["Psychosis"])
    else:
        st.info("No Daily Model summary available.")

    st.markdown("### Current State — Snapshot Model")
    if snapshot_model_summary:
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
        if snapshot_model_summary["Mixed"]["active"]:
            st.error(
                f"Mixed state active — Trend: {snapshot_model_summary['Mixed']['trend']} | "
                f"Confidence: {snapshot_model_summary['Mixed']['confidence']}"
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
    st.caption("Drawn directly from the Model sheet.")

    if model_data.empty:
        st.info("No daily model data available.")
    else:
        if daily_model_summary:
            st.markdown("### Current Daily State")
            c1, c2, c3 = st.columns(3)

            with c1:
                render_daily_card("Depression", daily_model_summary["Depression"])
            with c2:
                render_daily_card("Mania", daily_model_summary["Mania"])
            with c3:
                render_daily_card("Psychosis", daily_model_summary["Psychosis"])

        render_filtered_chart(
            model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Daily state scores",
            default_cols=["Depression Score", "Mania Score", "Psychosis Score", "Mixed Score"],
            key_prefix="daily_state_scores",
            chart_type="line",
        )

        render_filtered_chart(
            model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Daily moving averages",
            default_cols=[
                "3-Day Average (Depression)",
                "3-Day Average (Mania)",
                "3-Day Average (Psychosis)",
                "3-Day Average (Mixed)",
            ],
            key_prefix="daily_3day_avg",
            chart_type="line",
        )

        render_filtered_chart(
            model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Deviation from 3-day averages",
            default_cols=[
                "Depression Deviation",
                "Mania Deviation",
                "Psychosis Deviation",
                "Mixed Deviation",
            ],
            key_prefix="daily_deviation",
            chart_type="line",
        )

        render_filtered_chart(
            model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Daily flags",
            default_cols=[
                "Concerning Situation Flags",
                "Mania Flags",
                "Depression Flags",
                "Mixed Flags",
                "Psychosis Flags",
            ],
            key_prefix="daily_flags",
            chart_type="bar",
        )

        render_filtered_chart(
            model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Self-reported episode flags",
            default_cols=[
                "Self-Reported Depression",
                "Self-Reported Mania",
                "Self-Reported Mixed",
            ],
            key_prefix="daily_self_reported",
            chart_type="bar",
        )

        render_filtered_chart(
            model_data,
            date_col="Date",
            label_col="DateLabel",
            title="Underlying model drivers",
            default_cols=[
                "Low Mood Score",
                "High Mood Score",
                "Low Sleep Quality",
                "High Sleep Quality",
                "Low Energy",
                "High Energy",
                "Low Mental Speed",
                "High Mental Speed",
                "Low Motivation",
                "High Motivation",
            ],
            key_prefix="daily_drivers",
            chart_type="line",
        )

        st.markdown("### Daily model data")
        default_daily_cols = [
            c for c in [
                "Date",
                "Depression Score",
                "Mania Score",
                "Psychosis Score",
                "Mixed Score",
                "3-Day Average (Depression)",
                "3-Day Average (Mania)",
                "3-Day Average (Psychosis)",
                "3-Day Average (Mixed)",
                "Concerning Situation Flags",
                "Depression Flags",
                "Mania Flags",
                "Psychosis Flags",
                "Overall Risk",
                "Mania Warning",
                "Psychosis Warning",
            ]
            if c in model_data.columns
        ]

        selected_daily_cols = st.multiselect(
            "Choose Daily Model columns",
            model_data.columns.tolist(),
            default=default_daily_cols if default_daily_cols else model_data.columns.tolist()[:12],
            key="daily_model_columns",
        )

        if selected_daily_cols:
            st.dataframe(model_data[selected_daily_cols], use_container_width=True)
        else:
            st.info("Pick at least one Daily Model column to display.")


# =========================
# Snapshot Model
# =========================
with tab_snapshot_model:
    st.subheader("Snapshot Model")
    st.caption("Drawn directly from the Quick Model sheet.")

    if snapshot_model_summary is None or snapshot_model_data.empty:
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
                f"Mixed state active — Trend: {snapshot_model_summary['Mixed']['trend']} | "
                f"Confidence: {snapshot_model_summary['Mixed']['confidence']}"
            )
        else:
            st.success("Mixed state not currently active.")

        render_filtered_chart(
            snapshot_model_data,
            date_col="FilterDate",
            label_col="TimeLabel",
            title="Snapshot model scores",
            default_cols=["Depression Score", "Mania Score", "Psychosis Score", "Mixed Score"],
            key_prefix="snapshot_model_scores",
            chart_type="line",
        )

        render_filtered_chart(
            snapshot_model_data,
            date_col="FilterDate",
            label_col="TimeLabel",
            title="3-response averages",
            default_cols=[
                "3-Response Average (Depression)",
                "3-Response Average (Mania)",
                "3-Response Average (Psychosis)",
                "3-Response Average (Mixed)",
            ],
            key_prefix="snapshot_3resp_avg",
            chart_type="line",
        )

        render_filtered_chart(
            snapshot_model_data,
            date_col="FilterDate",
            label_col="TimeLabel",
            title="Deviation from 3-response averages",
            default_cols=[
                "Deviation From 3-Response Average (Depression)",
                "Deviation From 3-Response Average (Mania)",
                "Deviation From 3-Response Average (Psychosis)",
                "Deviation From 3-Response Average (Mixed)",
            ],
            key_prefix="snapshot_deviation",
            chart_type="line",
        )

        st.markdown("### Snapshot model data")
        preview_cols = [
            c for c in [
                "Timestamp",
                "Depression Score",
                "Mania Score",
                "Psychosis Score",
                "Mixed Score",
                "3-Response Average (Depression)",
                "3-Response Average (Mania)",
                "3-Response Average (Psychosis)",
                "3-Response Average (Mixed)",
                "Deviation From 3-Response Average (Depression)",
                "Deviation From 3-Response Average (Mania)",
                "Deviation From 3-Response Average (Psychosis)",
                "Deviation From 3-Response Average (Mixed)",
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
        else:
            st.info("Pick at least one column to display.")


# =========================
# Snapshot Data
# =========================
with tab_snapshot_data:
    st.subheader("Snapshot Data")
    st.caption("Imported directly from Quick Form Responses.")

    if quick_form_data.empty:
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
                "Symptoms: [Very low or depressed mood] Numeric",
                "Symptoms: [Very high or elevated mood] Numeric",
                "Symptoms: [Paranoia or suspicion] Numeric",
                "Symptoms: [Very low or depressed mood] Trend",
                "Symptoms: [Very high or elevated mood] Trend",
                "Symptoms: [Paranoia or suspicion] Trend",
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
        else:
            st.info("Pick at least one column to display.")
