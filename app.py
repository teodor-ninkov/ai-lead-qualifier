import os

import pandas as pd
import streamlit as st

from qualifier import SCORES, qualify_leads, validate_columns

MAX_LEADS = 25
SAMPLE_PATH = "sample_leads.csv"
SCORE_COLORS = {"Hot": "#C2410C", "Warm": "#B7791F", "Cold": "#2B6CB0", "Error": "#6B7280"}

st.set_page_config(page_title="AI Lead Qualifier", page_icon="🚗", layout="wide")


def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.getenv("GEMINI_API_KEY")


def color_score(value):
    color = SCORE_COLORS.get(value)
    return f"color: {color}; font-weight: 600" if color else ""


st.title("AI Lead Qualifier")
st.write(
    "Turns raw vehicle transport quote requests into qualified leads: "
    "extracts the vehicle, route and date, scores each lead Hot, Warm or Cold "
    "and drafts a personalized follow-up email."
)

api_key = get_api_key()
if not api_key:
    st.error("No Gemini API key found. Add GEMINI_API_KEY to .env or to the app's Streamlit secrets.")
    st.stop()

source = st.radio("Leads", ["Use sample leads", "Upload my own CSV"], horizontal=True)

if source == "Use sample leads":
    leads = pd.read_csv(SAMPLE_PATH)
else:
    uploaded = st.file_uploader("CSV with columns: name, email, phone, message, date", type="csv")
    if not uploaded:
        st.info("Upload a CSV to continue.")
        st.stop()
    leads = pd.read_csv(uploaded)

missing = validate_columns(leads)
if missing:
    st.error(f"The CSV is missing these columns: {', '.join(missing)}")
    st.stop()

if len(leads) > MAX_LEADS:
    st.warning(f"Only the first {MAX_LEADS} leads will be processed.")
    leads = leads.head(MAX_LEADS)

with st.expander(f"Preview {len(leads)} leads"):
    st.dataframe(leads, width="stretch", hide_index=True)

if st.button("Qualify leads", type="primary"):
    progress = st.progress(0, text="Starting...")

    def update(done, total):
        progress.progress(done / total, text=f"Qualified {done} of {total}")

    st.session_state["results"] = qualify_leads(leads, api_key=api_key, on_progress=update)
    progress.empty()

results = st.session_state.get("results")
if results is not None:
    counts = results["score"].value_counts()
    cols = st.columns(len(SCORES))
    for col, score in zip(cols, SCORES):
        col.metric(score, int(counts.get(score, 0)))

    errors = int(counts.get("Error", 0))
    if errors:
        st.warning(f"Failed leads: {errors}. Check the score_reason column for details.")

    selected = st.multiselect("Show", SCORES + ["Error"], default=SCORES)
    view = results[results["score"].isin(selected)]

    table = view[["name", "vehicle", "pickup_city", "delivery_city", "desired_date", "score", "score_reason"]]
    st.dataframe(table.style.map(color_score, subset=["score"]), width="stretch", hide_index=True)

    st.subheader("Follow-up emails")
    for _, row in view.iterrows():
        with st.expander(f"{row['score']}: {row['name']} ({row['vehicle']})"):
            st.text(row["follow_up_email"])

    st.download_button(
        "Download results CSV",
        results.to_csv(index=False).encode("utf-8"),
        file_name="qualified_leads.csv",
        mime="text/csv",
    )
