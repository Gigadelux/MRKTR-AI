import streamlit as st

import client

st.title("Logs")
st.caption("The tail of the API log (gitignore/temp/logs/api.log).")
count = st.select_slider("Lines", options=[50, 100, 200, 500, 1000], value=200)
st.button("Refresh")
lines = client.get("/logs", lines=count)["lines"]
st.code("\n".join(lines) if lines else "The log is empty.", language=None)
