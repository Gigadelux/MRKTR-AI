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

# (direction, message_type) -> what the stored text is
LABEL = {
    ("in", "text"): "typed",
    ("out", "text"): "text",
    ("in", "voice"): "voice note, transcribed",
    ("out", "voice"): "voice note, script sent to text-to-speech",
    ("in", "sticker"): "sticker",
    ("out", "sticker"): "sticker",
    ("out", "video"): "tutorial video",
}
for m in messages:
    who = "user" if m["direction"] == "in" else "assistant"
    kind = m.get("message_type", "text")
    label = LABEL.get((m["direction"], kind), kind)
    with st.chat_message(who):
        st.write(m["text"] or ("[sticker]" if kind == "sticker" else ""))
        st.caption(f"{m['channel']} · {label} · {m['created_at'][:16].replace('T', ' ')}")
