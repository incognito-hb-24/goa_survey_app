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
# Storage schema (kept for backward compatibility)
# NOTE: We will NOT export *_other_text columns in CSV.
# NOTE: We will store "Other" typed values directly into zone / age_group.
# -----------------------------
ALL_COLUMNS = [
    "timestamp",
    "respondent_type",
    "zone",
    "zone_other_text",         # kept (legacy), but unused in final output
    "time_in_area",
    "age_group",
    "age_group_other_text",    # kept (legacy), but unused in final output
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
    # Staff
    "peak_season_shortages_staff",
    "main_water_source",
    "water_saving_measures",
    "tourism_growth_increases_pressure",
    # Worker
    "peak_season_pressure",
    "facilities_stressed",
    "infra_handles_future_growth",
    # Sustainability
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
# DB helpers (with migration)
# -----------------------------
def ensure_db():
    os.makedirs(DB_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()

        # Migration: add missing columns
        existing_cols = set(r[1] for r in conn.execute("PRAGMA table_info(responses);").fetchall())
        for col in ALL_COLUMNS:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE responses ADD COLUMN {col} TEXT;")
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
        return pd.read_sql_query("SELECT * FROM responses ORDER BY id DESC", conn)


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    # Excel-friendly (UTF-8 with BOM)
    # Remove legacy columns from export
    drop_cols = [c for c in ["zone_other_text", "age_group_other_text"] if c in df.columns]
    out = df.drop(columns=drop_cols, errors="ignore")
    return out.to_csv(index=False).encode("utf-8-sig")


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
        st.session_state.page = "landing"
    if "step" not in st.session_state:
        st.session_state.step = 0
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

    # Clear widget states so nothing is prefilled
    for k in list(st.session_state.keys()):
        if k.startswith(("q", "admin_")) or k.endswith("_w"):
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
        if not f.get("time_in_area"):
            set_error("Q3 (Time in area) is required.")
        # age_group optional (no validation unless you want)

    if step == 2:
        rt = f.get("respondent_type", "")
        if rt == "Tourist":
            req = ["length_of_stay","places_visited","aware_water_stress","showers_per_day","drinking_water",
                   "tourism_increases_water_demand","perceived_crowding","crowding_reduces_enjoyment","beach_cleanliness"]
            if any(not str(f.get(k, "")).strip() for k in req):
                set_error("All Tourist questions (Q4–Q12) are required.")

        elif rt == "Local Resident":
            req = ["tourism_affects_water_availability","peak_season_shortages_local","tanker_dependency","water_trend_years","benefits_shared_fairly"]
            if any(not str(f.get(k, "")).strip() for k in req):
                set_error("All Local Resident questions (Q13–Q17) are required.")

        elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
            req = ["peak_season_shortages_staff","main_water_source","water_saving_measures","tourism_growth_increases_pressure"]
            if any(not str(f.get(k, "")).strip() for k in req):
                set_error("All Staff questions (Q18–Q21) are required.")

        elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
            req = ["peak_season_pressure","facilities_stressed","infra_handles_future_growth"]
            if any(not str(f.get(k, "")).strip() for k in req):
                set_error("All Worker questions (Q22–Q24) are required.")
        else:
            set_error("Respondent type is missing. Go back to Step 1.")

    if step == 3:
        req = ["biggest_issue","should_define_limits","support_stricter_water_rules"]
        if any(not str(f.get(k, "")).strip() for k in req):
            set_error("Q25–Q27 are required.")

    return len(st.session_state.errors) == 0


# -----------------------------
# Landing
# -----------------------------
def render_landing():
    st.title(APP_TITLE)

    st.subheader("Consent")
    st.write("This is an academic field survey for sustainable tourism planning in Goa. Participation is voluntary.")

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
# Step 1
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

        # Clear role-specific fields only when type changes
        if st.session_state.last_respondent_type != (rt or ""):
            for k in [
                "length_of_stay","places_visited","aware_water_stress","showers_per_day","drinking_water",
                "tourism_increases_water_demand","perceived_crowding","crowding_reduces_enjoyment","beach_cleanliness",
                "tourism_affects_water_availability","peak_season_shortages_local","tanker_dependency","water_trend_years","benefits_shared_fairly",
                "peak_season_shortages_staff","main_water_source","water_saving_measures","tourism_growth_increases_pressure",
                "peak_season_pressure","facilities_stressed","infra_handles_future_growth",
            ]:
                st.session_state.form[k] = ""
            st.session_state.last_respondent_type = rt or ""

        if validate_current_step(0):
            st.session_state.step = 1
            st.rerun()


# -----------------------------
# Step 2 (Dynamic "Other" appears immediately)
# IMPORTANT: no st.form here
# AND "Other" text is stored into SAME column (zone / age_group)
# -----------------------------
def render_step_2():
    st.subheader(progress_label(1))
    st.write("## Section 2 — Basic Context")

    zone_options = ["Baga", "Calangute", "Anjuna", "Candolim", "Vagator", "Other"]
    time_options = ["<1 week", "1–4 weeks", "several months", "many years"]
    age_options = ["<18", "18-25", "26-35", "36-50", "50+", "Other"]

    st.selectbox(
        "Q2. Area you are currently in / associated with:",
        zone_options,
        index=None,
        placeholder="Select one",
        key="q2_zone_w",
    )

    zone_other_box = st.empty()
    if st.session_state.get("q2_zone_w") == "Other":
        zone_other_box.text_input("Other (specify):", key="q2_zone_other_w")
    else:
        # ensure stale value doesn't hang around
        if "q2_zone_other_w" in st.session_state:
            st.session_state["q2_zone_other_w"] = ""

    st.selectbox(
        "Q3. How long have you been in this area (visit or residence)?",
        time_options,
        index=None,
        placeholder="Select one",
        key="q3_time_w",
    )

    st.selectbox(
        "Age group (optional):",
        age_options,
        index=None,
        placeholder="Optional",
        key="q_age_w",
    )

    age_other_box = st.empty()
    if st.session_state.get("q_age_w") == "Other":
        age_other_box.text_input("Age group (Other - specify):", key="q_age_other_w")
    else:
        if "q_age_other_w" in st.session_state:
            st.session_state["q_age_other_w"] = ""

    if st.button("Next", use_container_width=True):
        f = st.session_state.form

        zone_sel = st.session_state.get("q2_zone_w") or ""
        zone_other = (st.session_state.get("q2_zone_other_w") or "").strip()

        # Store "Other" text into SAME column
        if zone_sel == "Other":
            f["zone"] = zone_other
        else:
            f["zone"] = zone_sel

        # keep legacy columns empty
        f["zone_other_text"] = ""

        f["time_in_area"] = st.session_state.get("q3_time_w") or ""

        age_sel = st.session_state.get("q_age_w") or ""
        age_other = (st.session_state.get("q_age_other_w") or "").strip()

        # Store "Other" text into SAME column
        if age_sel == "Other":
            f["age_group"] = age_other
        else:
            f["age_group"] = age_sel

        f["age_group_other_text"] = ""

        # Extra validation: if "Other" chosen but textbox empty, block
        st.session_state.errors = []
        if zone_sel == "Other" and not zone_other:
            set_error("Q2 (Other zone) is required when Zone = Other.")
        if age_sel == "Other" and not age_other:
            set_error("Age group (Other) text is required when Age group = Other.")

        if validate_current_step(1) and not st.session_state.errors:
            st.session_state.step = 2
            st.rerun()


# -----------------------------
# Step 3 (form)
# -----------------------------
def render_step_3():
    st.subheader(progress_label(2))
    rt = st.session_state.form.get("respondent_type", "")
    st.write("## Section 3 — Role-specific Questions")

    with st.form("step3_form", clear_on_submit=False):
        if rt == "Tourist":
            st.write("### Tourist")
            st.selectbox("Q4. Length of stay in Goa:", ["1–3 days","4–7 days","More than 7 days"],
                         index=None, placeholder="Select one", key="q4_w")
            st.multiselect("Q5. Which places have you visited or plan to visit? (Multiple choice)",
                           ["Beaches","Markets","Nightlife areas","Heritage / cultural sites"], default=[], key="q5_w")
            st.selectbox("Q6. Awareness of Goa water stress during peak season?",
                         ["Yes","No"], index=None, placeholder="Select one", key="q6_w")
            st.selectbox("Q7. Showers per day:",
                         ["Once","Twice","More than twice"], index=None, placeholder="Select one", key="q7_w")
            st.selectbox("Q8. Drinking water source:",
                         ["Bottled water","Hotel-provided filtered water","Both"], index=None, placeholder="Select one", key="q8_w")
            st.selectbox("Q9. Tourism increases water demand (Likert):",
                         ["Strongly agree","Agree","Neutral","Disagree"], index=None, placeholder="Select one", key="q9_w")
            st.selectbox("Q10. Perceived crowding:",
                         ["Low","Moderate","High","Very high"], index=None, placeholder="Select one", key="q10_w")
            st.selectbox("Q11. Crowding reduces enjoyment:",
                         ["Not at all","Slightly","Moderately","Significantly"], index=None, placeholder="Select one", key="q11_w")
            st.selectbox("Q12. Beach cleanliness:",
                         ["Very clean","Clean","Average","Poor"], index=None, placeholder="Select one", key="q12_w")

        elif rt == "Local Resident":
            st.write("### Local Resident")
            st.selectbox("Q13. Tourism affected water availability?",
                         ["Yes, significantly","Yes, slightly","No"], index=None, placeholder="Select one", key="q13_w")
            st.selectbox("Q14. Peak-season water shortages?",
                         ["Frequently","Sometimes","Rarely","Never"], index=None, placeholder="Select one", key="q14_w")
            st.selectbox("Q15. Tanker dependency during peak?",
                         ["Yes","No"], index=None, placeholder="Select one", key="q15_w")
            st.selectbox("Q16. Water availability trend over years:",
                         ["Improved","No change","Worsened"], index=None, placeholder="Select one", key="q16_w")
            st.selectbox("Q17. Tourism benefits shared fairly?",
                         ["Yes","No","Partially"], index=None, placeholder="Select one", key="q17_w")

        elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
            st.write("### Hotel / Shack / Restaurant Staff")
            st.selectbox("Q18. Establishment faces peak-season water shortages?",
                         ["Yes","No","Sometimes"], index=None, placeholder="Select one", key="q18_w")
            st.selectbox("Q19. Main source of water:",
                         ["Municipal supply","Borewell / groundwater","Water tankers","Combination"],
                         index=None, placeholder="Select one", key="q19_w")
            st.multiselect("Q20. Water-saving measures used? (Multiple choice)",
                           ["Towel reuse policy","Low-flow fixtures","Guest awareness signage","None"],
                           default=[], key="q20_w")
            st.selectbox("Q21. Tourism growth increases operational pressure?",
                         ["Yes","No","Unsure"], index=None, placeholder="Select one", key="q21_w")

        elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
            st.write("### Transport / Beach Worker")
            st.selectbox("Q22. Peak-season tourist pressure:",
                         ["Low","Moderate","High","Extreme"], index=None, placeholder="Select one", key="q22_w")
            st.selectbox("Q23. Peak months increase stress on public facilities?",
                         ["Yes","No"], index=None, placeholder="Select one", key="q23_w")
            st.selectbox("Q24. Infrastructure can handle future tourism growth?",
                         ["Yes","No","Not sure"], index=None, placeholder="Select one", key="q24_w")
        else:
            st.warning("Respondent type missing. Go back to Step 1.")
            st.form_submit_button("Next", disabled=True)

        go_next = st.form_submit_button("Next")

    if go_next:
        f = st.session_state.form

        if rt == "Tourist":
            f["length_of_stay"] = (st.session_state.get("q4_w") or "").replace("More than 7 days", ">7 days")
            f["places_visited"] = multiselect_to_text(st.session_state.get("q5_w", [])).lower()
            f["aware_water_stress"] = (st.session_state.get("q6_w") or "").lower()
            f["showers_per_day"] = (st.session_state.get("q7_w") or "").replace("Once","1").replace("Twice","2").replace("More than twice",">2")
            f["drinking_water"] = (st.session_state.get("q8_w") or "").replace("Bottled water","bottled").replace("Hotel-provided filtered water","filtered").replace("Both","both")
            f["tourism_increases_water_demand"] = (st.session_state.get("q9_w") or "").lower()
            f["perceived_crowding"] = (st.session_state.get("q10_w") or "").lower()
            f["crowding_reduces_enjoyment"] = (st.session_state.get("q11_w") or "").lower()
            f["beach_cleanliness"] = (st.session_state.get("q12_w") or "").lower()

        elif rt == "Local Resident":
            f["tourism_affects_water_availability"] = (st.session_state.get("q13_w") or "").replace("Yes, significantly","yes significantly").replace("Yes, slightly","yes slightly").replace("No","no")
            f["peak_season_shortages_local"] = (st.session_state.get("q14_w") or "").lower()
            f["tanker_dependency"] = (st.session_state.get("q15_w") or "").lower()
            f["water_trend_years"] = (st.session_state.get("q16_w") or "").lower()
            f["benefits_shared_fairly"] = (st.session_state.get("q17_w") or "").lower()

        elif rt in ["Hotel / Homestay / Resort Staff", "Shack / Restaurant Worker"]:
            f["peak_season_shortages_staff"] = (st.session_state.get("q18_w") or "").lower()
            f["main_water_source"] = (st.session_state.get("q19_w") or "").replace("Municipal supply","municipal").replace("Borewell / groundwater","borewell/groundwater").replace("Water tankers","tankers").replace("Combination","combination")
            raw = st.session_state.get("q20_w", [])
            mapped = [x.replace("Towel reuse policy","towel reuse").replace("Low-flow fixtures","low-flow fixtures").replace("Guest awareness signage","signage").replace("None","none") for x in raw]
            f["water_saving_measures"] = multiselect_to_text(mapped)
            f["tourism_growth_increases_pressure"] = (st.session_state.get("q21_w") or "").lower()

        elif rt in ["Taxi / Transport Worker", "Beach Worker / Lifeguard"]:
            f["peak_season_pressure"] = (st.session_state.get("q22_w") or "").lower()
            f["facilities_stressed"] = (st.session_state.get("q23_w") or "").lower()
            f["infra_handles_future_growth"] = (st.session_state.get("q24_w") or "").lower()

        if validate_current_step(2):
            st.session_state.step = 3
            st.rerun()


# -----------------------------
# Step 4 (form)
# -----------------------------
def render_step_4():
    st.subheader(progress_label(3))
    st.write("## Section 4 — Sustainability & Planning")

    with st.form("step4_form", clear_on_submit=False):
        st.selectbox("Q25. Biggest issue caused by tourism in Goa?",
                     ["Water shortage","Overcrowding","Waste & pollution","Traffic","Loss of natural beauty"],
                     index=None, placeholder="Select one", key="q25_w")
        st.selectbox("Q26. Should Goa define limits on tourism growth?",
                     ["Strongly agree","Agree","Neutral","Disagree"],
                     index=None, placeholder="Select one", key="q26_w")
        st.selectbox("Q27. Support stricter water-use rules for tourism facilities?",
                     ["Yes","No","Depends"],
                     index=None, placeholder="Select one", key="q27_w")
        st.text_area("Q28. Priority suggestion (open-ended)", value="", key="q28_w", height=120)

        submit = st.form_submit_button("Submit")

    if submit:
        f = st.session_state.form
        f["biggest_issue"] = (st.session_state.get("q25_w") or "").lower()
        f["should_define_limits"] = (st.session_state.get("q26_w") or "").lower()
        f["support_stricter_water_rules"] = (st.session_state.get("q27_w") or "").lower()
        f["priority_suggestion"] = (st.session_state.get("q28_w") or "").strip()

        if validate_current_step(3):
            ensure_db()
            f["timestamp"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

            insert_response(f)
            st.success("Response submitted.")
            reset_survey()
            st.session_state.page = "landing"
            st.rerun()


def render_survey():
    st.title(APP_TITLE)
    st.progress((st.session_state.step + 1) / 4)

    if st.session_state.step == 0:
        render_step_1()
    elif st.session_state.step == 1:
        render_step_2()
    elif st.session_state.step == 2:
        render_step_3()
    elif st.session_state.step == 3:
        render_step_4()

    show_errors()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Back", use_container_width=True, disabled=(st.session_state.step == 0)):
            st.session_state.errors = []
            st.session_state.step = max(0, st.session_state.step - 1)
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

    df = fetch_all_responses()
    st.write(f"Total responses: **{len(df)}**")

    if len(df) == 0:
        st.info("No responses yet.")
    else:
        st.dataframe(df.drop(columns=["zone_other_text", "age_group_other_text"], errors="ignore"),
                     use_container_width=True, hide_index=True)

        st.download_button(
            "Download CSV",
            data=df_to_csv_bytes(df),
            file_name="goa_survey_responses.csv",
            mime="text/csv",
            use_container_width=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Logout", use_container_width=True):
            st.session_state.admin_logged_in = False
            st.rerun()
    with c2:
        if st.button("Back to Landing", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()


def main():
    st.set_page_config(page_title="Goa Survey", layout="centered")
    init_state()
    ensure_db()

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


if __name__ == "__main__":
    main()
