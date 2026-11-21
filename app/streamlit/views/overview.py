import altair as alt
import pandas as pd
import streamlit as st

import client
import ui
from orb import render_orb

st.title("Overview")
source, funnel = client.data("/funnel")
ui.banner(source)
render_orb(height=460)

steps = {s["step"]: s["count"] for s in funnel["steps"]}
cols = st.columns(5)
cols[0].metric("Emails sent", steps["Emails sent"])
cols[1].metric("Click-through", ui.pct(funnel["click_through"]))
cols[2].metric("Replied", steps["Replied"])
cols[3].metric("Qualified", steps["Qualified"])
cols[4].metric("Booked", steps["Booked"])

st.subheader("Funnel")
frame = pd.DataFrame(funnel["steps"])
chart = (
    alt.Chart(frame)
    .mark_bar(color=ui.ACCENT, cornerRadiusEnd=4)
    .encode(
        y=alt.Y(
            "step:N", sort=None, title=None, axis=alt.Axis(labelColor="#cfcfcf", labelFontSize=13)
        ),
        x=alt.X("count:Q", title=None, axis=alt.Axis(labelColor="#8a8a8a", gridColor="#141414")),
        tooltip=["step", "count"],
    )
    .properties(height=260, background="#000000")
    .configure_view(strokeWidth=0)
)
st.altair_chart(chart, width="stretch")

left, right = st.columns(2)
with left:
    st.subheader("Mode chosen")
    labels = {
        "audio_transcript": "Audio + transcript",
        "audio_only": "Audio only",
        "text_only": "Text only",
    }
    split = funnel["mode_split"]
    if split:
        st.dataframe(
            pd.DataFrame(
                {"Mode": [labels.get(k, k) for k in split], "Users": list(split.values())}
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("No mode chosen yet.")
with right:
    st.subheader("Conversation")
    st.metric("Replied, of those who opened Telegram", ui.pct(funnel["reply_rate"]))
    st.metric(
        "Messages per replying user",
        funnel["avg_turns"] if funnel["avg_turns"] is not None else "n/a",
    )
