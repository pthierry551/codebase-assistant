# app.py
import streamlit as st
from agent import Agent

st.set_page_config(page_title="Codebase Assistant", page_icon="🔍")
st.title("🔍 Codebase Assistant")
st.caption("RAG + agentic tool use over a local codebase")

# Repo path input — only re-init the agent if the path changes
repo_path = st.text_input("Repo path", value=r"C:\Project\sticky-board")

if "agent" not in st.session_state or st.session_state.get("repo_path") != repo_path:
    with st.spinner("Loading embeddings and connecting agent..."):
        st.session_state.agent = Agent(repo_path)
        st.session_state.repo_path = repo_path
        st.session_state.messages = []

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
question = st.chat_input("Ask about the codebase...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = st.session_state.agent.ask(question)
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})