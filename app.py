import os
from collections import Counter

import pandas as pd
import streamlit as st

from qualifier import SCORES, qualify_leads, validate_columns

MAX_LEADS = 25
SAMPLE_PATH = "sample_leads.csv"
SCORE_COLORS = {"Hot": "#C2410C", "Warm": "#B7791F", "Cold": "#2B6CB0", "Error": "#6B7280"}
SCORE_ORDER = {"Hot": 0, "Warm": 1, "Cold": 2, "Error": 3}

st.set_page_config(page_title="AI Lead Qualifier", page_icon="🚗", layout="wide")

st.markdown("""
<style>
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1180px; }
.hero h1 { font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 .3rem; }
.hero p { color: #5C6B73; margin: 0; font-size: 1.02rem; max-width: 62ch; }
.kpi { border: 1px solid #D5DBDF; border-radius: 8px; padding: 14px 16px; background: #fff; }
.kpi .label { color: #5C6B73; font-size: .82rem; margin-bottom: 4px; }
.kpi .value { font-size: 1.9rem; font-weight: 800; line-height: 1; letter-spacing: -0.02em; }
.kpi .sub { color: #5C6B73; font-size: .8rem; margin-top: 6px; }
.lead { border: 1px solid #D5DBDF; border-left: 5px solid var(--c); border-radius: 8px; padding: 14px 16px 10px; background: #fff; margin-bottom: 4px; }
.lead .top { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.lead .name { font-size: 1.08rem; font-weight: 700; }
.badge { display: inline-block; background: var(--c); color: #fff; font-size: .74rem; font-weight: 700; padding: 3px 10px; border-radius: 999px; }
.lead .meta { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px 16px; margin: 10px 0 8px; }
.lead .meta div { font-size: .9rem; }
.lead .meta span { display: block; color: #5C6B73; font-size: .74rem; }
.lead .reason { color: #3B4752; font-size: .92rem; margin: 0; }
.step { color: #5C6B73; font-size: .9rem; }
</style>
""", unsafe_allow_html=True)


def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.getenv("GEMINI_API_KEY")


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def run_qualification(leads, api_key, label):
    progress = st.progress(0, text=label)

    def update(done, total):
        progress.progress(done / total, text=f"{label} {done} of {total}")

    result = qualify_leads(leads, api_key=api_key, on_progress=update)
    progress.empty()
    return result


def lead_card(row):
    color = SCORE_COLORS.get(row["score"], "#6B7280")
    meta = "".join(
        f"<div><span>{label}</span>{value or 'Unknown'}</div>"
        for label, value in [("Vehicle", row["vehicle"]), ("Pickup", row["pickup_city"]), ("Delivery", row["delivery_city"]), ("Wanted", row["desired_date"])]
    )
    st.markdown(
        f'<div class="lead" style="--c:{color}"><div class="top"><div class="name">{row["name"]}</div>'
        f'<span class="badge">{row["score"]}</span></div><div class="meta">{meta}</div>'
        f'<p class="reason">{row["score_reason"]}</p></div>',
        unsafe_allow_html=True,
    )


st.markdown(
    '<div class="hero"><h1>AI Lead Qualifier</h1><p>Paste in raw vehicle transport quote requests and get back qualified leads: '
    "vehicle, route and date extracted, a Hot / Warm / Cold score with the reason, and a ready-to-send follow-up email for each one.</p></div>",
    unsafe_allow_html=True,
)
st.write("")

api_key = get_api_key()
if not api_key:
    st.error("No Gemini API key found. Add GEMINI_API_KEY to .env or to the app's Streamlit secrets.")
    st.stop()

with st.sidebar:
    st.subheader("How it works")
    st.markdown(
        '<p class="step">1. Load the sample leads or upload a CSV with columns name, email, phone, message, date.</p>'
        '<p class="step">2. Each message is sent to Gemini with scoring rules and a strict JSON format.</p>'
        '<p class="step">3. Review the leads, edit the emails and export everything as CSV.</p>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("Scoring rules")
    st.markdown("**Hot** clear vehicle, route and date within 2 weeks, ready to book\n\n**Warm** most details present, flexible or later date, comparing prices\n\n**Cold** vague request, key details missing, just browsing")
    st.divider()
    sample = pd.read_csv(SAMPLE_PATH)
    st.download_button("Download CSV template", sample.head(2).to_csv(index=False).encode("utf-8"), "leads_template.csv", "text/csv")
    st.caption(f"Built by Teodor Ninkov · [Source on GitHub](https://github.com/teodor-ninkov/ai-lead-qualifier)")

source = st.radio("Leads", ["Use sample leads", "Upload my own CSV"], horizontal=True, label_visibility="collapsed")
if source == "Use sample leads":
    leads = pd.read_csv(SAMPLE_PATH)
else:
    uploaded = st.file_uploader("CSV with columns: name, email, phone, message, date", type="csv")
    if not uploaded:
        st.info("Upload a CSV to continue, or switch to the sample leads.")
        st.stop()
    leads = pd.read_csv(uploaded)

missing = validate_columns(leads)
if missing:
    st.error(f"The CSV is missing these columns: {', '.join(missing)}")
    st.stop()
if len(leads) > MAX_LEADS:
    st.warning(f"Only the first {MAX_LEADS} leads will be processed.")
    leads = leads.head(MAX_LEADS)

left, right = st.columns([3, 1])
with left:
    with st.expander(f"Preview {len(leads)} incoming leads"):
        st.dataframe(leads, width="stretch", hide_index=True)
with right:
    if st.button("Qualify leads", type="primary", width="stretch"):
        st.session_state["results"] = run_qualification(leads, api_key, "Qualifying")
        st.session_state["emails"] = {}

results = st.session_state.get("results")
if results is None:
    st.stop()

counts = Counter(results["score"])
errors = counts.get("Error", 0)
if errors:
    st.warning(f"Failed leads: {errors}. Usually a temporary overload on Google's side.")
    if st.button("Retry failed leads"):
        failed = results[results["score"] == "Error"][list(leads.columns)]
        retried = run_qualification(failed, api_key, "Retrying")
        retried.index = failed.index
        st.session_state["results"] = pd.concat([results[results["score"] != "Error"], retried]).sort_index()
        st.rerun()

st.write("")
c1, c2, c3, c4 = st.columns(4)
total = len(results)
kpi(c1, "Leads processed", total, f"{total - errors} scored")
kpi(c2, "Hot", counts.get("Hot", 0), "call today")
kpi(c3, "Warm", counts.get("Warm", 0), "follow up this week")
kpi(c4, "Cold", counts.get("Cold", 0), "ask for details")

st.write("")
chart_col, table_col = st.columns([1, 2])
with chart_col:
    st.caption("Score distribution")
    dist = pd.DataFrame({"score": SCORES, "leads": [counts.get(s, 0) for s in SCORES]}).set_index("score")
    st.bar_chart(dist, color="#1E3A5F", height=220)
with table_col:
    st.caption("Routes")
    routes = results[results["score"].isin(SCORES)][["name", "pickup_city", "delivery_city", "desired_date", "score"]]
    st.dataframe(routes.sort_values("score", key=lambda s: s.map(SCORE_ORDER)), width="stretch", hide_index=True, height=220)

st.divider()
f1, f2 = st.columns([2, 3])
with f1:
    selected = st.multiselect("Show", SCORES + ["Error"], default=SCORES + ["Error"] if errors else SCORES)
with f2:
    query = st.text_input("Search", placeholder="Name, vehicle or city")

view = results[results["score"].isin(selected)].copy()
if query:
    q = query.lower()
    hay = view[["name", "vehicle", "pickup_city", "delivery_city"]].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    view = view[hay.str.contains(q, regex=False)]
view = view.sort_values("score", key=lambda s: s.map(SCORE_ORDER))

st.subheader(f"{len(view)} leads")
emails = st.session_state.setdefault("emails", {})
for idx, row in view.iterrows():
    lead_card(row)
    if row["score"] != "Error":
        with st.expander(f"Follow-up email to {row['name']}"):
            emails[idx] = st.text_area("Email", emails.get(idx, row["follow_up_email"]), height=160, key=f"email-{idx}", label_visibility="collapsed")
            st.caption(f"To: {row['email']} · {row['phone']}")
    st.write("")

export = results.copy()
for idx, text in emails.items():
    if idx in export.index:
        export.loc[idx, "follow_up_email"] = text
st.divider()
d1, d2 = st.columns(2)
d1.download_button("Download results CSV", export.to_csv(index=False).encode("utf-8"), "qualified_leads.csv", "text/csv", width="stretch")
emails_txt = "\n\n----------\n\n".join(f"To: {r['email']}\nSubject: Your vehicle transport quote\n\n{export.loc[i, 'follow_up_email']}" for i, r in export.iterrows() if r["score"] in SCORES)
d2.download_button("Download all emails (.txt)", emails_txt.encode("utf-8"), "follow_up_emails.txt", "text/plain", width="stretch")
