import streamlit as st

import client
import ui

st.title("Conversations")
source, leads = client.data("/leads")
ui.banner(source)

talkers = [lead for lead in leads if lead["messages"] > 0]
if not talkers:
    st.caption("No conversations yet.")
    st.stop()

pick = st.selectbox(
    "Lead",
    talkers,
    format_func=lambda lead: f"{lead['user']['email']}  ({lead['messages']} messages)",
)
_, messages = client.data(f"/conversations/{pick['user']['user_id']}")

LABEL = {
    "user_text": "typed",
    "stt": "voice note, transcribed",
    "agent_text": "text",
    "tts_script": "voice note, script sent to text-to-speech",
}
for m in messages:
    who = "user" if m["direction"] == "in" else "assistant"
    with st.chat_message(who):
        st.write(m["text"] or "")
        st.caption(
            f"{m['channel']} · {LABEL[m['transcript_source']]} · {m['created_at'][:16].replace('T', ' ')}"
        )
