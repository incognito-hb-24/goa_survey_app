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

# Fixed admin credentials (as requested)
ADMIN_USERNAME = "givegoagroup9"
ADMIN_PASSWORD = "987654321"


# -----------------------------
# Storage schema
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


# -----------------------------
# DB helpers
# -----------------------------
def ensure_db():
    os.makedirs(DB_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()


def insert_response(row: dict):
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
# App state
# -----------------------------
RESPONDENT_TYPES = [
    "Tourist",
    "Local Resident",
    "Hotel / Homestay / Resort Staff",
    "Shack / Restaurant Worker",
    "Taxi / Transport Worker",
    "Beach Worker / Lifeguard",
]


def init_state():
    if "page" not in st.session_state:
        st.session_state.page = "landing"  # landing | survey | admin
    if "step" not in st.session_state:
        st.session_state.step = 0  # 0..3
    if "form" not in st.session_state:
        st.session_state.form = {c: "" for c in ALL_COLUMNS}
    if "errors" not in st.session_state:
        st.session_state.errors = []
    if "last_respondent_type" not in st.session_state:
        st.session_state.last_respondent_type = None
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False


def reset_survey():
    st.session_state.step = 0
    st.session_state.form = {c: "" for c in ALL_COLUMNS}
    st.session_state.errors = []
    st.session_state.last_respondent_type = None


def set_error(msg: str):
    st.session_state.errors.append(msg)


def show_errors():
    if st.session_state.errors:
        st.error("Please fix the following before continuing:")
        for e in st.session_state.errors:
            st.write(f"- {e}")


def progress_label(step: int) -> str:
    return f"Step {step + 1} of 4"


def multiselect_to_text(values):
    return ", ".join(values) if values else ""


# -----------------------------
# Validation
# -----------------------------
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

    # Step 3 (role-specific)
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

    # Step 4 (sustainability)
    if step == 3:
        required = ["biggest_issue", "should_define_limits", "support_stricter_water_rules"]
        for k in required:
            if not str(f.get(k, "")).strip():
                set_error(f"{k} is required.")

    return len(st.session_state.errors) == 0


# -----------------------------
# Pages
# -----------------------------
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

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Start Survey", use_container_width=True):
            reset_survey()
            st.session_state.page = "survey"
            st.rerun()

    with c2:
        if st.button("Admin View", use_container_width=True):
            st.session_state.page = "admin"
            st.rerun()


def render_step_1():
    st.subheader(progress_label(0))
    st.write("### Step 1: Respondent Type (required)")

    default_rt = st.session_state.form.get("respondent_type") or RESPONDENT_TYPES[0]
    default_idx = RESPONDENT_TYPES.index(default_rt) if default_rt in RESPONDENT_TYPES else 0

    with st.form("step1_form", clear_on_submit=False):
        rt = st.selectbox("Respondent type:", RESPONDENT_TYPES, index=default_idx, key="rt_widget")
        go_next = st.form_submit_button("Next")

    if go_next:
        st.session_state.form["respondent_type"] = rt

        # Clear role-specific fields ONLY when respondent type changes
        if st.session_state.last_respondent_type != rt:
            for k in [
                "length_of_stay","places_visited","aware_water_stress","showers_per_day","drinking_water",
                "tourism_increases_water_demand","perceived_crowding","crowding_reduces_enjoyment","beach_cleanliness",
                "tourism_affects_water_availability","peak_season_shortages_local","tanker_dependency","water_trend_years","benefits_shared_fairly",
                "peak_season_shortages_staff","main_water_source","water_saving_measures","tourism_growth_increases_pressure",
                "peak_season_pressure","facilities_stressed","infra_handles_future_growth",
            ]:
                st.session_state.form[k] = ""
            st.session_state.last_respondent_type = rt

        if validate_current_step(0):
            st.session_state.step = 1
            st.rerun()


def render_step_2():
    st.subheader(progress_label(1))
    st.write("### Step 2: Basic Context (all respondents)")

    f = st.session_state.form

    zone_default = f.get("zone") if f.get("zone") else "Baga"
    zone_options = ["Baga", "Calangute", "Anjuna", "Candolim", "Vagator", "Other"]
    zone_idx = zone_options.index(zone_default) if zone_default in zone_options else 0

    time_options = ["<1 week", "1–4 weeks", "several months", "many years"]
    time_default = f.get("time_in_area") if f.get("time_in_area") else "<1 week"
    time_idx = time_options.index(time_default) if time_default in time_options else 0

    age_options = ["", "<18", "18–25", "26–35", "36–50", "50+"]
    age_default = f.get("age_group") if f.get("age_group") in age_options else ""
    age_idx = age_options.index(age_default)

    with st.form("step2_form", clear_on_submit=False):
        zone = st.selectbox("zone (select):", zone_options, index=zone_idx, key="zone_widget")
        zone_other = ""
        if zone == "Other":
            zone_other = st.text_input("Other (text):", value=f.get("zone_other_text", ""), key="zone_other_widget")

        time_in_area = st.selectbox("time_in_area (select):", time_options, index=time_idx, key="time_widget")
        age_group = st.selectbox("age_group (optional):", age_options, index=age_idx, key="age_widget")

        go_next = st.form_submit_button("Next")

    if go_next:
        f["zone"] = zone
        f["zone_other_text"] = zone_other if zone == "Other" else ""
        f["time_in_area"] = time_in_area
        f["age_group"] = age_group

        if validate_current_step(1):
            st.session_state.step = 2
            st.rerun()


def render_step_3():
    st.subheader(progress_label(2))
    st.write("### Step 3: Role-specific Questions")

    f = st.session_state.form
    rt = f.get("respondent_type", "")

    with st.form("step3_form", clear_on_submit=False):
        if rt == "Tourist":
            st.write("#### Tourist Questions")

            length_of_stay = st.selectbox(
                "length_of_stay:",
                ["1–3 days", "4–7 days", ">7 days"],
                index=0,
                key="tourist_len",
            )

            places = st.multiselect(
                "places_visited (multi-select):",
                ["beaches", "markets", "nightlife", "heritage/culture"],
                default=(f.get("places_visited", "").split(", ") if f.get("places_visited") else []),
                key="tourist_places",
            )

            aware = st.radio("aware_water_stress (yes/no):", ["yes", "no"], horizontal=True, key="tourist_aware")
            showers = st.selectbox("showers_per_day:", ["1", "2", ">2"], index=0, key="tourist_showers")
            drinking = st.selectbox("drinking_water:", ["bottled", "filtered", "both"], index=0, key="tourist_drinking")
            demand = st.selectbox(
                "tourism_increases_water_demand (Likert):",
                ["strongly agree", "agree", "neutral", "disagree"],
                index=0,
                key="tourist_demand",
            )
            crowding = st.selectbox("perceived_crowding:", ["low", "moderate", "high", "very high"], index=0, key="tourist_crowding")
            reduce = st.selectbox(
                "crowding_reduces_enjoyment:",
                ["not at all", "slightly", "moderately", "significantly"],
                index=0,
                key="tourist_reduce",
            )
            clean = st.selectbox("beach_cleanliness:", ["very clean", "clean", "average", "poor"], index=0, key="tourist_clean")

        elif rt == "Local Resident":
            st.write("#### Local Resident Questions")

            affects = st.selectbox(
                "tourism_affects_water_availability:",
                ["yes significantly", "yes slightly", "no"],
                index=0,
                key="local_affects",
            )
            shortages = st.selectbox(
                "peak_season_shortages:",
                ["frequently", "sometimes", "rarely", "never"],
                index=0,
                key="local_shortages",
            )
            tanker = st.radio("tanker_dependency (yes/no):", ["yes", "no"], horizontal=True, key="local_tanker")
            trend = st.selectbox("water_trend_years:", ["improved", "no change", "worsened"], index=0, key="local_trend")
            benefits = st.selectbox("benefits_shared_fairly:", ["yes", "no", "partially"], index=0, key="local_benefits")

        elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
            st.write("#### Hotel / Shack / Restaurant Staff Questions")

            shortages_staff = st.selectbox("peak_season_shortages:", ["yes", "no", "sometimes"], index=0, key="staff_shortages")
            source = st.selectbox(
                "main_water_source:",
                ["municipal", "borewell/groundwater", "tankers", "combination"],
                index=0,
                key="staff_source",
            )
            wsm = st.multiselect(
                "water_saving_measures (multi-select):",
                ["towel reuse", "low-flow fixtures", "signage", "none"],
                default=(f.get("water_saving_measures", "").split(", ") if f.get("water_saving_measures") else []),
                key="staff_wsm",
            )
            pressure = st.selectbox("tourism_growth_increases_pressure:", ["yes", "no", "unsure"], index=0, key="staff_pressure")

        elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
            st.write("#### Transport / Beach Worker Questions")

            pressure_level = st.selectbox("peak_season_pressure:", ["low", "moderate", "high", "extreme"], index=0, key="work_pressure")
            stressed = st.radio("facilities_stressed (yes/no):", ["yes", "no"], horizontal=True, key="work_stressed")
            infra = st.selectbox("infra_handles_future_growth:", ["yes", "no", "not sure"], index=0, key="work_infra")

        else:
            st.warning("Respondent type is missing. Go back to Step 1.")
            st.form_submit_button("Next", disabled=True)

        go_next = st.form_submit_button("Next")

    if go_next:
        # Save role-specific fields
        if rt == "Tourist":
            f["length_of_stay"] = st.session_state.get("tourist_len", "")
            f["places_visited"] = multiselect_to_text(st.session_state.get("tourist_places", []))
            f["aware_water_stress"] = st.session_state.get("tourist_aware", "")
            f["showers_per_day"] = st.session_state.get("tourist_showers", "")
            f["drinking_water"] = st.session_state.get("tourist_drinking", "")
            f["tourism_increases_water_demand"] = st.session_state.get("tourist_demand", "")
            f["perceived_crowding"] = st.session_state.get("tourist_crowding", "")
            f["crowding_reduces_enjoyment"] = st.session_state.get("tourist_reduce", "")
            f["beach_cleanliness"] = st.session_state.get("tourist_clean", "")

        elif rt == "Local Resident":
            f["tourism_affects_water_availability"] = st.session_state.get("local_affects", "")
            f["peak_season_shortages_local"] = st.session_state.get("local_shortages", "")
            f["tanker_dependency"] = st.session_state.get("local_tanker", "")
            f["water_trend_years"] = st.session_state.get("local_trend", "")
            f["benefits_shared_fairly"] = st.session_state.get("local_benefits", "")

        elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
            f["peak_season_shortages_staff"] = st.session_state.get("staff_shortages", "")
            f["main_water_source"] = st.session_state.get("staff_source", "")
            f["water_saving_measures"] = multiselect_to_text(st.session_state.get("staff_wsm", []))
            f["tourism_growth_increases_pressure"] = st.session_state.get("staff_pressure", "")

        elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
            f["peak_season_pressure"] = st.session_state.get("work_pressure", "")
            f["facilities_stressed"] = st.session_state.get("work_stressed", "")
            f["infra_handles_future_growth"] = st.session_state.get("work_infra", "")

        if validate_current_step(2):
            st.session_state.step = 3
            st.rerun()


def render_step_4():
    st.subheader(progress_label(3))
    st.write("### Step 4: Sustainability & Planning (all respondents)")

    f = st.session_state.form

    with st.form("step4_form", clear_on_submit=False):
        biggest_issue = st.selectbox(
            "biggest_issue:",
            ["water shortage", "overcrowding", "waste & pollution", "traffic", "loss of natural beauty"],
            index=0,
            key="sus_issue",
        )
        limits = st.selectbox(
            "should_define_limits (Likert):",
            ["strongly agree", "agree", "neutral", "disagree"],
            index=0,
            key="sus_limits",
        )
        stricter = st.selectbox(
            "support_stricter_water_rules:",
            ["yes", "no", "depends"],
            index=0,
            key="sus_rules",
        )
        suggestion = st.text_area(
            "priority_suggestion (open text):",
            value=f.get("priority_suggestion", ""),
            placeholder="Write your suggestion...",
            height=120,
            key="sus_suggestion",
        )

        submit = st.form_submit_button("Submit")

    if submit:
        f["biggest_issue"] = biggest_issue
        f["should_define_limits"] = limits
        f["support_stricter_water_rules"] = stricter
        f["priority_suggestion"] = suggestion

        if validate_current_step(3):
            ensure_db()
            ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            f["timestamp"] = ts

            # Ensure zone_other_text empty unless zone=Other
            if f.get("zone") != "Other":
                f["zone_other_text"] = ""

            insert_response(f)

            st.success("Submitted successfully. Thank you!")
            reset_survey()
            st.session_state.page = "landing"
            st.rerun()


def render_survey():
    st.title(APP_TITLE)
    st.caption("Multi-step academic survey (stable + mobile-friendly).")

    step = st.session_state.step
    st.progress((step + 1) / 4)

    # Render current step
    if step == 0:
        render_step_1()
    elif step == 1:
        render_step_2()
    elif step == 2:
        render_step_3()
    elif step == 3:
        render_step_4()

    show_errors()

    # Navigation (Back + Cancel) outside forms -> no accidental submits
    c1, c2 = st.columns(2)

    with c1:
        if st.button("Back", use_container_width=True, disabled=(step == 0)):
            st.session_state.errors = []
            st.session_state.step = max(0, step - 1)
            st.rerun()

    with c2:
        if st.button("Cancel", use_container_width=True):
            reset_survey()
            st.session_state.page = "landing"
            st.rerun()


def render_admin():
    st.title("Admin View")
    st.caption("View responses stored locally and export CSV.")

    # Login flow (Enter button)
    if not st.session_state.admin_logged_in:
        st.subheader("Admin Login")

        with st.form("admin_login_form", clear_on_submit=False):
            username = st.text_input("Username", key="admin_user")
            password = st.text_input("Password", type="password", key="admin_pass")
            login = st.form_submit_button("Enter")  # press Enter to submit

        if not login:
            st.info("Enter credentials and press Enter.")
            if st.button("Back to Landing", use_container_width=True):
                st.session_state.page = "landing"
                st.rerun()
            return

        if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
            st.error("Invalid username or password.")
            if st.button("Back to Landing", use_container_width=True):
                st.session_state.page = "landing"
                st.rerun()
            return

        st.session_state.admin_logged_in = True
        st.rerun()

    # Admin dashboard
    df = fetch_all_responses()
    st.write(f"Total responses: **{len(df)}**")

    if len(df) == 0:
        st.info("No responses yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.download_button(
            "Download CSV",
            data=df_to_csv_bytes(df),
            file_name="goa_survey_responses.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.subheader("Quick summaries")
        try:
            c1, c2 = st.columns(2)
            with c1:
                st.write("Respondent type distribution")
                st.bar_chart(df["respondent_type"].value_counts())

            with c2:
                st.write("Zone distribution")
                zone_series = df["zone"].fillna("")
                other_text = df["zone_other_text"].fillna("")
                zone_display = zone_series.where(zone_series != "Other", "Other: " + other_text)
                st.bar_chart(zone_display.value_counts())

            st.write("Biggest issue distribution")
            st.bar_chart(df["biggest_issue"].value_counts())
        except Exception:
            st.info("Charts unavailable due to missing values in current data.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Logout", use_container_width=True):
            st.session_state.admin_logged_in = False
            st.rerun()
    with c2:
        if st.button("Back to Landing", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()


# -----------------------------
# Main
# -----------------------------
def main():
    st.set_page_config(page_title="Goa Survey", layout="centered")
    init_state()
    ensure_db()

    # Sidebar: disabled during survey to prevent random jumps
    with st.sidebar:
        st.markdown("### Navigation")
        if st.session_state.page != "survey":
            if st.button("Landing", use_container_width=True):
                st.session_state.page = "landing"
                st.rerun()
            if st.button("Survey", use_container_width=True):
                reset_survey()
                st.session_state.page = "survey"
                st.rerun()
            if st.button("Admin", use_container_width=True):
                st.session_state.page = "admin"
                st.rerun()
        else:
            st.info("Survey in progress.\n\nUse Next/Back buttons in the main page.")

        st.markdown("---")
        st.markdown("**Local storage:** SQLite (`data/survey.db`)")
        st.markdown("**Export:** Admin → Download CSV")

    # Route
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
