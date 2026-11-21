import pandas as pd
import streamlit as st

import client
import ui

st.title("Safety")
source, body = client.data("/masked")
ui.banner(source)

st.subheader("Masked before the model saw them")
st.caption(
    "Flagged sentences are replaced before the LLM reads the message. Originals live only here."
)
masked = body["masked"]
if not masked:
    st.caption("Nothing masked yet.")
for item in masked:
    row = item["masked"]
    with st.expander(
        f"{row['reason'] or row['detector']}  ·  {row['detector']}  ·  score {row['score']}"
    ):
        st.markdown("**Original**")
        st.code(row["original_text"], language=None)
        st.markdown("**What the model saw**")
        st.code(row["masked_text"], language=None)
        st.caption(
            f"{item['email'] or 'unknown user'} · {row['created_at'][:16].replace('T', ' ')}"
        )

st.subheader("Benign decoys that were not masked")
st.caption(
    "Nothing in a decoy looks malicious, so the guards let it through. "
    "These rows come from the security evals; a low score means the agent was drawn off its goal."
)
decoys = body["decoys"]
if decoys:
    frame = pd.DataFrame(decoys).rename(
        columns={
            "experiment": "Run",
            "version": "Version",
            "input": "Decoy",
            "masked": "Masked",
            "decoy_resisted": "Resisted (0-1)",
        }
    )
    st.dataframe(frame, hide_index=True, width="stretch")
else:
    st.caption("No decoy results yet.")
