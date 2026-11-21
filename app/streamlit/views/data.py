import streamlit as st

import client
import ui

st.title("Data")
status = client.get("/mock/status")
source, _ = client.data("/funnel")
ui.banner(source)

st.markdown(
    "Mock data is fictional and exists only to preview the dashboard. It is stored as JSON files in "
    f"`{status['directory']}` (git-ignored). Loading it never touches a database, and deleting it "
    "removes only those files."
)

seed, delete = st.columns(2)
with seed:
    if st.button("Load mock data", width="stretch"):
        rows = client.call("POST", "/mock/seed")["rows"]
        st.success(f"Loaded {sum(rows.values())} mock rows across {len(rows)} tables.")
        st.rerun()
with delete:
    confirm = st.checkbox("Yes, delete the mock data", disabled=not status["mock"])
    if st.button("Delete mock data", width="stretch", disabled=not (status["mock"] and confirm)):
        client.call("DELETE", "/mock")
        st.success("Mock data deleted.")
        st.rerun()

st.caption("Mock data is loaded." if status["mock"] else "No mock data is loaded.")
