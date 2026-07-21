# app.py
import streamlit as st
from agent import Agent
from file_tree import build_file_tree, render_tree_html

st.set_page_config(page_title="Codebase Assistant", page_icon="🔍", layout="wide")

st.markdown("""
<style>
.loader-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0 4px 0;
}
.loader-spinner {
    width: 20px;
    height: 20px;
    border: 3px solid rgba(124, 108, 255, 0.15);
    border-top-color: #7c6cff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loader-text { font-size: 14px; color: #cfcfe8; }
details.tree-node > summary {
    cursor: pointer;
    padding: 3px 0;
    font-size: 14px;
}
details.tree-node { margin-left: 14px; }
.tree-file { margin-left: 14px; padding: 3px 0; font-size: 13px; color: #a8a8c0; }
</style>
""", unsafe_allow_html=True)

# --- Session state ---
st.session_state.setdefault("repo_locked", False)
st.session_state.setdefault("repo_input", "")
st.session_state.setdefault("messages", [])
st.session_state.setdefault("file_tree_html", None)

st.title("🔍 Codebase Assistant")

# --- Repo input row: editable before start, locked after ---
input_col, button_col = st.columns([5, 1])
with input_col:
    if st.session_state.repo_locked:
        st.text(st.session_state.repo_input)
    else:
        st.session_state.repo_input = st.text_input(
            "Repo",
            value=st.session_state.repo_input,
            placeholder="Local folder path or GitHub URL",
            label_visibility="collapsed",
        )
with button_col:
    if st.session_state.repo_locked:
        if st.button("Change", use_container_width=True):
            st.session_state.repo_locked = False
            st.session_state.pop("agent", None)
            st.session_state.messages = []
            st.session_state.file_tree_html = None
            st.rerun()
    else:
        if st.button("Start", use_container_width=True, type="primary", disabled=not st.session_state.repo_input.strip()):
            st.session_state.repo_locked = True
            st.rerun()

# --- Build the agent (only once, right after locking) ---
if st.session_state.repo_locked and "agent" not in st.session_state:
    status_box = st.empty()
    progress_bar = st.progress(0)

    def update_status(pct, message):
        status_box.markdown(
            f'<div class="loader-wrap"><div class="loader-spinner"></div>'
            f'<div class="loader-text">{message}</div></div>',
            unsafe_allow_html=True,
        )
        progress_bar.progress(min(pct, 100))

    agent = Agent(st.session_state.repo_input, status_callback=update_status)
    st.session_state.agent = agent
    st.session_state.file_tree_html = render_tree_html(build_file_tree(agent.repo_path))

    status_box.empty()
    progress_bar.empty()
    st.rerun()

# --- Main layout ---
if not st.session_state.repo_locked:
    st.info("Enter a local folder path or a public GitHub repo URL above, then click **Start**.")

elif "agent" in st.session_state:
    chat_col, tree_col = st.columns([3, 1])

    with chat_col:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

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

    with tree_col:
        st.markdown("**Project files**")
        st.markdown(st.session_state.file_tree_html, unsafe_allow_html=True)