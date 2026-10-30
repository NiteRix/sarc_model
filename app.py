"""Web demo.  Run:  streamlit run app.py"""
from pathlib import Path

import pandas as pd
import streamlit as st

import engine as e

ROOT = Path(__file__).parent
st.set_page_config(page_title="Sarcoidosis Likelihood Score", page_icon="🫁", layout="wide")


@st.cache_data
def load():
    df = e.load_cases()
    table, _, _ = e.train(df)
    return df, table


df, table = load()
pts = dict(zip(table["Finding"], table["Points"]))

GROUPS = {
    "General": ["Fever / fatigue", "Night sweats", "Weight loss", "Muscle pain", "Joint / back pain"],
    "Chest": ["Dry cough", "Shortness of breath", "Palpitations / heart block"],
    "Skin, nose & mouth": ["Skin lesions / itching", "Blocked nose", "Oral ulcers"],
    "Abdomen": ["Abdominal pain", "Chronic diarrhea", "Nausea / vomiting", "Jaundice",
                "Enlarged liver", "Enlarged spleen"],
    "Other": ["Enlarged lymph nodes", "Nerve pain / numbness"],
    "Imaging & tests": ["Imaging: enlarged chest lymph nodes", "Imaging: lung nodules / infiltrates",
                        "Heart tests abnormal (ECG / echo / MRI)", "Liver tests abnormal"],
}

st.title("Sarcoidosis Likelihood Score")
st.caption("Research prototype for a student competition. It estimates a likelihood — it does not diagnose. "
           "Always confirm with a specialist and biopsy.")

tab1, tab2 = st.tabs(["Check a patient", "What the model learned"])

with tab1:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("1. Symptoms & findings")
        st.caption("Tick everything the patient has. Leave the rest empty.")
        chosen = {}
        cols = st.columns(2)
        for i, (g, items) in enumerate(GROUPS.items()):
            with cols[i % 2]:
                st.markdown(f"**{g}**")
                for f in items:
                    chosen[f] = "Yes" if st.checkbox(f, key=f) else "Not checked"

        st.subheader("2. Lab results (optional)")
        st.caption("Leave empty if the test was not done.")
        labs = {}
        lc = st.columns(4)
        for i, (name, lab) in enumerate(e.CONFIG["labs"].items()):
            with lc[i % 4]:
                v = st.number_input(f"{name} ({lab['unit']})", min_value=0.0, value=None,
                                    step=0.1, format="%.2f", key=name,
                                    help=f"Normal: {lab['low']}–{lab['high']}")
                if v is not None:
                    labs[name] = v

        with st.expander("Advanced"):
            pretest = st.slider("Starting chance before any findings (%)", 1, 50,
                                int(e.CONFIG["pretest_probability"] * 100)) / 100

    total, breakdown = e.score({"symptoms": chosen, "labs": labs}, table)
    prob = e.probability(pretest, total)

    with right:
        st.subheader("Result")
        level = "High" if prob >= 0.6 else ("Moderate" if prob >= 0.3 else "Low")
        color = {"High": "#C0504D", "Moderate": "#E3A21A", "Low": "#2E8B57"}[level]
        st.markdown(
            f"<div style='padding:18px;border-radius:12px;border:2px solid {color}'>"
            f"<div style='font-size:15px;color:gray'>Estimated likelihood of sarcoidosis</div>"
            f"<div style='font-size:56px;font-weight:700;color:{color}'>{prob*100:.0f}%</div>"
            f"<div style='font-size:18px'>{level} — total points: <b>{total}</b></div></div>",
            unsafe_allow_html=True)
        st.progress(min(prob, 1.0))
        if breakdown:
            st.markdown("**Why — points from each finding**")
            bd = pd.DataFrame(breakdown, columns=["Finding", "Points"])
            st.dataframe(bd, hide_index=True, width="stretch")
        else:
            st.info("No findings entered yet.")
        if level != "Low":
            st.warning("Suggested next step: rule out TB and lymphoma, then refer for chest CT and biopsy.")

with tab2:
    st.subheader(f"Based on {len(df)} published cases "
                 f"({int(df.y.sum())} sarcoidosis, {int((df.y == 0).sum())} look-alike diseases)")
    c1, c2 = st.columns(2)
    out = ROOT / "outputs"
    with c1:
        if (out / "1_most_frequent_symptoms.png").exists():
            st.image(str(out / "1_most_frequent_symptoms.png"))
    with c2:
        if (out / "2_points_per_finding.png").exists():
            st.image(str(out / "2_points_per_finding.png"))
    st.markdown("**Points per finding**")
    show = table[["Finding", "Points", "Starting points (clinical knowledge)",
                  "% in sarcoidosis", "% in other diseases"]].copy()
    for c in ("% in sarcoidosis", "% in other diseases"):
        show[c] = show[c].map(lambda x: "–" if pd.isna(x) else f"{x:.0%}")
    st.dataframe(show, hide_index=True, width="stretch")
    st.markdown("**Lab points** — a lab gets points when it is outside its normal range: "
                "up to 1.5× the limit = ⅓ of its max points, 1.5–2× = ⅔, more than 2× = full.")
    st.dataframe(pd.DataFrame([{"Lab": k, "Normal range": f"{v['low']}–{v['high']} {v['unit']}",
                                "Max points": v["max_points"]} for k, v in e.CONFIG["labs"].items()]),
                 hide_index=True, width="stretch")
    st.caption("Points start from clinical knowledge of how typical each finding is for sarcoidosis, "
               "then are adjusted by how often it appeared in the sarcoidosis cases vs the look-alike cases. "
               "How the % works: the patient starts at a base chance (default 10%), and every 2 points "
               "doubles the odds. Negative points come from findings more typical of TB or lymphoma.")
