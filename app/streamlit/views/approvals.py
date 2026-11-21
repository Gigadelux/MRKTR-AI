import streamlit as st

import client
import ui

st.title("Approvals")
st.caption(
    "Draft replies to incoming email. Nothing is sent from this page: it is read-only for now."
)
source, drafts = client.data("/approvals")
ui.banner(source)

_, funnel = client.data("/funnel")
st.metric("Drafts approved unchanged", ui.pct(funnel["drafts_approved_unchanged"]))

if not drafts:
    st.caption("No drafts yet.")
for view in drafts:
    d = view["draft"]
    with st.container(border=True):
        st.markdown(
            f"**{d['classification'].replace('_', ' ')}** · {d['status']} · {view['email'] or ''}"
        )
        st.markdown("Incoming")
        st.write(view["incoming"] or "")
        st.markdown("Draft reply")
        st.write(d["draft_text"])
        if d["final_text"] and d["final_text"] != d["draft_text"]:
            st.markdown("Approved with edits")
            st.write(d["final_text"])
