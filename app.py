import streamlit as st
import pandas as pd
import gspread

st.set_page_config(page_title="Wellbeing Dashboard", layout="wide")
st.title("Wellbeing Dashboard")
st.caption("Minimal starter app for rebuilding the dashboard from scratch.")


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Google Sheets connection
# ---------------------------------------------------------
SHEET_NAME = "Bipolar Dashboard"


@st.cache_resource
def get_gspread_client() -> gspread.Client:
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))


@st.cache_resource
def get_workbook() -> gspread.Spreadsheet:
    return get_gspread_client().open(SHEET_NAME)


@st.cache_data(ttl=60)
def list_worksheet_names() -> list[str]:
    workbook = get_workbook()
    return [worksheet.title for worksheet in workbook.worksheets()]


@st.cache_data(ttl=60)
def load_sheet(tab_name: str) -> pd.DataFrame:
    values = get_workbook().worksheet(tab_name).get_all_values()
    if not values:
        return pd.DataFrame()

    headers = [str(h).strip() if h else f"Unnamed_{i + 1}" for i, h in enumerate(values[0])]
    return pd.DataFrame(values[1:], columns=headers)


# ---------------------------------------------------------
# App
# ---------------------------------------------------------
try:
    workbook = get_workbook()
    sheet_names = list_worksheet_names()
    st.success(f"Connected to Google Sheets: {workbook.title}")
except Exception as exc:
    st.error("Google Sheets connection failed.")
    st.exception(exc)
    st.stop()

st.subheader("Starter workspace")
st.write("This has been stripped back to a single page so you can rebuild from the data layer upward.")

selected_sheet = st.selectbox("Choose a worksheet", sheet_names)
df = load_sheet(selected_sheet)

col1, col2, col3 = st.columns(3)
col1.metric("Rows", len(df))
col2.metric("Columns", len(df.columns))
col3.metric("Worksheet", selected_sheet)

st.markdown("### Preview")
st.dataframe(df, use_container_width=True)

st.markdown("### Columns")
st.write(list(df.columns))
