import pandas as pd
import streamlit as st

import client
import ui

st.title("Leads")
STATUSES = ["all", "new", "contacted", "engaged", "qualified", "booked", "not_now", "unsubscribed"]
status = st.selectbox("Status", STATUSES)
source, leads = client.data("/leads", status=None if status == "all" else status)
ui.banner(source)

rows = []
for lead in leads:
    crm = lead["crm"] or {}
    rows.append(
        {
            "Email": lead["user"]["email"],
            "Status": crm.get("status", "new"),
            "Their company": crm.get("company_name"),
            "Company description": crm.get("company_description"),
            "Role": crm.get("role"),
            "Industry": crm.get("industry"),
            "Size": crm.get("size"),
            "Use case": crm.get("use_case"),
            "Mode": lead["user"]["pref_mode"],
            "Messages": lead["messages"],
        }
    )
if rows:
    height = min(38 + 35 * len(rows), 760)  # show every row instead of an inner scrollbar
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=height)
    st.caption(f"{len(rows)} leads")
else:
    st.caption("No leads to show.")
