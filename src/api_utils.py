import requests
import streamlit as st
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
import numpy as np
from config import ANTHROPIC_MODEL

# Initialize Anthropic client
try:
    st.write("Initializing Anthropic client...")
    anthropic = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    st.write("Done init Anthropic client...")
except KeyError:
    st.error("Anthropic API key not found. Please set it in secrets.toml.")
    st.stop()

def is_in_doaj(issn):
    url = f"https://api.openalex.org/sources?filter=ids.value:{issn},ids.schema:ISSN"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['meta']['count'] > 0:
                return data['results'][0].get('is_in_doaj', False)
        return False
    except Exception as e:
        st.error(f"Failed to query OpenAlex API: {e}")
        return False

def get_journal_metadata(issn):
    url = f"https://api.openalex.org/sources?filter=ids.value:{issn},ids.schema:ISSN"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['meta']['count'] > 0:
                source = data['results'][0]
                total_works = sum(count['works_count'] for count in source.get('counts_by_year', []))
                works_url = f"https://api.openalex.org/works?filter=source.id:{source['id']}&per-page=100"
                works_response = requests.get(works_url)
                avg_citations = 0
                if works_response.status_code == 200:
                    works_data = works_response.json()
                    citations = [work.get('cited_by_count', 0) for work in works_data.get('results', [])]
                    avg_citations = np.mean(citations) if citations else 0
                return {
                    'total_works': total_works,
                    'avg_citations': avg_citations,
                    'is_in_doaj': source.get('is_in_doaj', False)
                }
        return None
    except Exception as e:
        st.error(f"Failed to fetch journal metadata: {e}")
        return None

def get_claude_confidence(metadata, is_predatory):
    prompt = f"{HUMAN_PROMPT}You are an expert in academic publishing. Given the following journal metadata, provide a confidence score (0-100) indicating the likelihood that the journal is predatory, considering factors like low citation counts, high publication volume, and lack of DOAJ indexing. Metadata: Total Works: {metadata['total_works']}, Average Citations: {metadata['avg_citations']}, In DOAJ: {metadata['is_in_doaj']}. The journal is {'in' if is_predatory else 'not in'} a known predatory journal list. Respond with a single number representing the confidence score.{AI_PROMPT}"
    try:
        response = anthropic.completions.create(
            model=ANTHROPIC_MODEL,
            max_tokens_to_sample=10,
            prompt=prompt
        )
        return int(response.completion.strip())
    except Exception as e:
        st.error(f"Failed to get Claude confidence score: {e}")
        return 50