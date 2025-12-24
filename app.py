import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import streamlit as st


# -----------------------------
# Config
# -----------------------------
APP_TITLE = "Tourism Digital Twin of Goa – Water Stress & Carrying Capacity Survey"
DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "survey.db")

ADMIN_USERNAME = "givegoagroup9"
ADMIN_PASSWORD = "987654321"


# -----------------------------
# Data / DB helpers
# -----------------------------
ALL_COLUMNS = [
    "timestamp",
    "respondent_type",
    "zone",
    "zone_other_text",
    "time_in_area",
    "age_group",
    # Tourist
    "length_of_stay",
    "places_visited",
    "aware_water_stress",
    "showers_per_day",
    "drinking_water",
    "tourism_increases_water_demand",
    "perceived_crowding",
    "crowding_reduces_enjoyment",
    "beach_cleanliness",
    # Local resident
    "tourism_affects_water_availability",
    "peak_season_shortages_local",
    "tanker_dependency",
    "water_trend_years",
    "benefits_shared_fairly",
    # Hotel/Shack/Restaurant staff
    "peak_season_shortages_staff",
    "main_water_source",
    "water_saving_measures",
    "tourism_growth_increases_pressure",
    # Transport/Beach worker
    "peak_season_pressure",
    "facilities_stressed",
    "infra_handles_future_growth",
    # Common sustainability
    "biggest_issue",
    "should_define_limits",
    "support_stricter_water_rules",
    "priority_suggestion",
]

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS responses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  {", ".join([f"{c} TEXT" for c in ALL_COLUMNS])}
);
"""


def ensure_db():
    os.makedirs(DB_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()


def insert_response(row: dict):
    # Ensure all columns exist in dict
    data = {c: ("" if row.get(c) is None else str(row.get(c))) for c in ALL_COLUMNS}
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    values = list(data.values())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(f"INSERT INTO responses ({cols}) VALUES ({placeholders})", values)
        conn.commit()


def fetch_all_responses() -> pd.DataFrame:
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM responses ORDER BY id DESC", conn)
    return df


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# -----------------------------
# UI helpers
# -----------------------------
def init_state():
    if "page" not in st.session_state:
        st.session_state.page = "landing"  # landing | survey | admin
    if "step" not in st.session_state:
        st.session_state.step = 0  # 0..3
    if "form" not in st.session_state:
        st.session_state.form = {c: "" for c in ALL_COLUMNS}
    if "errors" not in st.session_state:
        st.session_state.errors = []


def reset_survey():
    st.session_state.step = 0
    st.session_state.form = {c: "" for c in ALL_COLUMNS}
    st.session_state.errors = []


def set_error(msg: str):
    st.session_state.errors.append(msg)


def show_errors():
    if st.session_state.errors:
        st.error("Please fix the following before continuing:")
        for e in st.session_state.errors:
            st.write(f"- {e}")


def progress_label(step: int) -> str:
    # 4 steps total: 1) respondent type, 2) context, 3) role questions, 4) sustainability
    return f"Step {step + 1} of 4"


def zone_selector():
    zone = st.selectbox(
        "zone (select):",
        ["Baga", "Calangute", "Anjuna", "Candolim", "Vagator", "Other"],
        index=0,
    )
    zone_other = ""
    if zone == "Other":
        zone_other = st.text_input("Other (text):")
    return zone, zone_other


def multiselect_to_text(values):
    return ", ".join(values) if values else ""


# -----------------------------
# Survey steps
# -----------------------------
RESPONDENT_TYPES = [
    "Tourist",
    "Local Resident",
    "Hotel / Homestay / Resort Staff",
    "Shack / Restaurant Worker",
    "Taxi / Transport Worker",
    "Beach Worker / Lifeguard",
]


def render_landing():
    st.title(APP_TITLE)
    st.caption("Field survey for sustainable tourism planning (water stress, carrying capacity, infrastructure pressure).")

    st.subheader("Consent")
    st.write(
        "- Participation is voluntary.\n"
        "- Your responses are collected for academic planning analysis.\n"
        "- No real-time tracking, surveillance, or external APIs are used.\n"
        "- Responses are stored locally on the device running this app."
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Start Survey", use_container_width=True):
            reset_survey()
            st.session_state.page = "survey"
    with col2:
        if st.button("Admin View", use_container_width=True):
            st.session_state.page = "admin"


def render_step_1():
    st.subheader(progress_label(0))
    st.write("### Step 1: Respondent Type (required)")

    rt = st.selectbox("Respondent type:", RESPONDENT_TYPES, index=0)
    st.session_state.form["respondent_type"] = rt


def render_step_2():
    st.subheader(progress_label(1))
    st.write("### Step 2: Basic Context (all respondents)")

    zone, zone_other = zone_selector()
    st.session_state.form["zone"] = zone
    st.session_state.form["zone_other_text"] = zone_other

    tia = st.selectbox(
        "time_in_area (select):",
        ["<1 week", "1–4 weeks", "several months", "many years"],
        index=0,
    )
    st.session_state.form["time_in_area"] = tia

    ag = st.selectbox(
        "age_group (optional):",
        ["", "<18", "18–25", "26–35", "36–50", "50+"],
        index=0,
        help="Optional",
    )
    st.session_state.form["age_group"] = ag


def render_step_3():
    st.subheader(progress_label(2))
    rt = st.session_state.form.get("respondent_type", "")
    st.write("### Step 3: Role-specific Questions")

    # Clear all role-specific fields first (keeps data consistent if user switches role)
    for key in [
        "length_of_stay", "places_visited", "aware_water_stress", "showers_per_day", "drinking_water",
        "tourism_increases_water_demand", "perceived_crowding", "crowding_reduces_enjoyment", "beach_cleanliness",
        "tourism_affects_water_availability", "peak_season_shortages_local", "tanker_dependency", "water_trend_years", "benefits_shared_fairly",
        "peak_season_shortages_staff", "main_water_source", "water_saving_measures", "tourism_growth_increases_pressure",
        "peak_season_pressure", "facilities_stressed", "infra_handles_future_growth",
    ]:
        # only blank if not already set? safer: keep user input; but switching roles should blank irrelevant fields
        pass

    if rt == "Tourist":
        st.write("#### Tourist Questions")

        st.session_state.form["length_of_stay"] = st.selectbox(
            "length_of_stay:", ["1–3 days", "4–7 days", ">7 days"], index=0
        )

        pv = st.multiselect(
            "places_visited (multi-select):",
            ["beaches", "markets", "nightlife", "heritage/culture"],
        )
        st.session_state.form["places_visited"] = multiselect_to_text(pv)

        st.session_state.form["aware_water_stress"] = st.radio(
            "aware_water_stress (yes/no):", ["yes", "no"], horizontal=True
        )

        st.session_state.form["showers_per_day"] = st.selectbox(
            "showers_per_day:", ["1", "2", ">2"], index=0
        )

        st.session_state.form["drinking_water"] = st.selectbox(
            "drinking_water:", ["bottled", "filtered", "both"], index=0
        )

        st.session_state.form["tourism_increases_water_demand"] = st.selectbox(
            "tourism_increases_water_demand (Likert):",
            ["strongly agree", "agree", "neutral", "disagree"],
            index=0,
        )

        st.session_state.form["perceived_crowding"] = st.selectbox(
            "perceived_crowding:", ["low", "moderate", "high", "very high"], index=0
        )

        st.session_state.form["crowding_reduces_enjoyment"] = st.selectbox(
            "crowding_reduces_enjoyment:",
            ["not at all", "slightly", "moderately", "significantly"],
            index=0,
        )

        st.session_state.form["beach_cleanliness"] = st.selectbox(
            "beach_cleanliness:", ["very clean", "clean", "average", "poor"], index=0
        )

        # Blank non-applicable sections
        for k in [
            "tourism_affects_water_availability", "peak_season_shortages_local", "tanker_dependency", "water_trend_years", "benefits_shared_fairly",
            "peak_season_shortages_staff", "main_water_source", "water_saving_measures", "tourism_growth_increases_pressure",
            "peak_season_pressure", "facilities_stressed", "infra_handles_future_growth",
        ]:
            st.session_state.form[k] = ""

    elif rt == "Local Resident":
        st.write("#### Local Resident Questions")

        st.session_state.form["tourism_affects_water_availability"] = st.selectbox(
            "tourism_affects_water_availability:",
            ["yes significantly", "yes slightly", "no"],
            index=0,
        )

        st.session_state.form["peak_season_shortages_local"] = st.selectbox(
            "peak_season_shortages:", ["frequently", "sometimes", "rarely", "never"], index=0
        )

        st.session_state.form["tanker_dependency"] = st.radio(
            "tanker_dependency (yes/no):", ["yes", "no"], horizontal=True
        )

        st.session_state.form["water_trend_years"] = st.selectbox(
            "water_trend_years:", ["improved", "no change", "worsened"], index=0
        )

        st.session_state.form["benefits_shared_fairly"] = st.selectbox(
            "benefits_shared_fairly:", ["yes", "no", "partially"], index=0
        )

        # Blank non-applicable
        for k in [
            "length_of_stay", "places_visited", "aware_water_stress", "showers_per_day", "drinking_water",
            "tourism_increases_water_demand", "perceived_crowding", "crowding_reduces_enjoyment", "beach_cleanliness",
            "peak_season_shortages_staff", "main_water_source", "water_saving_measures", "tourism_growth_increases_pressure",
            "peak_season_pressure", "facilities_stressed", "infra_handles_future_growth",
        ]:
            st.session_state.form[k] = ""

    elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
        st.write("#### Hotel / Shack / Restaurant Staff Questions")

        st.session_state.form["peak_season_shortages_staff"] = st.selectbox(
            "peak_season_shortages:", ["yes", "no", "sometimes"], index=0
        )

        st.session_state.form["main_water_source"] = st.selectbox(
            "main_water_source:",
            ["municipal", "borewell/groundwater", "tankers", "combination"],
            index=0,
        )

        wsm = st.multiselect(
            "water_saving_measures (multi-select):",
            ["towel reuse", "low-flow fixtures", "signage", "none"],
        )
        st.session_state.form["water_saving_measures"] = multiselect_to_text(wsm)

        st.session_state.form["tourism_growth_increases_pressure"] = st.selectbox(
            "tourism_growth_increases_pressure:", ["yes", "no", "unsure"], index=0
        )

        # Blank non-applicable
        for k in [
            "length_of_stay", "places_visited", "aware_water_stress", "showers_per_day", "drinking_water",
            "tourism_increases_water_demand", "perceived_crowding", "crowding_reduces_enjoyment", "beach_cleanliness",
            "tourism_affects_water_availability", "peak_season_shortages_local", "tanker_dependency", "water_trend_years", "benefits_shared_fairly",
            "peak_season_pressure", "facilities_stressed", "infra_handles_future_growth",
        ]:
            st.session_state.form[k] = ""

    elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
        st.write("#### Transport / Beach Worker Questions")

        st.session_state.form["peak_season_pressure"] = st.selectbox(
            "peak_season_pressure:", ["low", "moderate", "high", "extreme"], index=0
        )

        st.session_state.form["facilities_stressed"] = st.radio(
            "facilities_stressed (yes/no):", ["yes", "no"], horizontal=True
        )

        st.session_state.form["infra_handles_future_growth"] = st.selectbox(
            "infra_handles_future_growth:", ["yes", "no", "not sure"], index=0
        )

        # Blank non-applicable
        for k in [
            "length_of_stay", "places_visited", "aware_water_stress", "showers_per_day", "drinking_water",
            "tourism_increases_water_demand", "perceived_crowding", "crowding_reduces_enjoyment", "beach_cleanliness",
            "tourism_affects_water_availability", "peak_season_shortages_local", "tanker_dependency", "water_trend_years", "benefits_shared_fairly",
            "peak_season_shortages_staff", "main_water_source", "water_saving_measures", "tourism_growth_increases_pressure",
        ]:
            st.session_state.form[k] = ""

    else:
        st.info("Select a respondent type in Step 1.")


def render_step_4():
    st.subheader(progress_label(3))
    st.write("### Step 4: Sustainability & Planning (all respondents)")

    st.session_state.form["biggest_issue"] = st.selectbox(
        "biggest_issue:",
        ["water shortage", "overcrowding", "waste & pollution", "traffic", "loss of natural beauty"],
        index=0,
    )

    st.session_state.form["should_define_limits"] = st.selectbox(
        "should_define_limits (Likert):",
        ["strongly agree", "agree", "neutral", "disagree"],
        index=0,
    )

    st.session_state.form["support_stricter_water_rules"] = st.selectbox(
        "support_stricter_water_rules:", ["yes", "no", "depends"], index=0
    )

    st.session_state.form["priority_suggestion"] = st.text_area(
        "priority_suggestion (open text):",
        placeholder="Write your suggestion...",
        height=120,
    )


def validate_current_step(step: int) -> bool:
    st.session_state.errors = []
    f = st.session_state.form

    # Step 1
    if step == 0:
        if not f.get("respondent_type"):
            set_error("Respondent type is required.")

    # Step 2
    if step == 1:
        if not f.get("zone"):
            set_error("zone is required.")
        if f.get("zone") == "Other" and not f.get("zone_other_text", "").strip():
            set_error("Please specify zone_other_text because zone = Other.")
        if not f.get("time_in_area"):
            set_error("time_in_area is required.")

    # Step 3: role-specific required fields
    if step == 2:
        rt = f.get("respondent_type", "")
        if rt == "Tourist":
            required = [
                "length_of_stay", "places_visited", "aware_water_stress", "showers_per_day",
                "drinking_water", "tourism_increases_water_demand", "perceived_crowding",
                "crowding_reduces_enjoyment", "beach_cleanliness"
            ]
            for k in required:
                if not str(f.get(k, "")).strip():
                    set_error(f"{k} is required for Tourist.")

        elif rt == "Local Resident":
            required = [
                "tourism_affects_water_availability", "peak_season_shortages_local",
                "tanker_dependency", "water_trend_years", "benefits_shared_fairly"
            ]
            for k in required:
                if not str(f.get(k, "")).strip():
                    set_error(f"{k} is required for Local Resident.")

        elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
            required = [
                "peak_season_shortages_staff", "main_water_source",
                "water_saving_measures", "tourism_growth_increases_pressure"
            ]
            for k in required:
                if not str(f.get(k, "")).strip():
                    set_error(f"{k} is required for Hotel/Shack/Restaurant Staff.")

        elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
            required = ["peak_season_pressure", "facilities_stressed", "infra_handles_future_growth"]
            for k in required:
                if not str(f.get(k, "")).strip():
                    set_error(f"{k} is required for Transport/Beach Worker.")

        else:
            set_error("Respondent type is missing (go back to Step 1).")

    # Step 4
    if step == 3:
        required = ["biggest_issue", "should_define_limits", "support_stricter_water_rules"]
        for k in required:
            if not str(f.get(k, "")).strip():
                set_error(f"{k} is required.")
        # priority_suggestion is open text (not marked required in your spec)

    return len(st.session_state.errors) == 0


def render_survey():
    st.title(APP_TITLE)
    st.caption("Multi-step academic survey (local storage).")

    step = st.session_state.step
    st.progress((step + 1) / 4)

    if step == 0:
        render_step_1()
    elif step == 1:
        render_step_2()
    elif step == 2:
        render_step_3()
    elif step == 3:
        render_step_4()

    show_errors()

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("Back", use_container_width=True, disabled=(step == 0)):
            st.session_state.errors = []
            st.session_state.step = max(0, step - 1)

    with col2:
        if step < 3:
            if st.button("Next", use_container_width=True):
                if validate_current_step(step):
                    st.session_state.step = step + 1
        else:
            if st.button("Submit", use_container_width=True):
                if validate_current_step(step):
                    ensure_db()
                    # Timestamp in ISO
                    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
                    st.session_state.form["timestamp"] = ts

                    # Ensure zone_other_text empty unless zone=Other
                    if st.session_state.form.get("zone") != "Other":
                        st.session_state.form["zone_other_text"] = ""

                    insert_response(st.session_state.form)

                    st.success("Submitted successfully. Thank you!")
                    st.balloons()
                    # Reset for next respondent
                    reset_survey()
                    st.session_state.page = "landing"

    with col3:
        if st.button("Cancel", use_container_width=True):
            reset_survey()
            st.session_state.page = "landing"


# -----------------------------
# Admin view
# -----------------------------
def render_admin():
    st.title("Admin View")
    st.caption("View responses stored locally and export CSV.")

    # Simple protection if ADMIN_PASSWORD is set
    st.subheader("Admin Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        st.warning("Invalid username or password.")
        if st.button("Back to Landing"):
            st.session_state.page = "landing"
        return

    

    df = fetch_all_responses()

    st.write(f"Total responses: **{len(df)}**")

    if len(df) == 0:
        st.info("No responses yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv_bytes = df_to_csv_bytes(df)
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name="goa_survey_responses.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.subheader("Quick summaries (optional)")
        # Charts: respondent types + zones + biggest issue
        try:
            c1, c2 = st.columns(2)
            with c1:
                st.write("Respondent type distribution")
                counts = df["respondent_type"].value_counts()
                st.bar_chart(counts)

            with c2:
                st.write("Zone distribution")
                # If zone=Other, show "Other:<text>" in a derived series
                zone_series = df["zone"].fillna("")
                other_text = df["zone_other_text"].fillna("")
                zone_display = zone_series.where(zone_series != "Other", "Other: " + other_text)
                st.bar_chart(zone_display.value_counts())

            st.write("Biggest issue distribution")
            st.bar_chart(df["biggest_issue"].value_counts())
        except Exception:
            st.info("Charts are unavailable due to missing/empty fields in current data.")

    if st.button("Back to Landing", use_container_width=True):
        st.session_state.page = "landing"


# -----------------------------
# Main
# -----------------------------
def main():
    st.set_page_config(page_title="Goa Survey", layout="centered")
    init_state()
    ensure_db()

    # Simple top nav
    with st.sidebar:
        st.markdown("### Navigation")
        if st.button("Landing"):
            st.session_state.page = "landing"
        if st.button("Survey"):
            st.session_state.page = "survey"
        if st.button("Admin"):
            st.session_state.page = "admin"
        st.markdown("---")
        st.markdown("**Local storage:** SQLite (`data/survey.db`)")
        st.markdown("**Export:** Admin → Download CSV")

    if st.session_state.page == "landing":
        render_landing()
    elif st.session_state.page == "survey":
        render_survey()
    elif st.session_state.page == "admin":
        render_admin()
    else:
        st.session_state.page = "landing"
        render_landing()


if __name__ == "__main__":
    main()
