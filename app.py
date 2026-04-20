import streamlit as st
import pandas as pd
import gspread

st.set_page_config(page_title="Wellbeing Dashboard", layout="wide")

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

SHEET_NAME     = "Bipolar Dashboard"
FORM_TAB       = "Form Responses"
QUICK_FORM_TAB = "Quick Form Responses"
NEW_FORM_TAB   = "Updated Bipolar Form"
DOMAIN_NAMES   = ["Depression", "Mania", "Psychosis", "Mixed"]
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

COL_MOOD          = "Mood Score"
COL_SLEEP_HOURS   = "Sleep (hours)"
COL_SLEEP_QUALITY = "Sleep quality"
COL_ENERGY        = "Energy"
COL_MENTAL_SPEED  = "Mental speed"
COL_IMPULSIVITY   = "Impulsivity"
COL_MOTIVATION    = "Motivation"
COL_IRRITABILITY  = "Irritability"
COL_AGITATION     = "Agitation"
COL_SLEEPING_PILLS= "Took sleeping medication?"
COL_UNUSUAL       = "Unusual perceptions"
COL_SUSPICIOUS    = "Suspiciousness"
COL_CERTAINTY     = "Certainty and belief in unusual ideas or things others don't believe"

SIG_NOT_MYSELF    = 'Signals and indicators [Felt "not like myself"]'
SIG_MOOD_SHIFT    = "Signals and indicators [Noticed a sudden mood shift]"
SIG_LESS_SLEEP    = "Signals and indicators [Needed less sleep than usual without feeling tired]"
SIG_MORE_ACTIVITY = "Signals and indicators [Started more activities than usual]"
SIG_WITHDRAW      = "Signals and indicators [Withdrew socially or emotionally from others]"
SIG_HEARD_SAW     = "Signals and indicators [Heard or saw something others didn't]"
SIG_WATCHED       = "Signals and indicators [Felt watched, followed, targeted]"
SIG_TROUBLE_TRUST = "Signals and indicators [Trouble trusting perceptions and thoughts]"
SIG_MISSED_MEDS   = "Signals and indicators [Missed meds]"
SIG_ROUTINE       = "Signals and indicators [Significant disruption to routine]"
SIG_STRESS_PSYCH  = "Signals and indicators [Major stressor or trigger (psychological)]"
SIG_STRESS_PHYS   = "Signals and indicators [Major stressor or trigger (physiological)]"
SIG_UP_NOW        = "Signals and indicators [Feel like I'm experiencing an up]"
SIG_DOWN_NOW      = "Signals and indicators [Feel like I'm experiencing a down]"
SIG_MIXED_NOW     = "Signals and indicators [Feel like I'm experiencing a mixed]"
SIG_UP_COMING     = "Signals and indicators [Feel like I'm going to experience an up]"
SIG_DOWN_COMING   = "Signals and indicators [Feel like I'm going to experience a down]"
SIG_MIXED_COMING  = "Signals and indicators [Feel like I'm going to experience a mixed]"

NF_LOW_MOOD        = "Have I felt a low mood?"
NF_SLOWED          = "Have I felt slowed down or low on energy?"
NF_MOTIVATION      = "Have I felt low on motivation or had difficulty initiating tasks?"
NF_ANHEDONIA       = "Have I felt a lack of interest or pleasure in activities?"
NF_WITHDRAWAL      = "Have I been socially or emotionally withdrawn?"
NF_SELF_HARM       = "Have I had ideation around self-harming or suicidal behaviours?"
NF_ELEVATED_MOOD   = "Have I felt an elevated mood?"
NF_SPED_UP         = "Have I felt sped up or high on energy?"
NF_RACING          = "Have I had racing thoughts or speech?"
NF_GOAL_DRIVE      = "Have I had an increased drive towards goal-directed activity or a sense that I must be 'doing things' at all times?"
NF_IMPULSIVITY     = "Have I felt impulsivity or an urge to take risky actions?"
NF_AGITATION       = "Have I felt agitated or restless?"
NF_IRRITABILITY    = "Have I been more irritable and reactive than normal?"
NF_CANT_SETTLE     = "Have I been unable to settle or switch off?"
NF_HIGH_E_LOW_MOOD = "Have I had a high energy combined with low mood?"
NF_RAPID_SHIFTS    = "Have I experienced rapid emotional shifts?"
NF_HEARD_SAW       = "Have I heard or seen things others didn't?"
NF_SUSPICIOUS      = "Have I felt watched, followed, targeted or suspicious?"
NF_TRUST_PERCEPT   = "Have I had trouble trusting my perceptions and thoughts?"
NF_CONFIDENCE_REA  = "How confident have I been in the reality of these experiences?"
NF_DISTRESS        = "How distressed have I been by these beliefs and experiences?"
NF_WORK_FUNC       = "How effectively have I been functioning at work?"
NF_DAILY_FUNC      = "How well have I been functioning in my daily life?"
NF_UNLIKE_SELF     = "Do I feel unlike my usual self?"
NF_SOMETHING_WRONG = "Do I think something may be wrong or changing?"
NF_CONCERNED       = "Am I concerned about my current state?"
NF_DISORG_THOUGHTS = "Do my thoughts feel disorganised or hard to follow?"
NF_UNSTABLE_ATTN   = "Is my attention unstable or jumping?"
NF_DRIVEN_ACT      = "Do I feel driven to act without thinking?"
NF_INTENSIFYING    = "Is my state intensifying (in any direction)?"
NF_TOWARDS_EPISODE = "Do I feel like I'm moving towards an episode?"
NF_FLAG_NOT_MYSELF = 'I\'ve been feeling "not like myself"'
NF_FLAG_MOOD_SHIFT = "I noticed a sudden mood shift"
NF_FLAG_MISSED_MEDS= "I missed medication"
NF_FLAG_SLEEP_MEDS = "I took sleeping or anti-anxiety medication"
NF_FLAG_ROUTINE    = "There were significant disruptions to my routine"
NF_FLAG_PHYS       = "I had a major physiological stress"
NF_FLAG_PSYCH      = "I had a major psychological stress"
NF_OBS_UP_NOW      = "Observations [I feel like I'm experiencing an up]"
NF_OBS_DOWN_NOW    = "Observations [I feel like I'm experiencing a down]"
NF_OBS_MIXED_NOW   = "Observations [I feel like I'm experiencing a mixed]"
NF_OBS_UP_COMING   = "Observations [I feel like I'm going to experience an up]"
NF_OBS_DOWN_COMING = "Observations [I feel like I'm going to experience a down]"
NF_OBS_MIXED_COMING= "Observations [I feel like I'm going to experience a mixed]"
NF_SLEEP_HOURS     = "How many hours did I sleep last night?"
NF_SLEEP_QUALITY   = "How poor was my sleep quality last night"

NF_META_COLS     = [NF_UNLIKE_SELF, NF_SOMETHING_WRONG, NF_CONCERNED, NF_INTENSIFYING, NF_TOWARDS_EPISODE]
NF_CONCERN_FLAGS = [NF_FLAG_NOT_MYSELF, NF_FLAG_MOOD_SHIFT, NF_FLAG_MISSED_MEDS,
                    NF_FLAG_ROUTINE, NF_FLAG_PHYS, NF_FLAG_PSYCH]

NF_DOMAIN_CONFIG = {
    "Depression": {
        "components": [
            ("Low mood",           NF_LOW_MOOD,      "nf_dep_low_mood_w"),
            ("Slowed/low energy",  NF_SLOWED,        "nf_dep_slowed_w"),
            ("Low motivation",     NF_MOTIVATION,    "nf_dep_motivation_w"),
            ("Anhedonia",          NF_ANHEDONIA,     "nf_dep_anhedonia_w"),
            ("Withdrawal",         NF_WITHDRAWAL,    "nf_dep_withdrawal_w"),
            ("Self-harm ideation", NF_SELF_HARM,     "nf_dep_self_harm_w"),
            ("Poor sleep",         NF_SLEEP_QUALITY, "nf_dep_sleep_w"),
            ("Poor work function", NF_WORK_FUNC,     "nf_dep_work_func_w"),
            ("Poor daily function",NF_DAILY_FUNC,    "nf_dep_daily_func_w"),
        ],
        "yes_no_flags":    [NF_OBS_DOWN_NOW, NF_OBS_DOWN_COMING],
        "flag_weight_key": "nf_dep_flag_w",
    },
    "Mania": {
        "components": [
            ("Elevated mood",   NF_ELEVATED_MOOD, "nf_man_elevated_w"),
            ("Sped up/energy",  NF_SPED_UP,       "nf_man_sped_up_w"),
            ("Racing thoughts", NF_RACING,        "nf_man_racing_w"),
            ("Goal drive",      NF_GOAL_DRIVE,    "nf_man_goal_drive_w"),
            ("Impulsivity",     NF_IMPULSIVITY,   "nf_man_impulsivity_w"),
            ("Agitation",       NF_AGITATION,     "nf_man_agitation_w"),
            ("Irritability",    NF_IRRITABILITY,  "nf_man_irritability_w"),
            ("Can't settle",    NF_CANT_SETTLE,   "nf_man_cant_settle_w"),
            ("Poor sleep",      NF_SLEEP_QUALITY, "nf_man_sleep_w"),
        ],
        "yes_no_flags":    [NF_OBS_UP_NOW, NF_OBS_UP_COMING],
        "flag_weight_key": "nf_man_flag_w",
    },
    "Psychosis": {
        "components": [
            ("Heard/saw things",  NF_HEARD_SAW,       "nf_psy_heard_saw_w"),
            ("Suspicious",        NF_SUSPICIOUS,      "nf_psy_suspicious_w"),
            ("Trust perceptions", NF_TRUST_PERCEPT,   "nf_psy_trust_w"),
            ("Confidence reality",NF_CONFIDENCE_REA,  "nf_psy_confidence_w"),
            ("Distress",          NF_DISTRESS,        "nf_psy_distress_w"),
            ("Disorg. thoughts",  NF_DISORG_THOUGHTS, "nf_psy_disorg_w"),
        ],
        "yes_no_flags":    [NF_OBS_MIXED_NOW, NF_OBS_MIXED_COMING],
        "flag_weight_key": "nf_psy_flag_w",
    },
}

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
    "anomaly_z_threshold": 1.5, "high_anomaly_z_threshold": 2.5, "persistence_days": 3,
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

DEFAULT_NF_SETTINGS = {
    "nf_dep_low_mood_w": 3.0, "nf_dep_slowed_w": 1.5, "nf_dep_motivation_w": 2.0,
    "nf_dep_anhedonia_w": 2.0, "nf_dep_withdrawal_w": 1.0, "nf_dep_self_harm_w": 4.0,
    "nf_dep_sleep_w": 1.0, "nf_dep_work_func_w": 1.0, "nf_dep_daily_func_w": 1.0,
    "nf_dep_flag_w": 2.0,
    "nf_man_elevated_w": 2.0, "nf_man_sped_up_w": 1.5, "nf_man_racing_w": 1.5,
    "nf_man_goal_drive_w": 1.5, "nf_man_impulsivity_w": 2.0, "nf_man_agitation_w": 1.5,
    "nf_man_irritability_w": 1.5, "nf_man_cant_settle_w": 1.0, "nf_man_sleep_w": 1.5,
    "nf_man_flag_w": 2.0,
    "nf_psy_heard_saw_w": 2.0, "nf_psy_suspicious_w": 1.5, "nf_psy_trust_w": 1.5,
    "nf_psy_confidence_w": 2.0, "nf_psy_distress_w": 1.5, "nf_psy_disorg_w": 1.0,
    "nf_psy_flag_w": 1.5,
    "nf_mix_dep_w": 0.4, "nf_mix_man_w": 0.4, "nf_mix_psy_w": 0.2,
    "nf_mix_high_e_low_mood_w": 3.0, "nf_mix_rapid_shifts_w": 2.0,
    "medium_threshold_pct": 33.0, "high_threshold_pct": 66.0,
    "trend_threshold_pct": 8.0, "baseline_window_days": 14,
    "anomaly_z_threshold": 1.5, "high_anomaly_z_threshold": 2.5, "persistence_days": 3,
}

REASON_LABELS = {
    "Depression - Low Mood Score": "Lower mood",
    "Depression - Low Sleep Quality": "Poor sleep quality",
    "Depression - Low Energy": "Lower energy",
    "Depression - Low Mental Speed": "Slower mental speed",
    "Depression - Low Motivation": "Lower motivation",
    "Depression - Flags": "Depression flag",
    "Mania - High Mood Score": "Higher mood",
    "Mania - Low Sleep Quality": "Poor sleep",
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

NF_REASON_LABELS = {
    "Low mood": "Low mood", "Slowed/low energy": "Slowed / low energy",
    "Low motivation": "Low motivation", "Anhedonia": "Anhedonia / low pleasure",
    "Withdrawal": "Social/emotional withdrawal", "Self-harm ideation": "Self-harm ideation",
    "Poor sleep": "Poor sleep quality", "Poor work function": "Poor work functioning",
    "Poor daily function": "Poor daily functioning", "Elevated mood": "Elevated mood",
    "Sped up/energy": "Sped up / high energy", "Racing thoughts": "Racing thoughts / speech",
    "Goal drive": "Goal-directed drive", "Impulsivity": "Impulsivity / risky urges",
    "Agitation": "Agitation / restlessness", "Irritability": "Irritability",
    "Can't settle": "Unable to settle", "Heard/saw things": "Heard / saw things",
    "Suspicious": "Suspicion / paranoia", "Trust perceptions": "Trouble trusting perceptions",
    "Confidence reality": "Confidence in unusual experiences",
    "Distress": "Distress from experiences", "Disorg. thoughts": "Disorganised thoughts",
    "Flags": "Observation flags",
}

DAILY_DOMAIN_CONFIG = {
    "Depression": {
        "components": [
            ("Low Mood Score",    COL_MOOD,          True,  "dep_low_mood_weight"),
            ("Low Sleep Quality", COL_SLEEP_QUALITY,  True,  "dep_low_sleep_quality_weight"),
            ("Low Energy",        COL_ENERGY,         True,  "dep_low_energy_weight"),
            ("Low Mental Speed",  COL_MENTAL_SPEED,   True,  "dep_low_mental_speed_weight"),
            ("Low Motivation",    COL_MOTIVATION,     True,  "dep_low_motivation_weight"),
        ],
        "flags": [], "flag_weight_key": "dep_flag_weight", "custom_flag_logic": "depression",
    },
    "Mania": {
        "components": [
            ("High Mood Score",   COL_MOOD,          False, "mania_high_mood_weight"),
            ("Low Sleep Quality", COL_SLEEP_QUALITY,  True,  "mania_low_sleep_quality_weight"),
            ("High Energy",       COL_ENERGY,         False, "mania_high_energy_weight"),
            ("High Mental Speed", COL_MENTAL_SPEED,   False, "mania_high_mental_speed_weight"),
            ("High Impulsivity",  COL_IMPULSIVITY,    False, "mania_high_impulsivity_weight"),
            ("High Irritability", COL_IRRITABILITY,   False, "mania_high_irritability_weight"),
            ("High Agitation",    COL_AGITATION,      False, "mania_high_agitation_weight"),
        ],
        "flags": [SIG_LESS_SLEEP, SIG_MORE_ACTIVITY, SIG_UP_NOW, SIG_UP_COMING],
        "flag_weight_key": "mania_flag_weight",
    },
    "Psychosis": {
        "components": [
            ("Unusual perceptions", COL_UNUSUAL,    False, "psych_unusual_weight"),
            ("Suspiciousness",      COL_SUSPICIOUS, False, "psych_suspicious_weight"),
            ("Certainty",           COL_CERTAINTY,  False, "psych_certainty_weight"),
        ],
        "flags": [SIG_HEARD_SAW, SIG_WATCHED, SIG_TROUBLE_TRUST],
        "flag_weight_key": "psych_flag_weight",
    },
}

SNAPSHOT_DOMAIN_CONFIG = {
    "Depression": {"components": [
        ("Symptoms: [Very low or depressed mood]",     "dep_very_low_mood"),
        ("Symptoms: [Somewhat low or depressed mood]", "dep_somewhat_low_mood"),
        ("Symptoms: [Social or emotional withdrawal]", "dep_withdrawal"),
        ("Symptoms: [Feeling slowed down]",            "dep_slowed_down"),
        ("Symptoms: [Difficulty with self-care]",      "dep_self_care"),
    ]},
    "Mania": {"components": [
        ("Symptoms: [Very high or elevated mood]",     "mania_very_high_mood"),
        ("Symptoms: [Somewhat high or elevated mood]", "mania_somewhat_high_mood"),
        ("Symptoms: [Agitation or restlessness]",      "mania_agitation"),
        ("Symptoms: [Racing thoughts]",                "mania_racing"),
        ("Symptoms: [Driven to activity]",             "mania_driven"),
    ]},
    "Psychosis": {"components": [
        ("Symptoms: [Hearing or seeing things that aren't there]",       "psych_hearing_seeing"),
        ("Symptoms: [Paranoia or suspicion]",                            "psych_paranoia"),
        ("Symptoms: [Firm belief in things others would not agree with]","psych_beliefs"),
    ]},
}

DAILY_SETTINGS_UI = {
    "Depression weights": [
        ("dep_low_mood_weight","Low mood",0.0,5.0,0.1),
        ("dep_low_sleep_quality_weight","Low sleep quality",0.0,5.0,0.1),
        ("dep_low_energy_weight","Low energy",0.0,5.0,0.1),
        ("dep_low_mental_speed_weight","Low mental speed",0.0,5.0,0.1),
        ("dep_low_motivation_weight","Low motivation",0.0,5.0,0.1),
        ("dep_flag_weight","Depression flag",0.0,5.0,0.1),
    ],
    "Mania weights": [
        ("mania_high_mood_weight","High mood",0.0,5.0,0.1),
        ("mania_low_sleep_quality_weight","Low sleep quality (mania)",0.0,5.0,0.1),
        ("mania_high_energy_weight","High energy",0.0,5.0,0.1),
        ("mania_high_mental_speed_weight","High mental speed",0.0,5.0,0.1),
        ("mania_high_impulsivity_weight","High impulsivity",0.0,5.0,0.1),
        ("mania_high_irritability_weight","High irritability",0.0,5.0,0.1),
        ("mania_high_agitation_weight","High agitation",0.0,5.0,0.1),
        ("mania_flag_weight","Mania flags",0.0,5.0,0.1),
    ],
    "Psychosis weights": [
        ("psych_unusual_weight","Unusual perceptions",0.0,5.0,0.1),
        ("psych_suspicious_weight","Suspiciousness",0.0,5.0,0.1),
        ("psych_certainty_weight","Certainty",0.0,5.0,0.1),
        ("psych_flag_weight","Psychosis flags",0.0,5.0,0.1),
    ],
    "Mixed weights": [
        ("mixed_dep_weight","Mixed: depression",0.0,3.0,0.05),
        ("mixed_mania_weight","Mixed: mania",0.0,3.0,0.05),
        ("mixed_psych_weight","Mixed: psychosis",0.0,3.0,0.05),
        ("mixed_low_sleep_quality_weight","Mixed: low sleep quality",0.0,3.0,0.05),
    ],
    "Thresholds": [
        ("medium_threshold_pct","Medium threshold (%)",0.0,100.0,1.0),
        ("high_threshold_pct","High threshold (%)",0.0,100.0,1.0),
        ("trend_threshold_pct","Trend threshold (pp)",0.0,100.0,1.0),
    ],
    "Baseline & alert tuning": [
        ("baseline_window_days","Baseline window (days)",3,60,1),
        ("anomaly_z_threshold","Unusual z-threshold",0.5,5.0,0.1),
        ("high_anomaly_z_threshold","High unusual z-threshold",0.5,6.0,0.1),
        ("persistence_days","Persistence days",2,14,1),
    ],
}

SNAPSHOT_SETTINGS_UI = {
    "Depression weights": [
        ("dep_very_low_mood","Very low mood",0.0,5.0,0.1),
        ("dep_somewhat_low_mood","Somewhat low mood",0.0,5.0,0.1),
        ("dep_withdrawal","Withdrawal",0.0,5.0,0.1),
        ("dep_slowed_down","Slowed down",0.0,5.0,0.1),
        ("dep_self_care","Self-care",0.0,5.0,0.1),
    ],
    "Mania weights": [
        ("mania_very_high_mood","Very high mood",0.0,5.0,0.1),
        ("mania_somewhat_high_mood","Somewhat high mood",0.0,5.0,0.1),
        ("mania_agitation","Agitation",0.0,5.0,0.1),
        ("mania_racing","Racing thoughts",0.0,5.0,0.1),
        ("mania_driven","Driven to activity",0.0,5.0,0.1),
    ],
    "Psychosis weights": [
        ("psych_hearing_seeing","Hearing / seeing things",0.0,5.0,0.1),
        ("psych_paranoia","Paranoia",0.0,5.0,0.1),
        ("psych_beliefs","Firm unusual beliefs",0.0,5.0,0.1),
    ],
    "Mixed weights": [
        ("mixed_dep_weight","Mixed: depression",0.0,3.0,0.05),
        ("mixed_mania_weight","Mixed: mania",0.0,3.0,0.05),
        ("mixed_psych_weight","Mixed: psychosis",0.0,3.0,0.05),
    ],
    "Thresholds": [
        ("medium_threshold_pct","Medium threshold (%)",0.0,100.0,1.0),
        ("high_threshold_pct","High threshold (%)",0.0,100.0,1.0),
        ("trend_threshold_pct","Trend threshold (pp)",0.0,100.0,1.0),
    ],
}

NF_SETTINGS_UI = {
    "Depression weights": [
        ("nf_dep_low_mood_w","Low mood",0.0,5.0,0.1),
        ("nf_dep_slowed_w","Slowed / low energy",0.0,5.0,0.1),
        ("nf_dep_motivation_w","Low motivation",0.0,5.0,0.1),
        ("nf_dep_anhedonia_w","Anhedonia",0.0,5.0,0.1),
        ("nf_dep_withdrawal_w","Withdrawal",0.0,5.0,0.1),
        ("nf_dep_self_harm_w","Self-harm ideation",0.0,5.0,0.1),
        ("nf_dep_sleep_w","Poor sleep",0.0,5.0,0.1),
        ("nf_dep_work_func_w","Work functioning",0.0,5.0,0.1),
        ("nf_dep_daily_func_w","Daily functioning",0.0,5.0,0.1),
        ("nf_dep_flag_w","Down obs. flags",0.0,5.0,0.1),
    ],
    "Mania weights": [
        ("nf_man_elevated_w","Elevated mood",0.0,5.0,0.1),
        ("nf_man_sped_up_w","Sped up/energy",0.0,5.0,0.1),
        ("nf_man_racing_w","Racing thoughts",0.0,5.0,0.1),
        ("nf_man_goal_drive_w","Goal drive",0.0,5.0,0.1),
        ("nf_man_impulsivity_w","Impulsivity",0.0,5.0,0.1),
        ("nf_man_agitation_w","Agitation",0.0,5.0,0.1),
        ("nf_man_irritability_w","Irritability",0.0,5.0,0.1),
        ("nf_man_cant_settle_w","Can't settle",0.0,5.0,0.1),
        ("nf_man_sleep_w","Poor sleep",0.0,5.0,0.1),
        ("nf_man_flag_w","Up obs. flags",0.0,5.0,0.1),
    ],
    "Psychosis weights": [
        ("nf_psy_heard_saw_w","Heard/saw things",0.0,5.0,0.1),
        ("nf_psy_suspicious_w","Suspicious/paranoia",0.0,5.0,0.1),
        ("nf_psy_trust_w","Trust perceptions",0.0,5.0,0.1),
        ("nf_psy_confidence_w","Confidence in reality",0.0,5.0,0.1),
        ("nf_psy_distress_w","Distress",0.0,5.0,0.1),
        ("nf_psy_disorg_w","Disorg. thoughts",0.0,5.0,0.1),
        ("nf_psy_flag_w","Mixed obs. flags",0.0,5.0,0.1),
    ],
    "Mixed weights": [
        ("nf_mix_dep_w","Mixed: depression",0.0,3.0,0.05),
        ("nf_mix_man_w","Mixed: mania",0.0,3.0,0.05),
        ("nf_mix_psy_w","Mixed: psychosis",0.0,3.0,0.05),
        ("nf_mix_high_e_low_mood_w","High energy + low mood",0.0,5.0,0.1),
        ("nf_mix_rapid_shifts_w","Rapid emotional shifts",0.0,5.0,0.1),
    ],
    "Thresholds": [
        ("medium_threshold_pct","Medium threshold (%)",0.0,100.0,1.0),
        ("high_threshold_pct","High threshold (%)",0.0,100.0,1.0),
        ("trend_threshold_pct","Trend threshold (pp)",0.0,100.0,1.0),
    ],
    "Baseline & alert tuning": [
        ("baseline_window_days","Baseline window (days)",3,60,1),
        ("anomaly_z_threshold","Unusual z-threshold",0.5,5.0,0.1),
        ("high_anomaly_z_threshold","High unusual z-threshold",0.5,6.0,0.1),
        ("persistence_days","Persistence days",2,14,1),
    ],
}

def _score_charts(prefix):
    return [
        {"title":"State scores (%)","cols":["Depression Score %","Mania Score %","Psychosis Score %","Mixed Score %"],"key":f"{prefix}_scores","type":"line"},
        {"title":"5-day averages (%)","cols":["5-Day Average (Depression %)","5-Day Average (Mania %)","5-Day Average (Psychosis %)","5-Day Average (Mixed %)"],"key":f"{prefix}_5day","type":"line"},
        {"title":"Deviation from 5-day averages (pp)","cols":["Depression Deviation %","Mania Deviation %","Psychosis Deviation %","Mixed Deviation %"],"key":f"{prefix}_dev","type":"line"},
        {"title":"Personal baseline vs current","cols":["Depression Score %","Depression Baseline %","Mania Score %","Mania Baseline %","Psychosis Score %","Psychosis Baseline %","Mixed Score %","Mixed Baseline %"],"key":f"{prefix}_bl_vs","type":"line"},
        {"title":"Distance from baseline (pp)","cols":["Depression Baseline Difference %","Mania Baseline Difference %","Psychosis Baseline Difference %","Mixed Baseline Difference %"],"key":f"{prefix}_bl_diff","type":"line"},
        {"title":"Unusual-for-me score (z)","cols":["Depression Baseline Z","Mania Baseline Z","Psychosis Baseline Z","Mixed Baseline Z"],"key":f"{prefix}_z","type":"line"},
    ]

DAILY_CHARTS = _score_charts("daily") + [
    {"title":"Flag breakdown","cols":["Concerning Situation Flags","Depression Flags","Mania Flags","Mixed Flags","Psychosis Flags"],"key":"daily_flags","type":"bar"},
    {"title":"Depression drivers","cols":["Depression - Low Mood Score","Depression - Low Sleep Quality","Depression - Low Energy","Depression - Low Mental Speed","Depression - Low Motivation","Depression - Flags"],"key":"daily_dep_drv","type":"line"},
    {"title":"Mania drivers","cols":["Mania - High Mood Score","Mania - Low Sleep Quality","Mania - High Energy","Mania - High Mental Speed","Mania - High Impulsivity","Mania - High Irritability","Mania - High Agitation","Mania - Flags"],"key":"daily_man_drv","type":"line"},
    {"title":"Psychosis drivers","cols":["Psychosis - Unusual perceptions","Psychosis - Suspiciousness","Psychosis - Certainty","Psychosis - Flags"],"key":"daily_psy_drv","type":"line"},
]

SNAPSHOT_CHARTS = [
    {"title":"Snapshot model scores (%)","cols":["Depression Score %","Mania Score %","Psychosis Score %","Mixed Score %"],"key":"snap_scores","type":"line"},
    {"title":"Snapshot vs 10-response averages (%)","cols":["Depression Score %","10-Response Average (Depression %)","Mania Score %","10-Response Average (Mania %)","Psychosis Score %","10-Response Average (Psychosis %)","Mixed Score %","10-Response Average (Mixed %)"],"key":"snap_vs_avg","type":"line"},
    {"title":"Deviation from 10-response averages (pp)","cols":["Deviation From 10-Response Average (Depression %)","Deviation From 10-Response Average (Mania %)","Deviation From 10-Response Average (Psychosis %)","Deviation From 10-Response Average (Mixed %)"],"key":"snap_dev","type":"line"},
]

NF_CHARTS = _score_charts("nf") + [
    {"title":"Flag breakdown","cols":["Concerning Situation Flags","Depression Flags","Mania Flags","Psychosis Flags","Mixed Flags","Meta-Awareness Score"],"key":"nf_flags","type":"bar"},
    {"title":"Depression drivers","cols":["Depression - Low mood","Depression - Slowed/low energy","Depression - Low motivation","Depression - Anhedonia","Depression - Withdrawal","Depression - Self-harm ideation","Depression - Poor sleep","Depression - Poor work function","Depression - Poor daily function","Depression - Flags"],"key":"nf_dep_drv","type":"line"},
    {"title":"Mania drivers","cols":["Mania - Elevated mood","Mania - Sped up/energy","Mania - Racing thoughts","Mania - Goal drive","Mania - Impulsivity","Mania - Agitation","Mania - Irritability","Mania - Can't settle","Mania - Poor sleep","Mania - Flags"],"key":"nf_man_drv","type":"line"},
    {"title":"Psychosis drivers","cols":["Psychosis - Heard/saw things","Psychosis - Suspicious","Psychosis - Trust perceptions","Psychosis - Confidence reality","Psychosis - Distress","Psychosis - Disorg. thoughts","Psychosis - Flags"],"key":"nf_psy_drv","type":"line"},
]

for _k, _d in [("daily_settings",DEFAULT_DAILY_SETTINGS),("snapshot_settings",DEFAULT_SNAPSHOT_SETTINGS),("nf_settings",DEFAULT_NF_SETTINGS)]:
    if _k not in st.session_state:
        st.session_state[_k] = _d.copy()

# =========================================================
# SHARED HELPERS
# =========================================================
def normalize_columns(df):
    return df.rename(columns=COLUMN_ALIASES) if not df.empty else df

def convert_numeric(df, skip=("Timestamp","Date","Date (int)")):
    if df.empty: return df
    for col in df.columns:
        if col in skip: continue
        c = pd.to_numeric(df[col], errors="coerce")
        if c.notna().any(): df[col] = c
    return df

def bool_from_response(val):
    return str(val).strip().lower() in ("yes","true","1","y","checked")

def score_response_0_2(val):
    return {"yes":2,"somewhat":1}.get(str(val).strip().lower(),0)

def score_response_pct(val):
    return score_response_0_2(val)/2*100.0

def prettify_signal_name(name):
    for p in ("Signals and indicators [","Symptoms: [","Observations ["):
        name = name.replace(p,"")
    return name.replace("]","")

def drop_blank_tail_rows(df, required_cols):
    present = [c for c in required_cols if c in df.columns]
    return df.dropna(subset=present or None, how="all").copy()

def to_float(value, default=0.0):
    if value is None: return default
    try:
        if pd.isna(value): return default
    except Exception: pass
    try: return float(str(value).strip())
    except Exception: return default

def to_int(value, default=0):
    return int(round(to_float(value, default)))

def normalize_0_10_to_pct(series, inverse=False):
    s = pd.to_numeric(series if isinstance(series,pd.Series) else pd.Series(series), errors="coerce")
    return ((10-s).clip(0,10)/10.0*100.0) if inverse else (s.clip(0,10)/10.0*100.0)

def normalize_1_5_to_pct(series):
    s = pd.to_numeric(series if isinstance(series,pd.Series) else pd.Series(series), errors="coerce")
    return (s-1).clip(0,4)/4.0*100.0

def normalize_flag_count_to_pct(series, max_flags):
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    return pd.Series(0.0,index=s.index) if max_flags<=0 else (s.clip(0,max_flags)/max_flags*100.0)

def weighted_average_percent(df, col_weight_pairs, from_response=False):
    num,denom = pd.Series(0.0,index=df.index),0.0
    for col,weight in col_weight_pairs:
        if col in df.columns and weight>0:
            vals = df[col].apply(score_response_pct) if from_response else pd.to_numeric(df[col],errors="coerce").fillna(0.0)
            num += vals*weight; denom += weight
    return num/denom if denom else pd.Series(0.0,index=df.index)

def confidence_from_count(count,trend,level):
    s = (2 if count>=5 else 1 if count>=3 else 0)+(1 if trend!="Stable" else 0)+(1 if level in("Medium","High") else 0)
    return "High" if s>=4 else "Medium" if s>=2 else "Low"

def level_from_percent(score_pct,medium_pct,high_pct):
    s=to_float(score_pct)
    return "High" if s>=high_pct else "Medium" if s>=medium_pct else "Low"

def trend_from_deviation_pct(dev_pct,threshold_pct):
    d=to_float(dev_pct)
    return "Rising" if d>threshold_pct else "Falling" if d<-threshold_pct else "Stable"

def alert_rank(severity):
    return {"Monitor":1,"Pay attention today":2,"High concern":3}.get(severity,0)

def tone_color_tag(tone):
    return {"error":"red","warning":"orange","info":"blue","success":"green"}.get(tone,"gray")

def split_two(items):
    mid=(len(items)+1)//2; return items[:mid],items[mid:]

def find_possible_columns(df,patterns):
    lowered={c.lower():c for c in df.columns}
    return [o for l,o in lowered.items() if any(p in l for p in patterns)]

def build_sleeping_pills_flag_series(daily):
    if COL_SLEEPING_PILLS not in daily.columns: return pd.Series(0,index=daily.index,dtype=int)
    vals=daily[COL_SLEEPING_PILLS]
    if pd.api.types.is_numeric_dtype(vals): return (pd.to_numeric(vals,errors="coerce").fillna(0)>0).astype(int)
    return vals.apply(bool_from_response).astype(int)

def add_personal_baselines(df,settings,domains):
    if df.empty: return df
    window=max(int(settings.get("baseline_window_days",14)),3)
    for name in domains:
        sc=f"{name} Score %"; prev=df[sc].shift(1)
        bl=prev.rolling(window=window,min_periods=3).mean()
        std=prev.rolling(window=window,min_periods=3).std()
        df[f"{name} Baseline %"]=bl; df[f"{name} Baseline Std %"]=std
        df[f"{name} Baseline Difference %"]=df[sc]-bl
        safe_std=std.where(std.notna()&(std>0),1.0)
        z=(df[sc]-bl)/safe_std
        df[f"{name} Baseline Z"]=z.where(bl.notna(),0.0).fillna(0.0)
    return df

def build_domain_summary(df,settings,domains,include_reasons=True,reason_labels=None):
    if df.empty: return {}
    rl=reason_labels or REASON_LABELS
    latest=df.iloc[-1]; last5=df.tail(5)
    mp=float(settings["medium_threshold_pct"]); hp=float(settings["high_threshold_pct"])
    tt=float(settings["trend_threshold_pct"]); at=float(settings.get("anomaly_z_threshold",1.5))
    hat=float(settings.get("high_anomaly_z_threshold",2.5)); summary={}
    for name in domains:
        sp=to_float(latest.get(f"{name} Score %",0.0)); dp=to_float(latest.get(f"{name} Deviation %",0.0))
        zv=to_float(latest.get(f"{name} Baseline Z",0.0)); dv=to_float(latest.get(f"{name} Baseline Difference %",0.0))
        level=level_from_percent(sp,mp,hp); trend=trend_from_deviation_pct(dp,tt)
        conf=confidence_from_count(len(last5),trend,level)
        direction="higher" if dv>=0 else "lower"
        if abs(zv)>=hat:   bn=f"much {direction} than your recent baseline ({dv:+.1f} points)"; bzt=f"z={zv:+.2f}"
        elif abs(zv)>=at:  bn=f"noticeably {direction} than your recent baseline ({dv:+.1f} points)"; bzt=f"z={zv:+.2f}"
        elif pd.notna(latest.get(f"{name} Baseline %",pd.NA)): bn=f"close to your recent baseline ({dv:+.1f} points)"; bzt=f"z={zv:+.2f}"
        else: bn=bzt=""
        item=dict(score_pct=sp,level=level,trend=trend,confidence=conf,baseline_z=zv,baseline_diff_pct=dv,baseline_note=bn,baseline_z_text=bzt)
        if include_reasons:
            cc=[c for c in df.columns if c.startswith(f"{name} - ")]
            item["reasons"]=[rl.get(col,rl.get(col.replace(f"{name} - ",""),col.replace(f"{name} - ",""))) for col,_ in sorted([(c,to_float(latest.get(c,0.0))) for c in cc],key=lambda x:x[1],reverse=True) if to_float(latest.get(col,0.0))>0][:4]
        if name=="Depression" and to_int(latest.get("Depression Flags",0))==0:
            item.update(level="Low",trend="Stable",confidence="Low",reasons=[],baseline_note="",baseline_z_text="")
        summary[name]=item
    return summary

# =========================================================
# LEGACY MODELS
# =========================================================
def build_daily_depression_flag_series(daily):
    mood=pd.to_numeric(daily.get(COL_MOOD,pd.Series(pd.NA,index=daily.index)),errors="coerce")
    ms=pd.to_numeric(daily.get(COL_MENTAL_SPEED,pd.Series(pd.NA,index=daily.index)),errors="coerce")
    mot=pd.to_numeric(daily.get(COL_MOTIVATION,pd.Series(pd.NA,index=daily.index)),errors="coerce")
    return ((mood<=3)|((ms<4)&(mot<4))).fillna(False).astype(int)

def build_snapshot_depression_flag_series(df):
    result=pd.Series(False,index=df.index)
    for col in ["Symptoms: [Very low or depressed mood]","Symptoms: [Somewhat low or depressed mood]"]:
        if col in df.columns: result|=df[col].astype(str).str.strip().str.lower().isin(("yes","somewhat"))
    for col in find_possible_columns(df,["experiencing a down","going to experience a down"]):
        result|=df[col].astype(str).str.strip().str.lower().isin(("yes","somewhat"))
    return result.astype(int)

def build_domain_scores(daily,domain_name,config,settings):
    spp=build_sleeping_pills_flag_series(daily)*100.0; cp=[]
    for label,source_col,inverse,weight_key in config["components"]:
        oc=f"{domain_name} - {label}"
        src=daily[source_col] if source_col in daily.columns else pd.Series(0,index=daily.index)
        daily[oc]=normalize_0_10_to_pct(src,inverse=inverse)
        if label=="Low Sleep Quality": daily[oc]=pd.concat([daily[oc],spp],axis=1).max(axis=1)
        cp.append((oc,float(settings[weight_key])))
    fsc=f"{domain_name} - Flags"; fc=f"{domain_name} Flags"
    if config.get("custom_flag_logic")=="depression":
        daily[fc]=build_daily_depression_flag_series(daily); daily[fsc]=normalize_flag_count_to_pct(daily[fc],max_flags=1)
    else:
        fl=[c for c in config["flags"] if c in daily.columns]
        daily[fc]=daily[fl].sum(axis=1) if fl else 0
        daily[fsc]=normalize_flag_count_to_pct(daily[fc],max_flags=len(fl)) if fl else 0.0
    cp.append((fsc,float(settings[config["flag_weight_key"]])))
    sc=f"{domain_name} Score %"; ac=f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average ({domain_name} %)"; dc=f"{domain_name} Deviation %"
    daily[sc]=weighted_average_percent(daily,cp); daily[ac]=daily[sc].rolling(window=DAILY_ROLLING_WINDOW_DAYS,min_periods=1).mean(); daily[dc]=daily[sc]-daily[ac]
    return daily

def build_daily_model_from_form(form_df,settings):
    if form_df.empty or "Timestamp" not in form_df.columns: return pd.DataFrame(),None
    working=convert_numeric(form_df.copy())
    working["Timestamp"]=pd.to_datetime(working["Timestamp"],errors="coerce"); working["Date"]=working["Timestamp"].dt.date
    sig_cols=[c for c in working.columns if c.startswith("Signals and indicators [")]
    for col in sig_cols: working[col]=working[col].apply(bool_from_response).astype(int)
    num_cols=[c for c in [COL_MOOD,COL_SLEEP_HOURS,COL_SLEEP_QUALITY,COL_ENERGY,COL_MENTAL_SPEED,COL_IMPULSIVITY,COL_MOTIVATION,COL_IRRITABILITY,COL_AGITATION,COL_UNUSUAL,COL_SUSPICIOUS,COL_CERTAINTY] if c in working.columns]
    ds=working.groupby("Date",as_index=False)[num_cols].mean() if num_cols else pd.DataFrame({"Date":working["Date"].dropna().unique()})
    df2=working.groupby("Date",as_index=False)[sig_cols].sum() if sig_cols else pd.DataFrame({"Date":working["Date"].dropna().unique()})
    if COL_SLEEPING_PILLS in working.columns:
        sm=working.groupby("Date",as_index=False)[COL_SLEEPING_PILLS].agg(lambda s:int(any(bool_from_response(v) for v in s)))
    else: sm=pd.DataFrame({"Date":working["Date"].dropna().unique()})
    daily=(ds.merge(df2,on="Date",how="outer").merge(sm,on="Date",how="outer").sort_values("Date").reset_index(drop=True))
    daily["DateLabel"]=pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")
    if COL_SLEEPING_PILLS in daily.columns: daily[COL_SLEEPING_PILLS]=daily[COL_SLEEPING_PILLS].fillna(0).astype(int)
    for dn,cfg in DAILY_DOMAIN_CONFIG.items(): daily=build_domain_scores(daily,dn,cfg,settings)
    daily["Sleeping Pills Flag"]=build_sleeping_pills_flag_series(daily)
    mw={k:float(settings[k]) for k in ["mixed_dep_weight","mixed_mania_weight","mixed_psych_weight","mixed_low_sleep_quality_weight"]}
    mt=sum(mw.values()) or 1.0
    daily["Mixed Score %"]=(daily["Depression Score %"]*mw["mixed_dep_weight"]+daily["Mania Score %"]*mw["mixed_mania_weight"]+daily["Psychosis Score %"]*mw["mixed_psych_weight"]+daily.get("Depression - Low Sleep Quality",pd.Series(0,index=daily.index))*mw["mixed_low_sleep_quality_weight"])/mt
    daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"]=daily["Mixed Score %"].rolling(DAILY_ROLLING_WINDOW_DAYS,min_periods=1).mean()
    daily["Mixed Deviation %"]=daily["Mixed Score %"]-daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"]
    for oc,cols in [("Mixed Flags",[SIG_MIXED_NOW,SIG_MIXED_COMING,SIG_WITHDRAW,SIG_LESS_SLEEP,SIG_MORE_ACTIVITY]),("Concerning Situation Flags",[SIG_NOT_MYSELF,SIG_MISSED_MEDS,SIG_ROUTINE,SIG_STRESS_PSYCH,SIG_STRESS_PHYS]),("Self-Reported Depression",[SIG_DOWN_NOW,SIG_DOWN_COMING]),("Self-Reported Mania",[SIG_UP_NOW,SIG_UP_COMING]),("Self-Reported Mixed",[SIG_MIXED_NOW,SIG_MIXED_COMING])]:
        present=[c for c in cols if c in daily.columns]; daily[oc]=daily[present].sum(axis=1) if present else 0
    daily=add_personal_baselines(daily,settings,DOMAIN_NAMES)
    return daily,build_domain_summary(daily,settings,DOMAIN_NAMES,include_reasons=True)

def build_snapshot_model_from_quick_form(qf_df,settings):
    if qf_df.empty or "Timestamp" not in qf_df.columns: return None,pd.DataFrame()
    w=drop_blank_tail_rows(qf_df.copy(),["Timestamp"]); w["Timestamp"]=pd.to_datetime(w["Timestamp"],errors="coerce"); w=w.sort_values("Timestamp").reset_index(drop=True)
    for dn,cfg in SNAPSHOT_DOMAIN_CONFIG.items():
        pairs=[(col,float(settings[wk])) for col,wk in cfg["components"]]
        w[f"{dn} Score %"]=weighted_average_percent(w,pairs,from_response=True)
    w["Depression Flags"]=build_snapshot_depression_flag_series(w)
    mwl=[float(settings[k]) for k in ("mixed_dep_weight","mixed_mania_weight","mixed_psych_weight")]; mt=sum(mwl) or 1.0
    w["Mixed Score %"]=(w["Depression Score %"]*mwl[0]+w["Mania Score %"]*mwl[1]+w["Psychosis Score %"]*mwl[2])/mt
    for name in DOMAIN_NAMES:
        avg=w[f"{name} Score %"].rolling(10,min_periods=1).mean()
        w[f"10-Response Average ({name} %)"]=avg; w[f"Deviation From 10-Response Average ({name} %)"]=w[f"{name} Score %"]-avg
    w["FilterDate"]=w["Timestamp"].dt.date; w["TimeLabel"]=w["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    summary={}
    if not w.empty:
        latest=w.iloc[-1]; mp=float(settings["medium_threshold_pct"]); hp=float(settings["high_threshold_pct"]); tt=float(settings["trend_threshold_pct"])
        for name in DOMAIN_NAMES:
            sp=to_float(latest.get(f"{name} Score %",0.0)); dp=to_float(latest.get(f"Deviation From 10-Response Average ({name} %)",0.0))
            level=level_from_percent(sp,mp,hp); trend=trend_from_deviation_pct(dp,tt); conf=confidence_from_count(len(w.tail(5)),trend,level)
            if name=="Depression" and to_int(latest.get("Depression Flags",0))==0: level,trend,conf="Low","Stable","Low"
            summary[name]=dict(score_pct=sp,level=level,trend=trend,confidence=conf)
    return summary,w

# =========================================================
# NEW FORM MODEL
# =========================================================
def prepare_new_form_raw(df):
    if df.empty: return df
    w=drop_blank_tail_rows(df.copy(),["Timestamp"])
    w["Timestamp"]=pd.to_datetime(w["Timestamp"],errors="coerce",dayfirst=True); w["Date"]=w["Timestamp"].dt.date
    yn=[NF_FLAG_NOT_MYSELF,NF_FLAG_MOOD_SHIFT,NF_FLAG_MISSED_MEDS,NF_FLAG_SLEEP_MEDS,NF_FLAG_ROUTINE,NF_FLAG_PHYS,NF_FLAG_PSYCH,NF_OBS_UP_NOW,NF_OBS_DOWN_NOW,NF_OBS_MIXED_NOW,NF_OBS_UP_COMING,NF_OBS_DOWN_COMING,NF_OBS_MIXED_COMING]
    for col in (c for c in w.columns if c not in ("Timestamp","Date") and c not in yn): w[col]=pd.to_numeric(w[col],errors="coerce")
    for col in (c for c in yn if c in w.columns): w[col]=w[col].apply(bool_from_response).astype(int)
    return w.sort_values("Timestamp").reset_index(drop=True)

def build_nf_depression_flag(df):
    result=pd.Series(False,index=df.index)
    if NF_LOW_MOOD in df.columns: result|=pd.to_numeric(df[NF_LOW_MOOD],errors="coerce").fillna(0)>=3
    if NF_SELF_HARM in df.columns: result|=pd.to_numeric(df[NF_SELF_HARM],errors="coerce").fillna(0)>=2
    for col in (c for c in [NF_OBS_DOWN_NOW,NF_OBS_DOWN_COMING] if c in df.columns): result|=df[col].astype(int)>0
    return result.astype(int)

def build_new_form_model(nf_df,settings):
    if nf_df.empty or "Timestamp" not in nf_df.columns: return pd.DataFrame(),None
    w=nf_df.copy(); w["Timestamp"]=pd.to_datetime(w["Timestamp"],errors="coerce"); w["Date"]=w["Timestamp"].dt.date
    num_cols=[NF_LOW_MOOD,NF_SLOWED,NF_MOTIVATION,NF_ANHEDONIA,NF_WITHDRAWAL,NF_SELF_HARM,NF_ELEVATED_MOOD,NF_SPED_UP,NF_RACING,NF_GOAL_DRIVE,NF_IMPULSIVITY,NF_AGITATION,NF_IRRITABILITY,NF_CANT_SETTLE,NF_HIGH_E_LOW_MOOD,NF_RAPID_SHIFTS,NF_HEARD_SAW,NF_SUSPICIOUS,NF_TRUST_PERCEPT,NF_CONFIDENCE_REA,NF_DISTRESS,NF_WORK_FUNC,NF_DAILY_FUNC,NF_UNLIKE_SELF,NF_SOMETHING_WRONG,NF_CONCERNED,NF_DISORG_THOUGHTS,NF_UNSTABLE_ATTN,NF_DRIVEN_ACT,NF_INTENSIFYING,NF_TOWARDS_EPISODE,NF_SLEEP_HOURS,NF_SLEEP_QUALITY]
    yn_cols=[NF_FLAG_NOT_MYSELF,NF_FLAG_MOOD_SHIFT,NF_FLAG_MISSED_MEDS,NF_FLAG_SLEEP_MEDS,NF_FLAG_ROUTINE,NF_FLAG_PHYS,NF_FLAG_PSYCH,NF_OBS_UP_NOW,NF_OBS_DOWN_NOW,NF_OBS_MIXED_NOW,NF_OBS_UP_COMING,NF_OBS_DOWN_COMING,NF_OBS_MIXED_COMING]
    np2=[c for c in num_cols if c in w.columns]; ynp=[c for c in yn_cols if c in w.columns]
    dn=w.groupby("Date",as_index=False)[np2].mean() if np2 else pd.DataFrame({"Date":w["Date"].dropna().unique()})
    df2=w.groupby("Date",as_index=False)[ynp].max() if ynp else pd.DataFrame({"Date":w["Date"].dropna().unique()})
    daily=(dn.merge(df2,on="Date",how="outer").sort_values("Date").reset_index(drop=True))
    daily["DateLabel"]=pd.to_datetime(daily["Date"]).dt.strftime("%Y-%m-%d")
    for dn2,cfg in NF_DOMAIN_CONFIG.items():
        cp=[]
        for label,src_col,wk in cfg["components"]:
            oc=f"{dn2} - {label}"; src=daily[src_col] if src_col in daily.columns else pd.Series(1,index=daily.index)
            daily[oc]=normalize_1_5_to_pct(src); cp.append((oc,float(settings[wk])))
        fsc=f"{dn2} - Flags"; fc=f"{dn2} Flags"
        obs=[c for c in cfg["yes_no_flags"] if c in daily.columns]
        daily[fc]=daily[obs].sum(axis=1) if obs else 0
        daily[fsc]=normalize_flag_count_to_pct(daily[fc],max_flags=len(obs)) if obs else 0.0
        cp.append((fsc,float(settings[cfg["flag_weight_key"]])))
        sc=f"{dn2} Score %"; ac=f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average ({dn2} %)"; dc=f"{dn2} Deviation %"
        daily[sc]=weighted_average_percent(daily,cp); daily[ac]=daily[sc].rolling(DAILY_ROLLING_WINDOW_DAYS,min_periods=1).mean(); daily[dc]=daily[sc]-daily[ac]
    daily["Depression Flags"]=build_nf_depression_flag(daily)
    hel=normalize_1_5_to_pct(daily[NF_HIGH_E_LOW_MOOD]) if NF_HIGH_E_LOW_MOOD in daily.columns else pd.Series(0.0,index=daily.index)
    rs=normalize_1_5_to_pct(daily[NF_RAPID_SHIFTS]) if NF_RAPID_SHIFTS in daily.columns else pd.Series(0.0,index=daily.index)
    md,mm,mp2,mh,mr=float(settings["nf_mix_dep_w"]),float(settings["nf_mix_man_w"]),float(settings["nf_mix_psy_w"]),float(settings["nf_mix_high_e_low_mood_w"]),float(settings["nf_mix_rapid_shifts_w"])
    mt=(md+mm+mp2+mh+mr) or 1.0
    daily["Mixed Score %"]=(daily["Depression Score %"]*md+daily["Mania Score %"]*mm+daily["Psychosis Score %"]*mp2+hel*mh+rs*mr)/mt
    daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"]=daily["Mixed Score %"].rolling(DAILY_ROLLING_WINDOW_DAYS,min_periods=1).mean()
    daily["Mixed Deviation %"]=daily["Mixed Score %"]-daily[f"{DAILY_ROLLING_WINDOW_DAYS}-Day Average (Mixed %)"]
    mfc=[c for c in [NF_OBS_MIXED_NOW,NF_OBS_MIXED_COMING] if c in daily.columns]
    daily["Mixed Flags"]=daily[mfc].sum(axis=1) if mfc else 0
    meta=[c for c in NF_META_COLS if c in daily.columns]
    daily["Meta-Awareness Score"]=daily[meta].apply(lambda r:sum(1 for v in r if to_float(v)>=3)/len(meta)*100,axis=1) if meta else 0.0
    cp2=[c for c in NF_CONCERN_FLAGS if c in daily.columns]
    daily["Concerning Situation Flags"]=daily[cp2].sum(axis=1) if cp2 else 0
    daily["Sleeping Pills Flag"]=(daily[NF_FLAG_SLEEP_MEDS]>0).astype(int) if NF_FLAG_SLEEP_MEDS in daily.columns else 0
    daily=add_personal_baselines(daily,settings,DOMAIN_NAMES)
    return daily,build_domain_summary(daily,settings,DOMAIN_NAMES,include_reasons=True,reason_labels=NF_REASON_LABELS)

# =========================================================
# ALERT ENGINE
# =========================================================
def build_alerts(primary_data,primary_summary,settings,cross_summaries=None,cross_dep_flags=None):
    if primary_data.empty or not primary_summary: return []
    cross_summaries=cross_summaries or []; cross_dep_flags=cross_dep_flags or [True]*len(cross_summaries)
    latest=primary_data.iloc[-1]; mp=float(settings["medium_threshold_pct"])
    at=float(settings.get("anomaly_z_threshold",1.5)); hat=float(settings.get("high_anomaly_z_threshold",2.5))
    pd_days=int(settings.get("persistence_days",3)); pdf=to_int(latest.get("Depression Flags",0))>0
    def get_persistence(domain):
        recent=primary_data[f"{domain} Score %"].tail(pd_days)
        return len(recent)>=pd_days and bool((recent>=mp).all())
    alerts=[]
    for name in DOMAIN_NAMES:
        item=primary_summary[name]
        if name=="Depression" and not pdf: continue
        zv=to_float(item.get("baseline_z",0.0)); dv=to_float(item.get("baseline_diff_pct",0.0)); details=[]
        if item["level"] in("Medium","High"): details.append(f"{name} score is {item['level'].lower()} at {item['score_pct']:.1f}%.")
        if item["trend"] in("Rising","Falling"): details.append(f"Recent direction is {item['trend'].lower()}.")
        if abs(zv)>=at:
            direction="above" if dv>=0 else "below"; details.append(f"This is {abs(dv):.1f} points {direction} your personal baseline (z={zv:+.2f}).")
        if get_persistence(name): details.append(f"Has stayed at or above medium for the last {pd_days} days.")
        for (label,cs),df_flag in zip(cross_summaries,cross_dep_flags):
            if cs and name in cs:
                sl=cs[name]["level"]
                if sl in("Medium","High") and (name!="Depression" or df_flag): details.append(f"{label} model also shows {name.lower()} as {sl.lower()}.")
        if item["level"]=="High": sev="High concern"
        elif item["level"]=="Medium" and item["trend"]=="Rising": sev="Pay attention today"
        elif abs(zv)>=hat: sev="Pay attention today"
        elif get_persistence(name): sev="Pay attention today"
        elif abs(zv)>=at and item["score_pct"]>=mp*0.8: sev="Monitor"
        else: continue
        st2=f"{name} looks {item['level'].lower()} with a {item['trend'].lower()} recent direction."
        if abs(zv)>=at: st2+=" Also unusual relative to your recent baseline."
        alerts.append(dict(severity=sev,domain=name,title=f"{name} pattern",summary=st2,details=details))
    cf=to_int(latest.get("Concerning Situation Flags",0))
    if cf>0:
        alerts.append(dict(severity="High concern" if cf>2 else "Pay attention today",domain="General",title="Concerning situation flags",summary=f"{cf} concerning situation flag(s) in the latest data.",details=["Can matter even if domain scores are not high.","Check routine disruption, missed meds, or major stressor signals."]))
    amed=[d for d in DOMAIN_NAMES if d!="Depression" and primary_summary[d]["level"] in("Medium","High")]
    ahigh=[d for d in DOMAIN_NAMES if d!="Depression" and primary_summary[d]["level"]=="High"]
    if pdf and primary_summary["Depression"]["level"] in("Medium","High"):
        amed.append("Depression")
        if primary_summary["Depression"]["level"]=="High": ahigh.append("Depression")
    if len(ahigh)>=2 or len(amed)>=3:
        alerts.append(dict(severity="High concern",domain="General",title="Multiple elevated patterns",summary="More than one domain is elevated at the same time.",details=[f"Elevated domains: {', '.join(amed)}.","Worth extra attention — not confined to one area."]))
    return sorted(alerts,key=lambda a:(-alert_rank(a["severity"]),a["title"]))

def build_today_summary(daily_summary,alerts,daily_model_data):
    if not daily_summary or daily_model_data.empty: return "No interpretation is available yet."
    pn,p=max(daily_summary.items(),key=lambda kv:({"High":3,"Medium":2,"Low":1}.get(kv[1]["level"],0),kv[1]["score_pct"],abs(kv[1].get("baseline_z",0.0))))
    parts=[f"Main pattern today: {pn.lower()} looks {p['level'].lower()}"]
    if p["trend"]!="Stable": parts[0]+=f" and is {p['trend'].lower()}"
    parts[0]+=f" ({p['score_pct']:.1f}%)."
    if p.get("baseline_note"): parts.append(f"Compared with your usual, it is {p['baseline_note']}.")
    if p.get("reasons"): parts.append(f"Main drivers: {', '.join(p['reasons'][:3])}.")
    if alerts: parts.append(f"Overall status: {alerts[0]['severity']}.")
    return " ".join(parts)

# =========================================================
# WARNING HELPERS
# =========================================================
def get_latest_form_warning_items(form_df):
    if form_df.empty or "Timestamp" not in form_df.columns: return [],[]
    latest=form_df.sort_values("Timestamp").iloc[-1]
    sigs=[c for c in form_df.columns if c.startswith("Signals and indicators [")]
    flagged=[prettify_signal_name(c) for c in sigs if bool_from_response(latest.get(c,""))]
    thresholds=[(COL_MOOD,"Mood score is low",lambda v:v<=4),(COL_SLEEP_HOURS,"Sleep hours are low",lambda v:v<=5),(COL_SLEEP_QUALITY,"Sleep quality is poor",lambda v:v<=4),(COL_MOTIVATION,"Motivation is low",lambda v:v<=4),(COL_ENERGY,"Energy is elevated",lambda v:v>=6),(COL_MENTAL_SPEED,"Mental speed is elevated",lambda v:v>=6),(COL_IMPULSIVITY,"Impulsivity is elevated",lambda v:v>=6),(COL_IRRITABILITY,"Irritability is elevated",lambda v:v>=6),(COL_AGITATION,"Agitation is elevated",lambda v:v>=6),(COL_UNUSUAL,"Unusual perceptions are elevated",lambda v:v>=6),(COL_SUSPICIOUS,"Suspiciousness is elevated",lambda v:v>=6),(COL_CERTAINTY,"Belief certainty is elevated",lambda v:v>=6)]
    concerning=[]
    for col,label,check in thresholds:
        if col in latest.index:
            val=pd.to_numeric(latest[col],errors="coerce")
            if pd.notna(val) and check(val): concerning.append(f"{label} ({val:.1f})")
    if COL_SLEEPING_PILLS in latest.index and bool_from_response(latest.get(COL_SLEEPING_PILLS,"")): concerning.append("Took sleeping medication (treat as bad sleep flag)")
    return flagged,concerning

def get_latest_quick_form_warning_items(qf_df):
    if qf_df.empty or "Timestamp" not in qf_df.columns: return [],[]
    latest=qf_df.sort_values("Timestamp").iloc[-1]; signals=[]
    for col in (c for c in qf_df.columns if c!="Timestamp" and not c.endswith((" Numeric"," Percent"," Trend"))):
        val=str(latest.get(col,"")).strip().lower()
        if val in("yes","somewhat"): signals.append(f"{prettify_signal_name(col)} — {'Yes' if val=='yes' else 'Somewhat'}")
    yc=sum(1 for s in signals if s.endswith("Yes")); sc=sum(1 for s in signals if s.endswith("Somewhat"))
    concerning=[]
    if yc>=3: concerning.append(f"Several snapshot symptoms marked Yes ({yc})")
    if sc>=3: concerning.append(f"Several snapshot symptoms marked Somewhat ({sc})")
    return signals,concerning

def get_latest_nf_warning_items(nf_df):
    if nf_df.empty or "Timestamp" not in nf_df.columns: return [],[]
    latest=nf_df.sort_values("Timestamp").iloc[-1]; signals=[]; concerning=[]
    scale_items=[(NF_LOW_MOOD,"Low mood"),(NF_SLOWED,"Slowed / low energy"),(NF_MOTIVATION,"Low motivation"),(NF_ANHEDONIA,"Anhedonia"),(NF_WITHDRAWAL,"Social withdrawal"),(NF_SELF_HARM,"Self-harm ideation"),(NF_ELEVATED_MOOD,"Elevated mood"),(NF_SPED_UP,"Sped up / high energy"),(NF_RACING,"Racing thoughts"),(NF_GOAL_DRIVE,"Goal-directed drive"),(NF_IMPULSIVITY,"Impulsivity"),(NF_AGITATION,"Agitation"),(NF_IRRITABILITY,"Irritability"),(NF_CANT_SETTLE,"Unable to settle"),(NF_HIGH_E_LOW_MOOD,"High energy + low mood"),(NF_RAPID_SHIFTS,"Rapid emotional shifts"),(NF_HEARD_SAW,"Heard / saw things"),(NF_SUSPICIOUS,"Suspicion / paranoia"),(NF_TRUST_PERCEPT,"Trouble trusting perceptions"),(NF_CONFIDENCE_REA,"Confidence in unusual experiences"),(NF_DISTRESS,"Distress from experiences"),(NF_DISORG_THOUGHTS,"Disorganised thoughts"),(NF_SLEEP_QUALITY,"Poor sleep quality")]
    for col,label in scale_items:
        if col in latest.index:
            val=pd.to_numeric(latest[col],errors="coerce")
            if pd.notna(val):
                if val>=4: concerning.append(f"{label} ({val:.0f}/5)")
                elif val>=3: signals.append(f"{label} (moderate, {val:.0f}/5)")
    meta_items={NF_UNLIKE_SELF:"Feels unlike usual self",NF_SOMETHING_WRONG:"Thinks something may be wrong",NF_CONCERNED:"Concerned about current state",NF_INTENSIFYING:"State intensifying",NF_TOWARDS_EPISODE:"Moving towards an episode"}
    for col,label in meta_items.items():
        if col in latest.index:
            val=pd.to_numeric(latest[col],errors="coerce")
            if pd.notna(val) and val>=3: concerning.append(f"{label} ({val:.0f}/5)")
    flag_items={NF_FLAG_NOT_MYSELF:"Feeling not like myself",NF_FLAG_MOOD_SHIFT:"Noticed mood shift",NF_FLAG_MISSED_MEDS:"Missed medication",NF_FLAG_SLEEP_MEDS:"Took sleeping / anti-anxiety medication",NF_FLAG_ROUTINE:"Significant routine disruption",NF_FLAG_PHYS:"Major physiological stress",NF_FLAG_PSYCH:"Major psychological stress"}
    for col,label in flag_items.items():
        if col in latest.index and bool_from_response(latest[col]): signals.append(label)
    return signals,concerning

def get_model_concerning_findings(nf_summary,daily_summary,snap_summary,nf_df,daily_df,snap_df):
    nf_f=[]; other_f=[]
    nf_dep=not nf_df.empty and to_int(nf_df.iloc[-1].get("Depression Flags",0))>0
    d_dep=not daily_df.empty and to_int(daily_df.iloc[-1].get("Depression Flags",0))>0
    s_dep=not snap_df.empty and to_int(snap_df.iloc[-1].get("Depression Flags",0))>0
    for summ,dep,label,fl in [(nf_summary,nf_dep,"New form",nf_f),(daily_summary,d_dep,"Daily",other_f),(snap_summary,s_dep,"Snapshot",other_f)]:
        if summ:
            for name in DOMAIN_NAMES:
                if name=="Depression" and not dep: continue
                item=summ[name]
                if item["level"] in("Medium","High"): fl.append(f"{label} {name.lower()} is {item['level'].lower()} and {item['trend'].lower()}")
                if abs(to_float(item.get("baseline_z",0.0)))>=1.5: fl.append(f"{label} {name.lower()} is unusual vs recent baseline")
            if dep and label!="New form": other_f.append(f"{label} depression flag is present")
    if not nf_df.empty:
        cf=to_float(nf_df.iloc[-1].get("Concerning Situation Flags",0))
        if cf>0: nf_f.append(f"Concerning situation flags: {int(cf)}")
    return nf_f,other_f

# =========================================================
# UI HELPERS
# =========================================================
def _render_two_col_list(items,color):
    if not items: st.markdown(":gray[- None]"); return
    left,right=split_two(items); c1,c2=st.columns(2)
    for col,chunk in((c1,left),(c2,right)):
        with col:
            for item in chunk: st.markdown(f":{color}[- {item}]")

def render_status_card(title,score_pct,level,trend,confidence):
    lc={"High":"red","Medium":"orange","Low":"green"}.get(level,"gray")
    cc={"High":"green","Medium":"orange","Low":"gray"}.get(confidence,"gray")
    tc={"Rising":"orange","Falling":"blue","Stable":"green"}.get(trend,"gray")
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(f"**Current:** :{lc}[{level}] ({score_pct:.1f}%)")
        st.markdown(f"**Trend:** :{tc}[{trend}]")
        st.markdown(f"**Confidence:** :{cc}[{confidence}]")

def render_daily_card(title,data):
    lc={"High":"red","Medium":"orange","Low":"green"}.get(data["level"],"gray")
    cc={"High":"green","Medium":"orange","Low":"gray"}.get(data["confidence"],"gray")
    tc={"Rising":"orange","Falling":"blue","Stable":"green"}.get(data["trend"],"gray")
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(f"**Current state:** :{lc}[{data['level']}] ({data['score_pct']:.1f}%)")
        st.markdown(f"**Recent direction:** :{tc}[{data['trend']}]")
        st.markdown(f"**Confidence:** :{cc}[{data['confidence']}]")
        if data.get("baseline_note"): st.markdown(f"**Compared with usual:** {data['baseline_note']}")
        if data.get("baseline_z_text"):
            with st.expander("Baseline detail"): st.write(data["baseline_z_text"])
        st.markdown("**Main drivers:**")
        _render_two_col_list(data.get("reasons") or ["No strong drivers"],lc)

def render_two_column_flag_box(title,items,tone="info"):
    color=tone_color_tag(tone)
    with st.container(border=True):
        st.markdown(f"#### :{color}[{title}]")
        _render_two_col_list(items,color)

def render_alert_card(alert):
    tone={"High concern":"error","Pay attention today":"warning","Monitor":"info"}.get(alert["severity"],"info")
    color=tone_color_tag(tone)
    with st.container(border=True):
        st.markdown(f"#### :{color}[{alert['title']}]")
        st.markdown(f"**Status:** :{color}[{alert['severity']}]")
        st.markdown(f"**Summary:** {alert['summary']}")
        if alert.get("details"): st.markdown("**Details:**"); _render_two_col_list(alert["details"],color)

def render_summary_cards(summary,detailed=False):
    if not summary: st.info("No summary available."); return
    for col,name in zip(st.columns(len(summary)),summary):
        with col:
            if detailed: render_daily_card(name,summary[name])
            else: render_status_card(name,summary[name]["score_pct"],summary[name]["level"],summary[name]["trend"],summary[name]["confidence"])

def render_settings_form(session_key,settings_ui,columns_per_row=3):
    for section,items in settings_ui.items():
        st.markdown(f"#### {section}")
        for i in range(0,len(items),columns_per_row):
            row=items[i:i+columns_per_row]
            for col,(key,label,mn,mx,step) in zip(st.columns(len(row)),row):
                with col:
                    cur=st.session_state[session_key][key]; is_int=isinstance(step,int) or (isinstance(cur,int) and float(step).is_integer())
                    st.session_state[session_key][key]=st.number_input(label,min_value=int(mn) if is_int else float(mn),max_value=int(mx) if is_int else float(mx),value=int(cur) if is_int else float(cur),step=int(step) if is_int else float(step),key=f"{session_key}_{key}")

def filter_df_by_date(df,date_col,key_prefix):
    if df.empty or date_col not in df.columns: return df
    w=df[df[date_col].notna()].copy()
    if w.empty: return w
    dates=pd.to_datetime(w[date_col]); mn,mx=dates.min().date(),dates.max().date()
    r=st.date_input("Date range",value=(mn,mx),min_value=mn,max_value=mx,key=f"{key_prefix}_date_range")
    start,end=(r[0],r[1]) if isinstance(r,tuple) and len(r)==2 else (mn,mx)
    return w[(dates.dt.date>=start)&(dates.dt.date<=end)].copy()

def render_filtered_chart(df,date_col,label_col,title,default_cols,key_prefix,chart_type="line"):
    st.markdown(f"### {title}")
    if df.empty: st.info("No data available."); return
    filtered=filter_df_by_date(df,date_col,key_prefix); available=[c for c in default_cols if c in filtered.columns]
    selected=st.multiselect("Series",available,default=available,key=f"{key_prefix}_series")
    if filtered.empty: st.info("No data in selected date range."); return
    if not selected: st.info("Pick at least one series."); return
    (st.bar_chart if chart_type=="bar" else st.line_chart)(filtered[[label_col]+selected].set_index(label_col))

def render_chart_group(df,date_col,label_col,chart_defs):
    for chart in chart_defs: render_filtered_chart(df,date_col,label_col,chart["title"],chart["cols"],chart["key"],chart["type"])

def render_dataframe_picker(title,df,default_cols,key):
    st.markdown(f"### {title}")
    if df.empty: st.info("No data available."); return
    selected=st.multiselect(f"Choose {title} columns",df.columns.tolist(),default=default_cols or df.columns.tolist()[:12],key=key)
    if selected: st.dataframe(df[selected],use_container_width=True)

def _render_metrics_row(metrics):
    cols=st.columns(len(metrics))
    for col,(label,value) in zip(cols,metrics):
        with col: st.metric(label,value)

def _trend_chart(data,label_col,window_key):
    if data.empty: st.info("No data available."); return
    max_date=pd.to_datetime(data["Date"]).max().date(); min_date=pd.to_datetime(data["Date"]).min().date()
    window=st.selectbox("Trend window",["Last 7 days","Last 14 days","Last 30 days","All data"],index=1,key=window_key)
    offsets={"Last 7 days":6,"Last 14 days":13,"Last 30 days":29}
    start=(max_date-pd.Timedelta(days=offsets[window])) if window in offsets else min_date
    td=data[pd.to_datetime(data["Date"]).dt.date.between(start,max_date)]
    st.line_chart(td[[label_col,"Depression Score %","Mania Score %","Psychosis Score %","Mixed Score %"]].set_index(label_col))

# =========================================================
# GOOGLE SHEETS & PREP
# =========================================================
@st.cache_resource
def get_gspread_client():
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))

@st.cache_resource
def get_workbook():
    return get_gspread_client().open(SHEET_NAME)

@st.cache_data(ttl=60)
def load_sheet(tab_name):
    data=get_workbook().worksheet(tab_name).get_all_values()
    if not data: return pd.DataFrame()
    headers=[str(h).strip() if h else "" for h in data[0]]
    seen,uh={},[]
    for i,h in enumerate(headers):
        base=h or f"Unnamed_{i+1}"; seen[base]=seen.get(base,0)
        uh.append(f"{base}_{seen[base]}" if seen[base] else base); seen[base]+=1 if seen[base] else 1
    df=pd.DataFrame(data[1:],columns=uh).loc[:,lambda d:~d.columns.duplicated()]
    df=normalize_columns(df)
    for dt_col in("Timestamp","Date","Date (int)"):
        if dt_col in df.columns: df[dt_col]=pd.to_datetime(df[dt_col],errors="coerce",dayfirst=True)
    return df

def prepare_form_raw(df):
    if df.empty: return df
    w=convert_numeric(df.copy()); w=drop_blank_tail_rows(w,["Timestamp",COL_MOOD,COL_SLEEP_QUALITY,COL_ENERGY])
    if "Timestamp" in w.columns: w["Timestamp"]=pd.to_datetime(w["Timestamp"],errors="coerce"); w["Date"]=w["Timestamp"].dt.date
    return w.sort_values("Timestamp").reset_index(drop=True)

def prepare_quick_form_raw(df):
    if df.empty: return df
    w=drop_blank_tail_rows(df.copy(),["Timestamp"]); w["Timestamp"]=pd.to_datetime(w["Timestamp"],errors="coerce"); w=w.sort_values("Timestamp").reset_index(drop=True)
    for col in(c for c in w.columns if c!="Timestamp"):
        w[f"{col} Numeric"]=w[col].apply(score_response_0_2); w[f"{col} Percent"]=w[col].apply(score_response_pct); w[f"{col} Trend"]=w[f"{col} Percent"].diff()
    return w

# =========================================================
# PAGE RENDERERS
# =========================================================
def render_dashboard_page(form_data,quick_form_data,nf_model_data,nf_model_summary,daily_model_data,daily_model_summary,snapshot_model_summary,latest_nf_signals,latest_nf_findings,latest_form_signals,latest_form_findings,latest_snapshot_signals,latest_snapshot_findings,nf_model_findings,other_model_findings,alerts,today_summary):
    st.subheader("Dashboard")
    st.caption("New Form Model is the primary signal source. Daily and Snapshot are legacy cross-checks.")
    st.markdown("### Today's interpretation")
    top_sev=alerts[0]["severity"] if alerts else "Monitor"
    tone="error" if top_sev=="High concern" else "warning" if top_sev=="Pay attention today" else "info"
    render_two_column_flag_box("Today at a glance",[today_summary],tone=tone)
    st.markdown("### Current alerts")
    if alerts:
        for col,alert in zip(st.columns(min(3,len(alerts))),alerts[:3]):
            with col: render_alert_card(alert)
    else: st.info("No active alerts from current rules.")
    st.markdown("### Current state")
    st.markdown("#### New Form Model"); render_summary_cards(nf_model_summary,detailed=True)
    st.markdown("#### Daily Model (legacy)"); render_summary_cards(daily_model_summary,detailed=True)
    st.markdown("#### Snapshot Model (legacy)"); render_summary_cards(snapshot_model_summary,detailed=False)
    st.markdown("### Key warnings")
    c1,c2,c3=st.columns(3)
    with c1: render_two_column_flag_box("New form",latest_nf_findings+nf_model_findings+latest_nf_signals,tone="error" if(latest_nf_findings or nf_model_findings) else "warning")
    with c2: render_two_column_flag_box("Daily questionnaire / model",latest_form_findings+other_model_findings+latest_form_signals,tone="error" if(latest_form_findings or other_model_findings) else "warning")
    with c3: render_two_column_flag_box("Snapshot questionnaire / model",latest_snapshot_findings+latest_snapshot_signals,tone="warning")
    st.markdown("### Recent trends")
    st.markdown("**New Form**"); _trend_chart(nf_model_data,"DateLabel","dash_nf_trend")
    st.markdown("**Daily Model (legacy)**"); _trend_chart(daily_model_data,"DateLabel","dash_leg_trend")
    st.markdown("### Personal baseline (New Form)")
    if not nf_model_data.empty:
        ld=nf_model_data.iloc[-1]
        _render_metrics_row([("Depression vs baseline",f"{to_float(ld.get('Depression Baseline Difference %',0.0)):+.1f} pp"),("Mania vs baseline",f"{to_float(ld.get('Mania Baseline Difference %',0.0)):+.1f} pp"),("Psychosis vs baseline",f"{to_float(ld.get('Psychosis Baseline Difference %',0.0)):+.1f} pp"),("Mixed vs baseline",f"{to_float(ld.get('Mixed Baseline Difference %',0.0)):+.1f} pp")])
    else: st.info("No baseline data yet.")
    st.markdown("### Flags overview (New Form)")
    if not nf_model_data.empty:
        ld=nf_model_data.iloc[-1]
        _render_metrics_row([("Concerning flags",str(to_int(ld.get("Concerning Situation Flags",0)))),("Depression flags",str(to_int(ld.get("Depression Flags",0)))),("Mania flags",str(to_int(ld.get("Mania Flags",0)))),("Psychosis flags",str(to_int(ld.get("Psychosis Flags",0)))),("Meta-awareness",f"{to_float(ld.get('Meta-Awareness Score',0.0)):.0f}%")])
    st.markdown("### Recent activity")
    nft=nf_model_data["Timestamp"].max() if not nf_model_data.empty and "Timestamp" in nf_model_data.columns else None
    ft=form_data["Timestamp"].max() if not form_data.empty and "Timestamp" in form_data.columns else None
    st2=quick_form_data["Timestamp"].max() if not quick_form_data.empty and "Timestamp" in quick_form_data.columns else None
    _render_metrics_row([("Latest new form entry",nft.strftime("%Y-%m-%d %H:%M") if nft else "N/A"),("Latest legacy form",ft.strftime("%Y-%m-%d %H:%M") if ft else "N/A"),("Latest snapshot entry",st2.strftime("%Y-%m-%d %H:%M") if st2 else "N/A"),("Days (new form)",str(len(nf_model_data)) if not nf_model_data.empty else "0")])

def render_warnings_page(nf_model_summary,daily_model_summary,snapshot_model_summary,latest_nf_signals,latest_nf_findings,latest_form_signals,latest_form_findings,latest_snapshot_signals,latest_snapshot_findings,nf_model_findings,other_model_findings,alerts,today_summary):
    st.subheader("Warnings")
    render_two_column_flag_box("Today at a glance",[today_summary],tone="info")
    st.markdown("### Alert engine output")
    if alerts:
        for alert in alerts: render_alert_card(alert)
    else: st.info("No alerts currently being generated.")
    st.markdown("### Current State — New Form Model"); render_summary_cards(nf_model_summary,detailed=True)
    st.markdown("### Current State — Daily Model (legacy)"); render_summary_cards(daily_model_summary,detailed=True)
    st.markdown("### Current State — Snapshot Model (legacy)"); render_summary_cards(snapshot_model_summary,detailed=False)
    st.markdown("### Warning signals and concerning findings")
    c1,c2,c3=st.columns(3)
    with c1:
        render_two_column_flag_box("New form — warning signals",latest_nf_signals,tone="warning")
        render_two_column_flag_box("New form — concerning findings",latest_nf_findings+nf_model_findings,tone="error")
    with c2:
        render_two_column_flag_box("Daily questionnaire — signals",latest_form_signals,tone="warning")
        render_two_column_flag_box("Daily questionnaire — findings",latest_form_findings+other_model_findings,tone="error")
    with c3:
        render_two_column_flag_box("Snapshot — signals",latest_snapshot_signals,tone="warning")
        render_two_column_flag_box("Snapshot — findings",latest_snapshot_findings,tone="error")

def render_nf_model_page(nf_data):
    st.subheader("New Form Model")
    st.caption("All 1–5 scales: higher = worse → normalised to 0–100%.")
    with st.expander("New form model settings"): render_settings_form("nf_settings",NF_SETTINGS_UI,columns_per_row=3)
    nf_model_data,nf_model_summary=build_new_form_model(nf_data,st.session_state["nf_settings"])
    if nf_model_data.empty: st.info("No new form data available."); return
    render_summary_cards(nf_model_summary,detailed=True)
    render_chart_group(nf_model_data,"Date","DateLabel",NF_CHARTS)
    default_cols=[c for c in ["Date","Depression Score %","5-Day Average (Depression %)","Depression Baseline %","Depression Baseline Difference %","Depression Baseline Z","Mania Score %","5-Day Average (Mania %)","Mania Baseline %","Mania Baseline Difference %","Mania Baseline Z","Psychosis Score %","5-Day Average (Psychosis %)","Psychosis Baseline %","Psychosis Baseline Difference %","Psychosis Baseline Z","Mixed Score %","5-Day Average (Mixed %)","Mixed Baseline %","Mixed Baseline Difference %","Mixed Baseline Z","Concerning Situation Flags","Sleeping Pills Flag","Meta-Awareness Score","Depression Flags","Mania Flags","Psychosis Flags","Mixed Flags"] if c in nf_model_data.columns]
    render_dataframe_picker("New form model data",nf_model_data,default_cols,"nf_model_columns")

def render_nf_data_page(nf_data):
    st.subheader("New Form Data")
    st.caption("Raw data from the updated bipolar form tab.")
    default_cols=[c for c in ["Timestamp","Date",NF_LOW_MOOD,NF_SLOWED,NF_MOTIVATION,NF_ANHEDONIA,NF_WITHDRAWAL,NF_SELF_HARM,NF_ELEVATED_MOOD,NF_SPED_UP,NF_RACING,NF_GOAL_DRIVE,NF_IMPULSIVITY,NF_AGITATION,NF_IRRITABILITY,NF_CANT_SETTLE,NF_HEARD_SAW,NF_SUSPICIOUS,NF_TRUST_PERCEPT,NF_CONFIDENCE_REA,NF_DISTRESS,NF_UNLIKE_SELF,NF_SOMETHING_WRONG,NF_CONCERNED,NF_INTENSIFYING,NF_TOWARDS_EPISODE,NF_SLEEP_HOURS,NF_SLEEP_QUALITY,NF_FLAG_NOT_MYSELF,NF_FLAG_MOOD_SHIFT,NF_FLAG_MISSED_MEDS,NF_FLAG_SLEEP_MEDS] if c in nf_data.columns]
    render_dataframe_picker("New Form Data",nf_data,default_cols,"nf_data_columns")

def render_daily_model_page(form_data):
    st.subheader("Daily Model (legacy)")
    with st.expander("Daily model settings"): render_settings_form("daily_settings",DAILY_SETTINGS_UI,columns_per_row=3)
    daily_model_data,daily_model_summary=build_daily_model_from_form(form_data,st.session_state["daily_settings"])
    if daily_model_data.empty: st.info("No data available."); return
    render_summary_cards(daily_model_summary,detailed=True)
    render_chart_group(daily_model_data,"Date","DateLabel",DAILY_CHARTS)
    default_cols=[c for c in ["Date","Depression Score %","5-Day Average (Depression %)","Depression Baseline %","Depression Baseline Difference %","Depression Baseline Z","Mania Score %","5-Day Average (Mania %)","Mania Baseline %","Mania Baseline Difference %","Mania Baseline Z","Psychosis Score %","5-Day Average (Psychosis %)","Psychosis Baseline %","Psychosis Baseline Difference %","Psychosis Baseline Z","Mixed Score %","5-Day Average (Mixed %)","Mixed Baseline %","Mixed Baseline Difference %","Mixed Baseline Z","Concerning Situation Flags","Sleeping Pills Flag","Depression Flags","Mania Flags","Mixed Flags","Psychosis Flags"] if c in daily_model_data.columns]
    render_dataframe_picker("Daily model data",daily_model_data,default_cols,"daily_model_columns")

def render_snapshot_model_page(quick_form_data):
    st.subheader("Snapshot Model (legacy)")
    st.caption("No/Somewhat/Yes → 0/50/100%.")
    with st.expander("Snapshot model settings"): render_settings_form("snapshot_settings",SNAPSHOT_SETTINGS_UI,columns_per_row=3)
    snapshot_model_summary,snapshot_model_data=build_snapshot_model_from_quick_form(quick_form_data,st.session_state["snapshot_settings"])
    if snapshot_model_summary is None or snapshot_model_data.empty: st.info("No data available."); return
    render_summary_cards(snapshot_model_summary,detailed=False)
    render_chart_group(snapshot_model_data,"FilterDate","TimeLabel",SNAPSHOT_CHARTS)
    preview_cols=[c for c in ["Timestamp","Depression Score %","Depression Flags","Mania Score %","Psychosis Score %","Mixed Score %","10-Response Average (Depression %)","10-Response Average (Mania %)","10-Response Average (Psychosis %)","10-Response Average (Mixed %)","Deviation From 10-Response Average (Depression %)","Deviation From 10-Response Average (Mania %)","Deviation From 10-Response Average (Psychosis %)","Deviation From 10-Response Average (Mixed %)"] if c in snapshot_model_data.columns]
    render_dataframe_picker("Snapshot model data",snapshot_model_data,preview_cols,"snapshot_model_columns")

def render_form_data_page(form_data):
    st.subheader("Legacy Form Data")
    default_cols=[c for c in ["Timestamp","Date","Mood Score","Sleep (hours)","Sleep quality","Energy","Mental speed","Impulsivity","Motivation","Irritability","Agitation","Unusual perceptions","Suspiciousness","Certainty and belief in unusual ideas or things others don't believe","Took sleeping medication?"] if c in form_data.columns]
    render_dataframe_picker("Form Data",form_data,default_cols,"form_data_columns")

def render_snapshot_data_page(quick_form_data):
    st.subheader("Snapshot Data (legacy)")
    default_cols=[c for c in ["Timestamp","Symptoms: [Very low or depressed mood]","Symptoms: [Very low or depressed mood] Percent","Symptoms: [Somewhat low or depressed mood]","Symptoms: [Somewhat low or depressed mood] Percent","Symptoms: [Very high or elevated mood]","Symptoms: [Very high or elevated mood] Percent","Symptoms: [Paranoia or suspicion]","Symptoms: [Paranoia or suspicion] Percent","Depression Flags"] if c in quick_form_data.columns]
    render_dataframe_picker("Snapshot Data",quick_form_data,default_cols,"snapshot_data_columns")

# =========================================================
# APP ENTRY POINT
# =========================================================
st.title("Wellbeing Dashboard")

try:
    get_workbook()
    st.success("Google Sheets connected successfully.")
except Exception as e:
    st.error("Google Sheets connection failed.")
    st.exception(e)
    st.stop()

form_df         = load_sheet(FORM_TAB)
quick_form_df   = load_sheet(QUICK_FORM_TAB)
nf_df           = load_sheet(NEW_FORM_TAB)

form_data       = prepare_form_raw(form_df)
quick_form_data = prepare_quick_form_raw(quick_form_df)
nf_data         = prepare_new_form_raw(nf_df)

daily_model_data, daily_model_summary = build_daily_model_from_form(
    form_data, st.session_state["daily_settings"])
snapshot_model_summary, snapshot_model_data = build_snapshot_model_from_quick_form(
    quick_form_data, st.session_state["snapshot_settings"])
nf_model_data, nf_model_summary = build_new_form_model(
    nf_data, st.session_state["nf_settings"])

latest_nf_signals,       latest_nf_findings       = get_latest_nf_warning_items(nf_data)
latest_form_signals,     latest_form_findings     = get_latest_form_warning_items(form_data)
latest_snapshot_signals, latest_snapshot_findings = get_latest_quick_form_warning_items(quick_form_data)

nf_model_findings, other_model_findings = get_model_concerning_findings(
    nf_model_summary, daily_model_summary, snapshot_model_summary,
    nf_model_data, daily_model_data, snapshot_model_data)

d_dep_flag = not daily_model_data.empty and to_int(daily_model_data.iloc[-1].get("Depression Flags",0))>0
s_dep_flag = not snapshot_model_data.empty and to_int(snapshot_model_data.iloc[-1].get("Depression Flags",0))>0

alerts = build_alerts(
    primary_data    = nf_model_data,
    primary_summary = nf_model_summary,
    settings        = st.session_state["nf_settings"],
    cross_summaries = [("Daily", daily_model_summary), ("Snapshot", snapshot_model_summary)],
    cross_dep_flags = [d_dep_flag, s_dep_flag],
)
today_summary = build_today_summary(nf_model_summary, alerts, nf_model_data)

tabs = st.tabs([
    "Dashboard", "Warnings",
    "New Form Model", "New Form Data",
    "Daily Model", "Snapshot Model",
    "Legacy Form Data", "Snapshot Data",
])

with tabs[0]:
    render_dashboard_page(
        form_data, quick_form_data,
        nf_model_data, nf_model_summary,
        daily_model_data, daily_model_summary,
        snapshot_model_summary,
        latest_nf_signals, latest_nf_findings,
        latest_form_signals, latest_form_findings,
        latest_snapshot_signals, latest_snapshot_findings,
        nf_model_findings, other_model_findings,
        alerts, today_summary,
    )
with tabs[1]:
    render_warnings_page(
        nf_model_summary, daily_model_summary, snapshot_model_summary,
        latest_nf_signals, latest_nf_findings,
        latest_form_signals, latest_form_findings,
        latest_snapshot_signals, latest_snapshot_findings,
        nf_model_findings, other_model_findings,
        alerts, today_summary,
    )
with tabs[2]:
    render_nf_model_page(nf_data)
with tabs[3]:
    render_nf_data_page(nf_data)
with tabs[4]:
    render_daily_model_page(form_data)
with tabs[5]:
    render_snapshot_model_page(quick_form_data)
with tabs[6]:
    render_form_data_page(form_data)
with tabs[7]:
    render_snapshot_data_page(quick_form_data)
