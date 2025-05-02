import streamlit as st
try:
    st.write("API Key:", st.secrets["ANTHROPIC_API_KEY"])
except KeyError:
    st.error("Key not found in secrets.toml.")
