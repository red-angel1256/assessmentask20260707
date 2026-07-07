import os
import streamlit as st
import requests
import uuid

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/ask")

st.set_page_config(page_title="AI Mental Health Evaluation", layout="wide")
st.title("MindMate: Mental Health Check-In")
st.caption("Structured wellbeing evaluation with safety-first design")

with st.sidebar:
    st.header("Evaluation Status")
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    st.text(f"Session: {st.session_state.session_id[:8]}...")
    if "last_meta" in st.session_state:
        meta = st.session_state.last_meta
        st.metric("Severity Index", f"{meta.get('severity_index', 0):.2f}")
        st.text(f"Label: {meta.get('severity_label', '—')}")
        st.text(f"State: {meta.get('session_state', '—')}")
        st.text(f"PHQ-9: {meta.get('phq9_total', '—')}/27")
        if meta.get("safety_triggered"):
            st.error("Safety layer activated")
    st.divider()
    if st.button("Clear Chat"):
        st.session_state.chat_history = []
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.pop("last_meta", None)
        st.rerun()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    avatar = "😊" if msg["role"] == "user" else "🪷"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])
        if msg["role"] == "assistant" and msg.get("tool_called", "None") != "None":
            st.caption(f"🔧 Tool used: `{msg['tool_called']}`")

user_input = st.chat_input("What's on your mind today?")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    try:
        with st.spinner("Processing..."):
            response = requests.post(
                BACKEND_URL,
                json={
                    "message": user_input,
                    "session_id": st.session_state.session_id,
                    "history": st.session_state.chat_history[:-1],
                },
                timeout=60,
            )
            data = response.json()
            bot_reply = data.get("response", "Sorry, I couldn't process that.")
            tool_used = data.get("tool_called", "None")
            st.session_state.last_meta = data
            if data.get("session_id"):
                st.session_state.session_id = data["session_id"]
    except Exception:
        bot_reply = "⚠️ Backend service is currently unavailable."
        tool_used = "Error"

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": bot_reply,
        "tool_called": tool_used,
    })
    st.rerun()
