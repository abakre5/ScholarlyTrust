import pandas as pd
import streamlit as st

@st.cache_data
def load_predatory_journals():
    url = 'https://raw.githubusercontent.com/stop-predatory-journals/stop-predatory-journals.github.io/master/_data/journals.csv'
    try:
        return pd.read_csv(url).dropna(subset=['ISSN'])
    except Exception as e:
        st.error(f"Failed to load predatory journals list: {e}")
        return pd.DataFrame()