# =========================================================
# WELLBEING DASHBOARD
# =========================================================

# =========================
# Imports
# =========================
import streamlit as st
import pandas as pd
import gspread


# =========================
# Authentication
# =========================
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["authenticated"] = True
        else:
            st.session_state["authenticated"] = False

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
    else:
        return True


if not check_password():
    st.stop()


# =========================
# Page Configuration
# =========================
st.set_page_config(page_title="Wellbeing Dashboard", layout="wide")


# =========================
# Sheet Configuration
# =========================
SHEET_NAME = "Bipolar Dashboard"
FORM_TAB = "Form Responses"
MODEL_TAB = "Model"
QUICK_TAB = "Quick Form Responses"


# =========================
# Warning Sensitivity Settings
# =========================
DEFAULT_WARNING_SETTINGS = {
    "high_alert": 8,
    "low_alert": 3,
    "change_alert": 2.0,
    "mood_swing_alert": 2.5,
    "sleep_low_hours": 5.0,
    "sleep_drop_alert": 1.5,
}


# =========================
# Signal Groupings
# =========================
MANIA_SIGNAL_COLUMNS = [
    "Signals and indicators [Needed less sleep than usual without feeling tired]",
    "Signals and indicators [Started more activities than usual]",
    "Signals and indicators [Feel like I'm experiencing an up]",
    "Signals and indicators [Feel like I'm going to experience an up]",
]

DEPRESSION_SIGNAL_COLUMNS = [
    "Signals and indicators [Feel like I'm experiencing a down]",
    "Signals and indicators [Feel like I'm going to experience a down]",
    "Signals and indicators [Withdrew socially or emotionally from others]",
    "Signals and indicators [Avoided normal responsiblities]",
]

PARANOIA_SIGNAL_COLUMNS = [
    "Signals and indicators [Heard or saw something others didn't]",
    "Signals and indicators [Felt watched, followed, targeted]",
    "Signals and indicators [Felt something had special meaning for me]",
    "Signals and indicators [Trouble trusting perceptions and thoughts]",
]

MIXED_SIGNAL_COLUMNS = [
    "Signals and indicators [Feel like I'm experiencing a mixed]",
    "Signals and indicators [Feel like I'm going to experience a mixed]",
    "Signals and indicators [Noticed a sudden mood shift]",
    'Signals and indicators [Felt "not like myself"]',
]


# =========================
# Quick Response Groupings
# =========================
QUICK_DEPRESSION_COLUMNS = [
    "Symptoms: [Very low or depressed mood]",
    "Symptoms: [Somewhat low or depressed mood]",
    "Symptoms: [Social or emotional withdrawal]",
    "Symptoms: [Feeling slowed down]",
    "Symptoms: [Difficulty with self-care]",
]

QUICK_MANIA_COLUMNS = [
    "Symptoms: [Very high or elevated mood]",
    "Symptoms: [Somewhat high or elevated mood]",
    "Symptoms: [Agitation or restlessness]",
    "Symptoms: [Racing thoughts]",
    "Symptoms: [Driven to activity]",
]

QUICK_PSYCHOSIS_COLUMNS = [
    "Symptoms: [Hearing or seeing things that aren't there]",
    "Symptoms: [Paranoia or suspicion]",
    "Symptoms: [Firm belief in things others would not agree with]",
]


# =========================
# Google Sheets Access
# =========================
@st.cache_resource
def get_gspread_client():
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))


@st.cache_data(ttl=60)
def load_sheet(tab_name: str) -> pd.DataFrame:
    gc = get_gspread_client()
    sh = gc.open(SHEET_NAME)
    worksheet = sh.worksheet(tab_name)

    data = worksheet.get_all_values()

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

    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df["Date"] = df["Timestamp"].dt.date
        df = df.sort_values("Timestamp")

    return df


# =========================
# Data Conversion Helpers
# =========================
def convert_form_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    score_columns = [
        "Mood Score",
        "Sleep (hours)",
        "Sleep quality",
        "Energy",
        "Mental speed",
        "Impulsivity",
        "Motivation",
        "Unusual perceptions",
        "Suspiciousness",
        "Certainty and  belief in unusual ideas or things others don't believe",
    ]

    for col in score_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    signal_columns = [c for c in df.columns if c.startswith("Signals and indicators [")]

    for col in signal_columns:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["yes", "true", "1", "y", "checked"])
        )

    return df


def convert_model_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

    for col in df.columns:
        if col == "Date":
            continue

        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().any():
            df[col] = converted

    return df


def convert_quick_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df["Date"] = df["Timestamp"].dt.date

    quick_columns = (
        QUICK_DEPRESSION_COLUMNS + QUICK_MANIA_COLUMNS + QUICK_PSYCHOSIS_COLUMNS
    )

    def score_response(val):
        text = str(val).strip().lower()
        if text == "yes":
            return 2
        if text == "somewhat":
            return 1
        if text == "no":
            return 0
        return 0

    for col in quick_columns:
        if col in df.columns:
            df[col] = df[col].apply(score_response)

    return df


# =========================
# Daily Summary Builders
# =========================
def make_daily_form_data(df: pd.DataFrame) -> pd.DataFrame:
    if "Date" not in df.columns:
        return pd.DataFrame()

    score_columns = [
        c
        for c in [
            "Mood Score",
            "Sleep (hours)",
            "Sleep quality",
            "Energy",
            "Mental speed",
            "Impulsivity",
            "Motivation",
            "Unusual perceptions",
            "Suspiciousness",
            "Certainty and  belief in unusual ideas or things others don't believe",
        ]
        if c in df.columns
    ]

    signal_columns = [c for c in df.columns if c.startswith("Signals and indicators [")]

    agg_dict = {}

    for col in score_columns:
        agg_dict[col] = "mean"

    for col in signal_columns:
        agg_dict[col] = "sum"

    daily = df.groupby("Date", as_index=False).agg(agg_dict)

    if signal_columns:
        daily["Total Signals"] = daily[signal_columns].sum(axis=1)

    daily["DateLabel"] = pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")
    return daily


def make_daily_model_data(df: pd.DataFrame) -> pd.DataFrame:
    if "Date" not in df.columns:
        return pd.DataFrame()

    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    if not numeric_cols:
        return pd.DataFrame()

    daily = df.groupby("Date", as_index=False)[numeric_cols].mean()
    daily["DateLabel"] = pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")
    return daily


def make_quick_summary_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    depression_cols = [c for c in QUICK_DEPRESSION_COLUMNS if c in df.columns]
    mania_cols = [c for c in QUICK_MANIA_COLUMNS if c in df.columns]
    psychosis_cols = [c for c in QUICK_PSYCHOSIS_COLUMNS if c in df.columns]

    working = df.copy()

    working["Depression Score"] = (
        working[depression_cols].sum(axis=1) if depression_cols else 0
    )
    working["Mania Score"] = working[mania_cols].sum(axis=1) if mania_cols else 0
    working["Psychosis Score"] = (
        working[psychosis_cols].sum(axis=1) if psychosis_cols else 0
    )
    working["Overall Score"] = (
        working["Depression Score"]
        + working["Mania Score"]
        + working["Psychosis Score"]
    )

    if "Timestamp" in working.columns:
        working = working.sort_values("Timestamp")
        working["DateLabel"] = working["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
        return working[
            [
                "Timestamp",
                "DateLabel",
                "Overall Score",
                "Mania Score",
                "Depression Score",
                "Psychosis Score",
            ]
        ]

    if "Date" in working.columns:
        working = working.sort_values("Date")
        working["DateLabel"] = pd.to_datetime(working["Date"]).dt.strftime("%Y-%m-%d")
        return working[
            [
                "Date",
                "DateLabel",
                "Overall Score",
                "Mania Score",
                "Depression Score",
                "Psychosis Score",
            ]
        ]

    return pd.DataFrame()


def make_signal_cluster_totals(form_daily: pd.DataFrame) -> pd.Series:
    if form_daily.empty:
        return pd.Series(dtype=float)

    signal_columns = [c for c in form_daily.columns if c.startswith("Signals and indicators [")]

    def safe_sum(columns):
        available = [c for c in columns if c in form_daily.columns]
        if not available:
            return 0
        return form_daily[available].sum().sum()

    used = set(
        MANIA_SIGNAL_COLUMNS
        + DEPRESSION_SIGNAL_COLUMNS
        + PARANOIA_SIGNAL_COLUMNS
        + MIXED_SIGNAL_COLUMNS
    )
    other_columns = [c for c in signal_columns if c not in used]

    cluster_totals = pd.Series(
        {
            "Mania": safe_sum(MANIA_SIGNAL_COLUMNS),
            "Depression": safe_sum(DEPRESSION_SIGNAL_COLUMNS),
            "Paranoia": safe_sum(PARANOIA_SIGNAL_COLUMNS),
            "Mixed": safe_sum(MIXED_SIGNAL_COLUMNS),
            "Other": safe_sum(other_columns),
        }
    )

    return cluster_totals[cluster_totals > 0]


def make_model_cluster_data(model_daily: pd.DataFrame) -> pd.DataFrame:
    if model_daily.empty:
        return pd.DataFrame()

    working = model_daily.copy()

    working["Mania Cluster"] = (
        working["Mania Score"] if "Mania Score" in working.columns else 0
    )
    working["Depression Cluster"] = (
        working["Depression Score"] if "Depression Score" in working.columns else 0
    )
    working["Paranoia Cluster"] = (
        working["Psychosis Score"] if "Psychosis Score" in working.columns else 0
    )
    working["Mixed Cluster"] = (
        working["Instability Score"] if "Instability Score" in working.columns else 0
    )

    used_columns = {
        "Date",
        "DateLabel",
        "Date (int)",
        "Mania Score",
        "Depression Score",
        "Psychosis Score",
        "Instability Score",
    }

    other_numeric = [
        c
        for c in working.select_dtypes(include="number").columns
        if c not in used_columns
    ]

    if other_numeric:
        working["Other Cluster"] = working[other_numeric].mean(axis=1)
    else:
        working["Other Cluster"] = 0

    cluster_cols = [
        "Mania Cluster",
        "Depression Cluster",
        "Paranoia Cluster",
        "Mixed Cluster",
        "Other Cluster",
    ]

    return working[["DateLabel"] + cluster_cols]


# =========================
# Utility Helpers
# =========================
def latest_value(df: pd.DataFrame, col: str):
    if col not in df.columns or df.empty:
        return None
    s = df[col].dropna()
    if s.empty:
        return None
    return s.iloc[-1]


def previous_avg(df: pd.DataFrame, col: str, n: int = 3):
    if col not in df.columns or df.empty:
        return None
    s = df[col].dropna()
    if len(s) <= n:
        return None
    prev = s.iloc[:-1].tail(n)
    if prev.empty:
        return None
    return prev.mean()


def bool_latest(df: pd.DataFrame, col: str) -> bool:
    if col not in df.columns or df.empty:
        return False
    s = df[col].dropna()
    if s.empty:
        return False
    return bool(s.iloc[-1])


def clamp_score(x: float) -> int:
    return int(max(0, min(100, round(x))))


def risk_label(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Moderate"
    return "Low"


def risk_color(score: int) -> str:
    if score >= 70:
        return "#d32f2f"
    if score >= 40:
        return "#f9a825"
    return "#2e7d32"


# =========================
# UI Rendering Helpers
# =========================
def render_banner(title: str, score: int):
    color = risk_color(score)
    label = risk_label(score)

    st.markdown(
        f"""
        <div style="
            background-color: {color};
            color: white;
            padding: 18px;
            border-radius: 12px;
            text-align: center;
            font-weight: bold;
            font-size: 22px;
            margin-bottom: 10px;
        ">
            {title}: {label} ({score}/100)
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_settings_panel():
    st.markdown("## Warning Settings")

    with st.expander("Edit warning thresholds"):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.session_state["warning_settings"]["high_alert"] = st.number_input(
                "High score alert threshold",
                min_value=1,
                max_value=10,
                value=int(st.session_state["warning_settings"]["high_alert"]),
                step=1,
            )
            st.session_state["warning_settings"]["low_alert"] = st.number_input(
                "Low score alert threshold",
                min_value=1,
                max_value=10,
                value=int(st.session_state["warning_settings"]["low_alert"]),
                step=1,
            )

        with c2:
            st.session_state["warning_settings"]["change_alert"] = st.number_input(
                "Score change alert threshold",
                min_value=0.5,
                max_value=5.0,
                value=float(st.session_state["warning_settings"]["change_alert"]),
                step=0.5,
            )
            st.session_state["warning_settings"]["mood_swing_alert"] = st.number_input(
                "Mood swing alert threshold",
                min_value=0.5,
                max_value=5.0,
                value=float(st.session_state["warning_settings"]["mood_swing_alert"]),
                step=0.5,
            )

        with c3:
            st.session_state["warning_settings"]["sleep_low_hours"] = st.number_input(
                "Low sleep threshold (hours)",
                min_value=0.0,
                max_value=12.0,
                value=float(st.session_state["warning_settings"]["sleep_low_hours"]),
                step=0.5,
            )
            st.session_state["warning_settings"]["sleep_drop_alert"] = st.number_input(
                "Sleep drop alert threshold",
                min_value=0.5,
                max_value=5.0,
                value=float(st.session_state["warning_settings"]["sleep_drop_alert"]),
                step=0.5,
            )


# =========================
# Warning Score Logic
# =========================
def build_warning_scores(form_daily: pd.DataFrame, settings: dict) -> dict:
    if form_daily.empty:
        return {
            "up_score": 0,
            "down_score": 0,
            "mixed_score": 0,
            "reasons_up": [],
            "reasons_down": [],
            "reasons_mixed": [],
        }

    up_score = 0
    down_score = 0
    mixed_score = 0

    reasons_up = []
    reasons_down = []
    reasons_mixed = []

    latest_sleep = latest_value(form_daily, "Sleep (hours)")
    latest_sleep_quality = latest_value(form_daily, "Sleep quality")
    latest_energy = latest_value(form_daily, "Energy")
    latest_speed = latest_value(form_daily, "Mental speed")
    latest_impulsivity = latest_value(form_daily, "Impulsivity")
    latest_mood = latest_value(form_daily, "Mood Score")
    latest_motivation = latest_value(form_daily, "Motivation")
    latest_unusual = latest_value(form_daily, "Unusual perceptions")
    latest_suspicious = latest_value(form_daily, "Suspiciousness")
    latest_total_signals = latest_value(form_daily, "Total Signals")

    prev_sleep = previous_avg(form_daily, "Sleep (hours)", 3)
    prev_energy = previous_avg(form_daily, "Energy", 3)
    prev_speed = previous_avg(form_daily, "Mental speed", 3)
    prev_impulsivity = previous_avg(form_daily, "Impulsivity", 3)
    prev_mood = previous_avg(form_daily, "Mood Score", 3)
    prev_motivation = previous_avg(form_daily, "Motivation", 3)
    prev_sleep_quality = previous_avg(form_daily, "Sleep quality", 3)

    less_sleep_flag = bool_latest(
        form_daily,
        "Signals and indicators [Needed less sleep than usual without feeling tired]",
    )
    more_activity_flag = bool_latest(
        form_daily,
        "Signals and indicators [Started more activities than usual]",
    )
    up_now_flag = bool_latest(
        form_daily,
        "Signals and indicators [Feel like I'm experiencing an up]",
    )
    up_coming_flag = bool_latest(
        form_daily,
        "Signals and indicators [Feel like I'm going to experience an up]",
    )

    down_now_flag = bool_latest(
        form_daily,
        "Signals and indicators [Feel like I'm experiencing a down]",
    )
    down_coming_flag = bool_latest(
        form_daily,
        "Signals and indicators [Feel like I'm going to experience a down]",
    )

    mixed_now_flag = bool_latest(
        form_daily,
        "Signals and indicators [Feel like I'm experiencing a mixed]",
    )
    mixed_coming_flag = bool_latest(
        form_daily,
        "Signals and indicators [Feel like I'm going to experience a mixed]",
    )

    withdraw_flag = bool_latest(
        form_daily,
        "Signals and indicators [Withdrew socially or emotionally from others]",
    )
    avoid_flag = bool_latest(
        form_daily,
        "Signals and indicators [Avoided normal responsiblities]",
    )
    mood_shift_flag = bool_latest(
        form_daily,
        "Signals and indicators [Noticed a sudden mood shift]",
    )
    not_myself_flag = bool_latest(
        form_daily,
        'Signals and indicators [Felt "not like myself"]',
    )

    heard_saw_flag = bool_latest(
        form_daily,
        "Signals and indicators [Heard or saw something others didn't]",
    )
    watched_flag = bool_latest(
        form_daily,
        "Signals and indicators [Felt watched, followed, targeted]",
    )
    special_meaning_flag = bool_latest(
        form_daily,
        "Signals and indicators [Felt something had special meaning for me]",
    )
    trust_thoughts_flag = bool_latest(
        form_daily,
        "Signals and indicators [Trouble trusting perceptions and thoughts]",
    )

    psychosis_flags = [
        heard_saw_flag,
        watched_flag,
        special_meaning_flag,
        trust_thoughts_flag,
    ]
    psychosis_count = sum(psychosis_flags)

    HIGH_ALERT = settings["high_alert"]
    LOW_ALERT = settings["low_alert"]
    CHANGE_ALERT = settings["change_alert"]
    MOOD_SWING_ALERT = settings["mood_swing_alert"]
    SLEEP_LOW_HOURS = settings["sleep_low_hours"]
    SLEEP_DROP_ALERT = settings["sleep_drop_alert"]

    if latest_sleep is not None and latest_sleep <= SLEEP_LOW_HOURS:
        up_score += 18
        reasons_up.append("Sleep is clearly reduced")

    if latest_sleep is not None and prev_sleep is not None and latest_sleep <= prev_sleep - SLEEP_DROP_ALERT:
        up_score += 22
        reasons_up.append("Sleep dropped sharply versus recent days")

    if less_sleep_flag:
        up_score += 24
        reasons_up.append("Needed less sleep without feeling tired")

    if latest_energy is not None and latest_energy >= HIGH_ALERT:
        up_score += 14
        reasons_up.append("Energy is very elevated")

    if latest_energy is not None and prev_energy is not None and latest_energy >= prev_energy + CHANGE_ALERT:
        up_score += 16
        reasons_up.append("Energy increased sharply versus recent days")

    if latest_speed is not None and latest_speed >= HIGH_ALERT:
        up_score += 12
        reasons_up.append("Mental speed is very elevated")

    if latest_speed is not None and prev_speed is not None and latest_speed >= prev_speed + CHANGE_ALERT:
        up_score += 14
        reasons_up.append("Mental speed increased sharply versus recent days")

    if latest_impulsivity is not None and latest_impulsivity >= HIGH_ALERT:
        up_score += 14
        reasons_up.append("Impulsivity is very elevated")

    if latest_impulsivity is not None and prev_impulsivity is not None and latest_impulsivity >= prev_impulsivity + CHANGE_ALERT:
        up_score += 14
        reasons_up.append("Impulsivity increased sharply versus recent days")

    if more_activity_flag:
        up_score += 18
        reasons_up.append("Started more activities than usual")

    if mood_shift_flag:
        up_score += 8
        reasons_up.append("Sudden mood shift was flagged")

    if up_now_flag:
        up_score += 28
        reasons_up.append("You marked that you're experiencing an up")

    if up_coming_flag:
        up_score += 24
        reasons_up.append("You marked that an up may be coming")

    if psychosis_count >= 1:
        up_score += 10
        reasons_up.append("Psychosis-like symptoms are present")

    if psychosis_count >= 2:
        up_score += 12
        reasons_up.append("Multiple psychosis-like symptoms are present")

    if latest_unusual is not None and latest_unusual >= HIGH_ALERT:
        up_score += 8
        reasons_up.append("Unusual perceptions are very elevated")

    if latest_suspicious is not None and latest_suspicious >= HIGH_ALERT:
        up_score += 8
        reasons_up.append("Suspiciousness is very elevated")

    if latest_mood is not None and latest_mood <= LOW_ALERT:
        down_score += 20
        reasons_down.append("Mood score is clearly low")

    if latest_mood is not None and prev_mood is not None and latest_mood <= prev_mood - CHANGE_ALERT:
        down_score += 15
        reasons_down.append("Mood dropped sharply versus recent days")

    if latest_energy is not None and latest_energy <= LOW_ALERT:
        down_score += 15
        reasons_down.append("Energy is clearly low")

    if latest_motivation is not None and latest_motivation <= LOW_ALERT:
        down_score += 18
        reasons_down.append("Motivation is clearly low")

    if latest_motivation is not None and prev_motivation is not None and latest_motivation <= prev_motivation - CHANGE_ALERT:
        down_score += 12
        reasons_down.append("Motivation dropped sharply versus recent days")

    if withdraw_flag:
        down_score += 15
        reasons_down.append("Withdrawal was flagged")

    if avoid_flag:
        down_score += 15
        reasons_down.append("Avoided normal responsibilities")

    if down_now_flag:
        down_score += 25
        reasons_down.append("You marked that you're experiencing a down")

    if down_coming_flag:
        down_score += 20
        reasons_down.append("You marked that a down may be coming")

    if latest_sleep is not None and latest_sleep <= SLEEP_LOW_HOURS:
        mixed_score += 14
        reasons_mixed.append("Sleep is clearly reduced")

    if latest_sleep is not None and prev_sleep is not None and latest_sleep <= prev_sleep - SLEEP_DROP_ALERT:
        mixed_score += 16
        reasons_mixed.append("Sleep dropped sharply versus recent days")

    if latest_sleep_quality is not None and latest_sleep_quality <= LOW_ALERT:
        mixed_score += 12
        reasons_mixed.append("Sleep quality is clearly poor")

    if latest_sleep_quality is not None and prev_sleep_quality is not None and latest_sleep_quality <= prev_sleep_quality - CHANGE_ALERT:
        mixed_score += 10
        reasons_mixed.append("Sleep quality worsened sharply versus recent days")

    if mood_shift_flag:
        mixed_score += 18
        reasons_mixed.append("Sudden mood shift was flagged")

    if not_myself_flag:
        mixed_score += 16
        reasons_mixed.append('You flagged feeling "not like myself"')

    if up_now_flag or up_coming_flag:
        mixed_score += 10
        reasons_mixed.append("Up-type warning signs are present")

    if down_now_flag or down_coming_flag:
        mixed_score += 10
        reasons_mixed.append("Down-type warning signs are present")

    if (up_now_flag or up_coming_flag) and (down_now_flag or down_coming_flag):
        mixed_score += 24
        reasons_mixed.append("Both up-type and down-type warning signs are present")

    if latest_mood is not None and prev_mood is not None and abs(latest_mood - prev_mood) >= MOOD_SWING_ALERT:
        mixed_score += 14
        reasons_mixed.append("Mood shifted strongly versus recent days")

    if latest_impulsivity is not None and latest_impulsivity >= HIGH_ALERT:
        mixed_score += 10
        reasons_mixed.append("Impulsivity is very elevated")

    if psychosis_count >= 1:
        mixed_score += 10
        reasons_mixed.append("Psychosis-like symptoms are present")

    if psychosis_count >= 2:
        mixed_score += 14
        reasons_mixed.append("Multiple psychosis-like symptoms are present")

    if latest_unusual is not None and latest_unusual >= HIGH_ALERT:
        mixed_score += 8
        reasons_mixed.append("Unusual perceptions are very elevated")

    if latest_suspicious is not None and latest_suspicious >= HIGH_ALERT:
        mixed_score += 8
        reasons_mixed.append("Suspiciousness is very elevated")

    if latest_total_signals is not None and latest_total_signals >= 4:
        mixed_score += 12
        reasons_mixed.append("Several warning signals were flagged today")

    if mixed_now_flag:
        mixed_score += 28
        reasons_mixed.append("You marked that you're experiencing a mixed state")

    if mixed_coming_flag:
        mixed_score += 22
        reasons_mixed.append("You marked that a mixed state may be coming")

    return {
        "up_score": clamp_score(up_score),
        "down_score": clamp_score(down_score),
        "mixed_score": clamp_score(mixed_score),
        "reasons_up": reasons_up[:5],
        "reasons_down": reasons_down[:5],
        "reasons_mixed": reasons_mixed[:5],
    }


def latest_signal_summary(form_daily: pd.DataFrame) -> dict:
    if form_daily.empty:
        return {
            "all_pct": 0.0,
            "mania_pct": 0.0,
            "depression_pct": 0.0,
            "psychosis_pct": 0.0,
            "all_count": 0,
            "all_total": 0,
            "mania_count": 0,
            "mania_total": 0,
            "depression_count": 0,
            "depression_total": 0,
            "psychosis_count": 0,
            "psychosis_total": 0,
        }

    latest_row = form_daily.iloc[-1]
    signal_columns = [c for c in form_daily.columns if c.startswith("Signals and indicators [")]

    def count_flagged(columns):
        available = [c for c in columns if c in form_daily.columns]
        if not available:
            return 0, 0
        count = sum(bool(latest_row[c]) for c in available)
        return count, len(available)

    all_count, all_total = count_flagged(signal_columns)
    mania_count, mania_total = count_flagged(MANIA_SIGNAL_COLUMNS)
    depression_count, depression_total = count_flagged(DEPRESSION_SIGNAL_COLUMNS)
    psychosis_count, psychosis_total = count_flagged(PARANOIA_SIGNAL_COLUMNS)

    def pct(count, total):
        if total == 0:
            return 0.0
        return 100 * count / total

    return {
        "all_pct": pct(all_count, all_total),
        "mania_pct": pct(mania_count, mania_total),
        "depression_pct": pct(depression_count, depression_total),
        "psychosis_pct": pct(psychosis_count, psychosis_total),
        "all_count": all_count,
        "all_total": all_total,
        "mania_count": mania_count,
        "mania_total": mania_total,
        "depression_count": depression_count,
        "depression_total": depression_total,
        "psychosis_count": psychosis_count,
        "psychosis_total": psychosis_total,
    }


# =========================
# Session State Initialization
# =========================
if "warning_settings" not in st.session_state:
    st.session_state["warning_settings"] = DEFAULT_WARNING_SETTINGS.copy()


# =========================
# Load and Prepare Data
# =========================
form_df = convert_form_data(load_sheet(FORM_TAB))
model_df = convert_model_data(load_sheet(MODEL_TAB))
quick_df = convert_quick_data(load_sheet(QUICK_TAB))

form_daily = make_daily_form_data(form_df)
model_daily = make_daily_model_data(model_df)
quick_summary = make_quick_summary_data(quick_df)
model_cluster_data = make_model_cluster_data(model_daily)

render_settings_panel()

warning_scores = build_warning_scores(form_daily, st.session_state["warning_settings"])
signal_summary = latest_signal_summary(form_daily)
signal_cluster_totals = make_signal_cluster_totals(form_daily)


# =========================
# Dashboard Header
# =========================
st.title("Wellbeing Dashboard")

top1, top2, top3, top4 = st.columns(4)

top1.metric("Form entries", len(form_df))
top2.metric("Days tracked", len(form_daily) if not form_daily.empty else 0)
top3.metric(
    "Average Mood",
    f"{form_df['Mood Score'].mean():.1f}" if "Mood Score" in form_df.columns else "N/A",
)
top4.metric(
    "Average Sleep",
    f"{form_df['Sleep (hours)'].mean():.1f} hrs"
    if "Sleep (hours)" in form_df.columns
    else "N/A",
)


# =========================
# Current Warning Status
# =========================
st.markdown("## Current Warning Status")
b1, b2, b3 = st.columns(3)

with b1:
    render_banner("Up / Mania Risk", warning_scores["up_score"])

with b2:
    render_banner("Down / Depression Risk", warning_scores["down_score"])

with b3:
    render_banner("Mixed / Instability Risk", warning_scores["mixed_score"])


# =========================
# Dashboard Tabs
# =========================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "Daily Trends",
        "Signals by Day",
        "Warnings",
        "Model",
        "Quick Responses",
        "Form Data",
        "Model Data",
    ]
)


# =========================
# Tab 1: Daily Trends
# =========================
with tab1:
    st.subheader("Daily trends from Form Responses")

    if not form_daily.empty:
        score_columns = [
            c
            for c in [
                "Mood Score",
                "Sleep (hours)",
                "Sleep quality",
                "Energy",
                "Mental speed",
                "Impulsivity",
                "Motivation",
                "Unusual perceptions",
                "Suspiciousness",
                "Certainty and  belief in unusual ideas or things others don't believe",
            ]
            if c in form_daily.columns
        ]

        selected = st.multiselect(
            "Choose scores",
            score_columns,
            default=[
                c
                for c in ["Mood Score", "Sleep (hours)", "Energy", "Motivation"]
                if c in score_columns
            ],
        )

        if selected:
            chart_df = form_daily[["DateLabel"] + selected].set_index("DateLabel")
            st.line_chart(chart_df)
        else:
            st.info("Pick at least one score.")
    else:
        st.info("No daily form data available.")


# =========================
# Tab 2: Signals by Day
# =========================
with tab2:
    st.subheader("Signals by day")
    st.markdown("### Latest signal summary")

    s1, s2, s3, s4 = st.columns(4)

    s1.metric(
        "All signals flagged",
        f"{signal_summary['all_pct']:.0f}%",
        f"{signal_summary['all_count']}/{signal_summary['all_total']}",
    )
    s2.metric(
        "Mania-associated",
        f"{signal_summary['mania_pct']:.0f}%",
        f"{signal_summary['mania_count']}/{signal_summary['mania_total']}",
    )
    s3.metric(
        "Depression-associated",
        f"{signal_summary['depression_pct']:.0f}%",
        f"{signal_summary['depression_count']}/{signal_summary['depression_total']}",
    )
    s4.metric(
        "Paranoia-associated",
        f"{signal_summary['psychosis_pct']:.0f}%",
        f"{signal_summary['psychosis_count']}/{signal_summary['psychosis_total']}",
    )

    if not form_daily.empty:
        signal_columns = [c for c in form_daily.columns if c.startswith("Signals and indicators [")]

        if "Total Signals" in form_daily.columns:
            st.markdown("### Total signals per day")
            total_signals_df = form_daily[["DateLabel", "Total Signals"]].set_index("DateLabel")
            st.bar_chart(total_signals_df)

        if not signal_cluster_totals.empty:
            st.markdown("### Signal totals by association")
            st.bar_chart(signal_cluster_totals)

        totals = form_daily[signal_columns].sum().sort_values(ascending=False)
        totals = totals[totals > 0]

        if not totals.empty:
            totals.index = [
                c.replace("Signals and indicators [", "").replace("]", "")
                for c in totals.index
            ]
            st.markdown("### Signal totals")
            st.bar_chart(totals)
    else:
        st.info("No signal data available.")


# =========================
# Tab 3: Warnings
# =========================
with tab3:
    st.subheader("Predictive warnings from current data")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Up / Mania Risk",
        f"{warning_scores['up_score']}/100",
        risk_label(warning_scores["up_score"]),
    )
    c2.metric(
        "Down / Depression Risk",
        f"{warning_scores['down_score']}/100",
        risk_label(warning_scores["down_score"]),
    )
    c3.metric(
        "Mixed / Instability Risk",
        f"{warning_scores['mixed_score']}/100",
        risk_label(warning_scores["mixed_score"]),
    )

    st.markdown("### Traffic light summary")
    t1, t2, t3 = st.columns(3)

    with t1:
        render_banner("Up / Mania", warning_scores["up_score"])
    with t2:
        render_banner("Down / Depression", warning_scores["down_score"])
    with t3:
        render_banner("Mixed / Instability", warning_scores["mixed_score"])

    st.markdown("### Why these warnings are showing")
    left, middle, right = st.columns(3)

    with left:
        st.markdown("**Up / Mania reasons**")
        if warning_scores["reasons_up"]:
            for reason in warning_scores["reasons_up"]:
                st.write(f"- {reason}")
        else:
            st.write("No strong up-type warnings today.")

    with middle:
        st.markdown("**Down / Depression reasons**")
        if warning_scores["reasons_down"]:
            for reason in warning_scores["reasons_down"]:
                st.write(f"- {reason}")
        else:
            st.write("No strong down-type warnings today.")

    with right:
        st.markdown("**Mixed / Instability reasons**")
        if warning_scores["reasons_mixed"]:
            for reason in warning_scores["reasons_mixed"]:
                st.write(f"- {reason}")
        else:
            st.write("No strong mixed-state warnings today.")

    st.info(
        "These warnings are based on your self-tracked patterns and are therefore almost entirely subjective. "
        "They should be taken seriously, but do not allow them to override your judgement or that of those close to you."
    )


# =========================
# Tab 4: Model
# =========================
with tab4:
    st.subheader("Model tab")

    if not model_daily.empty:
        model_numeric = [c for c in model_daily.columns if c not in ["Date", "DateLabel"]]

        selected_model_cols = st.multiselect(
            "Choose model columns",
            model_numeric,
            default=model_numeric[:3] if len(model_numeric) >= 3 else model_numeric,
        )

        if selected_model_cols:
            model_chart_df = model_daily[["DateLabel"] + selected_model_cols].set_index("DateLabel")
            st.line_chart(model_chart_df)

        if not model_cluster_data.empty:
            st.markdown("### Model clusters")
            cluster_chart_df = model_cluster_data.set_index("DateLabel")
            st.line_chart(cluster_chart_df)

        st.markdown("### Daily model data")
        st.dataframe(model_daily, use_container_width=True)
    else:
        st.info("The Model tab loaded, but I couldn't find daily numeric columns to chart.")


# =========================
# Tab 5: Quick Responses
# =========================
with tab5:
    st.subheader("Quick form responses")

    if not quick_summary.empty:
        st.markdown("### Overall symptom load")
        overall_chart = quick_summary[["DateLabel", "Overall Score"]].set_index("DateLabel")
        st.line_chart(overall_chart)

        q1, q2, q3 = st.columns(3)

        with q1:
            st.markdown("### Mania")
            mania_chart = quick_summary[["DateLabel", "Mania Score"]].set_index("DateLabel")
            st.line_chart(mania_chart)

        with q2:
            st.markdown("### Depression")
            depression_chart = quick_summary[["DateLabel", "Depression Score"]].set_index("DateLabel")
            st.line_chart(depression_chart)

        with q3:
            st.markdown("### Psychosis")
            psychosis_chart = quick_summary[["DateLabel", "Psychosis Score"]].set_index("DateLabel")
            st.line_chart(psychosis_chart)

        st.markdown("### Quick response data")
        st.dataframe(quick_summary, use_container_width=True)
    else:
        st.info("No quick form response data available.")


# =========================
# Tab 6: Raw Form Data
# =========================
with tab6:
    st.subheader("Raw Form Responses")
    st.dataframe(form_df, use_container_width=True)


# =========================
# Tab 7: Raw Model Data
# =========================
with tab7:
    st.subheader("Raw Model Data")
    st.dataframe(model_df, use_container_width=True)
