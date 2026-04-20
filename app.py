import streamlit as st
import pandas as pd
import gspread
from typing import Any

st.set_page_config(page_title="Wellbeing Dashboard", layout="wide")
st.title("Wellbeing Dashboard")
st.caption("Data-model foundation for rebuilding the dashboard from scratch.")


# =========================================================
# AUTHENTICATION
# =========================================================
def check_password() -> bool:
    def password_entered() -> None:
        st.session_state["authenticated"] = (
            st.session_state["password"] == st.secrets["auth"]["password"]
        )

    if not st.session_state.get("authenticated", False):
        st.text_input(
            "Enter password",
            type="password",
            on_change=password_entered,
            key="password",
        )
        if "authenticated" in st.session_state:
            st.error("Wrong password")
        return False
    return True


if not check_password():
    st.stop()


# =========================================================
# GOOGLE SHEETS
# =========================================================
SHEET_NAME = "Bipolar Dashboard"
NEW_FORM_TAB = "Updated Bipolar Form"


@st.cache_resource
def get_gspread_client() -> gspread.Client:
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))


@st.cache_resource
def get_workbook() -> gspread.Spreadsheet:
    return get_gspread_client().open(SHEET_NAME)


@st.cache_data(ttl=60)
def load_sheet(tab_name: str) -> pd.DataFrame:
    values = get_workbook().worksheet(tab_name).get_all_values()
    if not values:
        return pd.DataFrame()

    headers = [str(h).strip() if h else f"Unnamed_{i + 1}" for i, h in enumerate(values[0])]
    return pd.DataFrame(values[1:], columns=headers)


# =========================================================
# QUESTION DEFINITIONS
# =========================================================
QUESTION_CATALOG = [
    {
        "question_code": "dep_low_mood",
        "question_text": "Have I felt a low mood?",
        "group_name": "depression",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 10,
    },
    {
        "question_code": "dep_slowed_low_energy",
        "question_text": "Have I felt slowed down or low on energy?",
        "group_name": "depression",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 20,
    },
    {
        "question_code": "dep_low_motivation",
        "question_text": "Have I felt low on motivation or had difficulty initiating tasks?",
        "group_name": "depression",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 30,
    },
    {
        "question_code": "dep_anhedonia",
        "question_text": "Have I felt a lack of interest or pleasure in activities?",
        "group_name": "depression",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 40,
    },
    {
        "question_code": "dep_withdrawal",
        "question_text": "Have I been socially or emotionally withdrawn?",
        "group_name": "depression",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 50,
    },
    {
        "question_code": "dep_self_harm_ideation",
        "question_text": "Have I had ideation around self-harming or suicidal behaviours?",
        "group_name": "depression",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 60,
    },
    {
        "question_code": "man_elevated_mood",
        "question_text": "Have I felt an elevated mood?",
        "group_name": "mania",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 70,
    },
    {
        "question_code": "man_sped_up_high_energy",
        "question_text": "Have I felt sped up or high on energy?",
        "group_name": "mania",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 80,
    },
    {
        "question_code": "man_racing_thoughts",
        "question_text": "Have I had racing thoughts or speech?",
        "group_name": "mania",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 90,
    },
    {
        "question_code": "man_goal_drive",
        "question_text": "Have I had an increased drive towards goal-directed activity or a sense that I must be 'doing things' at all times?",
        "group_name": "mania",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 100,
    },
    {
        "question_code": "man_impulsivity",
        "question_text": "Have I felt impulsivity or an urge to take risky actions?",
        "group_name": "mania",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 110,
    },
    {
        "question_code": "man_agitation",
        "question_text": "Have I felt agitated or restless?",
        "group_name": "mania",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 120,
    },
    {
        "question_code": "man_irritability",
        "question_text": "Have I been more irritable and reactive than normal?",
        "group_name": "mania",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 130,
    },
    {
        "question_code": "man_cant_settle",
        "question_text": "Have I been unable to settle or switch off?",
        "group_name": "mania",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 140,
    },
    {
        "question_code": "mix_high_energy_low_mood",
        "question_text": "Have I had a high energy combined with low mood?",
        "group_name": "mixed",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 150,
    },
    {
        "question_code": "mix_rapid_emotional_shifts",
        "question_text": "Have I experienced rapid emotional shifts?",
        "group_name": "mixed",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 160,
    },
    {
        "question_code": "psy_heard_saw",
        "question_text": "Have I heard or seen things others didn't?",
        "group_name": "psychosis",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 170,
    },
    {
        "question_code": "psy_suspicious",
        "question_text": "Have I felt watched, followed, targeted or suspicious?",
        "group_name": "psychosis",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 180,
    },
    {
        "question_code": "psy_trust_perceptions",
        "question_text": "Have I had trouble trusting my perceptions and thoughts?",
        "group_name": "psychosis",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 190,
    },
    {
        "question_code": "psy_confidence_reality",
        "question_text": "How confident have I been in the reality of these experiences?",
        "group_name": "psychosis",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 200,
    },
    {
        "question_code": "psy_distress",
        "question_text": "How distressed have I been by these beliefs and experiences?",
        "group_name": "psychosis",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 210,
    },
    {
        "question_code": "func_work",
        "question_text": "How effectively have I been functioning at work?",
        "group_name": "functioning",
        "response_type": "scale_1_5",
        "polarity": "higher_better",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 220,
    },
    {
        "question_code": "func_daily",
        "question_text": "How well have I been functioning in my daily life?",
        "group_name": "functioning",
        "response_type": "scale_1_5",
        "polarity": "higher_better",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 230,
    },
    {
        "question_code": "meta_unlike_self",
        "question_text": "Do I feel unlike my usual self?",
        "group_name": "meta",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 240,
    },
    {
        "question_code": "meta_something_wrong",
        "question_text": "Do I think something may be wrong or changing?",
        "group_name": "meta",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 250,
    },
    {
        "question_code": "meta_concerned",
        "question_text": "Am I concerned about my current state?",
        "group_name": "meta",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 260,
    },
    {
        "question_code": "meta_disorganised_thoughts",
        "question_text": "Do my thoughts feel disorganised or hard to follow?",
        "group_name": "meta",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 270,
    },
    {
        "question_code": "meta_attention_unstable",
        "question_text": "Is my attention unstable or jumping?",
        "group_name": "meta",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 280,
    },
    {
        "question_code": "meta_driven_without_thinking",
        "question_text": "Do I feel driven to act without thinking?",
        "group_name": "meta",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 290,
    },
    {
        "question_code": "meta_intensifying",
        "question_text": "Is my state intensifying (in any direction)?",
        "group_name": "meta",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 300,
    },
    {
        "question_code": "meta_towards_episode",
        "question_text": "Do I feel like I'm moving towards an episode?",
        "group_name": "meta",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 310,
    },
    {
        "question_code": "flag_not_myself",
        "question_text": "I've been feeling \"not like myself\"",
        "group_name": "flags",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 320,
    },
    {
        "question_code": "flag_mood_shift",
        "question_text": "I noticed a sudden mood shift",
        "group_name": "flags",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 330,
    },
    {
        "question_code": "flag_missed_medication",
        "question_text": "I missed medication",
        "group_name": "flags",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 340,
    },
    {
        "question_code": "flag_sleep_medication",
        "question_text": "I took sleeping or anti-anxiety medication",
        "group_name": "flags",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 350,
    },
    {
        "question_code": "flag_routine_disruption",
        "question_text": "There were significant disruptions to my routine",
        "group_name": "flags",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 360,
    },
    {
        "question_code": "flag_physiological_stress",
        "question_text": "I had a major physiological stress",
        "group_name": "flags",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 370,
    },
    {
        "question_code": "flag_psychological_stress",
        "question_text": "I had a major psychological stress",
        "group_name": "flags",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 380,
    },
    {
        "question_code": "obs_up_now",
        "question_text": "Observations [I feel like I'm experiencing an up]",
        "group_name": "observations",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 390,
    },
    {
        "question_code": "obs_down_now",
        "question_text": "Observations [I feel like I'm experiencing a down]",
        "group_name": "observations",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 400,
    },
    {
        "question_code": "obs_mixed_now",
        "question_text": "Observations [I feel like I'm experiencing a mixed]",
        "group_name": "observations",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 410,
    },
    {
        "question_code": "obs_up_coming",
        "question_text": "Observations [I feel like I'm going to experience an up]",
        "group_name": "observations",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 420,
    },
    {
        "question_code": "obs_down_coming",
        "question_text": "Observations [I feel like I'm going to experience a down]",
        "group_name": "observations",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 430,
    },
    {
        "question_code": "obs_mixed_coming",
        "question_text": "Observations [I feel like I'm going to experience a mixed]",
        "group_name": "observations",
        "response_type": "boolean_yes_no",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": True,
        "display_order": 440,
    },
    {
        "question_code": "func_sleep_hours",
        "question_text": "How many hours did I sleep last night?",
        "group_name": "functioning",
        "response_type": "numeric",
        "polarity": "custom_numeric",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": False,
        "display_order": 450,
    },
    {
        "question_code": "func_sleep_quality",
        "question_text": "How poor was my sleep quality last night",
        "group_name": "functioning",
        "response_type": "scale_1_5",
        "polarity": "higher_worse",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": False,
        "display_order": 460,
    },
    {
        "question_code": "experience_description",
        "question_text": "How would I describe my experiences?",
        "group_name": "notes",
        "response_type": "text",
        "polarity": "not_applicable",
        "used_in_daily_model": True,
        "used_in_snapshot_model": True,
        "used_in_snapshot_scoring": False,
        "display_order": 470,
    },
]


# =========================================================
# SETTINGS + SCORING CONFIG
# =========================================================
SETTINGS_TAB = "Scoring Settings"
DEFAULT_WEIGHTS = {
    "dep_low_mood": 3.0,
    "dep_slowed_low_energy": 1.5,
    "dep_low_motivation": 2.0,
    "dep_anhedonia": 2.0,
    "dep_withdrawal": 1.0,
    "dep_self_harm_ideation": 4.0,
    "man_elevated_mood": 2.0,
    "man_sped_up_high_energy": 1.5,
    "man_racing_thoughts": 1.5,
    "man_goal_drive": 1.5,
    "man_impulsivity": 2.0,
    "man_agitation": 1.5,
    "man_irritability": 1.5,
    "man_cant_settle": 1.0,
    "mix_high_energy_low_mood": 3.0,
    "mix_rapid_emotional_shifts": 2.0,
    "psy_heard_saw": 2.0,
    "psy_suspicious": 1.5,
    "psy_trust_perceptions": 1.5,
    "psy_confidence_reality": 2.0,
    "psy_distress": 1.5,
    "func_work": 1.0,
    "func_daily": 1.0,
    "func_sleep_quality": 1.25,
    "func_sleep_hours": 1.25,
    "flag_not_myself": 1.0,
    "flag_mood_shift": 1.0,
    "flag_missed_medication": 1.25,
    "flag_sleep_medication": 0.75,
    "flag_routine_disruption": 1.0,
    "flag_physiological_stress": 1.0,
    "flag_psychological_stress": 1.0,
    "obs_up_now": 1.0,
    "obs_down_now": 1.0,
    "obs_mixed_now": 1.0,
    "obs_up_coming": 0.75,
    "obs_down_coming": 0.75,
    "obs_mixed_coming": 0.75,
}
DOMAIN_MAP = {
    "Depression": [
        "dep_low_mood", "dep_slowed_low_energy", "dep_low_motivation",
        "dep_anhedonia", "dep_withdrawal", "dep_self_harm_ideation",
        "func_work", "func_daily", "func_sleep_quality", "func_sleep_hours",
        "flag_not_myself", "flag_mood_shift", "flag_missed_medication",
        "flag_routine_disruption", "flag_psychological_stress", "flag_physiological_stress",
        "obs_down_now", "obs_down_coming",
    ],
    "Mania": [
        "man_elevated_mood", "man_sped_up_high_energy", "man_racing_thoughts",
        "man_goal_drive", "man_impulsivity", "man_agitation", "man_irritability",
        "man_cant_settle", "func_sleep_quality", "func_sleep_hours",
        "flag_not_myself", "flag_mood_shift", "flag_missed_medication",
        "flag_routine_disruption", "flag_psychological_stress", "flag_physiological_stress",
        "obs_up_now", "obs_up_coming",
    ],
    "Psychosis": [
        "psy_heard_saw", "psy_suspicious", "psy_trust_perceptions",
        "psy_confidence_reality", "psy_distress", "flag_not_myself",
        "flag_mood_shift", "flag_missed_medication", "flag_routine_disruption",
        "flag_psychological_stress", "flag_physiological_stress",
        "obs_mixed_now", "obs_mixed_coming",
    ],
    "Mixed": [
        "mix_high_energy_low_mood", "mix_rapid_emotional_shifts",
        "man_agitation", "man_irritability", "dep_low_mood",
        "man_sped_up_high_energy", "func_sleep_quality", "func_sleep_hours",
        "flag_mood_shift", "flag_routine_disruption", "obs_mixed_now", "obs_mixed_coming",
    ],
}


# =========================================================
# HELPERS
# =========================================================
def bool_from_response(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "y", "checked"}


@st.cache_data
def question_catalog_df() -> pd.DataFrame:
    return pd.DataFrame(QUESTION_CATALOG).sort_values("display_order").reset_index(drop=True)


def build_question_lookup() -> dict[str, dict[str, Any]]:
    return {item["question_text"]: item for item in QUESTION_CATALOG}


def add_submission_indexing(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    working = df.copy()
    working["submitted_at"] = pd.to_datetime(working["Timestamp"], errors="coerce", dayfirst=True)
    working = working.dropna(subset=["submitted_at"]).sort_values("submitted_at").reset_index(drop=True)
    working["submitted_date"] = working["submitted_at"].dt.date
    working["submission_order_in_day"] = working.groupby("submitted_date").cumcount() + 1
    working["snapshot_number_in_day"] = working["submission_order_in_day"]
    working["is_first_of_day"] = working["submission_order_in_day"] == 1
    working["submission_id"] = working["submitted_at"].dt.strftime("%Y%m%d%H%M%S") + "_" + working.index.astype(str)
    return working


def clean_submission_values(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    catalog = question_catalog_df()
    boolean_questions = catalog.loc[catalog["response_type"] == "boolean_yes_no", "question_text"].tolist()
    numeric_questions = catalog.loc[catalog["response_type"].isin(["scale_1_5", "numeric"]), "question_text"].tolist()

    working = df.copy()

    for column in boolean_questions:
        if column in working.columns:
            working[column] = working[column].apply(bool_from_response)

    for column in numeric_questions:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")

    return working


def build_submissions_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    base_columns = [
        "submission_id",
        "submitted_at",
        "submitted_date",
        "submission_order_in_day",
        "snapshot_number_in_day",
        "is_first_of_day",
    ]

    submissions = df[base_columns].copy()
    if "How would I describe my experiences?" in df.columns:
        submissions["experience_description"] = df["How would I describe my experiences?"].replace("", pd.NA)
    else:
        submissions["experience_description"] = pd.NA

    return submissions


def build_answers_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    catalog = question_catalog_df()
    answer_rows: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        for _, question in catalog.iterrows():
            question_text = question["question_text"]
            if question_text not in df.columns:
                continue

            raw_value = row.get(question_text)
            if pd.isna(raw_value) or raw_value == "":
                continue

            answer_rows.append(
                {
                    "submission_id": row["submission_id"],
                    "submitted_at": row["submitted_at"],
                    "submitted_date": row["submitted_date"],
                    "question_code": question["question_code"],
                    "question_text": question_text,
                    "group_name": question["group_name"],
                    "response_type": question["response_type"],
                    "polarity": question["polarity"],
                    "used_in_daily_model": question["used_in_daily_model"],
                    "used_in_snapshot_model": question["used_in_snapshot_model"],
                    "used_in_snapshot_scoring": question["used_in_snapshot_scoring"],
                    "value_numeric": raw_value if question["response_type"] in {"scale_1_5", "numeric"} else pd.NA,
                    "value_boolean": raw_value if question["response_type"] == "boolean_yes_no" else pd.NA,
                    "value_text": raw_value if question["response_type"] == "text" else pd.NA,
                    "value_raw": raw_value,
                }
            )

    return pd.DataFrame(answer_rows)


def build_submission_wide(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    lookup = build_question_lookup()
    base_columns = [
        "submission_id",
        "submitted_at",
        "submitted_date",
        "submission_order_in_day",
        "snapshot_number_in_day",
        "is_first_of_day",
    ]

    wide = df[base_columns].copy()
    for question_text, meta in lookup.items():
        if question_text in df.columns:
            wide[meta["question_code"]] = df[question_text]

    return wide


def build_daily_model_input(submission_wide: pd.DataFrame) -> pd.DataFrame:
    if submission_wide.empty:
        return pd.DataFrame()

    daily = (
        submission_wide[submission_wide["is_first_of_day"]]
        .sort_values("submitted_at")
        .rename(columns={"submission_id": "anchor_submission_id", "submitted_date": "date"})
        .reset_index(drop=True)
    )

    return daily


def build_snapshot_model_input(submission_wide: pd.DataFrame) -> pd.DataFrame:
    if submission_wide.empty:
        return pd.DataFrame()

    snapshot = submission_wide.sort_values("submitted_at").reset_index(drop=True).copy()
    snapshot["minutes_since_first_submission"] = (
        snapshot["submitted_at"]
        - snapshot.groupby("submitted_date")["submitted_at"].transform("min")
    ).dt.total_seconds() / 60.0
    return snapshot


def build_snapshot_scoring_view(snapshot_model_input: pd.DataFrame) -> pd.DataFrame:
    if snapshot_model_input.empty:
        return pd.DataFrame()

    catalog = question_catalog_df()
    scoring_codes = catalog.loc[catalog["used_in_snapshot_scoring"], "question_code"].tolist()
    base_columns = [
        "submission_id",
        "submitted_at",
        "submitted_date",
        "snapshot_number_in_day",
        "is_first_of_day",
        "minutes_since_first_submission",
    ]
    available = [column for column in scoring_codes if column in snapshot_model_input.columns]
    return snapshot_model_input[base_columns + available].copy()


def build_daily_change_table(daily_model_input: pd.DataFrame) -> pd.DataFrame:
    if daily_model_input.empty:
        return pd.DataFrame()

    value_columns = [
        column
        for column in daily_model_input.columns
        if column not in {"date", "anchor_submission_id", "submitted_at", "submission_order_in_day", "snapshot_number_in_day", "is_first_of_day"}
        and pd.api.types.is_numeric_dtype(daily_model_input[column])
    ]

    changes = daily_model_input[["date"] + value_columns].copy()
    changes = changes.sort_values("date").reset_index(drop=True)

    for column in value_columns:
        changes[f"{column}_delta"] = changes[column].diff()

    return changes


def safe_get_worksheet(tab_name: str):
    workbook = get_workbook()
    try:
        return workbook.worksheet(tab_name)
    except Exception:
        return None


@st.cache_data(ttl=60)
def load_weights_from_sheet() -> dict[str, float]:
    worksheet = safe_get_worksheet(SETTINGS_TAB)
    if worksheet is None:
        return DEFAULT_WEIGHTS.copy()

    values = worksheet.get_all_values()
    if not values or len(values) == 1:
        return DEFAULT_WEIGHTS.copy()

    df = pd.DataFrame(values[1:], columns=values[0])
    if "question_code" not in df.columns or "weight" not in df.columns:
        return DEFAULT_WEIGHTS.copy()

    weights = DEFAULT_WEIGHTS.copy()
    for _, row in df.iterrows():
        code = str(row.get("question_code", "")).strip()
        if code in weights:
            parsed = pd.to_numeric(row.get("weight"), errors="coerce")
            if pd.notna(parsed):
                weights[code] = float(parsed)
    return weights


def save_weights_to_sheet(weights: dict[str, float]) -> tuple[bool, str]:
    worksheet = safe_get_worksheet(SETTINGS_TAB)
    if worksheet is None:
        return False, (
            f"Could not find a worksheet named '{SETTINGS_TAB}', and this service account does not appear to have permission to create one. "
            "Create that tab manually in the spreadsheet, then saving will work."
        )

    rows = [["question_code", "weight"]] + [[code, value] for code, value in weights.items()]
    worksheet.clear()
    worksheet.update("A1", rows)
    load_weights_from_sheet.clear()
    return True, "Weights saved."


def normalize_series_for_scoring(series: pd.Series, polarity: str, response_type: str, question_code: str) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")

    if response_type == "boolean_yes_no":
        return s.fillna(0).astype(float) * 100.0

    if question_code == "func_sleep_hours":
        hours = s.astype(float)
        score = pd.Series(0.0, index=hours.index)
        score = score.mask(hours < 3, 100.0)
        score = score.mask((hours >= 3) & (hours < 4), 85.0)
        score = score.mask((hours >= 4) & (hours < 5), 70.0)
        score = score.mask((hours >= 5) & (hours < 6), 50.0)
        score = score.mask((hours >= 6) & (hours <= 9), 20.0)
        score = score.mask((hours > 9) & (hours <= 10), 40.0)
        score = score.mask(hours > 10, 60.0)
        return score.fillna(0.0)

    if response_type == "scale_1_5":
        base = ((s - 1).clip(lower=0, upper=4) / 4.0) * 100.0
        if polarity == "higher_better":
            return 100.0 - base
        return base.fillna(0.0)

    return s.fillna(0.0).astype(float)


def build_component_score_frame(submission_wide: pd.DataFrame) -> pd.DataFrame:
    if submission_wide.empty:
        return pd.DataFrame()

    catalog = question_catalog_df()
    base = submission_wide[[
        "submission_id", "submitted_at", "submitted_date",
        "submission_order_in_day", "snapshot_number_in_day", "is_first_of_day"
    ]].copy()

    for _, question in catalog.iterrows():
        code = question["question_code"]
        if code not in submission_wide.columns:
            continue
        base[code] = normalize_series_for_scoring(
            submission_wide[code],
            question["polarity"],
            question["response_type"],
            code,
        )

    return base


def compute_domain_score(frame: pd.DataFrame, domain_codes: list[str], weights: dict[str, float]) -> pd.Series:
    available = [code for code in domain_codes if code in frame.columns and weights.get(code, 0) > 0]
    if not available:
        return pd.Series(0.0, index=frame.index)

    numerator = pd.Series(0.0, index=frame.index)
    denominator = 0.0
    for code in available:
        weight = float(weights.get(code, 0.0))
        numerator += frame[code].fillna(0.0) * weight
        denominator += weight
    return numerator / denominator if denominator else pd.Series(0.0, index=frame.index)


def build_scored_snapshot_table(submission_wide: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    if submission_wide.empty:
        return pd.DataFrame()

    scored = build_snapshot_model_input(build_component_score_frame(submission_wide))
    for domain, codes in DOMAIN_MAP.items():
        snapshot_codes = []
        for code in codes:
            row = question_catalog_df().loc[question_catalog_df()["question_code"] == code]
            if row.empty or bool(row.iloc[0]["used_in_snapshot_scoring"]):
                snapshot_codes.append(code)
        scored[f"{domain} Score %"] = compute_domain_score(scored, snapshot_codes, weights)

    scored["Overall Score %"] = scored[["Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"]].mean(axis=1)
    return scored


def build_scored_daily_table(submission_wide: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    if submission_wide.empty:
        return pd.DataFrame()

    component_frame = build_component_score_frame(submission_wide)
    daily = build_daily_model_input(component_frame)
    for domain, codes in DOMAIN_MAP.items():
        daily[f"{domain} Score %"] = compute_domain_score(daily, codes, weights)
    daily["Overall Score %"] = daily[["Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"]].mean(axis=1)
    for column in ["Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %", "Overall Score %"]:
        daily[f"{column} Delta"] = daily[column].diff()
    return daily


def build_warnings_table(scored_daily: pd.DataFrame, scored_snapshots: pd.DataFrame) -> pd.DataFrame:
    if scored_daily.empty and scored_snapshots.empty:
        return pd.DataFrame()

    warnings = []
    if not scored_daily.empty:
        latest_daily = scored_daily.sort_values("date").iloc[-1]
        for domain in ["Depression", "Mania", "Psychosis", "Mixed"]:
            score = float(latest_daily.get(f"{domain} Score %", 0.0))
            delta = float(latest_daily.get(f"{domain} Score % Delta", 0.0))
            severity = "High" if score >= 70 else "Medium" if score >= 45 else None
            if severity:
                warnings.append({
                    "source": "Daily Model",
                    "timestamp": latest_daily.get("submitted_at"),
                    "domain": domain,
                    "severity": severity,
                    "score_pct": round(score, 1),
                    "delta": round(delta, 1),
                    "message": f"{domain} daily score is {score:.1f}%",
                })

    if not scored_snapshots.empty:
        latest_snapshot = scored_snapshots.sort_values("submitted_at").iloc[-1]
        for domain in ["Depression", "Mania", "Psychosis", "Mixed"]:
            score = float(latest_snapshot.get(f"{domain} Score %", 0.0))
            severity = "High" if score >= 75 else "Medium" if score >= 50 else None
            if severity:
                warnings.append({
                    "source": "Snapshots",
                    "timestamp": latest_snapshot.get("submitted_at"),
                    "domain": domain,
                    "severity": severity,
                    "score_pct": round(score, 1),
                    "delta": pd.NA,
                    "message": f"{domain} latest snapshot score is {score:.1f}%",
                })

    if not warnings:
        return pd.DataFrame(columns=["source", "timestamp", "domain", "severity", "score_pct", "delta", "message"])
    return pd.DataFrame(warnings).sort_values(["severity", "timestamp"], ascending=[False, False]).reset_index(drop=True)


def render_weights_editor(weights: dict[str, float]) -> dict[str, float]:
    st.markdown("### Scoring weights")
    worksheet_exists = safe_get_worksheet(SETTINGS_TAB) is not None
    if worksheet_exists:
        st.caption("Changes are saved to the Google Sheet and persist across refreshes.")
    else:
        st.warning(
            f"Worksheet '{SETTINGS_TAB}' was not found. Weights are currently using in-memory defaults only. "
            f"Create a worksheet with that exact name to make changes persist."
        )
    catalog = question_catalog_df()
    updated = weights.copy()
    groups = ["depression", "mania", "mixed", "psychosis", "functioning", "flags", "observations"]
    for group in groups:
        group_df = catalog[catalog["group_name"] == group]
        if group_df.empty:
            continue
        with st.expander(group.title(), expanded=False):
            for _, row in group_df.iterrows():
                code = row["question_code"]
                updated[code] = st.number_input(
                    f"{code}",
                    min_value=0.0,
                    max_value=10.0,
                    step=0.25,
                    value=float(updated.get(code, 0.0)),
                    key=f"weight_{code}",
                )
    save_col, reset_col = st.columns(2)
    with save_col:
        if st.button("Save weights", type="primary"):
            ok, message = save_weights_to_sheet(updated)
            if ok:
                st.success(message)
            else:
                st.error(message)
    with reset_col:
        if st.button("Reset to defaults"):
            ok, message = save_weights_to_sheet(DEFAULT_WEIGHTS.copy())
            if ok:
                st.success("Weights reset to defaults.")
            else:
                st.error(message)
    return updated


# =========================================================
# LOAD + BUILD
# =========================================================
try:
    workbook = get_workbook()
    st.success(f"Connected to Google Sheets: {workbook.title}")
except Exception as exc:
    st.error("Google Sheets connection failed.")
    st.exception(exc)
    st.stop()

weights = load_weights_from_sheet()
raw_df = load_sheet(NEW_FORM_TAB)
indexed_df = add_submission_indexing(raw_df)
clean_df = clean_submission_values(indexed_df)
submissions_df = build_submissions_table(clean_df)
answers_df = build_answers_table(clean_df)
submission_wide_df = build_submission_wide(clean_df)
daily_model_input_df = build_daily_model_input(submission_wide_df)
snapshot_model_input_df = build_snapshot_model_input(submission_wide_df)
snapshot_scoring_view_df = build_snapshot_scoring_view(snapshot_model_input_df)
scored_daily_df = build_scored_daily_table(submission_wide_df, weights)
scored_snapshots_df = build_scored_snapshot_table(submission_wide_df, weights)
daily_change_df = build_daily_change_table(scored_daily_df)
warnings_df = build_warnings_table(scored_daily_df, scored_snapshots_df)


# =========================================================
# APP
# =========================================================
st.subheader("Data model workspace")
st.write("This page turns the form into a reusable data layer for daily and snapshot models.")
st.caption(f"Locked to worksheet: {NEW_FORM_TAB}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Raw rows", len(raw_df))
m2.metric("Submissions", len(submissions_df))
m3.metric("Daily anchor rows", len(daily_model_input_df))
m4.metric("Snapshot rows", len(snapshot_model_input_df))

st.markdown("### Model rules")
st.markdown("- Daily model: first response of each day")
st.markdown("- Snapshot model: all responses, including the first response of the day")
st.markdown("- Sleep is shown in snapshots but excluded from repeated snapshot scoring")
st.markdown("- Higher is better only for `func_work` and `func_daily`")
st.markdown("- Higher is worse for all other scale items, including `func_sleep_quality`")

with st.expander("Question catalog", expanded=True):
    st.dataframe(question_catalog_df(), use_container_width=True)

tabs = st.tabs(["Warnings", "Daily Model", "Snapshots", "Data Layer"])

with tabs[0]:
    st.markdown("### Warnings")
    st.dataframe(warnings_df, use_container_width=True)
    st.markdown("### Scoring weights")
    weights = render_weights_editor(weights)

with tabs[1]:
    st.markdown("### Daily Model")
    st.dataframe(scored_daily_df, use_container_width=True)
    if not scored_daily_df.empty:
        chart_df = scored_daily_df[["date", "Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"]].copy()
        st.line_chart(chart_df.set_index("date"))
        st.markdown("### Daily changes")
        st.dataframe(daily_change_df, use_container_width=True)

with tabs[2]:
    st.markdown("### Snapshots")
    st.dataframe(scored_snapshots_df, use_container_width=True)
    if not scored_snapshots_df.empty:
        chart_df = scored_snapshots_df[["submitted_at", "Depression Score %", "Mania Score %", "Psychosis Score %", "Mixed Score %"]].copy()
        st.line_chart(chart_df.set_index("submitted_at"))
        st.markdown("### Snapshot scoring view")
        st.dataframe(snapshot_scoring_view_df, use_container_width=True)

with tabs[3]:
    with st.expander("Submissions table"):
        st.dataframe(submissions_df, use_container_width=True)

    with st.expander("Answers table"):
        st.dataframe(answers_df, use_container_width=True)

    with st.expander("Submission wide table"):
        st.dataframe(submission_wide_df, use_container_width=True)

    with st.expander("Daily model input"):
        st.dataframe(daily_model_input_df, use_container_width=True)

    with st.expander("Snapshot model input"):
        st.dataframe(snapshot_model_input_df, use_container_width=True)

with st.expander("Raw worksheet preview"):
    st.dataframe(raw_df, use_container_width=True)
    st.write(list(raw_df.columns))
