import pandas as pd
import streamlit as st

import client
import ui

st.title("Evals")
st.caption(
    "Laid out like Braintrust: experiments, one row per test case, scores from 0 to 1, and the spans behind each row."
)
source, experiments = client.data("/evals")
ui.banner(source)

if not experiments:
    st.caption("No eval runs yet.")
    st.stop()

suite = st.radio("Suite", ["performance", "security"], horizontal=True)
runs = [e for e in experiments if e["experiment"]["suite"] == suite]
if not runs:
    st.caption("No runs for this suite.")
    st.stop()

st.subheader("Compare runs")
names = [r["experiment"]["name"] for r in runs]
matrix = pd.DataFrame({r["experiment"]["name"]: r["scores"] for r in runs})
st.dataframe(matrix.style.format("{:.2f}"), width="stretch")
st.caption("Each cell is the mean score over the run's test cases. Higher is better.")

st.subheader("Test cases")
chosen = st.selectbox("Run", names)
run = next(r for r in runs if r["experiment"]["name"] == chosen)
_, detail = client.data(f"/evals/{run['experiment']['id']}")
results = detail["results"]
roots = [r for r in results if r["span_type"] == "eval"]
children: dict[str, list] = {}
for r in results:
    if r["span_parents"]:
        children.setdefault(r["root_span_id"], []).append(r)

table = pd.DataFrame(
    [
        {
            "Input": r["input"],
            "Output": r["output"],
            "Expected": r["expected"],
            **{k: v for k, v in r["scores"].items()},
            "Latency (s)": r["metrics"].get("latency_s"),
            "Tags": ", ".join(t for t in r["tags"] if t != "mock"),
        }
        for r in roots
    ]
)
st.dataframe(table, hide_index=True, width="stretch")

with st.expander("Spans of one test case"):
    case = st.selectbox("Case", roots, format_func=lambda r: str(r["input"])[:70])
    st.markdown(f"**{case['span_type']}** · {case['span_name']} · `{case['span_id']}`")
    for child in children.get(case["root_span_id"], []):
        st.markdown(f"↳ **{child['span_type']}** · {child['span_name']} · `{child['span_id']}`")
        st.json(
            {"input": child["input"], "output": child["output"], "metrics": child["metrics"]},
            expanded=False,
        )
