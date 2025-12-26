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

    # Clear widget states (so nothing appears prefilled)
    for k in list(st.session_state.keys()):
        if k.endswith("_w") or k.startswith("q") or k.startswith("admin_"):
            del st.session_state[k]


def set_error(msg: str):
    st.session_state.errors.append(msg)


def show_errors():
    if st.session_state.errors:
        st.error("Please complete the required fields:")
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

    if step == 0:
        if not f.get("respondent_type"):
            set_error("Q1 (Respondent type) is required.")

    if step == 1:
        if not f.get("zone"):
            set_error("Q2 (Zone) is required.")
        if f.get("zone") == "Other" and not f.get("zone_other_text", "").strip():
            set_error("Q2 (Other zone) is required when Zone = Other.")
        if not f.get("time_in_area"):
            set_error("Q3 (Time in area) is required.")

    if step == 2:
        rt = f.get("respondent_type", "")
        if rt == "Tourist":
            required = [
                ("length_of_stay", "Q4"),
                ("places_visited", "Q5"),
                ("aware_water_stress", "Q6"),
                ("showers_per_day", "Q7"),
                ("drinking_water", "Q8"),
                ("tourism_increases_water_demand", "Q9"),
                ("perceived_crowding", "Q10"),
                ("crowding_reduces_enjoyment", "Q11"),
                ("beach_cleanliness", "Q12"),
            ]
            for k, q in required:
                if not str(f.get(k, "")).strip():
                    set_error(f"{q} is required for Tourist respondents.")

        elif rt == "Local Resident":
            required = [
                ("tourism_affects_water_availability", "Q13"),
                ("peak_season_shortages_local", "Q14"),
                ("tanker_dependency", "Q15"),
                ("water_trend_years", "Q16"),
                ("benefits_shared_fairly", "Q17"),
            ]
            for k, q in required:
                if not str(f.get(k, "")).strip():
                    set_error(f"{q} is required for Local Resident respondents.")

        elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
            required = [
                ("peak_season_shortages_staff", "Q18"),
                ("main_water_source", "Q19"),
                ("water_saving_measures", "Q20"),
                ("tourism_growth_increases_pressure", "Q21"),
            ]
            for k, q in required:
                if not str(f.get(k, "")).strip():
                    set_error(f"{q} is required for Staff respondents.")

        elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
            required = [
                ("peak_season_pressure", "Q22"),
                ("facilities_stressed", "Q23"),
                ("infra_handles_future_growth", "Q24"),
            ]
            for k, q in required:
                if not str(f.get(k, "")).strip():
                    set_error(f"{q} is required for Worker respondents.")
        else:
            set_error("Respondent type is missing. Go back to Step 1.")

    if step == 3:
        required = [
            ("biggest_issue", "Q25"),
            ("should_define_limits", "Q26"),
            ("support_stricter_water_rules", "Q27"),
        ]
        for k, q in required:
            if not str(f.get(k, "")).strip():
                set_error(f"{q} is required.")

    return len(st.session_state.errors) == 0


# -----------------------------
# Landing
# -----------------------------
def render_landing():
    st.title(APP_TITLE)

    st.subheader("Consent")
    st.write(
        "This is an academic field survey for sustainable tourism planning in Goa.\n\n"
        "Participation is voluntary. Responses are stored locally for planning analysis."
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


# -----------------------------
# Steps
# -----------------------------
def render_step_1():
    st.subheader(progress_label(0))
    st.write("## Section 1 — Respondent Identification")

    with st.form("step1_form", clear_on_submit=False):
        rt = st.selectbox(
            "Q1. You are currently visiting / living / working in Goa as:",
            RESPONDENT_TYPES,
            index=None,
            placeholder="Select one",
            key="q1_rt_w",
        )
        go_next = st.form_submit_button("Next")

    if go_next:
        st.session_state.form["respondent_type"] = rt or ""

        # Clear role-specific fields only if type changes (and also blank old values)
        if st.session_state.last_respondent_type != (rt or ""):
            for k in [
                "length_of_stay", "places_visited", "aware_water_stress", "showers_per_day", "drinking_water",
                "tourism_increases_water_demand", "perceived_crowding", "crowding_reduces_enjoyment", "beach_cleanliness",
                "tourism_affects_water_availability", "peak_season_shortages_local", "tanker_dependency", "water_trend_years", "benefits_shared_fairly",
                "peak_season_shortages_staff", "main_water_source", "water_saving_measures", "tourism_growth_increases_pressure",
                "peak_season_pressure", "facilities_stressed", "infra_handles_future_growth",
            ]:
                st.session_state.form[k] = ""
            st.session_state.last_respondent_type = rt or ""

        if validate_current_step(0):
            st.session_state.step = 1
            st.rerun()


def render_step_2():
    st.subheader(progress_label(1))
    st.write("## Section 2 — Basic Context")

    zone_options = ["Baga", "Calangute", "Anjuna", "Candolim", "Vagator", "Other"]
    time_options = ["<1 week", "1–4 weeks", "several months", "many years"]
    age_options = ["<18", "18–25", "26–35", "36–50", "50+"]

    with st.form("step2_form", clear_on_submit=False):
        zone = st.selectbox(
            "Q2. Area you are currently in / associated with:",
            zone_options,
            index=None,
            placeholder="Select one",
            key="q2_zone_w",
        )

        zone_other = ""
        if zone == "Other":
            zone_other = st.text_input("Other (specify):", key="q2_other_w")

        time_in_area = st.selectbox(
            "Q3. How long have you been in this area (visit or residence)?",
            time_options,
            index=None,
            placeholder="Select one",
            key="q3_time_w",
        )

        age_group = st.selectbox(
            "Age group (optional):",
            age_options,
            index=None,
            placeholder="Optional",
            key="age_w",
        )

        go_next = st.form_submit_button("Next")

    if go_next:
        f = st.session_state.form
        f["zone"] = zone or ""
        f["zone_other_text"] = (zone_other.strip() if zone == "Other" else "")
        f["time_in_area"] = time_in_area or ""
        f["age_group"] = age_group or ""

        if validate_current_step(1):
            st.session_state.step = 2
            st.rerun()


def render_step_3():
    st.subheader(progress_label(2))
    rt = st.session_state.form.get("respondent_type", "")
    st.write("## Section 3 — Role-specific Questions")

    with st.form("step3_form", clear_on_submit=False):
        if rt == "Tourist":
            st.write("### Tourist")

            length_of_stay = st.selectbox(
                "Q4. Length of stay in Goa:",
                ["1–3 days", "4–7 days", "More than 7 days"],
                index=None,
                placeholder="Select one",
                key="q4_w",
            )

            places = st.multiselect(
                "Q5. Which places have you visited or plan to visit? (Multiple choice)",
                ["Beaches", "Markets", "Nightlife areas", "Heritage / cultural sites"],
                default=[],
                key="q5_w",
            )

            aware = st.selectbox(
                "Q6. Were you aware that Goa faces water stress, especially during peak tourist season?",
                ["Yes", "No"],
                index=None,
                placeholder="Select one",
                key="q6_w",
            )

            showers = st.selectbox(
                "Q7. During your stay, how often do you shower per day?",
                ["Once", "Twice", "More than twice"],
                index=None,
                placeholder="Select one",
                key="q7_w",
            )

            drinking = st.selectbox(
                "Q8. How do you usually consume drinking water?",
                ["Bottled water", "Hotel-provided filtered water", "Both"],
                index=None,
                placeholder="Select one",
                key="q8_w",
            )

            demand = st.selectbox(
                "Q9. Do you think tourism significantly increases water demand in Goa?",
                ["Strongly agree", "Agree", "Neutral", "Disagree"],
                index=None,
                placeholder="Select one",
                key="q9_w",
            )

            crowding = st.selectbox(
                "Q10. How crowded do you feel this area is during your visit?",
                ["Low", "Moderate", "High", "Very high"],
                index=None,
                placeholder="Select one",
                key="q10_w",
            )

            reduce = st.selectbox(
                "Q11. Does crowding reduce your enjoyment of the destination?",
                ["Not at all", "Slightly", "Moderately", "Significantly"],
                index=None,
                placeholder="Select one",
                key="q11_w",
            )

            clean = st.selectbox(
                "Q12. How would you rate beach cleanliness here?",
                ["Very clean", "Clean", "Average", "Poor"],
                index=None,
                placeholder="Select one",
                key="q12_w",
            )

        elif rt == "Local Resident":
            st.write("### Local Resident")

            affects = st.selectbox(
                "Q13. Has tourism affected water availability in your area?",
                ["Yes, significantly", "Yes, slightly", "No"],
                index=None,
                placeholder="Select one",
                key="q13_w",
            )

            shortages = st.selectbox(
                "Q14. During peak tourist season, do you face water shortages?",
                ["Frequently", "Sometimes", "Rarely", "Never"],
                index=None,
                placeholder="Select one",
                key="q14_w",
            )

            tanker = st.selectbox(
                "Q15. Do you rely on water tankers during peak season?",
                ["Yes", "No"],
                index=None,
                placeholder="Select one",
                key="q15_w",
            )

            trend = st.selectbox(
                "Q16. Over the years, has water availability improved or worsened?",
                ["Improved", "No change", "Worsened"],
                index=None,
                placeholder="Select one",
                key="q16_w",
            )

            benefits = st.selectbox(
                "Q17. Do you feel tourism benefits are shared fairly with local residents?",
                ["Yes", "No", "Partially"],
                index=None,
                placeholder="Select one",
                key="q17_w",
            )

        elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
            st.write("### Hotel / Shack / Restaurant Staff")

            shortages_staff = st.selectbox(
                "Q18. During peak season, does your establishment face water shortages?",
                ["Yes", "No", "Sometimes"],
                index=None,
                placeholder="Select one",
                key="q18_w",
            )

            source = st.selectbox(
                "Q19. What is the main source of water?",
                ["Municipal supply", "Borewell / groundwater", "Water tankers", "Combination"],
                index=None,
                placeholder="Select one",
                key="q19_w",
            )

            wsm = st.multiselect(
                "Q20. Are water-saving measures used? (Multiple choice)",
                ["Towel reuse policy", "Low-flow fixtures", "Guest awareness signage", "None"],
                default=[],
                key="q20_w",
            )

            pressure = st.selectbox(
                "Q21. Does tourism growth increase operational pressure on water and waste systems?",
                ["Yes", "No", "Unsure"],
                index=None,
                placeholder="Select one",
                key="q21_w",
            )

        elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
            st.write("### Transport / Beach Worker")

            pressure_level = st.selectbox(
                "Q22. During peak season, how would you describe tourist pressure here?",
                ["Low", "Moderate", "High", "Extreme"],
                index=None,
                placeholder="Select one",
                key="q22_w",
            )

            stressed = st.selectbox(
                "Q23. Do peak tourist months increase stress on public facilities (toilets, water points)?",
                ["Yes", "No"],
                index=None,
                placeholder="Select one",
                key="q23_w",
            )

            infra = st.selectbox(
                "Q24. Do you think current infrastructure can handle future tourism growth?",
                ["Yes", "No", "Not sure"],
                index=None,
                placeholder="Select one",
                key="q24_w",
            )
        else:
            st.warning("Respondent type missing. Please go back to Step 1.")
            st.form_submit_button("Next", disabled=True)

        go_next = st.form_submit_button("Next")

    if go_next:
        f = st.session_state.form

        if rt == "Tourist":
            f["length_of_stay"] = (st.session_state.get("q4_w") or "").replace("More than 7 days", ">7 days").strip()
            f["places_visited"] = multiselect_to_text(st.session_state.get("q5_w", []))
            f["aware_water_stress"] = (st.session_state.get("q6_w") or "").strip().lower()
            f["showers_per_day"] = (st.session_state.get("q7_w") or "").replace("Once", "1").replace("Twice", "2").replace("More than twice", ">2")
            f["drinking_water"] = (st.session_state.get("q8_w") or "")
            # Normalize to spec values
            f["drinking_water"] = (
                f["drinking_water"]
                .replace("Bottled water", "bottled")
                .replace("Hotel-provided filtered water", "filtered")
                .replace("Both", "both")
            )
            f["tourism_increases_water_demand"] = (st.session_state.get("q9_w") or "").lower()
            f["perceived_crowding"] = (st.session_state.get("q10_w") or "").lower()
            f["crowding_reduces_enjoyment"] = (st.session_state.get("q11_w") or "").lower()
            f["beach_cleanliness"] = (st.session_state.get("q12_w") or "").lower()

        elif rt == "Local Resident":
            f["tourism_affects_water_availability"] = (
                (st.session_state.get("q13_w") or "")
                .replace("Yes, significantly", "yes significantly")
                .replace("Yes, slightly", "yes slightly")
                .replace("No", "no")
            )
            f["peak_season_shortages_local"] = (st.session_state.get("q14_w") or "").lower()
            f["tanker_dependency"] = (st.session_state.get("q15_w") or "").lower()
            f["water_trend_years"] = (st.session_state.get("q16_w") or "").lower()
            f["benefits_shared_fairly"] = (st.session_state.get("q17_w") or "").lower()

        elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
            f["peak_season_shortages_staff"] = (st.session_state.get("q18_w") or "").lower()
            f["main_water_source"] = (st.session_state.get("q19_w") or "")
            f["main_water_source"] = (
                f["main_water_source"]
                .replace("Municipal supply", "municipal")
                .replace("Borewell / groundwater", "borewell/groundwater")
                .replace("Water tankers", "tankers")
                .replace("Combination", "combination")
            )
            # Store in spec-style values
            raw_wsm = st.session_state.get("q20_w", [])
            mapped = []
            for item in raw_wsm:
                mapped.append(
                    item.replace("Towel reuse policy", "towel reuse")
                    .replace("Low-flow fixtures", "low-flow fixtures")
                    .replace("Guest awareness signage", "signage")
                    .replace("None", "none")
                )
            f["water_saving_measures"] = multiselect_to_text(mapped)
            f["tourism_growth_increases_pressure"] = (st.session_state.get("q21_w") or "").lower()

        elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
            f["peak_season_pressure"] = (st.session_state.get("q22_w") or "").lower()
            f["facilities_stressed"] = (st.session_state.get("q23_w") or "").lower()
            f["infra_handles_future_growth"] = (st.session_state.get("q24_w") or "").lower()

        if validate_current_step(2):
            st.session_state.step = 3
            st.rerun()


def render_step_4():
    st.subheader(progress_label(3))
    st.write("## Section 4 — Sustainability & Planning")

    with st.form("step4_form", clear_on_submit=False):
        biggest_issue = st.selectbox(
            "Q25. What do you think is the biggest issue caused by tourism in Goa?",
            ["Water shortage", "Overcrowding", "Waste & pollution", "Traffic", "Loss of natural beauty"],
            index=None,
            placeholder="Select one",
            key="q25_w",
        )

        limits = st.selectbox(
            "Q26. Should Goa define limits on tourism growth to protect water and environment?",
            ["Strongly agree", "Agree", "Neutral", "Disagree"],
            index=None,
            placeholder="Select one",
            key="q26_w",
        )

        stricter = st.selectbox(
            "Q27. Would you support stricter water-use rules for tourism facilities?",
            ["Yes", "No", "Depends"],
            index=None,
            placeholder="Select one",
            key="q27_w",
        )

        suggestion = st.text_area(
            "Q28. In your opinion, what should be the priority for sustainable tourism planning in Goa? (Open-ended)",
            value="",
            placeholder="Write your suggestion...",
            height=120,
            key="q28_w",
        )

        submit = st.form_submit_button("Submit")

    if submit:
        f = st.session_state.form
        f["biggest_issue"] = (biggest_issue or "").lower()
        f["should_define_limits"] = (limits or "").lower()
        f["support_stricter_water_rules"] = (stricter or "").lower()
        f["priority_suggestion"] = (suggestion or "").strip()

        if validate_current_step(3):
            ensure_db()
            ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            f["timestamp"] = ts

            if f.get("zone") != "Other":
                f["zone_other_text"] = ""

            insert_response(f)

            st.success("Response submitted.")
            reset_survey()
            st.session_state.page = "landing"
            st.rerun()


def render_survey():
    st.title(APP_TITLE)

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


# -----------------------------
# Admin
# -----------------------------
def render_admin():
    st.title("Admin")

    if not st.session_state.admin_logged_in:
        with st.form("admin_login_form", clear_on_submit=False):
            username = st.text_input("Username", key="admin_user_w")
            password = st.text_input("Password", type="password", key="admin_pass_w")
            login = st.form_submit_button("Enter")  # Enter key works

        if not login:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Back to Landing", use_container_width=True):
                    st.session_state.page = "landing"
                    st.rerun()
            with c2:
                st.empty()
            return

        if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
            st.error("Invalid username or password.")
            if st.button("Back to Landing", use_container_width=True):
                st.session_state.page = "landing"
                st.rerun()
            return

        st.session_state.admin_logged_in = True
        st.rerun()

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

        st.subheader("Summary")
        try:
            c1, c2 = st.columns(2)
            with c1:
                st.bar_chart(df["respondent_type"].value_counts())
            with c2:
                zone_series = df["zone"].fillna("")
                other_text = df["zone_other_text"].fillna("")
                zone_display = zone_series.where(zone_series != "Other", "Other: " + other_text)
                st.bar_chart(zone_display.value_counts())

            st.bar_chart(df["biggest_issue"].value_counts())
        except Exception:
            st.info("Summary charts unavailable.")

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

    # Sidebar: keep minimal; disable navigation during survey
    with st.sidebar:
        if st.session_state.page != "survey":
            if st.button("Home", use_container_width=True):
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
            st.write("Survey in progress")

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
